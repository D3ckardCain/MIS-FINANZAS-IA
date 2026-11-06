"""Hey: cuenta operativa, pagarés y propuestas de reinversión con evidencia."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import re

from .ledger import _sum
from .readers import ReaderError, fold, periods, parse_date

_AMOUNT = r"(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}"
_DATE = r"\d{2}/[A-Za-z]{3}/\d{4}"


def amount(text):
    return Decimal(text.replace(",", ""))


@dataclass(frozen=True)
class HeyCashSummary:
    initial: Decimal
    credits: Decimal
    withdrawals: Decimal
    commissions: Decimal
    other_debits: Decimal
    final: Decimal
    unit: str | None = None


@dataclass(frozen=True)
class HeyInvestmentSummary:
    initial: Decimal
    interest_reported: Decimal
    final: Decimal
    accrued_included_in_final: Decimal
    withholding_reported: Decimal
    allocation: Decimal
    current_contract_total_reported: Decimal
    unit: str | None = None


@dataclass(frozen=True)
class HeyEntry:
    effective_date: date
    description: str
    category: str
    reference: str
    contract_id: str
    debit: Decimal
    credit: Decimal
    balance: Decimal
    page: int
    line: int
    source_extraction: str = "layout"


@dataclass(frozen=True)
class HeyContract:
    id: str
    opened: date
    maturity: date
    days: int
    annual_rate: Decimal
    principal: Decimal
    interest_at_maturity: Decimal
    withholding_at_maturity: Decimal
    net_at_maturity: Decimal
    status_at_cutoff: str
    commission_reported: Decimal
    gat_nominal: Decimal
    gat_real: Decimal
    page: int
    line: int
    source_extraction: str = "plain"


@dataclass(frozen=True)
class RenewalProposal:
    previous_contract: str
    next_contract: str
    effective_date: date
    principal_returned: Decimal
    interest_paid: Decimal
    withholding: Decimal
    reinvested: Decimal
    source_lines: tuple[tuple[int, int], ...]
    needs_review: bool = True


@dataclass(frozen=True)
class HeyDifference:
    check: str
    reported: Decimal
    calculated: Decimal
    page: int
    line: int


@dataclass(frozen=True)
class HeyPreview:
    document_id: str
    period_start: date
    period_end: date
    account_fingerprint: str
    cash_summary: HeyCashSummary
    investment_summary: HeyInvestmentSummary
    portfolio_total_reported: Decimal
    entries: tuple[HeyEntry, ...]
    contracts: tuple[HeyContract, ...]
    renewal_proposals: tuple[RenewalProposal, ...]
    differences: tuple[HeyDifference, ...]
    cash_issues: tuple[str, ...]
    investment_issues: tuple[str, ...]
    lane: str
    currency_markers: tuple[str, ...] = ()

    @property
    def summary(self):
        return self.cash_summary if self.lane == "debit" else self.investment_summary

    @property
    def issues(self):
        return () if self.lane == "debit" else self.investment_issues

    @property
    def detail_issues(self):
        return self.cash_issues

    @property
    def reconciled(self):
        return not self.issues and not self.detail_issues

    @property
    def detail_reconciled(self):
        return not self.cash_issues

    @property
    def ready_to_import(self):
        return False


def _label(text, label):
    found = re.findall(re.escape(label) + r"\s*\$\s*(" + _AMOUNT + r")", text)
    if len(found) != 1:
        raise ReaderError("Resumen Hey incompleto o ambiguo: " + label)
    return amount(found[0])


class HeyReader:
    def __init__(self, lane="investments"):
        if lane not in ("debit", "investments"):
            raise ReaderError("Vista Hey desconocida")
        self.lane = lane

    def read_image(self, content, *, engine=None):
        from .imaging import read_statement_image
        return read_statement_image(content, "hey", self.lane, engine=engine)

    def read_pdf(self, content, *, password=None):
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            pdf = PdfReader(BytesIO(content))
            if pdf.is_encrypted and (password is None or not pdf.decrypt(password)):
                raise ReaderError("PDF Hey protegido: contraseña requerida o no válida")
            raw = tuple(p.extract_text() or "" for p in pdf.pages)
            layout = tuple(p.extract_text(extraction_mode="layout") or "" for p in pdf.pages)
        except PyPdfError as error:
            raise ReaderError("PDF Hey no legible") from error
        return self.read_pages(layout, sha256(content).hexdigest(), raw_pages=raw)

    def read_pages(self, pages, identifier, *, raw_pages=None):
        pages = tuple(pages)
        raw_pages = tuple(raw_pages) if raw_pages is not None else pages
        text, raw = "\n".join(pages), "\n".join(raw_pages)
        if not re.search(r"hey,? banco", fold(text)):
            raise ReaderError("Identidad Hey ausente")
        ranges = periods(raw)
        account = set(re.findall(r"CLABE\s+(\d{18})", text))
        if len(ranges) != 1 or len(account) != 1 or len(raw_pages) != len(pages):
            raise ReaderError("Cuenta, fechas o extracciones Hey no compatibles")
        start, end = ranges[0]
        if (start.year, start.month) != (end.year, end.month):
            raise ReaderError("Fechas de día sin mes requieren un período mensual único")
        fingerprint = sha256(("hey:" + account.pop()).encode()).hexdigest()
        graphs = [p[p.index("Gráfico Transaccional"):].split("MANDATO ESPECIAL", 1)[0]
                  for p in pages if "Gráfico Transaccional" in p]
        if len(graphs) != 1:
            raise ReaderError("Resumen operativo Hey ausente o ambiguo")
        graph = graphs[0]
        cash_summary = HeyCashSummary(*(_label(graph, label) for label in (
            "Saldo Inicial", "+ Abonos", "- Retiros", "- Comisiones Efectivamente Cobradas", "- Otros Cargos", "= Saldo Final")))
        investment_block = pages[0].split("Inversiones", 1)[-1].split("* Los intereses devengados", 1)[0]
        summaries = []
        for line in investment_block.splitlines():
            values = re.findall(_AMOUNT, line)
            if len(values) == 6 and not re.sub(_AMOUNT, "", line).strip():
                summaries.append(tuple(map(amount, values)))
        if len(summaries) != 1:
            raise ReaderError("Resumen de pagarés Hey no reconocido")
        live_total = re.findall(r"Total Vigentes\s+(" + _AMOUNT + r")", text)
        if len(live_total) != 1:
            raise ReaderError("Total Vigentes ausente o ambiguo")
        investment_summary = HeyInvestmentSummary(*summaries[0], amount(live_total[0]))
        markers={m.upper() for m in re.findall(r'\b(?:moneda|divisa)\s*:?\s*([A-Z]{3})\b',text,re.I)}
        if re.search(r'\bmoneda\s*:?\s*(?:nacional|pesos mexicanos)\b',fold(text)):markers.add('MXN')
        from dataclasses import replace
        unit='MXN' if markers=={'MXN'} else None
        cash_summary=replace(cash_summary,unit=unit)
        investment_summary=replace(investment_summary,unit=unit)
        portfolio = re.findall(r"Total Portafolio\s+(" + _AMOUNT + r")", pages[0])
        if len(portfolio)!=1:
            raise ReaderError("Total Portafolio Hey ausente o ambiguo")
        portfolio_total = amount(portfolio[0])
        rates, contracts = {}, []
        disclosure = re.compile(r"^\s*(\d{7,})\s+(\d+\.\d+)%\s+(" + _AMOUNT + r")\s+(\d+\.\d+)%\s+Antes de impuestos\s+(\d+\.\d+)%\s+Antes de impuestos\s*$")
        for page in pages:
            for line in page.splitlines():
                match = disclosure.fullmatch(line)
                if match:
                    if match[1] in rates:
                        raise ReaderError("Condiciones de contrato repetidas")
                    rates[match[1]] = tuple(map(amount, match.groups()[1:]))
        contract_pattern = re.compile(r"^\s*(\d{7,})\s+(\d+\.\d+)%\s+(\d+)\s+(" + _AMOUNT + r")\s+(" + _AMOUNT + r")\s+(" + _AMOUNT + r")\s+(" + _AMOUNT + r")\s*$")
        for page_number, page in enumerate(raw_pages, 1):
            if "CAPITAL" not in page or "INTERES" not in page or "INVERSION" not in page:
                continue
            for line_number, line in enumerate(page.splitlines(), 1):
                if not re.match(r"^\s*" + _DATE, line):
                    continue
                dates = re.findall(_DATE, line)
                cleaned = re.sub(_DATE, " ", line)
                match = contract_pattern.fullmatch(cleaned)
                if len(dates) != 2 or not match or match[1] not in rates:
                    raise ReaderError("Fila de contrato Hey no reconocida")
                opened, maturity = map(parse_date, dates)
                contract_id, rate_text, days, principal, interest, retained, total = match.groups()
                reported_rate, commission, gat_nominal, gat_real = rates[contract_id]
                if reported_rate != amount(rate_text) or (maturity - opened).days != int(days):
                    raise ReaderError("Tasa/plazo de contrato contradice condiciones o fechas")
                status = "matured_in_period" if start <= maturity <= end else ("active" if opened <= end < maturity else "outside_period")
                contracts.append(HeyContract(contract_id, opened, maturity, int(days), reported_rate,
                    *map(amount, (principal, interest, retained, total)), status, commission, gat_nominal, gat_real,
                    page_number, line_number))
        by_id = {c.id:c for c in contracts}
        if not contracts or len(by_id) != len(contracts) or set(by_id) != set(rates):
            raise ReaderError("Contratos/condiciones Hey incompletos o repetidos")
        cash_issues, investment_issues, differences, entries = [], [], [], []
        category_labels = (("Pago Cap. de Inversion", "principal_repayment"),
                           ("Pago Intereses de Inv.", "interest_paid"),
                           ("Ret. ISR de Inversion", "withholding"),
                           ("Apertura de Inversion Hey", "investment_opening"))
        for page_number, page in enumerate(pages, 1):
            if "CARGOS" not in page or "ABONOS" not in page or "SALDO" not in page:
                continue
            headers = [line for line in page.splitlines() if "CARGOS" in line and "ABONOS" in line and "SALDO" in line]
            if len(headers) != 1:
                raise ReaderError("Columnas operativas Hey ambiguas")
            header = headers[0]
            debit_start, credit_start, balance_start = (header.index(s) for s in ("CARGOS", "ABONOS", "SALDO"))
            # El encabezado está centrado; sus límites medios separan columnas.
            debit_boundary = (debit_start + len("CARGOS")/2 + credit_start + len("ABONOS")/2)/2
            credit_boundary = (credit_start + len("ABONOS")/2 + balance_start + len("SALDO")/2)/2
            for line_number, line in enumerate(page.splitlines(), 1):
                match = re.match(r"^\s*(\d{2})\s+((?:DOC|TRA)\s+(\d+)-.*)$", line)
                if not match:
                    if re.match(r"^\s*\d{2}\s+", line):
                        cash_issues.append("Fila operativa Hey no reconocida")
                    continue
                values = list(re.finditer(_AMOUNT, line))
                if len(values) != 2:
                    cash_issues.append("Importe/saldo Hey no reconocidos")
                    continue
                first, last = values
                if last.start() < credit_boundary:
                    cash_issues.append("Saldo fuera de su columna")
                    continue
                direction = "debit" if (first.start()+first.end())/2 < debit_boundary else "credit"
                try:
                    when = date(start.year,start.month,int(match[1]))
                except ValueError as error:
                    raise ReaderError("Día Hey inválido") from error
                if not start <= when <= end:
                    cash_issues.append("Día Hey fuera del período")
                description = line[match.start(2):first.start()].strip()
                category = next((kind for label,kind in category_labels if label in description), "unknown")
                candidates = [c.id for c in contracts if match[3].endswith(c.id)]
                if len(candidates) != 1:
                    cash_issues.append("Referencia no vinculable a contrato único")
                if category == "unknown":
                    cash_issues.append("Concepto Hey pendiente de mapear")
                debit, credit = (amount(first[0]),Decimal(0)) if direction == "debit" else (Decimal(0),amount(first[0]))
                if (category in ("principal_repayment","interest_paid") and direction != "credit") or (category in ("withholding","investment_opening") and direction != "debit"):
                    cash_issues.append("Columna y tipo de movimiento Hey contradictorios")
                entries.append(HeyEntry(when,description,category,match[3],candidates[0] if len(candidates)==1 else "",
                                        debit,credit,amount(last[0]),page_number,line_number))
        def check(label, reported, calculated, target, page=1, line=0):
            if reported != calculated:
                target.append(label)
                differences.append(HeyDifference(label,reported,calculated,page,line))
        if not entries:
            cash_issues.append("Detalle operativo Hey vacío")
        balance, previous, identities = cash_summary.initial, start, set()
        for entry in entries:
            if entry.effective_date < previous:
                cash_issues.append("Secuencia operativa Hey invertida")
            previous = entry.effective_date
            balance = _sum((balance,entry.credit,entry.debit.copy_negate()))
            check("Saldo corriente Hey no concilia",entry.balance,balance,cash_issues,entry.page,entry.line)
            key = (entry.reference,entry.category)
            if key in identities:
                cash_issues.append("Referencia/categoría Hey repetida; conservar evidencia y revisar")
            identities.add(key)
        check("Saldo final operativo Hey no concilia",cash_summary.final,balance,cash_issues)
        check("Abonos del resumen Hey no coinciden",cash_summary.credits,_sum(e.credit for e in entries),cash_issues)
        check("Cargos del resumen Hey no coinciden",_sum((cash_summary.withdrawals,cash_summary.commissions,cash_summary.other_debits)),_sum(e.debit for e in entries),cash_issues)
        def total(kind):return _sum(_sum((e.credit,e.debit)) for e in entries if e.category==kind)
        check("ISR del portafolio frente a retenciones pagadas no coincide",investment_summary.withholding_reported,total("withholding"),investment_issues)
        check("Intereses reportados no coinciden con interés pagado menos retención",investment_summary.interest_reported,
              _sum((total("interest_paid"),total("withholding").copy_negate())),investment_issues)
        active = [c for c in contracts if c.status_at_cutoff=="active"]
        check("Capital vigente más devengado difiere del saldo actual",investment_summary.final,
              _sum((*[c.principal for c in active],investment_summary.accrued_included_in_final)),investment_issues)
        check("Total Portafolio difiere de cuenta e inversiones actuales",portfolio_total,
              _sum((cash_summary.final,investment_summary.final)),investment_issues)
        check("Total Vigentes difiere de netos al vencimiento",investment_summary.current_contract_total_reported,
              _sum(c.net_at_maturity for c in active),investment_issues)
        for contract in contracts:
            check("Capital más interés menos ISR no coincide con neto del contrato",contract.net_at_maturity,
                  _sum((contract.principal,contract.interest_at_maturity,contract.withholding_at_maturity.copy_negate())),investment_issues,contract.page,contract.line)
            relevant = [e for e in entries if e.contract_id==contract.id]
            if contract.status_at_cutoff=="matured_in_period":
                for kind,expected in (("principal_repayment",contract.principal),("interest_paid",contract.interest_at_maturity),("withholding",contract.withholding_at_maturity)):
                    rows = [e for e in relevant if e.category==kind]
                    if len(rows)!=1 or rows[0].effective_date!=contract.maturity:
                        investment_issues.append("Vencimiento sin pago/retención único en fecha documental")
                    else:check("Pago/retención difiere del contrato",expected,_sum((rows[0].credit,rows[0].debit)),investment_issues,rows[0].page,rows[0].line)
            if start<=contract.opened<=end:
                rows = [e for e in relevant if e.category=="investment_opening"]
                if len(rows)!=1 or rows[0].effective_date!=contract.opened:
                    investment_issues.append("Apertura sin cargo único en fecha documental")
                else:check("Cargo de apertura difiere de capital contractual",contract.principal,rows[0].debit,investment_issues,rows[0].page,rows[0].line)
            if contract.status_at_cutoff=="active" and any(e.category in ("interest_paid","principal_repayment","withholding") for e in relevant):
                investment_issues.append("Contrato vigente presenta pago no explicado por el formato reconocido")
            if contract.status_at_cutoff=="outside_period":
                investment_issues.append("Contrato fuera del alcance temporal reconocido")
        proposals = []
        for offset in range(len(entries)-3):
            rows = entries[offset:offset+4]
            if [e.category for e in rows]!=["principal_repayment","interest_paid","withholding","investment_opening"]:
                continue
            if len({e.effective_date for e in rows})!=1 or len({e.contract_id for e in rows[:3]})!=1 or rows[0].contract_id==rows[3].contract_id:
                continue
            net = _sum((rows[0].credit,rows[1].credit,rows[2].debit.copy_negate()))
            if net==rows[3].debit and all(e.contract_id for e in rows):
                proposals.append(RenewalProposal(rows[0].contract_id,rows[3].contract_id,rows[0].effective_date,
                    rows[0].credit,rows[1].credit,rows[2].debit,rows[3].debit,tuple((e.page,e.line) for e in rows)))
        if cash_issues:
            proposals = []
        return HeyPreview(identifier,start,end,fingerprint,cash_summary,investment_summary,portfolio_total,tuple(entries),tuple(contracts),
            tuple(proposals),tuple(differences),tuple(dict.fromkeys(cash_issues)),tuple(dict.fromkeys(investment_issues)),self.lane,tuple(sorted(markers)))
