"""Cajitas ficticias individuales: sumas, continuidad, identidades y cashback."""
import copy
from decimal import Decimal as D
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from finanzas.book import FinancialBook
from finanzas.intake import Inbox
from finanzas.ledger import Kind,Origin
from tests.test_book_nu import content,source,review
from tests.test_openbank import synthetic_pdf
from tests import test_intake


def individual(doc,*,next_period=False):
    r=review(doc,next_period=next_period);del r['nu']['buckets']['investments']
    r['nu']['cajitas']=[dict(name='FICTICIA',initial='105.00' if next_period else '53.00',final='127.00' if next_period else '105.00',gross_interest='2.10',withholding='0.10'),
        dict(name='Sin movimientos',initial='20.00',final='20.00',gross_interest='0.00',withholding='0.00')]
    return r


class NuCajitaTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'bandeja.sqlite3';self.book=FinancialBook(self.path);self.addCleanup(self.book.close)
        self.doc=self.upload(content())

    def upload(self,data):
        with Inbox(self.path) as inbox:return inbox.upload(data,'ficticio.pdf')

    def confirm(self,doc=None,r=None):
        doc=doc or self.doc;r=r or individual(doc);p=self.book.preview(doc['id'],operation_review=r)
        self.assertTrue(p['can_confirm'],p['issues'])
        return self.book.confirm(doc['id'],revision=doc['revision'],plan_hash=p['plan_hash'],operation_review=r)

    def test_individual_closures_replace_aggregate_without_duplicate_balance_or_income(self):
        plan=self.confirm();accounts=self.book.summary()['accounts'];self.assertEqual(len(accounts),3)
        self.assertEqual(sum(D(a['closing']) for a in accounts),130)
        cajitas=[a for a in accounts if a['role']=='cajita'];self.assertEqual({a['portfolio'] for a in cajitas},{'ficticia','sin movimientos'})
        self.assertFalse(any(a['role']=='cajitas_aggregate' for a in accounts))
        ledger=self.book.store.load_ledger();self.assertEqual(ledger.interest_received('MXN'),D('2.10'));self.assertEqual(ledger.withholding_recorded('MXN'),D('.10'))
        self.assertEqual(ledger.external_contributions('MXN'),0);self.assertEqual(ledger.pending_transfers(),())
        self.assertTrue(all(r['reconciled'] for a in self.book.evolution()['accounts'] for r in a['history']))
        self.assertTrue(plan['nu_individual_mode']);self.assertEqual(plan['operation_review']['nu']['buckets']['investments']['initial'],'73.00')

    def test_individual_totals_correct_but_wrong_per_cajita_closure_still_blocks(self):
        r=individual(self.doc);r['nu']['cajitas'][0]['final']='104';r['nu']['cajitas'][1]['final']='21'
        p=self.book.preview(self.doc['id'],operation_review=r);self.assertFalse(p['can_confirm']);self.assertTrue(any('Cierre individual' in i for i in p['issues']))

    def test_individual_sum_must_match_global_cajitas_and_income_summary(self):
        for key in ('final','initial','gross_interest','withholding'):
            r=individual(self.doc);r['nu']['cajitas'][0][key]='1'
            self.assertFalse(self.book.preview(self.doc['id'],operation_review=r)['can_confirm'],key)

    def test_missing_active_cajita_cannot_drop_its_transfer_or_freeze(self):
        r=individual(self.doc);r['nu']['cajitas'][0]['name']='Otra Cajita'
        p=self.book.preview(self.doc['id'],operation_review=r);self.assertFalse(p['can_confirm']);self.assertTrue(any('Faltan Cajitas' in i for i in p['issues']))

    def test_normalized_duplicate_names_and_invalid_fields_block(self):
        for item in (None,{},[],True):
            r=individual(self.doc);r['nu']['cajitas']=item
            self.assertFalse(self.book.preview(self.doc['id'],operation_review=r)['can_confirm'])
        r=individual(self.doc);r['nu']['cajitas'][1]['name']='  fictícia  '
        self.assertFalse(self.book.preview(self.doc['id'],operation_review=r)['can_confirm'])
        for name in ('','a\nb',True,'a'*121):
            r=individual(self.doc);r['nu']['cajitas'][1]['name']=name
            self.assertFalse(self.book.preview(self.doc['id'],operation_review=r)['can_confirm'])
        r=individual(self.doc);r['nu']['cajitas'][0]['final']=1.0
        self.assertFalse(self.book.preview(self.doc['id'],operation_review=r)['can_confirm'])

    def test_months_out_of_order_and_unchanged_names_preserve_cajita_accounts(self):
        feb=self.upload(content(next_period=True));self.confirm(feb,individual(feb,next_period=True));self.confirm()
        accounts=self.book.evolution()['accounts'];self.assertEqual(len(accounts),3)
        self.assertTrue(all(len(a['history'])==2 for a in accounts))
        self.assertTrue(all(r['reconciled'] and not r['gap_before'] for a in accounts for r in a['history']))

    def test_historical_quiet_cajita_cannot_disappear_by_omission_or_rename(self):
        self.confirm();feb=self.upload(content(next_period=True));r=individual(feb,next_period=True)
        r['nu']['cajitas'][1]['name']='Renombrada'
        p=self.book.preview(feb['id'],operation_review=r);self.assertFalse(p['can_confirm']);self.assertTrue(any('históricas' in i for i in p['issues']))

    def test_granularity_cannot_switch_and_double_same_money_in_later_period(self):
        self.confirm();feb=self.upload(content(next_period=True))
        p=self.book.preview(feb['id'],operation_review=review(feb,next_period=True));self.assertFalse(p['can_confirm'])
        self.assertTrue(any('historial Nu usa Cajitas individuales' in i for i in p['issues']))

    def test_aggregate_history_cannot_be_reimported_as_individual_history(self):
        r=review(self.doc);p=self.book.preview(self.doc['id'],operation_review=r)
        self.book.confirm(self.doc['id'],revision=1,plan_hash=p['plan_hash'],operation_review=r)
        feb=self.upload(content(next_period=True));p=self.book.preview(feb['id'],operation_review=individual(feb,next_period=True))
        self.assertFalse(p['can_confirm']);self.assertTrue(any('historial Nu usa Cajitas agregadas' in i for i in p['issues']))

    def test_atomic_failure_retry_reopen_preserve_individual_plan(self):
        original=self.book.store.record_many
        def fail(rows):original(rows);raise ValueError('Fallo ficticio')
        with patch.object(self.book.store,'record_many',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm()
        self.assertEqual(self.book.summary()['documents'],0);plan=self.confirm()
        retry=self.book.confirm(self.doc['id'],revision=1,plan_hash='retry');self.assertTrue(retry['duplicate'])
        with FinancialBook(self.path) as reopened:self.assertEqual(reopened.preview(self.doc['id'])['operation_review'],plan['operation_review'])

    def test_explicit_cashback_is_a_contribution_with_provenance_not_interest(self):
        pages=source();pages[0]=pages[0].replace('Depósitos +$50.00','Depósitos +$51.00').replace('estado de cuenta $130.00','estado de cuenta $131.00').replace('$5.00  $125.00','$6.00  $125.00')
        pages[1]=pages[1].replace('Nu México Financiera','07 ENE 2026 Cashback de tarjeta FICTICIA +$1.00\nNu México Financiera')
        doc=self.upload(synthetic_pdf(pages));self.confirm(doc,individual(doc));ledger=self.book.store.load_ledger()
        cashback=[m for m in ledger.movements if m.origin==Origin.CASHBACK]
        self.assertEqual(len(cashback),1);self.assertEqual(cashback[0].kind,Kind.CONTRIBUTION)
        self.assertEqual(ledger.external_contributions('MXN'),1);self.assertEqual(ledger.interest_received('MXN'),D('2.10'))
        self.assertEqual(next(D(r['cashback_contributions']) for a in self.book.evolution()['accounts'] if a['lane']=='debit' for r in a['history']),1)


class NuIndividualHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_individual_http_plan_confirm_evolution_and_normalized_review(self):
        doc=self.request('/api/upload',content(),raw=True);p=self.request('/api/documents/'+doc['id']+'/plan')
        self.assertEqual(p['nu_cajita_candidates'],['ficticia'])
        p=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=1,operation_review=individual(doc)))
        self.assertTrue(p['can_confirm'],p['issues'])
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=1,plan_hash=p['plan_hash'],operation_review=p['operation_review']))
        accounts=self.request('/api/book/evolution')['accounts'];self.assertEqual(len(accounts),3)
        self.assertEqual({a['portfolio'] for a in accounts if a['role']=='cajita'},{'ficticia','sin movimientos'})


if __name__=='__main__':unittest.main()
