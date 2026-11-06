"""Mifel al ledger: una cuenta compartida, cobro/ISR/rangos distintos."""
from datetime import date
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from finanzas.book import FinancialBook
from finanzas.intake import Inbox
from finanzas.ledger import Kind, Origin
from tests import test_intake
from tests.test_book import content as openbank_content
from tests.test_mifel import statement
from tests.test_openbank import synthetic_pdf


def content(*, august=False, transfers=False, zero=False, zero_interest=False, extra=''):
    texts=statement(august)
    if transfers:
        def row(ref,description,*,debit='',credit='',balance=''):
            return ('30/07/2026  '+ref+'  '+description).ljust(96)+debit.rjust(12)+credit.rjust(20)+balance.rjust(24)+'\n'
        additions=row('E9000-1','TRANSFERENCIA SPEI RECIBIDA',credit='100.00',balance='200.00')
        additions+=row('E9001-1','TRANSFERENCIA SPEI ENVIADA',debit='50.00',balance='150.00')
        texts[1]=texts[1].replace('31/07/2026  S1000-2',additions+'31/07/2026  S1000-2')
        texts=[p.replace('99.70','149.70').replace('102.70','152.70') for p in texts]
        texts[1]=texts[1].replace('Suma de retiros y depósitos  0.30  3.00','Suma de retiros y depósitos  50.30  103.00')
    if zero or zero_interest:
        texts=[p.replace('0.30','0.00').replace('99.70','100.00').replace('102.70','103.00') for p in texts]
    if zero_interest:
        texts=[p.replace('3.00','0.00').replace('103.00','100.00') for p in texts]
    texts[-1]+='\n'+extra
    return synthetic_pdf(texts)


class MifelBookTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'bandeja.sqlite3'
        self.doc=self.upload(content())
        self.book=FinancialBook(self.path);self.addCleanup(self.book.close)

    def upload(self,data):
        with Inbox(self.path) as inbox:return inbox.upload(data,'ejemplo-ficticio.pdf')

    def confirm(self,doc=None):
        doc=doc or self.doc;plan=self.book.preview(doc['id'])
        self.assertTrue(plan['can_confirm'],plan['issues'])
        return self.book.confirm(doc['id'],revision=plan['revision'],plan_hash=plan['plan_hash'])

    def test_shared_views_import_one_account_once_and_zero_initial_contributions(self):
        plan=self.book.preview(self.doc['id'])
        self.assertEqual(len(plan['periods']),1)
        self.assertEqual(plan['periods'][0]['view_lanes'],['debit','investments'])
        self.assertEqual(len(plan['movements']),2)
        self.assertEqual(plan['transfers'],[])
        self.confirm();ledger=self.book.store.load_ledger()
        self.assertEqual(len(ledger.movements),2)
        self.assertFalse(any(m.kind==Kind.OPENING for m in ledger.movements))
        self.assertEqual(ledger.external_contributions('MXN'),0)
        summary=self.book.summary();self.assertEqual(len(summary['accounts']),1)
        self.assertTrue(summary['accounts'][0]['shared_account'])
        self.assertEqual(summary['accounts'][0]['closing'],'102.70')

    def test_nonzero_isr_from_row_not_repeated_from_group_or_summary(self):
        self.confirm();ledger=self.book.store.load_ledger()
        self.assertEqual(ledger.interest_received('MXN'),Decimal('3.00'))
        self.assertEqual(ledger.withholding_recorded('MXN'),Decimal('0.30'))
        self.assertEqual(sum(m.signed_amount for m in ledger.movements),Decimal('2.70'))
        self.assertEqual(sum(m.kind==Kind.WITHHOLDING for m in ledger.movements),1)
        self.assertEqual(Decimal(self.book.summary()['accounts'][0]['interest_net_of_withholding']),Decimal('2.70'))

    def test_cash_date_and_future_weekend_accrual_range_survive_confirmation(self):
        result=self.confirm()
        income=next(m for m in result['movements'] if m['kind']=='interes_cobrado')
        self.assertEqual(income['effective_date'],'2026-07-31')
        self.assertEqual(income['accrual_start'],'2026-07-31')
        self.assertEqual(income['accrual_end'],'2026-08-02')
        self.assertEqual(len(result['payment_groups']),1)
        self.assertEqual(result['reported_terms']['annual_rate_reported'],'10.00')
        saved=self.book.preview(self.doc['id'])
        self.assertEqual(saved['payment_groups'],result['payment_groups'])
        self.assertEqual(next(m for m in self.book.store.load_ledger().movements if m.kind==Kind.INTEREST).effective_date,date(2026,7,31))

    def test_spei_contribution_and_reduction_keep_unknown_origins(self):
        doc=self.upload(content(transfers=True));self.confirm(doc)
        ledger=self.book.store.load_ledger()
        capital=[m for m in ledger.movements if m.kind in (Kind.CONTRIBUTION,Kind.WITHDRAWAL)]
        self.assertEqual(len(capital),2)
        self.assertTrue(all(m.origin==Origin.UNKNOWN and m.transfer_id is None for m in capital))
        self.assertEqual(ledger.external_contributions('MXN'),0)
        self.assertEqual(self.book.summary()['accounts'][0]['closing'],'152.70')
        self.assertEqual(self.book.summary()['accounts'][0]['pending_origins'],2)

    def test_explicit_zero_isr_is_recorded_once(self):
        self.confirm(self.upload(content(zero=True)))
        ledger=self.book.store.load_ledger()
        self.assertEqual(ledger.withholding_recorded('MXN'),0)
        self.assertEqual(len(ledger.movements),2)
        self.assertEqual(self.book.summary()['accounts'][0]['closing'],'103.00')

    def test_zero_interest_stays_evidence_and_not_an_invalid_cash_movement(self):
        result=self.confirm(self.upload(content(zero_interest=True)))
        self.assertEqual(len(result['zero_interest_observations']),1)
        self.assertEqual(len(self.book.store.load_ledger().movements),1)
        self.assertEqual(self.book.summary()['accounts'][0]['closing'],'100.00')

    def test_duplicate_confirmation_reopen_and_frozen_plan(self):
        self.confirm();before=self.book.summary()
        result=self.book.confirm(self.doc['id'],revision=1,plan_hash='old-request-retry')
        self.assertTrue(result['duplicate'])
        self.assertEqual(self.book.summary(),before)
        with FinancialBook(self.path) as other:
            self.assertEqual(other.preview(self.doc['id'])['status'],'imported')
            self.assertEqual(other.summary(),before)

    def test_overlap_of_shared_account_is_blocked_even_when_pdf_changes(self):
        self.confirm();doc=self.upload(content(extra='Otra representacion del mismo periodo'))
        plan=self.book.preview(doc['id'])
        self.assertFalse(plan['can_confirm'])
        self.assertTrue(any('superpuesto' in s for s in plan['issues']))

    def test_out_of_order_months_use_one_account_and_validate_adjoining_balances(self):
        self.confirm(self.upload(content(august=True)));self.confirm()
        accounts=self.book.summary()['accounts'];self.assertEqual(len(accounts),1)
        self.assertEqual(accounts[0]['periods'],2)
        self.assertEqual(accounts[0]['closing'],'103.60')
        self.assertEqual(Decimal(accounts[0]['interest']),Decimal('4.00'))
        self.assertEqual(Decimal(accounts[0]['withholding']),Decimal('0.40'))
        self.assertEqual(accounts[0]['gaps'],[])

    def test_reader_differences_or_other_products_block_financial_import(self):
        for before,after in [('99.70','99.69'),('Inversiones 0.00','Inversiones 1.00'),
                             ('Comisiones efectivamente cobradas 0.00','Comisiones efectivamente cobradas 1.00')]:
            doc=self.upload(synthetic_pdf([p.replace(before,after) for p in statement()]))
            plan=self.book.preview(doc['id']);self.assertFalse(plan['can_confirm'])
        self.assertEqual(self.book.summary()['documents'],0)

    def test_adjacent_month_with_valid_detail_but_wrong_opening_is_blocked(self):
        import re
        replacements={'102.70':'103.70','102.60':'103.60','103.60':'104.60'}
        texts=[re.sub(r'102\.70|102\.60|103\.60',lambda m:replacements[m[0]],p) for p in statement(True)]
        self.confirm();doc=self.upload(synthetic_pdf(texts));plan=self.book.preview(doc['id'])
        self.assertFalse(plan['can_confirm'])
        self.assertTrue(any('cierre anterior' in s for s in plan['issues']),plan['issues'])
        self.assertEqual(self.book.summary()['documents'],1)

    def test_atomic_failure_rolls_back_shared_account_and_approval(self):
        original=self.book.store.record_many
        def fail(movements):
            original(movements);raise ValueError('Fallo de prueba tras guardar movimientos')
        with patch.object(self.book.store,'record_many',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm()
        self.assertEqual(self.book.summary()['documents'],0)
        self.assertEqual(self.book.store.load_ledger().movements,())
        self.assertEqual(self.book.store.review_history(self.doc['id']),())
        self.confirm()

    def test_openbank_and_mifel_coexist_without_account_or_institution_collisions(self):
        self.confirm();self.confirm(self.upload(openbank_content()))
        summary=self.book.summary()
        self.assertEqual(summary['documents'],2)
        self.assertEqual(len(summary['accounts']),3)
        self.assertEqual({a['institution'] for a in summary['accounts']},{'openbank','mifel'})
        self.assertEqual(sum(a['shared_account'] for a in summary['accounts']),1)


class MifelFinancialHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_upload_plan_confirmation_and_shared_book_http(self):
        doc=self.request('/api/upload',content(),raw=True)
        self.assertEqual(doc['result']['institution'],'mifel')
        plan=self.request('/api/documents/'+doc['id']+'/plan')
        self.assertTrue(plan['can_confirm'],plan['issues'])
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=plan['revision'],plan_hash=plan['plan_hash']))
        book=self.request('/api/book');self.assertEqual(book['documents'],1)
        self.assertEqual(len(book['accounts']),1)
        self.assertEqual(book['movements'],2)


if __name__=='__main__':unittest.main()
