"""Mifel ficticio: fecha del cobro y días remunerados separados."""
from dataclasses import replace
from datetime import date
from decimal import Decimal as D
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from finanzas.mifel import MifelReader,review_mifel_documents
from finanzas.readers import ReaderError,reader_for,main
from tests.test_openbank import synthetic_pdf


def statement(august=False):
    month="08" if august else "07";day="03" if august else "31"
    initial="102.70" if august else "100.00";final="103.60" if august else "102.70"
    gross="1.00" if august else "3.00";tax="0.10" if august else "0.30"
    accrual_start=f'{day}-{month}-2026';accrual_end='03-08-2026' if august else '02-08-2026'
    first=f"""Banca Mifel
Periodo 01/{month}/2026 al 31/{month}/2026
Resumen de Cuenta a la vista
GAT nominal antes de impuestos 10.47%
GAT Real antes de impuestos 6.14%
Interés aplicable o rendimiento {gross}
Tasa anual 10.00%
Saldo promedio diario {initial}
Todos los Importes denominados en pesos mexicanos
Comisiones efectivamente cobradas 0.00
IVA 0.00
Posición total al inicio del mes {initial}
Cuenta a la vista {final}
Inversiones 0.00
Fondos de inversión 0.00
Pendiente de liquidar – compras 0.00
Pendiente de liquidar – ventas 0.00
Mesa de dinero 0.00
Efectivo en Mesa de dinero 0.00
Posición total al cierre del mes {final}
1. Saldo inicial $100
7. Saldo final $103
"""
    second=f"""Rendimientos y valuación de productos
Productos  Interés ganado  ISR Retenido
Cuenta a la vista  {gross}  {tax}
Detalles de la Cuenta a la vista 1111111111
Saldo inicial {initial}
"""
    second+='Fecha  Referencia  Descripción'.ljust(96)+'Retiros'.ljust(20)+'Depósitos'.ljust(24)+'Saldo\n'
    root="S2000" if august else "S1000"
    tax_balance='102.60' if august else '99.70'
    def row(ref,description,debit=None,credit=None,balance="0.00"):
        return f'{day}/{month}/2026  {ref}  {description}'.ljust(96)+(debit or '').rjust(12)+(credit or '').rjust(20)+balance.rjust(24)
    second+=row(root+'-2','ISR RETENIDO PARA -',debit=tax,balance=tax_balance)+'\n  01111111111\n'
    second+=row(root+'-1',f'PAGO INTERESES:{accrual_start} to',credit=gross,balance=final)+'\n  '+accrual_end+'\n'
    second+=f'Suma de retiros y depósitos  {tax}  {gross}\nSaldo a fecha de corte  {final}\n'
    second+='31/07/2026  S9999-1  CARGO OBJETADO FUERA DEL DETALLE  500.00\n'
    return [first,second]


def read(source=None,lane="investments"):
    return MifelReader(lane).read_pages(source or statement(),"synthetic")


class MifelTests(unittest.TestCase):
    def test_interest_and_tax_are_distinct_without_using_rounded_chart(self):
        r=read()
        self.assertTrue(r.reconciled,(r.issues,r.detail_issues))
        self.assertEqual(r.summary.final,D("102.70"))
        self.assertEqual(r.summary.gross_interest,D("3.00"))
        self.assertEqual(r.summary.withholding,D("0.30"))
        self.assertEqual(r.income_groups[0].net,D("2.70"))
        self.assertEqual(len(r.entries),2)
        self.assertFalse(r.ready_to_import)

    def test_payment_month_does_not_change_when_coverage_extends_next_month(self):
        r=read();g=r.income_groups[0]
        self.assertEqual(g.effective_date,date(2026,7,31))
        self.assertEqual(g.accrual_start,date(2026,7,31))
        self.assertEqual(g.accrual_end,date(2026,8,2))
        self.assertEqual(r.period_end,date(2026,7,31))

    def test_views_share_exact_account_and_evidence_not_two_balances(self):
        debit=read(lane="debit");investment=read()
        self.assertEqual(debit.account_fingerprint,investment.account_fingerprint)
        self.assertEqual(debit.summary,investment.summary)
        self.assertEqual(debit.entries,investment.entries)
        self.assertTrue(investment.shared_account)
        self.assertEqual(investment.product,"cuenta_a_la_vista_remunerada")

    def test_interest_and_retention_pair_by_root_and_date_not_row_order(self):
        g=read().income_groups[0]
        self.assertEqual(g.reference_root,"S1000")
        self.assertEqual(g.interest_reference,"S1000-1")
        self.assertEqual(g.withholding_reference,"S1000-2")
        self.assertEqual(len(g.source_lines),2)

    def test_one_cent_balance_difference_is_never_adjusted(self):
        source=statement();source[1]=source[1].replace('99.70','99.69')
        r=read(source)
        self.assertFalse(r.detail_reconciled)
        self.assertEqual(r.entries[0].balance,D('99.69'))

    def test_missing_accrual_end_is_not_inferred_from_booking_date(self):
        source=statement();source[1]=source[1].replace('  02-08-2026\n','')
        r=read(source)
        self.assertFalse(r.detail_reconciled)
        self.assertIsNone(r.entries[-1].accrual_end)
        self.assertEqual(r.income_groups,())

    def test_inverted_accrual_range_remains_pending(self):
        source=statement();source[1]=source[1].replace('02-08-2026','30-07-2026')
        self.assertFalse(read(source).detail_reconciled)

    def test_unknown_concept_retains_row_without_classifying_it_as_interest(self):
        source=statement();source[1]=source[1].replace('ISR RETENIDO PARA -','OTRO CONCEPTO'.ljust(len('ISR RETENIDO PARA -')))
        r=read(source)
        self.assertFalse(r.detail_reconciled)
        self.assertEqual(len(r.entries),2)
        self.assertEqual(r.entries[0].category,'unknown')

    def test_duplicate_reference_is_not_silently_deleted(self):
        source=statement();row=next(l for l in source[1].splitlines() if 'ISR RETENIDO' in l)
        source[1]=source[1].replace('Suma de retiros',row+'\nSuma de retiros')
        r=read(source)
        self.assertEqual(len(r.entries),3)
        self.assertFalse(r.detail_reconciled)

    def test_other_products_nonzero_require_specific_reader(self):
        source=statement();source[0]=source[0].replace('Inversiones 0.00','Inversiones 1.00')
        r=read(source)
        self.assertFalse(r.reconciled)
        self.assertEqual(dict(r.summary.other_positions)['Inversiones'],D('1.00'))

    def test_cross_month_coverage_deduplicates_evidence_and_does_not_double_count_days(self):
        july=read();august=replace(read(statement(True)),document_id='august')
        result=review_mifel_documents([july,august,july])
        self.assertEqual(result.coverage.continuity_checked,1)
        self.assertEqual(len(result.coverage.duplicate_documents),1)
        self.assertEqual(result.accrual_days,4)
        self.assertEqual(result.accrual_gaps,())
        self.assertEqual(result.accrual_overlaps,())

    def test_same_period_versions_do_not_hide_overlapping_paid_ranges(self):
        first=read();version=replace(first,document_id='another-file')
        result=review_mifel_documents([first,version])
        self.assertEqual(result.accrual_days,3)
        self.assertTrue(result.accrual_overlaps)
        self.assertTrue(result.coverage.issues)

    def test_missing_identity_currency_account_or_table_fails_closed(self):
        for marker in ('Banca Mifel','pesos mexicanos','Detalles de la Cuenta a la vista','Suma de retiros y depósitos'):
            with self.assertRaises(ReaderError):read([p.replace(marker,'Ausente') for p in statement()])

    def test_pdf_catalog_and_private_console(self):
        content=synthetic_pdf(statement())
        r=reader_for('mifel','investments').read_reconciled_pdf(content)
        self.assertTrue(r.reconciled,(r.issues,r.detail_issues))
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'nombre_noviembre.pdf';p.write_bytes(content);out=StringIO()
            with contextlib.redirect_stdout(out):main([str(p),'--institution','mifel','--lane','debit','--reconcile'])
            self.assertTrue(json.loads(out.getvalue())['reconciled'])
            self.assertNotIn('102.70',out.getvalue())
        self.assertEqual(r.period_start,date(2026,7,1))


if __name__=='__main__':unittest.main()
