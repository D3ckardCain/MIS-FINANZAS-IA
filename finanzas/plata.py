"""Plata: two products, cashback provenance and explicit post-cutoff bookings."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import re
from .readers import ReaderError,fold,periods,parse_date
from .ledger import _sum

_MONEY=r'[−-]?\s*\$\s*(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}'
_DATE=r'\d{2}\s+\w{3}\s+\d{4}'
_ROW=re.compile(r'^\s*('+_DATE+r')\s+('+_DATE+r')\s+(.+?)\s{2,}([A-Z]{3})\s+(\d+\.\d+)\s+(\S+)\s+(.*?)\s*$')


def money(raw):return Decimal(re.sub(r'[\s$,]','',raw).replace('−','-'))


def take(text,label,*,optional=False):
    found=re.findall(r'^\s*'+re.escape(label)+r'\s+('+_MONEY+r')',text,re.M)
    if not found and optional:return None
    if len(found)!=1:raise ReaderError('Campo Plata ausente/ambiguo: '+label)
    return money(found[0])


@dataclass(frozen=True)
class PlataSummary:
    initial: Decimal
    final: Decimal
    deposits_and_income: Decimal
    withdrawals_printed: Decimal
    commissions_printed: Decimal
    vat_withheld_printed: Decimal
    other_charges_printed: Decimal | None
    isr_withheld_printed: Decimal
    gross_income_reported: Decimal | None
    annual_rate_reported: Decimal | None
    average_balance_reported: Decimal | None = None
    gat_nominal_reported: Decimal | None = None
    gat_real_reported: Decimal | None = None


@dataclass(frozen=True)
class PlataMovement:
    evidence_id: str
    operation_date: date
    posting_date: date
    description: str
    currency: str
    exchange_rate: Decimal
    reference: str | None
    amount: Decimal
    category: str
    outside_period: bool
    page: int
    line: int


@dataclass(frozen=True)
class PlataProduct:
    lane: str
    account_fingerprint: str
    summary: PlataSummary
    rows: tuple[PlataMovement,...]
    issues: tuple[str,...]
    timing_issues: tuple[str,...]


@dataclass(frozen=True)
class PlataTransferCandidate:
    source_evidence: str
    destination_evidence: str
    amount: Decimal
    cashback_origin_candidate: str | None
    status: str = 'candidate_requires_review'


@dataclass(frozen=True)
class PlataPreview:
    document_id: str
    period_start: date
    period_end: date
    relationship_fingerprint: str
    debit: PlataProduct
    investments: PlataProduct
    aggregate: PlataSummary
    aggregate_isr_basis: str
    aggregate_issues: tuple[str,...]
    transfer_candidates: tuple[PlataTransferCandidate,...]
    annex_pages: tuple[int,...]
    lane: str

    @property
    def product(self):return self.debit if self.lane=='debit' else self.investments
    @property
    def account_fingerprint(self):return self.product.account_fingerprint
    @property
    def summary(self):return self.product.summary
    @property
    def entries(self):return self.product.rows
    @property
    def rows(self):return self.product.rows
    @property
    def issues(self):return self.product.issues+self.aggregate_issues
    @property
    def composition_issues(self):return self.aggregate_issues
    @property
    def detail_issues(self):return self.product.timing_issues
    @property
    def summary_reconciled(self):return not self.issues
    @property
    def detail_reconciled(self):return not self.issues and not self.detail_issues
    @property
    def reconciled(self):return self.detail_reconciled
    @property
    def ready_to_import(self):return False


def summary(text,*,aggregate=False):
    rate=re.findall(r'Tasa bruta de interés\s+([\d.]+)%',text,re.M)
    if not aggregate and len(rate)!=1:raise ReaderError('Tasa Plata ausente/ambigua')
    income=re.findall(r'(?<!\w)Rendimientos\s+('+_MONEY+r')',text)
    if not aggregate and len(income)!=1:raise ReaderError('Rendimiento Plata ausente/ambiguo')
    def optional_money(label):
        found=re.findall(re.escape(label)+r'\s+('+_MONEY+r')',text)
        if len(found)>1:raise ReaderError('Campo Plata repetido: '+label)
        return money(found[0]) if found else None
    def percent(label):
        found=re.findall(re.escape(label)+r'\s+([\d.]+)%',text)
        if len(found)>1:raise ReaderError('Porcentaje Plata repetido: '+label)
        return Decimal(found[0]) if found else None
    return PlataSummary(take(text,'Saldo anterior'),take(text,'Saldo final'),take(text,'Depósitos y rendimientos'),
        take(text,'Retiros'),take(text,'Comisiones'),take(text,'IVA retenido'),take(text,'Otros cargos',optional=True),
        take(text,'ISR retenido'),(money(income[0]) if income else None),Decimal(rate[0]) if rate else None,
        optional_money("Saldo promedio mensual"),percent("GAT nominal"),percent("GAT real"))


def classify(description,amount):
    c=fold(description)
    if c=='cashback' and amount>0:return 'cashback_contribution'
    if c=='transferencia entre cuentas propias' and amount<0:return 'own_transfer_out'
    if c=='deposito desde cuenta propia' and amount>0:return 'own_transfer_in'
    if c=='pago por transferencia spei':return 'spei_in' if amount>0 else 'spei_out'
    if c=='impuestos retenidos (isr)' and amount<=0:return 'isr_withholding'
    if c=='rendimientos' and amount>0:return 'interest_received'
    return 'unmapped'


class PlataReader:
    def __init__(self,lane='investments'):
        if lane not in ('debit','investments'):raise ReaderError('Vista Plata desconocida')
        self.lane=lane

    def read_image(self,content,*,engine=None):
        from .imaging import read_statement_image
        return read_statement_image(content,'plata',self.lane,engine=engine)

    def read_pdf(self,content):
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            pdf=PdfReader(BytesIO(content))
            if pdf.is_encrypted:raise ReaderError('PDF Plata cifrado')
            pages=tuple(p.extract_text(extraction_mode='layout') or '' for p in pdf.pages)
        except PyPdfError as e:raise ReaderError('PDF Plata no legible') from e
        return self.read_pages(pages,sha256(content).hexdigest())

    def read_pages(self,pages,identifier):
        pages=tuple(pages);text='\n'.join(pages)
        if 'banco plata' not in fold(text):raise ReaderError('Identidad Plata ausente')
        ranges=periods(text);accounts=set(re.findall(r'No\.\s*de Cuenta:\s*(\d+)',text))
        if len(ranges)!=1 or len(accounts)!=1:raise ReaderError('Relación/período Plata ausente o ambiguo')
        start,end=ranges[0];relationship=sha256(('plata:'+accounts.pop()).encode()).hexdigest()
        summaries={};clabes={};aggregate=None;annex=[]
        for pno,page in enumerate(pages,1):
            if 'comprobante fiscal' in fold(page):annex.append(pno);continue
            for lane,title in [('debit','Plata Cuenta'),('investments','Ahorro Flexible')]:
                head=re.search(r'^\s*'+title+r'\s+CLABE:\s*(\d{18})\s*$',page,re.M)
                if head:
                    if lane in summaries:raise ReaderError('Resumen de producto Plata repetido')
                    body=page[head.end():].split('Comportamiento',1)[0]
                    parts=re.split(r'^\s*Total\s*$',body,maxsplit=1,flags=re.M)
                    summaries[lane]=summary(parts[0]);clabes[lane]=head[1]
                    if len(parts)==2:
                        if aggregate is not None:raise ReaderError('Total Plata repetido')
                        aggregate=summary(parts[1],aggregate=True)
        if set(summaries)!={'debit','investments'} or aggregate is None:raise ReaderError('Faltan las dos vistas o total Plata')
        if len(set(clabes.values()))!=2:raise ReaderError('CLABE compartida inesperada entre productos Plata')
        rows={'debit':[],'investments':[]};section=None;current=None;desc_start=None;desc_end=None
        def finish():
            nonlocal current
            if current is None:return
            op,post,desc,unit,fx,ref,chunks,page,line=current
            printed=' '.join(chunks).strip()
            if not re.fullmatch(_MONEY,printed):raise ReaderError('Importe/signo Plata ausente o ambiguo')
            amount=money(printed);description=' '.join(desc)
            outside=not(start<=op<=end and start<=post<=end)
            rows[section].append(PlataMovement(sha256(f'{identifier}:{page}:{line}'.encode()).hexdigest(),op,post,description,
                unit,fx,None if ref in ('—','–','-') else ref,amount,classify(description,amount),outside,page,line))
            current=None
        for pno,page in enumerate(pages,1):
            if pno in annex:finish();section=None;continue
            for lno,line in enumerate(page.splitlines(),1):
                c=fold(line)
                if c.startswith(('unicamente estan garantizados','banco plata, s.a.')):finish();section=None;continue
                heading=re.match(r'^\s*Movimientos de (Plata Cuenta|Ahorro Flexible)\s+CLABE:\s*(\d{18})\s*$',line)
                if heading:
                    finish();section='debit' if heading[1]=='Plata Cuenta' else 'investments'
                    if heading[2]!=clabes[section]:raise ReaderError('CLABE de movimientos difiere del resumen')
                    continue
                if section is None:continue
                if 'fecha de operacion' in c and 'fecha de cargo' in c and 'descripcion' in c:
                    desc_start=line.index('Descripción');desc_end=line.index('Moneda');continue
                m=_ROW.match(line)
                if m:
                    finish()
                    current=(parse_date(m[1]),parse_date(m[2]),[m[3].strip()],m[4],Decimal(m[5]),m[6],[m[7].strip()],pno,lno)
                    continue
                if re.fullmatch(r'\s*'+_DATE+r'\s+[—–-]\s+'+_DATE+r'\s+\(\d+ días\)\s+No\. de Cuenta:\s*',line):continue
                if re.match(r'^\s*'+_DATE+r'\s+',line):raise ReaderError('Fila fechada Plata con columnas no reconocidas')
                # Header/footer of a continuation page is not part of a movement.
                if not line.strip() or c.startswith(('periodo','pagina','no. de cuenta:')) or re.fullmatch(r'\d+',c):continue
                if current is not None:
                    if desc_start is None or desc_end is None:raise ReaderError('Columnas Plata no reconocidas')
                    money_matches=list(re.finditer(_MONEY,line))
                    description=line[max(0,desc_start-3):max(0,desc_end-2)].strip()
                    if description:current[2].append(description)
                    if len(money_matches)>1:raise ReaderError('Continuación con varios importes Plata')
                    if money_matches:current[6].append(money_matches[0][0])
            # Keep an unfinished multi-line movement until next row or section.
        finish()
        products={}
        for lane in ('debit','investments'):
            s=summaries[lane];rr=tuple(rows[lane]);issues=[];timing=[]
            def check(label,a,b):
                if a!=b:issues.append(label)
            incoming=_sum(r.amount for r in rr if r.amount>0);outgoing=_sum(r.amount for r in rr if r.amount<0)
            check('Depósitos/rendimientos Plata no coinciden con detalle',s.deposits_and_income,incoming)
            check('Saldo Plata no concilia con filas publicadas',s.final,_sum((s.initial,incoming,outgoing)))
            check('Rendimiento Plata no coincide con resumen',s.gross_income_reported,_sum(r.amount for r in rr if r.category=='interest_received'))
            check('ISR Plata no coincide con detalle',-abs(s.isr_withheld_printed),_sum(r.amount for r in rr if r.category=='isr_withholding'))
            if any(r.category=='unmapped' for r in rr):issues.append('Concepto Plata sin mapeo')
            if any(r.currency!='MXN' or r.exchange_rate!=1 for r in rr):issues.append('Moneda/tipo de cambio Plata requiere mapeo específico')
            if any(r.outside_period for r in rr):timing.append('Filas publicadas con operación/cargo fuera del período: conservar fecha y atribución documental por separado')
            if any(a.operation_date>b.operation_date for a,b in zip(rr,rr[1:])):timing.append('Orden de operaciones Plata no cronológico')
            # Test only the fields actually printed for this product.
            equation=_sum((s.initial,s.deposits_and_income,s.other_charges_printed or Decimal(0),-abs(s.withdrawals_printed),
                -abs(s.commissions_printed),-abs(s.vat_withheld_printed),-abs(s.isr_withheld_printed)))
            check('Ecuación de campos publicados del producto Plata no concilia',s.final,equation)
            products[lane]=PlataProduct(lane,sha256(('plata-clabe:'+clabes[lane]).encode()).hexdigest(),s,rr,tuple(dict.fromkeys(issues)),tuple(dict.fromkeys(timing)))
        agg_issues=[]
        for key in ('initial','final','deposits_and_income'):
            if getattr(aggregate,key)!=_sum(getattr(s,key) for s in summaries.values()):agg_issues.append('Total Plata difiere de suma de productos: '+key)
        if aggregate.isr_withheld_printed!=_sum(s.isr_withheld_printed for s in summaries.values()):agg_issues.append('ISR informativo total difiere de productos')
        base=_sum((aggregate.initial,aggregate.deposits_and_income,aggregate.other_charges_printed or Decimal(0),
            -abs(aggregate.withdrawals_printed),-abs(aggregate.commissions_printed),-abs(aggregate.vat_withheld_printed)))
        with_extra=_sum((base,-abs(aggregate.isr_withheld_printed)))
        if base==aggregate.final and aggregate.isr_withheld_printed==0:basis='indistinguishable_zero_retention'
        elif base==aggregate.final:basis='arithmetic_included_in_other_charges'
        elif with_extra==aggregate.final:basis='additional_to_other_charges'
        else:basis='unexplained';agg_issues.append('Base del total Plata no conciliada; no ajustar ISR')
        transfers=[]
        outgoing=[r for r in rows['debit'] if r.category=='own_transfer_out']
        incoming=[r for r in rows['investments'] if r.category=='own_transfer_in']
        def match(a,b):return a.operation_date==b.operation_date and a.posting_date==b.posting_date and a.currency==b.currency and a.exchange_rate==b.exchange_rate and -a.amount==b.amount
        for a in outgoing:
            found=[b for b in incoming if match(a,b)]
            if len(found)==1 and sum(match(other,found[0]) for other in outgoing)==1:
                cashback=[r for r in rows['debit'] if r.category=='cashback_contribution' and r.operation_date==a.operation_date and r.posting_date==a.posting_date and r.amount==-a.amount]
                origin=cashback[0].evidence_id if len(cashback)==1 and len(rows['debit'])==2 and summaries['debit'].initial==0 else None
                transfers.append(PlataTransferCandidate(a.evidence_id,found[0].evidence_id,-a.amount,origin))
        return PlataPreview(identifier,start,end,relationship,products['debit'],products['investments'],aggregate,basis,
            tuple(dict.fromkeys(agg_issues)),tuple(transfers),tuple(annex),self.lane)
