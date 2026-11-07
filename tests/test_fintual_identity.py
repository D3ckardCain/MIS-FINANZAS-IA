"""Decisión del titular: Fintual MXN/USD; Alpaca solo perfil/custodio técnico."""
import json
from pathlib import Path
import tempfile
import unittest
from finanzas.intake import Inbox, analyze
from finanzas.book import FinancialBook
from tests import test_intake
from tests.test_book_alpaca import content as stock_content
from tests.test_book_fintual import content as fund_content


class FintualIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'bandeja.sqlite3'

    def test_catalog_has_one_fintual_and_no_alpaca_institution(self):
        with Inbox(self.path) as inbox:
            keys=[r['key'] for r in inbox.catalog()['institutions']]
        self.assertEqual(keys.count('fintual'),1);self.assertNotIn('alpaca',keys)

    def test_custodian_document_is_registered_as_fintual_usd(self):
        result=analyze(stock_content())
        self.assertEqual(result['institution'],'fintual');self.assertEqual(result['candidates'],['fintual'])
        self.assertEqual(result['custodian'],'alpaca');self.assertEqual(result['reader_profile'],'alpaca')
        self.assertEqual(result['portfolio_unit'],'USD')

    def test_manual_fintual_selection_uses_native_usd_reader_and_preserves_mxn_reader(self):
        for data,profile,unit in [(stock_content(),'alpaca','USD'),(fund_content(),'fintual','MXN')]:
            result=analyze(data,institution='fintual')
            self.assertEqual(result['institution'],'fintual');self.assertEqual(result['reader_profile'],profile)
            self.assertEqual(result['portfolio_unit'],unit)
            self.assertEqual(result['views']['investments']['mode'],'specialized')

    def test_two_portfolios_one_institution_and_distinct_units_accounts(self):
        with Inbox(self.path) as inbox:
            docs=[inbox.upload(data,'ficticio.pdf') for data in (fund_content(),stock_content())]
            self.assertEqual({d['institution'] for d in inbox.list()},{'fintual'})
        with FinancialBook(self.path) as book:
            for doc in docs:
                plan=book.preview(doc['id']);self.assertEqual(plan['institution'],'fintual')
                book.confirm(doc['id'],revision=1,plan_hash=plan['plan_hash'])
            accounts=book.summary()['accounts'];self.assertEqual(len(accounts),2)
            self.assertEqual({a['institution'] for a in accounts},{'fintual'})
            self.assertEqual({a['unit'] for a in accounts},{'USD','MXN'})
            self.assertEqual({a['portfolio'] for a in accounts},{'Acciones USD','Fondos MXN'})
            self.assertEqual({row[0] for row in book.db.execute('SELECT institution FROM documents')},{'fintual'})

    def test_legacy_inbox_is_presented_as_fintual_without_changing_original_or_revision(self):
        data=stock_content()
        with Inbox(self.path) as inbox:
            doc=inbox.upload(data,'legacy-ficticio.pdf');old=dict(doc['result'],institution='alpaca',candidates=['alpaca'])
            for key in ('reader_profile','custodian','portfolio_unit'):old.pop(key,None)
            with inbox.db:inbox.db.execute('UPDATE intake_files SET result=? WHERE id=?',(json.dumps(old),doc['id']))
            restored=inbox.get(doc['id'])
            self.assertEqual(restored['result']['institution'],'fintual');self.assertEqual(restored['revision'],1)
            self.assertEqual(inbox.original(doc['id']),data)
            self.assertEqual(inbox.list()[0]['institution'],'fintual')
        with FinancialBook(self.path) as book:
            plan=book.preview(doc['id']);self.assertEqual(plan['custodian'],'alpaca');self.assertTrue(plan['can_confirm'])

    def test_legacy_financial_batch_relabels_without_duplicate_or_rewriting_audit(self):
        with Inbox(self.path) as inbox:doc=inbox.upload(stock_content(),'legacy-ficticio.pdf')
        with FinancialBook(self.path) as book:
            plan=book.preview(doc['id']);book.confirm(doc['id'],revision=1,plan_hash=plan['plan_hash'])
            legacy=dict(plan,institution='alpaca')
            for key in ('reader_profile','custodian','portfolio_unit'):legacy.pop(key,None)
            raw=json.dumps(legacy)
            with book.db:book.db.execute('UPDATE book_batches SET plan_json=? WHERE document_id=?',(raw,doc['id']))
            before=book.store.load_ledger().movements
            self.assertEqual(book.preview(doc['id'])['institution'],'fintual')
            self.assertTrue(book.confirm(doc['id'],revision=1,plan_hash='retry')['duplicate'])
            self.assertEqual(book.summary()['accounts'][0]['institution'],'fintual')
            self.assertEqual(book.store.load_ledger().movements,before)
            self.assertEqual(book.db.execute('SELECT plan_json FROM book_batches').fetchone()[0],raw)

    def test_legacy_group_alias_preserved_but_explicit_fintual_choice_wins(self):
        with Inbox(self.path) as inbox:
            with inbox.db:inbox.db.execute('INSERT INTO intake_groups VALUES(?,?)',('alpaca','Acciones'))
            get=lambda:next(i for i in inbox.catalog()['institutions'] if i['key']=='fintual')['category']
            self.assertEqual(get(),'Acciones')
            inbox.set_group('fintual','Fondos y deuda');self.assertEqual(get(),'Fondos y deuda')


class FintualIdentityHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_navigation_document_and_financial_book_all_name_fintual(self):
        doc=self.request('/api/upload',stock_content(),raw=True)
        self.assertEqual(doc['result']['institution'],'fintual')
        state=self.request('/api/state')
        self.assertNotIn('alpaca',[i['key'] for i in state['catalog']['institutions']])
        self.assertEqual(state['documents'][0]['institution'],'fintual')
        plan=self.request('/api/documents/'+doc['id']+'/plan');self.assertEqual(plan['institution'],'fintual')
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=1,plan_hash=plan['plan_hash']))
        self.assertEqual(self.request('/api/book')['accounts'][0]['institution'],'fintual')
