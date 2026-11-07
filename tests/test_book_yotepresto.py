"""YoTePresto ficticio: apertura acreditada, pago único y componentes con evidencia."""
from pathlib import Path
from io import BytesIO
from decimal import Decimal as D
import tempfile
import unittest
from unittest.mock import patch
from finanzas.book import FinancialBook
from finanzas.intake import Inbox
from finanzas.ledger import Kind,Origin
from tests import test_intake
from tests.test_yotepresto import source,movement
from tests.test_openbank import synthetic_pdf


def content(pages=None,*,next_period=False,zero_tax=False,extra=''):
    pages=list(pages or source(retained=not zero_tax))
    if zero_tax:pages[0]=pages[0].replace('(-) Administración','(-) Retenciones $0.00\nRetenciones IVA $0.00\nRetenciones ISR $0.00\n(-) Administración')
    if next_period:
        pages=[p.replace('01 Enero 2026 Al 31 Enero 2026, 31 días','01 Febrero 2026 Al 28 Febrero 2026, 28 días').replace('/01/2026','/02/2026') for p in pages]
        pages[0]=pages[0].replace('Saldo inicial del periodo $100.00','Saldo inicial del periodo $121.84')
        pages[0]=pages[0].replace('Saldo final del periodo $121.84','Saldo final del periodo $143.68').replace('fecha $29.84','fecha $49.68')
        pages[0]=pages[0].replace('Al corriente 2 100.00% $92.00','Al corriente 3 100.00% $94.00')
        for old,new in [('$30.00','$49.84'),('$44.00','$63.84'),('$42.00','$61.84'),('$40.84','$60.68'),('$34.84','$54.68'),('$29.84','$49.68')]:pages[1]=pages[1].replace(old,new)
        pages[1]=pages[1].replace('LLL-2002','LLL-2003').replace('$90.00 $86.00 $18.62 $2.98 $14.00','$86.00 $82.00 $27.24 $4.36 $18.00')
        pages[1]=pages[1].replace('07/02/2026 2002','07/01/2026 2002')
        pages[1]=pages[1].replace('Inversiones realizadas atrasadas','07/02/2026 2003 Al Corriente 0/36 9.00% $6.00 $6.00 $6.00 $0.00 $0.00 $0.00\nInversiones realizadas atrasadas')
    pages[-1]+='\n'+extra
    return synthetic_pdf(pages)


def protected_content():
    from pypdf import PdfReader,PdfWriter
    w=PdfWriter();w.append(PdfReader(BytesIO(content())));w.encrypt('ONLY-FICTITIOUS-YTP')
    b=BytesIO();w.write(b);return b.getvalue()


class YoTePrestoBookTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'bandeja.sqlite3';self.doc=self.upload(content())
        self.book=FinancialBook(self.path);self.addCleanup(self.book.close)

    def upload(self,data):
        with Inbox(self.path) as inbox:return inbox.upload(data,'ejemplo-ficticio.pdf')

    def confirm(self,doc=None,*,opening='10.00',password=None):
        doc=doc or self.doc;plan=self.book.preview(doc['id'],cash_opening_confirmation=opening,password=password)
        self.assertTrue(plan['can_confirm'],plan['issues'])
        return self.book.confirm(doc['id'],revision=plan['revision'],plan_hash=plan['plan_hash'],
            cash_opening_confirmation=plan.get('cash_opening_confirmation'),password=password)

    def test_opening_candidate_is_not_global_opening_or_automatically_accepted(self):
        plan=self.book.preview(self.doc['id']);self.assertFalse(plan['can_confirm'])
        self.assertTrue(plan['cash_opening_confirmation_required']);self.assertEqual(plan['cash_opening_candidate'],'10.00')
        self.assertEqual(plan['platform_summary_observation']['initial'],'100.00')
        self.assertEqual(self.book.summary()['documents'],0)

    def test_reviewed_opening_bound_to_plan_and_original_revision(self):
        plan=self.book.preview(self.doc['id'],cash_opening_confirmation='10')
        self.assertTrue(plan['can_confirm']);self.assertEqual(plan['cash_opening_source'],'user_review')
        with self.assertRaises(ValueError):self.book.confirm(self.doc['id'],revision=1,plan_hash=plan['plan_hash'])
        self.confirm();self.assertEqual(self.book.preview(self.doc['id'])['cash_opening_confirmation'],'10.00')

    def test_wrong_opening_type_nonfinite_or_value_cannot_override(self):
        for value in (10,True,'NaN','Infinity','11.00','100.00'):
            self.assertFalse(self.book.preview(self.doc['id'],cash_opening_confirmation=value)['can_confirm'])

    def test_single_cash_account_and_split_payment_not_global_or_accumulated(self):
        result=self.confirm();ledger=self.book.store.load_ledger();summary=self.book.summary()
        self.assertEqual(len(summary['accounts']),1);self.assertEqual(summary['accounts'][0]['closing'],'29.84')
        self.assertEqual(result['platform_summary_observation']['final'],'121.84')
        self.assertEqual(ledger.interest_received('MXN'),D('8.62'))
        self.assertEqual(ledger.withholding_recorded('MXN'),D('1'))
        self.assertEqual(summary['accounts'][0]['vat_received'],'1.38');self.assertEqual(summary['accounts'][0]['vat_paid'],'1.00')
        self.assertEqual(summary['accounts'][0]['charges_fees_and_vat'],'1.16')
        self.assertEqual(len(ledger.movements),11);self.assertEqual(len(result['loan_snapshots']),2)
        self.assertFalse(any(m.kind==Kind.OPENING for m in ledger.movements))

    def test_principal_matches_published_loan_change_without_external_or_reinvestment(self):
        result=self.confirm();p=[m for m in result['movements'] if m.get('component')=='principal']
        self.assertEqual(len(p),1);self.assertEqual(p[0]['amount'],'4.00')
        self.assertEqual(self.book.store.load_ledger().external_contributions('MXN'),0)
        self.assertEqual(result['transfers'],[])
        self.assertFalse(any(m.origin==Origin.REINVESTMENT for m in self.book.store.load_ledger().movements))

    def test_principal_mismatch_ambiguous_payment_or_cancelled_operation_blocks(self):
        cases=[source(),source(),source()]
        cases[0][1]=cases[0][1].replace('$90.00 $86.00','$90.00 $85.00')
        line=movement('06/01/2026','Pago','1001','$14.00','$44.00')
        cases[1][1]=cases[1][1].replace(line,line+'\n'+line)
        cases[2][1]=cases[2][1].replace('Abono','Cancelación de préstamo')
        for pages in cases:self.assertFalse(self.book.preview(self.upload(content(pages))['id'],cash_opening_confirmation='10.00')['can_confirm'])

    def test_unknown_retention_is_blocked_and_documented_zero_can_confirm(self):
        doc=self.upload(content(source(False)))
        self.assertFalse(self.book.preview(doc['id'],cash_opening_confirmation='10.00')['can_confirm'])
        self.confirm(self.upload(content(zero_tax=True)))
        self.assertEqual(self.book.store.load_ledger().withholding_recorded('MXN'),0)

    def test_previous_confirmed_closing_accredits_next_opening_without_extra_review(self):
        self.confirm();doc=self.upload(content(next_period=True));plan=self.book.preview(doc['id'])
        self.assertTrue(plan['can_confirm'],plan['issues'])
        self.assertEqual(plan['cash_opening_source'],'previous_confirmed_closing')
        self.confirm(doc,opening=None);self.assertEqual(self.book.summary()['accounts'][0]['closing'],'49.68')

    def test_months_out_of_order_retries_overlap_and_cash_gap(self):
        self.confirm(self.upload(content(next_period=True)),opening='29.84');self.confirm()
        self.assertTrue(self.book.confirm(self.doc['id'],revision=1,plan_hash='retry')['duplicate'])
        with FinancialBook(self.path) as other:self.assertEqual(other.summary()['documents'],2)
        plan=self.book.preview(self.upload(content(extra='Otra representacion'))['id'],cash_opening_confirmation='10.00')
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('superpuesto' in i for i in plan['issues']))

    def test_currency_missing_review_or_conflicting_currency_not_overridden(self):
        pages=source();pages[1]=pages[1].replace('moneda nacional','moneda pendiente')
        doc=self.upload(content(pages));plan=self.book.preview(doc['id'],cash_opening_confirmation='10.00')
        self.assertTrue(plan['currency_confirmation_required'])
        self.assertTrue(self.book.preview(doc['id'],cash_opening_confirmation='10.00',currency_confirmation='MXN')['can_confirm'])
        pages=source();pages[1]+='\nMoneda: USD\n'
        plan=self.book.preview(self.upload(content(pages))['id'],cash_opening_confirmation='10.00',currency_confirmation='MXN')
        self.assertFalse(plan['can_confirm']);self.assertFalse(plan['currency_confirmation_required'])

    def test_stale_review_and_atomic_failure_rollback_opening_and_components(self):
        plan=self.book.preview(self.doc['id'],cash_opening_confirmation='10.00')
        with Inbox(self.path) as inbox:inbox.review(self.doc['id'],expected_revision=1,decision='reviewed')
        with self.assertRaises(ValueError):self.book.confirm(self.doc['id'],revision=1,plan_hash=plan['plan_hash'],cash_opening_confirmation='10.00')
        original=self.book.store.record_many
        def fail(rows):original(rows);raise ValueError('Fallo simulado')
        with patch.object(self.book.store,'record_many',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm()
        self.assertEqual(self.book.summary()['documents'],0);self.assertEqual(self.book.store.load_ledger().movements,())
        self.assertEqual(self.book.store.review_history(self.doc['id']),());self.confirm()

    def test_protected_original_reread_with_opening_review_no_saved_password(self):
        with Inbox(self.path) as inbox:doc=inbox.upload(protected_content(),'protected.pdf',password='ONLY-FICTITIOUS-YTP')
        self.assertTrue(self.book.preview(doc['id'])['password_required'])
        result=self.confirm(doc,password='ONLY-FICTITIOUS-YTP')
        self.assertNotIn('ONLY-FICTITIOUS-YTP',str(result))
        self.assertNotIn('ONLY-FICTITIOUS-YTP',str(list(self.book.db.iterdump())))


class YoTePrestoFinancialHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_explicit_opening_review_and_confirmation_http(self):
        from urllib.error import HTTPError
        doc=self.request('/api/upload',content(),raw=True)
        plan=self.request('/api/documents/'+doc['id']+'/plan');self.assertTrue(plan['cash_opening_confirmation_required'])
        plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=1,cash_opening_confirmation='10.00'))
        self.assertTrue(plan['can_confirm'])
        with self.assertRaises(HTTPError):self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=1,plan_hash=plan['plan_hash']))
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=1,plan_hash=plan['plan_hash'],cash_opening_confirmation='10.00'))
        self.assertEqual(self.request('/api/book')['accounts'][0]['closing'],'29.84')

    def test_encrypted_opening_review_and_confirmation_http(self):
        doc=self.request('/api/upload',protected_content(),raw=True)
        doc=self.request('/api/documents/'+doc['id']+'/reprocess',dict(revision=1,password='ONLY-FICTITIOUS-YTP'))
        plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=doc['revision'],password='ONLY-FICTITIOUS-YTP',cash_opening_confirmation='10.00'))
        self.assertTrue(plan['can_confirm'])
        result=self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=doc['revision'],plan_hash=plan['plan_hash'],cash_opening_confirmation='10.00',password='ONLY-FICTITIOUS-YTP'))
        self.assertEqual(result['status'],'imported')


if __name__=='__main__':unittest.main()
