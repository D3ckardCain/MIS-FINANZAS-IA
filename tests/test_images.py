"""Imágenes sintéticas; OCR real sin red ni documentos privados."""
from dataclasses import replace
from decimal import Decimal as D
from hashlib import sha256
from io import BytesIO, StringIO
import contextlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont

from finanzas.imaging import LocalOcr, ImageReadError, ImageEvidence, OcrLine, parse_tsv
from finanzas.openbank import OpenbankDebitReader, OpenbankInvestmentReader
from finanzas.readers import PROFILES, reader_for, main


def picture(lines, *, image_format="PNG"):
    image = Image.new("RGB", (1200, max(200, 80 + len(lines) * 52)), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 32)
    except OSError:
        font = ImageFont.load_default(size=32)
    for index, line in enumerate(lines):
        draw.text((40, 30 + index * 52), line, font=font, fill="black")
    data = BytesIO()
    image.save(data, format=image_format)
    return data.getvalue()


def evidence(lines, confidence=D("99")):
    identifier = sha256("\n".join(lines).encode()).hexdigest()
    return ImageEvidence(identifier, (1200, 800), (1200, 800), False, "PNG", "eng",
                         tuple(OcrLine(f"{identifier}-{i}", line, confidence, (0, i * 30, 500, 30))
                               for i, line in enumerate(lines)), ())


class FixedEngine:
    def __init__(self, result):
        self.result = result

    def read(self, content):
        return self.result


class ImageTests(unittest.TestCase):
    def test_real_ocr_supported_formats_preserve_hash_text_and_coordinates(self):
        for image_format in ("PNG", "JPEG", "WEBP", "TIFF", "BMP"):
            with self.subTest(format=image_format):
                data = picture(["BANK TEST", "Balance 123.45"], image_format=image_format)
                result = LocalOcr(languages="eng").read(data)
                self.assertEqual(result.document_id, sha256(data).hexdigest())
                self.assertIn("123.45", " ".join(line.text for line in result.lines))
                self.assertTrue(all(line.box[2] > 0 and line.box[3] > 0 for line in result.lines))
                self.assertEqual(result.original_size, result.working_size)
                self.assertEqual(result.image_format, image_format)

    def test_blank_image_is_unreadable_evidence_not_zero_balance(self):
        result = LocalOcr(languages="eng").read(picture([]))
        self.assertEqual(result.lines, ())
        self.assertTrue(any("No se reconoció" in issue for issue in result.issues))

    def test_low_confidence_flags_the_line_without_correcting_digits(self):
        tsv = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        tsv += "5\t1\t1\t1\t1\t1\t10\t20\t50\t15\t40\t1O.OO\n"
        lines, issues = parse_tsv(tsv, "image")
        self.assertEqual(lines[0].text, "1O.OO")
        self.assertEqual(lines[0].confidence, D("40"))
        self.assertTrue(issues)

    def test_invalid_tsv_and_corrupt_image_rejected(self):
        with self.assertRaises(ImageReadError):
            parse_tsv("not a TSV", "image")
        with self.assertRaises(ImageReadError):
            LocalOcr().read(b"not an image")

    def test_all_30_statement_views_expose_image_preview_without_import(self):
        for profile in PROFILES:
            for lane in ("debit", "investments"):
                with self.subTest(institution=profile.key, lane=lane):
                    raw = evidence(["unknown bank cropped image", "Balance: 123.45"])
                    result = reader_for(profile.key, lane).read_image(b"image", engine=FixedEngine(raw))
                    self.assertEqual(result.evidence, raw)
                    self.assertEqual(result.lane, lane)
                    self.assertFalse(result.identity_detected)
                    self.assertFalse(result.ready_to_import)

    def test_direct_openbank_classes_accept_image_but_do_not_inherit_pdf_reconciliation(self):
        raw = evidence(["Openbank", "Apartado Open", "Saldo final 100.00"])
        for cls in (OpenbankDebitReader, OpenbankInvestmentReader):
            result = cls().read_image(b"image", engine=FixedEngine(raw))
            self.assertTrue(result.identity_detected)
            self.assertIsNone(result.document_preview)
            self.assertFalse(result.ready_to_import)

    def test_ocr_malformed_date_retains_evidence_for_review(self):
        raw = evidence(["Cuenta Nu", "Periodo: del 31 al 31 feb 2026", "Detalle de movimientos de tus cajitas"])
        result = reader_for("nu", "investments").read_image(b"image", engine=FixedEngine(raw))
        self.assertEqual(result.evidence, raw)
        self.assertIsNone(result.document_preview)
        self.assertTrue(any("incompatible" in issue for issue in result.issues))

    def test_missing_engine_and_missing_language_raise_actionable_errors(self):
        data = picture(["TEST"])
        with patch("finanzas.imaging.shutil.which", return_value=None):
            with self.assertRaisesRegex(ImageReadError, "Tesseract"):
                LocalOcr().read(data)
        with self.assertRaisesRegex(ImageReadError, "Idioma"):
            LocalOcr(languages="language_not_installed").read(data)

    def test_timeout_does_not_create_partial_financial_record(self):
        langs = subprocess.CompletedProcess([], 0, "List of available languages:\neng\n", "")
        with patch("finanzas.imaging.shutil.which", return_value="tesseract"), patch(
                "finanzas.imaging.subprocess.run", side_effect=[langs, subprocess.TimeoutExpired("tesseract", 1)]):
            with self.assertRaisesRegex(ImageReadError, "agotó"):
                LocalOcr(timeout=1).read(picture(["TEST"]))

    def test_multiframe_tiff_requires_separate_pages(self):
        data = BytesIO()
        Image.new("RGB", (50, 50), "white").save(data, format="TIFF", save_all=True,
                                               append_images=[Image.new("RGB", (50, 50), "black")])
        with self.assertRaisesRegex(ImageReadError, "varias imágenes"):
            LocalOcr().read(data.getvalue())

    def test_exif_orientation_recorded_with_coordinate_space(self):
        data = BytesIO()
        exif = Image.Exif()
        exif[274] = 6
        Image.new("RGB", (300, 200), "white").save(data, format="JPEG", exif=exif)
        result = LocalOcr(languages="eng").read(data.getvalue())
        self.assertTrue(result.orientation_applied)
        self.assertEqual(result.original_size, (300, 200))
        self.assertEqual(result.working_size, (200, 300))

    def test_cli_image_content_is_detected_without_trusting_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "picture.dat"
            path.write_bytes(picture(["Banca Mifel", "Saldo final 123.45"]))
            output = StringIO()
            with contextlib.redirect_stdout(output):
                status = main([str(path), "--institution", "mifel", "--lane", "investments", "--ocr-language", "eng"])
            result = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertEqual(result["source"], "image")
            self.assertFalse(result["ready_to_import"])


if __name__ == "__main__":
    unittest.main()
