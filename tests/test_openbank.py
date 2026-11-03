"""Dos lectores: ejemplos totalmente ficticios con columnas y continuaciones."""
from dataclasses import replace
from decimal import Decimal
from io import BytesIO
import unittest

from finanzas.openbank import (
    FormatError, OpenbankDebitReader, OpenbankInvestmentReader, transfer_candidates,
)


def table_row(day, concept, deposit="", withdrawal="", balance=""):
    return f"{day:<12}{concept:<53}{deposit:<20}{withdrawal:<20}{balance}"


HEADER = table_row("Fecha", "Concepto", "Depósito", "Retiro", "Saldo MXN")


def page(title, rows, *, initial=None, deposits="0.00", other="0.00",
         final="0.00", interest="0.00", withholding="0.00", fees="0.00"):
    lines = [title]
    if initial is not None:
        lines += [
            "Periodo 01/01/26 - 31/01/26", "Interés aplicable o rendimientos $ " + interest,
            "Comisiones cobradas $ " + fees, "Resumen informativo MXN",
            "Saldo inicial $ " + initial, "Depósitos $ " + deposits,
            "Retiro en efectivo $ 0.00", "Otros cargos $ " + other,
            "Saldo final $ " + final, "Impuestos retenidos $ " + withholding,
            "Tasa bruta de interés anual 10.00 %",
        ]
    return "\n".join(lines + ["Detalle de tus transacciones", HEADER, *rows, "Fecha Comisiones"])


def pages():
    return [
        page("Cuenta Débito Open Light", [
            table_row("05/01/26", "Transferencia SPEI recibida", "$ 200.00", "", "$ 210.00"),
            table_row("05/01/26", "Retiro a Apartado Open", "", "$ 200.00", "$ 10.00")],
             initial="10.00", deposits="200.00", other="200.00", final="10.00"),
        page("Apartado Open", [
            table_row("02/01/26", "Abono de intereses", "$ 1.00", "", "$ 101.00"),
            table_row("05/01/26", "Abono desde Cuenta Débito Open Light", "$ 200.00", "", "$ 301.00")],
             initial="100.00", deposits="200.00", final="303.00", interest="3.00"),
        page("Apartado Open", [
            table_row("06/01/26", "Abono de intereses", "$ 2.00", "", "$ 303.00")]),
        "Cuenta Débito Open Light\nComunicados y recomendaciones\nGlosario",
    ]


def synthetic_pdf(text_pages):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter()
    for text in text_pages:
        target = writer.add_blank_page(width=1200, height=800)
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Courier"), NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        })
        target[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        lines = []
        for line in text.splitlines():
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            lines.append("(" + escaped + ") Tj T*")
        stream = DecodedStreamObject()
        stream.set_data(("BT /F1 8 Tf 11 TL 20 780 Td\n" + "\n".join(lines) + "\nET").encode("cp1252"))
        target[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class OpenbankTests(unittest.TestCase):
    def test_independent_readers_separate_sections_and_reconcile(self):
        debit = OpenbankDebitReader().read_pages(pages(), "synthetic")
        investments = OpenbankInvestmentReader().read_pages(pages(), "synthetic")
        self.assertEqual(len(debit.rows), 2)
        self.assertEqual(len(investments.rows), 3)
        self.assertTrue(debit.reconciled)
        self.assertTrue(investments.reconciled)
        self.assertEqual(investments.interest_received, Decimal("3"))
        self.assertEqual(investments.summary.deposits, Decimal("200"))

    def test_continuation_keeps_page_and_line_provenance(self):
        preview = OpenbankInvestmentReader().read_pages(pages(), "synthetic")
        self.assertEqual(preview.rows[-1].page, 3)
        self.assertIn("pagina 3", preview.rows[-1].locator)

    def test_unique_transfer_is_a_proposal_not_a_new_external_contribution(self):
        debit = OpenbankDebitReader().read_pages(pages(), "synthetic")
        investments = OpenbankInvestmentReader().read_pages(pages(), "synthetic")
        self.assertEqual(len(transfer_candidates(debit, investments)), 1)
        self.assertEqual(investments.rows[1].category, "from_debit")

    def test_other_document_does_not_auto_match(self):
        debit = OpenbankDebitReader().read_pages(pages(), "doc-a")
        investments = OpenbankInvestmentReader().read_pages(pages(), "doc-b")
        self.assertEqual(transfer_candidates(debit, investments), ())

    def test_ambiguous_equal_transfers_are_not_linked(self):
        debit = OpenbankDebitReader().read_pages(pages(), "synthetic")
        investments = OpenbankInvestmentReader().read_pages(pages(), "synthetic")
        debit = replace(debit, rows=debit.rows + (debit.rows[-1],))
        self.assertEqual(transfer_candidates(debit, investments), ())

    def test_missing_section_does_not_fallback_to_other_reader(self):
        with self.assertRaises(FormatError):
            OpenbankDebitReader().read_pages(pages()[1:3], "synthetic")

    def test_inconsistent_running_balance_stays_unreconciled(self):
        texts = pages()
        texts[2] = texts[2].replace("$ 303.00", "$ 304.00")
        result = OpenbankInvestmentReader().read_pages(texts, "synthetic")
        self.assertFalse(result.reconciled)
        self.assertTrue(any("Saldo por movimiento" in issue for issue in result.issues))
        debit = OpenbankDebitReader().read_pages(texts, "synthetic")
        self.assertEqual(transfer_candidates(debit, result), ())

    def test_unsupported_investment_description_requires_review(self):
        texts = pages()
        texts[2] = texts[2].replace("Abono de intereses", "Abono desconocido ")
        result = OpenbankInvestmentReader().read_pages(texts, "synthetic")
        self.assertFalse(result.reconciled)
        self.assertEqual(result.rows[-1].category, "unclassified")

    def test_wrong_period_and_dates_do_not_pass_reconciliation(self):
        texts = pages()
        texts[2] = texts[2].replace("06/01/26", "06/02/26")
        result = OpenbankInvestmentReader().read_pages(texts, "synthetic")
        self.assertFalse(result.reconciled)
        self.assertTrue(any("fuera del período" in issue for issue in result.issues))

    def test_conflicting_periods_raise_format_error(self):
        texts = pages()
        texts[2] += "\nPeriodo 01/02/26 - 28/02/26"
        with self.assertRaises(FormatError):
            OpenbankInvestmentReader().read_pages(texts, "synthetic")

    def test_unknown_withholding_cannot_be_silently_zeroed(self):
        texts = pages()
        texts[1] = texts[1].replace("Impuestos retenidos $ 0.00", "")
        with self.assertRaises(FormatError):
            OpenbankInvestmentReader().read_pages(texts, "synthetic")

    def test_nonzero_withholding_is_preserved_but_blocks_this_format(self):
        texts = pages()
        texts[1] = texts[1].replace("Impuestos retenidos $ 0.00", "Impuestos retenidos $ 1.00")
        result = OpenbankInvestmentReader().read_pages(texts, "synthetic")
        self.assertEqual(result.summary.withholding, Decimal("1"))
        self.assertFalse(result.reconciled)

    def test_raw_and_layout_disagreement_is_rejected(self):
        texts = pages()
        raw = texts.copy()
        raw[1] = raw[1].replace("$ 1.00", "$ 9.00")
        with self.assertRaises(FormatError):
            OpenbankInvestmentReader().read_pages(texts, "synthetic", raw_pages=raw)

    def test_wrapped_description_requires_logical_extraction(self):
        texts = pages()
        full = texts[0]
        line = table_row("05/01/26", "Transferencia SPEI recibida", "$ 200.00", "", "$ 210.00")
        wrapped = " " * 12 + "Transferencia SPEI\n" + table_row(
            "05/01/26", "recibida", "$ 200.00", "", "$ 210.00")
        texts[0] = texts[0].replace(line, wrapped)
        with self.assertRaises(FormatError):
            OpenbankDebitReader().read_pages(texts, "synthetic")
        raw = texts.copy()
        raw[0] = full
        result = OpenbankDebitReader().read_pages(texts, "synthetic", raw_pages=raw)
        self.assertEqual(result.rows[0].description, "Transferencia SPEI recibida")
        self.assertEqual(result.rows[1].description, "Retiro a Apartado Open")
        self.assertTrue(result.reconciled)

    def test_textual_pdf_end_to_end_without_files_or_network(self):
        content = synthetic_pdf(pages())
        debit = OpenbankDebitReader().read_pdf(content)
        investments = OpenbankInvestmentReader().read_pdf(content)
        self.assertTrue(debit.reconciled)
        self.assertTrue(investments.reconciled)
        self.assertEqual(len(transfer_candidates(debit, investments)), 1)


if __name__ == "__main__":
    unittest.main()
