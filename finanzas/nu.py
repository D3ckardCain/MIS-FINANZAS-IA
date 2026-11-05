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
    cajita: str | None = None
    tracking_key: str | None = None

    @property
    def amount(self):
        return self.value_candidates[0] if len(self.value_candidates)==1 else None


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
    issuer_reported: str = ""

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
    def detail_review(self):return review_nu_document(self)

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
        issuers=[label for marker,label in (
            ("nu mexico financiera","Nu México Financiera"),
            ("nubank, s.a., institucion de banca multiple","Nubank, S.A., Institución de Banca Múltiple")) if marker in fold(text)]
        if not pages or len(issuers)!=1:raise ReaderError("Identidad Nu ausente o ambigua")
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
            clean=_MONEY.sub("",description)
            clean=re.sub(r"\s+"," ",clean).strip()
            name=re.search(r"(?:en tu Cajita:|de tu Cajita:|Depósito en Cajita:|Retiro de Cajita:)\s*(.+)",clean,re.I)
            cajita=fold(name[1]).strip() if name else ("credito con garantia" if area=="guarantee" else None)
            tracking=re.search(r"Clave de rastreo\s+([A-Z0-9]+)",description,re.I)
            maturity=re.search(r"congelaste saldo hasta el\s+(\d{2}\s+[A-Z]{3}\s+\d{4})",description,re.I)
            proposed=parse_date(maturity[1]) if maturity else None
            event=NuEvent(sha256(f'{identifier}:{page}:{line}'.encode()).hexdigest(),when,area,kind(description),description,values,proposed,page,line,cajita,tracking[1] if tracking else None)
            (account_events if area=="account" else investment_events).append(event);current=None
        for pno,page in enumerate(pages[1:],2):
            page_lines=page.splitlines()
            header_end=next((i for i,l in enumerate(page_lines) if "Cuenta Nu:" in l),-1)
            for lno,line in enumerate(page_lines,1):
                if lno<=header_end+1:continue
                normalized=fold(line)
                if normalized.startswith("dinero generado en tu cuenta nu"):finish();section=None
                elif "movimientos en tu cuenta" in normalized:finish();section="account"
                elif "movimientos de tus cajitas" in normalized:finish();section="cajitas"
                elif "movimientos de tu cajita nu credito" in normalized:finish();section="guarantee"
                if normalized.startswith(("nu mexico financiera","nubank, s.a., institucion de banca multiple")):break
                if "saldo promedio del periodo" in normalized or "este dinero funciona" in normalized:
                    finish();section=None;continue
                if section is None:continue
                # In older statements the printed year is in the following row.
                wrapped=re.match(r"^\s*(\d{2})\s+([A-Z]{3})\s+(?!\d{4}\b)(.*)$",line)
                if wrapped and not _ROW.match(line):
                    following=page_lines[lno] if lno<len(page_lines) else ""
                    year=re.match(r"^\s*(\d{4})\b",following)
                    if year:row_year=year[1]
                    elif start.year==end.year:row_year=str(start.year)
                    else:raise ReaderError("Año de fila Nu ambiguo")
                    line=f"{wrapped[1]} {wrapped[2]} {row_year} {wrapped[3]}"
                elif re.match(r"^\s*\d{4}\b",line):
                    line=re.sub(r"^\s*\d{4}\s*","",line)
                match=_ROW.match(line)
                if match:
                    finish();when=parse_date(f'{match[1]} {match[2]} {match[3]}')
                    current=(when,section,[match[4]],pno,lno)
                elif current is not None and line.strip():
                    if not re.search(r"Cuenta Nu:|\d+ de \d+|MONTO EN PESOS|^\s*FECHA|^\s*MEXICANOS$",line):current[2].append(line.strip())
            # A footer does not finish the last transaction: its SPEI details
            # or wrapped Cajita name can continue on the next page.
        finish()
        detail=[]
        if any(not start<=e.effective_date<=end for e in account_events+investment_events):detail.append("Fecha de evidencia Nu fuera del período")
        if any(len(e.value_candidates)!=1 for e in account_events+investment_events):detail.append("Evidencia Nu con importe ausente/ambiguo, conservada sin convertir en cero")
        preview=NuPreview(identifier,start,end,fingerprint,summary,tuple(account_events),tuple(investment_events),tuple(differences),
            tuple(dict.fromkeys(summary_issues)),tuple(dict.fromkeys(composition)),tuple(detail),self.lane,issuer_reported=issuers[0])
        from dataclasses import replace
        review=review_nu_document(preview)
        return replace(preview,detail_issues=tuple(dict.fromkeys(detail+list(review.issues))))


@dataclass(frozen=True)
class NuPosting:
    evidence_id: str
    bucket: str
    amount: Decimal
    kind: str


@dataclass(frozen=True)
class NuTransferPair:
    account_evidence: str
    investment_evidence: str
    cajita: str
    amount: Decimal
    status: str = "documentary_pair"  # Not confirmation of external ownership.


@dataclass(frozen=True)
class NuDetailReview:
    postings: tuple[NuPosting, ...]
    pairs: tuple[NuTransferPair, ...]
    unmatched_internal: tuple[str, ...]
    unallocated_net_income: Decimal
    external_net: Decimal
    issues: tuple[str, ...]


def internal_direction(event):
    text=fold(event.description_printed)
    if "deposito en cajita:" in text or "agregado a tu cajita" in text:return 1
    if "retiro de cajita:" in text or "retirado de tu cajita" in text:return -1
    return None


def review_nu_document(preview):
    """Build auditable subaccount changes; never manufacture opening balances.

    Pair only explicit internal-transfer descriptions, the SAME named Cajita,
    date, exact opposite amounts, and unique one-to-one counterparts. This is
    documentary pairing inside one statement, not cross-bank ownership proof.
    """
    postings=[];pairs=[];unmatched=[];issues=[]
    account=preview.account_events;investments=preview.investment_events
    internals=[e for e in account if internal_direction(e) is not None]
    destinations=[e for e in investments if internal_direction(e) is not None]
    def compatible(a,b):
        return (a.amount is not None and b.amount is not None and a.cajita is not None
            and a.cajita==b.cajita and a.effective_date==b.effective_date
            and internal_direction(a)==internal_direction(b)
            and a.amount==-b.amount and a.amount!=0)
    for a in internals:
        found=[b for b in destinations if compatible(a,b)]
        if len(found)==1 and sum(compatible(other,found[0]) for other in internals)==1:
            b=found[0];pairs.append(NuTransferPair(a.evidence_id,b.evidence_id,a.cajita,b.amount))
        else:unmatched.append(a.evidence_id)
    paired={p.investment_evidence for p in pairs}
    unmatched.extend(e.evidence_id for e in destinations if e.evidence_id not in paired)
    for e in account+investments:
        amount=e.amount
        if amount is None:issues.append("Importe de fila Nu ausente o ambiguo");continue
        if not preview.period_start<=e.effective_date<=preview.period_end:issues.append("Fecha de fila Nu fuera del período")
        if e.section=="account":postings.append(NuPosting(e.evidence_id,"account",amount,"account_cash"));continue
        if e.cajita is None:issues.append("Cajita no identificada en fila Nu");continue
        bucket=("guarantee:" if e.section=="guarantee" else "cajita:")+e.cajita
        text=fold(e.description_printed)
        if "congelaste saldo" in text:
            if amount>=0 or e.maturity_candidate is None or e.maturity_candidate<=e.effective_date:
                issues.append("Congelamiento Nu con signo o vencimiento no válido");continue
            postings.extend((NuPosting(e.evidence_id,bucket+":available",amount,"freeze"),
                             NuPosting(e.evidence_id,bucket+":frozen",-amount,"freeze")))
        elif "descongelamos saldo" in text:
            if amount<=0:issues.append("Descongelamiento Nu con signo no válido");continue
            postings.extend((NuPosting(e.evidence_id,bucket+":frozen",-amount,"unfreeze"),
                             NuPosting(e.evidence_id,bucket+":available",amount,"unfreeze")))
        elif internal_direction(e) is not None:
            if amount*internal_direction(e)<=0:issues.append("Signo de traspaso Nu incompatible con concepto")
            postings.append(NuPosting(e.evidence_id,bucket+":available",amount,"internal_transfer"))
        else:issues.append("Concepto de inversión Nu no reconocido")
    if unmatched:issues.append("Traspasos internos Nu sin contraparte documental única")
    external=_sum(e.amount for e in account if internal_direction(e) is None and e.amount is not None)
    expected=_sum((preview.summary.deposits,preview.summary.expenses_printed))
    if external!=expected:issues.append("Neto externo del detalle Nu difiere del resumen")
    if preview.summary.net_income:
        issues.append("Rendimiento neto global Nu sin distribución publicada por Cajita/cuenta/garantía")
    if investments or preview.summary.cajitas_reported or preview.summary.guarantee_reported:
        issues.append("Saldos iniciales/finales individuales Nu no publicados; cambios por Cajita disponibles sin inventar saldos")
    return NuDetailReview(tuple(postings),tuple(pairs),tuple(unmatched),preview.summary.net_income,external,tuple(dict.fromkeys(issues)))


@dataclass(frozen=True)
class NuMaturityCandidate:
    frozen_evidence: str
    released_evidence: str
    cajita: str
    principal_reported: Decimal
    released_reported: Decimal
    status: str = "candidate_requires_contract"


@dataclass(frozen=True)
class NuHistoryReview:
    documents: tuple[NuPreview, ...]
    duplicate_documents: tuple[str, ...]
    detail_reviews: tuple[NuDetailReview, ...]
    maturity_candidates: tuple[NuMaturityCandidate, ...]
    unmatched_freezes: tuple[str, ...]
    unmatched_releases: tuple[str, ...]


def review_nu_documents(previews):
    """One account, binary deduplication and explicit maturity/name candidates.

    Never infer a contract rate or interest from released minus frozen amounts.
    Multiple freezes/release rows on one maturity date remain unmatched.
    """
    unique={};duplicates=[]
    for p in previews:
        if p.document_id in unique:duplicates.append(p.document_id)
        else:unique[p.document_id]=p
    docs=tuple(sorted(unique.values(),key=lambda p:p.period_start))
    if len({p.account_fingerprint for p in docs})>1:raise ReaderError("Historial Nu mezcla cuentas")
    for a,b in zip(docs,docs[1:]):
        if b.period_start<=a.period_end:raise ReaderError("Historial Nu tiene períodos solapados")
    freezes=[e for p in docs for e in p.investment_events if e.category=="freeze_evidence"]
    releases=[e for p in docs for e in p.investment_events if e.category=="unfreeze_evidence"]
    def compatible(a,b):
        return (a.cajita is not None and a.cajita==b.cajita and a.maturity_candidate==b.effective_date
            and a.effective_date<b.effective_date and a.amount is not None and a.amount<0
            and b.amount is not None and b.amount>0)
    matches=[]
    for a in freezes:
        found=[b for b in releases if compatible(a,b)]
        if len(found)==1 and sum(compatible(other,found[0]) for other in freezes)==1:
            b=found[0];matches.append(NuMaturityCandidate(a.evidence_id,b.evidence_id,a.cajita,-a.amount,b.amount))
    used_a={m.frozen_evidence for m in matches};used_b={m.released_evidence for m in matches}
    return NuHistoryReview(docs,tuple(duplicates),tuple(review_nu_document(p) for p in docs),tuple(matches),
        tuple(e.evidence_id for e in freezes if e.evidence_id not in used_a),
        tuple(e.evidence_id for e in releases if e.evidence_id not in used_b))
