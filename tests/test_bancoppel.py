"""Extractos ficticios independientes del catálogo; no incluyen estados del titular."""
from dataclasses import replace
from datetime import date
from decimal import Decimal as D
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from finanzas.bancoppel import BanCoppelDebitReader
from finanzas.coverage import review_coverage
from finanzas.readers import ReaderError, reader_for, main
from tests.test_openbank import synthetic_pdf


def statement(commission="4.75", gross="0.25", withholding="0.00"):
    return f"""BanCoppel
Número de Cuenta:
CLABE:
11111111111
111111111111111111
Detalle de Movimientos
Período: 12/DIC./2025 AL 11/ENE./2026
Fecha Retiros Depósitos Saldo Conceptos
01/11 0.25 124.70
PAGO DE INTERESES
01/05 0.80 124.45
IVA COMISIONES
01/05 4.75 125.25
COMISION DEPOSITO CORRESPONSAL
12/20 20.00 130.00
CARGO SPEI referencia-ficticia
12/15 50.00 150.00
DEPOSITO EN EFECTIVO
Hoja 1 de 2
Resumen de la Cuenta
+ Más Depósitos
- Menos Retiros
+ Más Intereses del Periodo
- Menos Comisiones
- Menos IVA Comisiones
Saldo Actual
Saldo Anterior
100.00
50.00
20.00
0.25
{commission}
0.80
124.70
Hoja 2 de 2
$
(Saldo inicial de $100.00)
Cálculo de Intereses
Saldo Promedio Mensual
Días del Periodo
Intereses Ganados
- Menos Retención
Intereses del Periodo
120.00
31
0.10 %
{gross}
{withholding}
0.25
Utiliza tu tarjeta
"""


def parsed(**kwargs):
    return BanCoppelDebitReader().read_pages([statement(**kwargs)], "synthetic-document")


class BanCoppelTests(unittest.TestCase):
    def test_reverse_detail_and_year_rollover_reconcile(self):
        result = parsed()
        self.assertTrue(result.reconciled)
        self.assertTrue(result.detail_reconciled)
        self.assertFalse(result.ready_to_import)
        self.assertEqual(len(result.entries), 5)
        self.assertEqual(result.entries[0].effective_date, date(2025, 12, 15))
        self.assertEqual(result.entries[-1].effective_date, date(2026, 1, 11))
        self.assertEqual(result.entries[0].direction, "deposit")
        self.assertEqual(result.entries[1].direction, "withdrawal")
        self.assertEqual(result.summary.interest_gross, D("0.25"))
        self.assertEqual(result.summary.withholding, D("0.00"))
        self.assertEqual(result.summary.annual_rate_reported, D("0.10"))

    def test_summary_fee_difference_not_fixed_by_inventing_adjustment(self):
        result = parsed(commission="5.00")
        self.assertTrue(result.detail_reconciled)
        self.assertFalse(result.reconciled)
        self.assertEqual(result.summary.commissions, D("5.00"))
        self.assertEqual(next(e.amount for e in result.entries if e.category == "commission"), D("4.75"))
        self.assertEqual(len(result.entries), 5)
        self.assertTrue(any("Comisiones" in issue for issue in result.issues))

    def test_tampered_detail_is_detected_without_rewriting_balance(self):
        text = statement().replace("01/11 0.25 124.70", "01/11 0.25 124.71")
        result = BanCoppelDebitReader().read_pages([text], "synthetic")
        self.assertFalse(result.detail_reconciled)
        self.assertEqual(result.entries[-1].balance, D("124.71"))

    def test_unrecognized_dated_row_cannot_be_silently_dropped(self):
        text = statement().replace("12/20 20.00 130.00", "12/20 importe ilegible")
        with self.assertRaises(ReaderError):
            BanCoppelDebitReader().read_pages([text], "synthetic")

    def test_missing_withholding_is_not_assumed_zero(self):
        text = statement().replace("0.25\n0.00\n0.25\nUtiliza", "0.25\n0.25\nUtiliza")
        with self.assertRaises(ReaderError):
            BanCoppelDebitReader().read_pages([text], "synthetic")

    def test_positive_withholding_requires_detail_review(self):
        result = parsed(gross="0.35", withholding="0.10")
        self.assertEqual(result.summary.withholding, D("0.10"))
        self.assertFalse(result.reconciled)
        self.assertTrue(any("Retención no nula" in issue for issue in result.issues))

    def test_pdf_and_catalog_strict_entry_are_consistent(self):
        content = synthetic_pdf([statement()])
        direct = BanCoppelDebitReader().read_pdf(content)
        catalog = reader_for("bancoppel", "debit").read_reconciled_pdf(content)
        self.assertEqual(direct, catalog)
        self.assertTrue(catalog.reconciled)

    def test_explicit_admin_fee_is_not_personal_rent_expense(self):
        text = statement().replace("COMISION DEPOSITO CORRESPONSAL", "ADMINISTRACION RENTA")
        result = BanCoppelDebitReader().read_pages([text], "synthetic")
        self.assertEqual(next(e for e in result.entries if e.amount == D("4.75")).category, "commission")

    def test_cli_reconcile_does_not_print_balances_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "statement.pdf"
            path.write_bytes(synthetic_pdf([statement()]))
            output = StringIO()
            with contextlib.redirect_stdout(output):
                result = main([str(path), "--institution", "bancoppel", "--lane", "debit", "--reconcile"])
            self.assertEqual(result, 0)
            self.assertTrue(json.loads(output.getvalue())["reconciled"])
            self.assertNotIn("124.70", output.getvalue())


class CoverageTests(unittest.TestCase):
    def test_exact_document_duplicate_does_not_duplicate_coverage(self):
        first = parsed()
        review = review_coverage([first, first])
        self.assertEqual(len(review.unique_documents), 1)
        self.assertEqual(review.duplicate_documents, (first.document_id,))

    def test_adjacent_balances_checked_and_gap_not_filled(self):
        first = parsed()
        second = replace(first, document_id="second", period_start=date(2026, 1, 12),
                         period_end=date(2026, 2, 11), summary=replace(first.summary, initial=first.summary.final))
        third = replace(second, document_id="third", period_start=date(2026, 4, 12), period_end=date(2026, 5, 11))
        review = review_coverage([third, first, second])
        self.assertEqual(review.continuity_checked, 1)
        self.assertEqual(review.missing_ranges, ((date(2026, 2, 12), date(2026, 4, 11)),))
        self.assertEqual(review.issues, ())

    def test_different_accounts_never_compared_for_continuity(self):
        first = parsed()
        for identity in ("another-account", None):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                review_coverage([first, replace(first, document_id="another", account_fingerprint=identity)])

    def test_overlap_does_not_create_a_false_gap_within_covered_dates(self):
        first = replace(parsed(), period_start=date(2026, 1, 1), period_end=date(2026, 3, 31))
        nested = replace(first, document_id="nested", period_start=date(2026, 2, 1), period_end=date(2026, 2, 28))
        last = replace(first, document_id="last", period_start=date(2026, 5, 1), period_end=date(2026, 5, 31))
        result = review_coverage([first, nested, last])
        self.assertEqual(result.missing_ranges, ((date(2026, 4, 1), date(2026, 4, 30)),))
        self.assertTrue(result.issues)

    def test_same_period_different_version_is_not_silently_merged(self):
        first = parsed()
        result = review_coverage([first, replace(first, document_id="different-version")])
        self.assertEqual(len(result.unique_documents), 2)
        self.assertTrue(result.issues)


if __name__ == "__main__":
    unittest.main()
