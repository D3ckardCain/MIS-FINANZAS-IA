"""SuperTasas: cash paid versus fixed-term snapshots, without financial writes."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import re
from .ledger import _sum
from .readers import ReaderError,fold

_NUM=r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?|\.\d{1,2}'
_VALID=re.compile(r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?|\.\d{1,2}')
_MONTHS='enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()

def decimal(text):
    text=text.strip()
    if not _VALID.fullmatch(text):raise ReaderError('Importe SuperTasas no reconocido')
    return Decimal(text.replace(',',''))


def compact(text):return re.sub(r'\s+','',fold(text))


def field(text,label):
    found=re.findall(re.escape(label)+r'\s*\$?\s*('+_NUM+r')(?=\s|$)',text)
    if len(found)!=1 or not found[0]:raise ReaderError('Campo SuperTasas ausente/ambiguo: '+label)
    return decimal(found[0])


@dataclass(frozen=True)
class SuperTasasSummary:
    initial: Decimal | None
    final: Decimal
    deposits: Decimal
    withdrawals: Decimal
    gross_interest: Decimal
    retention: Decimal
    net_interest: Decimal
    annual_rate_reported: Decimal
    average_balance: Decimal
    fees: Decimal
    fees_vat: Decimal
    term_fees: Decimal
    term_fees_vat: Decimal
    unit: str | None = None


@dataclass(frozen=True)
class SuperTasasEntry:
    evidence_id: str
    effective_date: date
    description: str
    reference: str
    deposit: Decimal
    withdrawal: Decimal
    balance: Decimal
    category: str
    page: int
    line: int


@dataclass(frozen=True)
class SuperTasasContract:
    snapshot_key: str
    principal: Decimal
    term_days: int
    opened: date
    maturity: date
    projected_gross: Decimal
    projected_retention: Decimal
    projected_net: Decimal
    capital_at_maturity_reported: Decimal
    annual_rate: Decimal
    gat_nominal: Decimal
    gat_real: Decimal
    maturity_amount_form: str
    page: int
    line: int


@dataclass(frozen=True)
class SuperTasasPreview:
    document_id: str
    period_start: date
    period_end: date
    account_fingerprint: str
    summary: SuperTasasSummary
    rows: tuple[SuperTasasEntry,...]
    contracts: tuple[SuperTasasContract,...]
    cash_issues: tuple[str,...]
    contract_issues: tuple[str,...]
    lane: str
    shared_account: bool = True
    currency_markers: tuple[str,...] = ()

    @property
    def entries(self):return self.rows if self.lane=='debit' else tuple(r for r in self.rows if r.category not in ('incoming_transfer','outgoing_transfer'))
    @property
    def issues(self):return self.cash_issues+self.contract_issues
    @property
    def detail_issues(self):return ()
    @property
    def detail_reconciled(self):return not self.cash_issues
    @property
    def reconciled(self):return not self.issues
    @property
    def ready_to_import(self):return False


def category(text):
    c=compact(text)
    if c in ('aperturainversion','aperturacede'):return 'term_opening'
    if c in ('pagoinversion.capital','pagocede.capital'):return 'principal_return'
    if c.startswith(('pagoinversion.interes','pagocede.interes')):return 'term_interest'
    if c=='pagorendimientocta.gravado':return 'vista_interest'
    if c in ('recepcionspei','abonostp'):return 'incoming_transfer'
    if c in ('enviospei','retiroacuenta'):return 'outgoing_transfer'
    return 'unmapped'


class SuperTasasReader:
    def __init__(self,lane='investments'):
        if lane not in ('debit','investments'):raise ReaderError('Vista SuperTasas desconocida')
        self.lane=lane

    def read_image(self,content,*,engine=None):
        from .imaging import read_statement_image
        return read_statement_image(content,'supertasas',self.lane,engine=engine)

    def read_pdf(self,content,*,password=None):
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            pdf=PdfReader(BytesIO(content))
            if pdf.is_encrypted and (password is None or not pdf.decrypt(password)):raise ReaderError('PDF SuperTasas protegido: contraseña requerida o no válida')
            pages=tuple(p.extract_text(extraction_mode='layout') or '' for p in pdf.pages)
        except PyPdfError as error:raise ReaderError('PDF SuperTasas no legible') from error
        return self.read_pages(pages,sha256(content).hexdigest())

    def read_pages(self,pages,identifier):
        pages=tuple(pages);text='\n'.join(pages)
        if 'supertasas.com' not in fold(text) or 'crediclub' not in fold(text):raise ReaderError('Identidad SuperTasas ausente')
        periods=re.findall(r'Periodo:\s*(\d{2})\s+al\s+(\d{2})\s+de\s+(\w+)\s+del\s+(\d{4})',text)
        accounts=set(re.findall(r'Núm\. de Cuenta:\s*(\d+)',text))
        if len(periods)!=1 or len(accounts)!=1:raise ReaderError('Cuenta/período SuperTasas ambiguo')
        a,b,month,year=periods[0]
        if fold(month) not in _MONTHS:raise ReaderError('Mes SuperTasas no reconocido')
        start=date(int(year),_MONTHS.index(fold(month))+1,int(a));end=date(start.year,start.month,int(b))
        if start>end:raise ReaderError('Período SuperTasas invertido')
        account=sha256(('supertasas:'+accounts.pop()).encode()).hexdigest()
        summary_part=text.split('RESUMEN DE MOVIMIENTOS EN CUENTA A LA VISTA',1)
        if len(summary_part)!=2:raise ReaderError('Resumen SuperTasas ausente')
        cash_summary=summary_part[1].split('DETALLE DE MOVIMIENTOS',1)[0]
        before=summary_part[0];commissions=text.split('RESUMEN DE COMISIONES EN INVERSION A PLAZO',1)
        if len(commissions)!=2:raise ReaderError('Comisiones a plazo no informadas')
        term_commissions=commissions[1].split('RESUMEN DE INVERSIONES A PLAZO VIGENTES',1)[0]
        initial_match=re.search(r'Saldo Inicial[ \t]+([^\n]*)',cash_summary)
        if not initial_match:raise ReaderError('Etiqueta de saldo inicial ausente')
        initial_cell=initial_match[1].split('Saldo Promedio diario',1)[0].strip()
        initial=decimal(initial_cell) if initial_cell else None
        s=SuperTasasSummary(initial,field(cash_summary,'Saldo Final'),field(cash_summary,'(+) Abonos'),
            field(cash_summary,'(-) Cargos'),field(cash_summary,'Intereses Brutos'),field(cash_summary,'Retención ISR'),
            field(cash_summary,'Intereses Netos'),field(before,'Tasa de interés o rendimiento'),field(cash_summary,'Saldo Promedio diario'),
            field(before,'Total de Comisiones Cobradas'),field(before,'IVA de Comisiones'),field(term_commissions,'Total de Comisiones Cobradas'),field(term_commissions,'IVA de Comisiones'))
        # La leyenda del rendimiento en pesos no acredita la moneda de la cuenta.
        currency_text=fold(text)
        markers=set(re.findall(r'\b(?:moneda|divisa)\s*:?\s*([A-Z]{3})\b',text,re.I))
        markers={m.upper() for m in markers}
        if re.search(r'\b(?:moneda\s*:?\s*(?:nacional|pesos mexicanos)|divisa\s*:?\s*pesos mexicanos)\b',currency_text):markers.add('MXN')
        from dataclasses import replace
        s=replace(s,unit='MXN' if markers=={'MXN'} else None)
        rows=[];contracts=[];cash_issues=[];contract_issues=[];section=None;header=None;had_cash_header=False
        for pno,page in enumerate(pages,1):
            for lno,line in enumerate(page.splitlines(),1):
                c=compact(line)
                if c.startswith('detalledemovimientosencuentaala'):section='cash';header=None;continue
                if c.startswith('resumendecomisioneseninversionaplazo'):section=None;continue
                if c.startswith('resumendeinversionesaplazovigentes'):section='contracts';continue
                if c.startswith(('*lagatreal','detalledecomisiones','supertasas.com')):section=None;continue
                if section=='cash':
                    if all(k in line for k in ('FECHA','REFERENCIA','CARGO','ABONO','SALDO')):
                        header=tuple(line.index(k) for k in ('DESCRIPCION','REFERENCIA','CARGO','ABONO','SALDO'));had_cash_header=True;continue
                    when=re.match(r'^\s*(\d{4}-\d{2}-\d{2})\s+',line)
                    if when:
                        if header is None:raise ReaderError('Columnas SuperTasas ausentes')
                        desc,ref,cargo,abono,saldo=header
                        token='(?:'+_VALID.pattern+')'
                        pattern=r'^\s*(\d{4}-\d{2}-\d{2})\s+\d+\s+(.+?)\s{2,}(\d+)\s+('+token+r')\s+(\(?'+token+r'\)?)\s*$'
                        match=re.match(pattern,line)
                        if not match:raise ReaderError('Fila monetaria SuperTasas no reconocida')
                        description=match[2].strip();reference=match[3]
                        number=decimal(match[4]);printed_balance=match[5]
                        if printed_balance.startswith('(') != printed_balance.endswith(')'):raise ReaderError('Signo de saldo SuperTasas ambiguo')
                        balance=-decimal(printed_balance[1:-1]) if printed_balance.startswith('(') else decimal(printed_balance)
                        # Header labels are centered; numbers can start left of labels.
                        boundary=(cargo+abono)/2
                        inc=number if match.start(4)>boundary else Decimal(0)
                        out=number if match.start(4)<=boundary else Decimal(0)
                        if (out>0)==(inc>0):raise ReaderError('Movimiento SuperTasas sin sentido único')
                        rows.append(SuperTasasEntry(sha256(f'{identifier}:{pno}:{lno}'.encode()).hexdigest(),date.fromisoformat(when[1]),description,reference,inc,out,balance,category(description),pno,lno))
                    elif line.strip() and header is not None:
                        if not line[:header[0]].strip() and not line[header[1]:].strip():
                            if not rows:raise ReaderError('Continuación SuperTasas sin movimiento')
                            from dataclasses import replace
                            rows[-1]=replace(rows[-1],description=rows[-1].description+' '+line[header[0]:header[1]].strip())
                        else:raise ReaderError('Contenido de tabla SuperTasas no reconocido')
                elif section=='contracts' and re.search(r'\d{4}-\d{2}-\d{2}',line):
                    parts=line.replace('%',' ').replace('*',' ').split()
                    if len(parts)!=11:raise ReaderError('Fila de inversión SuperTasas no reconocida')
                    principal=decimal(parts[0]);days=int(parts[1]);opened=date.fromisoformat(parts[2]);maturity=date.fromisoformat(parts[3])
                    gross,tax,net,capital,rate,gat,real=map(decimal,parts[4:])
                    mode='principal_only' if capital==principal else ('principal_plus_net' if capital==_sum((principal,net)) else 'unexplained')
                    key=sha256(f'{account}:{opened}:{maturity}:{principal}'.encode()).hexdigest()
                    if any(t.snapshot_key==key for t in contracts):raise ReaderError('Posición a plazo duplicada en el mismo estado')
                    contracts.append(SuperTasasContract(key,principal,days,opened,maturity,gross,tax,net,capital,rate,gat,real,mode,pno,lno))
                    if _sum((gross,-tax))!=net:contract_issues.append('Proyección bruta menos retención difiere del neto')
                    if (maturity-opened).days!=days:contract_issues.append('Plazo informado difiere de fechas de inversión')
                    if maturity<=end:contract_issues.append('Posición publicada como vigente con vencimiento al corte o anterior')
                    if opened>end:contract_issues.append('Posición publicada antes de su fecha de apertura')
                    if mode=='unexplained':contract_issues.append('Capital al vencimiento no corresponde a las dos formas documentadas')
        if not had_cash_header:raise ReaderError("Encabezado de movimientos SuperTasas ausente")
        previous=s.initial
        if previous is None:cash_issues.append('Saldo inicial no publicado; no se sustituye por cero')
        for r in rows:
            if previous is not None and _sum((previous,r.deposit,-r.withdrawal))!=r.balance:cash_issues.append('Saldo de movimiento SuperTasas no concilia')
            if not start<=r.effective_date<=end:cash_issues.append('Movimiento fuera del período')
            if r.category=='unmapped':cash_issues.append('Concepto SuperTasas sin mapeo')
            previous=r.balance
        if previous is not None and previous!=s.final:cash_issues.append('Cierre SuperTasas no concilia')
        if _sum(r.deposit for r in rows)!=s.deposits:cash_issues.append('Abonos SuperTasas no concilian')
        if _sum(r.withdrawal for r in rows)!=s.withdrawals:cash_issues.append('Cargos SuperTasas no concilian')
        if s.initial is not None and _sum((s.initial,s.deposits,-s.withdrawals))!=s.final:cash_issues.append('Resumen de efectivo no concilia')
        if _sum((s.gross_interest,-s.retention))!=s.net_interest:cash_issues.append('Bruto/retención/neto a la vista no concilian')
        if _sum(r.deposit for r in rows if r.category=='vista_interest')!=s.net_interest:cash_issues.append('Rendimiento de cuenta no coincide con resumen')
        if field(before,'Rendimiento bruto en pesos mexicanos')!=s.gross_interest:cash_issues.append('Rendimiento repetido no coincide')
        if any(getattr(s,k)!=0 for k in ('retention','fees','fees_vat','term_fees','term_fees_vat')):cash_issues.append('Retención/comisión no nula requiere detalle específico')
        if any(a.effective_date>b.effective_date for a,b in zip(rows,rows[1:])):cash_issues.append('Fechas de movimientos fuera de orden')
        if not contracts:contract_issues.append('Sin posiciones legibles: no se supone inversión cero')
        return SuperTasasPreview(identifier,start,end,account,s,tuple(rows),tuple(contracts),tuple(dict.fromkeys(cash_issues)),tuple(dict.fromkeys(contract_issues)),self.lane,currency_markers=tuple(sorted(markers)))


@dataclass(frozen=True)
class SuperTasasMatch:
    snapshot_key: str
    evidence_id: str
    kind: str
    status: str = 'candidate_requires_review'


@dataclass(frozen=True)
class SuperTasasHistory:
    documents: tuple[SuperTasasPreview,...]
    duplicates: tuple[str,...]
    candidates: tuple[SuperTasasMatch,...]
    issues: tuple[str,...]


def review_supertasas(previews):
    unique={};duplicates=[];issues=[]
    for p in previews:
        if p.document_id in unique:
            if (p.period_start,p.period_end,p.summary,p.rows,p.contracts)!=(unique[p.document_id].period_start,unique[p.document_id].period_end,unique[p.document_id].summary,unique[p.document_id].rows,unique[p.document_id].contracts):raise ReaderError('Huella SuperTasas con metadatos distintos')
            duplicates.append(p.document_id)
        else:unique[p.document_id]=p
    docs=tuple(sorted(unique.values(),key=lambda p:p.period_start))
    if len({p.account_fingerprint for p in docs})>1:raise ReaderError('Historia SuperTasas mezcla cuentas')
    for a,b in zip(docs,docs[1:]):
        if b.period_start<=a.period_end:raise ReaderError('Períodos SuperTasas solapados')
    snapshots={}
    for p in docs:
        for t in p.contracts:
            if t.snapshot_key in snapshots:
                old=snapshots[t.snapshot_key]
                if (t.annual_rate,t.projected_gross,t.projected_retention,t.projected_net)!=(old.annual_rate,old.projected_gross,old.projected_retention,old.projected_net):issues.append('Condiciones de la misma huella de posición cambian; revisar')
            snapshots[t.snapshot_key]=t
    candidates=[]
    operations=[r for p in docs for r in p.rows if r.category in ('term_opening','principal_return')]
    def compatible(t,r):
        return (t.opened==r.effective_date and t.principal==r.withdrawal) if r.category=='term_opening' else (t.maturity==r.effective_date and t.principal==r.deposit)
    for r in operations:
        found=[t for t in snapshots.values() if compatible(t,r)]
        if len(found)==1 and sum(other.category==r.category and compatible(found[0],other) for other in operations)==1:
            candidates.append(SuperTasasMatch(found[0].snapshot_key,r.evidence_id,r.category))
        else:issues.append('Apertura/devolución de principal sin posición única compatible')
    return SuperTasasHistory(docs,tuple(duplicates),tuple(candidates),tuple(dict.fromkeys(issues)))
