"""Hey ficticio: efectivo cobrado, devengo observado y renovación pendiente."""
from pathlib import Path
from decimal import Decimal as D
from io import BytesIO
import re
import tempfile
import unittest
from unittest.mock import patch

from finanzas.book import FinancialBook
from finanzas.intake import Inbox
from finanzas.ledger import Kind, Origin
from tests import test_intake
from tests.test_hey import pages, row
from tests.test_openbank import synthetic_pdf


def content(source=None,*,currency='MXN',next_period=False,cash_offset=0,extra=''):
    source=list(source or pages())
    if next_period:
        source=[p.replace('01 al 30 de NOVIEMBRE 2024','01 al 31 de DICIEMBRE 2024')
            .replace('13/Oct/2024','12/Nov/2024').replace('10/Nov/2024','10/Dic/2024')
            .replace('08/Dic/2024','07/Ene/2025').replace('0000101','0000103').replace('0000102','0000104') for p in source]
    if cash_offset:
        source[0]=source[0].replace('Total Portafolio 1005.00',f'Total Portafolio {D(1005)+cash_offset:.2f}')
        source[1]=source[1].replace('Saldo Inicial $0.00',f'Saldo Inicial ${cash_offset:.2f}').replace('Saldo Final $0.00',f'Saldo Final ${cash_offset:.2f}')
        source[1]='\n'.join(re.sub(r'(\d+\.\d{2})(\s*)$',lambda m:f'{D(m[1])+cash_offset:.2f}'+m[2],line)
            if re.match(r'^10\s',line) else line for line in source[1].splitlines())
    if currency:source[0]+='\nMoneda: '+currency+'\n'
    source[-1]+='\n'+extra
    return synthetic_pdf(source)


def protected_content():
    from pypdf import PdfReader, PdfWriter
    writer=PdfWriter();writer.append(PdfReader(BytesIO(content())))
    writer.encrypt('ONLY-FICTITIOUS-HEY');buffer=BytesIO();writer.write(buffer)
    return buffer.getvalue()


class HeyBookTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'bandeja.sqlite3';self.doc=self.upload(content())
        self.book=FinancialBook(self.path);self.addCleanup(self.book.close)

    def upload(self,data):
        with Inbox(self.path) as inbox:return inbox.upload(data,'ejemplo-ficticio.pdf')

    def confirm(self,doc=None,**kwargs):
        doc=doc or self.doc;plan=self.book.preview(doc['id'],**kwargs)
        self.assertTrue(plan['can_confirm'],plan['issues'])
        return self.book.confirm(doc['id'],revision=plan['revision'],plan_hash=plan['plan_hash'],
            currency_confirmation=plan.get('currency_confirmation'),password=kwargs.get('password'))

    def test_operational_account_without_double_portfolio_or_accrual(self):
        result=self.confirm();summary=self.book.summary()
        self.assertEqual(len(result['periods']),1);self.assertEqual(len(summary['accounts']),1)
        self.assertEqual(summary['accounts'][0]['closing'],'0.00')
        self.assertEqual(len(result['term_snapshots']),2)
        self.assertEqual({s['as_of'] for s in result['term_snapshots']},{'2024-11-30'})
        self.assertEqual(result['investment_summary_observation']['accrued_included_in_final'],'1.00')
        self.assertEqual(result['portfolio_total_reported'],'1005.00')
        self.assertEqual(len(self.book.store.load_ledger().movements),4)

    def test_gross_net_retention_separate_and_paid_once(self):
        self.confirm();ledger=self.book.store.load_ledger()
        self.assertEqual(sum(m.amount for m in ledger.movements if m.kind==Kind.INTEREST),D('5'))
        self.assertEqual(ledger.withholding_recorded('MXN'),D('1'))
        account=self.book.summary()['accounts'][0]
        self.assertEqual(account['interest_net_of_withholding'],'4.00')
        self.assertEqual(account['withholding'],'1.00')

    def test_principal_return_and_new_opening_do_not_create_external_capital(self):
        self.confirm();ledger=self.book.store.load_ledger()
        principal=[m for m in ledger.movements if m.kind==Kind.CONTRIBUTION]
        opened=[m for m in ledger.movements if m.kind==Kind.WITHDRAWAL]
        self.assertEqual([m.amount for m in principal],[D('1000')])
        self.assertEqual([m.amount for m in opened],[D('1004')])
        self.assertTrue(all(m.origin==Origin.UNKNOWN for m in principal+opened))
        self.assertEqual(ledger.external_contributions('MXN'),0)

    def test_renewal_keeps_four_evidences_without_confirmation(self):
        result=self.confirm();proposal=result['renewal_proposals'][0]
        self.assertTrue(proposal['needs_review']);self.assertEqual(proposal['status'],'candidate_requires_review')
        self.assertEqual(len(proposal['source_lines']),4);self.assertEqual(proposal['reinvested'],'1004.00')
        self.assertEqual(result['transfers'],[])
        self.assertFalse(any(m.origin==Origin.REINVESTMENT for m in self.book.store.load_ledger().movements))

    def test_future_tax_and_contract_terms_do_not_replace_cash_tax(self):
        source=pages();source[2]=source[2].replace('1004.00 4.00 1.00 1007.00','1004.00 4.00 2.00 1006.00')
        source[2]=source[2].replace('Total Vigentes 1007.00','Total Vigentes 1006.00')
        result=self.confirm(self.upload(content(source)))
        self.assertEqual(self.book.store.load_ledger().withholding_recorded('MXN'),D('1'))
        active=next(s for s in result['term_snapshots'] if s['status_at_cutoff']=='active')
        self.assertEqual(active['withholding_at_maturity'],'2.00')
        self.assertEqual(active['annual_rate'],'5.00');self.assertEqual(active['gat_real'],'1.00')

    def test_zero_paid_withholding_keeps_explicit_row_not_future_tax(self):
        source=pages();source[0]=source[0].replace('1002.00  4.00  1005.00  1.00  1.00','1002.00  5.00  1006.00  1.00  0.00')
        source[0]=source[0].replace('Total Portafolio 1005.00','Total Portafolio 1006.00')
        source[1]=source[1].replace(row('Ret. ISR de Inversion','888888880000101',debit='1.00',balance='1004.00'),
            row('Ret. ISR de Inversion','888888880000101',debit='0.00',balance='1005.00'))
        source[1]=source[1].replace(row('Apertura de Inversion Hey PER: 1','888888880000102',debit='1004.00',balance='0.00'),
            row('Apertura de Inversion Hey PER: 1','888888880000102',debit='1005.00',balance='0.00'))
        source[2]=source[2].replace('1000.00 5.00 1.00 1004.00','1000.00 5.00 0.00 1005.00')
        source[2]=source[2].replace('1004.00 4.00 1.00 1007.00','1005.00 4.00 1.00 1008.00').replace('Total Vigentes 1007.00','Total Vigentes 1008.00')
        self.confirm(self.upload(content(source)))
        retained=[m for m in self.book.store.load_ledger().movements if m.kind==Kind.WITHHOLDING]
        self.assertEqual(len(retained),1);self.assertEqual(retained[0].amount,0)

    def test_same_contract_reference_different_categories_not_deduplicated(self):
        result=self.confirm();paid=result['movements'][:3]
        self.assertEqual(len({m['reference'] for m in paid}),1)
        self.assertEqual(len({m['id'] for m in paid}),3)
        self.assertTrue(all(m['source_extraction']=='layout' for m in paid))
        self.assertTrue(all(s['source_extraction']=='plain' for s in result['term_snapshots']))

    def test_bad_forecast_or_portfolio_blocks_even_if_cash_reconciles(self):
        for old,new in [('Total Vigentes 1007.00','Total Vigentes 1006.99'),('Total Portafolio 1005.00','Total Portafolio 1004.99')]:
            source=[p.replace(old,new) for p in pages()];plan=self.book.preview(self.upload(content(source))['id'])
            self.assertFalse(plan['can_confirm']);self.assertTrue(plan['issues'])
        self.assertEqual(self.book.summary()['documents'],0)

    def test_missing_currency_requires_document_bound_review(self):
        doc=self.upload(content(currency=None));plan=self.book.preview(doc['id'])
        self.assertTrue(plan['currency_confirmation_required']);self.assertFalse(plan['can_confirm'])
        reviewed=self.book.preview(doc['id'],currency_confirmation='MXN')
        self.assertTrue(reviewed['can_confirm'])
        with self.assertRaises(ValueError):self.book.confirm(doc['id'],revision=1,plan_hash=reviewed['plan_hash'])
        self.confirm(doc,currency_confirmation='MXN')
        self.assertEqual(self.book.preview(doc['id'])['currency_source'],'user_review')

    def test_foreign_conflicting_or_unsupported_currency_not_overridden(self):
        for currency in ('USD','CAD','USD\nMoneda: MXN'):
            plan=self.book.preview(self.upload(content(currency=currency))['id'],currency_confirmation='MXN')
            self.assertFalse(plan['can_confirm']);self.assertFalse(plan['currency_confirmation_required'])

    def test_unknown_concept_or_duplicate_reference_blocks_whole_batch(self):
        source=pages();source[1]=source[1].replace('Pago Intereses de Inv.','Abono desconocido')
        self.assertFalse(self.book.preview(self.upload(content(source))['id'])['can_confirm'])
        source=pages();line=next(l for l in source[1].splitlines() if 'Pago Cap.' in l)
        source[1]=source[1].replace('Gráfico Transaccional',line+'\nGráfico Transaccional')
        self.assertFalse(self.book.preview(self.upload(content(source))['id'])['can_confirm'])

    def test_retry_reopen_overlap_and_out_of_order_months(self):
        self.confirm(self.upload(content(next_period=True)));self.confirm()
        self.assertTrue(self.book.confirm(self.doc['id'],revision=1,plan_hash='retry')['duplicate'])
        with FinancialBook(self.path) as other:self.assertEqual(other.summary()['documents'],2)
        plan=self.book.preview(self.upload(content(extra='Otra representacion'))['id'])
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('superpuesto' in s for s in plan['issues']))

    def test_adjacent_balance_discrepancy_not_adjusted(self):
        self.confirm();doc=self.upload(content(next_period=True,cash_offset=1))
        plan=self.book.preview(doc['id']);self.assertFalse(plan['can_confirm'])
        self.assertTrue(any('cierre anterior' in s for s in plan['issues']),plan['issues'])

    def test_stale_version_and_transaction_rollback(self):
        plan=self.book.preview(self.doc['id'])
        with Inbox(self.path) as inbox:inbox.review(self.doc['id'],expected_revision=1,decision='reviewed')
        with self.assertRaises(ValueError):self.book.confirm(self.doc['id'],revision=1,plan_hash=plan['plan_hash'])
        original=self.book.store.record_many
        def fail(rows):original(rows);raise ValueError('Fallo simulado')
        with patch.object(self.book.store,'record_many',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm()
        self.assertEqual(self.book.summary()['documents'],0);self.assertEqual(self.book.store.load_ledger().movements,())
        self.assertEqual(self.book.store.review_history(self.doc['id']),());self.confirm()

    def test_protected_original_reread_without_saved_password(self):
        with Inbox(self.path) as inbox:doc=inbox.upload(protected_content(),'protegido-ficticio.pdf',password='ONLY-FICTITIOUS-HEY')
        for secret in (None,'WRONG-FICTITIOUS'):
            plan=self.book.preview(doc['id'],password=secret)
            self.assertTrue(plan['password_required']);self.assertFalse(plan['can_confirm'])
        result=self.confirm(doc,password='ONLY-FICTITIOUS-HEY')
        self.assertNotIn('ONLY-FICTITIOUS-HEY',str(result))
        self.assertNotIn('ONLY-FICTITIOUS-HEY',str(list(self.book.db.iterdump())))
        with Inbox(self.path) as inbox:self.assertNotIn('ONLY-FICTITIOUS-HEY',str(list(inbox.db.iterdump())))

    def test_eight_institutions_without_contract_account_collision(self):
        from tests.test_book import content as openbank
        from tests.test_book_mifel import content as mifel
        from tests.test_book_bancoppel import content as bancoppel
        from tests.test_book_didi import content as didi
        from tests.test_book_fondeadora import content as fondeadora
        from tests.test_book_plata import content as plata
        from tests.test_book_supertasas import content as supertasas
        self.confirm()
        for fixture in (openbank,mifel,bancoppel,didi,fondeadora,plata,supertasas):self.confirm(self.upload(fixture()))
        self.assertEqual(self.book.summary()['documents'],8);self.assertEqual(len(self.book.summary()['accounts']),10)


class HeyFinancialHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_currency_review_and_confirmation_with_renewal_proposal_http(self):
        doc=self.request('/api/upload',content(currency=None),raw=True)
        plan=self.request('/api/documents/'+doc['id']+'/plan');self.assertTrue(plan['currency_confirmation_required'])
        plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=1,currency_confirmation='MXN'))
        self.assertTrue(plan['can_confirm']);self.assertEqual(len(plan['renewal_proposals']),1)
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=1,plan_hash=plan['plan_hash'],currency_confirmation='MXN'))
        self.assertEqual(self.request('/api/book')['documents'],1)

    def test_encrypted_reader_and_financial_confirmation_http(self):
        doc=self.request('/api/upload',protected_content(),raw=True)
        self.assertEqual(doc['result']['status'],'needs_password')
        doc=self.request('/api/documents/'+doc['id']+'/reprocess',dict(revision=1,password='ONLY-FICTITIOUS-HEY'))
        plan=self.request('/api/documents/'+doc['id']+'/plan');self.assertTrue(plan['password_required'])
        plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=doc['revision'],password='ONLY-FICTITIOUS-HEY'))
        self.assertTrue(plan['can_confirm'])
        result=self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=doc['revision'],plan_hash=plan['plan_hash'],password='ONLY-FICTITIOUS-HEY'))
        self.assertEqual(result['status'],'imported');self.assertNotIn('ONLY-FICTITIOUS-HEY',str(result))


if __name__=='__main__':unittest.main()
