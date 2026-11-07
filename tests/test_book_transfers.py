"""Traspasos propios ficticios, revisión vinculada y dos correcciones atómicas."""
from dataclasses import replace
from datetime import date
from decimal import Decimal as D
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from finanzas.book import FinancialBook
from finanzas.book_transfers import eligible
from finanzas.intake import Inbox,plain
from finanzas.ledger import Kind,Origin
from tests.test_book_bancoppel import content as bancoppel
from tests.test_openbank import page,table_row,synthetic_pdf
from tests import test_intake


def destination(*,account='0001234567',amount='20.00'):
    cash_initial=D('210')-D(amount)
    pages=[page('Cuenta Débito Open Light',[
        table_row('05/01/26','Transferencia SPEI recibida','$ '+amount,'','$ 210.00'),
        table_row('05/01/26','Retiro a Apartado Open','','$ 200.00','$ 10.00')],initial=str(cash_initial),deposits=amount,other='200.00',final='10.00'),
        page('Apartado Open',[table_row('05/01/26','Abono desde Cuenta Débito Open Light','$ 200.00','','$ 300.00')],initial='100.00',deposits='200.00',final='300.00')]
    pages[0]='Emitido por Openbank Mexico\nNúmero de cuenta '+account+'\n'+pages[0]
    return synthetic_pdf(pages)


class TransferBookTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'bandeja.sqlite3';self.book=FinancialBook(self.path);self.addCleanup(self.book.close)
        self.source=self.import_(bancoppel());self.target=self.import_(destination())
        data=self.book.transfer_overview();self.pair=data['matches'][0]
        self.out=self.pair['outgoing_id'];self.inc=self.pair['incoming_id']

    def import_(self,data):
        with Inbox(self.path) as inbox:doc=inbox.upload(data,'ficticio.pdf')
        plan=self.book.preview(doc['id']);self.assertTrue(plan['can_confirm'],plan['issues'])
        return self.book.confirm(doc['id'],revision=plan['revision'],plan_hash=plan['plan_hash'])

    def confirm(self):
        plan=self.book.transfer_plan(self.out,self.inc,ownership_confirmed=True)
        self.assertTrue(plan['can_confirm'],plan['issues'])
        return self.book.confirm_transfer(self.out,self.inc,ownership_confirmed=True,plan_hash=plan['plan_hash'])

    def test_candidates_are_not_automatically_classified_or_linked(self):
        data=self.book.transfer_overview();self.assertEqual(len(data['matches']),1);self.assertEqual(data['links'],[])
        self.assertTrue(all(m.origin==Origin.UNKNOWN for m in self.book.store.load_ledger().movements if m.id in (self.out,self.inc)))
        for flag in (False,None,'true',1):
            self.assertFalse(self.book.transfer_plan(self.out,self.inc,ownership_confirmed=flag)['can_confirm'])

    def test_link_preserves_both_cash_legs_dates_balances_and_frozen_batches(self):
        before={m.id:m for m in self.book.store.load_ledger().movements};frozen=self.book.preview(self.source['document_id'])
        result=self.confirm();after={m.id:m for m in self.book.store.load_ledger().movements}
        self.assertEqual(result['status'],'linked');self.assertEqual(len(before),len(after))
        for identifier in (self.out,self.inc):
            self.assertEqual(replace(after[identifier],origin=before[identifier].origin,transfer_id=None),before[identifier])
            self.assertEqual(after[identifier].origin,Origin.OWN_TRANSFER)
            self.assertEqual(len(self.book.store.history(identifier)),2)
        self.assertEqual(after[self.out].effective_date,date(2025,12,20));self.assertEqual(after[self.inc].effective_date,date(2026,1,5))
        self.assertEqual(self.book.preview(self.source['document_id']),frozen)
        self.assertEqual(sum(after[i].signed_amount for i in (self.out,self.inc)),0)
        self.assertEqual(self.book.store.load_ledger().external_contributions('MXN'),0)
        self.assertTrue(all(r['reconciled'] for a in self.book.evolution()['accounts'] for r in a['history']))
        self.assertEqual(sum(len(r['reviewed_origin_ids']) for a in self.book.evolution()['accounts'] for r in a['history']),2)
        self.assertEqual(self.book.transfer_overview()['matches'],[])

    def test_same_account_wrong_direction_and_amount_do_not_match(self):
        self.assertFalse(self.book.transfer_plan(self.inc,self.out,ownership_confirmed=True)['can_confirm'])
        self.assertFalse(self.book.transfer_plan(self.inc,self.inc,ownership_confirmed=True)['can_confirm'])
        plan=self.import_(destination(account='0007654321',amount='21.00'))
        incoming=next(m['id'] for m in plan['movements'] if m['kind']==Kind.CONTRIBUTION and m['origin']==Origin.UNKNOWN)
        self.assertFalse(self.book.transfer_plan(self.out,incoming,ownership_confirmed=True)['can_confirm'])
        with self.assertRaises(ValueError):self.book.transfer_plan('ausente',self.inc,ownership_confirmed=True)

    def test_different_currency_and_economic_principal_are_not_candidates(self):
        m=next(m for m in self.book.store.load_ledger().movements if m.id==self.inc)
        for row in ({'category':'purchase'},{'category':'repayment','component':'principal'},{'description':'Compra de valores SPEI'}):
            self.assertFalse(eligible(m,plain(m)|row))
        self.assertFalse(eligible(replace(m,origin=Origin.CASHBACK),plain(m)|dict(category='transfer')))
        # Otra unidad en un registro de cuenta distinto nunca aparece como pareja MXN.
        revised=replace(m,account='ficticio-usd',unit='USD')
        self.book.store.record_many([revised],corrections={m.id:(1,'Corrección ficticia de unidad y cuenta')})
        self.assertFalse(self.book.transfer_plan(self.out,self.inc,ownership_confirmed=True)['can_confirm'])

    def test_two_equal_incoming_rows_require_selection_not_arbitrary_pairing(self):
        second=self.import_(destination(account='0007654321'));data=self.book.transfer_overview()
        self.assertEqual(len(data['matches']),2);self.assertEqual(data['links'],[])
        self.confirm();remaining=self.book.transfer_overview()['incoming'];self.assertEqual(len(remaining),1)
        self.assertNotEqual(remaining[0]['id'],self.inc)
        self.assertFalse(self.book.transfer_plan(self.out,remaining[0]['id'],ownership_confirmed=True)['can_confirm'])

    def test_plan_hash_and_intervening_book_change_invalidate_confirmation(self):
        p=self.book.transfer_plan(self.out,self.inc,ownership_confirmed=True)
        with self.assertRaises(ValueError):self.book.confirm_transfer(self.out,self.inc,ownership_confirmed=True,plan_hash='incorrecto')
        self.import_(destination(account='0007654321'))
        with self.assertRaises(ValueError):self.book.confirm_transfer(self.out,self.inc,ownership_confirmed=True,plan_hash=p['plan_hash'])
        self.assertEqual(self.book.transfer_overview()['links'],[])

    def test_fail_after_corrections_rolls_back_both_versions_and_link(self):
        before=self.book.store._current();original=self.book.store.record_many
        def fail(*args,**kwargs):original(*args,**kwargs);raise ValueError('Fallo ficticio')
        with patch.object(self.book.store,'record_many',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm()
        self.assertEqual(self.book.store._current(),before);self.assertEqual(self.book.transfer_overview()['links'],[])
        self.confirm()

    def test_retry_and_reopen_preserve_one_link_and_no_new_movements(self):
        p=self.confirm();count=len(self.book.store.load_ledger().movements)
        again=self.book.confirm_transfer(self.out,self.inc,ownership_confirmed=True,plan_hash='retry')
        self.assertTrue(again['duplicate']);self.assertEqual(len(self.book.transfer_overview()['links']),1)
        self.assertEqual(len(self.book.store.load_ledger().movements),count)
        with FinancialBook(self.path) as other:self.assertEqual(other.transfer_overview()['links'][0]['transfer_id'],p['transfer_id'])

    def test_unregistered_origin_change_is_not_exempted_from_evolution_review(self):
        before=self.book.store._current();link='pareja-ficticia-sin-acta'
        rows=[replace(before[i][1],origin=Origin.OWN_TRANSFER,transfer_id=link) for i in (self.out,self.inc)]
        self.book.store.record_many(rows,corrections={i:(1,'Cambio ficticio externo al flujo') for i in (self.out,self.inc)})
        self.assertEqual(sum(len(r['changed_movement_ids']) for a in self.book.evolution()['accounts'] for r in a['history']),2)

    def test_financial_revision_after_link_requires_new_review_not_silent_retry(self):
        self.confirm();version,m=self.book.store._current()[self.inc]
        self.book.store.record_many([replace(m,effective_date=date(2026,1,6))],corrections={m.id:(version,'Cambio ficticio de fecha')})
        self.assertEqual(self.book.transfer_overview()['links'][0]['status'],'needs_review')
        self.assertFalse(self.book.transfer_plan(self.out,self.inc,ownership_confirmed=True)['can_confirm'])
        self.assertTrue(any(r['changed_movement_ids'] for a in self.book.evolution()['accounts'] for r in a['history']))


class TransferHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_http_candidates_review_confirm_and_retry(self):
        for content in (bancoppel(),destination()):
            doc=self.request('/api/upload',content,raw=True);p=self.request('/api/documents/'+doc['id']+'/plan')
            self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=1,plan_hash=p['plan_hash']))
        data=self.request('/api/book/transfers');payload=data['matches'][0]|dict(ownership_confirmed=True)
        p=self.request('/api/book/transfers/plan',payload);self.assertTrue(p['can_confirm'])
        result=self.request('/api/book/transfers/confirm',payload|dict(plan_hash=p['plan_hash']));self.assertEqual(result['status'],'linked')
        self.assertTrue(self.request('/api/book/transfers/confirm',payload|dict(plan_hash=p['plan_hash']))['duplicate'])
        self.assertTrue(all(r['reconciled'] for a in self.request('/api/book/evolution')['accounts'] for r in a['history']))


if __name__=='__main__':unittest.main()
