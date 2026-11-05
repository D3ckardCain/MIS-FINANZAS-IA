"""Doopla sintético: distinguir efectivo conciliado y cartera pendiente."""
import contextlib
from dataclasses import replace
from datetime import date
from decimal import Decimal as D
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from finanzas.doopla import DooplaReader, review_doopla_documents
from finanzas.readers import ReaderError, main, reader_for
from tests.test_openbank import synthetic_pdf


def statement(modern=False):
    vat_sign = "-" if modern else "+"
    retained = "(-) ISR: $ 0.40\n" if modern else ""
    fee, fee_vat = ("0.50", "0.08") if modern else ("0.00", "0.00")
    final, cash_final, expenses = ("118.70", "19.02", "3.30") if modern else ("120.32", "20.32", "2.00")
    summary = f"""doopla.mx
Período: del 01-Ene-26 al 31-Ene-26
Número de cliente:1111111111
Resumen
Valor de cuenta al inicio de período $ 100.00
Intereses recibidos
(+) Monto: $ 2.00
({vat_sign}) IVA: $ 0.32
(+) Recompensas recibidas: $ 0.00
(+) Depositos realizados: $ 20.00
* Comisiones pagadas
(-) Monto: $ {fee}
(-) IVA: $ {fee_vat}
{retained}(-) Retiros realizados: $ 2.00
Saldo al final de período $ {final}
Efectivo disponible
Saldo al inicio del período $ 0.00
(+) Ingresos $ 32.32
(-) Egresos $ {expenses}
(+) Recompensas $ 0.00
(-) Inversiones realizadas $ 10.00
Efectivo disponible para retiro $ {cash_final}
Movimientos del período
Fecha  Tipo de Movimiento  Alias  Capital  Interés  IVA  Total
02-01-2026  Pago  FICTICIO  $ 10.00  $ 2.00  $ 0.32  $ 12.32
03-01-2026  Depósito  -  -  -  $ 20.00
04-01-2026  Inversión  FICTICIO2  -  -  -  -$ 15.00
05-01-2026  Cancelación  FICTICIO3  -  -  -  $ 5.00
06-01-2026  Retiro  -  -  -  -$ 2.00
"""
    if modern:
        summary += """02-01-2026  IVA  FICTICIO  -  -  -  -$ 0.32
02-01-2026  ISR sobre interes  FICTICIO  -  -  -  -$ 0.40
02-01-2026  Comisión Doopla  FICTICIO  -  -  -  -$ 0.58
"""
    loans = """Inversiones realizadas
Alias  Estátus  No. Pagos  Inversión  Pagos recibidos  Intereses  IVA Intereses  Capital  Cap. Pendiente
FICTICIO  Al corriente  1 de 12  $ 110.00  $ 12.32  $ 2.00  $ 0.32  $ 10.00  $ 100.00
TOTAL  $ 110.00  $ 12.32  $ 2.00  $ 0.32  $ 10.00  $ 100.00
Alias  Estátus  Días de atraso  Acciones de cobranza
OTRO FICTICIO  Vencido  90  Cobranza extra judicial
Comisiones pagadas
"""
    return [summary, loans]


def parsed(pages=None, modern=False, lane="investments"):
    return DooplaReader(lane).read_pages(pages or statement(modern), "synthetic")


class DooplaTests(unittest.TestCase):
    def test_legacy_fully_consistent_synthetic_statement(self):
        result = parsed()
        self.assertTrue(result.reconciled, result.issues)
        self.assertEqual(len(result.entries), 5)
        self.assertEqual(result.summary.interest_vat_sign, 1)
        self.assertIsNone(result.summary.withholding)
        self.assertFalse(result.ready_to_import)

    def test_modern_retention_and_vat_sign_preserved_without_forcing_portfolio(self):
        result = parsed(modern=True)
        self.assertTrue(result.cash_reconciled, result.cash_issues)
        self.assertFalse(result.reconciled)
        self.assertEqual(result.summary.interest_vat_sign, -1)
        self.assertEqual(result.summary.withholding, D("0.40"))
        diff = next(d for d in result.differences if "cambio patrimonial" in d.check)
        self.assertEqual(diff.reported, D("118.70"))
        self.assertEqual(diff.calculated, D("119.02"))

    def test_capital_repayments_are_not_interest(self):
        payment = parsed().entries[0]
        self.assertEqual(payment.principal, D("10.00"))
        self.assertEqual(payment.interest, D("2.00"))
        self.assertEqual(payment.vat, D("0.32"))
        self.assertEqual(payment.total, D("12.32"))

    def test_explicit_zero_retention_differs_from_absent_retention(self):
        pages = statement(modern=True)
        pages[0] = pages[0].replace("(-) ISR: $ 0.40", "(-) ISR: $ 0.00")
        self.assertEqual(parsed(pages).summary.withholding, D("0.00"))
        self.assertIsNone(parsed().summary.withholding)

    def test_net_investment_preserves_cancellation_and_gross_investment(self):
        result = parsed()
        self.assertEqual(result.entries[2].total, D("-15.00"))
        self.assertEqual(result.entries[3].category, "cancellation")
        self.assertEqual(result.summary.net_investments, D("10.00"))
        self.assertEqual(result.summary.deposits, D("20.00"))

    def test_dash_is_absent_component_not_documented_zero(self):
        pages = statement()
        pages[0] = pages[0].replace("$ 2.00  $ 0.32  $ 12.32", "-  -  $ 10.00")
        result = parsed(pages)
        self.assertIsNone(result.entries[0].interest)
        self.assertIsNone(result.entries[0].vat)
        self.assertFalse(result.reconciled)

    def test_one_cent_component_difference_is_retained(self):
        pages = statement()
        pages[0] = pages[0].replace("$ 10.00  $ 2.00", "$ 9.99  $ 2.00")
        result = parsed(pages)
        self.assertTrue(result.cash_reconciled)
        self.assertFalse(result.detail_reconciled)
        diff = next(d for d in result.differences if "Componentes" in d.check)
        self.assertEqual(diff.calculated, D("12.31"))
        self.assertGreater(diff.line, 0)

    def test_cumulative_loan_results_do_not_become_monthly_income(self):
        result = parsed()
        self.assertEqual(len(result.loans), 1)
        self.assertEqual(result.loans[0].pending_principal, D("100.00"))
        self.assertEqual(result.summary.interest, D("2.00"))
        self.assertEqual(result.arrears[0].days, 90)
        self.assertEqual(result.arrears[0].collection_action, "Cobranza extra judicial")

    def test_loan_footer_difference_does_not_replace_rows(self):
        pages = statement()
        pages[1] = pages[1].replace("TOTAL  $ 110.00  $ 12.32", "TOTAL  $ 110.00  $ 12.31")
        result = parsed(pages)
        self.assertTrue(result.cash_reconciled)
        self.assertFalse(result.reconciled)
        self.assertEqual(result.loans[0].received, D("12.32"))
        self.assertEqual(result.loan_totals[1], D("12.31"))

    def test_unknown_category_date_or_sign_fails_closed(self):
        for old, new in (("  Pago  ", "  Ajuste  "), ("02-01-2026", "02/01/2026"),
                         ("02-01-2026", "02-02-2026"), ("-$ 2.00", "$ 2.00")):
            pages = statement()
            pages[0] = pages[0].replace(old, new)
            self.assertFalse(parsed(pages).cash_reconciled)

    def test_absent_identity_summary_or_loan_total_raises(self):
        for old in ("doopla.mx", "Número de cliente:", "Saldo al final de período", "TOTAL"):
            pages = [p.replace(old, "Ausente") for p in statement()]
            with self.assertRaises(ReaderError):
                parsed(pages)

    def test_both_views_share_account_and_rows(self):
        debit, investment = parsed(lane="debit"), parsed()
        self.assertTrue(debit.shared_account)
        self.assertEqual(debit.entries, investment.entries)
        self.assertEqual(debit.account_fingerprint, investment.account_fingerprint)
        self.assertEqual(debit.lane, "debit")

    def test_identical_economic_rows_are_not_deleted_without_operation_id(self):
        pages = statement()
        row = next(l for l in pages[0].splitlines() if l.startswith("02-01-2026"))
        pages[0] += row + "\n"
        result = parsed(pages)
        self.assertEqual(len(result.entries), 6)
        self.assertFalse(result.cash_reconciled)

    def test_coverage_deduplicates_only_exact_document_and_checks_cash(self):
        first = parsed()
        second = replace(first, document_id="second", period_start=date(2026,2,1), period_end=date(2026,2,28),
                         summary=replace(first.summary, initial=first.summary.final))
        review = review_doopla_documents([first, first, second])
        self.assertEqual(len(review.coverage.duplicate_documents), 1)
        self.assertEqual(review.cash_continuity_checked, 1)
        self.assertIn("Efectivo final e inicial consecutivos no coinciden", review.issues)
        self.assertTrue(any("repite cifras" in x for x in review.issues))

    def test_pdf_console_opt_in_and_default_output_hide_financial_values(self):
        content = synthetic_pdf(statement())
        result = reader_for("doopla", "investments").read_reconciled_pdf(content)
        self.assertTrue(result.reconciled, result.issues)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.pdf"
            path.write_bytes(content)
            out = StringIO()
            with contextlib.redirect_stdout(out):
                main([str(path), "--institution", "doopla", "--lane", "debit", "--reconcile"])
            data = json.loads(out.getvalue())
            self.assertTrue(data["reconciled"])
            self.assertEqual(data["entries"], 5)
            self.assertTrue(data["cash_reconciled"])
            self.assertNotIn("120.32", out.getvalue())


if __name__ == "__main__":
    unittest.main()
