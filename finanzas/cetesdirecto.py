"""CETESdirecto: efectivo y posiciones separados; ninguna valoración se crea como cobro."""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import re
import unicodedata

from .ledger import _sum
from .readers import ReaderError, fold, periods


_MONEY = r"-?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}"
_DATE = r"\d{2}/\d{2}/\d{2}"
_ROW = re.compile(r"^(" + _DATE + r")\s+(" + _DATE + r")\s+(SVD\d+)\s*([A-Z_]+)\s+(\S+)\s+(\S+)\s+(.*?)\s+(" + _MONEY + r")\s+(" + _MONEY + r")\s+(" + _MONEY + r")\s*$")
_POSITION = re.compile(r"^([A-Z][A-Z0-9_-]*)\s+(\S+)\s+([\d,]+(?:\.\d+)?)\s+\$?(\d+\.\d+)\s+\$?(" + _MONEY + r")(?:\s+(.*))?$")
_KINDS = {"INGEFVO": "cash_in", "EGREFVO": "cash_out", "COMPRA": "purchase",
          "COMPSI": "purchase", "VTASI": "sale", "AMORTIZACION": "amortization", "ISR": "withholding"}


def _decimal(value):
    return Decimal(value.replace(",", ""))


def _scalar(text, label):
    found = re.findall(label.replace(" ", r"\s+") + r"\s*:\s*\$?\s*(" + _MONEY + r")", text, re.I)
    if len(found) != 1:
        raise ReaderError("Campo CETESdirecto ausente o ambiguo: " + label)
    return _decimal(found[0])


@dataclass(frozen=True)
class PortfolioSummary:
    initial_positions: Decimal
    initial_cash: Decimal
    initial_total: Decimal
    final_positions: Decimal
    final_cash: Decimal
    final_total: Decimal
    cash_in: Decimal
    cash_out: Decimal
    interest_period: Decimal
    withholding_period: Decimal
    interest_cumulative: Decimal
    withholding_cumulative: Decimal
    unit: str = "MXN"

    @property
    def initial(self):
        return self.initial_total

    @property
    def final(self):
        return self.final_total


@dataclass(frozen=True)
class Position:
    issuer: str
    series: str
    units: Decimal
    market_price: Decimal
    market_value: Decimal
    additional_fields: str
    page: int
    line: int


@dataclass(frozen=True)
class CashEntry:
    registered: date
    settled: date
    folio: str
    operation: str
    issuer: str
    series: str
    instrument_fields: tuple[str, ...]
    debit: Decimal
    credit: Decimal
    balance: Decimal
    kind: str
    page: int
    line: int


@dataclass(frozen=True)
class ReportedResult:
    label: str
    amount: Decimal


@dataclass(frozen=True)
class CetesPreview:
    document_id: str
    logical_text_id: str
    account_fingerprint: str
    period_start: date
    period_end: date
    summary: PortfolioSummary
    initial_positions: tuple[Position, ...]
    final_positions: tuple[Position, ...]
    reported_results: tuple[ReportedResult, ...]
    entries: tuple[CashEntry, ...]
    cash_initial_detail: Decimal
    cash_final_detail: Decimal
    detail_issues: tuple[str, ...]
    issues: tuple[str, ...]
    lane: str = "investments"

    @property
    def detail_reconciled(self):
        return not self.detail_issues

    @property
    def reconciled(self):
        return not self.detail_issues and not self.issues

    @property
    def ready_to_import(self):
        return False


def _positions(page, section, number):
    start = re.search(r"Posici[oó]n\s+" + section + r"\s+del\s+per[ií]odo", page, re.I)
    if start is None:
        raise ReaderError("Sección de posiciones CETESdirecto ausente")
    content = page[start.end():]
    total = re.search(r"Posici[oó]n\s+Total\s+\$?\s*(" + _MONEY + r")", content, re.I)
    if total is None:
        raise ReaderError("Total de posiciones CETESdirecto ausente")
    body = content[:total.start()]
    rows = []
    offset = page[:start.end()].count("\n")
    for index, line in enumerate(body.splitlines(), offset + 1):
        match = _POSITION.fullmatch(line.strip())
        if match:
            issuer, series, units, price, value, additional = match.groups()
            rows.append(Position(issuer, series, _decimal(units), _decimal(price), _decimal(value),
                                 additional or "", number, index))
        elif re.match(r"^[A-Z][A-Z0-9_-]*\s+\S+\s+[\d,]+\s+", line.strip()):
            raise ReaderError("Fila de posiciones CETESdirecto no reconocida")
    observed_total = _decimal(total[1])
    if _sum(p.market_value for p in rows) != observed_total:
        raise ReaderError("Filas de posiciones no reconocidas o no conciliadas con su total")
    return tuple(rows), observed_total


class CetesDirectoInvestmentReader:
    def read_image(self, content, *, engine=None):
        from .imaging import read_statement_image
        return read_statement_image(content, "cetesdirecto", "investments", engine=engine)

    def read_pdf(self, content):
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise ReaderError("PDF CETESdirecto cifrado")
            pages = tuple(page.extract_text() or "" for page in reader.pages)
        except PyPdfError as error:
            raise ReaderError("PDF CETESdirecto no legible") from error
        return self.read_pages(pages, sha256(content).hexdigest())

    def read_pages(self, pages, identifier):
        pages = tuple(pages)
        text = "\n".join(pages)
        if "cetesdirecto.com" not in fold(text):
            raise ReaderError("Identidad CETESdirecto ausente")
        ranges = periods(text)
        if len(ranges) != 1:
            raise ReaderError("Período CETESdirecto ausente o ambiguo")
        start, end = ranges[0]
        account = re.findall(r"Contrato/Cuenta\s+CLABE:\s*(\d+)", text, re.I)
        if not account or len(set(account)) != 1:
            raise ReaderError("Cuenta CETESdirecto no identificada de forma única")
        final_pages = [(i, p) for i, p in enumerate(pages, 1) if re.search(r"Posici[oó]n final del per[ií]odo", p, re.I)]
        initial_pages = [(i, p) for i, p in enumerate(pages, 1) if re.search(r"Posici[oó]n inicial del per[ií]odo", p, re.I)]
        if len(final_pages) != 1 or len(initial_pages) != 1:
            raise ReaderError("Se requieren posiciones inicial/final únicas")
        final_number, final = final_pages[0]
        initial_number, initial = initial_pages[0]
        if not re.search(r"Moneda:\s*(?:MXN\s+)?PESOS\b", final, re.I):
            raise ReaderError("Moneda CETESdirecto ausente o no admitida por este perfil")
        # Variación tipográfica observada en la etiqueta fiscal nueva.
        final = re.sub(r"Retenidodel", "Retenido del", final, flags=re.I)
        reported_results = []
        for label, value in re.findall(
                r"(Ganancia de capital \(BONDDIA\)|Rendimiento BONDDIA|Rendimiento ENERFIN|"
                r"Resultado Acumulado por Venta Anticipada GUBER|Resultado por Venta Anticipada GUBER(?: Per[ií]odo)?)"
                r"\s*:\s*\$\s*(" + _MONEY + r")", final, re.I):
            reported_results.append(ReportedResult(label, _decimal(value)))
        summary = PortfolioSummary(
            _scalar(initial, r"Total de cartera"), _scalar(initial, r"Total de efectivo"),
            _scalar(initial, r"Total inicial"), _scalar(final, r"Total de cartera"),
            _scalar(final, r"Total de efectivo"), _scalar(final, r"Total final"),
            _scalar(final, r"Ingresos del per[ií]odo"), _scalar(final, r"Egresos del per[ií]odo"),
            _scalar(final, r"Intereses del per[ií]odo"), _scalar(final, r"ISR(?: Retenido)? del per[ií]odo"),
            _scalar(final, r"Intereses acumulados del ejercicio fiscal"),
            _scalar(final, r"ISR(?: Retenido)? acumulado del ejercicio fiscal"))
        initial_positions, initial_position_total = _positions(initial, "inicial", initial_number)
        final_positions, final_position_total = _positions(final, "final", final_number)
        entries, initial_cash, final_cash = [], [], []
        for number, page in enumerate(pages, 1):
            if "movimientos del periodo" not in fold(page):
                continue
            begin = re.search(r"Saldo inicial\s+\$?\s*(" + _MONEY + r")", page, re.I)
            finish = re.search(r"Saldo final\s+\$?\s*(" + _MONEY + r")", page, re.I)
            if not begin or not finish:
                raise ReaderError("Inicio/final del detalle de efectivo ausente")
            initial_cash.append(_decimal(begin[1])); final_cash.append(_decimal(finish[1]))
            for line_number, line in enumerate(page.splitlines(), 1):
                if not re.match(r"^\s*" + _DATE, line):
                    continue
                match = _ROW.fullmatch(line.strip())
                if not match:
                    raise ReaderError("Movimiento CETESdirecto no reconocido")
                registered, settled, folio, operation, issuer, series, instrument, debit, credit, balance = match.groups()
                entries.append(CashEntry(datetime.strptime(registered, "%d/%m/%y").date(),
                    datetime.strptime(settled, "%d/%m/%y").date(), folio, operation, issuer, series,
                    tuple(instrument.split()), _decimal(debit), _decimal(credit), _decimal(balance),
                    _KINDS.get(operation, "unclassified"), number, line_number))
        if len(initial_cash) != 1 or len(final_cash) != 1:
            raise ReaderError("Formato de detalle de efectivo multipágina no admitido todavía")
        detail_issues, issues = [], []
        previous = initial_cash[0]
        for e in entries:
            if not (start <= e.registered <= end or start <= e.settled <= end):
                detail_issues.append("Operación y liquidación fuera del período documental")
            if e.debit < 0 or e.credit < 0:
                detail_issues.append("Cargo o abono negativo no admitido")
            if _sum((previous, e.credit, e.debit.copy_negate())) != e.balance:
                detail_issues.append(f"Saldo de efectivo no conciliado en página {e.page}, línea {e.line}")
            if e.kind == "unclassified":
                issues.append("Código de operación no clasificado: " + e.operation)
            previous = e.balance
        if previous != final_cash[0]:
            detail_issues.append("Cierre del detalle de efectivo no coincide")
        if initial_cash[0] != summary.initial_cash or final_cash[0] != summary.final_cash:
            issues.append("Efectivo del resumen y detalle no coincide")
        if initial_position_total != summary.initial_positions or final_position_total != summary.final_positions:
            issues.append("Posiciones y resumen no coinciden")
        if _sum((summary.initial_positions, summary.initial_cash)) != summary.initial_total:
            issues.append("Posiciones más efectivo no coinciden con total inicial")
        if _sum((summary.final_positions, summary.final_cash)) != summary.final_total:
            issues.append("Posiciones más efectivo no coinciden con total final")
        for code, expected in (("cash_in", summary.cash_in), ("cash_out", summary.cash_out),
                               ("withholding", summary.withholding_period)):
            actual = _sum(e.credit if code == "cash_in" else e.debit for e in entries if e.kind == code)
            if actual != expected:
                issues.append("Detalle y resumen difieren en " + code)
        canonical_text = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()
        return CetesPreview(identifier, sha256(canonical_text.encode()).hexdigest(),
            sha256(("cetesdirecto:" + account[0]).encode()).hexdigest(), start, end, summary,
            initial_positions, final_positions, tuple(reported_results), tuple(entries), initial_cash[0], final_cash[0],
            tuple(detail_issues), tuple(issues))
