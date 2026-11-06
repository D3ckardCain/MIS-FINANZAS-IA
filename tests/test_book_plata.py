"""Integración financiera Plata con documentos exclusivamente ficticios."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from decimal import Decimal as D

from finanzas.book import FinancialBook
from finanzas.intake import Inbox
from finanzas.ledger import Kind, Origin
from tests import test_intake
from tests.test_plata import source, row
from tests.test_openbank import synthetic_pdf


def content(pages=None, *, next_period=False, extra=''):
    pages=pages if pages is not None else [p.replace('01 may 2026','30 abr 2026') for p in source()]
    if next_period:
        pages=[p.replace('01 abr 2026 al 30 abr 2026','01 may 2026 al 31 may 2026')
            .replace('15 abr 2026','15 may 2026').replace('20 abr 2026','20 may 2026')
            .replace('30 abr 2026','31 may 2026').replace('$120.80','$141.60').replace('$100.00','$120.80') for p in pages]
    pages=list(pages);pages[-1]+='\n'+extra
    return synthetic_pdf([p.replace('−','-') for p in pages])


class PlataBookTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'bandeja.sqlite3';self.doc=self.upload(content())
        self.book=FinancialBook(self.path);self.addCleanup(self.book.close)

    def upload(self,data):
        with Inbox(self.path) as inbox:return inbox.upload(data,'ejemplo-ficticio.pdf')

    def confirm(self,doc=None):
        doc=doc or self.doc;plan=self.book.preview(doc['id']);self.assertTrue(plan['can_confirm'],plan['issues'])
        return self.book.confirm(doc['id'],revision=plan['revision'],plan_hash=plan['plan_hash'])

    def test_two_accounts_without_aggregate_or_opening_contribution(self):
        result=self.confirm();ledger=self.book.store.load_ledger()
        self.assertEqual(len(result['periods']),2);self.assertEqual(len(ledger.movements),7)
        self.assertEqual({p['lane'] for p in result['periods']},{'debit','investments'})
        self.assertEqual(len(self.book.summary()['accounts']),2)
        self.assertFalse(any(m.kind==Kind.OPENING for m in ledger.movements))
        self.assertEqual(sum(m.signed_amount for m in ledger.movements),D('20.80'))

    def test_cashback_once_internal_pair_neutral_unknown_spei(self):
        result=self.confirm();ledger=self.book.store.load_ledger()
        self.assertEqual(ledger.external_contributions('MXN'),D('10'))
        self.assertEqual(len(result['transfers']),1)
        pair=[m for m in ledger.movements if m.origin==Origin.OWN_TRANSFER]
        self.assertEqual(len(pair),2);self.assertEqual(sum(m.signed_amount for m in pair),0)
        self.assertEqual(sum(m.origin==Origin.UNKNOWN for m in ledger.movements),1)
        self.assertFalse(any(m.origin==Origin.REINVESTMENT for m in ledger.movements))

    def test_actual_retention_once_zero_debit_and_no_annex_fee(self):
        result=self.confirm();ledger=self.book.store.load_ledger()
        taxes=[m for m in ledger.movements if m.kind==Kind.WITHHOLDING]
        self.assertEqual(sorted(m.amount for m in taxes),[D('0'),D('.20')])
        self.assertEqual(sum(m.amount for m in ledger.movements if m.kind==Kind.INTEREST),D('2'))
        self.assertFalse(any(m.kind==Kind.FEE for m in ledger.movements))
        self.assertEqual(result['annex_pages'],[4])
        self.assertEqual(result['aggregate_isr_basis'],'arithmetic_included_in_other_charges')

    def test_cutoff_blocks_entire_batch_without_changing_dates(self):
        doc=self.upload(content(source()));plan=self.book.preview(doc['id'])
        self.assertFalse(plan['can_confirm'])
        outside=[m for m in plan['movements'] if m.get('outside_period')]
        self.assertEqual(len(outside),2)
        self.assertTrue(all(m['posting_date']=='2026-05-01' for m in outside))
        with self.assertRaises(ValueError):self.book.confirm(doc['id'],revision=1,plan_hash=plan['plan_hash'])
        self.assertEqual(self.book.summary()['movements'],0)

    def test_operation_and_posting_preserved_effective_date_is_posting(self):
        pages=[p.replace('01 may 2026','30 abr 2026') for p in source()]
        pages[2]=pages[2].replace(f"{'20 abr 2026':<25}{'20 abr 2026':<25}",f"{'20 abr 2026':<25}{'21 abr 2026':<25}")
        result=self.confirm(self.upload(content(pages)))
        moved=[m for m in result['movements'] if m.get('operation_date')=='2026-04-20']
        self.assertEqual(len(moved),3)
        self.assertTrue(all(m['posting_date']=='2026-04-21' and m['effective_date']=='2026-04-21' for m in moved))

    def test_equal_spei_amounts_preserve_distinct_evidence(self):
        pages=[p.replace('01 may 2026','30 abr 2026') for p in source()]
        line=row('15 abr 2026','15 abr 2026','Pago por','$9.00')+'\n'+' '*50+'transferencia SPEI\n'
        pages[2]=pages[2].replace(line,line+line)
        pages=[p.replace('$21.00','$30.00').replace('$31.00','$40.00').replace('$120.80','$129.80') for p in pages]
        result=self.confirm(self.upload(content(pages)))
        matches=[m for m in result['movements'] if m.get('category')=='spei_in']
        self.assertEqual(len(matches),2);self.assertNotEqual(matches[0]['id'],matches[1]['id'])
        self.assertTrue(all(m['reference'] is None for m in matches))

    def test_ambiguous_transfer_cannot_be_confirmed(self):
        pages=[p.replace('01 may 2026','30 abr 2026') for p in source()]
        line=row('20 abr 2026','20 abr 2026','Depósito desde','$10.00')+'\n'+' '*50+'cuenta propia\n'
        pages[2]=pages[2].replace(line,line+line)
        pages=[p.replace('$21.00','$31.00').replace('$120.80','$130.80') for p in pages]
        plan=self.book.preview(self.upload(content(pages))['id'])
        self.assertFalse(plan['can_confirm']);self.assertEqual(plan['transfers'],[])

    def test_foreign_currency_unknown_concept_and_fee_block(self):
        for old,new in [('MXN','USD'),('Pago por','Otro concepto'),('Comisiones $0.00','Comisiones $1.00')]:
            pages=[p.replace(old,new).replace('01 may 2026','30 abr 2026') for p in source()]
            self.assertFalse(self.book.preview(self.upload(content(pages))['id'])['can_confirm'])

    def test_zero_retention_keeps_explicit_evidence(self):
        pages=[p.replace('01 may 2026','30 abr 2026').replace('−$0.20','$0.00')
            .replace('−$10.20','−$10.00').replace('$120.80','$121.00') for p in source()]
        self.confirm(self.upload(content(pages)))
        taxes=[m for m in self.book.store.load_ledger().movements if m.kind==Kind.WITHHOLDING]
        self.assertEqual(len(taxes),2);self.assertTrue(all(m.amount==0 for m in taxes))

    def test_retry_reopen_overlap_and_out_of_order_months(self):
        self.confirm(self.upload(content(next_period=True)));self.confirm()
        self.assertTrue(self.book.confirm(self.doc['id'],revision=1,plan_hash='retry')['duplicate'])
        with FinancialBook(self.path) as other:self.assertEqual(other.summary()['documents'],2)
        plan=self.book.preview(self.upload(content(extra='Otra representacion'))['id'])
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('superpuesto' in s for s in plan['issues']))

    def test_adjacent_balance_mismatch_blocks_both_product_batch(self):
        self.confirm()
        pages=[p.replace('01 abr 2026 al 30 abr 2026','01 may 2026 al 31 may 2026')
            .replace('15 abr 2026','15 may 2026').replace('20 abr 2026','20 may 2026') for p in source()]
        plan=self.book.preview(self.upload(content(pages))['id'])
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('cierre anterior' in s for s in plan['issues']))

    def test_stale_review_and_rollback_leave_no_partial_financial_data(self):
        plan=self.book.preview(self.doc['id'])
        with Inbox(self.path) as inbox:inbox.review(self.doc['id'],expected_revision=1,decision='reviewed')
        with self.assertRaises(ValueError):self.book.confirm(self.doc['id'],revision=1,plan_hash=plan['plan_hash'])
        original=self.book.store.record_many
        def fail(rows):original(rows);raise ValueError('Fallo simulado')
        with patch.object(self.book.store,'record_many',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm()
        self.assertEqual(self.book.summary()['documents'],0)
        self.assertEqual(self.book.store.load_ledger().movements,())
        self.assertEqual(self.book.store.review_history(self.doc['id']),())
        self.confirm()

    def test_six_institutions_without_account_collision(self):
        from tests.test_book import content as openbank
        from tests.test_book_mifel import content as mifel
        from tests.test_book_bancoppel import content as bancoppel
        from tests.test_book_didi import content as didi
        from tests.test_book_fondeadora import content as fondeadora
        self.confirm()
        for fixture in (openbank,mifel,bancoppel,didi,fondeadora):self.confirm(self.upload(fixture()))
        self.assertEqual(self.book.summary()['documents'],6)
        self.assertEqual(len(self.book.summary()['accounts']),8)


class PlataFinancialHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_upload_prepare_confirm_http(self):
        doc=self.request('/api/upload',content(),raw=True)
        plan=self.request('/api/documents/'+doc['id']+'/plan');self.assertTrue(plan['can_confirm'],plan['issues'])
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=1,plan_hash=plan['plan_hash']))
        summary=self.request('/api/book');self.assertEqual(summary['documents'],1)
        self.assertEqual(len(summary['accounts']),2)


if __name__=='__main__':unittest.main()
