"""Alpaca ficticio: efectivo USD, dividendos y retención extranjera sin ISR supuesto."""
from pathlib import Path
from decimal import Decimal as D
from io import BytesIO
import re
import tempfile
import unittest
from unittest.mock import patch
from finanzas.book import FinancialBook
from finanzas.intake import Inbox
from finanzas.ledger import Kind, Origin
from tests import test_intake
from tests.test_funds_equities import alpaca_pages
from tests.test_openbank import synthetic_pdf


def content(pages=None,*,next_period=False,extra=''):
    pages=list(pages or alpaca_pages())
    if next_period:
        pages=[p.replace('JANUARY - 2026','FEBRUARY - 2026').replace('01/05/2026','02/05/2026') for p in pages]
        pages[0]=pages[0].replace('Beginning Balance $100.00 $100.00','Beginning Balance $1.00 $100.00')
        pages[0]=pages[0].replace('Trade Transaction -$100.00 -$100.00','Trade Transaction $0.00 -$100.00')
        pages[0]=pages[0].replace('Ending Value $1.00 $1.00','Ending Value $2.00 $2.00')
        pages[0]=pages[0].replace('Total Market Value $112.00','Total Market Value $113.00')
        pages[0]=pages[0].replace('Dividend $2.00 $2.00','Dividend $2.00 $4.00')
        pages[1]=pages[1].replace('$1.00  $ --','$2.00  $ --')
        pages[4]='Transaction\nNo record found.\n'
    pages[-1]+='\n'+extra
    # Las modificaciones monetarias del ejemplo no desplazan la columna derecha.
    normalized=[]
    for line in pages[0].splitlines():
        match=re.search(r'\s{2,}(Short Term|Long Term|(?:Gain|Loss|Net)\s+\$.*)$',line)
        normalized.append(line[:match.start()].ljust(100)+match[1] if match else line)
    pages[0]='\n'.join(normalized)
    return synthetic_pdf(pages)


def protected_content():
    from pypdf import PdfReader, PdfWriter
    writer=PdfWriter();writer.append(PdfReader(BytesIO(content())))
    writer.encrypt('ONLY-FICTITIOUS-ALPACA');buffer=BytesIO();writer.write(buffer)
    return buffer.getvalue()


class AlpacaBookTests(unittest.TestCase):
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

    def test_single_usd_cash_account_not_stock_valuation(self):
        result=self.confirm();summary=self.book.summary();account=summary['accounts'][0]
        self.assertEqual(len(summary['accounts']),1);self.assertEqual(account['role'],'fund_cash')
        self.assertEqual(account['closing'],'1.00');self.assertEqual(account['unit'],'USD')
        self.assertEqual(len(result['stock_positions']),2);self.assertEqual(len(result['trade_observations']),1)
        self.assertEqual(len(self.book.store.load_ledger().movements),3)

    def test_dividend_and_foreign_tax_not_interest_or_mexican_isr(self):
        self.confirm();ledger=self.book.store.load_ledger();account=self.book.summary()['accounts'][0]
        self.assertEqual(account['dividends'],'2.00');self.assertEqual(account['foreign_withholding'],'1.00')
        self.assertEqual(account['income_net_foreign_withholding'],'1.00')
        self.assertEqual(ledger.interest_received('USD'),0);self.assertIsNone(ledger.withholding_recorded('USD'))
        self.assertIsNone(account['withholding']);self.assertIsNone(account['interest_net_of_withholding'])

    def test_purchase_is_cash_reduction_with_unknown_origin(self):
        self.confirm();ledger=self.book.store.load_ledger()
        trades=[m for m in ledger.movements if m.kind==Kind.WITHDRAWAL]
        self.assertEqual([m.amount for m in trades],[D('100')]);self.assertEqual(trades[0].origin,Origin.UNKNOWN)
        self.assertEqual(ledger.external_contributions('USD'),0)
        self.assertFalse(any(m.origin==Origin.REINVESTMENT for m in ledger.movements))

    def test_sell_cash_not_realized_gain(self):
        pages=alpaca_pages();pages[0]=pages[0].replace('Trade Transaction -$100.00 -$100.00','Trade Transaction $100.00 $100.00')
        pages[0]=pages[0].replace('Ending Value $1.00 $1.00','Ending Value $201.00 $201.00').replace('Total Market Value $112.00','Total Market Value $312.00')
        pages[1]=pages[1].replace('$1.00  $ --','$201.00  $ --')
        pages[4]=pages[4].replace('  buy  ','  sell  ').replace('XYZ  1.000000000','XYZ  -1.000000000').replace('-$100.00','$100.00')
        self.confirm(self.upload(content(pages)));ledger=self.book.store.load_ledger()
        self.assertEqual([m.amount for m in ledger.movements if m.kind==Kind.CONTRIBUTION],[D('100')])
        self.assertEqual(ledger.external_contributions('USD'),0)
        self.assertEqual(self.book.summary()['accounts'][0]['dividends'],'2.00')

    def test_trade_commission_and_fee_section_charge_once(self):
        pages=alpaca_pages();pages[0]=pages[0].replace('Cost and Fees $0.00 $0.00','Cost and Fees $0.50 $0.50')
        pages[0]=pages[0].replace('Subtraction $1.00 $1.00','Subtraction $1.25 $1.25')
        pages[0]=pages[0].replace('Ending Value $1.00 $1.00','Ending Value $0.25 $0.25').replace('Total Market Value $112.00','Total Market Value $111.25')
        pages[1]=pages[1].replace('$1.00  $ --','$0.25  $ --')
        pages[3]=pages[3].replace('No record found.','01/05/2026  Regulatory fee  -$0.25')
        pages[4]=pages[4].replace('-$100.00  $0.00','-$100.00  $0.50')
        self.confirm(self.upload(content(pages)))
        self.assertEqual(self.book.summary()['accounts'][0]['charges_fees_and_vat'],'0.75')
        self.assertEqual(sorted(m.amount for m in self.book.store.load_ledger().movements if m.kind==Kind.FEE),[D('.25'),D('.5')])

    def test_missing_trade_commission_or_unexplained_cost_blocks(self):
        for old,new in [('-$100.00  $0.00','-$100.00  $ --'),('Cost and Fees $0.00 $0.00','Cost and Fees $0.01 $0.01')]:
            pages=[p.replace(old,new) for p in alpaca_pages()]
            self.assertFalse(self.book.preview(self.upload(content(pages))['id'])['can_confirm'])

    def test_reported_zero_foreign_withholding_is_not_mexican_zero(self):
        pages=alpaca_pages();pages[0]=pages[0].replace('Subtraction $1.00 $1.00','Subtraction $0.00 $0.00')
        pages[0]=pages[0].replace('Ending Value $1.00 $1.00','Ending Value $2.00 $2.00').replace('Total Market Value $112.00','Total Market Value $113.00')
        pages[1]=pages[1].replace('$1.00  $ --','$2.00  $ --');pages[2]=pages[2].replace('-$1.00','-$0.00')
        self.confirm(self.upload(content(pages)));ledger=self.book.store.load_ledger()
        taxes=[m for m in ledger.movements if m.kind==Kind.FOREIGN_WITHHOLDING]
        self.assertEqual(len(taxes),1);self.assertEqual(taxes[0].amount,0)
        self.assertIsNone(ledger.withholding_recorded('USD'))

    def test_valuation_and_year_to_date_not_income_again(self):
        result=self.confirm();self.assertEqual(result['stock_positions'][1]['unrealized'],'11.00')
        self.assertEqual(result['stock_positions'][1]['cost_basis'],'100.00')
        self.confirm(self.upload(content(next_period=True)))
        self.assertEqual(self.book.summary()['accounts'][0]['dividends'],'4.00')
        self.assertEqual(self.book.summary()['accounts'][0]['foreign_withholding'],'2.00')

    def test_cash_holdings_mismatch_foreign_currency_and_unsupported_assets_block(self):
        pages=alpaca_pages();pages[1]=pages[1].replace('$1.00  $ --','$2.00  $ --')
        pages[0]=pages[0].replace('Total Market Value $112.00','Total Market Value $113.00')
        plan=self.book.preview(self.upload(content(pages))['id']);self.assertFalse(plan['can_confirm'])
        self.assertTrue(any('Holdings' in i for i in plan['issues']))
        for index,old,new in [(1,'*Cash  USD','*Cash  EUR'),(0,'Options $0.00','Options $1.00')]:
            pages=alpaca_pages();pages[index]=pages[index].replace(old,new)
            self.assertFalse(self.book.preview(self.upload(content(pages))['id'])['can_confirm'])

    def test_memo_requires_explicit_zero_amount_and_commission(self):
        for amount,ready in [('$0.00',True),('$1.00',False),('$ --',False)]:
            pages=alpaca_pages();pages[4]+=f'01/06/2026  Memopost  XYZ  Noncash annotation  0  $0.00  {amount}  $0.00\n'
            plan=self.book.preview(self.upload(content(pages))['id'])
            self.assertEqual(plan['can_confirm'],ready,plan['issues'])
            self.assertEqual(len(plan['memo_observations']),1)

    def test_unknown_operation_and_unexplained_addition_block(self):
        for index,old,new in [(4,'Trade Entry','Unknown'),(0,'Addition $2.00 $2.00','Addition $5.00 $5.00')]:
            pages=alpaca_pages();pages[index]=pages[index].replace(old,new)
            self.assertFalse(self.book.preview(self.upload(content(pages))['id'])['can_confirm'])

    def test_retry_reopen_overlap_and_out_of_order_months(self):
        self.confirm(self.upload(content(next_period=True)));self.confirm()
        self.assertTrue(self.book.confirm(self.doc['id'],revision=1,plan_hash='retry')['duplicate'])
        with FinancialBook(self.path) as other:self.assertEqual(other.summary()['documents'],2)
        plan=self.book.preview(self.upload(content(extra='Otra representacion'))['id'])
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('superpuesto' in i for i in plan['issues']))

    def test_stale_review_and_failure_roll_back_dividend_and_tax(self):
        plan=self.book.preview(self.doc['id'])
        with Inbox(self.path) as inbox:inbox.review(self.doc['id'],expected_revision=1,decision='reviewed')
        with self.assertRaises(ValueError):self.book.confirm(self.doc['id'],revision=1,plan_hash=plan['plan_hash'])
        original=self.book.store.record_many
        def fail(rows):original(rows);raise ValueError('Fallo simulado')
        with patch.object(self.book.store,'record_many',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm()
        self.assertEqual(self.book.summary()['documents'],0);self.assertEqual(self.book.store.load_ledger().movements,())
        self.assertEqual(self.book.store.review_history(self.doc['id']),());self.confirm()

    def test_protected_original_password_not_saved(self):
        with Inbox(self.path) as inbox:doc=inbox.upload(protected_content(),'protected.pdf',password='ONLY-FICTITIOUS-ALPACA')
        self.assertTrue(self.book.preview(doc['id'])['password_required'])
        self.assertTrue(self.book.preview(doc['id'],password='WRONG-FICTITIOUS')['password_required'])
        result=self.confirm(doc,password='ONLY-FICTITIOUS-ALPACA')
        self.assertNotIn('ONLY-FICTITIOUS-ALPACA',str(result))
        self.assertNotIn('ONLY-FICTITIOUS-ALPACA',str(list(self.book.db.iterdump())))

    def test_twelve_institutions_keep_usd_and_mxn_separate(self):
        from tests.test_book import content as openbank
        from tests.test_book_mifel import content as mifel
        from tests.test_book_bancoppel import content as bancoppel
        from tests.test_book_didi import content as didi
        from tests.test_book_fondeadora import content as fondeadora
        from tests.test_book_plata import content as plata
        from tests.test_book_supertasas import content as supertasas
        from tests.test_book_hey import content as hey
        from tests.test_book_kapital import content as kapital
        from tests.test_book_doopla import content as doopla
        from tests.test_book_fintual import content as fintual
        self.confirm()
        for fixture in (openbank,mifel,bancoppel,didi,fondeadora,plata,supertasas,hey,kapital,doopla,fintual):self.confirm(self.upload(fixture()))
        summary=self.book.summary();self.assertEqual(summary['documents'],12);self.assertEqual(len(summary['accounts']),14)
        self.assertEqual(sum(a['unit']=='USD' for a in summary['accounts']),1)


class AlpacaFinancialHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_upload_plan_and_usd_cash_confirmation_http(self):
        doc=self.request('/api/upload',content(),raw=True)
        plan=self.request('/api/documents/'+doc['id']+'/plan');self.assertTrue(plan['can_confirm'])
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=1,plan_hash=plan['plan_hash']))
        account=self.request('/api/book')['accounts'][0]
        self.assertEqual(account['unit'],'USD');self.assertEqual(account['dividends'],'2.00')
        self.assertEqual(account['foreign_withholding'],'1.00');self.assertIsNone(account['withholding'])

    def test_encrypted_reader_and_confirmation_http(self):
        doc=self.request('/api/upload',protected_content(),raw=True)
        doc=self.request('/api/documents/'+doc['id']+'/reprocess',dict(revision=1,password='ONLY-FICTITIOUS-ALPACA'))
        plan=self.request('/api/documents/'+doc['id']+'/plan');self.assertTrue(plan['password_required'])
        plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=doc['revision'],password='ONLY-FICTITIOUS-ALPACA'))
        self.assertTrue(plan['can_confirm'])
        result=self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=doc['revision'],plan_hash=plan['plan_hash'],password='ONLY-FICTITIOUS-ALPACA'))
        self.assertEqual(result['status'],'imported')


if __name__=='__main__':unittest.main()
