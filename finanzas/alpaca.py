"""Alpaca USD: evidencia de acciones/ETF; guiones no equivalen a cero."""
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO
import re

from .ledger import _sum
from .readers import ReaderError

_MONTHS = dict((name, i) for i, name in enumerate(("JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"), 1))
_PRINTED = re.compile(r"-?\$\s*(?:--|(?:\d{1,3}(?:,\d{3})+|\d+)\.\d+)")


def printed(text):
    if not _PRINTED.fullmatch(text.strip()):
        raise ReaderError("Importe Alpaca no reconocido")
    if "--" in text:
        return None
    return Decimal(text.replace("$", "").replace(",", "").replace(" ", ""))


def quantity_value(text):
    try:
        value = Decimal(text.replace(",", ""))
    except InvalidOperation as error:
        raise ReaderError("Cantidad Alpaca no reconocida") from error
    if not value.is_finite():
        raise ReaderError("Cantidad Alpaca no finita")
    return value


@dataclass(frozen=True)
class PeriodAmount:
    label: str
    current: Decimal | None
    year_to_date: Decimal | None


@dataclass(frozen=True)
class StockPosition:
    symbol: str
    description: str
    quantity: Decimal | None
    price: Decimal | None
    market_value: Decimal | None
    cost_price: Decimal | None
    unrealized: Decimal | None
    cost_basis: Decimal | None
    page: int
    line: int


@dataclass(frozen=True)
class StockEntry:
    effective_date: date
    category: str
    label: str
    symbol: str | None
    description: str
    quantity: Decimal | None
    price: Decimal | None
    amount: Decimal | None
    commission: Decimal | None
    page: int
    line: int


@dataclass(frozen=True)
class AlpacaSummary:
    cash: tuple[PeriodAmount, ...]
    income: tuple[PeriodAmount, ...]
    realized: tuple[PeriodAmount, ...]
    account_values: tuple[tuple[str, Decimal | None], ...]
    unit: str = "USD"

    def cash_value(self, label):
        return next(x.current for x in self.cash if x.label == label)


@dataclass(frozen=True)
class AlpacaPreview:
    document_id: str
    period_start: date
    period_end: date
    account_fingerprint: str
    summary: AlpacaSummary
    positions: tuple[StockPosition, ...]
    entries: tuple[StockEntry, ...]
    issues: tuple[str, ...]
    detail_issues: tuple[str, ...]
    lane: str
    shared_account: bool = True

    @property
    def reconciled(self):
        return not self.issues and not self.detail_issues

    @property
    def detail_reconciled(self):
        return not self.detail_issues

    @property
    def ready_to_import(self):
        return False


def pair(line, label):
    values = _PRINTED.findall(line)
    if len(values) < 2:
        raise ReaderError("Columnas período/acumulado Alpaca incompletas")
    return PeriodAmount(label, *map(printed, values[:2]))


class AlpacaReader:
    def __init__(self, lane="investments"):
        if lane not in ("debit", "investments"):
            raise ReaderError("Vista Alpaca desconocida")
        self.lane = lane

    def read_image(self, content, *, engine=None):
        from .imaging import read_statement_image
        return read_statement_image(content, "alpaca", self.lane, engine=engine)

    def read_pdf(self, content):
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            pdf = PdfReader(BytesIO(content))
            if pdf.is_encrypted:
                raise ReaderError("PDF cifrado")
            pages = tuple(p.extract_text(extraction_mode="layout") or "" for p in pdf.pages)
        except PyPdfError as error:
            raise ReaderError("PDF Alpaca no legible") from error
        return self.read_pages(pages, sha256(content).hexdigest())

    def read_pages(self, pages, identifier):
        pages = tuple(pages)
        text = "\n".join(pages)
        if not pages or "alpaca" not in text.lower():
            raise ReaderError("Identidad Alpaca ausente")
        period = re.findall(r"Period:\s*([A-Z]+)\s*-\s*(\d{4})", pages[0])
        accounts = re.findall(r"Account No:\s*([A-Z0-9-]+)", pages[0])
        if len(period) != 1 or period[0][0] not in _MONTHS or len(set(accounts)) != 1:
            raise ReaderError("Período o cuenta Alpaca ausente o ambiguo")
        month, year = _MONTHS[period[0][0]], int(period[0][1])
        start, end = date(year, month, 1), date(year, month, monthrange(year, month)[1])
        fingerprint = sha256(("alpaca:" + accounts[0]).encode()).hexdigest()
        cash_labels = ("Beginning Balance", "Addition", "Subtraction", "Trade Transaction", "Cost and Fees", "Ending Value")
        cash, income, realized, account_values = [], [], [], []
        issues, details = [], []
        right, term = None, None
        for line in pages[0].splitlines():
            if "Realized Gain/Loss from Sales" in line:
                right = line.index("Realized Gain/Loss from Sales")
            for label in cash_labels:
                if line.strip().startswith(label):
                    cash.append(pair(line, label))
            if re.match(r"^\s*(Dividend|Interest\*{0,2})\s+\$", line):
                income.append(pair(line, line.strip().split()[0].rstrip("*")))
            if re.match(r"^\s*(Long|Short|Options|Fixed Income|Total Market Value)\s+\$", line):
                label = re.match(r"^\s*(.*?)\s+\$", line)[1]
                account_values.append((label, printed(_PRINTED.findall(line)[0])))
            if right is not None:
                segment = line[right:].strip()
                if segment.startswith("Short Term"):
                    term = "short"
                elif segment.startswith("Long Term"):
                    term = "long"
                elif term and re.match(r"^(Gain|Loss|Net)\s", segment):
                    realized.append(pair(segment, term + "_" + segment.split()[0].lower()))
        if tuple(x.label for x in cash) != cash_labels or {x.label for x in income} != {"Dividend", "Interest"}:
            raise ReaderError("Resumen Alpaca incompleto o diferente")
        if len(realized) != 6 or "Total Market Value" not in dict(account_values):
            raise ReaderError("Resultados/valores Alpaca incompletos")
        summary = AlpacaSummary(tuple(cash), tuple(income), tuple(realized), tuple(account_values))
        positions, entries = [], []
        seen_sections, cash_positions = set(), 0
        for page_number, page in enumerate(pages, 1):
            lines = page.splitlines()
            section = next((s for s in ("Holdings", "Income", "Fees", "Transaction") if any(l.strip() == s for l in lines[:5])), None)
            if section is None:
                continue
            seen_sections.add(section)
            row_count = 0
            continuation_lines = set()
            for line_number, line in enumerate(lines, 1):
                if line_number in continuation_lines:
                    continue
                cells = re.split(r"\s{2,}", line.strip())
                if section == "Holdings" and "$" in line:
                    if len(cells) != 8:
                        details.append("Fila de posiciones Alpaca no reconocida")
                        continue
                    symbol, description = cells[:2]
                    try:
                        quantity = printed(cells[2]) if cells[2].startswith("$") else quantity_value(cells[2])
                        values = tuple(printed(x) for x in cells[3:])
                    except ValueError:
                        details.append("Valores de posición Alpaca no reconocidos")
                        continue
                    if symbol == "*Cash":
                        cash_positions += 1
                        if description != "USD":
                            raise ReaderError("Moneda de efectivo Alpaca distinta de USD")
                    positions.append(StockPosition(symbol, description, quantity, *values, page_number, line_number))
                elif section != "Holdings" and re.match(r"^\s*\d{2}/\d{2}/\d{4}", line):
                    row_count += 1
                    try:
                        when = datetime.strptime(cells[0], "%m/%d/%Y").date()
                    except ValueError:
                        details.append("Fecha Alpaca no reconocida")
                        continue
                    if not start <= when <= end:
                        details.append("Operación Alpaca fuera del período")
                    if section == "Income" and len(cells) == 5:
                        category = {"Dividends": "dividend", "Div. Adj(NRA Withheld)": "foreign_withholding", "Interest": "interest"}.get(cells[1], "unknown")
                        entries.append(StockEntry(when, category, cells[1], cells[2], cells[3], None, None, printed(cells[4]), None, page_number, line_number))
                    elif section == "Fees" and len(cells) == 3:
                        entries.append(StockEntry(when, "fee", cells[1], None, cells[1], None, None, printed(cells[2]), None, page_number, line_number))
                    elif section == "Transaction" and len(cells) >= 8:
                        label = cells[1]
                        if label == "Trade Entry" and cells[2] in ("buy", "sell"):
                            category, symbol, description = cells[2], cells[3], " ".join(cells[4:-4])
                        elif label == "Memopost":
                            category, symbol, description = "memo", cells[2], " ".join(cells[3:-4])
                            if line_number < len(lines) and re.match(r"^\s*[0-9a-f]{4}-[0-9a-f-]+\s*$", lines[line_number]):
                                description += lines[line_number].strip()
                                continuation_lines.add(line_number + 1)
                        else:
                            category, symbol, description = "unknown", None, " ".join(cells[2:-4])
                        quantity = quantity_value(cells[-4])
                        price, amount, commission = map(printed, cells[-3:])
                        entries.append(StockEntry(when, category, label, symbol, description, quantity, price, amount, commission, page_number, line_number))
                        if category in ("buy", "sell") and (amount is None or (category == "buy" and (amount >= 0 or quantity <= 0)) or (category == "sell" and (amount <= 0 or quantity >= 0))):
                            details.append("Signo o importe de compraventa no reconocido")
                    else:
                        details.append("Fila de operaciones Alpaca no reconocida")
                elif section != "Holdings" and re.match(r"^\s*\d{1,4}[-/]", line):
                    details.append("Fila fechada Alpaca no reconocida")
            if section != "Holdings" and row_count == 0 and "No record found." not in page:
                details.append("Sección sin registros ni declaración explícita de ausencia")
        if seen_sections != {"Holdings", "Income", "Fees", "Transaction"} or cash_positions != 1:
            raise ReaderError("Secciones o moneda de posiciones Alpaca incompletas")
        if any(e.category == "unknown" for e in entries):
            details.append("Categoría Alpaca desconocida")
        if any(x.current is None for x in summary.cash + summary.income + summary.realized):
            issues.append("Guiones monetarios conservados como no informados; ecuaciones incompletas")
        cash_values = [x.current for x in summary.cash]
        if all(x is not None for x in cash_values):
            initial, addition, subtraction, trades, fees, final = cash_values
            if _sum((initial, addition, subtraction.copy_negate(), trades, fees.copy_negate())) != final:
                issues.append("Ecuación del efectivo Alpaca no concilia")
        known = [p.market_value for p in positions]
        if all(x is not None for x in known):
            if _sum(known) != dict(account_values)["Total Market Value"]:
                issues.append("Posiciones más efectivo no coinciden con valor total")
        else:
            issues.append("Valuación de posiciones incompleta por importes no informados")
        for label, category in (("Dividend", "dividend"), ("Interest", "interest")):
            reported = next(x.current for x in income if x.label == label)
            if reported is not None and reported != _sum(e.amount for e in entries if e.category == category and e.amount is not None):
                issues.append("Ingreso del resumen no coincide: " + label)
        trade_total = summary.cash_value("Trade Transaction")
        if trade_total is not None and trade_total != _sum(e.amount for e in entries if e.category in ("buy", "sell") and e.amount is not None):
            issues.append("Importe de compraventas no coincide con resumen")
        additions = _sum(e.amount for e in entries if e.category in ("dividend", "interest") and e.amount is not None and e.amount > 0)
        subtractions = _sum(e.amount.copy_negate() for e in entries if e.category in ("foreign_withholding", "fee") and e.amount is not None and e.amount < 0)
        if any(summary.cash_value(label) is not None and summary.cash_value(label) != total
               for label, total in (("Addition", additions), ("Subtraction", subtractions))):
            issues.append("Entradas/salidas agregadas requieren desglose y enlace de contrapartidas; no se crean operaciones por diferencia")
        return AlpacaPreview(identifier, start, end, fingerprint, summary, tuple(positions), tuple(entries),
                             tuple(dict.fromkeys(issues)), tuple(dict.fromkeys(details)), self.lane)
