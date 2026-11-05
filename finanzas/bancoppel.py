"""BanCoppel: control del detalle de débito, sin inferir aportaciones externas."""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import re

from .ledger import _sum
from .readers import fold, periods, ReaderError


_AMOUNT = r"(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}"
_ROW = re.compile(r"^\s*(\d{2})/(\d{2})\s+(" + _AMOUNT + r")\s+(" + _AMOUNT + r")\s*$")


def _decimal(value):
    return Decimal(value.replace(",", ""))


@dataclass(frozen=True)
class BankSummary:
    initial: Decimal
    deposits: Decimal
    withdrawals: Decimal
    interest: Decimal
    commissions: Decimal
    commission_vat: Decimal
    final: Decimal
    page: int
    interest_gross: Decimal
    withholding: Decimal
    annual_rate_reported: Decimal


@dataclass(frozen=True)
class DebitEntry:
    effective_date: date
    amount: Decimal
    balance: Decimal
    direction: str
    category: str
    description: str
    page: int
    line: int


@dataclass(frozen=True)
class BanCoppelPreview:
    document_id: str
    period_start: date
    period_end: date
    summary: BankSummary
    entries: tuple[DebitEntry, ...]
    issues: tuple[str, ...]
    detail_issues: tuple[str, ...]
    account_fingerprint: str | None
    lane: str = "debit"

    @property
    def reconciled(self):
        return not self.issues and not self.detail_issues

    @property
    def detail_reconciled(self):
        return not self.detail_issues

    @property
    def ready_to_import(self):
        return False


def _event_date(month, day, start, end):
    candidates = []
    for year in range(start.year, end.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if start <= candidate <= end:
            candidates.append(candidate)
    if len(candidates) != 1:
        raise ReaderError("Fecha MM/DD fuera del período o ambigua")
    return candidates[0]


def _category(description, direction):
    text = fold(description)
    if "pago de intereses" in text and direction == "deposit":
        return "interest"
    if "iva comisiones" in text and direction == "withdrawal":
        return "commission_vat"
    if direction == "withdrawal" and ("comision" in text or "deposito de efectivo oxxo" in text
                                      or text.startswith("administracion renta")):
        return "commission"
    if "devolucion spei" in text:
        return "transfer_return"
    if "spei" in text or "traspaso" in text:
        return "transfer"
    if direction == "deposit" and ("efectivo" in text or "corresponsales" in text):
        return "cash_deposit"
    return "debit_movement"


class BanCoppelDebitReader:
    def read_pdf(self, content):
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise ReaderError("PDF cifrado")
            pages = tuple(page.extract_text() or "" for page in reader.pages)
        except PyPdfError as error:
            raise ReaderError("PDF BanCoppel no legible") from error
        return self.read_pages(pages, sha256(content).hexdigest())

    def read_image(self, content, *, engine=None):
        from .imaging import read_statement_image
        return read_statement_image(content, "bancoppel", "debit", engine=engine)

    def read_pages(self, pages, identifier):
        pages = tuple(pages)
        text = "\n".join(pages)
        if "bancoppel" not in fold(text):
            raise ReaderError("Identidad BanCoppel ausente")
        ranges = periods(text)
        if len(ranges) != 1:
            raise ReaderError("Se requiere un período documental único")
        start, end = ranges[0]
        account = re.search(r"N[uú]mero\s+de\s+Cuenta:\s*CLABE:\s*(\d{6,})", text, re.I)
        account_fingerprint = sha256(("bancoppel:" + account[1]).encode()).hexdigest() if account else None
        summaries = []
        for number, page in enumerate(pages, 1):
            if "resumen de la cuenta" not in fold(page):
                continue
            # Este formato emite etiquetas y después los siete importes en orden.
            normalized = page.replace("\xa0", " ")
            match = re.search(r"Saldo\s+Anterior\s*\n(.*?)\nHoja", normalized, re.S | re.I)
            if not match:
                raise ReaderError("Resumen BanCoppel cambió de estructura")
            values = re.findall(r"^\s*(" + _AMOUNT + r")\s*$", match[1], re.M)
            if len(values) != 7:
                raise ReaderError("Resumen BanCoppel incompleto")
            interest_part = normalized.rsplit("Intereses del Periodo", 1)[-1].split("Utiliza", 1)[0]
            interest_values = re.findall(r"^\s*(" + _AMOUNT + r")\s*$", interest_part, re.M)
            rate = re.search(r"([\d.]+)\s*%", interest_part)
            if len(interest_values) != 4 or rate is None:
                raise ReaderError("Detalle de interés/retención/tasa no reconocido")
            _, gross, retained, net = map(_decimal, interest_values)
            if _sum((gross, retained.copy_negate())) != net or net != _decimal(values[3]):
                raise ReaderError("Interés bruto, retención y neto contradictorios")
            summary = BankSummary(*map(_decimal, values), page=number, interest_gross=gross,
                                  withholding=retained, annual_rate_reported=Decimal(rate[1]))
            repeated = re.search(r"Saldo inicial de\s*\$\s*(" + _AMOUNT + r")", normalized, re.I)
            if not repeated or _decimal(repeated[1]) != summary.initial:
                raise ReaderError("Saldo inicial contradictorio en resumen")
            summaries.append(summary)
        if len(summaries) != 1:
            raise ReaderError("Se requiere un resumen BanCoppel único")
        summary = summaries[0]
        raw = []
        current = None
        for number, page in enumerate(pages, 1):
            if "detalle de movimientos" not in fold(page):
                continue
            for line_number, line in enumerate(page.splitlines(), 1):
                line = line.replace("\xa0", " ")
                found = _ROW.fullmatch(line)
                if found:
                    if current:
                        raw.append(current)
                    month, day, amount, balance = found.groups()
                    current = [_event_date(int(month), int(day), start, end),
                               _decimal(amount), _decimal(balance), [], number, line_number]
                elif re.match(r"^\s*\d{2}/\d{2}", line):
                    raise ReaderError("Fila de movimientos BanCoppel no reconocida")
                elif current:
                    compact = fold(line)
                    if compact.startswith(("hoja ", "utiliza tu tarjeta", "detalle de movimientos",
                                           "periodo", "fecha", "moneda nacional", "retiros depositos",
                                           "movimientos en proceso")) or not compact:
                        continue
                    if " al " in compact and periods(compact):
                        continue
                    current[3].append(line.strip())
        if current:
            raw.append(current)
        if not raw:
            raise ReaderError("Detalle ausente; no se presume una cuenta sin movimientos")
        entries, detail_issues, issues = [], [], []
        if summary.withholding:
            issues.append("Retención no nula: validar su representación en el detalle antes de importar")
        previous = summary.initial
        for effective, amount, balance, description, page, line in reversed(raw):
            delta = _sum((balance, previous.copy_negate()))
            if amount > 0 and delta == amount:
                direction = "deposit"
            elif amount > 0 and delta == amount.copy_negate():
                direction = "withdrawal"
            else:
                direction = "unresolved"
                detail_issues.append(f"Saldo/importe no conciliado en página {page}, línea {line}")
            desc = " ".join(description)
            entries.append(DebitEntry(effective, amount, balance, direction,
                                      _category(desc, direction), desc, page, line))
            previous = balance
        if any(a.effective_date > b.effective_date for a, b in zip(entries, entries[1:])):
            detail_issues.append("Orden inverso del documento no reconocido")
        if previous != summary.final:
            detail_issues.append("Detalle y saldo final difieren")
        expected = _sum((summary.initial, summary.deposits, summary.interest,
                         summary.withdrawals.copy_negate(), summary.commissions.copy_negate(),
                         summary.commission_vat.copy_negate()))
        if expected != summary.final:
            issues.append("La ecuación del resumen no coincide con su saldo final")
        def total(direction, category=None):
            return _sum(entry.amount for entry in entries if entry.direction == direction
                        and (category is None or entry.category == category))
        if total("deposit", "interest") != summary.interest:
            issues.append("Intereses del detalle y resumen difieren")
        if _sum((total("deposit"), total("deposit", "interest").copy_negate())) != summary.deposits:
            issues.append("Depósitos del detalle y resumen difieren")
        if total("withdrawal", "commission") != summary.commissions:
            issues.append("Comisiones del detalle y resumen difieren")
        if total("withdrawal", "commission_vat") != summary.commission_vat:
            issues.append("IVA de comisiones del detalle y resumen difiere")
        ordinary = _sum((total("withdrawal"), total("withdrawal", "commission").copy_negate(),
                         total("withdrawal", "commission_vat").copy_negate()))
        if ordinary != summary.withdrawals:
            issues.append("Retiros del detalle y resumen difieren")
        return BanCoppelPreview(identifier, start, end, summary, tuple(entries),
                               tuple(issues), tuple(detail_issues), account_fingerprint)
