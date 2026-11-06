"""Fondeadora: efectivo, evidencia de Apartado y moneda revisada sin inventar saldo."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from finanzas.book import FinancialBook
from finanzas.intake import Inbox
from finanzas.ledger import Kind, Origin
from tests import test_intake
from tests.test_fondeadora import statement, report
from tests.test_openbank import synthetic_pdf
from tests.test_book import content as openbank_content
from tests.test_book_mifel import content as mifel_content
from tests.test_book_bancoppel import content as bancoppel_content
from tests.test_book_didi import content as didi_content


def content(*,empty=False,currency='MXN',extra='',next_period=False):
    pages=statement(explained=True,empty=empty)
    if next_period:pages=[p.replace('Enero 1-Enero 31','Febrero 1-Febrero 28').replace('/01/2026','/02/2026') for p in pages]
    if currency:pages[0]+='\n'+currency+'\n'
    pages[-1]+='\n'+extra
    return synthetic_pdf(pages)


class FondeadoraBookTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'bandeja.sqlite3';self.doc=self.upload(content())
        self.book=FinancialBook(self.path);self.addCleanup(self.book.close)

    def upload(self,data):
        with Inbox(self.path) as inbox:return inbox.upload(data,'ejemplo-ficticio.pdf')

    def confirm(self,doc=None,**kwargs):
        doc=doc or self.doc;plan=self.book.preview(doc['id'],**kwargs);self.assertTrue(plan['can_confirm'],plan['issues'])
        return self.book.confirm(doc['id'],revision=plan['revision'],plan_hash=plan['plan_hash'],
            currency_confirmation=plan.get('currency_confirmation'))

    def test_operational_account_and_unverified_vault_transfer_do_not_create_two_balances(self):
        result=self.confirm();ledger=self.book.store.load_ledger()
        self.assertEqual(len(result['periods']),1);self.assertEqual(result['periods'][0]['lane'],'debit')
        self.assertIsNone(result['investment_balance']);self.assertEqual(result['transfers'],[])
        self.assertEqual(len(result['investment_transfer_evidence']),1)
        self.assertEqual(len(ledger.movements),3)
        self.assertEqual(ledger.external_contributions('MXN'),0)
        self.assertTrue(all(m.origin==Origin.UNKNOWN for m in ledger.movements if m.kind in (Kind.CONTRIBUTION,Kind.WITHDRAWAL)))
        self.assertEqual(len(self.book.summary()['accounts']),1)
        self.assertEqual(self.book.summary()['accounts'][0]['closing'],'0.00')

    def test_empty_explicit_table_is_valid_but_does_not_prove_zero_investment(self):
        result=self.confirm(self.upload(content(empty=True)))
        self.assertEqual(len(self.book.store.load_ledger().movements),1)
        self.assertEqual(self.book.store.load_ledger().withholding_recorded('MXN'),0)
        self.assertIsNone(result['investment_balance']);self.assertEqual(result['movements'][0]['amount'],'0.00')

    def test_missing_currency_is_blocked_until_explicit_review_is_bound_to_confirmation(self):
        doc=self.upload(content(currency=None));plan=self.book.preview(doc['id'])
        self.assertFalse(plan['can_confirm']);self.assertTrue(plan['currency_confirmation_required'])
        reviewed=self.book.preview(doc['id'],expected_revision=1,currency_confirmation='MXN')
        self.assertTrue(reviewed['can_confirm']);self.assertEqual(reviewed['currency_source'],'user_review')
        with self.assertRaises(ValueError):self.book.confirm(doc['id'],revision=1,plan_hash=reviewed['plan_hash'])
        self.assertEqual(self.book.summary()['documents'],0)
        accepted=self.book.confirm(doc['id'],revision=1,plan_hash=reviewed['plan_hash'],currency_confirmation='MXN')
        self.assertEqual(accepted['currency_confirmation'],'MXN')
        self.assertEqual(self.book.preview(doc['id'])['currency_source'],'user_review')

    def test_currency_review_does_not_apply_to_other_documents_or_override_printed_foreign_currency(self):
        first=self.upload(content(currency=None));self.confirm(first,currency_confirmation='MXN')
        other=self.upload(content(currency=None,extra='Archivo diferente'))
        self.assertTrue(self.book.preview(other['id'])['currency_confirmation_required'])
        for unit in ('USD','MXN USD'):
            doc=self.upload(content(currency=unit));plan=self.book.preview(doc['id'],currency_confirmation='MXN')
            self.assertFalse(plan['can_confirm']);self.assertFalse(plan['currency_confirmation_required'])

    def test_stale_currency_review_or_plan_cannot_confirm(self):
        doc=self.upload(content(currency=None));plan=self.book.preview(doc['id'],currency_confirmation='MXN')
        with Inbox(self.path) as inbox:inbox.review(doc['id'],expected_revision=1,decision='reviewed')
        with self.assertRaises(ValueError):self.book.preview(doc['id'],expected_revision=1,currency_confirmation='MXN')
        with self.assertRaises(ValueError):self.book.confirm(doc['id'],revision=1,plan_hash=plan['plan_hash'],currency_confirmation='MXN')
        self.assertEqual(self.book.summary()['documents'],0)

    def test_movement_report_with_unknown_balances_is_not_imported_as_empty(self):
        doc=self.upload(synthetic_pdf(report()));plan=self.book.preview(doc['id'],currency_confirmation='MXN')
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('reporte' in s for s in plan['issues']))
        self.assertEqual(self.book.summary()['movements'],0)

    def test_summary_only_or_unexplained_transfer_stays_blocked(self):
        for pages in (statement(),statement(empty=True)[:1]):
            pages[0]+='\nMXN\n';plan=self.book.preview(self.upload(synthetic_pdf(pages))['id'])
            self.assertFalse(plan['can_confirm'])

    def test_nonzero_purchases_fees_or_tax_do_not_become_capital_reductions(self):
        for label in ('Compras','Comisiones totales','Impuestos retenidos'):
            pages=statement(explained=True)
            pages[0]=pages[0].replace(label+' $0.00',label+' $100.00').replace('Retiros $100.00','Retiros $0.00')+'\nMXN\n'
            plan=self.book.preview(self.upload(synthetic_pdf(pages))['id']);self.assertFalse(plan['can_confirm'])
            self.assertTrue(any('mapeo' in s for s in plan['issues']),plan['issues'])

    def test_inverted_dates_do_not_get_sorted_to_make_balances_fit(self):
        pages=statement(explained=True);pages[0]+='\nMXN\n'
        pages[1]=pages[1].replace('02/01/2026','04/01/2026')
        plan=self.book.preview(self.upload(synthetic_pdf(pages))['id'])
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('Secuencia' in s for s in plan['issues']))

    def test_equal_transfer_amounts_keep_separate_evidence_and_no_invented_destinations(self):
        pages=statement(explained=True);pages[0]+='\nMXN\n'
        pages[1]=pages[1].replace('03/01/2026  Traspaso entre cuentas FONDEA  $100.00  $0.00  $0.00',
            '03/01/2026  Traspaso entre cuentas FONDEA  $50.00  $0.00  $50.00\n03/01/2026  Traspaso entre cuentas FONDEA  $50.00  $0.00  $0.00')
        result=self.confirm(self.upload(synthetic_pdf(pages)))
        evidence=result['investment_transfer_evidence'];self.assertEqual(len(evidence),2)
        self.assertNotEqual(evidence[0]['locator'],evidence[1]['locator'])
        self.assertEqual(result['transfers'],[]);self.assertEqual(len(self.book.summary()['accounts']),1)

    def test_zero_and_blank_rates_remain_distinct(self):
        plain=self.confirm();self.assertIsNone(plain['reported_terms']['annual_rate_reported'])
        pages=statement(explained=True,empty=True)
        pages[0]=pages[0].replace('antes de impuestos %','antes de impuestos 0.00%')+'\nMXN\n'
        with FinancialBook(self.path) as other:
            doc=self.upload(synthetic_pdf(pages));plan=other.preview(doc['id'])
            self.assertEqual(plan['reported_terms']['annual_rate_reported'],'0.00')
            self.assertFalse(plan['can_confirm'])  # Ya existe un estado de ese período.

    def test_retry_reopen_overlap_and_out_of_order_periods(self):
        self.confirm(self.upload(content(next_period=True)));self.confirm()
        again=self.book.confirm(self.doc['id'],revision=1,plan_hash='retry');self.assertTrue(again['duplicate'])
        with FinancialBook(self.path) as other:self.assertEqual(other.summary()['documents'],2)
        overlap=self.book.preview(self.upload(content(extra='Otra representacion'))['id'])
        self.assertFalse(overlap['can_confirm']);self.assertTrue(any('superpuesto' in s for s in overlap['issues']))

    def test_failure_after_writes_rolls_back_approval_and_financial_movements(self):
        original=self.book.store.record_many
        def fail(rows):original(rows);raise ValueError('Fallo simulado')
        with patch.object(self.book.store,'record_many',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm()
        self.assertEqual(self.book.summary()['documents'],0)
        self.assertEqual(self.book.store.load_ledger().movements,())
        self.assertEqual(self.book.store.review_history(self.doc['id']),())
        self.confirm()

    def test_five_institutions_coexist_without_creating_a_vault(self):
        self.confirm()
        for data in (openbank_content(),mifel_content(),bancoppel_content(),didi_content()):self.confirm(self.upload(data))
        summary=self.book.summary();self.assertEqual(summary['documents'],5)
        self.assertEqual(len(summary['accounts']),6)
        self.assertEqual(sum(a['institution']=='fondeadora' for a in summary['accounts']),1)


class FondeadoraFinancialHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_currency_choice_plan_and_confirmation_http(self):
        doc=self.request('/api/upload',content(currency=None),raw=True)
        plan=self.request('/api/documents/'+doc['id']+'/plan');self.assertTrue(plan['currency_confirmation_required'])
        reviewed=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=1,currency_confirmation='MXN'))
        self.assertTrue(reviewed['can_confirm'])
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=1,plan_hash=reviewed['plan_hash'],currency_confirmation='MXN'))
        self.assertEqual(self.request('/api/book')['documents'],1)

    def test_currency_choice_rejects_missing_revision_and_unsupported_unit_http(self):
        from urllib.error import HTTPError
        doc=self.request('/api/upload',content(currency=None),raw=True)
        with self.assertRaises(HTTPError):
            self.request('/api/documents/'+doc['id']+'/plan',dict(revision=None,currency_confirmation='MXN'))
        plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=1,currency_confirmation='USD'))
        self.assertFalse(plan['can_confirm']);self.assertEqual(self.request('/api/book')['documents'],0)


if __name__=='__main__':unittest.main()
