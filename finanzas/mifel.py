"""Mifel: cuenta a la vista remunerada y rangos de interés publicados."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import re

from .coverage import CoverageReview, review_coverage
from .ledger import _sum
from .readers import ReaderError, fold, periods

_AMT=r"(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}"
_ROW=re.compile(r"^[ \t]*(\d{2}/\d{2}/\d{4})[ \t]+([A-Z][A-Z0-9]*-\d+)[ \t]+",re.M)


def amount(text):return Decimal(text.replace(",",""))


def label(text,key,percent=False):
    prefix=r"(?m)^\s*" if key=="Mesa de dinero" else ""
    matches=re.findall(prefix+re.escape(key)+r"\s+("+_AMT+r")"+(r"%" if percent else ""),text)
    if len(matches)!=1:raise ReaderError("Resumen Mifel incompleto o ambiguo: "+key)
    return amount(matches[0])


@dataclass(frozen=True)
class MifelSummary:
    initial: Decimal
    final: Decimal
    credits: Decimal
    withdrawals: Decimal
    gross_interest: Decimal
    withholding: Decimal
    annual_rate_reported: Decimal
    gat_nominal: Decimal
    gat_real: Decimal
    average_balance: Decimal
    commissions_reported: Decimal
    vat_reported: Decimal
    portfolio_initial_reported: Decimal
    portfolio_final_reported: Decimal
    other_positions: tuple[tuple[str,Decimal], ...]
    unit: str = "MXN"


@dataclass(frozen=True)
class MifelEntry:
    effective_date: date
    reference: str
    description_printed: str
    category: str
    debit: Decimal | None
    credit: Decimal | None
    balance: Decimal
    accrual_start: date | None
    accrual_end: date | None
    page: int
    line: int

    @property
    def delta(self):
        return _sum(x for x in (self.credit,None if self.debit is None else self.debit.copy_negate()) if x is not None)


@dataclass(frozen=True)
class MifelIncome:
    effective_date: date
    reference_root: str
    interest_reference: str
    withholding_reference: str
    gross: Decimal
    withholding: Decimal
    net: Decimal
    accrual_start: date
    accrual_end: date
    source_lines: tuple[tuple[int,int], ...]


@dataclass(frozen=True)
class MifelDifference:
    check: str
    reported: Decimal
    calculated: Decimal
    page: int
    line: int


@dataclass(frozen=True)
class MifelPreview:
    document_id: str
    period_start: date
    period_end: date
    account_fingerprint: str
    summary: MifelSummary
    entries: tuple[MifelEntry, ...]
    income_groups: tuple[MifelIncome, ...]
    differences: tuple[MifelDifference, ...]
    issues: tuple[str, ...]
    detail_issues: tuple[str, ...]
    lane: str
    shared_account: bool = True
    product: str = "cuenta_a_la_vista_remunerada"

    @property
    def reconciled(self):return not self.issues and not self.detail_issues

    @property
    def detail_reconciled(self):return not self.detail_issues

    @property
    def ready_to_import(self):return False


class MifelReader:
    def __init__(self,lane="investments"):
        if lane not in ("debit","investments"):raise ReaderError("Vista Mifel desconocida")
        self.lane=lane

    def read_image(self,content,*,engine=None):
        from .imaging import read_statement_image
        return read_statement_image(content,"mifel",self.lane,engine=engine)

    def read_pdf(self,content):
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            pdf=PdfReader(BytesIO(content))
            if pdf.is_encrypted:raise ReaderError("PDF cifrado")
            pages=tuple(p.extract_text(extraction_mode="layout") or "" for p in pdf.pages)
            raw=tuple(p.extract_text() or "" for p in pdf.pages)
        except PyPdfError as error:raise ReaderError("PDF Mifel no legible") from error
        return self.read_pages(pages,sha256(content).hexdigest(),raw_pages=raw)

    def read_pages(self,pages,identifier,*,raw_pages=None):
        pages=tuple(pages);raw_pages=tuple(raw_pages) if raw_pages is not None else pages
        text="\n".join(pages)
        if not pages or "banca mifel" not in fold(text) or "pesos mexicanos" not in fold(text):
            raise ReaderError("Identidad Mifel/MXN ausente")
        if len(pages)!=len(raw_pages):raise ReaderError("Extracciones Mifel no compatibles")
        ranges=periods(raw_pages[0])
        accounts=set(re.findall(r"Detalles de la Cuenta a la vista\s+(\d+)",text))
        if len(ranges)!=1 or len(accounts)!=1:raise ReaderError("Cuenta/período Mifel ausente o ambiguo")
        start,end=ranges[0];fingerprint=sha256(("mifel:"+accounts.pop()).encode()).hexdigest()
        first=pages[0];issues=[];details=[];differences=[]
        other_keys=("Inversiones","Fondos de inversión","Pendiente de liquidar – compras","Pendiente de liquidar – ventas","Mesa de dinero","Efectivo en Mesa de dinero")
        other=tuple((key,label(first,key)) for key in other_keys)
        if any(v!=0 for key,v in other):issues.append("Otros productos con posición requieren lector específico; no duplicar la cuenta remunerada")
        yield_blocks=[p.split("Rendimientos y valuación de productos",1)[1].split("Detalles de la Cuenta a la vista",1)[0]
                      for p in pages if "Rendimientos y valuación de productos" in p]
        if len(yield_blocks)!=1:raise ReaderError("Tabla de rendimiento Mifel ausente o ambigua")
        yields=[line for line in yield_blocks[0].splitlines() if line.strip().startswith("Cuenta a la vista")]
        if len(yields)!=1:raise ReaderError("Rendimiento de cuenta remunerada no reconocido")
        yield_values=re.findall(_AMT,yields[0])
        if len(yield_values)!=2:raise ReaderError("Columnas de interés/ISR Mifel no reconocidas")
        opening=re.findall(r"Saldo inicial\s+("+_AMT+r")",text)
        closing=re.findall(r"Saldo a fecha de corte\s+("+_AMT+r")",text)
        sums=re.findall(r"Suma de retiros y depósitos\s+("+_AMT+r")\s+("+_AMT+r")",text)
        if len(opening)!=1 or len(closing)!=1 or len(sums)!=1:raise ReaderError("Saldos/totales del detalle Mifel incompletos")
        summary=MifelSummary(amount(opening[0]),amount(closing[0]),amount(sums[0][1]),amount(sums[0][0]),
            label(first,"Interés aplicable o rendimiento"),amount(yield_values[1]),label(first,"Tasa anual",True),
            label(first,"GAT nominal antes de impuestos",True),label(first,"GAT Real antes de impuestos",True),
            label(first,"Saldo promedio diario"),label(first,"Comisiones efectivamente cobradas"),label(first,"IVA"),
            label(first,"Posición total al inicio del mes"),label(first,"Posición total al cierre del mes"),other)
        lines=[];active=False;stopped=False;column=None
        for pno,page in enumerate(pages,1):
            for lno,line in enumerate(page.splitlines(),1):
                if "Detalles de la Cuenta a la vista" in line:active=True
                if active and "Suma de retiros y depósitos" in line:active=False;stopped=True
                if not active:continue
                if "Fecha" in line and "Retiros" in line and "Depósitos" in line and "Saldo" in line:
                    if column is not None:raise ReaderError("Encabezados operativos Mifel repetidos: revisar estructura")
                    column=(line.index("Depósitos"),line.index("Saldo"))
                lines.append((line,pno,lno))
        if column is None or not stopped:raise ReaderError("Sección de movimientos Mifel incompleta")
        body="\n".join(line for line,p,l in lines);offsets=[];offset=0
        for line,pno,lno in lines:offsets.append((offset,pno,lno));offset+=len(line)+1
        matches=list(_ROW.finditer(body));dated=re.findall(r"^\s*\d{2}/\d{2}/\d{4}\s+",body,re.M)
        if len(dated)!=len(matches):details.append("Fila fechada Mifel no reconocida")
        entries=[]
        for index,m in enumerate(matches):
            line_end=body.find("\n",m.end());line_end=len(body) if line_end<0 else line_end
            start_line=body.rfind("\n",0,m.start())+1
            line=body[start_line:line_end]
            values=list(re.finditer(_AMT,line))
            if len(values)!=2:details.append("Importe/saldo de movimiento Mifel no reconocidos");continue
            value,balance=values
            if (balance.start()+balance.end())/2<column[1]:details.append("Saldo fuera de su columna Mifel");continue
            when=datetime.strptime(m[1],"%d/%m/%Y").date();reference=m[2]
            if not start<=when<=end:details.append("Fecha de movimiento Mifel fuera del período")
            description=line[m.end()-start_line:value.start()].strip();normal=fold(description)
            kind=("interest_paid" if normal.startswith("pago intereses:") else
                  "withholding" if normal.startswith("isr retenido para") else
                  "transfer_unmatched" if normal.startswith("transferencia spei") else "unknown")
            is_debit=(value.start()+value.end())/2<column[0]
            debit,credit=(amount(value[0]),None) if is_debit else (None,amount(value[0]))
            if kind=="unknown":details.append("Concepto Mifel pendiente de mapear")
            if (kind=="interest_paid" and is_debit) or (kind=="withholding" and not is_debit):details.append("Tipo y columna de interés/ISR Mifel contradictorios")
            block=body[m.end():matches[index+1].start() if index+1<len(matches) else len(body)]
            accrual_start=accrual_end=None
            if kind=="interest_paid":
                dates=re.search(r"PAGO INTERESES:(\d{2}-\d{2}-\d{4})\s+to\s+(\d{2}-\d{2}-\d{4})",block)
                # El importe/saldo está entre el inicio y la fecha final del concepto.
                if dates is None:
                    dates=re.search(r"PAGO INTERESES:(\d{2}-\d{2}-\d{4})\s+to[^\n]*\n\s*(\d{2}-\d{2}-\d{4})",block)
                if dates is None:details.append("Rango remunerado Mifel ausente o no reconocido")
                else:
                    accrual_start,accrual_end=(datetime.strptime(x,"%d-%m-%Y").date() for x in dates.groups())
                    if accrual_end<accrual_start:details.append("Rango remunerado Mifel invertido")
            source=next(x for x in reversed(offsets) if x[0]<=m.start())
            entries.append(MifelEntry(when,reference,description,kind,debit,credit,amount(balance[0]),accrual_start,accrual_end,source[1],source[2]))
        def check(key,reported,calculated,target,page=1,line=0):
            if reported!=calculated:target.append(key);differences.append(MifelDifference(key,reported,calculated,page,line))
        current=summary.initial;previous=start;seen=set()
        for e in entries:
            if e.effective_date<previous:details.append("Secuencia operativa Mifel invertida")
            previous=e.effective_date;current=_sum((current,e.delta))
            check("Saldo corriente Mifel no concilia",e.balance,current,details,e.page,e.line)
            if e.reference in seen:details.append("Referencia Mifel repetida; conservar evidencia y revisar")
            seen.add(e.reference)
        check("Ecuación operativa Mifel no concilia",summary.final,_sum((summary.initial,summary.credits,summary.withdrawals.copy_negate())),details)
        check("Cierre del detalle Mifel no coincide",summary.final,current,details)
        check("Depósitos del detalle Mifel no coinciden",summary.credits,_sum(e.credit for e in entries if e.credit is not None),details)
        check("Retiros del detalle Mifel no coinciden",summary.withdrawals,_sum(e.debit for e in entries if e.debit is not None),details)
        gross=_sum(e.credit for e in entries if e.category=="interest_paid" and e.credit is not None)
        tax=_sum(e.debit for e in entries if e.category=="withholding" and e.debit is not None)
        check("Interés Mifel del resumen frente a detalle no coincide",summary.gross_interest,gross,issues)
        check("Interés Mifel de tabla de productos no coincide",amount(yield_values[0]),gross,issues)
        check("ISR Mifel informado frente a detalle no coincide",summary.withholding,tax,issues)
        check("Cuenta a la vista frente al cierre del detalle no coincide",label(first,"Cuenta a la vista"),summary.final,issues)
        check("Posición inicial requiere otros componentes",summary.portfolio_initial_reported,summary.initial,issues)
        check("Posición final frente a componentes no coincide",summary.portfolio_final_reported,_sum((summary.final,*(v for key,v in other))),issues)
        if summary.commissions_reported!=0 or summary.vat_reported!=0:issues.append("Comisiones/IVA no nulos requieren mapeo de sus filas")
        groups=[];grouped={}
        for e in entries:
            if e.category in ("interest_paid","withholding"):grouped.setdefault((e.effective_date,e.reference.split("-",1)[0]),[]).append(e)
        for (when,root),rows in grouped.items():
            paid=[e for e in rows if e.category=="interest_paid"];retained=[e for e in rows if e.category=="withholding"]
            if len(paid)!=1 or len(retained)!=1:details.append("Interés/retención Mifel sin pareja documental única");continue
            a,b=paid[0],retained[0]
            if a.credit is None or b.debit is None or a.accrual_start is None or a.accrual_end is None:continue
            groups.append(MifelIncome(when,root,a.reference,b.reference,a.credit,b.debit,_sum((a.credit,b.debit.copy_negate())),
                a.accrual_start,a.accrual_end,((a.page,a.line),(b.page,b.line))))
        return MifelPreview(identifier,start,end,fingerprint,summary,tuple(entries),tuple(groups),tuple(differences),tuple(dict.fromkeys(issues)),tuple(dict.fromkeys(details)),self.lane)


@dataclass(frozen=True)
class MifelReview:
    coverage: CoverageReview
    accrual_gaps: tuple[tuple[date,date], ...]
    accrual_overlaps: tuple[tuple[date,date], ...]
    accrual_days: int


def review_mifel_documents(previews):
    previews=tuple(previews);coverage=review_coverage(previews)
    unique={p.document_id:p for p in previews}
    intervals=sorted((g.accrual_start,g.accrual_end) for p in unique.values() for g in p.income_groups if g.accrual_end>=g.accrual_start)
    gaps=[];overlaps=[];frontier=None;days=0
    for start,end in intervals:
        if frontier is None:days+=(end-start).days+1;frontier=end;continue
        if start>frontier+timedelta(days=1):gaps.append((frontier+timedelta(days=1),start-timedelta(days=1)))
        if start<=frontier:overlaps.append((start,min(end,frontier)))
        days+=max(0,(end-max(start,frontier+timedelta(days=1))).days+1)
        frontier=max(frontier,end)
    return MifelReview(coverage,tuple(gaps),tuple(overlaps),days)
