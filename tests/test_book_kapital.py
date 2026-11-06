"""Kapital ficticio: dos formatos, pagos y timbrado sin capital artificial."""
from pathlib import Path
from decimal import Decimal as D
from io import BytesIO
import tempfile
import unittest
from unittest.mock import patch

from finanzas.book import FinancialBook
from finanzas.intake import Inbox
from finanzas.ledger import Kind, Origin
from tests import test_intake
from tests.test_kapital import current, legacy
from tests.test_openbank import synthetic_pdf


def content(pages=None,*,month=7,currency=None,extra=''):
    pages=list(pages or current(month))
    if currency is not None:
        pages=[p.replace(' MN','').replace('MONEDA NACIONAL','DIVISA PENDIENTE') for p in pages]
        if currency:pages[0]+='\nMoneda: '+currency+'\n'
    pages[-1]+='\n'+extra
    return synthetic_pdf(pages)


def protected_content():
    from pypdf import PdfReader, PdfWriter
    writer=PdfWriter();writer.append(PdfReader(BytesIO(content())))
    writer.encrypt('ONLY-FICTITIOUS-KAPITAL');buffer=BytesIO();writer.write(buffer)
    return buffer.getvalue()


class KapitalBookTests(unittest.TestCase):
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

    def test_operational_account_and_contracts_without_double_portfolio(self):
        result=self.confirm();summary=self.book.summary()
        self.assertEqual(len(result['periods']),1);self.assertEqual(len(summary['accounts']),1)
        self.assertEqual(summary['accounts'][0]['closing'],'0.00')
        self.assertEqual(len(result['term_snapshots']),2)
        self.assertEqual({s['as_of'] for s in result['term_snapshots']},{'2026-07-31'})
        self.assertEqual(result['investment_summary_observation']['final'],'3000.00')
        self.assertEqual(len(self.book.store.load_ledger().movements),3)

    def test_stamp_and_discount_preserve_two_opposite_rows_without_capital(self):
        result=self.confirm();ledger=self.book.store.load_ledger()
        self.assertEqual({m.kind for m in ledger.movements},{Kind.FEE,Kind.FEE_REFUND,Kind.WITHHOLDING})
        self.assertEqual(ledger.external_contributions('MXN'),0);self.assertEqual(ledger.interest_received('MXN'),0)
        self.assertEqual(ledger.pending_origins(),())
        self.assertEqual(sum(m.signed_amount for m in ledger.movements),0)
        self.assertEqual(self.book.summary()['accounts'][0]['charges_fees_and_vat'],'0.00')
        self.assertEqual(result['movements'][0]['reference'],result['movements'][1]['reference'])

    def test_maturity_principal_gross_and_actual_tax_once(self):
        result=self.confirm(self.upload(content(month=8)));ledger=self.book.store.load_ledger()
        self.assertEqual(ledger.interest_received('MXN'),D('100'))
        self.assertEqual(ledger.withholding_recorded('MXN'),D('10'))
        self.assertEqual([m.amount for m in ledger.movements if m.kind==Kind.CONTRIBUTION],[D('1000')])
        self.assertEqual(ledger.external_contributions('MXN'),0)
        self.assertEqual(self.book.summary()['accounts'][0]['interest_net_of_withholding'],'90.00')
        self.assertEqual(result['periods'][0]['final'],'1090.00')

    def test_legacy_opening_is_reduction_unknown_origin_and_forecast_tax_unknown(self):
        result=self.confirm(self.upload(content(legacy())));ledger=self.book.store.load_ledger()
        opened=next(m for m in result['movements'] if m.get('category')=='investment_opening')
        self.assertEqual(opened['kind'],Kind.WITHDRAWAL.value);self.assertEqual(opened['withdrawal_printed'],'-1000.00')
        self.assertEqual(opened['origin'],Origin.UNKNOWN.value)
        self.assertIsNone(result['term_snapshots'][0]['retention_at_maturity'])
        self.assertIsNone(result['term_snapshots'][0]['net_at_maturity'])
        self.assertEqual(ledger.interest_received('MXN'),0);self.assertEqual(ledger.external_contributions('MXN'),0)
        self.assertEqual(result['transfers'],[])

    def test_future_tax_does_not_become_paid_withholding(self):
        result=self.confirm();ledger=self.book.store.load_ledger()
        self.assertEqual(result['term_snapshots'][0]['retention_at_maturity'],'10.00')
        self.assertEqual(ledger.withholding_recorded('MXN'),0)
        self.assertEqual(sum(m.kind==Kind.WITHHOLDING for m in ledger.movements),1)

    def test_real_uncompensated_fee_remains_charge(self):
        pages=current(8)
        pages[0]='\n'.join(l for l in pages[0].splitlines() if 'DESCUENTO POR TIMBRADO FISCAL' not in l)
        pages[0]=pages[0].replace('+ Depósitos 1100.01','+ Depósitos 1100.00')
        pages[0]=pages[0].replace('- Comisiones Efectivamente 0.00','- Comisiones Efectivamente 0.01')
        pages[0]=pages[0].replace('Saldo Final 1090.00','Saldo Final 1089.99')
        self.confirm(self.upload(content(pages)))
        self.assertEqual(self.book.summary()['accounts'][0]['charges_fees_and_vat'],'0.01')
        self.assertFalse(any(m.kind==Kind.FEE_REFUND for m in self.book.store.load_ledger().movements))

    def test_contract_discrepancy_or_unknown_concept_blocks_whole_batch(self):
        for old,new in [('1090.00','1089.99'),('COMISIÓN POR TIMBRADO FISCAL','OTRO CARGO'.ljust(26))]:
            pages=[p.replace(old,new) for p in current()]
            self.assertFalse(self.book.preview(self.upload(content(pages))['id'])['can_confirm'])
        self.assertEqual(self.book.summary()['documents'],0)

    def test_duplicate_same_reference_category_is_not_silently_deleted(self):
        pages=current();line=next(l for l in pages[0].splitlines() if 'COMISIÓN POR' in l)
        pages[0]=pages[0].replace('\nTotal\n','\n'+line+'\nTotal\n')
        plan=self.book.preview(self.upload(content(pages))['id'])
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('repetida' in i for i in plan['issues']))

    def test_missing_currency_requires_bound_review(self):
        doc=self.upload(content(currency=''));plan=self.book.preview(doc['id'])
        self.assertTrue(plan['currency_confirmation_required']);self.assertFalse(plan['can_confirm'])
        reviewed=self.book.preview(doc['id'],currency_confirmation='MXN');self.assertTrue(reviewed['can_confirm'])
        with self.assertRaises(ValueError):self.book.confirm(doc['id'],revision=1,plan_hash=reviewed['plan_hash'])
        self.confirm(doc,currency_confirmation='MXN')
        self.assertEqual(self.book.preview(doc['id'])['currency_source'],'user_review')

    def test_foreign_or_contradictory_currency_not_overridden(self):
        for currency in ('USD','CAD','USD\nMoneda: MXN'):
            plan=self.book.preview(self.upload(content(currency=currency))['id'],currency_confirmation='MXN')
            self.assertFalse(plan['can_confirm']);self.assertFalse(plan['currency_confirmation_required'])

    def test_nonzero_cheques_interest_requires_specific_detail(self):
        pages=current();pages[0]=pages[0].replace('+ Intereses Brutos Cheques 0.00','+ Intereses Brutos Cheques 1.00')
        plan=self.book.preview(self.upload(content(pages))['id'])
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('cheques' in s for s in plan['issues']))

    def test_retry_reopen_out_of_order_months_and_overlap(self):
        self.confirm(self.upload(content(month=8)));self.confirm()
        self.assertTrue(self.book.confirm(self.doc['id'],revision=1,plan_hash='retry')['duplicate'])
        with FinancialBook(self.path) as other:self.assertEqual(other.summary()['documents'],2)
        plan=self.book.preview(self.upload(content(extra='Otra representacion'))['id'])
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('superpuesto' in s for s in plan['issues']))

    def test_both_formats_preserve_identifiers_without_automatic_alias_or_reinvestment(self):
        old=self.confirm(self.upload(content(legacy())));new=self.confirm()
        self.assertEqual(old['term_snapshots'][0]['id'],'LD0001')
        self.assertEqual(new['term_snapshots'][0]['id'],'11111100026001')
        self.assertEqual(len(self.book.summary()['accounts']),1)
        self.assertTrue(self.book.summary()['accounts'][0]['gaps'])
        self.assertFalse(any(m.origin==Origin.REINVESTMENT for m in self.book.store.load_ledger().movements))

    def test_stale_version_and_failure_rollback_refund_and_period(self):
        plan=self.book.preview(self.doc['id'])
        with Inbox(self.path) as inbox:inbox.review(self.doc['id'],expected_revision=1,decision='reviewed')
        with self.assertRaises(ValueError):self.book.confirm(self.doc['id'],revision=1,plan_hash=plan['plan_hash'])
        original=self.book.store.record_many
        def fail(rows):original(rows);raise ValueError('Fallo simulado')
        with patch.object(self.book.store,'record_many',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm()
        self.assertEqual(self.book.summary()['documents'],0);self.assertEqual(self.book.store.load_ledger().movements,())
        self.assertEqual(self.book.store.review_history(self.doc['id']),());self.confirm()

    def test_protected_original_reopened_without_saving_password(self):
        with Inbox(self.path) as inbox:doc=inbox.upload(protected_content(),'protegido-ficticio.pdf',password='ONLY-FICTITIOUS-KAPITAL')
        for secret in (None,'WRONG-FICTITIOUS'):
            plan=self.book.preview(doc['id'],password=secret)
            self.assertTrue(plan['password_required']);self.assertFalse(plan['can_confirm'])
        result=self.confirm(doc,password='ONLY-FICTITIOUS-KAPITAL')
        self.assertNotIn('ONLY-FICTITIOUS-KAPITAL',str(result))
        self.assertNotIn('ONLY-FICTITIOUS-KAPITAL',str(list(self.book.db.iterdump())))
        with Inbox(self.path) as inbox:self.assertNotIn('ONLY-FICTITIOUS-KAPITAL',str(list(inbox.db.iterdump())))

    def test_nine_institutions_without_contract_account_collision(self):
        from tests.test_book import content as openbank
        from tests.test_book_mifel import content as mifel
        from tests.test_book_bancoppel import content as bancoppel
        from tests.test_book_didi import content as didi
        from tests.test_book_fondeadora import content as fondeadora
        from tests.test_book_plata import content as plata
        from tests.test_book_supertasas import content as supertasas
        from tests.test_book_hey import content as hey
        self.confirm()
        for fixture in (openbank,mifel,bancoppel,didi,fondeadora,plata,supertasas,hey):self.confirm(self.upload(fixture()))
        self.assertEqual(self.book.summary()['documents'],9);self.assertEqual(len(self.book.summary()['accounts']),11)


class KapitalFinancialHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_currency_review_and_refund_confirmation_http(self):
        doc=self.request('/api/upload',content(currency=''),raw=True)
        plan=self.request('/api/documents/'+doc['id']+'/plan');self.assertTrue(plan['currency_confirmation_required'])
        plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=1,currency_confirmation='MXN'))
        self.assertTrue(plan['can_confirm'])
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=1,plan_hash=plan['plan_hash'],currency_confirmation='MXN'))
        self.assertEqual(self.request('/api/book')['accounts'][0]['charges_fees_and_vat'],'0.00')

    def test_encrypted_reader_and_confirmation_http(self):
        doc=self.request('/api/upload',protected_content(),raw=True)
        self.assertEqual(doc['result']['status'],'needs_password')
        doc=self.request('/api/documents/'+doc['id']+'/reprocess',dict(revision=1,password='ONLY-FICTITIOUS-KAPITAL'))
        plan=self.request('/api/documents/'+doc['id']+'/plan');self.assertTrue(plan['password_required'])
        plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=doc['revision'],password='ONLY-FICTITIOUS-KAPITAL'))
        self.assertTrue(plan['can_confirm'])
        result=self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=doc['revision'],plan_hash=plan['plan_hash'],password='ONLY-FICTITIOUS-KAPITAL'))
        self.assertEqual(result['status'],'imported')


if __name__=='__main__':unittest.main()
