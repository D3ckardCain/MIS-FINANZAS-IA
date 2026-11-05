"""Nu annual certificate evidence. No tax return, cash entry or SAT validation."""
from dataclasses import dataclass,asdict
from datetime import date
from calendar import monthrange
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import argparse
import json
import re

from .readers import ReaderError,fold
from .ledger import _sum
from .nu import money,value

_FIELDS=(('operation','Monto total de la operación'),('taxable','Monto total gravado'),
    ('exempt','Monto total exento'),('total_retention','Monto total de las retenciones'),
    ('withholding_base','Base del impuesto retenido'),('period_retention','Monto retenido en el periodo'),
    ('nominal_interest','Interés nominal'),('real_interest','Interés real'),
    ('inflation_loss','Pérdida inflacionaria'))
_RFC=r'[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}'


@dataclass(frozen=True)
class NuTaxValues:
    operation: Decimal
    taxable: Decimal
    exempt: Decimal
    total_retention: Decimal
    withholding_base: Decimal
    period_retention: Decimal
    nominal_interest: Decimal
    real_interest: Decimal
    inflation_loss: Decimal


@dataclass(frozen=True)
class NuTaxDifference:
    check: str
    visible: Decimal
    compared: Decimal


@dataclass(frozen=True)
class NuTaxPreview:
    document_id: str
    period_start: date
    period_end: date
    issuer_fingerprint: str
    recipient_fingerprint: str
    generic_recipient: bool
    uuid: str
    values: NuTaxValues
    chain_values: NuTaxValues
    payment_type_reported: str
    financial_system_reported: str
    withdrawn_reported: str
    derivatives_reported: str
    differences: tuple[NuTaxDifference, ...]
    issues: tuple[str, ...]
    payment_code_reported: str = ''
    tax_label_reported: str = ''
    tax_code_reported: str = ''
    visible_page: int = 1
    chain_page: int | None = None
    unit: str = 'MXN'
    signature_verified: bool = False
    ready_to_import: bool = False

    @property
    def internally_consistent(self):return not self.issues


class NuTaxReader:
    def read_image(self,content,*,engine=None):
        from .imaging import read_statement_image
        return read_statement_image(content,'nu','investments',engine=engine)

    def read_pdf(self,content):
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            pdf=PdfReader(BytesIO(content))
            if pdf.is_encrypted:raise ReaderError('Constancia Nu cifrada')
            pages=tuple(p.extract_text(extraction_mode='layout') or '' for p in pdf.pages)
        except PyPdfError as error:raise ReaderError('PDF de constancia Nu no legible') from error
        return self.read_pages(pages,sha256(content).hexdigest())

    def read_pages(self,pages,identifier):
        pages=tuple(pages);text='\n'.join(pages)
        if not pages or 'nu mexico financiera' not in fold(pages[0]):raise ReaderError('Emisor de constancia Nu no reconocido')
        if 'CONSTANCIA DE PERCEPCIONES Y RETENCIONES DE INTERESES' not in text:raise ReaderError('Tipo de constancia Nu no reconocido')
        periods=re.findall(r'Periodo:\s*(\d{1,2})\s*-\s*(\d{1,2})\s+del\s+(\d{4})',text)
        if len(periods)!=1:raise ReaderError('Período de constancia Nu ausente o ambiguo')
        first,last,year=map(int,periods[0])
        if not 1<=first<=last<=12:raise ReaderError('Meses de constancia Nu inválidos')
        start=date(year,first,1);end=date(year,last,monthrange(year,last)[1])
        issuers=set(re.findall(r'RFC:\s*('+_RFC+r')',pages[0]))
        recipients=re.findall(r'RFC\s+('+_RFC+r')',pages[0])
        if len(issuers)!=1 or len(recipients)!=1:raise ReaderError('Identidad fiscal Nu ausente o ambigua')
        issuer=issuers.pop();recipient=recipients[0]
        uuid=re.findall(r'FOLIO DEL SAT \(UUID\):\s*([0-9a-fA-F-]{36})',text)
        if len(uuid)!=1 or not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',uuid[0]):raise ReaderError('UUID de constancia Nu no reconocido')
        vals=NuTaxValues(**{key:value(pages[0],label) for key,label in _FIELDS})
        chains=re.findall(r'\|\|2\.0\|.*?\|\|',text,re.S)
        if len(chains)!=1:raise ReaderError('Cadena original Nu ausente o ambigua')
        parts=re.sub(r'\s+','',chains[0]).strip('|').split('|')
        if len(parts)!=31 or parts[0]!='2.0' or parts[24]!='1.0':raise ReaderError('Formato de cadena original Nu no soportado')
        if parts[6]!=issuer or parts[10]!=recipient:raise ReaderError('Identidades de cadena Nu difieren de portada')
        if parts[13:16]!=[f'{first:02}',f'{last:02}',str(year)]:raise ReaderError('Período de cadena Nu difiere de portada')
        indexes=(16,17,18,19,20,22,28,29,30)
        if any(not re.fullmatch(r'\d+\.\d{2}',parts[i]) for i in indexes):raise ReaderError('Importe de cadena Nu no reconocido')
        chain=NuTaxValues(**{key:Decimal(parts[i]) for (key,_),i in zip(_FIELDS,indexes)})
        def label(pattern):
            matches=re.findall(pattern,pages[0],re.M)
            if len(matches)!=1:raise ReaderError('Etiqueta fiscal Nu ausente o ambigua')
            return matches[0].strip()
        payment=label(r'^\s*Tipo de pago retenido[ \t]+([^\n]+)$')
        flags=[label(r'^\s*'+re.escape(key)+r'[ \t]+(SI|NO)\s*$') for key in ('Interés sistema financiero','Interes retirados en el periodo','Operaciones financieras derivadas')]
        issues=[];differences=[]
        def check(key,a,b):
            if a!=b:issues.append(key);differences.append(NuTaxDifference(key,a,b))
        for key,_ in _FIELDS:check('Portada frente a cadena: '+key,getattr(vals,key),getattr(chain,key))
        for source,v in [('portada',vals),('cadena',chain)]:
            check('Gravado más exento: '+source,v.operation,_sum((v.taxable,v.exempt)))
            check('Retenciones repetidas: '+source,v.total_retention,v.period_retention)
        if parts[21]!='001':issues.append('Código de impuesto en cadena no reconocido como ISR')
        if '01 - ISR' not in pages[0]:issues.append('Etiqueta de impuesto de portada no reconocida como ISR')
        if flags!=parts[25:28]:issues.append('Indicadores de intereses difieren entre portada y cadena')
        if any(getattr(vals,key)<0 for key,_ in _FIELDS):issues.append('Importe fiscal negativo no soportado')
        # No identity or monetary ambiguity is resolved by preferring the chain.
        fingerprint=lambda v:sha256(('nu-tax:'+v).encode()).hexdigest()
        return NuTaxPreview(identifier,start,end,fingerprint(issuer),fingerprint(recipient),
            recipient in ('XAXX010101000','XEXX010101000'),uuid[0].lower(),vals,chain,payment,
            *flags,tuple(differences),tuple(dict.fromkeys(issues)),
            payment_code_reported=parts[23],tax_label_reported=label(r'^\s*Impuesto retenido[ \t]+([^\n]+)$'),
            tax_code_reported=parts[21],chain_page=next((i for i,p in enumerate(pages,1) if chains[0] in p),None))


@dataclass(frozen=True)
class NuTaxComparison:
    certificate_id: str
    statement_ids: tuple[str, ...]
    missing_months: tuple[str, ...]
    monthly_gross: Decimal
    monthly_retention: Decimal
    differences: tuple[NuTaxDifference, ...]
    issues: tuple[str, ...]
    identity_link_confirmed: bool = False
    ready_to_import: bool = False

    @property
    def monthly_totals_match(self):return not self.missing_months and not self.differences


def compare_nu_tax(certificate,previews):
    """Contextual comparison of supplied sources, not automatic account linking.

    Certificates lack the account number; generic RFC cannot establish owner.
    Totals matching does not imply signature verification or final tax payable.
    """
    unique={}
    for p in previews:
        if p.period_end<certificate.period_start or p.period_start>certificate.period_end:continue
        if p.document_id in unique:continue
        unique[p.document_id]=p
    docs=tuple(sorted(unique.values(),key=lambda p:p.period_start))
    if len({p.account_fingerprint for p in docs})>1:raise ReaderError('Comparación anual Nu mezcla cuentas')
    months={};issues=[]
    for p in docs:
        expected_end=date(p.period_start.year,p.period_start.month,monthrange(p.period_start.year,p.period_start.month)[1])
        if p.period_start.day!=1 or p.period_end!=expected_end:raise ReaderError('Estado Nu parcial en comparación anual')
        key=p.period_start.strftime('%Y-%m')
        if key in months:raise ReaderError('Mes Nu repetido con documentos distintos')
        months[key]=p
        if not p.summary_reconciled:issues.append('Resumen mensual Nu sin conciliar')
    expected=[f'{certificate.period_start.year}-{m:02}' for m in range(certificate.period_start.month,certificate.period_end.month+1)]
    missing=tuple(k for k in expected if k not in months)
    gross=_sum(p.summary.gross_income for p in docs);ret=_sum(p.summary.retention for p in docs)
    differences=[]
    # Partial totals are not compared as though an annual history were complete.
    if missing:issues.append('Faltan meses dentro del período de la constancia')
    else:
        for field,total in [('nominal_interest',gross),('total_retention',ret)]:
            visible=getattr(certificate.values,field)
            if visible!=total:differences.append(NuTaxDifference('Constancia frente a meses: '+field,visible,total))
    if certificate.issues:issues.append('Constancia Nu con diferencias internas pendientes')
    if certificate.generic_recipient:issues.append('RFC genérico: vinculación personal requiere revisión')
    issues.append('Constancia sin número de cuenta: cotejo contextual, vínculo no confirmado')
    return NuTaxComparison(certificate.document_id,tuple(p.document_id for p in docs),missing,gross,ret,
        tuple(differences),tuple(dict.fromkeys(issues)))


def main(argv=None):
    parser=argparse.ArgumentParser(description='Revisión documental local de constancias Nu, sin cálculo del SAT')
    parser.add_argument('file');parser.add_argument('--details',action='store_true');args=parser.parse_args(argv)
    try:
        from pathlib import Path
        result=NuTaxReader().read_pdf(Path(args.file).read_bytes())
    except (ValueError,OSError) as error:
        print(json.dumps({'status':'error','error':str(error)},ensure_ascii=False));return 2
    out=asdict(result) if args.details else {'period_start':result.period_start,'period_end':result.period_end,
        'internally_consistent':result.internally_consistent,'differences':len(result.differences),
        'issues':result.issues,'signature_verified':False,'ready_to_import':False}
    print(json.dumps(out,ensure_ascii=False,default=str));return 0


if __name__=='__main__':raise SystemExit(main())
