"""Doopla ficticio: componentes de efectivo y retención desconocida distinta de cero."""
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
from tests.test_doopla import statement
from tests.test_openbank import synthetic_pdf


def content(pages=None,*,currency='MXN',modern=False,next_period=False,repeated_annex=False,explicit_zero=False,extra=''):
    pages=list(pages or statement(modern))
    if modern:
        # Caso ficticio coherente: conserva el signo del resumen y ambos IVA.
        pages[0]=pages[0].replace('IVA  FICTICIO  -  -  -  -$ 0.32','IVA  FICTICIO  -  -  -  -$ 0.64')
        pages[0]=pages[0].replace('(-) Egresos $ 3.30','(-) Egresos $ 3.62')
        pages[0]=pages[0].replace('Efectivo disponible para retiro $ 19.02','Efectivo disponible para retiro $ 18.70')
    if explicit_zero:pages[0]=pages[0].replace('(-) Retiros realizados:', '(-) ISR: $ 0.00\n(-) Retiros realizados:')
    if next_period:
        pages=[p.replace('01-Ene-26 al 31-Ene-26','01-Feb-26 al 28-Feb-26').replace('-01-2026','-02-2026') for p in pages]
        pages[0]=pages[0].replace('Saldo al final de período $ 120.32','Saldo al final de período $ 140.64')
        pages[0]=pages[0].replace('Valor de cuenta al inicio de período $ 100.00','Valor de cuenta al inicio de período $ 120.32')
        pages[0]=pages[0].replace('Saldo al inicio del período $ 0.00','Saldo al inicio del período $ 20.32')
        pages[0]=pages[0].replace('Efectivo disponible para retiro $ 20.32','Efectivo disponible para retiro $ 40.64')
        if not repeated_annex:
            pages[1]=pages[1].replace('1 de 12','2 de 12').replace('$ 110.00  $ 12.32  $ 2.00  $ 0.32  $ 10.00',
                '$ 120.00  $ 24.64  $ 4.00  $ 0.64  $ 20.00')
    if currency:pages[0]+='\nMoneda: '+currency+'\n'
    pages[-1]+='\n'+extra
    return synthetic_pdf(pages)


def protected_content():
    from pypdf import PdfReader, PdfWriter
    writer=PdfWriter();writer.append(PdfReader(BytesIO(content())))
    writer.encrypt('ONLY-FICTITIOUS-DOOPLA');buffer=BytesIO();writer.write(buffer)
    return buffer.getvalue()


class DooplaBookTests(unittest.TestCase):
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

    def test_one_cash_account_without_loan_value_or_accumulated_income_twice(self):
        result=self.confirm();summary=self.book.summary()
        self.assertEqual(len(result['periods']),1);self.assertEqual(len(summary['accounts']),1)
        self.assertEqual(summary['accounts'][0]['closing'],'20.32')
        self.assertEqual(result['platform_summary_observation']['final'],'120.32')
        self.assertEqual(result['loan_snapshots'][0]['pending_principal'],'100.00')
        self.assertEqual(result['loan_snapshots'][0]['as_of'],'2026-01-31')
        self.assertEqual(len(self.book.store.load_ledger().movements),7)

    def test_payment_split_principal_interest_and_vat_not_capital_or_gain_twice(self):
        result=self.confirm();ledger=self.book.store.load_ledger()
        pay=[m for m in result['movements'] if m.get('category')=='payment']
        self.assertEqual({m['component'] for m in pay},{'principal','interest','vat'})
        self.assertEqual(len({m['id'] for m in pay}),3)
        self.assertEqual(ledger.interest_received('MXN'),D('2'))
        self.assertEqual(sum(m.amount for m in ledger.movements if m.kind==Kind.VAT_RECEIVED),D('.32'))
        self.assertEqual(ledger.external_contributions('MXN'),0)
        self.assertEqual(sum(m.amount for m in ledger.movements if m.kind==Kind.CONTRIBUTION),D('35'))

    def test_missing_withholding_stays_unknown_in_ledger_summary_and_net(self):
        result=self.confirm();account=self.book.summary()['accounts'][0]
        self.assertEqual(result['withholding_status'],'unknown')
        self.assertIsNone(self.book.store.load_ledger().withholding_recorded('MXN'))
        self.assertIsNone(account['withholding']);self.assertIsNone(account['interest_net_of_withholding'])
        self.assertFalse(account['withholding_complete'])

    def test_documented_zero_is_distinct_from_missing_retention(self):
        self.confirm(self.upload(content(explicit_zero=True)))
        self.assertEqual(self.book.store.load_ledger().withholding_recorded('MXN'),0)
        account=self.book.summary()['accounts'][0]
        self.assertTrue(account['withholding_complete']);self.assertEqual(account['withholding'],'0.00')
        self.assertEqual(account['interest_net_of_withholding'],'2.00')

    def test_modern_actual_isr_vat_and_grouped_fee_separate(self):
        result=self.confirm(self.upload(content(modern=True)));ledger=self.book.store.load_ledger()
        self.assertEqual(ledger.withholding_recorded('MXN'),D('.40'))
        self.assertEqual(ledger.interest_received('MXN'),D('2'))
        self.assertEqual(sum(m.amount for m in ledger.movements if m.kind==Kind.FEE),D('.58'))
        account=self.book.summary()['accounts'][0]
        self.assertEqual(account['vat_received'],'0.32');self.assertEqual(account['vat_paid'],'0.64')
        self.assertEqual(account['withholding'],'0.40');self.assertEqual(account['closing'],'18.70')
        self.assertEqual(result['commission_components_observation'],{'commission':'0.50','commission_vat':'0.08'})
        self.assertEqual(result['platform_summary_observation']['interest_vat_sign'],-1)

    def test_investment_cancellation_and_principal_do_not_infer_reinvestment(self):
        result=self.confirm();ledger=self.book.store.load_ledger()
        self.assertEqual(result['transfers'],[])
        capital=[m for m in ledger.movements if m.kind in (Kind.CONTRIBUTION,Kind.WITHDRAWAL)]
        self.assertTrue(all(m.origin==Origin.UNKNOWN for m in capital))
        self.assertEqual(sorted(m.amount for m in capital if m.kind==Kind.WITHDRAWAL),[D('2'),D('15')])
        self.assertFalse(any(m.origin==Origin.REINVESTMENT for m in ledger.movements))

    def test_arrears_and_cumulative_loan_interest_do_not_create_loss_or_income(self):
        result=self.confirm();ledger=self.book.store.load_ledger()
        self.assertEqual(result['arrears_observations'][0]['days'],90)
        self.assertEqual(result['arrears_observations'][0]['collection_action'],'Cobranza extra judicial')
        self.assertEqual(ledger.interest_received('MXN'),D('2'))
        self.assertEqual(len(ledger.movements),7)

    def test_rewards_are_other_income_without_capital_or_interest(self):
        pages=statement();pages[0]=pages[0].replace('(+) Recompensas recibidas: $ 0.00','(+) Recompensas recibidas: $ 1.00')
        pages[0]=pages[0].replace('(+) Recompensas $ 0.00','(+) Recompensas $ 1.00')
        pages[0]=pages[0].replace('Saldo al final de período $ 120.32','Saldo al final de período $ 121.32')
        pages[0]=pages[0].replace('Efectivo disponible para retiro $ 20.32','Efectivo disponible para retiro $ 21.32')
        pages[0]+='06-01-2026  Recompensa  -  -  -  $ 1.00\n'
        self.confirm(self.upload(content(pages)))
        ledger=self.book.store.load_ledger();self.assertEqual(ledger.external_contributions('MXN'),0)
        self.assertEqual(ledger.interest_received('MXN'),D('2'))
        self.assertEqual(self.book.summary()['accounts'][0]['rewards'],'1.00')

    def test_equal_payment_rows_keep_distinct_component_evidence(self):
        pages=statement();line='02-01-2026  Pago  FICTICIO  $ 10.00  $ 2.00  $ 0.32  $ 12.32'
        small='02-01-2026  Pago  FICTICIO  $ 5.00  $ 1.00  $ 0.16  $ 6.16'
        pages[0]=pages[0].replace(line,small+'\n'+small)
        result=self.confirm(self.upload(content(pages)))
        pay=[m for m in result['movements'] if m.get('category')=='payment']
        self.assertEqual(len(pay),6);self.assertEqual(len({m['id'] for m in pay}),6)
        self.assertEqual(self.book.store.load_ledger().interest_received('MXN'),D('2'))

    def test_inconsistent_modern_summary_or_bad_component_blocks_whole_batch(self):
        bad=[statement(True),[p.replace('$ 10.00  $ 2.00','$ 9.99  $ 2.00') for p in statement()],
            [p.replace('TOTAL  $ 110.00  $ 12.32','TOTAL  $ 110.00  $ 12.31') for p in statement()]]
        for pages in bad:self.assertFalse(self.book.preview(self.upload(content(pages))['id'])['can_confirm'])
        self.assertEqual(self.book.summary()['documents'],0)

    def test_unknown_components_are_not_zero_and_unknown_concepts_block(self):
        for old,new in [('$ 10.00  $ 2.00  $ 0.32  $ 12.32','-  $ 2.00  $ 0.32  $ 2.32'),('  Pago  ','  Ajuste  ')]:
            pages=[p.replace(old,new) for p in statement()]
            self.assertFalse(self.book.preview(self.upload(content(pages))['id'])['can_confirm'])

    def test_currency_review_bound_to_document_and_foreign_cannot_override(self):
        doc=self.upload(content(currency=None));plan=self.book.preview(doc['id'])
        self.assertTrue(plan['currency_confirmation_required'])
        reviewed=self.book.preview(doc['id'],currency_confirmation='MXN');self.assertTrue(reviewed['can_confirm'])
        with self.assertRaises(ValueError):self.book.confirm(doc['id'],revision=1,plan_hash=reviewed['plan_hash'])
        self.confirm(doc,currency_confirmation='MXN')
        for unit in ('USD','CAD','dólares','euros','USD\nMoneda: MXN'):
            plan=self.book.preview(self.upload(content(currency=unit))['id'],currency_confirmation='MXN')
            self.assertFalse(plan['can_confirm']);self.assertFalse(plan['currency_confirmation_required'])

    def test_out_of_order_months_retry_and_overlap(self):
        self.confirm(self.upload(content(next_period=True)));self.confirm()
        self.assertTrue(self.book.confirm(self.doc['id'],revision=1,plan_hash='retry')['duplicate'])
        with FinancialBook(self.path) as other:self.assertEqual(other.summary()['documents'],2)
        plan=self.book.preview(self.upload(content(extra='Otra representacion'))['id'])
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('superpuesto' in i for i in plan['issues']))

    def test_repeated_loan_annex_with_capital_activity_blocks_in_both_orders(self):
        self.confirm();plan=self.book.preview(self.upload(content(next_period=True,repeated_annex=True))['id'])
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('repetida' in i for i in plan['issues']))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'other.sqlite3'
            with Inbox(path) as inbox:
                after=inbox.upload(content(next_period=True,repeated_annex=True),'after.pdf')
                before=inbox.upload(content(),'before.pdf')
            with FinancialBook(path) as book:
                plan=book.preview(after['id']);book.confirm(after['id'],revision=1,plan_hash=plan['plan_hash'])
                plan=book.preview(before['id']);self.assertFalse(plan['can_confirm'])
                self.assertTrue(any('repetida' in i for i in plan['issues']))

    def test_unknown_withholding_in_one_month_keeps_aggregate_incomplete(self):
        self.confirm();self.confirm(self.upload(content(next_period=True,explicit_zero=True)))
        account=self.book.summary()['accounts'][0]
        self.assertFalse(account['withholding_complete']);self.assertIsNone(account['withholding'])
        self.assertEqual(account['withholding_documented'],'0.00');self.assertIsNone(account['interest_net_of_withholding'])

    def test_stale_review_and_rollback_of_split_payment(self):
        plan=self.book.preview(self.doc['id'])
        with Inbox(self.path) as inbox:inbox.review(self.doc['id'],expected_revision=1,decision='reviewed')
        with self.assertRaises(ValueError):self.book.confirm(self.doc['id'],revision=1,plan_hash=plan['plan_hash'])
        original=self.book.store.record_many
        def fail(rows):original(rows);raise ValueError('Fallo simulado')
        with patch.object(self.book.store,'record_many',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm()
        self.assertEqual(self.book.summary()['documents'],0);self.assertEqual(self.book.store.load_ledger().movements,())
        self.assertEqual(self.book.store.review_history(self.doc['id']),());self.confirm()

    def test_protected_original_reread_without_password_saved(self):
        with Inbox(self.path) as inbox:doc=inbox.upload(protected_content(),'protected.pdf',password='ONLY-FICTITIOUS-DOOPLA')
        for password in (None,'WRONG-FICTITIOUS'):
            plan=self.book.preview(doc['id'],password=password);self.assertTrue(plan['password_required'])
        result=self.confirm(doc,password='ONLY-FICTITIOUS-DOOPLA')
        self.assertNotIn('ONLY-FICTITIOUS-DOOPLA',str(result))
        self.assertNotIn('ONLY-FICTITIOUS-DOOPLA',str(list(self.book.db.iterdump())))

    def test_ten_institutions_without_duplicate_cash_or_loan_accounts(self):
        from tests.test_book import content as openbank
        from tests.test_book_mifel import content as mifel
        from tests.test_book_bancoppel import content as bancoppel
        from tests.test_book_didi import content as didi
        from tests.test_book_fondeadora import content as fondeadora
        from tests.test_book_plata import content as plata
        from tests.test_book_supertasas import content as supertasas
        from tests.test_book_hey import content as hey
        from tests.test_book_kapital import content as kapital
        self.confirm()
        for fixture in (openbank,mifel,bancoppel,didi,fondeadora,plata,supertasas,hey,kapital):self.confirm(self.upload(fixture()))
        self.assertEqual(self.book.summary()['documents'],10);self.assertEqual(len(self.book.summary()['accounts']),12)


class DooplaFinancialHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_currency_review_confirmation_and_unknown_withholding_http(self):
        doc=self.request('/api/upload',content(currency=None),raw=True)
        plan=self.request('/api/documents/'+doc['id']+'/plan');self.assertTrue(plan['currency_confirmation_required'])
        plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=1,currency_confirmation='MXN'))
        self.assertTrue(plan['can_confirm'])
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=1,plan_hash=plan['plan_hash'],currency_confirmation='MXN'))
        account=self.request('/api/book')['accounts'][0];self.assertIsNone(account['withholding'])
        self.assertEqual(account['vat_received'],'0.32')

    def test_encrypted_reader_and_confirmation_http(self):
        doc=self.request('/api/upload',protected_content(),raw=True)
        doc=self.request('/api/documents/'+doc['id']+'/reprocess',dict(revision=1,password='ONLY-FICTITIOUS-DOOPLA'))
        plan=self.request('/api/documents/'+doc['id']+'/plan');self.assertTrue(plan['password_required'])
        plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=doc['revision'],password='ONLY-FICTITIOUS-DOOPLA'))
        self.assertTrue(plan['can_confirm'])
        result=self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=doc['revision'],plan_hash=plan['plan_hash'],password='ONLY-FICTITIOUS-DOOPLA'))
        self.assertEqual(result['status'],'imported')


if __name__=='__main__':unittest.main()
