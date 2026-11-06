"""BanCoppel al libro: cuenta de paso, cargos e identidad sin capital inventado."""
from decimal import Decimal
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from finanzas.book import FinancialBook
from finanzas.intake import Inbox
from finanzas.ledger import Kind, Origin
from tests import test_intake
from tests.test_bancoppel import statement
from tests.test_book import content as openbank_content
from tests.test_book_mifel import content as mifel_content
from tests.test_openbank import synthetic_pdf as raw_pdf


def synthetic_pdf(pages):
    return raw_pdf(['Moneda Nacional $\n'+page for page in pages])


def content(*, next_period=False, no_interest=False, extra=''):
    text=statement()
    if no_interest:
        text=text.replace('01/11 0.25 124.70\nPAGO DE INTERESES\n','')
        text=text.replace('124.70','124.45').replace('\n0.25\n','\n0.00\n')
    if next_period:
        text=text.replace('12/DIC./2025 AL 11/ENE./2026','12/ENE./2026 AL 11/FEB./2026')
        mapping={'100.00':'124.70','150.00':'174.70','130.00':'154.70','125.25':'149.95','124.45':'149.15','124.70':'149.40'}
        text=re.sub('|'.join(re.escape(v) for v in mapping),lambda m:mapping[m[0]],text)
        dates={'12/15':'01/15','12/20':'01/20','01/05':'02/05','01/11':'02/11'}
        text=re.sub('|'.join(dates),lambda m:dates[m[0]],text)
    return synthetic_pdf([text+'\n'+extra])


class BanCoppelBookTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'bandeja.sqlite3';self.doc=self.upload(content())
        self.book=FinancialBook(self.path);self.addCleanup(self.book.close)

    def upload(self,data):
        with Inbox(self.path) as inbox:return inbox.upload(data,'ejemplo-ficticio.pdf')

    def confirm(self,doc=None):
        doc=doc or self.doc;plan=self.book.preview(doc['id']);self.assertTrue(plan['can_confirm'],plan['issues'])
        return self.book.confirm(doc['id'],revision=plan['revision'],plan_hash=plan['plan_hash'])

    def test_one_transit_account_cash_and_spei_are_not_external_capital(self):
        plan=self.book.preview(self.doc['id']);self.assertEqual(len(plan['periods']),1)
        self.assertEqual(plan['periods'][0]['lane'],'debit');self.assertEqual(plan['transfers'],[])
        self.confirm();ledger=self.book.store.load_ledger()
        self.assertEqual(len(ledger.movements),6)
        self.assertEqual(ledger.external_contributions('MXN'),0)
        self.assertEqual(len(ledger.pending_origins()),2)
        self.assertFalse(any(m.kind==Kind.OPENING for m in ledger.movements))
        account=self.book.summary()['accounts'][0]
        self.assertEqual(account['role'],'transit');self.assertEqual(account['closing'],'124.70')
        self.assertEqual(sum(m.signed_amount for m in ledger.movements),Decimal('24.70'))

    def test_commission_vat_and_isr_are_separate_and_charged_once(self):
        result=self.confirm();ledger=self.book.store.load_ledger()
        fees=[m for m in ledger.movements if m.kind==Kind.FEE]
        self.assertEqual(len(fees),2);self.assertEqual(sum(m.amount for m in fees),Decimal('5.55'))
        self.assertEqual(ledger.withholding_recorded('MXN'),0)
        self.assertEqual({m['category'] for m in result['movements'] if m['kind']=='comision'},{'commission','commission_vat'})
        self.assertEqual(Decimal(self.book.summary()['accounts'][0]['charges_fees_and_vat']),Decimal('5.55'))

    def test_zero_interest_document_never_creates_investment_or_yield(self):
        result=self.confirm(self.upload(content(no_interest=True)))
        self.assertFalse(any(m['kind']=='interes_cobrado' for m in result['movements']))
        self.assertEqual(self.book.store.load_ledger().interest_received('MXN'),0)
        self.assertEqual(len(self.book.summary()['accounts']),1)
        self.assertEqual(self.book.summary()['accounts'][0]['closing'],'124.45')

    def test_explicit_interest_keeps_its_date_across_year_boundary(self):
        result=self.confirm();income=next(m for m in result['movements'] if m['kind']=='interes_cobrado')
        self.assertEqual(income['effective_date'],'2026-01-11')
        self.assertEqual(result['periods'][0]['start'],'2025-12-12')
        self.assertEqual(result['reported_terms']['annual_rate_reported'],'0.10')

    def test_spei_return_is_contribution_with_pending_origin_not_a_yield(self):
        doc=self.upload(synthetic_pdf([statement().replace('DEPOSITO EN EFECTIVO','DEVOLUCION SPEI')]))
        result=self.confirm(doc);returned=next(m for m in result['movements'] if m.get('category')=='transfer_return')
        self.assertEqual(returned['kind'],'aportacion');self.assertEqual(returned['origin'],'pendiente')
        self.assertEqual(self.book.store.load_ledger().external_contributions('MXN'),0)

    def test_equal_amount_and_date_deposits_remain_two_distinct_evidences(self):
        text=statement()
        replacements={'150.00':'200.00','130.00':'180.00','125.25':'175.25','124.45':'174.45','124.70':'174.70'}
        text=re.sub('|'.join(re.escape(v) for v in replacements),lambda m:replacements[m[0]],text)
        text=text.replace('Hoja 1 de 2','12/15 50.00 150.00\nDEPOSITO EN EFECTIVO\nHoja 1 de 2').replace('\n50.00\n','\n100.00\n')
        result=self.confirm(self.upload(synthetic_pdf([text])))
        deposits=[m for m in result['movements'] if m.get('category')=='cash_deposit']
        self.assertEqual(len(deposits),2);self.assertNotEqual(deposits[0]['id'],deposits[1]['id'])
        self.assertEqual(self.book.summary()['accounts'][0]['closing'],'174.70')

    def test_retries_reopen_and_other_pdf_same_period_do_not_duplicate(self):
        self.confirm();result=self.book.confirm(self.doc['id'],revision=1,plan_hash='retry')
        self.assertTrue(result['duplicate'])
        with FinancialBook(self.path) as other:self.assertEqual(other.summary()['movements'],6)
        other=self.upload(content(extra='Mismo periodo, archivo distinto'));plan=self.book.preview(other['id'])
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('superpuesto' in s for s in plan['issues']))

    def test_months_out_of_order_preserve_transit_account_and_continuity(self):
        self.confirm(self.upload(content(next_period=True)));self.confirm()
        summary=self.book.summary();self.assertEqual(len(summary['accounts']),1)
        self.assertEqual(summary['accounts'][0]['periods'],2)
        self.assertEqual(summary['accounts'][0]['closing'],'149.40')
        self.assertEqual(summary['accounts'][0]['gaps'],[])

    def test_missing_conflicting_identity_or_discrepancies_block(self):
        sources=[statement().replace('Número de Cuenta:','Identificador ausente:'),
                 statement()+'\nNúmero de Cuenta:\nCLABE:\n22222222222',statement(commission='5.00'),
                 statement(gross='0.35',withholding='0.10')]
        for text in sources:
            plan=self.book.preview(self.upload(synthetic_pdf([text]))['id']);self.assertFalse(plan['can_confirm'])
        self.assertEqual(self.book.summary()['documents'],0)

    def test_failure_after_writing_reverts_approval_movements_and_coverage(self):
        original=self.book.store.record_many
        def fail(rows):original(rows);raise ValueError('Fallo de prueba')
        with patch.object(self.book.store,'record_many',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm()
        self.assertEqual(self.book.summary()['documents'],0)
        self.assertEqual(self.book.store.load_ledger().movements,())
        self.assertEqual(self.book.store.review_history(self.doc['id']),())
        self.confirm()

    def test_currency_is_not_inferred_from_institution_or_dollar_sign(self):
        for text in (statement(),'Moneda USD $\n'+statement(),'Moneda Nacional $\nMoneda USD $\n'+statement()):
            plan=self.book.preview(self.upload(raw_pdf([text]))['id'])
            self.assertFalse(plan['can_confirm'])
            self.assertTrue(any('moneda' in s for s in plan['issues']))

    def test_three_institutions_remain_distinct(self):
        self.confirm();self.confirm(self.upload(openbank_content()));self.confirm(self.upload(mifel_content()))
        summary=self.book.summary()
        self.assertEqual(summary['documents'],3);self.assertEqual(len(summary['accounts']),4)
        self.assertEqual({a['institution'] for a in summary['accounts']},{'bancoppel','openbank','mifel'})
        self.assertEqual(sum(a['role']=='transit' for a in summary['accounts']),1)


class BanCoppelFinancialHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_upload_plan_confirm_and_transit_book_http(self):
        doc=self.request('/api/upload',content(),raw=True)
        plan=self.request('/api/documents/'+doc['id']+'/plan')
        self.assertTrue(plan['can_confirm'],plan['issues'])
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=plan['revision'],plan_hash=plan['plan_hash']))
        book=self.request('/api/book');self.assertEqual(book['documents'],1)
        self.assertEqual(book['accounts'][0]['role'],'transit')


if __name__=='__main__':unittest.main()
