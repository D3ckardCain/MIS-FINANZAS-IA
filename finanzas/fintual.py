"""Fondos Fintual en MXN: valuación, flujos y retención separados."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO
import re

from .ledger import _sum
from .readers import ReaderError, fold, periods, parse_date

_MONEY = r"(?:-\$\s*|\$\s*-?)(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+|,\d{2})"
_DATE = r"\d{1,2}/[a-zA-Z]+/\d{4}"


def money(text):
    if not re.fullmatch(_MONEY, text.strip()):
        raise ReaderError("Importe Fintual no reconocido")
    text = text.strip().replace("$", "").replace(" ", "")
    if "." not in text and re.fullmatch(r"\d+,\d{2}", text):
        text = text.replace(",", ".")
    else:
        text = text.replace(",", "")
    return Decimal(text)


def value(block, label):
    found = re.findall(re.escape(label) + r"\s*(" + _MONEY + r")", block)
    if len(found) != 1:
        raise ReaderError("Fintual: importe ausente o ambiguo: " + label)
    return money(found[0])


@dataclass(frozen=True)
class FundPosition:
    name_printed: str
    units: Decimal
    price: Decimal
    market_value: Decimal
    average_cost: Decimal | None
    variation_reported: Decimal | None
    allocation: Decimal
    page: int
    line: int


@dataclass(frozen=True)
class FundEntry:
    effective_date: date
    category: str
    amount: Decimal
    commission: Decimal
    vat: Decimal
    page: int
    line: int


@dataclass(frozen=True)
class FundSummary:
    initial: Decimal
    final: Decimal
    initial_positions: Decimal
    final_positions: Decimal
    initial_cash: Decimal
    final_cash: Decimal
    initial_pending: Decimal
    final_pending: Decimal
    deposits: Decimal
    withdrawals: Decimal
    withholding_reported: Decimal
    commissions_reported: Decimal
    net_return_reported: Decimal | None
    unit: str = "MXN"


@dataclass(frozen=True)
class FundDifference:
    check: str
    reported: Decimal
    calculated: Decimal
    page: int


@dataclass(frozen=True)
class FintualPreview:
    document_id: str
    period_start: date
    period_end: date
    account_fingerprint: str
    summary: FundSummary
    initial_positions: tuple[FundPosition, ...]
    final_positions: tuple[FundPosition, ...]
    entries: tuple[FundEntry, ...]
    differences: tuple[FundDifference, ...]
    issues: tuple[str, ...]
    detail_issues: tuple[str, ...]
    lane: str = "investments"

    @property
    def reconciled(self):
        return not self.issues and not self.detail_issues

    @property
    def detail_reconciled(self):
        return not self.detail_issues

    @property
    def ready_to_import(self):
        return False


def positions(block, current, issues, offset=0):
    result = []
    for line_number, line in enumerate(block.splitlines(), 1):
        cells = re.split(r"\s{2,}", line.strip())
        if "$" not in line or any(label in line for label in ("Posición de Valores", "Efectivo:", "Pendiente por liquidar", "Posición total")):
            continue
        if len(cells) != (7 if current else 5):
            issues.append("Fila de posiciones Fintual no reconocida")
            continue
        try:
            units = Decimal(cells[1].replace(",", ""))
            values = [money(x) for x in cells[2:-1]]
            allocation = Decimal(cells[-1])
        except (ValueError, InvalidOperation):
            issues.append("Componentes de posición Fintual no reconocidos")
            continue
        if current:
            cost, price, market, variation = values
        else:
            price, market = values
            cost = variation = None
        result.append(FundPosition(cells[0], units, price, market, cost, variation, allocation, 1, line_number + offset))
    if not result and "no hay activos" not in fold(block):
        issues.append("Posiciones ausentes sin declaración explícita de cartera vacía")
    return tuple(result)


class FintualInvestmentReader:
    def read_image(self, content, *, engine=None):
        from .imaging import read_statement_image
        return read_statement_image(content, "fintual", "investments", engine=engine)

    def read_pdf(self, content):
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            pdf = PdfReader(BytesIO(content))
            if pdf.is_encrypted:
                raise ReaderError("PDF cifrado")
            pages = tuple(p.extract_text(extraction_mode="layout") or "" for p in pdf.pages)
        except PyPdfError as error:
            raise ReaderError("PDF Fintual no legible") from error
        return self.read_pages(pages, sha256(content).hexdigest())

    def read_pages(self, pages, identifier):
        pages = tuple(pages)
        text = "\n".join(pages)
        if not pages or not re.search(r"\bfintual\b", fold(text)) or "pesos mexicanos" not in fold(text):
            raise ReaderError("Identidad Fintual/MXN no comprobada")
        ranges = periods(text)
        account = re.findall(r"No\. cuenta:\s*([A-Z0-9]+(?:-[A-Z0-9]+)*)", pages[0])
        if len(ranges) != 1 or len(set(account)) != 1:
            raise ReaderError("Cuenta o período Fintual ausente o ambiguo")
        start, end = ranges[0]
        fingerprint = sha256(("fintual:" + account[0]).encode()).hexdigest()
        if pages[0].count("Cartera período actual") != 1 or pages[0].count("Cartera período anterior") != 1:
            raise ReaderError("Secciones de cartera no reconocidas")
        current, previous = pages[0].split("Cartera período actual", 1)[1].split("Cartera período anterior", 1)
        issues, detail, differences = [], [], []
        offsets = [pages[0][:pages[0].index(label) + len(label)].count("\n")
                   for label in ("Cartera período actual", "Cartera período anterior")]
        final_positions = positions(current, True, issues, offsets[0])
        initial_positions = positions(previous, False, issues, offsets[1])
        cash_sections = [p for p in pages if "RESUMEN DE MOVIMIENTOS" in p]
        if len(cash_sections) != 1:
            raise ReaderError("Resumen de movimientos ausente o ambiguo")
        cash = cash_sections[0]
        totals = re.search(r"Total retiros\s+Total depósitos\s*\n\s*(" + _MONEY + r")\s+(" + _MONEY + r")", cash)
        if not totals:
            raise ReaderError("Columnas de depósitos/retiros no reconocidas")
        rate = re.findall(r"^.*\(período actual\)\s+(NaN|-?[\d.]+)%", text, re.M)
        if len(rate) != 1:
            raise ReaderError("Rendimiento del período actual no identificado")
        summary = FundSummary(
            value(previous, "Posición total:"), value(current, "Posición total:"),
            value(previous, "Posición de Valores:"), value(current, "Posición de Valores:"),
            value(previous, "Efectivo:"), value(current, "Efectivo:"),
            value(previous, "Pendiente por liquidar:"), value(current, "Pendiente por liquidar:"),
            money(totals[2]), money(totals[1]), value(text, "Total de ISR retenido:"),
            value(text, "Total de Comisiones:"), None if rate[0] == "NaN" else Decimal(rate[0]))
        entries = []
        categories = {"Compra": "purchase", "Venta": "sale", "Nos depositaste": "deposit", "Te depositamos": "withdrawal"}
        in_movements = False
        for page_number, page in enumerate(pages, 1):
            for line_number, line in enumerate(page.splitlines(), 1):
                if "MOVIMIENTOS DEL PERÍODO" in line:
                    in_movements = True
                    continue
                if "RENDIMIENTO NETO DEL PORTAFOLIO" in line:
                    in_movements = False
                if not in_movements or not re.match(r"^\s*\d{1,2}/", line):
                    continue
                cells = re.split(r"\s{2,}", line.strip())
                # Fechas de liquidación independientes pertenecen al detalle, no son otra fila.
                if len(cells) == 1 and re.fullmatch(_DATE, cells[0]):
                    continue
                if len(cells) < 5 or not re.fullmatch(_DATE, cells[0]):
                    detail.append("Fila fechada Fintual no reconocida")
                    continue
                try:
                    amounts = tuple(money(x) for x in cells[-3:])
                    when = parse_date(cells[0])
                except ValueError:
                    detail.append("Importe/fecha Fintual no reconocido")
                    continue
                category = categories.get(cells[1], "unknown")
                if category == "unknown":
                    detail.append("Movimiento Fintual desconocido")
                if not start <= when <= end:
                    detail.append("Movimiento fuera del período")
                entries.append(FundEntry(when, category, *amounts, page_number, line_number))
        if not entries and "no hay movimientos en el periodo" not in fold(cash):
            detail.append("Movimientos ausentes sin declaración explícita")
        def check(label, reported, calculated, target, page=1):
            if reported != calculated:
                target.append(label)
                differences.append(FundDifference(label, reported, calculated, page))
        for prefix, block_positions, total, cash_amount, pending, position_total in (
                ("Inicial", initial_positions, summary.initial, summary.initial_cash, summary.initial_pending, summary.initial_positions),
                ("Final", final_positions, summary.final, summary.final_cash, summary.final_pending, summary.final_positions)):
            check(prefix + ": valuación de filas no coincide", position_total, _sum(p.market_value for p in block_positions), issues)
            check(prefix + ": valores más efectivo y pendientes no coinciden", total, _sum((position_total, cash_amount, pending)), issues)
        for category, reported in (("deposit", summary.deposits), ("withdrawal", summary.withdrawals)):
            check("Resumen frente a movimientos: " + category, reported, _sum(e.amount for e in entries if e.category == category), detail, 2)
        check("Comisiones del resumen frente al detalle", summary.commissions_reported, _sum(e.commission for e in entries), detail, 2)
        signed = [e.amount if e.category in ("deposit", "sale") else e.amount.copy_negate() for e in entries]
        fees = _sum(_sum((e.commission, e.vat)) for e in entries)
        check("Efectivo inicial más flujos no coincide con efectivo final", summary.final_cash,
              _sum((summary.initial_cash, *signed, fees.copy_negate())), detail, 2)
        if summary.net_return_reported is None:
            issues.append("Rendimiento NaN no se convierte en cero")
        return FintualPreview(identifier, start, end, fingerprint, summary, initial_positions, final_positions,
                              tuple(entries), tuple(differences), tuple(dict.fromkeys(issues)), tuple(dict.fromkeys(detail)))
