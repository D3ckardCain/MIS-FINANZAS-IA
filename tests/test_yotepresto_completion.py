"""Pagos múltiples, originales ambiguos y cancelaciones entre meses ficticios."""
from pathlib import Path
from decimal import Decimal as D
import json
import tempfile
import unittest
from unittest.mock import patch
from dataclasses import replace
from finanzas.book import FinancialBook
from finanzas.intake import Inbox
from finanzas.ledger import Kind,Origin
from tests import test_intake
from tests.test_yotepresto import source,movement
from tests.test_openbank import synthetic_pdf

PAY=dict(principal='4.00',ordinary_interest='8.00',late_interest='0.62',ordinary_vat='1.28',late_vat='0.10')
HALF=dict(principal='2.00',ordinary_interest='4.00',late_interest='0.31',ordinary_vat='0.64',late_vat='0.05')


def set_cash(pages,rows,opening='10.00'):
    before,after=pages[1].split('Inversiones realizadas\n',1)
    balance=D(opening);lines=[]
    for day,concept,ref,value in rows:
        amount=D(value);balance+=amount
        printed=('-' if amount<0 else '')+'$'+f'{abs(amount):.2f}'
        lines.append(movement(day,concept,ref,printed,('$' if balance>=0 else '-$')+f'{abs(balance):.2f}'))
    pages[1]='Mis movimientos\nFecha Concepto Usuario / Referencia Monto Saldo\n'+'\n'.join(lines)+'\nInversiones realizadas\n'+after
    return pages


def multiple_pages(different_loans=False):
    pages=source();ref='1002' if different_loans else '1001'
    rows=[('05/01/2026','Abono','FICTICIO','20'),('06/01/2026','Pago','1001','7'),
        ('06/01/2026','Retención','1001','-1'),('06/01/2026','Administración por éxito','1001','-.58'),
        ('07/01/2026','Pago',ref,'7'),('07/01/2026','Retención',ref,'-1'),('07/01/2026','Administración por éxito',ref,'-.58'),
        ('08/01/2026','Préstamo','LLL-2002','-6'),('09/01/2026','Retiro','FICTICIO','-5')]
    set_cash(pages,rows)
    if different_loans:
        pages[0]=pages[0].replace('Saldo inicial del periodo $100.00','Saldo inicial del periodo $110.00')
        pages[0]=pages[0].replace('Saldo final del periodo $121.84','Saldo final del periodo $131.84')
        pages[0]=pages[0].replace('Al corriente 2 100.00% $92.00','Al corriente 3 100.00% $102.00')
        pages[1]=pages[1].replace('$90.00 $86.00','$90.00 $88.00')
        pages[1]=pages[1].replace('Inversiones realizadas atrasadas',
            '01/06/2025 1002 Al Corriente 2/36 9.00% $10.00 $10.00 $8.00 $4.31 $0.69 $2.00\nInversiones realizadas atrasadas')
    return pages


def current_cancellation(kind):
    pages=source();rows=[('05/01/2026','Abono','FICTICIO','20'),('06/01/2026','Pago','1001','14'),
        ('06/01/2026','Retención','1001','-2'),('06/01/2026','Administración por éxito','1001','-1.16'),
        ('07/01/2026','Préstamo','LLL-2002','-6'),('08/01/2026','Retiro','FICTICIO','-5')]
    if kind=='loan':
        rows.append(('09/01/2026','Cancelación de préstamo','LLL-2002','6'))
        pages[0]=pages[0].replace('fecha $29.84','fecha $35.84').replace('100.00% $92.00','100.00% $86.00')
        pages[1]=pages[1].replace('$6.00 $6.00 $6.00','$6.00 $6.00 $0.00')
    elif kind=='commission':
        rows.append(('09/01/2026','Cancelación de comisión','1001','1.16'))
        pages[0]=pages[0].replace('fecha $29.84','fecha $31.00').replace('periodo $121.84','periodo $123.00')
        pages[0]=pages[0].replace('(-) Administración por Éxito $1.16','(-) Administración por Éxito $0.00')
        pages[0]=pages[0].replace('Comisión $1.00','Comisión $0.00').replace('IVA Comisión $0.16','IVA Comisión $0.00')
        pages[0]=pages[0].replace('Comisiones cobradas: $1.16','Comisiones cobradas: $0.00').replace('ganaste: $6.84','ganaste: $8.00')
    elif kind=='retention':
        rows.append(('09/01/2026','Cancelación de retención','1001','2'))
        pages[0]=pages[0].replace('fecha $29.84','fecha $31.84').replace('periodo $121.84','periodo $123.84')
        pages[0]=pages[0].replace('(-) Retenciones $2.00','(-) Retenciones $0.00').replace('Retenciones IVA $1.00','Retenciones IVA $0.00').replace('Retenciones ISR $1.00','Retenciones ISR $0.00')
        pages[0]=pages[0].replace('ganaste: $6.84','ganaste: $8.84')
    elif kind=='payment':
        rows.append(('09/01/2026','Cancelación de pago','1001','-14'))
        pages[0]=pages[0].replace('fecha $29.84','fecha $15.84').replace('periodo $121.84','periodo $111.84').replace('100.00% $92.00','100.00% $96.00')
        for old,new in [('(+) Intereses recibidos $10.00','(+) Intereses recibidos $0.00'),('Intereses $8.00','Intereses $0.00'),
            ('IVA de Intereses $1.28','IVA de Intereses $0.00'),('Intereses Moratorios $0.62','Intereses Moratorios $0.00'),('IVA de Intereses Moratorios $0.10','IVA de Intereses Moratorios $0.00')]:pages[0]=pages[0].replace(old,new)
        pages[0]=pages[0].replace('ganaste: $6.84','ganaste: -$3.16')
        pages[1]=pages[1].replace('$90.00 $86.00','$90.00 $90.00')
    return set_cash(pages,rows)


def historical_cancellation():
    pages=source()
    pages[0]=pages[0].replace('01 Enero 2026 Al 31 Enero 2026, 31 días','01 Febrero 2026 Al 28 Febrero 2026, 28 días')
    changes=[('Saldo inicial del periodo $100.00','Saldo inicial del periodo $121.84'),('Saldo final del periodo $121.84','Saldo final del periodo $115.00'),
        ('fecha $29.84','fecha $19.00'),('(+) Intereses recibidos $10.00','(+) Intereses recibidos -$10.00'),
        ('Intereses $8.00','Intereses -$8.00'),('IVA de Intereses $1.28','IVA de Intereses -$1.28'),
        ('Intereses Moratorios $0.62','Intereses Moratorios -$0.62'),('IVA de Intereses Moratorios $0.10','IVA de Intereses Moratorios -$0.10'),
        ('(-) Retenciones $2.00','(-) Retenciones -$2.00'),('Retenciones IVA $1.00','Retenciones IVA -$1.00'),('Retenciones ISR $1.00','Retenciones ISR -$1.00'),
        ('(-) Administración por Éxito $1.16','(-) Administración por Éxito -$1.16'),('Comisión $1.00','Comisión -$1.00'),('IVA Comisión $0.16','IVA Comisión -$0.16'),
        ('(+) Fondos Agregados $20.00','(+) Fondos Agregados $0.00'),('(-) Retiros $5.00','(-) Retiros $0.00'),('Recursos fondeados: $20.00','Recursos fondeados: $0.00'),
        ('Pagos recibidos: $14.00','Pagos recibidos: $0.00'),('Inversiones realizadas: $6.00','Inversiones realizadas: $0.00'),
        ('Comisiones cobradas: $1.16','Comisiones cobradas: -$1.16'),('Recursos retirados: $5.00','Recursos retirados: $0.00'),
        ('ganaste: $6.84','ganaste: -$6.84'),('100.00% $92.00','100.00% $96.00')]
    for old,new in changes:pages[0]=pages[0].replace(old,new)
    pages[1]=pages[1].replace('$90.00 $86.00 $18.62 $2.98 $14.00','$86.00 $90.00 $10.00 $1.60 $10.00')
    rows=[('06/02/2026','Cancelación de pago','1001','-14'),('06/02/2026','Cancelación de retención','1001','2'),
        ('06/02/2026','Cancelación de comisión','1001','1.16')]
    return set_cash(pages,rows,opening='29.84')


def content(pages):return synthetic_pdf(pages)


class YoTePrestoCompletionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'bandeja.sqlite3';self.book=FinancialBook(self.path);self.addCleanup(self.book.close)

    def upload(self,pages):
        with Inbox(self.path) as inbox:return inbox.upload(content(pages),'ficticio.pdf')

    def preview(self,doc,review=None,opening='10.00'):
        return self.book.preview(doc['id'],cash_opening_confirmation=opening,operation_review=review)

    def review(self,plan,payment=HALF,tax=None):
        review=json.loads(json.dumps(plan.get('operation_review',{})))
        for key in ('payments','retentions','cancellations'):review.setdefault(key,{})
        for row in plan.get('review_rows',[]):
            if row['type']=='payments':review['payments'][row['id']]=dict(payment,loan_id=row['loan_id'])
            elif row['type']=='retentions':review['retentions'][row['id']]=tax or dict(retention_isr='0.50',retention_vat='0.50')
            elif row['type']=='cancellations' and row['candidates']:
                selected=row['candidates'][0]['id']
                review['cancellations'][row['id']]=dict(original_event_id=selected,loan_id='2002') if row.get('loans') else selected
        return review

    def confirm(self,doc,review=None,opening='10.00'):
        plan=self.preview(doc,review,opening);self.assertTrue(plan['can_confirm'],plan['issues'])
        return self.book.confirm(doc['id'],revision=plan['revision'],plan_hash=plan['plan_hash'],cash_opening_confirmation=plan['cash_opening_confirmation'],operation_review=plan['operation_review'])

    def test_multiple_payments_require_review_without_proportional_guess(self):
        doc=self.upload(multiple_pages());plan=self.preview(doc)
        self.assertFalse(plan['can_confirm']);self.assertEqual(len(plan['review_rows']),4)
        self.assertTrue(all(not row.get('values') for row in plan['review_rows']))
        result=self.confirm(doc,self.review(plan));ledger=self.book.store.load_ledger()
        self.assertEqual(ledger.interest_received('MXN'),D('8.62'));self.assertEqual(ledger.withholding_recorded('MXN'),D('1'))
        self.assertEqual(self.book.summary()['accounts'][0]['closing'],'29.84')
        self.assertEqual(len(result['operation_events']),9)

    def test_multiple_loans_principal_is_checked_per_loan(self):
        doc=self.upload(multiple_pages(True));plan=self.preview(doc)
        result=self.confirm(doc,self.review(plan))
        principal=[r for r in result['movements'] if r['component']=='principal']
        self.assertEqual({r['loan_id'] for r in principal},{'1001','1002'})
        self.assertEqual(sum(D(r['amount']) for r in principal),D('4'))

    def test_review_totals_and_monthly_components_must_both_match(self):
        doc=self.upload(multiple_pages());plan=self.preview(doc);review=self.review(plan)
        key=next(iter(review['payments']))
        review['payments'][key]['ordinary_interest']='5.00'
        self.assertFalse(self.preview(doc,review)['can_confirm'])
        review=self.review(plan);review['payments'][key]['ordinary_interest']='4.10';review['payments'][key]['ordinary_vat']='0.54'
        self.assertFalse(self.preview(doc,review)['can_confirm'])

    def test_invalid_foreign_rows_nonfinite_negative_and_numeric_values_rejected(self):
        doc=self.upload(multiple_pages());plan=self.preview(doc)
        for value in ('NaN','Infinity','-1',1,True):
            review=self.review(plan);review['payments'][next(iter(review['payments']))]['principal']=value
            self.assertFalse(self.preview(doc,review)['can_confirm'])
        self.assertFalse(self.preview(doc,{'payments':{'stale':PAY}})['can_confirm'])
        self.assertFalse(self.preview(doc,[])['can_confirm'])

    def test_review_cannot_move_principal_between_loans(self):
        doc=self.upload(multiple_pages(True));plan=self.preview(doc);review=self.review(plan)
        key=next(iter(review['payments']));review['payments'][key]['loan_id']='2002'
        self.assertFalse(self.preview(doc,review)['can_confirm'])

    def test_loan_cancellation_returns_cash_without_gain_or_external_capital(self):
        doc=self.upload(current_cancellation('loan'));plan=self.preview(doc)
        self.assertFalse(plan['can_confirm']);result=self.confirm(doc,self.review(plan))
        self.assertEqual(len(result['cancellation_links']),1)
        self.assertEqual(self.book.summary()['accounts'][0]['closing'],'35.84')
        self.assertEqual(self.book.store.load_ledger().external_contributions('MXN'),0)
        self.assertEqual(self.book.store.load_ledger().interest_received('MXN'),D('8.62'))

    def test_commission_cancellation_is_refund_not_income(self):
        doc=self.upload(current_cancellation('commission'));plan=self.preview(doc)
        result=self.confirm(doc,self.review(plan));ledger=self.book.store.load_ledger()
        self.assertEqual(self.book.summary()['accounts'][0]['charges_fees_and_vat'],'0.00')
        self.assertTrue(any(m.kind==Kind.FEE_REFUND for m in ledger.movements))
        self.assertEqual(ledger.interest_received('MXN'),D('8.62'))
        refund=next(m for m in result['movements'] if m['kind']==Kind.FEE_REFUND.value)
        self.assertIn('reversal_of',refund)

    def test_retention_cancellation_refunds_exact_original_isr_and_vat(self):
        doc=self.upload(current_cancellation('retention'));plan=self.preview(doc)
        review=self.review(plan,tax=dict(retention_isr='1.00',retention_vat='1.00'))
        self.confirm(doc,review);ledger=self.book.store.load_ledger()
        self.assertEqual(ledger.withholding_recorded('MXN'),0)
        account=self.book.summary()['accounts'][0];self.assertEqual(account['vat_paid'],'0.00')
        self.assertEqual(account['withholding'],'0.00')
        self.assertTrue(any(m.kind==Kind.WITHHOLDING_REFUND for m in ledger.movements))

    def test_payment_cancellation_reverses_original_components_not_monthly_zero(self):
        doc=self.upload(current_cancellation('payment'));plan=self.preview(doc)
        self.confirm(doc,self.review(plan,payment=PAY))
        ledger=self.book.store.load_ledger();account=self.book.summary()['accounts'][0]
        self.assertEqual(ledger.interest_received('MXN'),0);self.assertEqual(account['vat_received'],'0.00')
        self.assertEqual(account['closing'],'15.84');self.assertEqual(account['withholding'],'1.00')
        self.assertTrue(any(m.kind==Kind.INTEREST_REVERSAL for m in ledger.movements))

    def test_historical_cancellations_do_not_rewrite_originals_and_net_all_components(self):
        original=self.upload(source());first=self.confirm(original)
        before=self.book.store.load_ledger().movements
        doc=self.upload(historical_cancellation());plan=self.preview(doc,opening=None)
        self.assertEqual(len(plan['review_rows']),3)
        result=self.confirm(doc,self.review(plan),opening=None)
        self.assertEqual(len(result['cancellation_links']),3)
        self.assertEqual(self.book.preview(original['id'])['movements'],first['movements'])
        self.assertTrue(all(m in self.book.store.load_ledger().movements for m in before))
        account=self.book.summary()['accounts'][0]
        self.assertEqual(account['interest'],'0.00');self.assertEqual(account['withholding'],'0.00')
        self.assertEqual(account['vat_received'],'0.00');self.assertEqual(account['vat_paid'],'0.00')
        self.assertEqual(account['charges_fees_and_vat'],'0.00');self.assertEqual(account['closing'],'19.00')

    def test_legacy_frozen_plans_can_supply_original_without_new_event_metadata(self):
        original=self.upload(source());self.confirm(original)
        with self.book.db:
            raw=json.loads(self.book.db.execute('SELECT plan_json FROM book_batches').fetchone()[0])
            raw.pop('operation_events');raw.pop('cancellation_links')
            for m in raw['movements']:m.pop('source_event_id',None);m.pop('loan_id',None)
            self.book.db.execute('UPDATE book_batches SET plan_json=?',(json.dumps(raw),))
        doc=self.upload(historical_cancellation());plan=self.preview(doc,opening=None)
        self.confirm(doc,self.review(plan),opening=None)
        self.assertEqual(self.book.summary()['accounts'][0]['interest'],'0.00')

    def test_cancellation_without_original_stays_blocked_and_does_not_invent_income(self):
        doc=self.upload(historical_cancellation());plan=self.preview(doc,opening='29.84')
        self.assertFalse(plan['can_confirm']);self.assertTrue(all(not row['candidates'] for row in plan['review_rows']))
        self.assertEqual(self.book.summary()['documents'],0)

    def test_already_cancelled_original_cannot_be_reused(self):
        first=self.upload(source());self.confirm(first)
        doc=self.upload(historical_cancellation());plan=self.preview(doc,opening=None);review=self.review(plan)
        self.confirm(doc,review,opening=None)
        available,used=__import__('finanzas.yotepresto_operations',fromlist=['historical_events']).historical_events(self.book,self.book.summary()['accounts'][0]['account'])
        self.assertEqual(len(used),3);self.assertTrue(set(review['cancellations'].values())<=used)
        # Una representación binaria distinta del mismo mes no puede reusar originales ya consumidos.
        other=historical_cancellation();other[1]+='\nRepresentación distinta\n'
        other_doc=self.upload(other);blocked=self.preview(other_doc,review=None,opening='29.84')
        self.assertFalse(blocked['can_confirm']);self.assertTrue(all(not row['candidates'] for row in blocked['review_rows']))

    def test_review_and_original_choice_are_bound_to_confirmation_hash(self):
        doc=self.upload(multiple_pages());review=self.review(self.preview(doc));plan=self.preview(doc,review)
        self.assertTrue(plan['can_confirm'])
        with self.assertRaises(ValueError):self.book.confirm(doc['id'],revision=1,plan_hash=plan['plan_hash'],cash_opening_confirmation='10.00')
        self.assertEqual(self.book.summary()['documents'],0)

    def test_failure_after_components_rolls_back_links_and_can_retry(self):
        doc=self.upload(current_cancellation('commission'));review=self.review(self.preview(doc))
        original=self.book.store.record_many
        def fail(rows):original(rows);raise ValueError('Fallo simulado')
        with patch.object(self.book.store,'record_many',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm(doc,review)
        self.assertEqual(self.book.summary()['documents'],0);self.assertEqual(self.book.store.load_ledger().movements,())
        self.assertEqual(self.book.store.review_history(doc['id']),())
        self.confirm(doc,review)

    def test_reopen_and_binary_retry_do_not_duplicate_cancellations(self):
        doc=self.upload(current_cancellation('commission'));result=self.confirm(doc,self.review(self.preview(doc)))
        with FinancialBook(self.path) as other:
            before=other.summary()['movements'];again=other.confirm(doc['id'],revision=1,plan_hash='retry')
            self.assertTrue(again['duplicate']);self.assertEqual(other.summary()['movements'],before)
            self.assertEqual(other.preview(doc['id'])['cancellation_links'],result['cancellation_links'])

    def test_ambiguous_original_requires_choice_and_each_original_only_once(self):
        pages=multiple_pages()
        pages[0]=pages[0].replace('fecha $29.84','fecha $31.00').replace('periodo $121.84','periodo $123.00')
        pages[0]=pages[0].replace('(-) Administración por Éxito $1.16','(-) Administración por Éxito $0.00')
        pages[0]=pages[0].replace('Comisión $1.00','Comisión $0.00').replace('IVA Comisión $0.16','IVA Comisión $0.00')
        pages[0]=pages[0].replace('Comisiones cobradas: $1.16','Comisiones cobradas: $0.00').replace('ganaste: $6.84','ganaste: $8.00')
        rows=[('05/01/2026','Abono','FICTICIO','20'),('06/01/2026','Pago','1001','7'),
            ('06/01/2026','Retención','1001','-1'),('06/01/2026','Administración por éxito','1001','-.58'),
            ('07/01/2026','Pago','1001','7'),('07/01/2026','Retención','1001','-1'),('07/01/2026','Administración por éxito','1001','-.58'),
            ('08/01/2026','Préstamo','LLL-2002','-6'),('09/01/2026','Retiro','FICTICIO','-5'),
            ('10/01/2026','Cancelación de comisión','1001','.58'),('11/01/2026','Cancelación de comisión','1001','.58')]
        doc=self.upload(set_cash(pages,rows));plan=self.preview(doc)
        cancels=[r for r in plan['review_rows'] if r['type']=='cancellations']
        self.assertEqual([len(r['candidates']) for r in cancels],[2,2])
        review=self.review(plan);self.assertFalse(self.preview(doc,review)['can_confirm'])  # mismo original dos veces
        review['cancellations'][cancels[1]['id']]=cancels[1]['candidates'][1]['id']
        result=self.confirm(doc,review)
        self.assertEqual(len({r['original_event_id'] for r in result['cancellation_links']}),2)
        self.assertEqual(self.book.summary()['accounts'][0]['charges_fees_and_vat'],'0.00')

    def test_tax_allocation_must_match_monthly_isr_and_vat_not_only_row_total(self):
        doc=self.upload(multiple_pages());plan=self.preview(doc)
        review=self.review(plan,tax=dict(retention_isr='0.60',retention_vat='0.40'))
        blocked=self.preview(doc,review)
        self.assertFalse(blocked['can_confirm']);self.assertTrue(any('ISR' in i for i in blocked['issues']))

    def test_review_from_another_document_and_stale_revision_rejected(self):
        doc=self.upload(multiple_pages());review=self.review(self.preview(doc))
        other=multiple_pages();other[1]+='\nOtra representación\n';second=self.upload(other)
        self.assertFalse(self.preview(second,review)['can_confirm'])
        plan=self.preview(doc,review)
        with Inbox(self.path) as inbox:inbox.review(doc['id'],expected_revision=1,decision='reviewed')
        with self.assertRaises(ValueError):self.book.confirm(doc['id'],revision=1,plan_hash=plan['plan_hash'],
            cash_opening_confirmation='10.00',operation_review=review)

    def test_unexplained_cumulative_change_does_not_get_ignored_as_a_refund(self):
        self.confirm(self.upload(source()))
        pages=historical_cancellation();pages[1]=pages[1].replace('$10.00 $1.60 $10.00','$18.62 $2.98 $14.00')
        doc=self.upload(pages);plan=self.preview(doc,opening=None)
        blocked=self.preview(doc,self.review(plan),opening=None)
        self.assertFalse(blocked['can_confirm']);self.assertTrue(any('acumulado' in i for i in blocked['issues']))
        self.assertEqual(self.book.summary()['documents'],1)

    def test_history_checks_work_with_months_added_in_reverse_order(self):
        from tests.test_book_yotepresto import content as original_content
        with Inbox(self.path) as inbox:after=inbox.upload(original_content(next_period=True),'after.pdf')
        self.confirm(after,opening='29.84')
        bad=source();bad[1]=bad[1].replace('$18.62 $2.98 $14.00','$18.61 $2.98 $14.00')
        blocked=self.preview(self.upload(bad))
        self.assertFalse(blocked['can_confirm']);self.assertTrue(any('acumulado' in i for i in blocked['issues']))
        self.confirm(self.upload(source()))

    def test_corrected_original_requires_current_evidence_not_old_frozen_amount(self):
        self.confirm(self.upload(source()))
        fee=next(m for m in self.book.store.load_ledger().movements if m.kind==Kind.FEE)
        self.book.store.record_many([replace(fee,amount=D('1.15'))],corrections={fee.id:(1,'Corrección ficticia')})
        doc=self.upload(historical_cancellation());plan=self.preview(doc,opening=None)
        commission=next(r for r in plan['review_rows'] if 'comisión' in r['description'])
        self.assertEqual(commission['candidates'],[]);self.assertFalse(plan['can_confirm'])

    def test_explicit_empty_period_can_be_reviewed_without_inventing_movements(self):
        pages=source()
        changes=[('Saldo final del periodo $121.84','Saldo final del periodo $100.00'),('fecha $29.84','fecha $10.00'),
            ('(+) Intereses recibidos $10.00','(+) Intereses recibidos $0.00'),('Intereses $8.00','Intereses $0.00'),
            ('IVA de Intereses $1.28','IVA de Intereses $0.00'),('Intereses Moratorios $0.62','Intereses Moratorios $0.00'),('IVA de Intereses Moratorios $0.10','IVA de Intereses Moratorios $0.00'),
            ('(-) Retenciones $2.00','(-) Retenciones $0.00'),('Retenciones IVA $1.00','Retenciones IVA $0.00'),('Retenciones ISR $1.00','Retenciones ISR $0.00'),
            ('(-) Administración por Éxito $1.16','(-) Administración por Éxito $0.00'),('Comisión $1.00','Comisión $0.00'),('IVA Comisión $0.16','IVA Comisión $0.00'),
            ('(+) Fondos Agregados $20.00','(+) Fondos Agregados $0.00'),('(-) Retiros $5.00','(-) Retiros $0.00'),('Recursos fondeados: $20.00','Recursos fondeados: $0.00'),
            ('Pagos recibidos: $14.00','Pagos recibidos: $0.00'),('Inversiones realizadas: $6.00','Inversiones realizadas: $0.00'),('Comisiones cobradas: $1.16','Comisiones cobradas: $0.00'),
            ('Recursos retirados: $5.00','Recursos retirados: $0.00'),('ganaste: $6.84','ganaste: $0.00'),('Al corriente 2 100.00% $92.00','Al corriente 1 100.00% $90.00')]
        for old,new in changes:pages[0]=pages[0].replace(old,new)
        pages[1]=pages[1].replace('$90.00 $86.00','$90.00 $90.00')
        pages[1]='\n'.join(line for line in pages[1].splitlines() if '2002 Al Corriente' not in line)
        pages=set_cash(pages,[]);pages[1]=pages[1].replace('Inversiones realizadas\n','No hay movimientos en el periodo\nInversiones realizadas\n',1)
        doc=self.upload(pages);plan=self.preview(doc,opening=None);self.assertTrue(plan['cash_opening_confirmation_required'])
        result=self.confirm(doc);self.assertEqual(len(result['movements']),1)
        self.assertEqual(self.book.summary()['accounts'][0]['closing'],'10.00')
        absent=[pages[0],pages[1].replace('Mis movimientos','').replace('Fecha Concepto Usuario / Referencia Monto Saldo','').replace('No hay movimientos en el periodo','')]
        self.assertFalse(self.preview(self.upload(absent))['can_confirm'])

    def test_historical_loan_cancellation_requires_loan_identity_and_does_not_inflate_paid_principal(self):
        self.confirm(self.upload(source()))
        pages=historical_cancellation()
        for old,new in [('-$10.00','$0.00'),('-$8.00','$0.00'),('-$1.28','$0.00'),('-$0.62','$0.00'),('-$0.10','$0.00'),
            ('-$2.00','$0.00'),('-$1.00','$0.00'),('-$1.16','$0.00'),('-$0.16','$0.00'),
            ('periodo $115.00','periodo $121.84'),('fecha $19.00','fecha $35.84'),('ganaste: -$6.84','ganaste: $0.00'),
            ('100.00% $96.00','100.00% $86.00')]:pages[0]=pages[0].replace(old,new)
        pages[1]=pages[1].replace('$86.00 $90.00 $10.00 $1.60 $10.00','$86.00 $86.00 $18.62 $2.98 $14.00')
        pages[1]=pages[1].replace('$6.00 $6.00 $6.00','$6.00 $6.00 $0.00')
        pages=set_cash(pages,[('06/02/2026','Cancelación de préstamo','LLL-2002','6')],opening='29.84')
        doc=self.upload(pages);plan=self.preview(doc,opening=None)
        row=plan['review_rows'][0];original=row['candidates'][0]['id']
        unlinked=dict(cancellations={row['id']:original})
        self.assertFalse(self.preview(doc,unlinked,opening=None)['can_confirm'])
        reviewed=dict(cancellations={row['id']:dict(original_event_id=original,loan_id='2002')})
        result=self.confirm(doc,reviewed,opening=None)
        self.assertEqual(self.book.summary()['accounts'][0]['closing'],'35.84')
        self.assertEqual(result['operation_review']['cancellations'][row['id']]['loan_id'],'2002')

    def test_reported_payments_can_be_net_without_overwriting_gross_events(self):
        pages=current_cancellation('payment');pages[0]=pages[0].replace('Pagos recibidos: $14.00','Pagos recibidos: $0.00')
        doc=self.upload(pages);plan=self.preview(doc);result=self.confirm(doc,self.review(plan,payment=PAY))
        self.assertEqual(result['payment_flow_observation'],dict(reported='0.00',gross='14.00',net='0.00',basis='net'))

    def test_reviewed_operations_survive_the_separate_opening_review(self):
        doc=self.upload(multiple_pages());review=self.review(self.preview(doc))
        pending=self.preview(doc,review,opening=None)
        self.assertTrue(pending['cash_opening_confirmation_required']);self.assertEqual(pending['review_rows'],[])
        self.confirm(doc,pending['operation_review'])

    def test_new_loan_uses_published_lent_capital_and_rejects_wrong_cancellation_loan(self):
        pages=current_cancellation('loan');pages[1]=pages[1].replace('$6.00 $6.00 $0.00','$6.00 $0.00 $0.00')
        doc=self.upload(pages);plan=self.preview(doc);review=self.review(plan)
        wrong=json.loads(json.dumps(review));next(iter(wrong['cancellations'].values()))['loan_id']='1001'
        self.assertFalse(self.preview(doc,wrong)['can_confirm'])
        self.confirm(doc,review)


class YoTePrestoCompletionHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_multiple_payment_review_confirm_http(self):
        doc=self.request('/api/upload',content(multiple_pages()),raw=True)
        plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=1,cash_opening_confirmation='10.00'))
        review=dict(payments={},retentions={},cancellations={})
        for row in plan['review_rows']:
            review[row['type']][row['id']]=dict(HALF,loan_id=row['loan_id']) if row['type']=='payments' else dict(retention_isr='0.50',retention_vat='0.50')
        plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=1,cash_opening_confirmation='10.00',operation_review=review))
        self.assertTrue(plan['can_confirm'])
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=1,plan_hash=plan['plan_hash'],cash_opening_confirmation='10.00',operation_review=plan['operation_review']))
        account=self.request('/api/book')['accounts'][0]
        self.assertEqual(account['interest'],'8.62');self.assertEqual(account['closing'],'29.84')

    def test_cancellation_original_selection_http(self):
        doc=self.request('/api/upload',content(current_cancellation('loan')),raw=True)
        plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=1,cash_opening_confirmation='10.00'))
        row=plan['review_rows'][0];review=dict(cancellations={row['id']:dict(original_event_id=row['candidates'][0]['id'],loan_id='2002')})
        plan=self.request('/api/documents/'+doc['id']+'/plan',dict(revision=1,cash_opening_confirmation='10.00',operation_review=review))
        self.assertTrue(plan['can_confirm'])
        self.request('/api/documents/'+doc['id']+'/confirm',dict(revision=1,plan_hash=plan['plan_hash'],cash_opening_confirmation='10.00',operation_review=plan['operation_review']))
        self.assertEqual(self.request('/api/book')['accounts'][0]['closing'],'35.84')

    def test_encrypted_multiple_payment_review_http(self):
        from pypdf import PdfReader,PdfWriter
        from io import BytesIO
        writer=PdfWriter();writer.append(PdfReader(BytesIO(content(multiple_pages()))));writer.encrypt('ONLY-FICTITIOUS-MULTI')
        buffer=BytesIO();writer.write(buffer)
        doc=self.request('/api/upload',buffer.getvalue(),raw=True)
        doc=self.request('/api/documents/'+doc['id']+'/reprocess',dict(revision=1,password='ONLY-FICTITIOUS-MULTI'))
        payload=dict(revision=doc['revision'],cash_opening_confirmation='10.00',password='ONLY-FICTITIOUS-MULTI')
        plan=self.request('/api/documents/'+doc['id']+'/plan',payload)
        review=dict(payments={},retentions={},cancellations={})
        for row in plan['review_rows']:
            review[row['type']][row['id']]=dict(HALF,loan_id=row['loan_id']) if row['type']=='payments' else dict(retention_isr='0.50',retention_vat='0.50')
        payload['operation_review']=review;plan=self.request('/api/documents/'+doc['id']+'/plan',payload)
        self.assertTrue(plan['can_confirm']);payload['plan_hash']=plan['plan_hash'];payload['operation_review']=plan['operation_review']
        result=self.request('/api/documents/'+doc['id']+'/confirm',payload)
        self.assertEqual(result['status'],'imported');self.assertNotIn('ONLY-FICTITIOUS-MULTI',str(result))


if __name__=='__main__':unittest.main()
