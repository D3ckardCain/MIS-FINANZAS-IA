"""Fuentes sintéticas de fondos MXN y acciones USD, sin datos personales."""
from decimal import Decimal as D
from datetime import date
import unittest

from finanzas.fintual import FintualInvestmentReader, money
from finanzas.alpaca import AlpacaReader
from finanzas.readers import ReaderError, reader_for
from tests.test_openbank import synthetic_pdf


def fund_pages():
    return ["""Fintual
No. cuenta: FINTUAL000001-1
Período del: 1/Ene/2026 al 31/Ene/2026
Cartera período actual
Fondo  Títulos  Costo promedio  Precio  Valuación  Variación  %
FONDO FICTICIO  11  $9.909091  $10.090909  $111.00  $11.00  100.0
Posición de Valores: $111.00
Efectivo: $1.00
Pendiente por liquidar: $0.00
Posición total: $112.00
La moneda utilizada en este documento es en pesos mexicanos.
Cartera período anterior
Fondo  Títulos  Precio  Valuación  %
FONDO FICTICIO  10  $10.000000  $100.00  100.0
Posición de Valores: $100.00
Efectivo: $0.00
Pendiente por liquidar: $0.00
Posición total: $100.00
""", """RESUMEN DE MOVIMIENTOS
Total retiros  Total depósitos
$0,00  $10.00
MOVIMIENTOS DEL PERÍODO
Fecha  Descripción  Detalle  Monto  Comisión  IVA
03/ene/2026  Nos depositaste  $10.00  $0.00  $0.00
Fondo: FONDO-FICTICIO
03/ene/2026  Compra  Precio: $9.00  $9.00  $0.00  $0.00
Fecha de liquidación:
03/ene/2026
""", """RENDIMIENTO NETO DEL PORTAFOLIO
Enero 2026 (período actual)  2.00%
Diciembre 2025  NaN%
Total de ISR retenido: $0.07
Total de Comisiones: $0.00
"""]


def alpaca_pages():
    first = ["Alpaca Securities Monthly Statement Period: JANUARY - 2026", "Account No: SYNTHETIC-001"]
    def columns(left, right=""):
        return left.ljust(100) + right
    first.append(columns("Cash Summary This Period Year to Date", "Realized Gain/Loss from Sales This Period Year to Date"))
    left = ["Beginning Balance $100.00 $100.00", "Addition $2.00 $2.00", "Subtraction $1.00 $1.00", "Trade Transaction -$100.00 -$100.00", "Cost and Fees $0.00 $0.00", "Ending Value $1.00 $1.00", "Account Summary", "Long $111.00", "Short $0.00", "Options $0.00", "Fixed Income $0.00", "Total Market Value $112.00", "Income Summary This Period Year to Date", "Dividend $2.00 $2.00", "Interest $0.00 $0.00"]
    right = ["Short Term", "Gain $0.00 $0.00", "Loss $0.00 $0.00", "Net $0.00 $0.00", "Long Term", "Gain $0.00 $0.00", "Loss $0.00 $0.00", "Net $0.00 $0.00"]
    first.extend(columns(l, right[i] if i < len(right) else "") for i,l in enumerate(left))
    return ["\n".join(first), """Holdings
Symbol  Description  Quantity  Market Price  Market Value  Cost Price  Unrealized  TD Cost Basis
*Cash  USD  $ --  $ --  $1.00  $ --  $ --  $ --
XYZ  SYNTHETIC ETF  1.000000000  $111.00  $111.00  $100.00  $11.00  $100.00
""", """Income
Trade Date  Entry Type  Symbol  Description  Net Amt
01/05/2026  Dividends  XYZ  Cash dividend  $2.00
01/05/2026  Div. Adj(NRA Withheld)  XYZ  Foreign withholding  -$1.00
""", """Fees
Trade Date  Description  Net Amt
No record found.
""", """Transaction
Trade Date  Entry Type  Side  Symbol  Description  Quantity  Price  Amount  Commission
01/03/2026  Trade Entry  buy  XYZ  1.000000000  $100.00  -$100.00  $0.00
"""]


class FintualTests(unittest.TestCase):
    def test_fund_value_flows_and_informative_tax_do_not_duplicate_tax(self):
        result = FintualInvestmentReader().read_pages(fund_pages(), "synthetic")
        self.assertTrue(result.reconciled, (result.issues, result.detail_issues))
        self.assertEqual(result.summary.withholding_reported, D("0.07"))
        self.assertEqual(result.summary.final_cash, D("1.00"))
        self.assertEqual(result.summary.net_return_reported, D("2.00"))
        self.assertEqual(result.final_positions[0].variation_reported, D("11.00"))
        self.assertEqual(result.summary.deposits, D("10.00"))
        self.assertFalse(result.ready_to_import)

    def test_position_source_line_is_from_original_page(self):
        pages = fund_pages()
        result = FintualInvestmentReader().read_pages(pages, "synthetic")
        for p in result.initial_positions + result.final_positions:
            self.assertIn("FONDO FICTICIO", pages[p.page-1].splitlines()[p.line-1])

    def test_comma_decimal_zero_not_thousand_separator(self):
        self.assertEqual(money("$0,00"), D("0.00"))
        self.assertEqual(money("$1,000.00"), D("1000.00"))

    def test_one_cent_difference_is_not_fixed(self):
        pages = fund_pages()
        pages[0] = pages[0].replace("Posición total: $112.00", "Posición total: $111.99")
        r = FintualInvestmentReader().read_pages(pages, "synthetic")
        self.assertFalse(r.reconciled)
        self.assertTrue(r.detail_reconciled)
        self.assertEqual(r.differences[0].reported, D("111.99"))
        self.assertEqual(r.differences[0].calculated, D("112.00"))

    def test_empty_position_explicit_and_nan_return_remain_distinct(self):
        pages = fund_pages()
        pages[0] = pages[0].replace("FONDO FICTICIO  11  $9.909091  $10.090909  $111.00  $11.00  100.0", "No hay activos en el período actual")
        pages[2] = pages[2].replace("2.00%", "NaN%")
        r = FintualInvestmentReader().read_pages(pages, "synthetic")
        self.assertEqual(r.final_positions, ())
        self.assertIsNone(r.summary.net_return_reported)
        self.assertFalse(r.reconciled)

    def test_unknown_cash_movement_fails_closed(self):
        pages = fund_pages()
        pages[1] = pages[1].replace("Nos depositaste", "Ajuste")
        self.assertFalse(FintualInvestmentReader().read_pages(pages, "synthetic").detail_reconciled)

    def test_missing_identity_currency_or_summary_raises(self):
        for marker in ("Fintual", "No. cuenta:", "pesos mexicanos", "Total de ISR retenido:"):
            with self.assertRaises(ReaderError):
                FintualInvestmentReader().read_pages([p.replace(marker, "Ausente") for p in fund_pages()], "synthetic")

    def test_fintual_pdf_catalog_and_lane_restriction(self):
        result = reader_for("fintual", "investments").read_reconciled_pdf(synthetic_pdf(fund_pages()))
        self.assertTrue(result.reconciled, result.issues)
        with self.assertRaises(ReaderError):
            reader_for("fintual", "debit").read_reconciled_pdf(synthetic_pdf(fund_pages()))


class AlpacaTests(unittest.TestCase):
    def test_usd_income_foreign_tax_and_buy_are_separate(self):
        r = AlpacaReader().read_pages(alpaca_pages(), "synthetic")
        self.assertTrue(r.reconciled, (r.issues,r.detail_issues))
        self.assertEqual(r.summary.unit, "USD")
        self.assertEqual([e.category for e in r.entries], ["dividend", "foreign_withholding", "buy"])
        self.assertEqual(r.entries[0].effective_date, date(2026,1,5))
        self.assertEqual(r.entries[-1].quantity, D("1.000000000"))
        self.assertEqual(r.entries[-1].amount, D("-100.00"))
        self.assertFalse(r.ready_to_import)

    def test_year_to_date_is_not_another_monthly_income(self):
        pages = alpaca_pages()
        pages[0] = pages[0].replace("Dividend $2.00 $2.00", "Dividend $2.00 $99.00")
        r = AlpacaReader().read_pages(pages, "synthetic")
        self.assertEqual(r.summary.income[0].year_to_date, D("99.00"))
        self.assertEqual(r.entries[0].amount, D("2.00"))
        self.assertTrue(r.reconciled)

    def test_printed_dash_does_not_become_zero(self):
        pages = alpaca_pages()
        pages[0] = pages[0].replace("Beginning Balance $100.00", "Beginning Balance $ --   ")
        r = AlpacaReader().read_pages(pages, "synthetic")
        self.assertIsNone(r.summary.cash_value("Beginning Balance"))
        self.assertFalse(r.reconciled)

    def test_memopost_quantity_and_wrapped_reference_are_not_cash_flows(self):
        pages = alpaca_pages()
        pages[-1] += """01/03/2026  Memopost  INSTANTUSD  type: memopost, transfer_id: 00000000-0000-0000-  -100.00  $ --  $ --  $ --
0000-000000000000
01/03/2026  Memopost  INSTANTUSD  type: memopost  100.00  $ --  $ --  $ --
"""
        r = AlpacaReader().read_pages(pages, "synthetic")
        memos = [e for e in r.entries if e.category == "memo"]
        self.assertEqual(len(memos),2)
        self.assertTrue(all(e.amount is None for e in memos))
        self.assertTrue(r.detail_reconciled, r.detail_issues)

    def test_missing_external_funding_is_pending_not_an_invented_entry(self):
        pages = alpaca_pages()
        pages[0] = pages[0].replace("Addition $2.00", "Addition $12.00")
        r = AlpacaReader().read_pages(pages, "synthetic")
        self.assertTrue(any("desglose" in x for x in r.issues))
        self.assertEqual(len(r.entries),3)

    def test_unknown_type_sign_date_or_currency_rejected(self):
        for old,new in (("Trade Entry", "Other Entry"),("-$100.00", "$100.00"),("01/03/2026", "03/01/2026")):
            pages = alpaca_pages()
            pages[-1] = pages[-1].replace(old,new)
            self.assertFalse(AlpacaReader().read_pages(pages,"synthetic").detail_reconciled)
        pages = alpaca_pages()
        pages[1] = pages[1].replace("USD", "MXN")
        with self.assertRaises(ReaderError):
            AlpacaReader().read_pages(pages,"synthetic")

    def test_views_share_evidence_and_catalog_pdf_reader(self):
        content = synthetic_pdf(alpaca_pages())
        debit = reader_for("alpaca", "debit").read_reconciled_pdf(content)
        investment = reader_for("alpaca", "investments").read_reconciled_pdf(content)
        self.assertEqual(debit.entries,investment.entries)
        self.assertEqual(debit.account_fingerprint,investment.account_fingerprint)
        self.assertTrue(investment.reconciled, (investment.issues,investment.detail_issues))

    def test_missing_required_section_or_identity_fails_closed(self):
        for marker in ("Alpaca", "Account No:", "Holdings", "Fees"):
            pages = [p.replace(marker,"Ausente") for p in alpaca_pages()]
            with self.assertRaises(ReaderError):
                AlpacaReader().read_pages(pages,"synthetic")


if __name__ == "__main__":
    unittest.main()
