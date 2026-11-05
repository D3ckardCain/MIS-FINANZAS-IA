"""Datos íntegramente sintéticos; no incluyen documentos del titular."""
import contextlib
from decimal import Decimal as D
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from finanzas.didi import DidiReader
from finanzas.readers import ReaderError, main, reader_for
from tests.test_openbank import synthetic_pdf


def fixture(new=True):
    header = """DiDi Cuenta J.P. Sofiexpress
El periodo: 01/01/26 - 31/01/26
Número de cuenta: 11111111111
"""
    layout = """Saldo inicial $ 100.00
Depósitos $ 51.00
Retiros $ 20.00
Saldo promedio $ 120.00
Rendimiento $ 1.00
Impuesto retenido $ 0.00
Saldo final $ 131.00
""" if new else """Saldo inicial    Depósitos    Retiros
$ 100.00         $ 51.00      $ 20.00
Saldo al cierre: $ 131.00   Rendimientos totales: $ 1.00
Saldo promedio diario: $ 120.00   Total de impuestos deducidos: $ 0.00
"""
    rates = """1. Hasta $ 10000.00 MXN:
Tasa de rendimiento anual fija: 12.00%. GAT Nominal 12.50%
2. Monto restante:
Tasa de rendimiento anual fija: 5.00%. GAT Nominal 5.10%
Fecha de cálculo: 01/12/2025
"""
    details = """Detalles de movimientos DiDi Cuenta
Saldo inicial $ 100.00
02/01/2026 Depósito Transferencia entrante
Identificación del movimiento:CBS000001
MXN $ 50.00 $ 150.00
05/01/2026 Depósito Rendimientos Identificación del
movimiento:SNCBS0000
02
MXN $ 1.00 $ 151.00
08/01/2026 Retiro Transferencia saliente
Identificación del movimiento:
MXN $ 20.00 $ 131.00
"""
    continuation = """4Página 3 de
El periodo: 01/01/26 - 31/01/26
Número de cuenta: 11111111111
Depósito Retiro
Registro de movimientos impugnados
ID de registro Hora de inicio Estado Conclusión
CBS000003
"""
    return [header + layout + rates, details, continuation], layout


def parsed(pages=None, layout=None, lane="investments"):
    source, summary = fixture()
    return DidiReader(lane).read_pages(pages or source, "synthetic", layout=layout or summary)


class DidiTests(unittest.TestCase):
    def test_both_summary_formats_and_reference_across_page(self):
        for new in (True, False):
            pages, layout = fixture(new)
            result = parsed(pages, layout)
            self.assertTrue(result.reconciled, (result.issues, result.detail_issues))
            self.assertEqual([e.reference for e in result.entries], ["CBS000001", "SNCBS000002", "CBS000003"])
            self.assertEqual(result.entries[-1].page, 2)
            self.assertFalse(result.ready_to_import)

    def test_deposits_include_interest_not_two_income_streams(self):
        result = parsed()
        self.assertEqual(result.summary.deposits, D("51.00"))
        self.assertEqual(result.summary.interest, D("1.00"))
        self.assertEqual(result.entries[0].category, "transfer_unmatched")
        self.assertEqual(result.entries[1].category, "interest")

    def test_views_share_evidence_and_do_not_create_two_accounts(self):
        debit, investment = parsed(lane="debit"), parsed()
        self.assertEqual(debit.account_fingerprint, investment.account_fingerprint)
        self.assertEqual(debit.entries, investment.entries)
        self.assertTrue(debit.shared_account)
        self.assertEqual(debit.lane, "debit")

    def test_disclosed_rates_preserve_caps_without_inventing_effective_date(self):
        result = parsed()
        self.assertEqual(result.annual_rates_reported, (D("12.00"), D("5.00")))
        self.assertIn("Hasta $ 10000.00", result.rate_disclosure)
        self.assertIn("01/12/2025", result.rate_disclosure)
        self.assertEqual(result.period_start.isoformat(), "2026-01-01")

    def test_running_balance_difference_stays_pending(self):
        pages, layout = fixture()
        pages[1] = pages[1].replace("$ 150.00", "$ 149.99")
        result = parsed(pages, layout)
        self.assertIn("Saldo corriente no concilia", result.detail_issues)
        self.assertEqual(result.entries[0].balance, D("149.99"))

    def test_summary_yield_mismatch_preserves_detail(self):
        pages, layout = fixture()
        result = parsed(pages, layout.replace("Rendimiento $ 1.00", "Rendimiento $ 2.00"))
        self.assertFalse(result.reconciled)
        self.assertTrue(result.detail_reconciled)
        self.assertEqual(result.entries[1].amount, D("1.00"))

    def test_reference_missing_or_duplicated_is_never_silently_accepted(self):
        for replacement in ("", "CBS000001"):
            pages, layout = fixture()
            pages[2] = pages[2].replace("CBS000003", replacement)
            result = parsed(pages, layout)
            self.assertFalse(result.detail_reconciled)
            self.assertEqual(len(result.entries), 3)

    def test_unknown_category_currency_or_row_remains_pending(self):
        for old, new in (("Transferencia entrante", "Otra operación"),
                         ("MXN $ 50.00", "USD $ 50.00"),
                         ("02/01/2026 Depósito", "02/01/2026 Abono")):
            pages, layout = fixture()
            pages[1] = pages[1].replace(old, new)
            self.assertFalse(parsed(pages, layout).reconciled)

    def test_date_outside_period_not_redistributed(self):
        pages, layout = fixture()
        pages[1] = pages[1].replace("05/01/2026", "05/02/2026")
        result = parsed(pages, layout)
        self.assertFalse(result.detail_reconciled)
        self.assertEqual(result.entries[1].effective_date.month, 2)

    def test_nonzero_retention_needs_explicit_mapping(self):
        pages, layout = fixture()
        result = parsed(pages, layout.replace("Impuesto retenido $ 0.00", "Impuesto retenido $ 0.10"))
        self.assertFalse(result.reconciled)
        self.assertEqual(result.summary.withholding, D("0.10"))

    def test_missing_summary_account_rates_or_identity_fails_closed(self):
        for field in ("Sofiexpress", "Número de cuenta:", "Tasa de rendimiento anual fija"):
            pages, layout = fixture()
            pages[0] = pages[0].replace(field, "Ausente")
            with self.assertRaises(ReaderError):
                parsed(pages, layout)
        pages, layout = fixture()
        with self.assertRaises(ReaderError):
            parsed(pages, layout.replace("Saldo final", "Sin cierre"))

    def test_pdf_and_opt_in_cli_do_not_print_financial_amounts(self):
        pages, _ = fixture()
        content = synthetic_pdf(pages)
        result = reader_for("didi", "investments").read_reconciled_pdf(content)
        self.assertTrue(result.reconciled)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.pdf"
            path.write_bytes(content)
            output = StringIO()
            with contextlib.redirect_stdout(output):
                main([str(path), "--institution", "didi", "--lane", "debit", "--reconcile"])
            data = json.loads(output.getvalue())
            self.assertTrue(data["reconciled"])
            self.assertEqual(data["entries"], 3)
            self.assertNotIn("131.00", output.getvalue())


if __name__ == "__main__":
    unittest.main()
