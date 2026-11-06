"""Doopla: efectivo, cartera y componentes separados; nunca importa datos."""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import re

from .ledger import _sum
from .coverage import CoverageReview
from .readers import ReaderError, fold, periods

_AMOUNT = r"(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}"
_VALUE = re.compile(r"(-?)\$\s*(" + _AMOUNT + r")")
_TYPES = {"Pago": "payment", "Inversión": "investment", "Cancelación": "cancellation",
          "Depósito": "deposit", "Retiro": "withdrawal", "IVA": "vat",
          "IVA moratorios": "late_vat", "ISR sobre interes": "withholding",
          "Comisión Doopla": "commission", "Recompensa": "reward"}


def _value(text):
    match = _VALUE.fullmatch(text.strip())
    if not match:
        raise ReaderError("Importe monetario Doopla no reconocido")
    value = Decimal(match[2].replace(",", ""))
    return value.copy_negate() if match[1] else value


def _label(text, label):
    found = re.findall(re.escape(label) + r"\s*\$\s*(" + _AMOUNT + r")", text)
    if len(found) != 1:
        raise ReaderError("Resumen Doopla incompleto o ambiguo: " + label)
    return Decimal(found[0].replace(",", ""))


@dataclass(frozen=True)
class DooplaSummary:
    initial: Decimal
    interest: Decimal
    interest_vat: Decimal
    interest_vat_sign: int
    rewards: Decimal
    deposits: Decimal
    commission: Decimal
    commission_vat: Decimal
    withholding: Decimal | None
    withdrawals: Decimal
    final: Decimal
    cash_initial: Decimal
    cash_income: Decimal
    cash_expenses: Decimal
    cash_rewards: Decimal
    net_investments: Decimal
    cash_final: Decimal
    page: int = 1
    unit: str | None = None


@dataclass(frozen=True)
class DooplaEntry:
    effective_date: date
    category: str
    label: str
    alias: str | None
    principal: Decimal | None
    interest: Decimal | None
    vat: Decimal | None
    total: Decimal
    page: int
    line: int


@dataclass(frozen=True)
class LoanPosition:
    alias: str
    status: str
    payments: str
    investment: Decimal
    received: Decimal
    interest: Decimal
    interest_vat: Decimal
    repaid_principal: Decimal
    pending_principal: Decimal
    page: int
    line: int


@dataclass(frozen=True)
class Arrears:
    alias: str
    status: str
    days: int
    collection_action: str
    page: int
    line: int


@dataclass(frozen=True)
class Difference:
    check: str
    reported: Decimal
    calculated: Decimal
    page: int
    line: int


@dataclass(frozen=True)
class DooplaPreview:
    document_id: str
    period_start: date
    period_end: date
    account_fingerprint: str
    summary: DooplaSummary
    entries: tuple[DooplaEntry, ...]
    loans: tuple[LoanPosition, ...]
    loan_totals: tuple[Decimal, ...]
    arrears: tuple[Arrears, ...]
    differences: tuple[Difference, ...]
    issues: tuple[str, ...]
    cash_issues: tuple[str, ...]
    component_issues: tuple[str, ...]
    lane: str
    shared_account: bool = True
    currency_markers: tuple[str, ...] = ()

    @property
    def cash_reconciled(self):
        return not self.cash_issues

    @property
    def detail_issues(self):
        return self.cash_issues + self.component_issues

    @property
    def detail_reconciled(self):
        return not self.detail_issues

    @property
    def reconciled(self):
        return not self.issues and not self.detail_issues

    @property
    def ready_to_import(self):
        return False


def _summary(first):
    interest = re.search(r"Intereses recibidos(.*?)\(\+\) Recompensas recibidas:", first, re.S)
    fees = re.search(r"\* Comisiones pagadas(.*?)(?:\(-\) ISR:|\(-\) Retiros realizados:)", first, re.S)
    if not interest or not fees:
        raise ReaderError("Secciones del resumen Doopla ausentes")
    sign = re.findall(r"\(([+-])\) IVA:", interest[1])
    if len(sign) != 1:
        raise ReaderError("Signo del IVA de intereses ausente o ambiguo")
    retained = _label(first, "(-) ISR:") if "(-) ISR:" in first else None
    return DooplaSummary(
        _label(first, "Valor de cuenta al inicio de período"),
        _label(interest[1], "(+) Monto:"), _label(interest[1], "(" + sign[0] + ") IVA:"),
        1 if sign[0] == "+" else -1,
        _label(first, "(+) Recompensas recibidas:"), _label(first, "(+) Depositos realizados:"),
        _label(fees[1], "(-) Monto:"), _label(fees[1], "(-) IVA:"), retained,
        _label(first, "(-) Retiros realizados:"), _label(first, "Saldo al final de período"),
        _label(first, "Saldo al inicio del período"), _label(first, "(+) Ingresos"),
        _label(first, "(-) Egresos"), _label(first, "(+) Recompensas"),
        _label(first, "(-) Inversiones realizadas"), _label(first, "Efectivo disponible para retiro"))


class DooplaReader:
    def __init__(self, lane="investments"):
        if lane not in ("debit", "investments"):
            raise ReaderError("Vista Doopla desconocida")
        self.lane = lane

    def read_image(self, content, *, engine=None):
        from .imaging import read_statement_image
        return read_statement_image(content, "doopla", self.lane, engine=engine)

    def read_pdf(self, content, *, password=None):
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            pdf = PdfReader(BytesIO(content))
            if pdf.is_encrypted and (password is None or not pdf.decrypt(password)):
                raise ReaderError("PDF Doopla protegido: contraseña requerida o no válida")
            pages = tuple(p.extract_text(extraction_mode="layout") or "" for p in pdf.pages)
        except PyPdfError as error:
            raise ReaderError("PDF Doopla no legible") from error
        return self.read_pages(pages, sha256(content).hexdigest())

    def read_pages(self, pages, identifier):
        pages = tuple(pages)
        text = "\n".join(pages)
        if not pages or not re.search(r"doopla\.mx", fold(text)):
            raise ReaderError("Identidad Doopla ausente")
        ranges = periods(text)
        if len(ranges) != 1:
            raise ReaderError("Período documental Doopla ausente o ambiguo")
        start, end = ranges[0]
        clients = set(re.findall(r"Número de cliente:\s*(\d+)", text))
        if len(clients) != 1:
            raise ReaderError("Identidad de cliente ausente o contradictoria")
        fingerprint = sha256(("doopla:" + clients.pop()).encode()).hexdigest()
        summary = _summary(pages[0])
        markers={m.upper() for m in re.findall(r'\b(?:moneda|divisa)\s*:?\s*([A-Z]{3})\b',text,re.I)}
        if re.search(r'\bmoneda\s*:?\s*(?:nacional|pesos mexicanos)\b',fold(text)):markers.add('MXN')
        if re.search(r'\b(?:moneda|divisa)\s*:?\s*dolares\b',fold(text)):markers.add('USD')
        if re.search(r'\b(?:moneda|divisa)\s*:?\s*euros\b',fold(text)):markers.add('EUR')
        from dataclasses import replace
        summary=replace(summary,unit='MXN' if markers=={'MXN'} else None)
        entries, loans, arrears, totals, differences = [], [], [], [], []
        issues, cash_issues, components = [], [], []

        def check(label, reported, calculated, target, page=1, line=0):
            if reported != calculated:
                target.append(label)
                differences.append(Difference(label, reported, calculated, page, line))

        section = None
        for page_number, page in enumerate(pages, 1):
            for line_number, line in enumerate(page.splitlines(), 1):
                stripped = line.strip()
                if stripped == "Movimientos del período":
                    section = "movements"
                    continue
                if stripped == "Inversiones realizadas":
                    section = "loans"
                    continue
                if "Alias" in line and "Días de atraso" in line:
                    section = "arrears"
                    continue
                if stripped == "Comisiones pagadas":
                    section = None
                cells = re.split(r"\s{2,}", stripped)
                if section == "movements" and re.match(r"^\d{2}-\d{2}-\d{4}", stripped):
                    if len(cells) == 6 and cells[1] in ("Depósito", "Retiro", "Recompensa"):
                        cells.insert(2, "")
                    if len(cells) != 7:
                        cash_issues.append("Fila de movimientos no reconocida")
                        continue
                    try:
                        when = datetime.strptime(cells[0], "%d-%m-%Y").date()
                        values = [None if x == "-" else _value(x) for x in cells[3:6]]
                        total = _value(cells[6])
                    except ValueError:
                        cash_issues.append("Fecha o importe de movimiento no reconocido")
                        continue
                    category = _TYPES.get(cells[1], "unknown")
                    if category == "unknown":
                        cash_issues.append("Categoría desconocida")
                    if not start <= when <= end:
                        cash_issues.append("Fecha de movimiento fuera del período")
                    if category in ("investment", "withdrawal", "vat", "late_vat", "withholding", "commission") and total > 0:
                        cash_issues.append("Signo de cargo inesperado")
                    if category in ("payment", "cancellation", "deposit", "reward") and total < 0:
                        cash_issues.append("Signo de abono inesperado")
                    if category == "payment":
                        if all(x is None for x in values) or any(x is not None and x < 0 for x in values):
                            components.append("Desglose de pago ausente o con signo inesperado")
                        check("Componentes de un pago no coinciden con su total", total,
                              _sum(x for x in values if x is not None), components, page_number, line_number)
                    elif any(x is not None for x in values):
                        components.append("Componentes inesperados en movimiento distinto de pago")
                    entries.append(DooplaEntry(when, category, cells[1], cells[2] or None,
                                               *values, total, page_number, line_number))
                elif section == "movements" and re.match(r"^\d{1,4}[-/]", stripped):
                    cash_issues.append("Fila con fecha no reconocida")
                elif section == "loans" and "$" in stripped:
                    if cells[0] == "TOTAL" and len(cells) == 7:
                        totals.append((tuple(_value(x) for x in cells[1:]), page_number, line_number))
                    elif len(cells) == 9 and re.fullmatch(r"\d+ de \d+", cells[2]):
                        loans.append(LoanPosition(*cells[:3], *map(_value, cells[3:]), page_number, line_number))
                    else:
                        issues.append("Fila de cartera no reconocida")
                elif section == "loans" and re.search(r"\d+ de \d+", stripped) and "No. Pagos" not in stripped:
                    issues.append("Fila de cartera con importes no reconocidos")
                elif section == "arrears" and len(cells) == 4 and cells[2].isdigit():
                    arrears.append(Arrears(cells[0], cells[1], int(cells[2]), cells[3], page_number, line_number))
        if not entries:
            cash_issues.append("Detalle de movimientos ausente o vacío")
        if len(totals) != 1:
            raise ReaderError("Total de cartera ausente o ambiguo")
        loan_totals, total_page, total_line = totals[0]
        retained_terms = () if summary.withholding is None else (summary.withholding.copy_negate(),)
        check("Ecuación del valor de cuenta no concilia", summary.final,
              _sum((summary.initial, summary.interest,
                    summary.interest_vat if summary.interest_vat_sign == 1 else summary.interest_vat.copy_negate(),
                    summary.rewards, summary.deposits, summary.commission.copy_negate(),
                    summary.commission_vat.copy_negate(), summary.withdrawals.copy_negate(), *retained_terms)), issues)
        check("Ecuación del efectivo no concilia", summary.cash_final,
              _sum((summary.cash_initial, summary.cash_income, summary.cash_expenses.copy_negate(),
                    summary.cash_rewards, summary.net_investments.copy_negate())), cash_issues)
        check("Movimientos no concilian con el efectivo final", summary.cash_final,
              _sum((summary.cash_initial, *(e.total for e in entries))), cash_issues)
        def total_for(*categories):
            return _sum(e.total for e in entries if e.category in categories)
        for label, reported, calculated in (
            ("Ingresos de efectivo no coinciden", summary.cash_income, total_for("deposit", "payment")),
            ("Egresos de efectivo no coinciden", summary.cash_expenses, total_for("withdrawal", "vat", "late_vat", "withholding", "commission").copy_negate()),
            ("Recompensas de efectivo no coinciden", summary.cash_rewards, total_for("reward")),
            ("Inversiones netas no coinciden", summary.net_investments, total_for("investment", "cancellation").copy_negate()),
        ):
            check(label, reported, calculated, cash_issues)
        for label, reported, calculated in (
            ("Depósitos del resumen no coinciden", summary.deposits, total_for("deposit")),
            ("Retiros del resumen no coinciden", summary.withdrawals, total_for("withdrawal").copy_negate()),
            ("Intereses del resumen no coinciden", summary.interest, _sum(e.interest for e in entries if e.interest is not None)),
            ("IVA de pagos no coincide con resumen", summary.interest_vat, _sum(e.vat for e in entries if e.vat is not None)),
            ("Comisión con IVA no coincide", _sum((summary.commission, summary.commission_vat)), total_for("commission").copy_negate()),
        ):
            check(label, reported, calculated, issues)
        if summary.withholding is not None:
            check("Retención ISR no coincide con movimientos", summary.withholding, total_for("withholding").copy_negate(), issues)
        elif any(e.category == "withholding" for e in entries):
            issues.append("ISR presente en detalle y ausente en resumen")
        check("Valor de cuenta y cambio patrimonial del detalle no coinciden", summary.final,
              _sum((summary.initial, total_for("deposit", "withdrawal", "reward", "vat", "late_vat", "withholding", "commission"),
                    *(_sum(x for x in (e.interest, e.vat) if x is not None) for e in entries if e.category == "payment"))), issues)
        names = ("investment", "received", "interest", "interest_vat", "repaid_principal", "pending_principal")
        for index, name in enumerate(names):
            check("Total de cartera difiere de sus filas: " + name, loan_totals[index],
                  _sum(getattr(loan, name) for loan in loans), issues, total_page, total_line)
        check("Capital pendiente total más efectivo difiere del valor de cuenta", summary.final,
              _sum((loan_totals[5], summary.cash_final)), issues, total_page, total_line)
        unique = lambda values: tuple(dict.fromkeys(values))
        return DooplaPreview(identifier, start, end, fingerprint, summary, tuple(entries), tuple(loans),
                             loan_totals, tuple(arrears), tuple(differences), unique(issues),
                             unique(cash_issues), unique(components), self.lane,currency_markers=tuple(sorted(markers)))


@dataclass(frozen=True)
class DooplaCoverage:
    coverage: CoverageReview
    cash_continuity_checked: int
    issues: tuple[str, ...]


def review_doopla_documents(previews):
    """Comprueba continuidad de ambas magnitudes sin corregir ni importar."""
    from datetime import timedelta
    from .coverage import review_coverage
    previews = tuple(previews)
    coverage = review_coverage(previews)
    ordered = sorted({p.document_id: p for p in previews}.values(), key=lambda p: (p.period_start, p.period_end))
    checked, issues = 0, []
    fields = ("alias", "payments", "investment", "received", "interest", "interest_vat",
              "repaid_principal", "pending_principal")
    snapshot = lambda p: tuple(sorted(tuple(getattr(loan, name) for name in fields) for loan in p.loans))
    for previous, current in zip(ordered, ordered[1:]):
        if previous.period_end + timedelta(days=1) != current.period_start:
            continue
        checked += 1
        if previous.summary.cash_final != current.summary.cash_initial:
            issues.append("Efectivo final e inicial consecutivos no coinciden")
        activity = any(e.category in ("investment", "cancellation") or
                       (e.category == "payment" and e.principal is not None and e.principal != 0)
                       for e in current.entries)
        if previous.loans and snapshot(previous) == snapshot(current) and activity:
            issues.append("Cartera repite cifras entre períodos con movimientos de capital; revisar vigencia del anexo")
    return DooplaCoverage(coverage, checked, tuple(issues))
