"""DiDi Cuenta: dos vistas de la misma cuenta, revisión sin importación."""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import re

from .ledger import _sum
from .readers import ReaderError, fold, periods

_MONEY = r"(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}"
_ROW = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(Depósito|Retiro)\s+", re.M)


def _money(value):
    return Decimal(value.replace(",", ""))


@dataclass(frozen=True)
class DidiSummary:
    initial: Decimal
    deposits: Decimal
    withdrawals: Decimal
    average: Decimal
    interest: Decimal
    withholding: Decimal
    final: Decimal
    page: int = 1


@dataclass(frozen=True)
class DidiEntry:
    effective_date: date
    direction: str
    category: str
    amount: Decimal
    balance: Decimal
    reference: str | None
    page: int
    line: int


@dataclass(frozen=True)
class DidiPreview:
    document_id: str
    period_start: date
    period_end: date
    account_fingerprint: str
    summary: DidiSummary
    entries: tuple[DidiEntry, ...]
    rate_disclosure: str
    annual_rates_reported: tuple[Decimal, ...]
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


def _summary(layout):
    if "Impuesto retenido" in layout:
        labels = ("Saldo inicial", "Depósitos", "Retiros", "Saldo promedio",
                  "Rendimiento", "Impuesto retenido", "Saldo final")
        values = []
        for label in labels:
            found = re.findall(r"^\s*" + re.escape(label) + r"\s+\$\s*(" + _MONEY + r")\s*$", layout, re.M)
            if len(found) != 1:
                raise ReaderError("Resumen DiDi nuevo incompleto o ambiguo")
            values.append(_money(found[0]))
        return DidiSummary(*values)
    header = re.search(r"Saldo inicial\s+Depósitos\s+Retiros\s*\n\s*\$\s*(" + _MONEY + r")\s+\$\s*(" + _MONEY + r")\s+\$\s*(" + _MONEY + r")", layout)
    if not header:
        raise ReaderError("Columnas del resumen DiDi no reconocidas")
    values = []
    for label in ("Saldo promedio diario", "Rendimientos totales", "Total de impuestos deducidos", "Saldo al cierre"):
        found = re.findall(re.escape(label) + r":\s*\$\s*(" + _MONEY + r")", layout)
        if len(found) != 1:
            raise ReaderError("Resumen DiDi antiguo incompleto o ambiguo")
        values.append(_money(found[0]))
    return DidiSummary(*map(_money, header.groups()), *values)


class DidiReader:
    def __init__(self, lane="investments"):
        if lane not in ("debit", "investments"):
            raise ReaderError("Vista DiDi desconocida")
        self.lane = lane

    def read_image(self, content, *, engine=None):
        from .imaging import read_statement_image
        return read_statement_image(content, "didi", self.lane, engine=engine)

    def read_pdf(self, content):
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise ReaderError("PDF cifrado")
            pages = tuple(p.extract_text() or "" for p in reader.pages)
            layout = reader.pages[0].extract_text(extraction_mode="layout") or ""
        except (PyPdfError, IndexError) as error:
            raise ReaderError("PDF DiDi no legible") from error
        return self.read_pages(pages, sha256(content).hexdigest(), layout=layout)

    def read_pages(self, pages, identifier, *, layout):
        pages = tuple(pages)
        text = "\n".join(pages)
        if not pages or "didi cuenta" not in fold(pages[0]) or "sofiexpress" not in fold(pages[0]):
            raise ReaderError("Identidad DiDi/Sofiexpress ausente")
        ranges = periods(text)
        if len(ranges) != 1:
            raise ReaderError("Se requiere un período documental único")
        start, end = ranges[0]
        accounts = set(re.findall(r"Número de cuenta:\s*(\d+)", text))
        if len(accounts) != 1 or not re.search(r"Número de cuenta:\s*\d+", pages[0]):
            raise ReaderError("Cuenta DiDi ausente o contradictoria")
        fingerprint = sha256(("didi:" + accounts.pop()).encode()).hexdigest()
        summary = _summary(layout)
        rate = re.search(r"(?:1\. Hasta[^\n]*\n)?Tasa de rendimiento anual fija.*?(?:Última actualización|Fecha de cálculo):[^\n]*", pages[0], re.S)
        if not rate:
            raise ReaderError("Información histórica de tasas ausente")
        disclosure = rate[0]
        rates = tuple(_money(x) for x in re.findall(r"Tasa de rendimiento anual fija:?\s*([\d.]+)%", disclosure))
        if not rates:
            raise ReaderError("Tasa anual no reconocida")
        # Conserva referencias de página/línea; elimina únicamente cabeceras repetidas.
        lines = []
        active = False
        for page_number, page in enumerate(pages, 1):
            for line_number, line in enumerate(page.splitlines(), 1):
                if line.strip() in ("Detalles de movimientos DiDi Cuenta", "Detalles de movimientos"):
                    active = True
                    continue
                if not active:
                    continue
                if re.search(r"Página\s+\d+\s+de|El periodo:|Días del periodo:|Número de (cliente|cuenta):|ABONO CARGO|Solución Factible Consultores|Proveedor Autorizado de Certificación|www.solucionfactible.com", line):
                    continue
                lines.append((line, page_number, line_number))
        body = "\n".join(x[0] for x in lines)
        offsets, pos = [], 0
        for line, page_number, line_number in lines:
            offsets.append((pos, page_number, line_number))
            pos += len(line) + 1
        matches = list(_ROW.finditer(body))
        entries, details, issues = [], [], []
        dated_lines = re.findall(r"^\d{2}/\d{2}/\d{4}[^\n]*", body, re.M)
        if len(dated_lines) != len(matches):
            details.append("Fila fechada no reconocida")
        initial = re.findall(r"Saldo inicial\s*\$\s*(" + _MONEY + r")", body)
        if len(initial) != 1 or _money(initial[0]) != summary.initial:
            details.append("Saldo inicial del detalle ausente o distinto del resumen")
        for index, match in enumerate(matches):
            block = body[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(body)]
            amounts = re.findall(r"MXN\s*\$\s*(" + _MONEY + r")\s*\$\s*(" + _MONEY + r")", block)
            if len(amounts) != 1:
                details.append("Movimiento sin importe/saldo MXN únicos")
                continue
            try:
                when = datetime.strptime(match[1], "%d/%m/%Y").date()
            except ValueError as error:
                raise ReaderError("Fecha DiDi inválida") from error
            direction = "deposit" if match[2] == "Depósito" else "withdrawal"
            normalized = fold(block)
            if normalized.startswith("rendimientos") and direction == "deposit":
                category = "interest"
            elif (normalized.startswith("transferencia entrante") and direction == "deposit") or (normalized.startswith("transferencia saliente") and direction == "withdrawal"):
                category = "transfer_unmatched"
            else:
                category = "unclassified"
                details.append("Tipo de movimiento no reconocido")
            # Algunos PDF separan el ID de su etiqueta y lo continúan tras
            # las cabeceras de la página siguiente. No usar números de CLABE.
            reference = re.findall(r"\b((?:SN)?CBS\d+(?:\n\d+)*)(?=\s|$)", block)
            ref = re.sub(r"\s", "", reference[0]) if len(reference) == 1 else None
            if ref is None:
                details.append("Referencia de movimiento pendiente")
            source = next(x for x in reversed(offsets) if x[0] <= match.start())
            entries.append(DidiEntry(when, direction, category, *map(_money, amounts[0]), ref, source[1], source[2]))
        if not entries:
            details.append("Detalle sin movimientos: requiere revisión")
        balance, previous, references = summary.initial, start, set()
        for entry in entries:
            if not start <= entry.effective_date <= end or entry.effective_date < previous:
                details.append("Fecha fuera del período o secuencia invertida")
            previous = entry.effective_date
            balance = _sum((balance, entry.amount if entry.direction == "deposit" else entry.amount.copy_negate()))
            if balance != entry.balance:
                details.append("Saldo corriente no concilia")
            if entry.reference in references and entry.reference is not None:
                details.append("Referencia repetida; revisar sin eliminar evidencia")
            references.add(entry.reference)
        if balance != summary.final:
            details.append("Cierre del detalle no coincide con resumen")
        for actual, expected, label in (
            (_sum(e.amount for e in entries if e.direction == "deposit"), summary.deposits, "Depósitos"),
            (_sum(e.amount for e in entries if e.direction == "withdrawal"), summary.withdrawals, "Retiros"),
            (_sum(e.amount for e in entries if e.category == "interest"), summary.interest, "Rendimientos"),
        ):
            if actual != expected:
                issues.append(label + " del resumen no coinciden con detalle")
        if _sum((summary.initial, summary.deposits, summary.withdrawals.copy_negate(), summary.withholding.copy_negate())) != summary.final:
            issues.append("Ecuación del resumen no concilia")
        if summary.withholding != 0:
            issues.append("Retención informada: falta validar su desglose y tratamiento en saldo")
        return DidiPreview(identifier, start, end, fingerprint, summary, tuple(entries), disclosure,
                           rates, tuple(issues), tuple(dict.fromkeys(details)), self.lane)
