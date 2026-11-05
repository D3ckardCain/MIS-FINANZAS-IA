"""Fondeadora ficticia: no convertir una cuenta operativa vacía en cartera cero."""
from dataclasses import replace
from datetime import date
from decimal import Decimal as D
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from finanzas.fondeadora import FondeadoraReader
from finanzas.coverage import review_coverage
from finanzas.readers import ReaderError, reader_for, main
from tests.test_openbank import synthetic_pdf


def statement(explained=False, empty=False):
    deposit = "0.00" if empty else "100.00"
    withdrawal = "100.00" if explained and not empty else "0.00"
    first = f"""Fondea Technologies S.A. de C.V. S.F.P.
Estado de cuenta
Enero 1-Enero 31, 2026 (31 días)
Detalles de la cuenta
CLABE interbancaria 111111111111111111
Saldo inicial $0.00
Compras $0.00
Depósitos ${deposit}
Retiros ${withdrawal}
Comisiones totales $0.00
Interés ganado $0.00
Impuestos retenidos $0.00
Saldo final al periodo $0.00
Ganancia Anual Total (GAT) nominal antes de impuestos %
Ganancia Anual Total (GAT) real %
Tasa de rendimiento anual, simple, antes de impuestos %
"""
    second = """Movimientos
Fecha  Descripción  Cargos  Abonos  Saldo
"""
    if not empty:
        second += """02/01/2026  Depósito vía SPEI  $0.00  $100.00  $100.00
03/01/2026  Traspaso entre cuentas FONDEA  $100.00  $0.00  $0.00
"""
    return [first, second + "2/2\n"]


def report():
    return ["""Reporte de movimientos enero 2026
Enero 01 - enero 31, 2026
Apoyo Múltiple, S.A. de C.V., S.F.P. apoyomultiple.com
Detalles de la cuenta
CLABE 111111111111111111
Detalle del mes
Depósitos $50.00
Gastos $40.00
""", """Fecha  Descripción  Cantidad
Ene 05  Apartado a 30 días  $40.00
Ene 05  Transferencia a Yo  -$40.00
Ene 06  Depósito vía SPEI  $50.00
Ene 06  Apartado a 30 días  -$50.00
"""]


class FondeadoraTests(unittest.TestCase):
    def test_internal_transfer_not_explained_by_summary_remains_pending(self):
        r = FondeadoraReader().read_pages(statement(), "synthetic")
        self.assertTrue(r.detail_reconciled, r.detail_issues)
        self.assertFalse(r.reconciled)
        self.assertEqual(r.entries[1].category, "internal_transfer")
        self.assertEqual(r.entries[1].debit, D("100.00"))
        self.assertEqual(r.summary.withdrawals_or_spending, D("0.00"))
        self.assertEqual(len(r.differences), 2)

    def test_recognized_balances_can_reconcile_without_becoming_importable(self):
        r = FondeadoraReader().read_pages(statement(explained=True), "synthetic")
        self.assertTrue(r.reconciled, (r.issues,r.detail_issues))
        self.assertIsNone(r.summary.annual_rate_reported)
        self.assertIsNone(r.investment_balance)
        self.assertFalse(r.ready_to_import)

    def test_report_does_not_invent_balances_interest_or_retention(self):
        r = FondeadoraReader().read_pages(report(), "synthetic")
        self.assertEqual(len(r.entries), 4)
        self.assertTrue(r.detail_reconciled)
        self.assertIsNone(r.summary.initial)
        self.assertIsNone(r.summary.final)
        self.assertIsNone(r.summary.interest)
        self.assertIsNone(r.summary.withholding)
        self.assertFalse(r.reconciled)

    def test_apartado_credit_is_not_interest_and_reinvestment_not_external_deposit(self):
        r = FondeadoraReader().read_pages(report(), "synthetic")
        self.assertEqual(r.entries[0].category,"term_transfer")
        self.assertEqual(r.entries[-1].category,"term_transfer")
        self.assertEqual(len(r.investment_candidates), 2)
        self.assertEqual(r.summary.deposits, D("50.00"))
        self.assertEqual(r.summary.withdrawals_or_spending, D("40.00"))
        self.assertIsNone(r.entries[0].debit)
        self.assertIsNone(r.entries[0].balance)

    def test_investment_view_never_uses_operating_zero_as_invested_balance(self):
        r = FondeadoraReader("investments").read_pages(statement(explained=True), "synthetic")
        self.assertTrue(r.detail_reconciled)
        self.assertFalse(r.reconciled)
        self.assertEqual(r.scope,"investment_transfer_evidence")
        self.assertIsNone(r.investment_balance)
        self.assertEqual(len(r.investment_candidates),1)

    def test_summary_only_and_explicit_empty_table_have_different_status(self):
        pages = statement(empty=True)
        summary_only = FondeadoraReader().read_pages(pages[:1],"synthetic")
        empty_table = FondeadoraReader().read_pages(pages,"synthetic")
        self.assertFalse(summary_only.detail_reconciled)
        self.assertTrue(empty_table.reconciled)
        self.assertEqual(summary_only.summary.interest,D("0.00"))
        self.assertIsNone(summary_only.investment_balance)

    def test_spacing_glitches_are_local_to_fields_and_raw_dates_remain_authoritative(self):
        raw = statement(empty=True)
        layout = [p.replace("Enero", "E ne ro").replace("CLABE", "C L A B E")
                    .replace("111111111111111111", "111111 111111 111111")
                    .replace("$0.00", "$0. 00") for p in raw]
        r = FondeadoraReader().read_pages(layout,"synthetic",raw_pages=raw)
        self.assertTrue(r.reconciled,(r.issues,r.detail_issues))
        self.assertEqual(r.period_end,date(2026,1,31))
        self.assertEqual(r.account_fingerprint,FondeadoraReader().read_pages(raw,"other").account_fingerprint)

    def test_blank_rate_is_not_zero_but_explicit_zero_rate_is_preserved(self):
        pages = statement(empty=True)
        pages[0] = pages[0].replace("antes de impuestos %", "antes de impuestos 0. 00%")
        r = FondeadoraReader().read_pages(pages,"synthetic")
        self.assertEqual(r.summary.annual_rate_reported,D("0.00"))
        self.assertIsNone(FondeadoraReader().read_pages(statement(empty=True),"other").summary.annual_rate_reported)

    def test_one_cent_running_balance_difference_is_not_adjusted(self):
        pages = statement(explained=True)
        pages[1] = pages[1].replace("$0.00  $100.00  $100.00", "$0.00  $100.00  $99.99")
        r = FondeadoraReader().read_pages(pages,"synthetic")
        self.assertFalse(r.detail_reconciled)
        self.assertEqual(r.entries[0].balance,D("99.99"))

    def test_unknown_category_date_or_amount_stays_pending(self):
        for old,new in (("Depósito vía SPEI","Otro concepto"),("02/01/2026","02/02/2026"),("$100.00  $0.00  $0.00","$10O.00  $0.00  $0.00")):
            pages = statement(explained=True)
            pages[1] = pages[1].replace(old,new)
            self.assertFalse(FondeadoraReader().read_pages(pages,"synthetic").detail_reconciled)

    def test_missing_identity_account_summary_or_conflicting_dates_fails_closed(self):
        for field in ("Fondea Technologies","CLABE interbancaria","Saldo final al periodo"):
            pages = [p.replace(field,"Ausente") for p in statement()]
            with self.assertRaises(ReaderError):FondeadoraReader().read_pages(pages,"synthetic")
        with self.assertRaises(ReaderError):
            FondeadoraReader().read_pages([p.replace("2026","2025") for p in statement()],"synthetic",raw_pages=statement())

    def test_continuity_never_compares_two_unknown_balances_as_zero(self):
        first = FondeadoraReader().read_pages(report(),"synthetic")
        second = replace(first,document_id="second",period_start=date(2026,2,1),period_end=date(2026,2,28))
        review = review_coverage([first,second,first])
        self.assertEqual(review.continuity_checked,0)
        self.assertEqual(len(review.duplicate_documents),1)
        self.assertTrue(any("no informado" in x for x in review.issues))

    def test_catalog_supports_both_issuer_formats_and_private_cli_output(self):
        content = synthetic_pdf(statement(explained=True))
        self.assertTrue(reader_for("fondeadora","debit").read_reconciled_pdf(content).reconciled)
        generic = reader_for("fondeadora","debit").read_pdf(content)
        self.assertEqual(generic.institution,"fondeadora")
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"synthetic.pdf";p.write_bytes(content)
            out=StringIO()
            with contextlib.redirect_stdout(out):main([str(p),"--institution","fondeadora","--lane","investments","--reconcile"])
            data=json.loads(out.getvalue())
            self.assertEqual(data["scope"],"investment_transfer_evidence")
            self.assertFalse(data["investment_balance_known"])
            self.assertNotIn("100.00",out.getvalue())


if __name__ == "__main__":unittest.main()
