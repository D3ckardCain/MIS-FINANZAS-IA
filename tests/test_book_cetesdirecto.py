"""CETESdirecto ficticio: efectivo liquidado y cobros sin principal inferido."""
from pathlib import Path
from decimal import Decimal as D
from io import BytesIO
import re
import tempfile
import unittest
from unittest.mock import patch
from finanzas.book import FinancialBook
from finanzas.intake import Inbox
from finanzas.ledger import Kind,Origin
from tests import test_intake
from tests.test_cetesdirecto import statement
from tests.test_openbank import synthetic_pdf


def content(pages=None,*,new_format=False,next_period=False,extra=''):
    pages=list(pages or statement(new_format=new_format))
    if next_period:
        pages=[p.replace('01/01/2026 al 31/01/2026','01/02/2026 al 28/02/2026')
            .replace('30/12/25','30/01/26').replace('02/01/26','02/02/26') for p in pages]
        pages[0]=pages[0].replace('Total de efectivo: $ 0.00','Total de efectivo: $ -0.15').replace('Total final: $ 11.20','Total final: $ 11.05')
        pages[0]=pages[0].replace('Intereses acumulados del ejercicio fiscal: $ 1.00','Intereses acumulados del ejercicio fiscal: $ 2.00')
        pages[0]=pages[0].replace('ISR acumulado del ejercicio fiscal: $ 0.05','ISR acumulado del ejercicio fiscal: $ 0.10')
        pages[1]=pages[1].replace('Total de cartera: $ 10.00','Total de cartera: $ 11.20').replace('Total de efectivo: $ 0.15','Total de efectivo: $ 0.00')
        pages[1]=pages[1].replace('Total inicial: $ 10.15','Total inicial: $ 11.20').replace('10.00000000 10.00','11.20000000 11.20').replace('Posición Total 10.00','Posición Total 11.20')
        pages[1]=pages[1].replace('Saldo inicial 0.15','Saldo inicial 0.00').replace('0.00 -9.95','0.00 -10.10')
        pages[1]=pages[1].replace('11.00 1.05','11.00 0.90').replace('0.05 0.00 1.00','0.05 0.00 0.85')
        pages[1]=pages[1].replace('1.00 0.00 0.00','1.00 0.00 -0.15').replace('Saldo final 0.00','Saldo final -0.15')
    pages[-1]+='\n'+extra
    return synthetic_pdf(pages)


def empty_pages():
    pages=statement()
    pages[0]=pages[0].replace('Total de cartera: $ 11.20','Total de cartera: $ 0.00').replace('Total de efectivo: $ 0.00','Total de efectivo: $ 0.10')
    pages[0]=pages[0].replace('Total final: $ 11.20','Total final: $ 0.10').replace('ISR del período: $ 0.05','ISR del período: $ 0.00').replace('Intereses del período: $ 1.00','Intereses del período: $ 0.00')
    pages[1]=pages[1].replace('Total de cartera: $ 10.00','Total de cartera: $ 0.00').replace('Total de efectivo: $ 0.15','Total de efectivo: $ 0.10')
    pages[1]=pages[1].replace('Total inicial: $ 10.15','Total inicial: $ 0.10').replace('Saldo inicial 0.15','Saldo inicial 0.10').replace('Saldo final 0.00','Saldo final 0.10')
    result=[]
    for page in pages:
        page='\n'.join(line for line in page.splitlines() if not line.startswith(('CETES ','BONDDIA ')) and not re.match(r'^\d{2}/\d{2}/\d{2}\b',line))
        page=re.sub(r'Posición Total [\d.]+','Posición Total 0.00',page)
        result.append(page)
    return result


def protected_content():
    from pypdf import PdfReader,PdfWriter
    w=PdfWriter();w.append(PdfReader(BytesIO(content())));w.encrypt('ONLY-FICTITIOUS-CETES')
    b=BytesIO();w.write(b);return b.getvalue()


class CetesBookTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'bandeja.sqlite3';self.doc=self.upload(content())
        self.book=FinancialBook(self.path);self.addCleanup(self.book.close)

    def upload(self,data):
        with Inbox(self.path) as inbox:return inbox.upload(data,'ejemplo-ficticio.pdf')

    def confirm(self,doc=None,**kwargs):
        doc=doc or self.doc;plan=self.book.preview(doc['id'],**kwargs)
        self.assertTrue(plan['can_confirm'],plan['issues'])
        return self.book.confirm(doc['id'],revision=plan['revision'],plan_hash=plan['plan_hash'],password=kwargs.get('password'))

    def test_one_cash_account_with_positions_not_added_as_balance(self):
        result=self.confirm();summary=self.book.summary()
        self.assertEqual(len(summary['accounts']),1);self.assertEqual(summary['accounts'][0]['role'],'fund_cash')
        self.assertEqual(summary['accounts'][0]['closing'],'0.00')
        self.assertEqual(result['security_summary_observation']['final_total'],'11.20')
        self.assertEqual(len(result['security_final_positions']),2)
        self.assertEqual(len(self.book.store.load_ledger().movements),4)

    def test_amortization_receipt_not_capital_or_interest_inferred_from_market_value(self):
        result=self.confirm();ledger=self.book.store.load_ledger()
        receipts=[m for m in ledger.movements if m.kind==Kind.SECURITY_PROCEEDS]
        self.assertEqual([m.amount for m in receipts],[D('11')])
        self.assertFalse(any(m.kind in (Kind.CONTRIBUTION,Kind.INTEREST) for m in ledger.movements))
        self.assertEqual(ledger.external_contributions('MXN'),0)
        self.assertEqual(result['security_receipts'][0]['allocation_status'],'principal_interest_unallocated')

    def test_interest_reported_and_classified_unknown_distinct_not_zero(self):
        self.confirm();account=self.book.summary()['accounts'][0]
        self.assertEqual(account['interest_reported'],'1.00');self.assertEqual(account['security_proceeds'],'11.00')
        self.assertIsNone(account['interest']);self.assertFalse(account['interest_complete'])
        self.assertIsNone(account['interest_net_of_withholding'])
        self.assertEqual(account['withholding'],'0.05')

    def test_registered_before_month_settled_inside_preserves_dates_and_negative_intermediate(self):
        result=self.confirm();trade=result['movements'][0]
        self.assertEqual(trade['registered'],'2025-12-30');self.assertEqual(trade['settled'],'2026-01-02')
        self.assertEqual(trade['effective_date'],'2026-01-02')
        self.assertEqual(result['periods'][0]['initial'],'0.15')

    def test_tax_period_once_and_annual_accumulated_not_reimported(self):
        pages=statement(new_format=True)
        pages[0]=pages[0].replace('ISR Retenido acumulado del ejercicio fiscal: $ 0.05','ISR Retenido acumulado del ejercicio fiscal: $ 0.75')
        result=self.confirm(self.upload(content(pages)))
        self.assertEqual(result['security_summary_observation']['withholding_cumulative'],'0.75')
        self.assertEqual(self.book.store.load_ledger().withholding_recorded('MXN'),D('.05'))

    def test_sale_kept_as_security_receipt_without_realized_gain(self):
        pages=statement();pages[1]=pages[1].replace('AMORTIZACION','VTASI')
        result=self.confirm(self.upload(content(pages)))
        self.assertEqual(result['security_receipts'][0]['operation'],'VTASI')
        self.assertEqual(self.book.summary()['accounts'][0]['security_proceeds'],'11.00')
        self.assertIsNone(self.book.summary()['accounts'][0]['interest'])

    def test_same_folio_amortization_and_tax_remain_distinct(self):
        result=self.confirm();pair=result['movements'][1:3]
        self.assertEqual(pair[0]['folio'],pair[1]['folio']);self.assertNotEqual(pair[0]['id'],pair[1]['id'])

    def test_liquidation_outside_period_is_not_moved_to_registration(self):
        pages=statement();pages[1]=pages[1].replace('30/12/25 02/01/26','30/01/26 02/02/26')
        plan=self.book.preview(self.upload(content(pages))['id'])
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('Liquidación' in i for i in plan['issues']))

    def test_unknown_code_contradictory_currency_and_summary_difference_block(self):
        for pages in (statement(movement='UNKNOWN'),statement(closing_cash='0.10')):
            self.assertFalse(self.book.preview(self.upload(content(pages))['id'])['can_confirm'])
        pages=statement();pages[0]+='\nMoneda: USD\n'
        self.assertFalse(self.book.preview(self.upload(content(pages))['id'])['can_confirm'])

    def test_column_code_contradiction_blocked_even_if_balances_still_match(self):
        pages=statement();pages[1]=pages[1].replace('SVD10002AMORTIZACION','SVD10002COMPRA')
        plan=self.book.preview(self.upload(content(pages))['id'])
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('columna' in i for i in plan['issues']))

    def test_empty_explicit_totals_keep_cash_and_zero_tax(self):
        result=self.confirm(self.upload(content(empty_pages())))
        self.assertEqual(result['security_final_positions'],[]);self.assertEqual(len(result['movements']),1)
        account=self.book.summary()['accounts'][0]
        self.assertEqual(account['closing'],'0.10');self.assertEqual(account['interest'],'0')
        self.assertTrue(account['interest_complete']);self.assertEqual(account['withholding'],'0.00')

    def test_equal_receipts_same_date_keep_distinct_evidence(self):
        pages=statement();line='02/01/26 02/01/26 SVD10002AMORTIZACION CETES 260102 1 0 0.00 11.00 1.05'
        one='02/01/26 02/01/26 SVD10002AMORTIZACION CETES 260102 1 0 0.00 5.50 -4.45'
        two='02/01/26 02/01/26 SVD10004AMORTIZACION CETES 260102 1 0 0.00 5.50 1.05'
        pages[1]=pages[1].replace(line,one+'\n'+two)
        result=self.confirm(self.upload(content(pages)))
        self.assertEqual(len(result['security_receipts']),2)
        self.assertEqual(len({r['locator'] for r in result['security_receipts']}),2)

    def test_retry_reopen_overlap_and_out_of_order_periods(self):
        self.confirm(self.upload(content(next_period=True)));self.confirm()
        self.assertTrue(self.book.confirm(self.doc['id'],revision=1,plan_hash='retry')['duplicate'])
        with FinancialBook(self.path) as other:self.assertEqual(other.summary()['documents'],2)
        account=self.book.summary()['accounts'][0]
        self.assertEqual(account['closing'],'-0.15');self.assertEqual(account['interest_reported'],'2.00')
        self.assertEqual(account['withholding'],'0.10');self.assertIsNone(account['interest'])
        plan=self.book.preview(self.upload(content(extra='Otra representacion'))['id'])
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('superpuesto' in i for i in plan['issues']))

    def test_stale_review_and_failure_roll_back_receipt_tax_and_period(self):
        plan=self.book.preview(self.doc['id'])
        with Inbox(self.path) as inbox:inbox.review(self.doc['id'],expected_revision=1,decision='reviewed')
        with self.assertRaises(ValueError):self.book.confirm(self.doc['id'],revision=1,plan_hash=plan['plan_hash'])
        original=self.book.store.record_many
        def fail(rows):original(rows);raise ValueError('Fallo simulado')
        with patch.object(self.book.store,'record_many',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm()
        self.assertEqual(self.book.summary()['documents'],0);self.assertEqual(self.book.store.load_ledger().movements,())
        self.assertEqual(self.book.store.review_history(self.doc['id']),());self.confirm()

    def test_protected_original_reread_without_saved_password(self):
        with Inbox(self.path) as inbox:doc=inbox.upload(protected_content(),'protected.pdf',password='ONLY-FICTITIOUS-CETES')
        self.assertTrue(self.book.preview(doc['id'])['password_required'])
        result=self.confirm(doc,password='ONLY-FICTITIOUS-CETES')
        self.assertNotIn('ONLY-FICTITIOUS-CETES',str(result))
        self.assertNotIn('ONLY-FICTITIOUS-CETES',str(list(self.book.db.iterdump())))

    def test_interest_status_is_per_account_and_fintual_keeps_its_identity(self):
        from tests.test_book_mifel import content as mifel
        from tests.test_book_fintual import content as fund
        from tests.test_book_alpaca import content as stocks
        self.confirm()
        for fixture in (mifel,fund,stocks):self.confirm(self.upload(fixture()))
        accounts=self.book.summary()['accounts']
        known=next(a for a in accounts if a['institution']=='mifel')
        self.assertTrue(known['interest_complete']);self.assertIsNotNone(known['interest'])
        self.assertIsNone(next(a for a in accounts if a['institution']=='cetesdirecto')['interest'])
        self.assertEqual({a['unit'] for a in accounts if a['institution']=='fintual'},{'MXN','USD'})
        self.assertFalse(any(a['institution']=='alpaca' for a in accounts))


class CetesFinancialHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_cash_confirmation_keeps_reported_interest_separate_http(self):
        doc=self.request('/api/upload',content(),raw=True)
        plan=self.request('/api/documents/'+doc['id']+'/plan');self.assertTrue(plan['can_confirm'])
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=1,plan_hash=plan['plan_hash']))
        account=self.request('/api/book')['accounts'][0]
        self.assertIsNone(account['interest']);self.assertEqual(account['interest_reported'],'1.00')
        self.assertEqual(account['security_proceeds'],'11.00')

    def test_encrypted_reader_and_confirmation_http(self):
        doc=self.request('/api/upload',protected_content(),raw=True)
        doc=self.request('/api/documents/'+doc['id']+'/reprocess',dict(revision=1,password='ONLY-FICTITIOUS-CETES'))
        plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=doc['revision'],password='ONLY-FICTITIOUS-CETES'))
        self.assertTrue(plan['can_confirm'])
        result=self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=doc['revision'],plan_hash=plan['plan_hash'],password='ONLY-FICTITIOUS-CETES'))
        self.assertEqual(result['status'],'imported')


if __name__=='__main__':unittest.main()
