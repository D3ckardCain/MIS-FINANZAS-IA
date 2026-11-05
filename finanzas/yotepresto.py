"""YoTePresto: reported summary, cash journal and cumulative loan snapshots."""
from dataclasses import dataclass,replace
from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import re
from .readers import ReaderError,parse_date,fold,periods
from .openbank import _fold
from .ledger import _sum

_MONEY=r'[-−]?\s*\$\s*(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}'
_CASH=re.compile(_MONEY)


def money(text):return Decimal(re.sub(r'[\s$,]','',text).replace('−','-'))


@dataclass(frozen=True)
class YoTePrestoSummary:
    initial: Decimal
    final: Decimal
    available: Decimal
    interest_received_with_vat: Decimal
    ordinary_interest: Decimal
    interest_vat: Decimal
    late_interest: Decimal
    late_interest_vat: Decimal
    commission_total: Decimal
    commission_base: Decimal
    commission_vat: Decimal
    retention_total: Decimal | None
    retention_vat: Decimal | None
    retention_isr: Decimal | None
    funds_added: Decimal
    withdrawals: Decimal
    investments_made: Decimal
    payments_received: Decimal
    total_invested_reported: Decimal
    gain_reported: Decimal
    gain_basis_observed: str


@dataclass(frozen=True)
class YoTePrestoPosition:
    status: str
    count_reported: int | None
    share_reported: Decimal
    amount_reported: Decimal


@dataclass(frozen=True)
class YoTePrestoMovement:
    evidence_id: str
    effective_date: date
    concept: str
    reference: str
    amount: Decimal
    balance: Decimal
    category: str
    page: int
    line: int


@dataclass(frozen=True)
class YoTePrestoLoan:
    evidence_id: str
    loan_id: str
    opened: date
    borrower_printed: str | None
    status: str
    term_printed: str
    rate_reported: Decimal
    lent: Decimal
    initial: Decimal
    final: Decimal
    interest_paid_cumulative: Decimal
    interest_vat_cumulative: Decimal
    principal_paid_cumulative: Decimal
    page: int
    line: int


@dataclass(frozen=True)
class YoTePrestoArrears:
    loan_id: str
    status: str
    days: int
    details_printed: str
    page: int
    line: int


@dataclass(frozen=True)
class YoTePrestoDifference:
    check: str
    reported: Decimal
    calculated: Decimal
    page: int | None = None
    line: int | None = None


@dataclass(frozen=True)
class YoTePrestoPreview:
    document_id: str
    period_start: date
    period_end: date
    account_fingerprint: str
    summary: YoTePrestoSummary
    positions: tuple[YoTePrestoPosition,...]
    rows: tuple[YoTePrestoMovement,...]
    loans: tuple[YoTePrestoLoan,...]
    arrears: tuple[YoTePrestoArrears,...]
    differences: tuple[YoTePrestoDifference,...]
    summary_issues: tuple[str,...]
    cash_issues: tuple[str,...]
    portfolio_issues: tuple[str,...]
    cash_initial_implied: Decimal | None
    lane: str
    shared_account: bool = True
    scope: str = 'platform_cash_and_lending'
    investment_balance: None = None

    @property
    def entries(self):return self.rows
    @property
    def issues(self):return self.summary_issues+self.portfolio_issues
    @property
    def detail_issues(self):return self.cash_issues
    @property
    def summary_reconciled(self):return not self.summary_issues
    @property
    def composition_issues(self):return self.portfolio_issues
    @property
    def detail_reconciled(self):return not self.cash_issues
    @property
    def reconciled(self):return not self.issues and not self.detail_issues
    @property
    def ready_to_import(self):return False


def category(concept):
    return {'abono':'funding','retiro':'withdrawal','prestamo':'loan_funding','pago':'repayment',
        'retencion':'retention','comision':'commission','comision por exito':'commission',
        'administracion por exito':'commission','cancelacion de prestamo':'loan_cancellation',
        'cancelacion de pago':'payment_cancellation','cancelacion de comision':'commission_cancellation',
        'cancelacion de administracion por exito':'commission_cancellation','cancelacion de retencion':'retention_cancellation'}.get(fold(concept),'unmapped')


class YoTePrestoReader:
    def __init__(self,lane='investments'):
        if lane not in ('debit','investments'):raise ReaderError('Vista YoTePresto desconocida')
        self.lane=lane

    def read_image(self,content,*,engine=None):
        from .imaging import read_statement_image
        return read_statement_image(content,'yotepresto',self.lane,engine=engine)

    def read_pdf(self,content):
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            pdf=PdfReader(BytesIO(content))
            if pdf.is_encrypted:raise ReaderError('PDF YoTePresto protegido')
            pages=tuple(p.extract_text(extraction_mode='layout') or '' for p in pdf.pages)
        except PyPdfError as e:raise ReaderError('PDF YoTePresto no legible') from e
        return self.read_pages(pages,sha256(content).hexdigest())

    def read_pages(self,pages,identifier):
        pages=tuple(pages)
        if not pages or not any('yotepresto.com' in fold(p) for p in pages):raise ReaderError('Identidad YoTePresto ausente')
        first=pages[0];norm=_fold(first)
        ids=set(re.findall(r'\bID:\s*(\d+)',first));ranges=periods(first)
        if len(ids)!=1 or len(ranges)!=1:raise ReaderError('Usuario/período YoTePresto ausente o ambiguo')
        start,end=ranges[0];account=sha256(('yotepresto:'+ids.pop()).encode()).hexdigest()
        def take(label,*,optional=False,anchored=True):
            pattern=(r'^\s*' if anchored else '')+re.escape(_fold(label))+r'\s+('+_MONEY+r')'
            values=re.findall(pattern,norm,re.M)
            if not values and optional:return None
            if len(values)!=1:raise ReaderError('Campo YoTePresto ausente o ambiguo: '+label)
            return money(values[0])
        def any_label(labels):
            found=[take(k,optional=True) for k in labels];found=[v for v in found if v is not None]
            if len(found)!=1:raise ReaderError('Comisión YoTePresto no reconocida')
            return found[0]
        received=take('(+) Intereses recibidos');fee=any_label(('(-) Comisión por éxito','(-) Administración por Éxito'))
        ret=take('(-) Retenciones',optional=True);vat=take('Retenciones IVA',optional=True);isr=take('Retenciones ISR',optional=True)
        if (ret is None)!=(vat is None) or (ret is None)!=(isr is None):raise ReaderError('Desglose de retención YoTePresto parcial')
        gain=take('En este periodo ganaste:',anchored=False)
        before=_sum((received,-fee));after=_sum((received,-fee,-ret)) if ret is not None else None
        basis='before_retention' if gain==before else ('after_retention' if gain==after else 'unexplained')
        s=YoTePrestoSummary(take('Saldo inicial del periodo'),take('Saldo final del periodo'),
            take('Saldo disponible para retiro a la fecha',anchored=False),received,take('Intereses'),take('IVA de Intereses'),
            take('Intereses Moratorios'),take('IVA de Intereses Moratorios'),fee,take('Comisión'),take('IVA Comisión'),
            ret,vat,isr,take('(+) Fondos Agregados'),take('(-) Retiros'),take('Inversiones realizadas:',anchored=False),
            take('Pagos recibidos:',anchored=False),take('Monto total invertido:',anchored=False),gain,basis)
        positions=[]
        pattern=r'(Al corriente|En tránsito|Atrasado|Vencido|Pagado)\s+(\d+|--)\s+([\d.]+)%\s+('+_MONEY+r')'
        for match in re.finditer(pattern,first,re.I):positions.append(YoTePrestoPosition(fold(match[1]),int(match[2]) if match[2]!='--' else None,Decimal(match[3]),money(match[4])))
        summary_issues=[];cash_issues=[];portfolio=[];differences=[]
        def check(key,reported,calculated,target,page=None,line=None):
            if reported!=calculated:
                target.append(key);differences.append(YoTePrestoDifference(key,reported,calculated,page,line))
        check('Desglose de intereses/IVA no coincide con recibido',received,_sum((s.ordinary_interest,s.interest_vat,s.late_interest,s.late_interest_vat)),summary_issues)
        check('Comisión más IVA no coincide con total',fee,_sum((s.commission_base,s.commission_vat)),summary_issues)
        if ret is not None:
            check('IVA/ISR no coinciden con retención total',ret,_sum((vat,isr)),summary_issues)
            check('Resumen global YoTePresto no concilia',s.final,_sum((s.initial,received,-fee,-ret,s.funds_added,-s.withdrawals)),summary_issues)
        else:summary_issues.append('Retenciones no publicadas: desconocido, no cero')
        if basis=='unexplained':summary_issues.append('Ganancia publicada no corresponde a bases cotejadas')
        check('Fondos repetidos en flujo no coinciden',s.funds_added,take('Recursos fondeados:',anchored=False),summary_issues)
        check('Retiros repetidos en flujo no coinciden',s.withdrawals,take('Recursos retirados:',anchored=False),summary_issues)
        check('Comisiones repetidas en flujo no coinciden',fee,take('Comisiones cobradas:',anchored=False),summary_issues)
        rows=[];loans=[];arrears=[];section=None
        for pno,page in enumerate(pages[1:],2):
            for lno,line in enumerate(page.splitlines(),1):
                normalized=fold(line)
                if re.match(r'^fecha\s+concepto\s+usuario',normalized):section='cash';continue
                if re.match(r'^fecha\s+id\b',normalized) and 'tasa' in normalized:section='loans';continue
                if normalized.startswith('id estatus dias de atraso'):section='arrears';continue
                if normalized=='mis movimientos':section='cash';continue
                if normalized=='inversiones realizadas':section='loans';continue
                if normalized=='inversiones realizadas atrasadas':section='arrears';continue
                if normalized.startswith(('todas las cantidades','los recursos de los usuarios','comunidad de prestamos')):section=None
                if section=='cash' and re.match(r'^\s*\d{2}/\d{2}/\d{4}\b',line):
                    match=re.match(r'^\s*(\d{2}/\d{2}/\d{4})\s+(.+?)\s{2,}(\S+)\s+('+_MONEY+r')\s+('+_MONEY+r')\s*$',line)
                    if not match:raise ReaderError(f'Fila operativa YoTePresto no reconocida en página {pno}')
                    rows.append(YoTePrestoMovement(sha256(f'{identifier}:{pno}:{lno}'.encode()).hexdigest(),parse_date(match[1]),match[2].strip(),match[3],money(match[4]),money(match[5]),category(match[2]),pno,lno))
                elif section=='loans' and re.match(r'^\s*\d{2}/\d{2}/\d{4}\b',line):
                    amounts=_CASH.findall(line)
                    head=re.match(r'^\s*(\d{2}/\d{2}/\d{4})\s+(\d+)\s+(.+?)\s+(\d+/\d+)\s+([\d.]+)%\s+\$',line)
                    if head is None or len(amounts)!=6:raise ReaderError(f'Posición YoTePresto no reconocida en página {pno}')
                    prefix=head[3].strip()
                    borrower_match=re.match(r'^([A-Z]+-[0-9]*)\s+(.+)$',prefix)
                    borrower=borrower_match[1] if borrower_match else None
                    status=borrower_match[2] if borrower_match else prefix
                    vals=tuple(money(v) for v in amounts)
                    loans.append(YoTePrestoLoan(sha256(f'{identifier}:{pno}:{lno}'.encode()).hexdigest(),head[2],parse_date(head[1]),borrower,fold(status),head[4],Decimal(head[5]),*vals,pno,lno))
                elif section=='loans' and re.fullmatch(r'\s*\d+\s*',line) and loans and loans[-1].borrower_printed is not None:
                    loans[-1]=replace(loans[-1],borrower_printed=loans[-1].borrower_printed+line.strip())
                elif section=='arrears':
                    match=re.match(r'^\s*(\d+)\s+(Atrasado|Vencido)\s+(\d+)\s*(.*)$',line,re.I)
                    if match:arrears.append(YoTePrestoArrears(match[1],fold(match[2]),int(match[3]),match[4].strip(),pno,lno))
        implied=_sum((rows[0].balance,-rows[0].amount)) if rows else None
        previous=None
        cash_issues.append('Saldo inicial de efectivo no publicado; candidato aritmético sin confirmar')
        for r in rows:
            if previous is not None:check('Saldo operativo por fila no concilia',r.balance,_sum((previous,r.amount)),cash_issues,r.page,r.line)
            previous=r.balance
            if not start<=r.effective_date<=end:cash_issues.append('Fecha operativa fuera del período')
            if r.category=='unmapped':cash_issues.append('Concepto operativo sin mapeo')
        if previous is not None:check('Último saldo operativo difiere del disponible',s.available,previous,cash_issues)
        elif s.payments_received or s.funds_added or s.investments_made:cash_issues.append('Faltan movimientos operativos')
        if any(a.effective_date>b.effective_date for a,b in zip(rows,rows[1:])):cash_issues.append('Fechas operativas fuera de orden publicado')
        for cat,total in [('funding',s.funds_added),('withdrawal',s.withdrawals),('repayment',s.payments_received)]:
            value=_sum((r.amount if cat!='withdrawal' else -r.amount) for r in rows if r.category==cat)
            check('Flujo operativo de '+cat+' no coincide con resumen',total,value,cash_issues)
        net_commission=-_sum(r.amount for r in rows if r.category in ('commission','commission_cancellation'))
        check('Comisiones netas del diario difieren del resumen',s.commission_total,net_commission,cash_issues)
        if s.retention_total is not None:
            net_retention=-_sum(r.amount for r in rows if r.category in ('retention','retention_cancellation'))
            check('Retenciones netas del diario difieren del resumen',s.retention_total,net_retention,cash_issues)
        gross_lending=-_sum(r.amount for r in rows if r.category=='loan_funding')
        net_lending=-_sum(r.amount for r in rows if r.category in ('loan_funding','loan_cancellation'))
        if s.investments_made not in (gross_lending,net_lending):
            check('Inversiones informadas difieren del fondeo bruto y neto de cancelaciones',s.investments_made,net_lending,cash_issues)
        ids=[l.loan_id for l in loans]
        if len(ids)!=len(set(ids)):portfolio.append('IDs de préstamo repetidos en una misma instantánea; no fusionar')
        if not loans:portfolio.append('Sin posiciones legibles: no se supone cartera cero')
        active=_sum(l.final for l in loans)
        reported_active=_sum(p.amount_reported for p in positions if p.status!='pagado')
        if positions:check('Cartera detallada difiere de categorías publicadas',reported_active,active,portfolio)
        else:portfolio.append('Categorías de cartera no reconocidas')
        check('Saldo global difiere de cartera más disponible',s.final,_sum((active,s.available)),portfolio)
        if any(l.opened>end for l in loans):portfolio.append('Préstamo abierto después del corte')
        return YoTePrestoPreview(identifier,start,end,account,s,tuple(positions),tuple(rows),tuple(loans),tuple(arrears),tuple(differences),
            tuple(dict.fromkeys(summary_issues)),tuple(dict.fromkeys(cash_issues)),tuple(dict.fromkeys(portfolio)),implied,self.lane)


@dataclass(frozen=True)
class YoTePrestoCashLink:
    period_start: date
    previous_available: Decimal
    next_implied: Decimal | None
    matches: bool


@dataclass(frozen=True)
class YoTePrestoCumulativeChange:
    loan_id: str
    field: str
    previous: Decimal
    current: Decimal
    period_start: date


@dataclass(frozen=True)
class YoTePrestoHistory:
    documents: tuple[YoTePrestoPreview,...]
    duplicates: tuple[str,...]
    cash_links: tuple[YoTePrestoCashLink,...]
    cumulative_decreases: tuple[YoTePrestoCumulativeChange,...]


def review_yotepresto(previews):
    from datetime import timedelta
    unique={};duplicates=[]
    for p in previews:
        if p.document_id in unique:
            old=unique[p.document_id]
            if (p.period_start,p.period_end,p.account_fingerprint,p.summary,p.rows,p.loans)!=(old.period_start,old.period_end,old.account_fingerprint,old.summary,old.rows,old.loans):raise ReaderError('Huella YoTePresto con metadatos incompatibles')
            duplicates.append(p.document_id)
        else:unique[p.document_id]=p
    docs=tuple(sorted(unique.values(),key=lambda p:p.period_start))
    if len({p.account_fingerprint for p in docs})>1:raise ReaderError('Historia YoTePresto mezcla usuarios')
    links=[];decreases=[]
    for a,b in zip(docs,docs[1:]):
        if b.period_start<=a.period_end:raise ReaderError('Historia YoTePresto tiene períodos solapados')
        if b.period_start!=a.period_end+timedelta(days=1):continue
        links.append(YoTePrestoCashLink(b.period_start,a.summary.available,b.cash_initial_implied,a.summary.available==b.cash_initial_implied))
        aa={l.loan_id:l for l in a.loans};bb={l.loan_id:l for l in b.loans}
        if len(aa)!=len(a.loans) or len(bb)!=len(b.loans):continue  # No ambiguous loan merge.
        for key in sorted(aa.keys()&bb.keys()):
            for name in ('interest_paid_cumulative','interest_vat_cumulative','principal_paid_cumulative'):
                old=getattr(aa[key],name);new=getattr(bb[key],name)
                if new<old:decreases.append(YoTePrestoCumulativeChange(key,name,old,new,b.period_start))
    return YoTePrestoHistory(docs,tuple(duplicates),tuple(links),tuple(decreases))
