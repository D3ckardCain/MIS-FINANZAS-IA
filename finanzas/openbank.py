"""Dos lectores independientes de Openbank. Solo producen vistas previas."""
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from io import BytesIO
import re
from hashlib import sha256
import unicodedata

from .ledger import _sum
from .storage import document_id


class FormatError(ValueError):
    pass


def _fold(text):
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c)).lower()


_MONEY = r"-?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}"
_CASH = re.compile(r"\$\s*(" + _MONEY + r")(?![\d,.])")
_DATE = re.compile(r"^\s*(\d{2}/\d{2}/\d{2})(?=\s)")


def _date(value):
    day, month, year = map(int, value.split("/"))
    return date(2000 + year, month, day)


def _money(value):
    return Decimal(value.replace(",", ""))


@dataclass(frozen=True)
class Row:
    effective_date: date
    description: str
    deposit: Decimal
    withdrawal: Decimal
    balance: Decimal
    page: int
    line: int
    category: str

    @property
    def locator(self):
        return f"pagina {self.page}, linea {self.line}"


@dataclass(frozen=True)
class Summary:
    initial: Decimal
    deposits: Decimal
    cash_withdrawals: Decimal
    other_charges: Decimal
    final: Decimal
    interest: Decimal
    withholding: Decimal
    fees: Decimal
    annual_rate_reported: Decimal


@dataclass(frozen=True)
class Preview:
    document_id: str
    lane: str
    period_start: date
    period_end: date
    summary: Summary
    rows: tuple[Row, ...]
    issues: tuple[str, ...]
    account_fingerprint: str | None = None
    recipient_fingerprint: str | None = None
    identity_source: str | None = None

    @property
    def ready_to_import(self):return False

    @property
    def reconciled(self):
        return not self.issues

    @property
    def interest_received(self):
        return _sum(r.deposit for r in self.rows if r.category == "interest")


def _category(description, lane, deposit, withdrawal):
    text = _fold(" ".join(description.split()))
    if text == "abono de intereses" and deposit > 0 and withdrawal == 0:
        return "interest"
    if lane == "debit":
        if text == "retiro a apartado open" and withdrawal > 0 and deposit == 0:
            return "to_investments"
        if text == "abono desde apartado open" and deposit > 0 and withdrawal == 0:
            return "from_investments"
        return "debit_movement"
    if text == "abono desde cuenta debito open light" and deposit > 0 and withdrawal == 0:
        return "from_debit"
    if text == "retiro a cuenta debito open light" and withdrawal > 0 and deposit == 0:
        return "to_debit"
    return "unclassified"


def _summary(text):
    folded = _fold(text)
    labels = {
        "initial": "saldo inicial", "deposits": "depositos",
        "cash_withdrawals": "retiro en efectivo", "other_charges": "otros cargos",
        "final": "saldo final", "interest": "interes aplicable o rendimientos",
        "withholding": "impuestos retenidos", "fees": "comisiones cobradas",
    }
    values = {}
    for name, label in labels.items():
        found = re.findall(r"^\s*" + re.escape(label) + r"\s+\$\s*(" + _MONEY + r")(?![\d,.])",
                           folded, re.MULTILINE)
        if not found or len({_money(v) for v in found}) != 1:
            raise FormatError("Resumen ausente o contradictorio: " + name)
        values[name] = _money(found[0])
    rate = re.findall(r"^\s*tasa bruta de interes anual\s+(\d+(?:\.\d+)?)\s*%", folded, re.MULTILINE)
    if len(rate) != 1:
        raise FormatError("Falta tasa informativa del resumen")
    return Summary(**values, annual_rate_reported=Decimal(rate[0]))


def _raw_rows(text):
    parts = re.split(r"Detalle de tus transacciones", text, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        raise FormatError("Falta tabla en extracción lógica")
    body = re.split(r"Fecha\s*Comisiones|Emitido por|Apartados a plazo fijo", parts[1],
                    maxsplit=1, flags=re.IGNORECASE)[0]
    starts = list(re.finditer(r"(\d{2}/\d{2}/\d{2})", body))
    result = []
    for index, found in enumerate(starts):
        segment = body[found.end():starts[index + 1].start() if index + 1 < len(starts) else len(body)]
        cash = list(_CASH.finditer(segment))
        if len(cash) != 2:
            raise FormatError("Importes no reconocidos en extracción lógica")
        description = " ".join(segment[:cash[0].start()].split())
        result.append((_date(found.group(1)), description, tuple(_money(m.group(1)) for m in cash)))
    return result


class _Reader:
    lane = ""
    title = ""

    def read_pages(self, pages, identifier, *, raw_pages=None):
        """Texto por página conservando columnas; no registra movimientos."""
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError("Identificador documental requerido")
        pages = tuple(pages)
        if raw_pages is not None and len(raw_pages) != len(pages):
            raise FormatError("Extracciones incompatibles")
        all_text="\n".join(pages)
        parent_accounts=set(re.findall(r"Número de cuenta\s+(\d+)",all_text))
        recipients=set(re.findall(r"\bRFC\s+([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})\b",all_text,re.M))
        if len(parent_accounts)>1 or len(recipients)>1:raise FormatError("Identidad Openbank contradictoria")
        account=next(iter(parent_accounts),None);recipient=next(iter(recipients),None)
        account_fp=sha256(("openbank:"+self.lane+":"+account).encode()).hexdigest() if account else None
        recipient_fp=sha256(("openbank-rfc:"+recipient).encode()).hexdigest() if recipient else None
        selected = [(number, text) for number, text in enumerate(pages, 1)
                    if any(_fold(line.strip()) == self.title for line in text.splitlines())
                    and ("detalle de tus transacciones" in _fold(text) or "resumen informativo" in _fold(text))]
        if not selected:
            raise FormatError("Sección ausente: " + self.lane)
        period = None
        summary = None
        rows = []
        for page_number, text in selected:
            periods = re.findall(r"periodo\s+(\d{2}/\d{2}/\d{2})\s*-\s*(\d{2}/\d{2}/\d{2})", _fold(text))
            for start, end in periods:
                candidate = (_date(start), _date(end))
                if candidate[1] < candidate[0] or (period and period != candidate):
                    raise FormatError("Períodos incompatibles")
                period = candidate
            if re.search(r"^\s*resumen informativo\s+mxn\s*$", _fold(text), re.MULTILINE):
                if summary is not None:
                    raise FormatError("Más de un resumen en la misma vista; formato no admitido")
                summary = _summary(text)
            first_row = len(rows)
            lines = text.splitlines()
            header = None
            had_header = False
            current = None
            for line_number, line in enumerate(lines, 1):
                folded = _fold(line)
                if re.match(r"^\s*fecha\s+concepto\s+deposito\s+retiro\s+saldo mxn\s*$", folded):
                    if current:
                        rows.append(current)
                        current = None
                    had_header = True
                    header = tuple(folded.index(label) for label in ("concepto", "deposito", "retiro", "saldo mxn"))
                    continue
                if header is None:
                    continue
                if re.match(r"^\s*(fecha\s+comisiones|emitido por|apartados a plazo fijo)", folded):
                    if current:
                        rows.append(current)
                        current = None
                    header = None
                    continue
                dated = _DATE.match(line)
                if dated:
                    if current:
                        rows.append(current)
                        current = None
                    concept, dep_col, out_col, bal_col = header
                    description = line[concept:dep_col].strip()
                    cells = [line[dep_col:out_col], line[out_col:bal_col], line[bal_col:]]
                    parsed = []
                    for index, cell in enumerate(cells):
                        amounts = _CASH.findall(cell)
                        if len(amounts) > 1 or (cell.strip() and (len(amounts) != 1 or _CASH.fullmatch(cell.strip()) is None)):
                            raise FormatError(f"Columnas no reconocidas en página {page_number}, línea {line_number}")
                        if index == 2 and not amounts:
                            raise FormatError("Movimiento sin saldo")
                        parsed.append(_money(amounts[0]) if amounts else Decimal("0"))
                    deposit, withdrawal, balance = parsed
                    if deposit < 0 or withdrawal < 0 or (deposit > 0) == (withdrawal > 0):
                        raise FormatError("Movimiento sin sentido único de entrada o salida")
                    current = Row(_date(dated.group(1)), description, deposit, withdrawal, balance,
                                  page_number, line_number, "")
                elif line.strip():
                    concept, dep_col, _, _ = header
                    if raw_pages is not None and not line[:concept].strip() and not line[dep_col:].strip():
                        # La extracción lógica determina a qué operación pertenece.
                        pass
                    else:
                        raise FormatError(f"Contenido no reconocido en tabla, página {page_number}, línea {line_number}")
            if current:
                rows.append(current)
            if not had_header:
                # A printed all-zero summary can omit the transaction table.
                # Never interpret an absent/nonzero/malformed table as zero.
                zero_summary=(summary is not None and all(getattr(summary,k)==0 for k in
                    ("initial","deposits","cash_withdrawals","other_charges","final","interest","withholding","fees")))
                if not (zero_summary and re.search(r"^\s*resumen informativo\s+mxn\s*$",_fold(text),re.M)
                        and all(_money(v)==0 for v in _CASH.findall(text))
                        and "detalle de tus transacciones" not in _fold(text)
                        and not re.search(r"\b\d{2}/\d{2}/\d{2}\b",re.sub(r"Periodo[^\n]*","",text,flags=re.I))):
                    raise FormatError("Encabezado de movimientos no reconocido")
            if raw_pages is not None and had_header:
                descriptions = _raw_rows(raw_pages[page_number - 1])
                if len(descriptions) != len(rows) - first_row:
                    raise FormatError("Las extracciones discrepan en el número de movimientos")
                for index, (effective, description, amounts) in enumerate(descriptions, first_row):
                    row = rows[index]
                    if effective != row.effective_date or amounts != (row.deposit or row.withdrawal, row.balance):
                        raise FormatError("Las extracciones discrepan en fechas o importes")
                    rows[index] = replace(row, description=description)
        if period is None or summary is None:
            raise FormatError("Faltan período o resumen de la sección")
        rows = tuple(replace(r, category=_category(r.description, self.lane, r.deposit, r.withdrawal)) for r in rows)
        issues = []
        previous = summary.initial
        for row in rows:
            if not period[0] <= row.effective_date <= period[1]:
                issues.append("Movimiento fuera del período: " + row.locator)
            if _sum((previous, row.deposit, row.withdrawal.copy_negate())) != row.balance:
                issues.append("Saldo por movimiento no conciliado: " + row.locator)
            previous = row.balance
            if self.lane == "investments" and row.category == "unclassified":
                issues.append("Concepto de inversión sin clasificar: " + row.locator)
        if any(a.effective_date > b.effective_date for a, b in zip(rows, rows[1:])):
            issues.append("Orden de fechas no admitido")
        if previous != summary.final:
            issues.append("Saldo final no conciliado")
        total_in = _sum(r.deposit for r in rows)
        expected_in = _sum((summary.deposits, summary.interest))
        # En este formato los intereses no están incluidos en Depósitos.
        if total_in != expected_in:
            issues.append("Total de abonos no conciliado")
        if _sum(r.withdrawal for r in rows) != _sum((summary.cash_withdrawals, summary.other_charges)):
            issues.append("Total de retiros no conciliado")
        if _sum(r.deposit for r in rows if r.category == "interest") != summary.interest:
            issues.append("Intereses del resumen no conciliados")
        if summary.withholding != 0 or summary.fees != 0:
            issues.append("Retenciones o comisiones no nulas requieren formato y detalle específicos")
        return Preview(identifier, self.lane, *period, summary, rows, tuple(issues),account_fp,recipient_fp,
                       ("explicit_debit_account" if self.lane=="debit" else "parent_debit_account_and_product") if account else None)

    def read_image(self, content, *, engine=None):
        from .imaging import read_statement_image
        return read_statement_image(content, "openbank", self.lane, engine=engine)

    def read_pdf(self, content: bytes):
        """PDF textual local; requiere el extra pypdf, sin servicios remotos."""
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            raise FormatError("PDF cifrado: revisión local requerida")
        pages = tuple(page.extract_text(extraction_mode="layout") or "" for page in reader.pages)
        raw = tuple(page.extract_text() or "" for page in reader.pages)
        return self.read_pages(pages, document_id(content), raw_pages=raw)


class OpenbankDebitReader(_Reader):
    lane = "debit"
    title = "cuenta debito open light"


class OpenbankInvestmentReader(_Reader):
    lane = "investments"
    title = "apartado open"


def transfer_candidates(debit: Preview, investments: Preview):
    """Propuestas únicas del mismo documento; no confirman identidad ni escriben."""
    if debit.lane != "debit" or investments.lane != "investments":
        raise ValueError("Se requieren vistas débito e inversiones")
    if debit.document_id != investments.document_id or not debit.reconciled or not investments.reconciled:
        return ()
    candidates = []
    for source in debit.rows:
        pairs = [target for target in investments.rows if source.effective_date == target.effective_date
                 and ((source.category == "to_investments" and target.category == "from_debit"
                       and source.withdrawal == target.deposit)
                      or (source.category == "from_investments" and target.category == "to_debit"
                          and source.deposit == target.withdrawal))]
        if len(pairs) == 1:
            target = pairs[0]
            alternatives = [r for r in debit.rows if r.category == source.category
                            and r.effective_date == source.effective_date
                            and r.deposit == source.deposit and r.withdrawal == source.withdrawal]
            if len(alternatives) == 1:
                candidates.append((source.locator, target.locator))
    return tuple(candidates)
