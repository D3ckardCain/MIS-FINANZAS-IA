"""Estados de CETESdirecto totalmente ficticios; precios no son interés cobrado."""
from dataclasses import replace
from datetime import date
from decimal import Decimal as D
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from finanzas.cetesdirecto import CetesDirectoInvestmentReader
from finanzas.coverage import review_coverage
from finanzas.readers import ReaderError, reader_for, main
from tests.test_openbank import synthetic_pdf


def statement(new_format=False, closing_cash="0.00", movement="COMPRA"):
    dollar = "$" if new_format else ""
    tax = "ISR Retenidodel período" if new_format else "ISR del período"
    cumulative = "ISR Retenido acumulado del ejercicio fiscal" if new_format else "ISR acumulado del ejercicio fiscal"
    final = f"""cetesdirecto.com
Contrato/Cuenta CLABE: 111111111111111111
Período del: 01/01/2026 al 31/01/2026
Resumen del portafolio
Moneda: MXN PESOS
Total de cartera: $ 11.20
Total de efectivo: $ {closing_cash}
Total final: $ {D('11.20')+D(closing_cash)}
Ingresos del período: $ 0.00
Egresos del período: $ 0.00
{tax}: $ 0.05
{cumulative}: $ 0.05
Intereses del período: $ 1.00
Intereses acumulados del ejercicio fiscal: $ 1.00
Rendimiento BONDDIA: $ 0.12
Resultado por Venta Anticipada GUBER Período: $ 0.00
Posición final del período
Emisora Serie Títulos Precio Valuación
CETES 260129 1 {dollar}10.20000000 {dollar}10.20 90.00% {dollar}10.10000000 29 7.00%
BONDDIA PF2 1 {dollar}1.00000000 {dollar}1.00 10.00% {dollar}1.00000000 0.00%
Posición Total {dollar}11.20
"""
    initial = f"""Contrato/Cuenta CLABE: 111111111111111111
Período del: 01/01/2026 al 31/01/2026
Posición inicial del período
Total de cartera: $ 10.00
Total de efectivo: $ 0.15
Total inicial: $ 10.15
Emisora Serie Títulos Precio Valuación
CETES 260102 1 {dollar}10.00000000 {dollar}10.00 100.00%
Posición Total {dollar}10.00
Movimientos del período
Fecha de registro Fecha de liquidación Folio Descripción Emisora Serie Títulos Precio Plazo Tasa Cargo Abono Saldo efectivo
Saldo inicial 0.15
30/12/25 02/01/26 SVD10001{movement} CETES 260129 1 10.10000000 29 7.00 10.10 0.00 -9.95
02/01/26 02/01/26 SVD10002AMORTIZACION CETES 260102 1 0 0.00 11.00 1.05
02/01/26 02/01/26 SVD10002ISR CETES 260102 0 0.05 0.00 1.00
02/01/26 02/01/26 SVD10003COMPSI BONDDIA PF2 1 1.00000000 0 0.00 1.00 0.00 0.00
Saldo final 0.00
"""
    return [final, initial]


def parsed(**kwargs):
    return CetesDirectoInvestmentReader().read_pages(statement(**kwargs), "synthetic-document")


class CetesDirectoTests(unittest.TestCase):
    def test_legacy_and_new_printed_currency_formats_reconcile(self):
        for new in (False, True):
            with self.subTest(new_format=new):
                result = parsed(new_format=new)
                self.assertTrue(result.reconciled)
                self.assertEqual(len(result.entries), 4)
                self.assertEqual(len(result.final_positions), 2)
                self.assertEqual(result.summary.unit, "MXN")
                self.assertFalse(result.ready_to_import)

    def test_registration_before_month_is_allowed_when_settled_inside_month(self):
        result = parsed()
        first = result.entries[0]
        self.assertEqual(first.registered, date(2025, 12, 30))
        self.assertEqual(first.settled, date(2026, 1, 2))
        self.assertEqual(first.balance, D("-9.95"))
        self.assertTrue(result.detail_reconciled)

    def test_summary_cash_difference_keeps_both_values_without_adjustment(self):
        result = parsed(closing_cash="0.10")
        self.assertTrue(result.detail_reconciled)
        self.assertFalse(result.reconciled)
        self.assertEqual(result.cash_final_detail, D("0.00"))
        self.assertEqual(result.summary.final_cash, D("0.10"))
        self.assertEqual(len(result.entries), 4)

    def test_asset_valuation_not_treated_as_cash_yield(self):
        result = parsed()
        self.assertEqual(result.summary.interest_period, D("1.00"))
        self.assertEqual(result.summary.final_positions, D("11.20"))
        self.assertEqual(result.summary.cash_in, D("0"))
        self.assertEqual(result.final_positions[0].market_price, D("10.20000000"))
        self.assertIn("7.00%", result.final_positions[0].additional_fields)
        self.assertEqual(result.reported_results[0].amount, D("0.12"))

    def test_period_and_cumulative_tax_are_separate(self):
        pages = statement()
        pages[0] = pages[0].replace("ISR acumulado del ejercicio fiscal: $ 0.05", "ISR acumulado del ejercicio fiscal: $ 0.75")
        result = CetesDirectoInvestmentReader().read_pages(pages, "synthetic")
        self.assertTrue(result.reconciled)
        self.assertEqual(result.summary.withholding_period, D("0.05"))
        self.assertEqual(result.summary.withholding_cumulative, D("0.75"))
        amortization, tax = result.entries[1:3]
        self.assertEqual(amortization.folio, tax.folio)
        self.assertNotEqual(amortization.operation, tax.operation)

    def test_unknown_operation_and_broken_balance_require_review(self):
        result = parsed(movement="UNKNOWN")
        self.assertFalse(result.reconciled)
        self.assertEqual(result.entries[0].kind, "unclassified")
        pages = statement()
        pages[1] = pages[1].replace("11.00 1.05", "11.00 1.06")
        result = CetesDirectoInvestmentReader().read_pages(pages, "synthetic")
        self.assertFalse(result.detail_reconciled)

    def test_missing_or_unrecognized_financial_fields_fail_closed(self):
        for old, new in (("ISR del período: $ 0.05", ""),
                         ("CETES 260129 1 10.20000000 10.20", "CETES 260129 1 ilegible 10.20"),
                         ("Moneda: MXN PESOS", "Moneda: USD"),
                         ("0.05 0.00 1.00", "ilegible 0.00 1.00")):
            with self.subTest(old=old), self.assertRaises(ReaderError):
                pages = [p.replace(old, new) for p in statement()]
                CetesDirectoInvestmentReader().read_pages(pages, "synthetic")

    def test_empty_portfolio_and_no_movements_are_valid_only_with_explicit_totals(self):
        pages = statement()
        pages[0] = """cetesdirecto.com
Contrato/Cuenta CLABE: 111111111111111111
Período del: 01/02/2026 al 28/02/2026
Resumen del portafolio
Moneda: PESOS
Total de cartera: $ 0.00
Total de efectivo: $ 0.10
Total final: $ 0.10
Ingresos del período: $ 0.00
Egresos del período: $ 0.00
ISR del período: $ 0.00
ISR acumulado del ejercicio fiscal: $ 0.05
Intereses del período: $ 0.00
Intereses acumulados del ejercicio fiscal: $ 1.00
Posición final del período
Emisora Serie Títulos Precio Valuación
Posición Total 0.00
"""
        pages[1] = """Posición inicial del período
Total de cartera: $ 0.00
Total de efectivo: $ 0.10
Total inicial: $ 0.10
Posición Total 0.00
Movimientos del período
Saldo inicial 0.10
Saldo final 0.10
"""
        result = CetesDirectoInvestmentReader().read_pages(pages, "synthetic")
        self.assertTrue(result.reconciled)
        self.assertEqual(result.entries, ())
        self.assertEqual(result.final_positions, ())

    def test_binary_identity_and_logical_text_equivalence_are_distinct(self):
        a = CetesDirectoInvestmentReader().read_pages(statement(), "pdf-a")
        pages = [p.replace("Total de cartera:", "Total  de cartera:") for p in statement()]
        b = CetesDirectoInvestmentReader().read_pages(pages, "pdf-b")
        self.assertNotEqual(a.document_id, b.document_id)
        self.assertEqual(a.logical_text_id, b.logical_text_id)
        # El control de cobertura conserva ambas versiones y exige revisión, sin fusionarlas.
        self.assertTrue(review_coverage([a, b]).issues)

    def test_pdf_and_catalog_entry_point(self):
        content = synthetic_pdf(statement(new_format=True))
        direct = CetesDirectoInvestmentReader().read_pdf(content)
        catalog = reader_for("cetesdirecto", "investments").read_reconciled_pdf(content)
        self.assertEqual(direct, catalog)
        self.assertTrue(direct.reconciled)

    def test_cli_reports_reconciliation_without_private_amounts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "statement.pdf"
            path.write_bytes(synthetic_pdf(statement()))
            output = StringIO()
            with contextlib.redirect_stdout(output):
                status = main([str(path), "--institution", "cetesdirecto", "--lane", "investments", "--reconcile"])
            self.assertEqual(status, 0)
            self.assertTrue(json.loads(output.getvalue())["reconciled"])
            self.assertNotIn("11.20", output.getvalue())


if __name__ == "__main__":
    unittest.main()
