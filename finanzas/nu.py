"""Nu: resumen consolidado y evidencia separada, sin importar Cajitas a ciegas."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import re

from .ledger import _sum
from .readers import ReaderError,fold,periods,parse_date

_MONEY=re.compile(r"[+−-]?\s*\$\s*(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}")
_ROW=re.compile(r"^[ \t]*(\d{2})[ \t]+([A-Z]{3})[ \t]+(\d{4})[ \t]+(.*)$")


def money(text):return Decimal(re.sub(r"[\s$,]","",text).replace("−","-"))


def value(text,key):
    matches=re.findall(re.escape(key)+r"\s+("+_MONEY.pattern+r")",text)
    if len(matches)!=1:raise ReaderError("Campo Nu ausente o ambiguo: "+key)
    return money(matches[0])


@dataclass(frozen=True)
class NuSummary:
    initial: Decimal
    final: Decimal
    deposits: Decimal
    expenses_printed: Decimal
    commissions: Decimal
    net_income: Decimal
    gross_income: Decimal
    retention: Decimal
    retention_printed: Decimal
    interest_rate_reported: Decimal
    interest_rate_label: str
    isr_rate_reported: Decimal
    cash_reported: Decimal
    cajitas_reported: Decimal
    guarantee_reported: Decimal | None
    available_cajitas: Decimal | None
    frozen_cajitas: Decimal | None
    gat_nominal: Decimal | None
    gat_real: Decimal | None
    unit: str = "MXN"


@dataclass(frozen=True)
class NuEvent:
    evidence_id: str
    effective_date: date
    section: str
    category: str
    description_printed: str
    value_candidates: tuple[Decimal, ...]
    maturity_candidate: date | None
    page: int
    line: int


@dataclass(frozen=True)
class NuDifference:
    check: str
    reported: Decimal
    calculated: Decimal


@dataclass(frozen=True)
class NuPreview:
    document_id: str
    period_start: date
    period_end: date
    account_fingerprint: str
    summary: NuSummary
    account_events: tuple[NuEvent, ...]
    investment_events: tuple[NuEvent, ...]
    differences: tuple[NuDifference, ...]
    summary_issues: tuple[str, ...]
    composition_issues: tuple[str, ...]
    detail_issues: tuple[str, ...]
    lane: str
    shared_account: bool = True

    @property
    def entries(self):return self.account_events if self.lane=="debit" else self.investment_events

    @property
    def issues(self):return self.summary_issues+self.composition_issues

    @property
    def summary_reconciled(self):return not self.summary_issues

    @property
    def detail_reconciled(self):return not self.detail_issues

    @property
    def reconciled(self):return not self.issues and not self.detail_issues

    @property
    def ready_to_import(self):return False


def kind(description):
    text=fold(description)
    if "congelaste saldo" in text:return "freeze_evidence"
    if "descongelamos saldo" in text:return "unfreeze_evidence"
    if "credito con garantia" in text or "cajita nu credito" in text:return "guarantee_evidence"
    if "deposito en cajita" in text or "retiro de cajita" in text:return "cajita_transfer_evidence"
    if "deposito spei" in text or "transferencia spei" in text:return "transfer_evidence"
    return "unmapped_evidence"


class NuReader:
    def __init__(self,lane="investments"):
        if lane not in ("debit","investments"):raise ReaderError("Vista Nu desconocida")
        self.lane=lane

    def read_image(self,content,*,engine=None):
        from .imaging import read_statement_image
        return read_statement_image(content,"nu",self.lane,engine=engine)

    def read_pdf(self,content):
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            pdf=PdfReader(BytesIO(content))
            if pdf.is_encrypted:raise ReaderError("PDF cifrado")
            pages=tuple(p.extract_text(extraction_mode="layout") or "" for p in pdf.pages)
        except PyPdfError as error:raise ReaderError("PDF Nu no legible") from error
        return self.read_pages(pages,sha256(content).hexdigest())

    def read_pages(self,pages,identifier):
        pages=tuple(pages);text="\n".join(pages)
        if not pages or "nu mexico financiera" not in fold(text):raise ReaderError("Identidad Nu ausente")
        headers="\n".join(l for l in text.splitlines() if re.search(r"\bDEL\s+\d{2}\s+AL\s+\d{2}\s+[A-Z]{3}\s+\d{4}",l))
        ranges=periods(headers);accounts=set(re.findall(r"Cuenta Nu:\s*(\d+)",text))
        if len(ranges)!=1 or len(accounts)!=1:raise ReaderError("Cuenta/período Nu ausente o ambiguo")
        start,end=ranges[0];fingerprint=sha256(("nu:"+accounts.pop()).encode()).hexdigest()
        first=pages[0];income=text.split("DINERO GENERADO EN TU CUENTA NU",1)
        if len(income)!=2:raise ReaderError("Resumen de rendimiento Nu ausente")
        income=income[1].split("GANANCIA ANUAL TOTAL",1)[0]
        gross=re.search(r"Dinero generado antes de impuestos\s*\((Interés Bruto(?: Anual)? de ([\d.,]+)%)\)\s*("+_MONEY.pattern+r")",income)
        tax=re.search(r"Impuestos sobre el dinero generado\s*\(ISR de ([\d.,]+)%\)\s*("+_MONEY.pattern+r")",income)
        if not gross or not tax:raise ReaderError("Interés/retención Nu no reconocidos")
        positions=[];lines=first.splitlines()
        for index,line in enumerate(lines):
            if "En su Cuenta" in line and ("En Cajitas" in line or "Total Cajitas" in line):
                following=next((l for l in lines[index+1:index+6] if l.strip()),"")
                positions.append(tuple(money(x) for x in _MONEY.findall(following)))
        if len(positions)!=1 or len(positions[0]) not in (2,3):raise ReaderError("Distribución de saldos Nu no reconocida")
        cash,cajitas=positions[0][:2];guarantee=positions[0][2] if len(positions[0])==3 else None
        optional=lambda key:value(first,key) if key in first else None
        def gat(key):
            found=re.findall(re.escape(key)+r"\s+([\d.,]+)%",text)
            if len(found)>1:raise ReaderError("GAT Nu ambiguo")
            return Decimal(found[0].replace(",",".")) if found else None
        summary=NuSummary(value(first,"Saldo inicial"),value(first,"Saldo al generar este estado de cuenta"),
            value(first,"Depósitos"),value(first,"Gastos"),value(first,"Comisiones cobradas por Nu"),
            value(first,"Dinero generado este mes"),money(gross[3]),abs(money(tax[2])),money(tax[2]),
            Decimal(gross[2].replace(",",".")),gross[1],Decimal(tax[1].replace(",",".")),cash,cajitas,guarantee,
            optional("Disponible 24/7"),optional("Congelado"),gat("GAT Nominal"),gat("GAT Real"))
        summary_issues=[];composition=[];differences=[]
        def check(key,reported,calculated,target):
            if reported!=calculated:target.append(key);differences.append(NuDifference(key,reported,calculated))
        check("Ecuación del resumen consolidado Nu no concilia",summary.final,
              _sum((summary.initial,summary.deposits,summary.expenses_printed,summary.net_income,summary.commissions.copy_negate())),summary_issues)
        check("Bruto menos retención Nu no coincide con neto",summary.net_income,
              _sum((summary.gross_income,summary.retention.copy_negate())),summary_issues)
        check("Neto Nu del anexo difiere de portada",summary.net_income,value(income,"Dinero generado este mes"),summary_issues)
        check("Distribución de Cuenta/Cajitas/garantía difiere del total Nu",summary.final,
              _sum(v for v in (cash,cajitas,guarantee) if v is not None),composition)
        if summary.available_cajitas is not None and summary.frozen_cajitas is not None:
            check("Disponible más congelado difiere de Total Cajitas",cajitas,_sum((summary.available_cajitas,summary.frozen_cajitas)),composition)
        elif summary.available_cajitas is not None or summary.frozen_cajitas is not None:composition.append("Distribución disponible/congelado parcial")
        if summary.commissions!=0:summary_issues.append("Comisión Nu no nula requiere mapeo de su inclusión en gastos")
        account_events=[];investment_events=[];section=None;current=None
        def finish():
            nonlocal current
            if current is None:return
            when,area,parts,page,line=current;description=" ".join(parts)
            values=tuple(money(x) for x in _MONEY.findall(description))
            maturity=re.search(r"congelaste saldo hasta el\s+(\d{2}\s+[A-Z]{3}\s+\d{4})",description,re.I)
            proposed=parse_date(maturity[1]) if maturity else None
            event=NuEvent(sha256(f'{identifier}:{page}:{line}'.encode()).hexdigest(),when,area,kind(description),description,values,proposed,page,line)
            (account_events if area=="account" else investment_events).append(event);current=None
        for pno,page in enumerate(pages[1:],2):
            for lno,line in enumerate(page.splitlines(),1):
                normalized=fold(line)
                if normalized.startswith("dinero generado en tu cuenta nu"):finish();section=None
                elif "movimientos en tu cuenta" in normalized:finish();section="account"
                elif "movimientos de tus cajitas" in normalized:finish();section="cajitas"
                elif "movimientos de tu cajita nu credito" in normalized:finish();section="guarantee"
                if normalized.startswith("nu mexico financiera") or "saldo promedio del periodo" in normalized:
                    finish();continue
                if section is None:continue
                match=_ROW.match(line)
                if match:
                    finish();when=parse_date(f'{match[1]} {match[2]} {match[3]}')
                    current=(when,section,[match[4]],pno,lno)
                elif current is not None and line.strip():
                    if not re.search(r"Cuenta Nu:|\d+ de \d+|MONTO EN PESOS|^\s*FECHA",line):current[2].append(line.strip())
            finish()
        detail=["Revisión económica por Cajita/garantía y pareo de movimientos internos pendientes; no importar ni sumar secciones"]
        if any(not start<=e.effective_date<=end for e in account_events+investment_events):detail.append("Fecha de evidencia Nu fuera del período")
        if any(len(e.value_candidates)!=1 for e in account_events+investment_events):detail.append("Evidencia Nu con importe ausente/ambiguo, conservada sin convertir en cero")
        return NuPreview(identifier,start,end,fingerprint,summary,tuple(account_events),tuple(investment_events),tuple(differences),
            tuple(dict.fromkeys(summary_issues)),tuple(dict.fromkeys(composition)),tuple(detail),self.lane)
