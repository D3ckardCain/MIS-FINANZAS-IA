"""DiDi al libro: depósitos incluyen interés y las vistas comparten cuenta."""
from decimal import Decimal
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from finanzas.book import FinancialBook
from finanzas.intake import Inbox
from finanzas.ledger import Kind
from tests import test_intake
from tests.test_didi import fixture
from tests.test_openbank import synthetic_pdf
from tests.test_book import content as openbank_content
from tests.test_book_mifel import content as mifel_content
from tests.test_book_bancoppel import content as bancoppel_content


def content(*,new=True,next_period=False,zero_interest=False,omit_interest=False,extra=''):
    pages,_=fixture(new)
    if next_period:
        amounts={'100.00':'131.00','150.00':'181.00','151.00':'182.00','131.00':'162.00'}
        pages=[re.sub('|'.join(re.escape(x) for x in amounts),lambda m:amounts[m[0]],p) for p in pages]
        pages=[p.replace('01/01/26 - 31/01/26','01/02/26 - 28/02/26').replace('/01/2026','/02/2026') for p in pages]
    if zero_interest or omit_interest:
        pages=[p.replace('$ 51.00','$ 50.00').replace('$ 1.00','$ 0.00').replace('$ 151.00','$ 150.00').replace('$ 131.00','$ 130.00') for p in pages]
        if omit_interest:
            pages[1]=re.sub(r'05/01/2026 Depósito Rendimientos.*?(?=08/01/2026)', '',pages[1],flags=re.S)
    pages[-1]+='\n'+extra
    return synthetic_pdf(pages)


class DidiBookTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'bandeja.sqlite3';self.doc=self.upload(content())
        self.book=FinancialBook(self.path);self.addCleanup(self.book.close)

    def upload(self,data):
        with Inbox(self.path) as inbox:return inbox.upload(data,'ejemplo-ficticio.pdf')

    def confirm(self,doc=None):
        doc=doc or self.doc;plan=self.book.preview(doc['id']);self.assertTrue(plan['can_confirm'],plan['issues'])
        return self.book.confirm(doc['id'],revision=plan['revision'],plan_hash=plan['plan_hash'])

    def test_one_account_and_deposits_include_interest_without_double_contribution(self):
        plan=self.book.preview(self.doc['id']);self.assertEqual(len(plan['periods']),1)
        self.assertTrue(plan['periods'][0]['shared_account']);self.assertEqual(plan['transfers'],[])
        self.confirm();ledger=self.book.store.load_ledger()
        self.assertEqual(len(ledger.movements),4)
        self.assertEqual(sum(m.amount for m in ledger.movements if m.kind==Kind.CONTRIBUTION),Decimal('50.00'))
        self.assertEqual(ledger.interest_received('MXN'),1)
        self.assertEqual(sum(m.signed_amount for m in ledger.movements),31)
        self.assertEqual(ledger.external_contributions('MXN'),0)
        self.assertEqual(len(ledger.pending_origins()),2)
        self.assertFalse(any(m.kind==Kind.OPENING for m in ledger.movements))
        account=self.book.summary()['accounts'][0]
        self.assertEqual(account['closing'],'131.00');self.assertTrue(account['shared_account'])

    def test_old_and_new_summary_formats_normalize_to_same_money(self):
        result=self.confirm(self.upload(content(new=False)))
        self.assertEqual(len(result['movements']),4)
        account=self.book.summary()['accounts'][0]
        self.assertEqual(account['closing'],'131.00');self.assertEqual(Decimal(account['interest']),1)
        self.assertEqual(Decimal(account['withholding']),0)

    def test_wrapped_reference_rates_and_disclosure_are_frozen_with_plan(self):
        result=self.confirm();interest=next(m for m in result['movements'] if m['kind']=='interes_cobrado')
        self.assertEqual(interest['reference'],'SNCBS000002')
        self.assertEqual(interest['effective_date'],'2026-01-05')
        self.assertEqual(result['reported_terms']['annual_rates_reported'],['12.00','5.00'])
        self.assertIn('Hasta $ 10000.00',result['reported_terms']['rate_disclosure'])
        self.assertIn('01/12/2025',result['reported_terms']['rate_disclosure'])
        self.assertEqual(self.book.preview(self.doc['id'])['reported_terms'],result['reported_terms'])

    def test_month_without_interest_does_not_invent_income(self):
        self.confirm(self.upload(content(omit_interest=True)))
        ledger=self.book.store.load_ledger();self.assertEqual(len(ledger.movements),3)
        self.assertEqual(ledger.interest_received('MXN'),0)
        self.assertEqual(ledger.withholding_recorded('MXN'),0)
        self.assertEqual(self.book.summary()['accounts'][0]['closing'],'130.00')

    def test_explicit_zero_interest_is_observation_not_second_cash_flow(self):
        result=self.confirm(self.upload(content(zero_interest=True)))
        self.assertEqual(len(result['zero_interest_observations']),1)
        self.assertEqual(len(self.book.store.load_ledger().movements),3)

    def test_retry_reopening_and_overlapping_pdf_do_not_duplicate(self):
        self.confirm();again=self.book.confirm(self.doc['id'],revision=1,plan_hash='retry')
        self.assertTrue(again['duplicate'])
        with FinancialBook(self.path) as other:self.assertEqual(other.summary()['movements'],4)
        doc=self.upload(content(extra='Otra representacion del mismo periodo'));plan=self.book.preview(doc['id'])
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('superpuesto' in s for s in plan['issues']))

    def test_out_of_order_periods_allow_reused_folios_without_losing_movements(self):
        self.confirm(self.upload(content(next_period=True)));self.confirm()
        summary=self.book.summary();self.assertEqual(len(summary['accounts']),1)
        self.assertEqual(summary['accounts'][0]['periods'],2)
        self.assertEqual(summary['accounts'][0]['closing'],'162.00')
        self.assertEqual(summary['accounts'][0]['gaps'],[])
        self.assertEqual(Decimal(summary['accounts'][0]['interest']),2)
        self.assertEqual(summary['movements'],8)

    def test_balance_summary_or_tax_discrepancies_block_confirmation(self):
        for before,after in [('$ 150.00','$ 149.99'),('Rendimiento $ 1.00','Rendimiento $ 2.00'),
                             ('Impuesto retenido $ 0.00','Impuesto retenido $ 0.10')]:
            pages,_=fixture();doc=self.upload(synthetic_pdf([p.replace(before,after) for p in pages]))
            self.assertFalse(self.book.preview(doc['id'])['can_confirm'])
        self.assertEqual(self.book.summary()['documents'],0)

    def test_unknown_currency_or_missing_duplicate_reference_is_not_imported(self):
        for before,after in [('MXN $ 50.00','USD $ 50.00'),('CBS000003',''),('CBS000003','CBS000001')]:
            pages,_=fixture();doc=self.upload(synthetic_pdf([p.replace(before,after) for p in pages]))
            self.assertFalse(self.book.preview(doc['id'])['can_confirm'])

    def test_equal_amount_same_date_different_folios_are_kept(self):
        pages,_=fixture()
        pages[1]=pages[1].replace('05/01/2026 Depósito Rendimientos',
            '02/01/2026 Depósito Transferencia entrante\nIdentificación del movimiento:CBS000004\nMXN $ 50.00 $ 200.00\n05/01/2026 Depósito Rendimientos')
        pages=[p.replace('$ 51.00','$ 101.00').replace('$ 151.00','$ 201.00').replace('$ 131.00','$ 181.00') for p in pages]
        result=self.confirm(self.upload(synthetic_pdf(pages)))
        contributions=[m for m in result['movements'] if m['kind']=='aportacion']
        self.assertEqual(len(contributions),2);self.assertNotEqual(contributions[0]['id'],contributions[1]['id'])
        self.assertEqual(self.book.summary()['accounts'][0]['closing'],'181.00')

    def test_atomic_failure_leaves_no_approval_or_movements(self):
        original=self.book.store.record_many
        def fail(rows):original(rows);raise ValueError('Fallo de prueba')
        with patch.object(self.book.store,'record_many',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm()
        self.assertEqual(self.book.summary()['documents'],0)
        self.assertEqual(self.book.store.load_ledger().movements,())
        self.assertEqual(self.book.store.review_history(self.doc['id']),())
        self.confirm()

    def test_four_institutions_coexist_and_shared_accounts_remain_unique(self):
        self.confirm()
        for data in (openbank_content(),mifel_content(),bancoppel_content()):self.confirm(self.upload(data))
        summary=self.book.summary()
        self.assertEqual(summary['documents'],4);self.assertEqual(len(summary['accounts']),5)
        self.assertEqual({a['institution'] for a in summary['accounts']},{'openbank','mifel','bancoppel','didi'})
        self.assertEqual(sum(a['shared_account'] for a in summary['accounts']),2)


class DidiFinancialHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_upload_plan_confirm_and_shared_account_http(self):
        doc=self.request('/api/upload',content(),raw=True)
        plan=self.request('/api/documents/'+doc['id']+'/plan');self.assertTrue(plan['can_confirm'],plan['issues'])
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=plan['revision'],plan_hash=plan['plan_hash']))
        book=self.request('/api/book');self.assertEqual(book['documents'],1)
        self.assertEqual(len(book['accounts']),1);self.assertEqual(book['movements'],4)


if __name__=='__main__':unittest.main()
