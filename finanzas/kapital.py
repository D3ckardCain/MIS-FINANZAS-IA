"""Kapital: dos formatos, efectivo y pagarés separados, sin importación."""
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import re

from .ledger import _sum
from .coverage import CoverageReview
from .readers import ReaderError, fold, periods, parse_date

_AMT = r"(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}"
_MONEY = re.compile(r"\$\s*-?\s*" + _AMT)
_PLAIN = re.compile(r"(?<![\w.])" + _AMT + r"-?(?!\d)")
_DATE = r"\d{2}-[A-Za-z]{3}-\d{4}"


def amount(text):
    text = re.sub(r"[\s$,]", "", text)
    if text.endswith("-"):
        text = "-" + text[:-1]
    return Decimal(text)


@dataclass(frozen=True)
class KapitalCashSummary:
    initial: Decimal
    final: Decimal
    credits: Decimal
    debits: Decimal
    interest_component: Decimal
    retention_component: Decimal
    commissions_reported: Decimal
    investment_interest_component: Decimal | None
    investment_retention_component: Decimal | None
    investment_principal_inflow: Decimal | None = None
    investment_principal_outflow: Decimal | None = None
    unit: str | None = None


@dataclass(frozen=True)
class KapitalInvestmentSummary:
    initial: Decimal
    final: Decimal
    unit: str | None = None


@dataclass(frozen=True)
class KapitalContract:
    id: str
    product: str
    opened: date
    maturity: date
    days: int
    principal: Decimal
    annual_rate: Decimal
    gat_nominal: Decimal
    gat_real: Decimal
    interest_at_maturity: Decimal
    retention_at_maturity: Decimal | None
    net_rate_reported: Decimal | None
    net_at_maturity: Decimal | None
    net_footer: Decimal | None
    page: int
    line: int

    @property
    def economic_terms(self):
        return (self.opened,self.maturity,self.days,self.principal,self.annual_rate,self.interest_at_maturity)


@dataclass(frozen=True)
class KapitalEntry:
    effective_date: date
    reference: str
    description_printed: str
    category: str
    credit: Decimal | None
    debit: Decimal | None
    withdrawal_printed: Decimal | None
    balance: Decimal
    page: int
    line: int

    @property
    def delta(self):
        return _sum(v for v in (self.credit,None if self.debit is None else self.debit.copy_negate()) if v is not None)


@dataclass(frozen=True)
class KapitalDifference:
    check: str
    reported: Decimal
    calculated: Decimal
    page: int
    line: int


@dataclass(frozen=True)
class KapitalPreview:
    document_id: str
    period_start: date
    period_end: date
    account_fingerprint: str
    format: str
    cash_summary: KapitalCashSummary
    investment_summary: KapitalInvestmentSummary
    contracts: tuple[KapitalContract, ...]
    entries: tuple[KapitalEntry, ...]
    differences: tuple[KapitalDifference, ...]
    cash_issues: tuple[str, ...]
    investment_issues: tuple[str, ...]
    lane: str
    currency_markers: tuple[str, ...] = ()

    @property
    def summary(self):
        return self.cash_summary if self.lane=="debit" else self.investment_summary

    @property
    def issues(self):
        return () if self.lane=="debit" else self.investment_issues

    @property
    def detail_issues(self):
        return self.cash_issues

    @property
    def detail_reconciled(self):
        return not self.cash_issues

    @property
    def reconciled(self):
        return not self.issues and not self.detail_issues

    @property
    def ready_to_import(self):
        return False


def label(text, key, dollar=True):
    found=re.findall(re.escape(key)+r"\s*"+(r"\$\s*" if dollar else "")+r"("+_AMT+r")",text)
    if len(found)!=1:
        raise ReaderError("Resumen Kapital incompleto o ambiguo: "+key)
    return amount(found[0])


def _legacy_summary(first):
    if first.count("RESUMEN DEL PERIODO")!=1:raise ReaderError("Resumen anterior Kapital no reconocido")
    block=first.split("RESUMEN DEL PERIODO",1)[1].split("DETALLE DE INVERSIONES (MONEDA NACIONAL)",1)[0]
    get=lambda key:label(block,key)
    credits=_sum(get(key) for key in ("(+) Depósitos en Efectivo","(+) Depósitos de Cheques","(+) Transferencias Recibidas","(+) Otros Abonos a su Cuenta","(+) Intereses Ganados"))
    debits=_sum(get(key) for key in ("(-) Retiros Efectivo Sucursal y Cajeros Automaticos","(-) Cheques Cobrados","(-) Transferencias Enviadas","(-) Otros Cargos a su Cuenta","(-) I.V.A. Cobrado","(-) Retenciones de I.S.R.","(-) Comisiones Cobradas","(-)Compras en Establecimientos"))
    principal_in=get("( - ) Movimientos del Mes");principal_out=get("(+) Movimientos del Mes")
    cash=KapitalCashSummary(get("(+) Saldo Inicial"),get("(-) Saldo Final"),_sum((credits,principal_in)),_sum((debits,principal_out)),
        get("(+) Intereses Ganados"),get("(-) Retenciones de I.S.R."),get("(-) Comisiones Cobradas"),None,None,principal_in,principal_out)
    return cash,KapitalInvestmentSummary(get("Saldo al Inicio"),get("Saldo al Final"))


def _current_summary(first):
    if first.count("CUENTA DE CHEQUES")!=1:raise ReaderError("Resumen de cheques Kapital no reconocido")
    block=first.split("CUENTA DE CHEQUES",1)[1].split("Saldo mínimo requerido",1)[0]
    get=lambda key:label(block,key,False)
    cash=KapitalCashSummary(get("Saldo Inicial"),get("Saldo Final"),get("+ Depósitos"),get("- Retiros"),
        get("+ Intereses Brutos Cheques"),get("- I.S.R. Retenido Cheques"),get("- Comisiones Efectivamente"),
        get("+ Intereses Brutos de Inversiones"),get("- I.S.R. Retenido de Inversiones"))
    headers=[l for l in first.splitlines() if "PRODUCTOS" in l and "SALDO/VALOR" in l and "INTERESES" in l]
    rows=[l for l in first.splitlines() if re.search(r"PAGARE\s+\(",l)]
    if len(headers)!=1 or len(rows)!=1:
        raise ReaderError("Resumen de pagarés Kapital no reconocido")
    header=headers[0];saldo=list(re.finditer("SALDO/VALOR",header))
    if len(saldo)!=2:raise ReaderError("Columnas de saldo de pagarés ambiguas")
    centers=[("initial",saldo[0].start()+len("SALDO/VALOR")/2),
             ("final",saldo[1].start()+len("SALDO/VALOR")/2)]
    for key in ("INTERESES","COMISIONES","IVA","%","SALDO","ISR","GAT/CAT"):
        pos=header.find(key,saldo[1].end()) if key=="SALDO" else header.find(key)
        if pos>=0:centers.append((key,pos+len(key)/2))
    values={}
    for m in _PLAIN.finditer(rows[0]):
        name=min(centers,key=lambda c:abs(c[1]-(m.start()+m.end())/2))[0]
        if name in values:raise ReaderError("Valores de resumen Kapital ambiguos")
        values[name]=amount(m[0])
    if not {"initial","final"}<=values.keys():raise ReaderError("Saldos de pagarés ausentes")
    return cash,KapitalInvestmentSummary(values["initial"],values["final"])


def _contracts(pages,legacy):
    result=[];context=None;footer_seen=set()
    legacy_row=re.compile(r"^\s*(LD\d+)\s+(.+?)\s+(\d+)\s+DIAS\s+("+_DATE+r")\s+("+_DATE+r")\s+\$\s*("+_AMT+r")\s+(\d+(?:\.\d+)?)\s*%\s+(\d+\.\d+)\s*%\s+(\d+\.\d+)\s*%\s+\$\s*("+_AMT+r")\s*$")
    current_row=re.compile(r"^\s*(\d+\.\d+)%\s+("+_AMT+r")\s+(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2})\s+(\d+)\s+(\d+\.\d+)\s+("+_AMT+r")\s+("+_AMT+r")\s+("+_AMT+r")\s*$")
    for pno,page in enumerate(pages,1):
        for lno,line in enumerate(page.splitlines(),1):
            if legacy:
                m=legacy_row.fullmatch(line)
                if m:
                    key,product,days,opened,maturity,principal,rate,gn,gr,interest=m.groups()
                    result.append(KapitalContract(key,product,parse_date(opened),parse_date(maturity),int(days),amount(principal),Decimal(rate),Decimal(gn),Decimal(gr),amount(interest),None,None,None,None,pno,lno))
                elif re.match(r"^\s*LD\d+",line):raise ReaderError("Contrato Kapital anterior no reconocido")
            else:
                ident=re.search(r"No\. de Inversión\s+(\d+)",line)
                if ident:
                    gat=re.search(r"GAT\s+(\d+\.\d+)%.*?GAT REAL\s+(\d+\.\d+)%",line)
                    if not gat:raise ReaderError("Condiciones GAT Kapital no reconocidas")
                    context=(ident[1],Decimal(gat[1]),Decimal(gat[2]))
                m=current_row.fullmatch(line)
                if m:
                    if context is None:raise ReaderError("Contrato sin identificador Kapital")
                    rate,principal,opened,maturity,days,netrate,interest,retained,net=m.groups()
                    result.append(KapitalContract(context[0],"Pagaré",date.fromisoformat(opened),date.fromisoformat(maturity),int(days),amount(principal),Decimal(rate),context[1],context[2],amount(interest),amount(retained),Decimal(netrate),amount(net),None,pno,lno))
                elif re.match(r"^\s*\d+\.\d+%\s+",line):raise ReaderError("Contrato Kapital nuevo no reconocido")
                footer=re.search(r"Total Vigentes\s+("+_AMT+r")",line)
                if footer:
                    if not result or context is None or result[-1].id!=context[0] or context[0] in footer_seen:
                        raise ReaderError("Total por contrato Kapital ausente/duplicado")
                    footer_seen.add(context[0]);result[-1]=replace(result[-1],net_footer=amount(footer[1]))
    if not result or len({c.id for c in result})!=len(result):raise ReaderError("Cartera Kapital ausente o contratos repetidos")
    if not legacy and footer_seen!={c.id for c in result}:raise ReaderError("Totales de pagarés incompletos")
    return tuple(result)


def _category(description,reference,contracts,legacy):
    if legacy:return "investment_opening" if reference in {c.id for c in contracts} else "cash_movement_unmatched"
    text=fold(description)
    for prefix,kind in (("pago cap. de inversion","principal_repayment"),("pago intereses de inv.","interest_paid"),
                        ("ret. isr de inversion","withholding"),("comision por timbrado fiscal","stamp_fee"),
                        ("descuento por timbrado fiscal","stamp_discount"),("envio spei","transfer_unmatched")):
        if text.startswith(prefix):return kind
    return "unknown"


class KapitalReader:
    def __init__(self,lane="investments"):
        if lane not in ("debit","investments"):raise ReaderError("Vista Kapital desconocida")
        self.lane=lane

    def read_image(self,content,*,engine=None):
        from .imaging import read_statement_image
        return read_statement_image(content,"kapital",self.lane,engine=engine)

    def read_pdf(self,content,*,password=None):
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            pdf=PdfReader(BytesIO(content))
            if pdf.is_encrypted and (password is None or not pdf.decrypt(password)):
                raise ReaderError("PDF Kapital protegido: contraseña requerida o no válida")
            pages=tuple(p.extract_text(extraction_mode="layout") or "" for p in pdf.pages)
            raw=tuple(p.extract_text() or "" for p in pdf.pages)
        except PyPdfError as error:raise ReaderError("PDF Kapital no legible") from error
        return self.read_pages(pages,sha256(content).hexdigest(),raw_pages=raw)

    def read_pages(self,pages,identifier,*,raw_pages=None):
        pages=tuple(pages);text="\n".join(pages);raw="\n".join(raw_pages) if raw_pages is not None else text
        if "kapital" not in fold(text):raise ReaderError("Identidad Kapital ausente")
        # Las fechas contractuales no son períodos del estado de cuenta.
        headers="\n".join(line for line in raw.splitlines() if re.match(r"^\s*Per[ií]odo\b",line,re.I))
        ranges=periods(headers);accounts=set(re.findall(r"CLABE\s+(\d{18})",text))
        if len(ranges)!=1 or len(accounts)!=1:raise ReaderError("Cuenta/período Kapital ausente o ambiguo")
        start,end=ranges[0]
        if (start.year,start.month)!=(end.year,end.month):raise ReaderError("Período Kapital no mensual")
        fingerprint=sha256(("kapital:"+accounts.pop()).encode()).hexdigest()
        legacy="RESUMEN DEL PERIODO" in text
        cash,investment=(_legacy_summary if legacy else _current_summary)(pages[0])
        markers={m.upper() for m in re.findall(r'\b(?:moneda|divisa)\s*:?\s*([A-Z]{3})\b',text,re.I)}
        if re.search(r'\bmoneda\s*:?\s*(?:nacional|pesos mexicanos|mn)\b|\b[\d.,]+\s+mn\b',fold(text)):markers.add('MXN')
        unit='MXN' if markers=={'MXN'} else None
        cash=replace(cash,unit=unit);investment=replace(investment,unit=unit)
        contracts=_contracts(pages,legacy)
        entries=[];cash_issues=[];investment_issues=[];differences=[];table_seen=False
        for pno,page in enumerate(pages,1):
            active=False;centers=None
            for lno,line in enumerate(page.splitlines(),1):
                if legacy and "DETALLE DE MOVIMIENTOS (MONEDA NACIONAL)" in line:active=True;table_seen=True
                if not legacy and "DÍA" in line and "FOLIO" in line and "DEPÓSITOS" in line:
                    active=True;table_seen=True;centers={k:line.index(k) for k in ("DEPÓSITOS","RETIROS","SALDO")};continue
                if not active:continue
                if not legacy and line.strip().startswith("Total"):active=False;continue
                if legacy:
                    match=re.match(r"^\s*("+_DATE+r")\s+",line)
                    if not match:continue
                    values=list(_MONEY.finditer(line));ref=re.findall(r"\b(?:FT|LD)\d+\b",line)
                    if len(values)!=3 or len(ref)!=1:cash_issues.append("Fila operativa Kapital anterior no reconocida");continue
                    when=parse_date(match[1]);credit,withdrawal,balance=map(lambda m:amount(m[0]),values)
                    description=line[match.end():line.index(ref[0])].strip();reference=ref[0]
                    if credit<0 or withdrawal>0:cash_issues.append("Signos de depósito/retiro anterior inesperados")
                    debit=withdrawal.copy_negate()
                else:
                    match=re.match(r"^\s*(\d{1,2})\s+(\d{6,})\s+(.*)$",line)
                    if not match:continue
                    values=list(_PLAIN.finditer(line));values=[m for m in values if m.start()>=match.start(3)]
                    if len(values)!=2 or centers is None:cash_issues.append("Columnas operativas Kapital no reconocidas");continue
                    first,last=values
                    def field(m):
                        midpoint=(m.start()+m.end())/2
                        return "DEPÓSITOS" if midpoint<centers["RETIROS"] else ("RETIROS" if midpoint<centers["SALDO"] else "SALDO")
                    if field(last)!="SALDO" or field(first)=="SALDO":cash_issues.append("Columna importe/saldo Kapital ambigua");continue
                    try:when=date(start.year,start.month,int(match[1]))
                    except ValueError as error:raise ReaderError("Día Kapital inválido") from error
                    value=amount(first[0]);balance=amount(last[0]);reference=match[2];description=line[match.start(3):first.start()].strip()
                    credit,debit=(value,None) if field(first)=="DEPÓSITOS" else (None,value)
                    withdrawal=debit
                    if value<0:cash_issues.append("Signo de movimiento Kapital nuevo inesperado")
                kind=_category(description,reference,contracts,legacy)
                if kind=="unknown":cash_issues.append("Concepto Kapital pendiente de mapear")
                if kind in ("principal_repayment","interest_paid","stamp_discount") and (credit is None or credit<=0):cash_issues.append("Tipo de abono Kapital en columna inesperada")
                if kind in ("withholding","stamp_fee","investment_opening") and (debit is None or debit<=0):cash_issues.append("Tipo de cargo Kapital en columna inesperada")
                if not start<=when<=end:cash_issues.append("Movimiento fuera del período Kapital")
                entries.append(KapitalEntry(when,reference,description,kind,credit,debit,withdrawal,balance,pno,lno))
        if not table_seen:cash_issues.append("Tabla de movimientos Kapital no incluida")
        def check(key,reported,calculated,target,page=1,line=0):
            if reported!=calculated:target.append(key);differences.append(KapitalDifference(key,reported,calculated,page,line))
        balance=cash.initial;seen=set();previous=start
        for e in entries:
            if e.effective_date<previous:cash_issues.append("Secuencia Kapital invertida")
            previous=e.effective_date;balance=_sum((balance,e.delta))
            check("Saldo corriente Kapital no concilia",e.balance,balance,cash_issues,e.page,e.line)
            key=(e.reference,e.category)
            if key in seen:cash_issues.append("Referencia/categoría Kapital repetida; revisar sin borrar")
            seen.add(key)
        check("Ecuación del resumen Kapital no concilia",cash.final,_sum((cash.initial,cash.credits,cash.debits.copy_negate())),cash_issues)
        check("Cierre del detalle Kapital no coincide",cash.final,balance,cash_issues)
        check("Depósitos del detalle Kapital no coinciden",cash.credits,_sum(e.credit for e in entries if e.credit is not None),cash_issues)
        check("Retiros del detalle Kapital no coinciden",cash.debits,_sum(e.debit for e in entries if e.debit is not None),cash_issues)
        check("Capital de pagarés Kapital no coincide con resumen",investment.final,_sum(c.principal for c in contracts),investment_issues)
        if legacy:
            check("Movimientos de capital de inversión no concilian",investment.final,
                  _sum((investment.initial,cash.investment_principal_outflow,cash.investment_principal_inflow.copy_negate())),investment_issues)
        else:
            check("Vencimientos frente a cambio de capital no concilian",investment.final,
                  _sum((investment.initial,*(_sum(x for x in (e.debit,None if e.credit is None else e.credit.copy_negate()) if x is not None)
                                            for e in entries if e.category in ("investment_opening","principal_repayment")))),investment_issues)
        for c in contracts:
            if (c.maturity-c.opened).days!=c.days:investment_issues.append("Días y fechas del pagaré Kapital no coinciden")
            if not c.opened<=end<c.maturity:investment_issues.append("Pagaré fuera del alcance de vigentes al corte")
            if c.net_at_maturity is not None:
                check("Neto futuro de pagaré Kapital no concilia",c.net_at_maturity,_sum((c.principal,c.interest_at_maturity,c.retention_at_maturity.copy_negate())),investment_issues,c.page,c.line)
                check("Total Vigentes por pagaré Kapital no coincide",c.net_footer,c.net_at_maturity,investment_issues,c.page,c.line)
            if legacy and start<=c.opened<=end:
                rows=[e for e in entries if e.reference==c.id and e.category=="investment_opening"]
                if len(rows)!=1 or rows[0].effective_date!=c.opened:investment_issues.append("Apertura Kapital sin cargo único en fecha contractual")
                else:check("Cargo de apertura Kapital difiere de capital",c.principal,rows[0].debit,investment_issues,rows[0].page,rows[0].line)
        if not legacy:
            total=lambda category:_sum(_sum(x for x in (e.credit,e.debit) if x is not None) for e in entries if e.category==category)
            check("Interés de inversiones vencidas difiere del detalle",cash.investment_interest_component,total("interest_paid"),investment_issues)
            check("ISR de inversiones vencidas difiere del detalle",cash.investment_retention_component,total("withholding"),investment_issues)
            check("Comisión efectiva frente a timbrado y descuento no coincide",cash.commissions_reported,_sum((total("stamp_fee"),total("stamp_discount").copy_negate())),cash_issues)
        return KapitalPreview(identifier,start,end,fingerprint,"legacy" if legacy else "current",cash,investment,contracts,tuple(entries),tuple(differences),tuple(dict.fromkeys(cash_issues)),tuple(dict.fromkeys(investment_issues)),self.lane,tuple(sorted(markers)))


@dataclass(frozen=True)
class ContractAliasProposal:
    previous_id: str
    next_id: str
    previous_document: str
    next_document: str
    needs_review: bool = True


@dataclass(frozen=True)
class MaturityProposal:
    contract_id: str
    forecast_document: str
    payment_document: str
    effective_date: date
    principal_paid: Decimal
    interest_paid: Decimal
    retention_paid: Decimal
    forecast_retention: Decimal | None
    matches_forecast: bool | None
    source_lines: tuple[tuple[int,int], ...]
    needs_review: bool = True


@dataclass(frozen=True)
class KapitalReview:
    cash_coverage: CoverageReview
    investment_coverage: CoverageReview
    contract_alias_proposals: tuple[ContractAliasProposal, ...]
    maturity_proposals: tuple[MaturityProposal, ...]
    issues: tuple[str, ...]


def review_kapital_documents(previews):
    """Compara evidencia sin fusionar IDs, crear operaciones ni confirmar vínculos."""
    from .coverage import review_coverage
    previews=tuple(previews)
    cash=review_coverage(replace(p,lane="debit") for p in previews)
    investments=review_coverage(replace(p,lane="investments") for p in previews)
    ordered=sorted({p.document_id:p for p in previews}.values(),key=lambda p:(p.period_start,p.period_end))
    observations={};issues=[]
    for p in ordered:
        for c in p.contracts:observations.setdefault(c.id,[]).append((p,c))
    signatures={}
    for key,versions in observations.items():
        terms={c.economic_terms for p,c in versions}
        if len(terms)!=1:
            issues.append("Un identificador contractual cambia de condiciones económicas; revisar versiones")
            continue
        signatures.setdefault(next(iter(terms)),[]).append((key,versions))
    aliases=[]
    for group in signatures.values():
        old=[x for x in group if all(p.format=="legacy" for p,c in x[1])]
        new=[x for x in group if all(p.format=="current" for p,c in x[1])]
        if len(old)==1 and len(new)==1:
            previous_id,previous=old[0];next_id,following=new[0]
            if previous[-1][0].period_end<following[0][0].period_start:
                aliases.append(ContractAliasProposal(previous_id,next_id,previous[-1][0].document_id,following[0][0].document_id))
        elif old and new:issues.append("Equivalencia contractual ambigua; no fusionar identificadores")
    maturities=[]
    for p in ordered:
        if p.cash_issues:continue
        prior={}
        for before in ordered:
            if before.period_end>=p.period_start or before.format!=p.format:continue
            for c in before.contracts:prior[c.id]=(before,c)
        for index in range(len(p.entries)-2):
            rows=p.entries[index:index+3]
            if [e.category for e in rows]!=["principal_repayment","interest_paid","withholding"]:continue
            if len({e.reference for e in rows})!=1 or len({e.effective_date for e in rows})!=1:continue
            matches=[(before,c) for before,c in prior.values() if c.maturity==rows[0].effective_date and c.principal==rows[0].credit and c.interest_at_maturity==rows[1].credit]
            if len(matches)!=1:
                issues.append("Cobro de vencimiento sin contrato anterior único")
                continue
            before,c=matches[0];known=None if c.retention_at_maturity is None else c.retention_at_maturity==rows[2].debit
            if known is False:issues.append("Retención pagada difiere de proyección anterior; preservar ambas")
            maturities.append(MaturityProposal(c.id,before.document_id,p.document_id,rows[0].effective_date,
                rows[0].credit,rows[1].credit,rows[2].debit,c.retention_at_maturity,known,tuple((e.page,e.line) for e in rows)))
    return KapitalReview(cash,investments,tuple(aliases),tuple(maturities),tuple(dict.fromkeys(issues)))
