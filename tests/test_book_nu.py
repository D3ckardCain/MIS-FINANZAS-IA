"""Nu ficticio: revisión de agregados, dos cuentas y traspasos sin inventar Cajitas."""
from dataclasses import replace
from decimal import Decimal as D
from io import BytesIO
from pathlib import Path
import copy
import tempfile
import unittest
from unittest.mock import patch

from finanzas.book import FinancialBook
from finanzas.intake import Inbox
from finanzas.ledger import Kind,Origin
from tests.test_nu import statement
from tests.test_openbank import synthetic_pdf
from tests import test_intake


def source(*,next_period=False,guarantee=False,zero=False,currency=True,issuer=False):
    pages=statement()
    pages[1]=pages[1].replace('Nu México Financiera','06 ENE 2026 Compra con tarjeta FICTICIA -$22.00\nNu México Financiera')
    pages[2]=pages[2].replace('+$100.00','-$100.00')
    if currency:pages[0]+='\nMoneda: MXN'
    if next_period:
        pages=[p.replace('DEL 01 AL 31 ENE 2026','DEL 01 AL 28 FEB 2026').replace('05 ENE','05 FEB').replace('06 ENE','06 FEB') for p in pages]
        pages[0]=pages[0].replace('Saldo inicial $100.00','Saldo inicial $130.00').replace('estado de cuenta $130.00','estado de cuenta $160.00')
        pages[0]=pages[0].replace('$5.00  $125.00','$13.00  $147.00').replace('24/7 $25.00','24/7 $47.00')
        pages[1]=pages[1].replace('FICTICIA -$50.00','FICTICIA -$20.00')
        pages[2]=pages[2].replace('FICTICIA +$50.00','FICTICIA +$20.00')
        pages[2]='\n'.join(l for l in pages[2].splitlines() if 'Congelaste' not in l)
    if guarantee:
        pages[0]=pages[0].replace('$5.00  $125.00  $0.00','$5.00  $115.00  $10.00').replace('24/7 $25.00','24/7 $15.00')
        pages.insert(3,'Cuenta Nu: 00011111111\nDetalle de movimientos de tu Cajita Nu Crédito\nSin movimientos\nNu México Financiera')
    if zero:
        import re
        pages=[re.sub(r'\$\d+\.\d{2}','$0.00',p) for p in pages]
        pages[1]='Cuenta Nu: 00011111111\nDetalle de movimientos en tu cuenta\nFECHA DEL 01 AL 31 ENE 2026\nSin movimientos\nNu México Financiera'
        pages[2]='Cuenta Nu: 00011111111\nDetalle de movimientos de tus cajitas\nSin movimientos\nNu México Financiera'
    if issuer:pages=[p.replace('Nu México Financiera','Nubank, S.A., Institución de Banca Múltiple') for p in pages]
    return pages


def content(**kwargs):return synthetic_pdf(source(**kwargs))


def review(doc,*,next_period=False,guarantee=False,zero=False):
    buckets=dict(debit=dict(initial='5.00' if next_period else '27.00',gross_interest='0.00',withholding='0.00'),
        investments=dict(initial='125.00' if next_period else '63.00' if guarantee else '73.00',gross_interest='2.10',withholding='0.10'))
    if guarantee:buckets['guarantee']=dict(initial='10.00',gross_interest='0.00',withholding='0.00')
    if zero:
        for b in buckets.values():
            for key in b:b[key]='0.00'
    return dict(nu=dict(document_id=doc['id'],revision=doc['revision'],buckets=buckets))


def protected():
    from pypdf import PdfReader,PdfWriter
    w=PdfWriter();w.append(PdfReader(BytesIO(content())));w.encrypt('ONLY-FICTITIOUS-NU');out=BytesIO();w.write(out);return out.getvalue()


class NuBookTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'bandeja.sqlite3';self.book=FinancialBook(self.path);self.addCleanup(self.book.close)
        self.doc=self.upload(content())

    def upload(self,data,**kwargs):
        with Inbox(self.path) as inbox:return inbox.upload(data,'ficticio.pdf',**kwargs)

    def confirm(self,doc=None,allocation=None,**kwargs):
        doc=doc or self.doc;allocation=allocation or review(doc)
        plan=self.book.preview(doc['id'],operation_review=allocation,**kwargs)
        self.assertTrue(plan['can_confirm'],plan['issues'])
        return self.book.confirm(doc['id'],revision=doc['revision'],plan_hash=plan['plan_hash'],operation_review=allocation,**kwargs)

    def test_missing_distribution_blocks_and_never_writes_financial_data(self):
        plan=self.book.preview(self.doc['id']);self.assertFalse(plan['can_confirm']);self.assertTrue(plan['nu_review_required'])
        self.assertEqual(len(plan['nu_buckets']),2);self.assertEqual(self.book.store.load_ledger().movements,())
        self.assertEqual(self.book.evolution()['accounts'],[])

    def test_two_accounts_close_without_consolidated_or_frozen_double_count(self):
        plan=self.confirm();summary=self.book.summary();accounts={a['lane']:a for a in summary['accounts']}
        self.assertEqual(len(accounts),2);self.assertEqual(accounts['debit']['closing'],'5.00')
        self.assertEqual(accounts['investments']['closing'],'125.00');self.assertEqual(accounts['investments']['role'],'cajitas_aggregate')
        self.assertEqual(plan['nu_summary_observation']['final'],'130.00')
        self.assertEqual(len(plan['nu_freeze_observations']),1)
        self.assertFalse(any(m.kind==Kind.OPENING for m in self.book.store.load_ledger().movements))
        self.assertEqual({m.origin for m in self.book.store.load_ledger().movements if m.origin},{Origin.UNKNOWN,Origin.OWN_TRANSFER})
        self.assertTrue(all(r['reconciled'] for a in self.book.evolution()['accounts'] for r in a['history']))

    def test_transfer_destination_contribution_origin_reduction_and_external_capital_zero(self):
        self.confirm();ledger=self.book.store.load_ledger();legs=[m for m in ledger.movements if m.origin==Origin.OWN_TRANSFER]
        self.assertEqual(len(legs),2);self.assertEqual(sum(m.signed_amount for m in legs),0)
        self.assertEqual(ledger.external_contributions('MXN'),0);self.assertEqual(ledger.pending_transfers(),())
        self.assertEqual(sum(m.amount for m in legs if m.kind==Kind.CONTRIBUTION),50)

    def test_global_income_tax_once_at_document_close_not_guessed_daily_payment(self):
        plan=self.confirm();ledger=self.book.store.load_ledger()
        self.assertEqual(ledger.interest_received('MXN'),D('2.10'));self.assertEqual(ledger.withholding_recorded('MXN'),D('.10'))
        tax=[m for m in plan['movements'] if m['kind']==Kind.WITHHOLDING]
        self.assertEqual(len(tax),2);self.assertEqual({m['effective_date'] for m in tax},{'2026-01-31'})
        self.assertEqual({m['date_basis'] for m in tax},{'period_close_summary'})
        self.assertEqual({m['allocation_source'] for m in tax},{'user_review'})
        self.assertEqual(plan['nu_summary_observation']['isr_rate_reported'],'0.9')

    def test_wrong_totals_or_correct_global_but_wrong_per_product_close_block(self):
        for field,value in [('initial','74.00'),('gross_interest','3.10'),('withholding','0.11')]:
            r=review(self.doc);r['nu']['buckets']['investments'][field]=value
            self.assertFalse(self.book.preview(self.doc['id'],operation_review=r)['can_confirm'])
        r=review(self.doc);r['nu']['buckets']['debit']['gross_interest']='1.00';r['nu']['buckets']['investments']['gross_interest']='1.10'
        plan=self.book.preview(self.doc['id'],operation_review=r);self.assertFalse(plan['can_confirm'])
        self.assertTrue(any('Cierre Nu' in s for s in plan['issues']))

    def test_invalid_or_stale_reviews_cannot_be_confirmed(self):
        for bad in [None,True,1,'NaN','Infinity','-1','1e3','0.'+'1'*31]:
            r=review(self.doc);r['nu']['buckets']['debit']['initial']=bad
            self.assertFalse(self.book.preview(self.doc['id'],operation_review=r)['can_confirm'])
        for key,value in [('document_id','otro'),('revision',True),('revision',2)]:
            r=review(self.doc);r['nu'][key]=value
            self.assertFalse(self.book.preview(self.doc['id'],operation_review=r)['can_confirm'])
        for r in ({},dict(nu=[]),dict(nu=review(self.doc)['nu'],unknown={})):
            self.assertFalse(self.book.preview(self.doc['id'],operation_review=r)['can_confirm'])

    def test_missing_unknown_product_and_unknown_component_reviews_rejected(self):
        for action in ('missing','extra','field'):
            r=review(self.doc)
            if action=='missing':del r['nu']['buckets']['debit']
            elif action=='extra':r['nu']['buckets']['inventada']=r['nu']['buckets']['debit']
            else:r['nu']['buckets']['debit']['fake']='0'
            self.assertFalse(self.book.preview(self.doc['id'],operation_review=r)['can_confirm'])

    def test_guarantee_is_separate_not_duplicated_in_cajitas(self):
        doc=self.upload(content(guarantee=True));self.confirm(doc,review(doc,guarantee=True));accounts=self.book.summary()['accounts']
        self.assertEqual(len(accounts),3);self.assertEqual(sum(D(a['closing']) for a in accounts),130)
        self.assertEqual(next(a['role'] for a in accounts if a['lane']=='guarantee'),'collateral')

    def test_missing_tables_unknown_concepts_and_bad_freeze_sign_block_even_reviewed(self):
        for change in ('table','concept','freeze','counterpart','amount','date'):
            pages=source()
            if change=='table':pages[2]=pages[2].replace('Detalle de movimientos de tus cajitas','Tabla ausente')
            elif change=='concept':pages[1]=pages[1].replace('Compra con tarjeta','Concepto desconocido')
            elif change=='freeze':pages[2]=pages[2].replace('-$100.00','+$100.00')
            elif change=='counterpart':pages[2]=pages[2].replace('Depósito en Cajita: FICTICIA','Depósito en Cajita: OTRA')
            elif change=='amount':pages[1]=pages[1].replace('+$50.00','+$49.00')
            else:pages[1]=pages[1].replace('06 ENE','06 FEB')
            doc=self.upload(synthetic_pdf(pages));self.assertFalse(self.book.preview(doc['id'],operation_review=review(doc))['can_confirm'],change)

    def test_gross_external_deposits_and_expenses_checked_not_only_net(self):
        pages=source();pages[1]=pages[1].replace('Nu México Financiera','07 ENE 2026 Depósito SPEI +$1.00\n08 ENE 2026 Transferencia SPEI -$1.00\nNu México Financiera')
        doc=self.upload(synthetic_pdf(pages));plan=self.book.preview(doc['id'],operation_review=review(doc))
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('por separado' in s for s in plan['issues']))

    def test_absent_currency_can_be_reviewed_but_contradictory_currency_cannot(self):
        doc=self.upload(content(currency=False));r=review(doc)
        plan=self.book.preview(doc['id'],operation_review=r);self.assertTrue(plan['currency_confirmation_required'])
        self.confirm(doc,r,currency_confirmation='MXN')
        pages=source();pages[0]+='\nMoneda: USD\n'
        doc=self.upload(synthetic_pdf(pages));self.assertFalse(self.book.preview(doc['id'],operation_review=review(doc),currency_confirmation='MXN')['can_confirm'])

    def test_months_out_of_order_contiguous_openings_and_overlap_control(self):
        feb=self.upload(content(next_period=True));self.confirm(feb,review(feb,next_period=True));self.confirm()
        self.assertEqual(self.book.summary()['documents'],2)
        self.assertTrue(all(not a['gaps'] for a in self.book.summary()['accounts']))
        self.assertEqual([D(h['final']) for a in self.book.evolution()['accounts'] if a['lane']=='investments' for h in a['history']],[125,147])
        pages=source();pages[-1]+='\nOtra representación ficticia'
        doc=self.upload(synthetic_pdf(pages));self.assertFalse(self.book.preview(doc['id'],operation_review=review(doc))['can_confirm'])

    def test_prior_closing_does_not_auto_allocate_nonzero_income(self):
        self.confirm();feb=self.upload(content(next_period=True));plan=self.book.preview(feb['id'])
        self.assertTrue(plan['nu_review_required']);self.assertEqual({b['key']:b['previous_initial'] for b in plan['nu_buckets']},{'debit':'5.00','investments':'125.00'})

    def test_zero_month_still_needs_first_opening_but_later_zero_month_links_prior(self):
        doc=self.upload(content(zero=True));self.assertTrue(self.book.preview(doc['id'])['nu_review_required']);self.confirm(doc,review(doc,zero=True))
        pages=[p.replace('DEL 01 AL 31 ENE 2026','DEL 01 AL 28 FEB 2026') for p in source(zero=True)]
        feb=self.upload(synthetic_pdf(pages));plan=self.book.preview(feb['id'])
        self.assertTrue(plan['can_confirm'],plan['issues']);self.assertEqual(plan['allocation_source'],'zero_global_and_previous_closing')
        self.book.confirm(feb['id'],revision=1,plan_hash=plan['plan_hash'])
        self.assertEqual(self.book.store.load_ledger().withholding_recorded('MXN'),0)

    def test_changed_review_hash_and_stale_revision_write_nothing(self):
        r=review(self.doc);plan=self.book.preview(self.doc['id'],operation_review=r)
        other=copy.deepcopy(r);other['nu']['buckets']['debit']['initial']='26';other['nu']['buckets']['investments']['initial']='74'
        other['nu']['buckets']['debit']['gross_interest']='1';other['nu']['buckets']['investments']['gross_interest']='1.10'
        self.assertTrue(self.book.preview(self.doc['id'],operation_review=other)['can_confirm'])
        with self.assertRaises(ValueError):self.book.confirm(self.doc['id'],revision=1,plan_hash=plan['plan_hash'],operation_review=other)
        with Inbox(self.path) as inbox:inbox.review(self.doc['id'],expected_revision=1,decision='reviewed')
        with self.assertRaises(ValueError):self.book.confirm(self.doc['id'],revision=1,plan_hash=plan['plan_hash'],operation_review=r)
        self.assertEqual(self.book.summary()['documents'],0)

    def test_failure_rolls_back_and_retry_reopen_does_not_duplicate(self):
        original=self.book.store.record_many
        def fail(rows):original(rows);raise ValueError('Fallo ficticio')
        with patch.object(self.book.store,'record_many',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm()
        self.assertEqual(self.book.summary()['documents'],0);self.assertEqual(self.book.store.load_ledger().movements,())
        self.assertEqual(self.book.store.review_history(self.doc['id']),());self.confirm()
        self.assertTrue(self.book.confirm(self.doc['id'],revision=1,plan_hash='retry')['duplicate'])
        with FinancialBook(self.path) as other:self.assertEqual(other.summary()['documents'],1)

    def test_protected_pdf_password_transient_and_banking_issuer_supported(self):
        doc=self.upload(protected(),password='ONLY-FICTITIOUS-NU')
        self.assertTrue(self.book.preview(doc['id'])['password_required'])
        self.confirm(doc,review(doc),password='ONLY-FICTITIOUS-NU')
        self.assertNotIn('ONLY-FICTITIOUS-NU',str(list(self.book.db.iterdump())))
        doc=self.upload(content(issuer=True));plan=self.book.preview(doc['id'],operation_review=review(doc))
        self.assertEqual(plan['issuer_reported'],'Nubank, S.A., Institución de Banca Múltiple')
        self.assertFalse(plan['can_confirm']) # Same account/period cannot enter twice under another issuer label.


class NuFinancialHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_http_review_confirm_and_evolution_separate_products(self):
        doc=self.request('/api/upload',content(),raw=True)
        self.assertTrue(self.request('/api/documents/'+doc['id']+'/plan')['nu_review_required'])
        r=review(doc);plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=1,operation_review=r))
        self.assertTrue(plan['can_confirm'],plan['issues'])
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=1,plan_hash=plan['plan_hash'],operation_review=r))
        self.assertEqual(len(self.request('/api/book/evolution')['accounts']),2)

    def test_http_encrypted_original_reprocess_plan_and_confirm(self):
        doc=self.request('/api/upload',protected(),raw=True)
        doc=self.request('/api/documents/'+doc['id']+'/reprocess',dict(revision=1,password='ONLY-FICTITIOUS-NU'))
        r=review(doc);plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=doc['revision'],password='ONLY-FICTITIOUS-NU',operation_review=r))
        self.assertTrue(plan['can_confirm'],plan['issues'])
        result=self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=doc['revision'],plan_hash=plan['plan_hash'],password='ONLY-FICTITIOUS-NU',operation_review=r))
        self.assertEqual(result['status'],'imported')
        self.assertNotIn('ONLY-FICTITIOUS-NU',str(result))


if __name__=='__main__':unittest.main()
