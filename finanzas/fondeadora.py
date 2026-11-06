"""Fondeadora: cuenta operativa y evidencia de traspasos, sin inventar Bóvedas."""
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import re

from .ledger import _sum
from .readers import ReaderError, fold, periods, parse_date

_MONEY = re.compile(r"[-−]?\s*\$\s*\d[\d, ]*\.\s*\d\s*\d")


def compact(text):
    return re.sub(r"\s+", "", fold(text))


def money(text):
    if not _MONEY.fullmatch(text):
        raise ReaderError("Importe Fondeadora no reconocido")
    return Decimal(re.sub(r"[\s$,]", "", text).replace("−", "-"))


def labelled(lines, label):
    found = []
    for line in lines:
        if compact(label) not in compact(line.split("$")[0]):
            continue
        values = _MONEY.findall(line)
        if len(values) == 1:
            found.append(money(values[0]))
    if len(found) != 1:
        raise ReaderError("Resumen Fondeadora incompleto o ambiguo: " + label)
    return found[0]


@dataclass(frozen=True)
class FondeadoraSummary:
    initial: Decimal | None
    final: Decimal | None
    deposits: Decimal
    withdrawals_or_spending: Decimal
    purchases: Decimal | None
    commissions: Decimal | None
    interest: Decimal | None
    withholding: Decimal | None
    annual_rate_reported: Decimal | None
    gat_nominal: Decimal | None
    gat_real: Decimal | None
    unit: str | None = None


@dataclass(frozen=True)
class FondeadoraEntry:
    effective_date: date
    description: str
    category: str
    debit: Decimal | None
    credit: Decimal | None
    balance: Decimal | None
    page: int
    line: int

    @property
    def delta(self):
        return _sum(x for x in (self.credit, None if self.debit is None else self.debit.copy_negate()) if x is not None)


@dataclass(frozen=True)
class FondeadoraDifference:
    check: str
    reported: Decimal
    calculated: Decimal
    page: int
    line: int


@dataclass(frozen=True)
class FondeadoraPreview:
    document_id: str
    period_start: date
    period_end: date
    account_fingerprint: str
    issuer_printed: str
    format: str
    summary: FondeadoraSummary
    entries: tuple[FondeadoraEntry, ...]
    differences: tuple[FondeadoraDifference, ...]
    issues: tuple[str, ...]
    detail_issues: tuple[str, ...]
    lane: str
    scope: str
    shared_account: bool = True
    investment_balance: None = None
    currency_markers: tuple[str, ...] = ()

    @property
    def investment_candidates(self):
        return tuple(e for e in self.entries if e.category in ("internal_transfer", "term_transfer"))

    @property
    def reconciled(self):
        return not self.issues and not self.detail_issues

    @property
    def detail_reconciled(self):
        return not self.detail_issues

    @property
    def ready_to_import(self):
        return False


def category(description):
    text = compact(description)
    if text.startswith("traspasoentrecuentasfondea"):
        return "internal_transfer"
    if text.startswith("apartadoa"):
        return "term_transfer"
    if text.startswith("deposito"):
        return "deposit_unmatched"
    if text.startswith("transferencia"):
        return "transfer_unmatched"
    return "unknown"


class FondeadoraReader:
    def __init__(self, lane="debit"):
        if lane not in ("debit", "investments"):
            raise ReaderError("Vista Fondeadora desconocida")
        self.lane = lane

    def read_image(self, content, *, engine=None):
        from .imaging import read_statement_image
        return read_statement_image(content, "fondeadora", self.lane, engine=engine)

    def read_pdf(self, content):
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            pdf = PdfReader(BytesIO(content))
            if pdf.is_encrypted:
                raise ReaderError("PDF cifrado")
            raw = tuple(p.extract_text() or "" for p in pdf.pages)
            layout = tuple(p.extract_text(extraction_mode="layout") or "" for p in pdf.pages)
        except PyPdfError as error:
            raise ReaderError("PDF Fondeadora no legible") from error
        return self.read_pages(layout, sha256(content).hexdigest(), raw_pages=raw)

    def read_pages(self, pages, identifier, *, raw_pages=None):
        pages = tuple(pages)
        raw_pages = tuple(raw_pages) if raw_pages is not None else pages
        text, raw = "\n".join(pages), "\n".join(raw_pages)
        normalized = compact(text)
        if "fondeatechnologies" in normalized:
            issuer = "Fondea Technologies"
        elif "apoyomultiple" in normalized:
            issuer = "Apoyo Múltiple"
        else:
            raise ReaderError("Identidad Fondeadora/Fondea/Apoyo Múltiple ausente")
        if len(raw_pages) != len(pages):
            raise ReaderError("Fuentes de extracción incompatibles")
        ranges = periods(raw)
        if len(ranges) != 1:
            raise ReaderError("Período interno Fondeadora ausente o ambiguo")
        layout_ranges = periods(text)
        if layout_ranges and layout_ranges != ranges:
            raise ReaderError("Extracciones de fechas Fondeadora contradictorias")
        start, end = ranges[0]
        accounts = set(re.findall(r"clabe(?:interbancaria)?(\d{18})(?!\d)", normalized))
        if len(accounts) != 1:
            raise ReaderError("CLABE ausente o contradictoria")
        fingerprint = sha256(("fondeadora:" + accounts.pop()).encode()).hexdigest()
        is_report = "reportedemovimientos" in normalized
        first_lines = pages[0].splitlines()
        issues, details, differences = [], [], []
        if is_report:
            summary = FondeadoraSummary(None, None, labelled(first_lines, "Depósitos"),
                labelled(first_lines, "Gastos"), None, None, None, None, None, None, None)
            issues.append("Reporte sin saldos, interés ni retención: no equivalen a cero")
        else:
            def rate(label):
                lines = [line for line in first_lines if compact(label) in compact(line)]
                if len(lines) != 1:
                    raise ReaderError("Campo de tasa/GAT ausente o ambiguo")
                percent = re.search(r"(\d[\d ]*\.\s*\d\s*\d)\s*%", lines[0])
                return Decimal(re.sub(r"\s", "", percent[1])) if percent else None
            summary = FondeadoraSummary(
                labelled(first_lines, "Saldo inicial"), labelled(first_lines, "Saldo final al periodo"),
                labelled(first_lines, "Depósitos"), labelled(first_lines, "Retiros"),
                labelled(first_lines, "Compras"), labelled(first_lines, "Comisiones totales"),
                labelled(first_lines, "Interés ganado"), labelled(first_lines, "Impuestos retenidos"),
                rate("Tasa de rendimiento anual"), rate("GAT) nominal"), rate("GAT) real"))
        markers=set(re.findall(r'\b(MXN|USD|EUR|GBP|JPY|CAD)\b',text,re.I))
        markers={v.upper() for v in markers}
        if re.search(r'\bmoneda nacional\b|\bpesos mexicanos\b',fold(text)):markers.add('MXN')
        summary=replace(summary,unit='MXN' if markers=={'MXN'} else None)
        entries, movement_table = [], False
        for page_number, page in enumerate(pages[1:], 2):
            for line_number, line in enumerate(page.splitlines(), 1):
                plain = line.strip()
                if re.fullmatch(r"\d{1,3}/\d{1,3}", plain):
                    continue
                if "fecha" in compact(line) and ("descripcion" in compact(line)):
                    movement_table = True
                full = re.match(r"^(\d{2}/\d{2}/\d{4})\s+", plain)
                short = re.match(r"^([A-Za-z]{3})\s+(\d{1,2})\s+", plain) if is_report else None
                if not full and not short:
                    if re.match(r"^\d{1,4}[-/]", plain):
                        details.append("Fila fechada Fondeadora no reconocida")
                    continue
                found = list(_MONEY.finditer(plain))
                if len(found) != (1 if is_report else 3):
                    details.append("Columnas monetarias Fondeadora no reconocidas")
                    continue
                try:
                    when = parse_date(full[1] if full else f"{short[2]}/{short[1]}/{start.year}")
                except ValueError:
                    details.append("Fecha Fondeadora no reconocida")
                    continue
                description = plain[(full.end() if full else short.end()):found[0].start()].strip()
                values = tuple(money(m[0]) for m in found)
                if is_report:
                    amount = values[0]
                    debit, credit, balance = (amount.copy_negate(), None, None) if amount < 0 else (None, amount, None)
                else:
                    debit, credit, balance = values
                    if debit < 0 or credit < 0 or (debit != 0 and credit != 0):
                        details.append("Signo o columnas de cargo/abono inesperados")
                kind = category(description)
                if kind == "unknown":
                    details.append("Categoría Fondeadora pendiente de mapear")
                if not start <= when <= end:
                    details.append("Movimiento Fondeadora fuera del período")
                entries.append(FondeadoraEntry(when, description, kind, debit, credit, balance, page_number, line_number))
        if not movement_table:
            details.append("Detalle no incluido: el resumen no prueba ausencia de traspasos o inversiones")
        def check(label, reported, calculated, target, page=1, line=0):
            if reported != calculated:
                target.append(label)
                differences.append(FondeadoraDifference(label, reported, calculated, page, line))
        if not is_report:
            check("Ecuación del resumen operativo no concilia", summary.final,
                  _sum((summary.initial, summary.deposits, summary.interest,
                        summary.withdrawals_or_spending.copy_negate(), summary.purchases.copy_negate(),
                        summary.commissions.copy_negate(), summary.withholding.copy_negate())), issues)
            if movement_table:
                balance = summary.initial
                for entry in entries:
                    balance = _sum((balance, entry.delta))
                    check("Saldo corriente del detalle no concilia", entry.balance, balance, details, entry.page, entry.line)
                check("Saldo final del detalle no concilia", summary.final, balance, details)
                check("Abonos del detalle frente al resumen no coinciden", summary.deposits,
                      _sum(e.credit for e in entries if e.credit is not None), issues)
                check("Cargos del detalle frente a conceptos del resumen no coinciden",
                      _sum((summary.withdrawals_or_spending, summary.purchases, summary.commissions, summary.withholding)),
                      _sum(e.debit for e in entries if e.debit is not None), issues)
        elif movement_table:
            check("Depósitos del reporte no coinciden con entradas identificadas", summary.deposits,
                  _sum(e.credit for e in entries if e.category == "deposit_unmatched" and e.credit is not None), issues)
            check("Gastos del reporte no coinciden con salidas fuera de apartados", summary.withdrawals_or_spending,
                  _sum(e.debit for e in entries if e.category == "transfer_unmatched" and e.debit is not None), issues)
        if self.lane == "investments":
            issues.append("Solo evidencia de traspasos; no determina saldo, interés ni contrato de inversión")
        return FondeadoraPreview(identifier, start, end, fingerprint, issuer,
            "movement_report" if is_report else "account_statement", summary, tuple(entries), tuple(differences),
            tuple(dict.fromkeys(issues)), tuple(dict.fromkeys(details)), self.lane,
            "investment_transfer_evidence" if self.lane == "investments" else "operational_cash",currency_markers=tuple(sorted(markers)))
