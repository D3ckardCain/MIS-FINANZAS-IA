"""Capturas y operaciones ficticias; control de unidades, precisión y duplicados."""
from dataclasses import replace
from decimal import Decimal as D
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from finanzas.crypto_images import BingXImageReader, PionexImageReader, parse_amount
from finanzas.imaging import LocalOcr, ImageReadError
from finanzas.readers import reader_for, main
from tests.test_images import picture, evidence, FixedEngine


def spot(platform="BingX", **changes):
    values = {"Market": "Spot", "Side": "Buy", "Pair": "BTC/USDT",
              "Order ID": "Order-AbC-001", "Trade ID": "Fill-XyZ-001",
              "Time": "2026-01-05 12:00:00", "Quantity": "0.0025 BTC",
              "Price": "30000.00 USDT", "Fee": "0.03 USDT", "Status": "Filled"}
    values.update(changes)
    return [platform] + [f"{key}: {value}" for key, value in values.items()]


class CryptoImagesTests(unittest.TestCase):
    def test_real_capture_ocr_bingx_and_pionex_pipeline(self):
        for platform, cls in (("BingX", BingXImageReader), ("Pionex", PionexImageReader)):
            with self.subTest(platform=platform):
                data = picture(spot(platform))
                result = cls().read_image(data, engine=LocalOcr(languages="eng"))
                self.assertEqual(result.operation_kind, "spot_buy")
                self.assertEqual(result.field("quantity").value, D("0.0025"))
                self.assertEqual(result.field("quantity").unit, "BTC")
                self.assertEqual(result.field("price").value, D("30000.00"))
                self.assertEqual(result.field("price").unit, "USDT")
                self.assertFalse(result.ready_to_import)

    def test_precision_is_decimal_and_missing_units_are_not_inferred(self):
        result = BingXImageReader().read_evidence(evidence(spot(Quantity="0.123456789012345678901234 BTC", Fee="0.03")))
        self.assertEqual(result.field("quantity").value, D("0.123456789012345678901234"))
        self.assertIsNone(result.field("fee").unit)
        self.assertTrue(result.field("fee").issues)

    def test_supported_decimal_conventions_and_signs(self):
        for text, amount, unit in (
                ("1,234.56 USDT", "1234.56", "USDT"),
                ("1.234,56 USDT", "1234.56", "USDT"),
                ("0,0025 BTC", "0.0025", "BTC"),
                ("−0.03 USDT", "-0.03", "USDT"),
                ("0.00000001 BTC", "0.00000001", "BTC")):
            with self.subTest(text=text):
                self.assertEqual(parse_amount(text), (D(amount), unit))

    def test_ambiguous_separators_require_explicit_convention(self):
        for text in ("1,234 USDT", "1.234 USDT"):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "ambiguo"):
                parse_amount(text)
        self.assertEqual(parse_amount("1,234 USDT", decimal_mode="international"), (D("1234"), "USDT"))
        self.assertEqual(parse_amount("1,234 USDT", decimal_mode="spanish"), (D("1.234"), "USDT"))

    def test_ocr_letter_in_amount_is_not_corrected_to_digit(self):
        result = BingXImageReader().read_evidence(evidence(spot(Price="3O000.00 USDT")))
        self.assertIsNone(result.field("price").value)
        self.assertEqual(result.field("price").raw_value, "3O000.00 USDT")
        self.assertTrue(any("price:" in issue for issue in result.issues))

    def test_missing_fee_is_not_documented_zero(self):
        lines = [line for line in spot() if not line.startswith("Fee:")]
        missing = BingXImageReader().read_evidence(evidence(lines))
        zero = BingXImageReader().read_evidence(evidence(spot(Fee="0.00 USDT")))
        self.assertIsNone(missing.field("fee"))
        self.assertEqual(zero.field("fee").value, D("0"))

    def test_low_confidence_id_cannot_propose_execution_identity(self):
        result = BingXImageReader(account="account_a").read_evidence(evidence(spot(), D("40")))
        self.assertIsNone(result.execution_identity)
        self.assertTrue(result.field("order_id").issues)

    def test_custom_ocr_threshold_is_respected_by_execution_identity(self):
        raw = evidence(spot(), D("89"))
        line = next(line for line in raw.lines if line.text.startswith("Order ID:"))
        raw = replace(raw, issues=("Baja confianza OCR: " + line.id,))
        result = BingXImageReader(account="account_a").read_evidence(raw)
        self.assertIsNone(result.execution_identity)
        self.assertTrue(result.field("order_id").issues)

    def test_order_id_alone_does_not_identify_a_fill(self):
        lines = [line for line in spot() if not line.startswith("Trade ID:")]
        result = BingXImageReader(account="account_a").read_evidence(evidence(lines))
        self.assertIsNone(result.execution_identity)

    def test_two_photos_same_fill_propose_same_identity_and_other_fill_differs(self):
        reader = BingXImageReader(account="account_a")
        first = reader.read_evidence(evidence(spot()))
        crop = reader.read_evidence(evidence(spot() + ["Cropped photo variant"]))
        second = reader.read_evidence(evidence(spot(**{"Trade ID": "Fill-XyZ-002"})))
        self.assertEqual(first.execution_identity, crop.execution_identity)
        self.assertNotEqual(first.evidence.document_id, crop.evidence.document_id)
        self.assertNotEqual(first.execution_identity, second.execution_identity)
        self.assertEqual(first.field("order_id").value, "Order-AbC-001")

    def test_different_accounts_do_not_collide(self):
        raw = evidence(spot())
        self.assertNotEqual(BingXImageReader(account="a").read_evidence(raw).execution_identity,
                            BingXImageReader(account="b").read_evidence(raw).execution_identity)

    def test_bot_summary_never_becomes_realized_trading_income(self):
        raw = evidence(["Pionex", "Bot ID: bot-001", "Grid Profit: 5.00 USDT", "PnL: 6.00 USDT"])
        result = PionexImageReader().read_evidence(raw)
        self.assertEqual(result.operation_kind, "bot_summary")
        self.assertIsNone(result.field("realized_pnl"))
        self.assertTrue(any("duplicar" in issue for issue in result.issues))

    def test_derivative_contracts_funding_and_pnl_remain_distinct(self):
        raw = evidence(["BingX", "Market: USDT-M Perpetual", "Pair: BTC/USDT", "Contracts: 2 contracts",
                        "Realized PnL: -3.00 USDT", "Unrealized PnL: 8.00 USDT", "Funding Fee: -0.02 USDT"])
        result = BingXImageReader().read_evidence(raw)
        self.assertEqual(result.operation_kind, "derivative")
        self.assertEqual(result.field("contracts").unit, "CONTRACTS")
        self.assertEqual(result.field("realized_pnl").value, D("-3"))
        self.assertEqual(result.field("unrealized_pnl").value, D("8"))
        self.assertEqual(result.field("funding").value, D("-0.02"))
        self.assertFalse(result.ready_to_import)

    def test_yield_does_not_become_spot_sale(self):
        result = PionexImageReader().read_evidence(evidence(["Pionex", "Interest: 0.25 USDT"]))
        self.assertEqual(result.operation_kind, "yield")

    def test_timezone_is_not_inferred_from_user_location(self):
        raw = evidence(spot())
        unknown = BingXImageReader().read_evidence(raw)
        explicit = BingXImageReader(timezone="UTC").read_evidence(raw)
        self.assertIsNone(unknown.timezone)
        self.assertEqual(explicit.timezone, "UTC")
        self.assertEqual(explicit.field("time").value, "2026-01-05 12:00:00")

    def test_fields_on_separate_lines_preserve_both_source_locations(self):
        result = BingXImageReader().read_evidence(evidence(["BingX", "Quantity", "0.0025 BTC", "Price: 30000 USDT"]))
        self.assertEqual(result.field("quantity").value, D("0.0025"))
        self.assertEqual(len(result.field("quantity").source_lines), 2)

    def test_multiple_values_are_not_silently_replaced(self):
        result = BingXImageReader().read_evidence(evidence(spot() + ["Quantity: 0.003 BTC"]))
        self.assertIsNone(result.field("quantity"))
        self.assertTrue(any("Campo repetido: quantity" in issue for issue in result.issues))

    def test_unit_mismatch_and_unknown_state_require_review(self):
        raw = evidence(["BingX", "Fee (USDT): 0.03 BTC", "Status: Canceled", "Market: Spot", "Side: Buy"])
        result = BingXImageReader().read_evidence(raw)
        self.assertIsNone(result.field("fee").value)
        self.assertTrue(any("Estado de ejecución" in issue for issue in result.issues))

    def test_other_platform_is_rejected_cropped_brand_requires_confirmation(self):
        with self.assertRaises(ImageReadError):
            BingXImageReader().read_evidence(evidence(spot("Pionex")))
        result = BingXImageReader().read_evidence(evidence(spot()[1:]))
        self.assertTrue(any("Marca de plataforma" in issue for issue in result.issues))

    def test_registry_routes_crypto_to_images_and_debit_does_not_apply(self):
        for key in ("bingx", "pionex"):
            with self.subTest(platform=key):
                result = reader_for(key, "investments").read_document(
                    b"image", engine=FixedEngine(evidence(spot(key))))
                self.assertEqual(result.platform, key)
                self.assertFalse(result.ready_to_import)
                with self.assertRaises(ValueError):
                    reader_for(key, "debit")

    def test_crypto_capture_cli_default_output_omits_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.png"
            path.write_bytes(picture(spot()))
            output = StringIO()
            with contextlib.redirect_stdout(output):
                status = main([str(path), "--institution", "bingx", "--lane", "investments", "--ocr-language", "eng"])
            result = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertEqual(result["operation_kind"], "spot_buy")
            self.assertNotIn("30000", output.getvalue())
            self.assertFalse(result["ready_to_import"])


if __name__ == "__main__":
    unittest.main()
