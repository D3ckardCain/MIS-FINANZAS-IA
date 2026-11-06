"""Fondos ficticios: efectivo, valuación e ISR informativo sin doble cargo."""
from pathlib import Path
from io import BytesIO
from decimal import Decimal as D
import tempfile
import unittest
from unittest.mock import patch
from finanzas.book import FinancialBook
from finanzas.intake import Inbox
from finanzas.ledger import Kind, Origin
from tests import test_intake
from tests.test_funds_equities import fund_pages
from tests.test_openbank import synthetic_pdf


def content(pages=None,*,next_period=False,extra=''):
    pages=list(pages or fund_pages())
    if next_period:
        pages=[p.replace('1/Ene/2026 al 31/Ene/2026','1/Feb/2026 al 28/Feb/2026')
            .replace('03/ene/2026','03/feb/2026').replace('Enero 2026 (período actual)','Febrero 2026 (período actual)') for p in pages]
        pages[0]=pages[0].replace('11  $9.909091  $10.090909  $111.00  $11.00','12  $9.909091  $10.166667  $122.00  $13.00')
        pages[0]=pages[0].replace('Posición de Valores: $111.00','Posición de Valores: $122.00',1)
        pages[0]=pages[0].replace('Efectivo: $1.00','Efectivo: $2.00',1).replace('Posición total: $112.00','Posición total: $124.00',1)
        pages[0]=pages[0].replace('10  $10.000000  $100.00','11  $10.090909  $111.00')
        pages[0]=pages[0].replace('Posición de Valores: $100.00','Posición de Valores: $111.00').replace('Efectivo: $0.00','Efectivo: $1.00')
        pages[0]=pages[0].replace('Posición total: $100.00','Posición total: $112.00')
    pages[-1]+='\n'+extra
    return synthetic_pdf(pages)


def protected_content():
    from pypdf import PdfReader, PdfWriter
    writer=PdfWriter();writer.append(PdfReader(BytesIO(content())))
    writer.encrypt('ONLY-FICTITIOUS-FINTUAL');buffer=BytesIO();writer.write(buffer)
    return buffer.getvalue()


class FintualBookTests(unittest.TestCase):
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

    def test_cash_closing_not_fund_or_total_portfolio(self):
        plan=self.confirm();summary=self.book.summary()
        self.assertEqual(len(summary['accounts']),1);self.assertEqual(summary['accounts'][0]['role'],'fund_cash')
        self.assertEqual(summary['accounts'][0]['closing'],'1.00')
        self.assertEqual(plan['fund_summary_observation']['final'],'112.00')
        self.assertEqual(len(plan['fund_initial_positions']),1);self.assertEqual(len(plan['fund_final_positions']),1)
        self.assertEqual(len(self.book.store.load_ledger().movements),2)

    def test_purchase_reduces_cash_without_external_capital_or_interest(self):
        self.confirm();ledger=self.book.store.load_ledger()
        self.assertEqual([m.amount for m in ledger.movements if m.kind==Kind.WITHDRAWAL],[D('9')])
        self.assertEqual([m.amount for m in ledger.movements if m.kind==Kind.CONTRIBUTION],[D('10')])
        self.assertTrue(all(m.origin==Origin.UNKNOWN for m in ledger.movements))
        self.assertEqual(ledger.external_contributions('MXN'),0);self.assertEqual(ledger.interest_received('MXN'),0)

    def test_informative_tax_does_not_create_cash_charge_or_zero(self):
        plan=self.confirm();ledger=self.book.store.load_ledger();account=self.book.summary()['accounts'][0]
        self.assertEqual(plan['withholding_reported_observation'],'0.07')
        self.assertIsNone(ledger.withholding_recorded('MXN'))
        self.assertIsNone(account['withholding']);self.assertIsNone(account['interest_net_of_withholding'])
        self.assertFalse(account['withholding_complete'])
        pages=fund_pages();pages[2]=pages[2].replace('Total de ISR retenido: $0.07','Total de ISR retenido: $0.00')
        plan=self.book.preview(self.upload(content(pages))['id'])
        self.assertEqual(plan['withholding_reported_observation'],'0.00');self.assertEqual(plan['withholding_status'],'unknown')

    def test_valuation_variation_and_return_percent_are_not_paid_income(self):
        plan=self.confirm();self.assertEqual(plan['fund_final_positions'][0]['variation_reported'],'11.00')
        self.assertEqual(plan['fund_summary_observation']['net_return_reported'],'2.00')
        self.assertEqual(self.book.store.load_ledger().interest_received('MXN'),0)
        self.assertEqual(plan['transfers'],[])

    def test_sale_is_receipt_with_unknown_basis_not_realized_gain(self):
        pages=fund_pages();pages[1]=pages[1].replace('  Compra  ','  Venta  ')
        pages[0]=pages[0].replace('Efectivo: $1.00','Efectivo: $19.00').replace('Posición total: $112.00','Posición total: $130.00')
        self.confirm(self.upload(content(pages)));ledger=self.book.store.load_ledger()
        self.assertTrue(all(m.kind==Kind.CONTRIBUTION for m in ledger.movements))
        self.assertEqual(ledger.interest_received('MXN'),0);self.assertEqual(ledger.external_contributions('MXN'),0)

    def test_commission_and_vat_from_columns_once(self):
        pages=fund_pages();pages[1]=pages[1].replace('Precio: $9.00  $9.00  $0.00  $0.00','Precio: $9.00  $9.00  $0.50  $0.08')
        pages[0]=pages[0].replace('Efectivo: $1.00','Efectivo: $0.42').replace('Posición total: $112.00','Posición total: $111.42')
        pages[2]=pages[2].replace('Total de Comisiones: $0.00','Total de Comisiones: $0.50')
        result=self.confirm(self.upload(content(pages)));ledger=self.book.store.load_ledger()
        self.assertEqual(sorted(m.amount for m in ledger.movements if m.kind==Kind.FEE),[D('.08'),D('.50')])
        self.assertEqual(self.book.summary()['accounts'][0]['charges_fees_and_vat'],'0.58')
        self.assertEqual(len(result['movements']),4)

    def test_empty_cash_table_requires_explicit_declaration(self):
        pages=fund_pages();pages[0]=pages[0].replace('Efectivo: $0.00','Efectivo: $1.00').replace('Posición total: $100.00','Posición total: $101.00')
        pages[1]=pages[1].split('MOVIMIENTOS DEL PERÍODO')[0].replace('$0,00  $10.00','$0,00  $0.00')+'MOVIMIENTOS DEL PERÍODO\nNo hay movimientos en el periodo\n'
        plan=self.confirm(self.upload(content(pages)));self.assertEqual(plan['movements'],[])
        self.assertEqual(self.book.summary()['accounts'][0]['closing'],'1.00')

    def test_nan_difference_unknown_concept_and_currency_fail_closed(self):
        for index,old,new in [(2,'2.00%','NaN%'),(0,'Posición total: $112.00','Posición total: $112.01'),
                              (1,'  Compra  ','  Ajuste  '),(0,'pesos mexicanos','dólares')]:
            pages=fund_pages();pages[index]=pages[index].replace(old,new)
            self.assertFalse(self.book.preview(self.upload(content(pages))['id'])['can_confirm'])
        pages=fund_pages();pages[0]+='\nMoneda: USD\n'
        self.assertFalse(self.book.preview(self.upload(content(pages))['id'],currency_confirmation='MXN')['can_confirm'])

    def test_binary_retry_reopen_overlap_and_out_of_order_periods(self):
        self.confirm(self.upload(content(next_period=True)));self.confirm()
        self.assertTrue(self.book.confirm(self.doc['id'],revision=1,plan_hash='retry')['duplicate'])
        with FinancialBook(self.path) as other:self.assertEqual(other.summary()['documents'],2)
        plan=self.book.preview(self.upload(content(extra='Otra representacion'))['id'])
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('superpuesto' in s for s in plan['issues']))

    def test_same_amount_purchase_rows_are_not_deduplicated(self):
        pages=fund_pages();line='03/ene/2026  Compra  Precio: $9.00  $9.00  $0.00  $0.00'
        small='03/ene/2026  Compra  Precio: $4.50  $4.50  $0.00  $0.00'
        pages[1]=pages[1].replace(line,small+'\n'+small)
        result=self.confirm(self.upload(content(pages)))
        purchases=[m for m in result['movements'] if m.get('category')=='purchase']
        self.assertEqual(len(purchases),2);self.assertNotEqual(purchases[0]['id'],purchases[1]['id'])

    def test_stale_version_and_failure_roll_back_all_financial_writes(self):
        plan=self.book.preview(self.doc['id'])
        with Inbox(self.path) as inbox:inbox.review(self.doc['id'],expected_revision=1,decision='reviewed')
        with self.assertRaises(ValueError):self.book.confirm(self.doc['id'],revision=1,plan_hash=plan['plan_hash'])
        original=self.book.store.record_many
        def fail(rows):original(rows);raise ValueError('Fallo simulado')
        with patch.object(self.book.store,'record_many',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm()
        self.assertEqual(self.book.summary()['documents'],0);self.assertEqual(self.book.store.load_ledger().movements,())
        self.assertEqual(self.book.store.review_history(self.doc['id']),());self.confirm()

    def test_protected_original_reopened_without_saved_password(self):
        with Inbox(self.path) as inbox:doc=inbox.upload(protected_content(),'protected.pdf',password='ONLY-FICTITIOUS-FINTUAL')
        self.assertTrue(self.book.preview(doc['id'])['password_required'])
        self.assertTrue(self.book.preview(doc['id'],password='WRONG-FICTITIOUS')['password_required'])
        result=self.confirm(doc,password='ONLY-FICTITIOUS-FINTUAL')
        self.assertNotIn('ONLY-FICTITIOUS-FINTUAL',str(result))
        self.assertNotIn('ONLY-FICTITIOUS-FINTUAL',str(list(self.book.db.iterdump())))

    def test_eleven_institutions_without_fund_value_counted_as_cash(self):
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
        self.confirm()
        for fixture in (openbank,mifel,bancoppel,didi,fondeadora,plata,supertasas,hey,kapital,doopla):self.confirm(self.upload(fixture()))
        self.assertEqual(self.book.summary()['documents'],11);self.assertEqual(len(self.book.summary()['accounts']),13)


class FintualFinancialHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_upload_plan_confirm_and_cash_role_http(self):
        doc=self.request('/api/upload',content(),raw=True)
        plan=self.request('/api/documents/'+doc['id']+'/plan');self.assertTrue(plan['can_confirm'])
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=1,plan_hash=plan['plan_hash']))
        account=self.request('/api/book')['accounts'][0]
        self.assertEqual(account['role'],'fund_cash');self.assertEqual(account['closing'],'1.00')
        self.assertIsNone(account['withholding'])

    def test_encrypted_reader_and_confirmation_http(self):
        doc=self.request('/api/upload',protected_content(),raw=True)
        doc=self.request('/api/documents/'+doc['id']+'/reprocess',dict(revision=1,password='ONLY-FICTITIOUS-FINTUAL'))
        plan=self.request('/api/documents/'+doc['id']+'/plan');self.assertTrue(plan['password_required'])
        plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=doc['revision'],password='ONLY-FICTITIOUS-FINTUAL'))
        self.assertTrue(plan['can_confirm'])
        result=self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=doc['revision'],plan_hash=plan['plan_hash'],password='ONLY-FICTITIOUS-FINTUAL'))
        self.assertEqual(result['status'],'imported')


if __name__=='__main__':unittest.main()
