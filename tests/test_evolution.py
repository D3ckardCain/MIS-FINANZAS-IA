"""Evolución con documentos ficticios: cobertura, netos y revisiones vigentes."""
from dataclasses import replace
from datetime import date
from decimal import Decimal as D
from pathlib import Path
import tempfile
import unittest

from finanzas.book import FinancialBook
from finanzas.intake import Inbox
from finanzas.ledger import Evidence,Kind,Movement,Origin
from tests.test_book import content
from tests.test_openbank import synthetic_pdf
from tests import test_intake


class EvolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'bandeja.sqlite3'
        self.book=FinancialBook(self.path);self.addCleanup(self.book.close)

    def upload(self,data):
        with Inbox(self.path) as inbox:return inbox.upload(data,'ficticio.pdf')

    def confirm(self,data,**kwargs):
        doc=self.upload(data);plan=self.book.preview(doc['id'],**kwargs)
        self.assertTrue(plan['can_confirm'] or plan['status']=='imported',plan['issues'])
        return self.book.confirm(doc['id'],revision=plan['revision'],plan_hash=plan['plan_hash'],**kwargs)

    def account(self,lane='investments'):
        return next(a for a in self.book.evolution()['accounts'] if a['lane']==lane)

    def test_empty_and_unconfirmed_documents_do_not_create_evolution(self):
        self.assertEqual(self.book.evolution()['accounts'],[])
        self.upload(content());self.assertEqual(self.book.evolution()['accounts'],[])

    def test_initial_anchor_is_not_a_contribution_and_internal_transfer_has_two_legs(self):
        self.confirm(content());s=self.account()['history'][0];d=self.account('debit')['history'][0]
        self.assertEqual(D(s['initial']),100);self.assertEqual(D(s['contributions']),200)
        self.assertEqual(D(s['withdrawals']),0);self.assertEqual(D(s['own_transfer_in']),200)
        self.assertEqual(D(d['own_transfer_out']),200);self.assertEqual(D(s['external_contributions']),0)
        self.assertEqual(D(s['interest']),3);self.assertEqual(D(s['withholding']),0)
        self.assertEqual(D(s['interest_net_of_withholding']),3)
        self.assertEqual(D(s['cash_change']),203);self.assertEqual(D(s['calculated_final']),303)
        self.assertEqual(D(s['closing_difference']),0);self.assertTrue(s['reconciled']);self.assertEqual(s['changed_movement_ids'],[])
        self.assertEqual(s['additional_movement_ids'],[]);self.assertEqual(s['pending_transfer_ids'],[])
        self.assertEqual(d['pending_origins'],1);self.assertEqual(self.book.evolution()['unassigned_movements'],[])

    def test_months_out_of_order_sorted_and_not_recounted_on_retry_or_reopen(self):
        self.confirm(content(2,initial='303.00'));first=self.confirm(content());self.confirm(content())
        history=self.account()['history'];self.assertEqual([h['start'] for h in history],['2026-01-01','2026-02-01'])
        self.assertEqual([D(h['interest']) for h in history],[3,3])
        self.assertIsNone(history[0]['boundary_difference']);self.assertEqual(D(history[1]['boundary_difference']),0)
        with FinancialBook(self.path) as other:self.assertEqual(other.evolution(),self.book.evolution())
        self.assertEqual(first['document_id'],history[0]['document_id'])

    def test_gap_is_between_actual_periods_without_synthetic_rows_or_boundary_guess(self):
        from pypdf import PdfReader
        from io import BytesIO
        self.confirm(content())
        texts=[p.extract_text(extraction_mode='layout').replace('/02/26','/03/26') for p in PdfReader(BytesIO(content(2,initial='500.00'))).pages]
        self.confirm(synthetic_pdf(texts));history=self.account()['history']
        self.assertEqual(len(history),2)
        self.assertEqual(history[1]['gap_before'],dict(start='2026-02-01',end='2026-02-28'))
        self.assertIsNone(history[1]['boundary_difference']);self.assertEqual(history[1]['end'],'2026-03-28')
        self.assertTrue(history[1]['reconciled'])

    def test_unknown_retention_stays_unknown_but_explicit_zero_is_known(self):
        from tests.test_book_doopla import content as doopla
        self.confirm(doopla());row=self.account('debit')['history'][0]
        self.assertIsNone(row['withholding']);self.assertIsNone(row['withholding_documented'])
        self.assertIsNone(row['interest_net_of_withholding']);self.assertEqual(D(row['interest']),2)
        self.assertEqual(D(row['vat_received']),D('.32'));self.assertTrue(row['reconciled'])

    def test_unallocated_security_receipts_are_not_interest_or_profit(self):
        from tests.test_book_cetesdirecto import content as cetes
        self.confirm(cetes());row=self.account()['history'][0]
        self.assertIsNone(row['interest']);self.assertIsNone(row['interest_net_of_withholding'])
        self.assertEqual(D(row['interest_documented']),0);self.assertGreater(D(row['security_proceeds']),0)
        self.assertTrue(row['reconciled'])

    def test_fintual_two_currencies_remain_separate_without_independent_custodian_institution(self):
        from tests.test_book_fintual import content as mxn
        from tests.test_book_alpaca import content as usd
        self.confirm(mxn());self.confirm(usd());data=self.book.evolution()
        self.assertEqual(len(data['accounts']),2)
        self.assertEqual({a['institution'] for a in data['accounts']},{'fintual'})
        self.assertEqual({a['unit'] for a in data['accounts']},{'MXN','USD'})
        foreign=next(a for a in data['accounts'] if a['unit']=='USD')['history'][0]
        self.assertEqual(D(foreign['dividends']),2);self.assertEqual(D(foreign['foreign_withholding']),1)
        self.assertIsNone(foreign['withholding']);self.assertIsNone(foreign['interest_net_of_withholding'])
        self.assertNotIn('total',data);self.assertTrue(all(a['role']=='fund_cash' for a in data['accounts']))

    def correction(self,movement,**changes):
        revised=replace(movement,**changes)
        self.book.store.record_many([revised],corrections={movement.id:(1,'Corrección ficticia documentada')})
        return revised

    def test_latest_revision_drives_exact_decimal_delta_without_rewriting_documentary_close(self):
        self.confirm(content());movement=next(m for m in self.book.store.load_ledger().movements if m.kind==Kind.INTEREST)
        self.correction(movement,amount=D('1.000000000000000000000000000001'))
        row=self.account()['history'][0]
        self.assertEqual(D(row['closing_difference']),D('0.000000000000000000000000000001'))
        self.assertEqual(D(row['final']),303);self.assertFalse(row['reconciled'])
        self.assertEqual(row['changed_movement_ids'],[movement.id])

    def test_same_net_correction_still_reports_changed_effective_date(self):
        self.confirm(content());movement=next(m for m in self.book.store.load_ledger().movements if m.kind==Kind.INTEREST)
        self.correction(movement,effective_date=date(2026,1,18))
        row=self.account()['history'][0]
        self.assertEqual(D(row['closing_difference']),0);self.assertFalse(row['reconciled'])
        self.assertEqual(row['changed_movement_ids'],[movement.id])

    def test_corrected_date_outside_coverage_is_visible_not_silently_lost(self):
        self.confirm(content());movement=next(m for m in self.book.store.load_ledger().movements if m.kind==Kind.INTEREST)
        self.correction(movement,effective_date=date(2026,2,2));data=self.book.evolution()
        self.assertEqual([m['id'] for m in data['unassigned_movements']],[movement.id])
        self.assertFalse(self.account()['history'][0]['reconciled'])

    def test_corrected_date_into_next_period_is_counted_once_and_both_periods_flagged(self):
        self.confirm(content());self.confirm(content(2,initial='303.00'))
        movement=next(m for m in self.book.store.load_ledger().movements if m.kind==Kind.INTEREST)
        self.correction(movement,effective_date=date(2026,2,2));history=self.account()['history']
        self.assertEqual([D(h['interest']) for h in history],[2,4]);self.assertTrue(all(not h['reconciled'] for h in history))
        self.assertEqual(history[1]['additional_movement_ids'],[movement.id]);self.assertEqual(self.book.evolution()['unassigned_movements'],[])

    def test_unpaired_transfer_and_external_cashback_stay_distinct(self):
        plan=self.confirm(content());period=next(p for p in plan['periods'] if p['lane']=='investments')
        rows=[Movement('ficticio-'+str(i),period['account'],'MXN',date(2026,1,15),Kind.CONTRIBUTION,D('2'),
              Evidence(plan['document_id'],'fila ficticia '+str(i)),origin,link)
              for i,(origin,link) in enumerate(((Origin.CASHBACK,None),(Origin.EXTERNAL,None),(Origin.OWN_TRANSFER,'solo-una-pata-ficticia')))]
        self.book.store.record_many(rows);row=self.account()['history'][0]
        self.assertEqual(D(row['contributions']),206);self.assertEqual(D(row['external_contributions']),4)
        self.assertEqual(D(row['cashback_contributions']),2);self.assertEqual(D(row['own_transfer_in']),202)
        self.assertEqual(row['pending_transfer_ids'],['solo-una-pata-ficticia']);self.assertFalse(row['reconciled'])

    def test_historical_reversals_are_negative_period_income_and_refunds_not_new_contributions(self):
        from tests import test_yotepresto_completion as ytp
        from tests.test_yotepresto import source
        self.confirm(ytp.content(source()),cash_opening_confirmation='10.00')
        doc=self.upload(ytp.content(ytp.historical_cancellation()));plan=self.book.preview(doc['id'])
        review=dict(cancellations={r['id']:r['candidates'][0]['id'] for r in plan['review_rows']})
        plan=self.book.preview(doc['id'],operation_review=review)
        self.assertTrue(plan['can_confirm'] or plan['status']=='imported',plan['issues'])
        self.book.confirm(doc['id'],revision=plan['revision'],plan_hash=plan['plan_hash'],operation_review=review)
        history=self.account('debit')['history'];a,b=history
        for key in ('interest','withholding','vat_received','vat_paid','fees'):
            self.assertEqual(D(a[key])+D(b[key]),0,key)
        self.assertLess(D(b['interest']),0);self.assertLess(D(b['withholding']),0)
        self.assertEqual(D(b['contributions']),0);self.assertTrue(b['reconciled'])

    def test_reporting_is_read_only_and_can_run_inside_existing_transaction(self):
        self.confirm(content());before=list(self.book.db.iterdump());self.book.evolution()
        self.assertEqual(before,list(self.book.db.iterdump()));self.assertFalse(self.book.db.in_transaction)
        self.book.db.execute('BEGIN');self.book.evolution();self.assertTrue(self.book.db.in_transaction);self.book.db.rollback()

    def test_all_integrated_institutions_reconcile_without_summing_positions(self):
        import importlib
        self.confirm(content())
        for profile in ('mifel','bancoppel','didi','plata','fondeadora','supertasas','hey','kapital','doopla','fintual','alpaca','cetesdirecto'):
            module=importlib.import_module('tests.test_book_'+profile)
            self.confirm(module.content())
        data=self.book.evolution()
        self.assertEqual(len(data['accounts']),15)
        self.assertTrue(all(row['reconciled'] for a in data['accounts'] for row in a['history']))
        self.assertEqual(data['unassigned_movements'],[])

    def test_corrected_account_without_period_is_exposed_and_old_close_is_flagged(self):
        self.confirm(content());movement=next(m for m in self.book.store.load_ledger().movements if m.kind==Kind.INTEREST)
        self.correction(movement,account='cuenta-ficticia-sin-periodo')
        data=self.book.evolution();self.assertEqual([m['account'] for m in data['unassigned_movements']],['cuenta-ficticia-sin-periodo'])
        self.assertFalse(self.account()['history'][0]['reconciled'])


class EvolutionHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_http_empty_confirmed_and_source_link(self):
        self.assertEqual(self.request('/api/book/evolution')['accounts'],[])
        doc=self.request('/api/upload',content(),raw=True);plan=self.request('/api/documents/'+doc['id']+'/plan')
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=1,plan_hash=plan['plan_hash']))
        data=self.request('/api/book/evolution');self.assertEqual(len(data['accounts']),2)
        row=next(a for a in data['accounts'] if a['lane']=='investments')['history'][0]
        self.assertEqual(row['document_id'],doc['id']);self.assertTrue(row['reconciled'])
        self.assertEqual(self.request('/api/documents/'+row['document_id'])['id'],doc['id'])


if __name__=='__main__':unittest.main()
