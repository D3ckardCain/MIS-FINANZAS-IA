"""Fictitious lending records: preserve reported amounts and incomplete evidence."""
from dataclasses import replace
from decimal import Decimal as D
from datetime import date
import unittest
from finanzas.yotepresto import YoTePrestoReader,review_yotepresto
from finanzas.readers import ReaderError,reader_for
from tests.test_openbank import synthetic_pdf


def movement(day,concept,ref,amount,balance):return f'{day}   {concept:<38}   {ref:<16}   {amount}   {balance}'


def source(retained=True,borrower=False):
    final='121.84' if retained else '123.84';available='29.84' if retained else '31.84';gain='6.84' if retained else '8.84'
    tax='(-) Retenciones $2.00\nRetenciones IVA $1.00\nRetenciones ISR $1.00\n' if retained else ''
    first=f'''Usuario: FICTICIO ID: 111
Resumen del mes Del 01 Enero 2026 Al 31 Enero 2026, 31 días
Saldo inicial del periodo $100.00
(+) Intereses recibidos $10.00
Intereses $8.00
IVA de Intereses $1.28
Intereses Moratorios $0.62
IVA de Intereses Moratorios $0.10
{tax}(-) Administración por Éxito $1.16
Comisión $1.00
IVA Comisión $0.16
(+) Fondos Agregados $20.00
(-) Retiros $5.00
Saldo final del periodo ${final}
Saldo disponible para retiro a la fecha ${available}
En este periodo ganaste: ${gain}
Monto total invertido: $106.00
Recursos fondeados: $20.00
Pagos recibidos: $14.00
Inversiones realizadas: $6.00
Comisiones cobradas: $1.16
Recursos retirados: $5.00
Inversiones realizadas históricas
Al corriente 2 100.00% $92.00
En tránsito 0 0.00% $0.00
Atrasado 0 0.00% $0.00
Vencido 0 0.00% $0.00
Pagado -- 0.00% $14.00
'''
    rows=[movement('05/01/2026','Abono','FICTICIO','$20.00','$30.00'),movement('06/01/2026','Pago','1001','$14.00','$44.00')]
    if retained:rows.append(movement('06/01/2026','Retención','1001','-$2.00','$42.00'))
    rows+=[movement('06/01/2026','Administración por éxito','1001','-$1.16','$40.84' if retained else '$42.84'),movement('07/01/2026','Préstamo','LLL-2002','-$6.00','$34.84' if retained else '$36.84'),movement('08/01/2026','Retiro','FICTICIO','-$5.00','$'+available)]
    a='LLL- Al Corriente' if borrower else 'Al Corriente'
    second='Mis movimientos\nFecha Concepto Usuario / Referencia Monto Saldo\n'+'\n'.join(rows)+'\nInversiones realizadas\nFecha ID Estatus Plazo Tasa Prestado Saldo al inicio Saldo al final Intereses IVA Capital\n'
    second+=f'01/05/2025 1001 {a} 12/36 10.00% $100.00 $90.00 $86.00 $18.62 $2.98 $14.00\n'
    if borrower:second+='  1001\n'
    second+='07/01/2026 2002 Al Corriente 0/36 9.00% $6.00 $6.00 $6.00 $0.00 $0.00 $0.00\nInversiones realizadas atrasadas\nActualmente no tienes inversiones atrasadas activas.\nTodas las cantidades en moneda nacional www.yotepresto.com'
    return [first,second]


def read(pages=None,lane='investments'):return YoTePrestoReader(lane).read_pages(pages or source(),'fictitious')


class YoTePrestoTests(unittest.TestCase):
    def test_summary_global_and_available_are_distinct(self):
        r=read();self.assertTrue(r.summary_reconciled)
        self.assertEqual(r.summary.final,D('121.84'))
        self.assertEqual(r.summary.available,D('29.84'))
        self.assertEqual(r.cash_initial_implied,D('10.00'))
        self.assertFalse(r.detail_reconciled)
        self.assertFalse(r.ready_to_import)

    def test_interest_vat_and_isr_are_not_combined_or_called_final_tax(self):
        r=read();self.assertEqual(r.summary.ordinary_interest,D('8.00'))
        self.assertEqual(r.summary.interest_received_with_vat,D('10.00'))
        self.assertEqual(r.summary.retention_vat,D('1.00'))
        self.assertEqual(r.summary.retention_isr,D('1.00'))
        self.assertEqual(r.summary.retention_total,D('2.00'))

    def test_absent_retention_stays_unknown_not_zero(self):
        r=read(source(False))
        self.assertIsNone(r.summary.retention_isr)
        self.assertIsNone(r.summary.retention_total)
        self.assertTrue(any('no publicadas' in i for i in r.summary_issues))

    def test_reported_gain_can_be_before_or_after_retention(self):
        a=read();self.assertEqual(a.summary.gain_basis_observed,'after_retention')
        s=source();s[0]=s[0].replace('ganaste: $6.84','ganaste: $8.84')
        self.assertEqual(read(s).summary.gain_basis_observed,'before_retention')

    def test_new_and_old_loan_formats_preserve_status_without_inventing_borrower(self):
        r=read();self.assertIsNone(r.loans[0].borrower_printed)
        self.assertEqual(r.loans[0].status,'al corriente')
        old=read(source(borrower=True))
        self.assertEqual(old.loans[0].borrower_printed,'LLL-1001')
        self.assertEqual(old.loans[0].status,'al corriente')
        self.assertEqual(old.loans[0].term_printed,'12/36')

    def test_cumulative_loan_fields_are_not_monthly_income(self):
        r=read();self.assertEqual(r.loans[0].interest_paid_cumulative,D('18.62'))
        self.assertEqual(r.summary.ordinary_interest,D('8.00'))
        self.assertEqual(r.loans[0].principal_paid_cumulative,D('14.00'))
        self.assertEqual(r.rows[1].category,'repayment')
        self.assertEqual(r.rows[1].amount,D('14.00'))

    def test_two_views_share_evidence_and_cannot_double_count_cash(self):
        a=read();b=read(lane='debit')
        self.assertEqual(a.rows,b.rows)
        self.assertEqual(a.account_fingerprint,b.account_fingerprint)
        self.assertEqual(len(review_yotepresto([a,b]).documents),1)

    def test_same_day_same_reference_different_concepts_not_deduplicated(self):
        r=read();group=[x for x in r.rows if x.reference=='1001']
        self.assertEqual(len(group),3)
        self.assertEqual(len({x.evidence_id for x in group}),3)

    def test_unbalanced_printed_cash_row_preserved_without_reordering(self):
        s=source();s[1]=s[1].replace('$44.00','$43.99')
        r=read(s)
        self.assertEqual(r.rows[1].balance,D('43.99'))
        self.assertTrue(any(d.check=='Saldo operativo por fila no concilia' for d in r.differences))
        self.assertTrue(r.summary_reconciled)

    def test_paid_position_count_dash_is_unknown(self):
        paid=next(p for p in read().positions if p.status=='pagado')
        self.assertIsNone(paid.count_reported)
        self.assertEqual(paid.amount_reported,D('14.00'))

    def test_arrears_preserve_days_and_raw_collection_context(self):
        s=source();s[1]=s[1].replace('Actualmente no tienes inversiones atrasadas activas.','1001 Vencido 93    Motivo ficticio    Gestión ficticia')
        a=read(s).arrears[0]
        self.assertEqual(a.loan_id,'1001');self.assertEqual(a.days,93)
        self.assertIn('Gestión',a.details_printed)

    def test_partial_tax_missing_identity_and_bad_loan_row_fail_closed(self):
        for old,new in [('ID: 111','Sin ID'),('Retenciones IVA $1.00','IVA ausente'),('$18.62 $2.98 $14.00','$18.62 ausente')]:
            with self.assertRaises(ReaderError):read([p.replace(old,new) for p in source()])

    def test_history_dedup_account_and_overlap(self):
        a=read();h=review_yotepresto([a,a]);self.assertEqual(h.duplicates,('fictitious',))
        with self.assertRaises(ReaderError):review_yotepresto([a,replace(a,document_id='other')])
        with self.assertRaises(ReaderError):review_yotepresto([a,replace(a,document_id='other',account_fingerprint='other')])

    def test_cumulative_decrease_preserved_not_reclassified_as_loss(self):
        a=read();loan=replace(a.loans[0],interest_paid_cumulative=D('18.61'))
        b=replace(a,document_id='feb',period_start=date(2026,2,1),period_end=date(2026,2,28),loans=(loan,a.loans[1]),cash_initial_implied=a.summary.available)
        h=review_yotepresto([a,b])
        self.assertEqual(len(h.cumulative_decreases),1)
        self.assertTrue(h.cash_links[0].matches)
        self.assertEqual(h.cumulative_decreases[0].current,D('18.61'))

    def test_pdf_catalog_uses_specialized_reader_without_import(self):
        r=reader_for('yotepresto','investments').read_reconciled_pdf(synthetic_pdf(source()))
        self.assertTrue(r.summary_reconciled)
        self.assertFalse(r.ready_to_import)
        self.assertEqual(len(r.loans),2)


    def test_cash_continuation_after_footer_restores_section_from_header(self):
        s=source();lines=s[1].splitlines();cut=next(i for i,l in enumerate(lines) if 'Administración por éxito' in l)
        pages=[s[0],'\n'.join(lines[:cut])+"\nComunidad de Préstamos texto legal",'Fecha Concepto Usuario / Referencia Monto Saldo\n'+'\n'.join(lines[cut:])]
        r=read(pages)
        self.assertEqual(len(r.rows),6)
        self.assertEqual(len(r.loans),2)
        self.assertEqual(r.rows[-1].balance,D('29.84'))


    def test_monthly_summary_tax_and_fee_not_replaced_by_cash_row_totals(self):
        s=source();s[1]=s[1].replace('-$2.00','-$1.99').replace('-$1.16','-$1.15')
        r=read(s)
        self.assertTrue(r.summary_reconciled)
        self.assertEqual(r.summary.retention_total,D('2.00'))
        self.assertTrue(any('Retenciones netas' in d.check for d in r.differences))
        self.assertTrue(any('Comisiones netas' in d.check for d in r.differences))


if __name__=='__main__':unittest.main()
