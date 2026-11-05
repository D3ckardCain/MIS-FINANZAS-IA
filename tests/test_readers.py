"""Catálogo documental: datos ficticios y rechazo de atribuciones automáticas."""
import contextlib
from datetime import date
from decimal import Decimal
from io import StringIO
import unittest

from finanzas.readers import (
    PROFILES, ReaderError, StatementReader, available_readers, reader_for,
    periods, parse_date, main,
)
from tests.test_openbank import synthetic_pdf


# Marcadores institucionales públicos; ningún estado ni dato del titular.
IDENTITY = {
    "alpaca": "Alpaca Securities",
    "bancoppel": "BanCoppel",
    "didi": "J.P. Sofiexpress",
    "cetesdirecto": "cetesdirecto.com",
    "doopla": "doopla.mx",
    "fintual": "Fintual",
    "fondeadora": "apoyomultiple.com",
    "hey": "Hey, Banco",
    "kapital": "Kapital",
    "nu": "Cuenta Nu",
    "supertasas": "SuperTasas.com",
    "plata": "Banco Plata",
    "mifel": "Banca Mifel",
}


def sample(profile, lane, *, period="Periodo 01/01/2026 al 31/01/2026"):
    headings = profile.debit_start if lane == "debit" else profile.investment_start
    text = IDENTITY[profile.key] + "\n" + period
    if headings:
        text += "\n" + headings[0] + "\nSaldo inicial      $ 100.00\n"
        text += "02/01/2026      Pago de intereses      $ 1.00\n"
        text += "ISR retenido      $ 0.00\nTasa anual      7.50%\n"
        text += "Saldo final      $ 101.00\n"
    return text


class ReaderCatalogTests(unittest.TestCase):
    def test_all_14_institutions_have_two_independent_reader_instances(self):
        self.assertEqual(len(PROFILES), 14)
        self.assertEqual(len(available_readers()), 30)
        for profile in PROFILES:
            with self.subTest(institution=profile.key):
                debit = reader_for(profile.key, "debit")
                investments = reader_for(profile.key, "investments")
                self.assertIsNot(debit, investments)
                self.assertNotEqual(debit.lane, investments.lane)

    def test_each_documentary_view_reads_its_own_section_or_reports_absence(self):
        for profile in PROFILES:
            if profile.key == "openbank":
                continue
            for lane in ("debit", "investments"):
                with self.subTest(institution=profile.key, lane=lane):
                    result = reader_for(profile.key, lane).read_pages([sample(profile, lane)], "synthetic")
                    expected = bool(profile.debit_start if lane == "debit" else profile.investment_start)
                    self.assertEqual(result.status, "review_required" if expected else "section_missing")
                    self.assertFalse(result.ready_to_import)
                    self.assertEqual(bool(result.observations), expected)
                    self.assertEqual(result.periods, ((date(2026, 1, 1), date(2026, 1, 31)),))

    def test_each_documentary_reader_extracts_pdf_offline(self):
        for profile in PROFILES:
            if profile.key == "openbank":
                continue
            for lane in ("debit", "investments"):
                with self.subTest(institution=profile.key, lane=lane):
                    pdf = synthetic_pdf([sample(profile, lane)])
                    result = reader_for(profile.key, lane).read_pdf(pdf)
                    self.assertEqual(result.institution, profile.key)
                    self.assertFalse(result.ready_to_import)
                    self.assertEqual(len(result.document_id), 64)

    def test_missing_section_never_means_zero_or_inexistent_product(self):
        profile = next(p for p in PROFILES if p.key == "fondeadora")
        result = reader_for("fondeadora", "investments").read_pages([sample(profile, "debit")], "synthetic")
        self.assertEqual(result.status, "section_missing")
        self.assertEqual(result.observations, ())
        self.assertTrue(any("no significa saldo cero" in issue for issue in result.issues))

    def test_cetes_lending_and_funds_do_not_invent_a_debit_bank_account(self):
        for key in ("cetesdirecto", "doopla", "fintual"):
            profile = next(p for p in PROFILES if p.key == key)
            result = reader_for(key, "debit").read_pages([sample(profile, "investments")], "synthetic")
            self.assertEqual(result.status, "section_missing")

    def test_other_institution_rejected_even_if_transfer_mentions_its_name(self):
        text = "BanCoppel\nPeriodo 01/01/2026 al 31/01/2026\nDetalle de movimientos\nRetiro Doopla 100.00"
        with self.assertRaises(ReaderError):
            reader_for("doopla", "investments").read_pages([text], "synthetic")

    def test_shared_account_observations_have_same_ids_in_both_views(self):
        for key in ("didi", "mifel", "supertasas"):
            profile = next(p for p in PROFILES if p.key == key)
            shared = next(h for h in profile.debit_start if h in profile.investment_start)
            text = IDENTITY[key] + "\nPeriodo 01/01/2026 al 31/01/2026\n" + shared + "\nSaldo final      100.00"
            debit = reader_for(key, "debit").read_pages([text], "synthetic")
            investments = reader_for(key, "investments").read_pages([text], "synthetic")
            self.assertTrue(debit.shared_account and investments.shared_account)
            self.assertEqual([o.id for o in debit.observations], [o.id for o in investments.observations])

    def test_distinct_sections_do_not_leak_between_plata_views(self):
        text = """Banco Plata
Periodo 01/01/2026 al 31/01/2026
Plata Cuenta
Saldo anterior      10.00
Ahorro Flexible
Saldo anterior      100.00
Movimientos de Plata Cuenta
02/01/2026      Cashback      1.00
Movimientos de Ahorro Flexible
02/01/2026      Rendimientos      2.00
"""
        debit = reader_for("plata", "debit").read_pages([text], "synthetic")
        investments = reader_for("plata", "investments").read_pages([text], "synthetic")
        self.assertTrue(any(o.kind == "cashback" for o in debit.observations))
        self.assertFalse(any(o.kind == "cashback" for o in investments.observations))
        self.assertFalse(any(Decimal("100") in o.numbers for o in debit.observations))

    def test_nu_freeze_is_not_classified_as_new_interest(self):
        text = """Cuenta Nu
Periodo: del 01 al 31 ene 2026
Detalle de movimientos de tus cajitas
02 ENE 2026      Congelaste saldo      -100.00
03 ENE 2026      Descongelamos saldo      +100.00
"""
        result = reader_for("nu", "investments").read_pages([text], "synthetic")
        self.assertEqual([o.kind for o in result.observations if o.numbers], ["freeze", "freeze"])

    def test_repeated_document_same_locators_same_ids_different_documents_distinct(self):
        profile = next(p for p in PROFILES if p.key == "mifel")
        text = sample(profile, "investments")
        reader = reader_for("mifel", "investments")
        a = reader.read_pages([text], "a")
        self.assertEqual(a.observations, reader.read_pages([text], "a").observations)
        self.assertNotEqual(a.observations[0].id, reader.read_pages([text], "b").observations[0].id)

    def test_values_remain_decimal_and_zero_is_not_assumed_if_absent(self):
        profile = next(p for p in PROFILES if p.key == "mifel")
        text = sample(profile, "investments")
        result = reader_for("mifel", "investments").read_pages([text], "synthetic")
        taxes = [o for o in result.observations if o.kind == "tax"]
        self.assertEqual(taxes[0].numbers, (Decimal("0.00"),))
        missing = reader_for("mifel", "investments").read_pages(
            [text.replace("ISR retenido      $ 0.00\n", "")], "synthetic")
        self.assertFalse(any(o.kind == "tax" for o in missing.observations))
        self.assertFalse(missing.ready_to_import)

    def test_cumulative_tax_distinct_from_period_tax(self):
        text = """cetesdirecto.com
Periodo 01/01/2026 al 31/01/2026
Resumen del portafolio
ISR del período      1.00
ISR acumulado del ejercicio fiscal      3.00
"""
        result = reader_for("cetesdirecto", "investments").read_pages([text], "synthetic")
        self.assertIn("tax", [o.kind for o in result.observations])
        self.assertIn("tax_cumulative", [o.kind for o in result.observations])

    def test_forecast_stays_unconfirmed(self):
        text = """Kapital
Período DEL 2026-01-01 AL 2026-01-31
Inversión a plazo
Interés neto estimado      10.00
Capital al vencimiento      110.00
"""
        result = reader_for("kapital", "investments").read_pages([text], "synthetic")
        self.assertFalse(result.ready_to_import)
        self.assertEqual([o.kind for o in result.observations if o.numbers], ["forecast", "forecast"])

    def test_dates_come_from_contents_all_observed_styles(self):
        expected = (date(2026, 1, 1), date(2026, 1, 31))
        for text in (
            "Periodo 01/01/2026 al 31/01/2026", "Periodo 01/01/26 - 31/01/26",
            "Periodo DEL 2026-01-01 AL 2026-01-31", "Periodo del 01-Ene-26 al 31-Ene-26",
            "Periodo: del 01 al 31 ene 2026", "del 01 al 31 de ENERO 2026",
            "Periodo: 01 al 31 de Enero del 2026", "Enero 01 - enero 31, 2026",
            "Periodo 01 ene 2026 — 31 ene 2026", "01/ENE./2026 AL 31/ENE./2026",
        ):
            with self.subTest(text=text):
                self.assertEqual(periods(text), (expected,))

    def test_invalid_or_reversed_period_rejected(self):
        for text in ("31/02/2026 al 31/03/2026", "31/01/2026 al 01/01/2026"):
            with self.subTest(text=text), self.assertRaises(ReaderError):
                periods(text)

    def test_contract_numbers_do_not_become_periods(self):
        self.assertEqual(periods("Periodo DEL 2026-01-01 AL 2026-01-31 10,000.00 2025-11-03 2026-11-02"),
                         ((date(2026, 1, 1), date(2026, 1, 31)),))

    def test_no_period_never_falls_back_to_filename(self):
        profile = next(p for p in PROFILES if p.key == "mifel")
        text = sample(profile, "investments", period="Sin período")
        result = reader_for("mifel", "investments").read_pages([text], "nombre_enero_2026")
        self.assertEqual(result.periods, ())
        self.assertFalse(result.ready_to_import)

    def test_cli_list_is_local_and_has_30_entries(self):
        import json
        output = StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["--list"]), 0)
        self.assertEqual(len(json.loads(output.getvalue())), 30)

    def test_doopla_components_and_withholding_remain_separate_observations(self):
        text = """doopla.mx
Período: del 01-Ene-26 al 31-Ene-26
Movimientos del período
Fecha      Tipo de Movimiento      Alias      Capital      Interés      IVA      Total
02-01-2026      Pago recibido      PRESTAMO_FICTICIO      100.00      10.00      1.60      111.60
02-01-2026      ISR sobre interes      PRESTAMO_FICTICIO      -      -      -      -$ 3.50
"""
        result = reader_for("doopla", "investments").read_pages([text], "synthetic")
        payment = next(o for o in result.observations if Decimal("111.60") in o.numbers)
        self.assertEqual(payment.numbers, (Decimal("100.00"), Decimal("10.00"), Decimal("1.60"), Decimal("111.60")))
        tax = next(o for o in result.observations if o.kind == "tax" and o.numbers)
        self.assertEqual(tax.numbers, (Decimal("-3.50"),))
        self.assertFalse(result.ready_to_import)

    def test_fintual_share_price_precision_does_not_become_interest_income(self):
        text = """Fintual
Período del: 1/Ene/2026 al 31/Ene/2026
MOVIMIENTOS DEL PERÍODO
02/ene/2026      Venta      Precio: $1.840082      Monto $100.00
RENDIMIENTO NETO DEL PORTAFOLIO
Enero 2026      0.91%
"""
        result = reader_for("fintual", "investments").read_pages([text], "synthetic")
        sale = next(o for o in result.observations if Decimal("1.840082") in o.numbers)
        self.assertEqual(sale.kind, "movement")
        self.assertEqual(sale.numbers, (Decimal("1.840082"), Decimal("100.00")))
        self.assertFalse(result.ready_to_import)

    def test_bancoppel_reverse_order_keeps_provenance_without_inventing_dates(self):
        text = """BanCoppel
Período: 12/DIC./2025 AL 11/ENE./2026
Detalle de Movimientos
Fecha      Conceptos      Retiros      Depósitos      Saldo
01/10      ABONO SPEI      100.00      100.00
12/20      CARGO SPEI      50.00      0.00
"""
        result = reader_for("bancoppel", "debit").read_pages([text], "synthetic")
        rows = [o for o in result.observations if o.numbers]
        self.assertTrue(rows[0].cells[0].startswith("01/10"))
        self.assertTrue(rows[1].cells[0].startswith("12/20"))
        self.assertLess(rows[0].line, rows[1].line)
        self.assertEqual(result.periods, ((date(2025, 12, 12), date(2026, 1, 11)),))

    def test_corrupt_pdf_never_becomes_empty_account(self):
        for key in ("nu", "openbank"):
            with self.subTest(key=key), self.assertRaises(ReaderError):
                reader_for(key, "investments").read_pdf(b"no es un pdf")

    def test_unknown_institution_or_lane_rejected(self):
        for key, lane in (("unknown", "debit"), ("nu", "credit_card")):
            with self.subTest(key=key, lane=lane), self.assertRaises(ReaderError):
                reader_for(key, lane)


if __name__ == "__main__":
    unittest.main()
