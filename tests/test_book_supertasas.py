"""SuperTasas ficticio: efectivo, proyecciones y moneda explícita."""
from pathlib import Path
from decimal import Decimal as D
import tempfile
import unittest
from unittest.mock import patch

from finanzas.book import FinancialBook
from finanzas.intake import Inbox
from finanzas.ledger import Kind, Origin
from tests import test_intake
from tests.test_supertasas import source, row
from tests.test_openbank import synthetic_pdf


def protected_content():
    from pypdf import PdfReader, PdfWriter
    from io import BytesIO
    writer=PdfWriter();writer.append(PdfReader(BytesIO(content())))
    writer.encrypt('ONLY-FICTITIOUS');buffer=BytesIO();writer.write(buffer)
    return buffer.getvalue()


def content(text=None,*,currency='MXN',next_period=False,extra=''):
    text=source() if text is None else text
    if next_period:
        text=text.replace('01 al 31 de Enero','01 al 28 de Febrero')
        text=text.replace(row('2026-01-05','ABONO STP','1001',deposit='20',balance='120')+'\n','')
        text=text.replace(row('2026-01-06','APERTURAINVERSION','1002',charge='50',balance='70')+'\n','')
        text=text.replace(row('2026-01-30','PAGORENDIMIENTO CTA.GRAVADO','1003',deposit='1',balance='71'),
            row('2026-02-27','PAGORENDIMIENTO CTA.GRAVADO','1003',deposit='1',balance='72'))
        text=text.replace('Saldo Inicial 100.00','Saldo Inicial 71.00').replace('Saldo Final 71.00','Saldo Final 72.00')
        text=text.replace('(+) Abonos 21.00','(+) Abonos 1.00').replace('(-) Cargos 50.00','(-) Cargos 0.00')
    if currency:text+='\nMoneda: '+currency+'\n'
    return synthetic_pdf([text+'\n'+extra])


class SuperTasasBookTests(unittest.TestCase):
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

    def test_one_cash_account_and_dated_term_snapshots_not_summed(self):
        plan=self.confirm();ledger=self.book.store.load_ledger()
        self.assertEqual(len(plan['periods']),1);self.assertEqual(plan['periods'][0]['lane'],'debit')
        self.assertEqual(len(plan['term_snapshots']),1);snapshot=plan['term_snapshots'][0]
        self.assertEqual(snapshot['as_of'],'2026-01-31');self.assertEqual(snapshot['projected_gross'],'5.00')
        self.assertEqual(snapshot['unit'],'MXN');self.assertEqual(snapshot['status'],'documentary_observation')
        self.assertEqual(len(ledger.movements),4);self.assertEqual(len(self.book.summary()['accounts']),1)
        self.assertEqual(self.book.summary()['accounts'][0]['closing'],'71.00')
        self.assertFalse(any(m.kind==Kind.OPENING for m in ledger.movements))

    def test_interest_once_and_zero_retention_not_projected_tax(self):
        plan=self.confirm();ledger=self.book.store.load_ledger()
        self.assertEqual(sum(m.amount for m in ledger.movements if m.kind==Kind.INTEREST),D('1'))
        self.assertEqual(ledger.withholding_recorded('MXN'),0)
        self.assertEqual(sum(m.kind==Kind.WITHHOLDING for m in ledger.movements),1)
        self.assertEqual(plan['reported_terms']['annual_rate_reported'],'7.00')
        self.assertEqual(plan['term_snapshots'][0]['annual_rate'],'10.00')

    def test_term_opening_reduces_cash_with_unknown_origin_without_reinvestment(self):
        plan=self.confirm();ledger=self.book.store.load_ledger()
        self.assertEqual(plan['transfers'],[]);self.assertEqual(ledger.external_contributions('MXN'),0)
        principal=[m for m in plan['movements'] if m.get('category')=='term_opening'][0]
        self.assertEqual(principal['kind'],Kind.WITHDRAWAL.value);self.assertEqual(principal['amount'],'50')
        self.assertTrue(all(m.origin==Origin.UNKNOWN for m in ledger.movements if m.kind in (Kind.CONTRIBUTION,Kind.WITHDRAWAL)))
        self.assertFalse(any(m.origin==Origin.REINVESTMENT for m in ledger.movements))

    def test_returned_principal_is_contribution_not_interest(self):
        self.confirm(self.upload(content(source().replace('ABONO STP','PAGOINVERSION.CAPITAL'))))
        ledger=self.book.store.load_ledger()
        self.assertEqual(sum(m.amount for m in ledger.movements if m.kind==Kind.INTEREST),D('1'))
        self.assertEqual(sum(m.amount for m in ledger.movements if m.kind==Kind.CONTRIBUTION),D('20'))
        self.assertEqual(ledger.external_contributions('MXN'),0)

    def test_paid_term_interest_without_gross_tax_detail_blocks_confirmation(self):
        doc=self.upload(content(source().replace('ABONO STP','PAGOCEDE. INTERESEXCENTO')))
        plan=self.book.preview(doc['id']);self.assertFalse(plan['can_confirm'])
        self.assertTrue(any('desglose' in s for s in plan['issues']))
        with self.assertRaises(ValueError):self.book.confirm(doc['id'],revision=1,plan_hash=plan['plan_hash'])
        self.assertEqual(self.book.summary()['movements'],0)

    def test_missing_opening_bad_contract_or_unknown_concept_blocks_whole_batch(self):
        for old,new in [('Saldo Inicial 100.00','Saldo Inicial       '),('5.00 .00 5.00','5.00 .00 4.99'),
                        ('2027-01-05','2026-01-05'),('APERTURAINVERSION','DESCONOCIDO')]:
            plan=self.book.preview(self.upload(content(source().replace(old,new)))['id'])
            self.assertFalse(plan['can_confirm']);self.assertTrue(plan['issues'])
        self.assertEqual(self.book.summary()['documents'],0)

    def test_nonzero_retention_or_fees_are_preserved_but_not_guessed(self):
        for old,new in [('Retención ISR .00','Retención ISR .10'),('Total de Comisiones Cobradas 0.00','Total de Comisiones Cobradas 1.00')]:
            self.assertFalse(self.book.preview(self.upload(content(source().replace(old,new)))['id'])['can_confirm'])

    def test_currency_missing_requires_document_bound_review(self):
        doc=self.upload(content(currency=None));plan=self.book.preview(doc['id'])
        self.assertTrue(plan['currency_confirmation_required']);self.assertFalse(plan['can_confirm'])
        reviewed=self.book.preview(doc['id'],expected_revision=1,currency_confirmation='MXN')
        self.assertTrue(reviewed['can_confirm']);self.assertEqual(reviewed['currency_source'],'user_review')
        with self.assertRaises(ValueError):self.book.confirm(doc['id'],revision=1,plan_hash=reviewed['plan_hash'])
        accepted=self.confirm(doc,currency_confirmation='MXN')
        self.assertEqual(accepted['currency_confirmation'],'MXN')
        self.assertEqual(self.book.preview(doc['id'])['currency_source'],'user_review')

    def test_explicit_foreign_conflicting_currency_cannot_be_overridden(self):
        for currency in ('USD','EUR','CAD','USD\nMoneda: MXN'):
            plan=self.book.preview(self.upload(content(currency=currency))['id'],currency_confirmation='MXN')
            self.assertFalse(plan['can_confirm']);self.assertFalse(plan['currency_confirmation_required'])

    def test_retry_reopen_out_of_order_months_and_repeated_snapshot(self):
        self.confirm(self.upload(content(next_period=True)));first=self.confirm()
        self.assertTrue(self.book.confirm(self.doc['id'],revision=1,plan_hash='retry')['duplicate'])
        with FinancialBook(self.path) as other:
            summary=other.summary();self.assertEqual(summary['documents'],2)
            self.assertEqual(len(summary['accounts']),1);self.assertEqual(summary['accounts'][0]['closing'],'72.00')
            self.assertEqual(summary['accounts'][0]['interest'],'2')
            self.assertEqual(other.preview(self.doc['id'])['term_snapshots'],first['term_snapshots'])

    def test_overlap_or_adjacent_balance_mismatch_blocked(self):
        self.confirm()
        overlap=self.book.preview(self.upload(content(extra='Otra representacion'))['id'])
        self.assertFalse(overlap['can_confirm']);self.assertTrue(any('superpuesto' in s for s in overlap['issues']))
        text=source().replace('01 al 31 de Enero','01 al 28 de Febrero').replace('2026-01-05','2026-02-05')
        text=text.replace('2026-01-06','2026-02-06').replace('2027-01-05','2027-02-05').replace('2026-01-30','2026-02-27')
        plan=self.book.preview(self.upload(content(text))['id'])
        self.assertFalse(plan['can_confirm']);self.assertTrue(any('cierre anterior' in s for s in plan['issues']),plan['issues'])

    def test_stale_review_and_failure_roll_back_financial_data(self):
        plan=self.book.preview(self.doc['id'])
        with Inbox(self.path) as inbox:inbox.review(self.doc['id'],expected_revision=1,decision='reviewed')
        with self.assertRaises(ValueError):self.book.confirm(self.doc['id'],revision=1,plan_hash=plan['plan_hash'])
        original=self.book.store.record_many
        def fail(rows):original(rows);raise ValueError('Fallo simulado')
        with patch.object(self.book.store,'record_many',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm()
        self.assertEqual(self.book.summary()['documents'],0)
        self.assertEqual(self.book.store.load_ledger().movements,())
        self.assertEqual(self.book.store.review_history(self.doc['id']),())
        self.confirm()

    def test_password_required_for_original_reread_but_never_saved(self):
        with Inbox(self.path) as inbox:
            doc=inbox.upload(protected_content(),'ejemplo-protegido.pdf',password='ONLY-FICTITIOUS')
        for secret in (None,'WRONG-FICTITIOUS'):
            plan=self.book.preview(doc['id'],password=secret)
            self.assertFalse(plan['can_confirm']);self.assertTrue(plan['password_required'])
            self.assertNotIn('WRONG-FICTITIOUS',str(plan))
        plan=self.book.preview(doc['id'],password='ONLY-FICTITIOUS')
        self.assertTrue(plan['can_confirm'])
        with self.assertRaises(ValueError):self.book.confirm(doc['id'],revision=1,plan_hash=plan['plan_hash'])
        result=self.confirm(doc,password='ONLY-FICTITIOUS')
        self.assertNotIn('ONLY-FICTITIOUS',str(result))
        self.assertEqual(self.book.preview(doc['id'])['status'],'imported')
        self.assertNotIn('ONLY-FICTITIOUS',str(list(self.book.db.iterdump())))
        with Inbox(self.path) as inbox:self.assertNotIn('ONLY-FICTITIOUS',str(list(inbox.db.iterdump())))

    def test_invalid_password_type_and_stale_currency_review_rejected(self):
        self.assertFalse(self.book.preview(self.doc['id'],password=['not-text'])['can_confirm'])
        doc=self.upload(content(currency=None));plan=self.book.preview(doc['id'],currency_confirmation='MXN')
        with Inbox(self.path) as inbox:inbox.review(doc['id'],expected_revision=1,decision='reviewed')
        with self.assertRaises(ValueError):self.book.preview(doc['id'],expected_revision=1,currency_confirmation='MXN')
        with self.assertRaises(ValueError):self.book.confirm(doc['id'],revision=1,plan_hash=plan['plan_hash'],currency_confirmation='MXN')

    def test_zero_interest_is_not_unknown_or_new_income(self):
        text=source().replace(row('2026-01-30','PAGORENDIMIENTO CTA.GRAVADO','1003',deposit='1',balance='71')+'\n','')
        text=text.replace('Saldo Final 71.00','Saldo Final 70.00').replace('(+) Abonos 21.00','(+) Abonos 20.00')
        text=text.replace('Intereses Brutos 1.00','Intereses Brutos 0.00').replace('Intereses Netos 1.00','Intereses Netos 0.00')
        text=text.replace('Rendimiento bruto en pesos mexicanos $ 1.00','Rendimiento bruto en pesos mexicanos $ 0.00')
        self.confirm(self.upload(content(text)))
        self.assertFalse(any(m.kind==Kind.INTEREST for m in self.book.store.load_ledger().movements))

    def test_reader_does_not_infer_account_currency_from_income_label(self):
        from finanzas.supertasas import SuperTasasReader
        plain=SuperTasasReader().read_pages([source()],'synthetic')
        self.assertIsNone(plain.summary.unit);self.assertEqual(plain.currency_markers,())
        explicit=SuperTasasReader().read_pages([source()+'\nMoneda Nacional'],'synthetic')
        self.assertEqual(explicit.summary.unit,'MXN');self.assertEqual(explicit.currency_markers,('MXN',))

    def test_seven_institutions_without_snapshot_account(self):
        from tests.test_book import content as openbank
        from tests.test_book_mifel import content as mifel
        from tests.test_book_bancoppel import content as bancoppel
        from tests.test_book_didi import content as didi
        from tests.test_book_fondeadora import content as fondeadora
        from tests.test_book_plata import content as plata
        self.confirm()
        for fixture in (openbank,mifel,bancoppel,didi,fondeadora,plata):self.confirm(self.upload(fixture()))
        self.assertEqual(self.book.summary()['documents'],7);self.assertEqual(len(self.book.summary()['accounts']),9)


class SuperTasasFinancialHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_upload_currency_review_and_confirm_with_snapshot_http(self):
        doc=self.request('/api/upload',content(currency=None),raw=True)
        plan=self.request('/api/documents/'+doc['id']+'/plan');self.assertTrue(plan['currency_confirmation_required'])
        plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=1,currency_confirmation='MXN'))
        self.assertTrue(plan['can_confirm']);self.assertEqual(len(plan['term_snapshots']),1)
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=1,plan_hash=plan['plan_hash'],currency_confirmation='MXN'))
        summary=self.request('/api/book');self.assertEqual(summary['documents'],1)
        self.assertEqual(len(summary['accounts']),1)

    def test_protected_original_is_reopened_with_transient_password_http(self):
        doc=self.request('/api/upload',protected_content(),raw=True)
        self.assertEqual(doc['result']['status'],'needs_password')
        doc=self.request('/api/documents/'+doc['id']+'/reprocess',dict(revision=1,password='ONLY-FICTITIOUS'))
        plan=self.request('/api/documents/'+doc['id']+'/plan');self.assertTrue(plan['password_required'])
        plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=doc['revision'],password='ONLY-FICTITIOUS'))
        self.assertTrue(plan['can_confirm'])
        result=self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=doc['revision'],plan_hash=plan['plan_hash'],password='ONLY-FICTITIOUS'))
        self.assertEqual(result['status'],'imported');self.assertNotIn('ONLY-FICTITIOUS',str(result))


if __name__=='__main__':unittest.main()
