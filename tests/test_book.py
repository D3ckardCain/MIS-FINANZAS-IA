"""Importación financiera: atomicidad, cobertura y traspasos con PDF ficticios."""
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from finanzas.book import FinancialBook
from finanzas.intake import Inbox
from finanzas.ledger import Kind, Origin
from tests import test_intake
from tests.test_openbank import pages, synthetic_pdf, page, table_row


def content(month=1, *, initial='100.00', account='0001234567', extra=''):
    start=f'01/{month:02d}/26';end=f'{31 if month==1 else 28}/{month:02d}/26'
    texts=pages()
    # Reconstruir el ahorro para mantener el mismo flujo con cualquier apertura.
    balance=Decimal(initial)
    texts[1]=page('Apartado Open',[
        table_row('02/01/26','Abono de intereses','$ 1.00','',f'$ {balance+1:.2f}'),
        table_row('05/01/26','Abono desde Cuenta Débito Open Light','$ 200.00','',f'$ {balance+201:.2f}')],
        initial=initial,deposits='200.00',final=f'{balance+203:.2f}',interest='3.00')
    texts[2]=page('Apartado Open',[
        table_row('06/01/26','Abono de intereses','$ 2.00','',f'$ {balance+203:.2f}')])
    texts=[p.replace('01/01/26 - 31/01/26',start+' - '+end).replace('02/01/26',f'02/{month:02d}/26')
             .replace('05/01/26',f'05/{month:02d}/26').replace('06/01/26',f'06/{month:02d}/26') for p in texts]
    texts[0]='Emitido por Openbank Mexico\nNúmero de cuenta '+account+'\n'+texts[0]
    texts[-1]+='\n'+extra
    return synthetic_pdf(texts)


class BookTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'bandeja.sqlite3'
        with Inbox(self.path) as inbox:self.doc=inbox.upload(content(),'ficticio.pdf')
        self.book=FinancialBook(self.path);self.addCleanup(self.book.close)

    def confirm(self,doc=None):
        doc=doc or self.doc;plan=self.book.preview(doc['id'])
        return self.book.confirm(doc['id'],revision=plan['revision'],plan_hash=plan['plan_hash'])

    def upload(self,data):
        with Inbox(self.path) as inbox:return inbox.upload(data,'otro-ficticio.pdf')

    def test_plan_never_writes_ledger_and_confirmation_preserves_exact_cash(self):
        plan=self.book.preview(self.doc['id'])
        self.assertTrue(plan['can_confirm'],plan['issues'])
        self.assertEqual(self.book.store.load_ledger().movements,())
        result=self.confirm();self.assertEqual(result['status'],'imported')
        ledger=self.book.store.load_ledger()
        self.assertEqual(ledger.interest_received('MXN'),Decimal('3'))
        self.assertEqual(ledger.withholding_recorded('MXN'),Decimal('0'))
        self.assertEqual(len(ledger.movements),7)
        self.assertFalse(any(m.kind==Kind.OPENING for m in ledger.movements))
        closing={a['lane']:a['closing'] for a in self.book.summary()['accounts']}
        self.assertEqual(closing,dict(debit='10.00',investments='303.00'))

    def test_internal_transfer_reduction_and_contribution_do_not_inflate_external_capital(self):
        self.confirm();ledger=self.book.store.load_ledger()
        transfers=[m for m in ledger.movements if m.origin==Origin.OWN_TRANSFER]
        self.assertEqual(len(transfers),2)
        self.assertEqual(sum(m.signed_amount for m in transfers),0)
        self.assertEqual(ledger.pending_transfers(),())
        self.assertEqual(ledger.external_contributions('MXN'),0)
        self.assertEqual(len(ledger.pending_origins()),1)

    def test_two_equal_legitimate_internal_transfers_are_not_paired_arbitrarily(self):
        texts=[page('Cuenta Débito Open Light',[
            table_row('05/01/26','Transferencia SPEI recibida','$ 400.00','','$ 410.00'),
            table_row('05/01/26','Retiro a Apartado Open','','$ 200.00','$ 210.00'),
            table_row('05/01/26','Retiro a Apartado Open','','$ 200.00','$ 10.00')],
            initial='10.00',deposits='400.00',other='400.00',final='10.00'),
            page('Apartado Open',[
            table_row('05/01/26','Abono desde Cuenta Débito Open Light','$ 200.00','','$ 300.00'),
            table_row('05/01/26','Abono desde Cuenta Débito Open Light','$ 200.00','','$ 500.00')],
            initial='100.00',deposits='400.00',final='500.00')]
        texts[0]='Emitido por Openbank Mexico\nNúmero de cuenta 0001234567\n'+texts[0]
        doc=self.upload(synthetic_pdf(texts));plan=self.book.preview(doc['id'])
        self.assertFalse(plan['can_confirm'])
        self.assertTrue(any('pareja única' in s for s in plan['issues']))
        self.assertEqual(self.book.store.load_ledger().movements,())

    def test_confirmation_retry_and_reopening_are_idempotent(self):
        plan=self.book.preview(self.doc['id']);self.confirm()
        again=self.book.confirm(self.doc['id'],revision=plan['revision'],plan_hash=plan['plan_hash'])
        self.assertTrue(again['duplicate']);self.assertEqual(len(self.book.store.load_ledger().movements),7)
        with FinancialBook(self.path) as other:self.assertEqual(other.preview(self.doc['id'])['status'],'imported')

    def test_overlap_in_different_pdf_is_blocked_instead_of_deduping_by_amount(self):
        self.confirm();other=self.upload(content(extra='Documento distinto, mismo periodo'))
        plan=self.book.preview(other['id']);self.assertFalse(plan['can_confirm'])
        self.assertTrue(any('superpuesto' in s for s in plan['issues']))
        with self.assertRaises(ValueError):self.book.confirm(other['id'],revision=plan['revision'],plan_hash=plan['plan_hash'])
        self.assertEqual(self.book.summary()['documents'],1)

    def test_months_may_arrive_out_of_order_without_duplicate_initial_contribution(self):
        feb=self.upload(content(2,initial='303.00'));self.confirm(feb);self.confirm()
        summary=self.book.summary();savings=next(a for a in summary['accounts'] if a['lane']=='investments')
        self.assertEqual(savings['closing'],'506.00');self.assertEqual(savings['interest'],'6.00')
        self.assertEqual(savings['gaps'],[])
        self.assertEqual(sum(m.kind==Kind.CONTRIBUTION for m in self.book.store.load_ledger().movements),4)

    def test_bad_boundary_blocks_import_without_adjusting_balances(self):
        self.confirm();feb=self.upload(content(2,initial='304.00'))
        plan=self.book.preview(feb['id']);self.assertFalse(plan['can_confirm'])
        self.assertTrue(any('cierre anterior' in s for s in plan['issues']))
        self.assertEqual(self.book.summary()['documents'],1)

    def test_gaps_remain_visible_without_fabricated_movements(self):
        self.confirm();march=content(2,initial='500.00')
        # Cambiar el mes sobre PDF textual mediante un nuevo archivo sintético.
        from pypdf import PdfReader
        from io import BytesIO
        texts=[p.extract_text(extraction_mode='layout').replace('/02/26','/03/26') for p in PdfReader(BytesIO(march)).pages]
        doc=self.upload(synthetic_pdf(texts));self.confirm(doc)
        self.assertTrue(all(a['gaps'] for a in self.book.summary()['accounts']))

    def test_stale_source_revision_or_plan_never_writes(self):
        plan=self.book.preview(self.doc['id'])
        with self.assertRaises(ValueError):self.book.confirm(self.doc['id'],revision=1,plan_hash='not-the-plan')
        with Inbox(self.path) as inbox:inbox.review(self.doc['id'],expected_revision=1,decision='reviewed')
        with self.assertRaises(ValueError):self.book.confirm(self.doc['id'],revision=1,plan_hash=plan['plan_hash'])
        self.assertEqual(self.book.summary()['documents'],0)

    def test_other_import_invalidates_previously_prepared_plan(self):
        plan=self.book.preview(self.doc['id'])
        other=self.upload(content(account='0007654321'));self.confirm(other)
        with self.assertRaises(ValueError):self.book.confirm(self.doc['id'],revision=1,plan_hash=plan['plan_hash'])
        self.confirm();self.assertEqual(self.book.summary()['documents'],2)

    def test_failure_after_ledger_writes_rolls_back_document_approval_and_movements(self):
        original=self.book.store.record_many
        def fail(movements):
            original(movements)
            raise ValueError('Fallo simulado antes de confirmar lote')
        with patch.object(self.book.store,'record_many',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm()
        self.assertEqual(self.book.store.load_ledger().movements,())
        self.assertEqual(self.book.store.review_history(self.doc['id']),())
        self.assertEqual(self.book.db.execute('SELECT COUNT(*) FROM documents').fetchone()[0],0)
        self.assertEqual(self.book.summary()['documents'],0)
        self.confirm()

    def test_missing_account_and_nonzero_withholding_do_not_enter_ledger(self):
        for data in (synthetic_pdf(['Emitido por Openbank Mexico\n'+p for p in pages()]),
                     content().replace(b'Impuestos retenidos $ 0.00',b'Impuestos retenidos $ 1.00')):
            doc=self.upload(data);plan=self.book.preview(doc['id'])
            self.assertFalse(plan['can_confirm'])


class FinancialHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request
    def test_plan_confirmation_and_book_http(self):
        doc=self.request('/api/upload',content(),raw=True)
        plan=self.request('/api/documents/'+doc['id']+'/plan')
        self.assertTrue(plan['can_confirm'])
        confirmed=self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=plan['revision'],plan_hash=plan['plan_hash']))
        self.assertEqual(confirmed['status'],'imported')
        book=self.request('/api/book');self.assertEqual(book['documents'],1)
        self.assertEqual(len(book['accounts']),2)


if __name__=='__main__':unittest.main()
