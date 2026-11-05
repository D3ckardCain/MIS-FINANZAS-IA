"""Openbank PDF/XML annual evidence. No financial writes or SAT requests."""
from dataclasses import dataclass
from datetime import date
from calendar import monthrange
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from email.parser import BytesParser
from email.policy import default
import re
import xml.etree.ElementTree as ET

from .openbank import FormatError,_fold
from .nu import value
from .ledger import _sum

RET='http://www.sat.gob.mx/esquemas/retencionpago/2'
INT='http://www.sat.gob.mx/esquemas/retencionpago/1/intereses'
TFD='http://www.sat.gob.mx/TimbreFiscalDigital'
ADD='http://www.Openbank.com.mx/schemas/xsd/Openbank'
MONTHS='enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
UUID=r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}'
FIELDS=('operation','taxable','exempt','retention','nominal_interest','real_interest','inflation_loss','period_retention')


def fp(kind,text):return sha256(('openbank-'+kind+':'+text).encode()).hexdigest()


def one(items,what):
    if len(items)!=1:raise FormatError('Campo Openbank ausente o ambiguo: '+what)
    return items[0]


def amount(raw):
    if not re.fullmatch(r'\d+(?:\.\d{1,2})?',raw):raise FormatError('Importe fiscal XML no reconocido')
    return Decimal(raw)


@dataclass(frozen=True)
class OpenbankTaxValues:
    operation: Decimal
    taxable: Decimal
    exempt: Decimal
    retention: Decimal
    nominal_interest: Decimal
    real_interest: Decimal
    inflation_loss: Decimal
    period_retention: Decimal


@dataclass(frozen=True)
class OpenbankTaxAddendum:
    movement_id: str
    account_fingerprint: str
    effective_date: date
    amount: Decimal
    description: str


@dataclass(frozen=True)
class OpenbankTaxPreview:
    document_id: str
    source: str
    lane: str | None
    period_start: date
    period_end: date
    issuer_fingerprint: str
    recipient_fingerprint: str
    product_reference_fingerprint: str
    uuid: str
    values: OpenbankTaxValues
    addendum: tuple[OpenbankTaxAddendum,...]
    issues: tuple[str,...]
    payment_type_reported: str | None = None
    signature_verified: bool = False
    ready_to_import: bool = False


def checks(v):
    issues=[]
    if v.operation!=_sum((v.taxable,v.exempt)):issues.append('Gravado más exento difiere de operación')
    if v.retention!=v.period_retention:issues.append('Retenciones repetidas difieren')
    return issues


class OpenbankTaxReader:
    def read_image(self,content,*,engine=None):
        from .imaging import read_statement_image
        return read_statement_image(content,'openbank','investments',engine=engine)

    def read_pdf(self,content):
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            r=PdfReader(BytesIO(content))
            if r.is_encrypted:raise FormatError('Constancia Openbank cifrada')
            pages=tuple(p.extract_text(extraction_mode='layout') or '' for p in r.pages)
        except PyPdfError as error:raise FormatError('Constancia Openbank no legible') from error
        return self.read_pages(pages,sha256(content).hexdigest())

    def read_pages(self,pages,identifier):
        pages=tuple(pages);text='\n'.join(pages)
        if not pages or 'openbank' not in _fold(text) or 'constancia fiscal' not in _fold(text):raise FormatError('Constancia Openbank no reconocida')
        titles={_fold(l.strip()) for l in text.splitlines()}&{'cuenta debito open light','apartado open'}
        title=one(list(titles),'producto');lane='debit' if title=='cuenta debito open light' else 'investments'
        period=one(re.findall(r'periodo que ampara la constancia:\s*([a-z]+)\s+a\s+([a-z]+)\s+de\s+(\d{4})',_fold(text)),'período')
        if period[0] not in MONTHS or period[1] not in MONTHS:raise FormatError('Mes fiscal Openbank desconocido')
        first,last=MONTHS.index(period[0])+1,MONTHS.index(period[1])+1;year=int(period[2])
        if first>last:raise FormatError('Período fiscal invertido')
        start=date(year,first,1);end=date(year,last,monthrange(year,last)[1])
        reference=one(re.findall(r'Número de cliente\s+(\d+)',pages[0]),'referencia de producto')
        folio=one(re.findall(r'Folio interno\s+(\d+)',text),'folio interno')
        if reference!=folio:raise FormatError('Referencia de producto y folio interno difieren')
        issuer=one(list(set(re.findall(r'RFC:\s*([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})',text))),'emisor')
        recipient=one(re.findall(r'\bRFC\s+([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})',pages[0]),'receptor')
        uuid=one(re.findall(r'\|1\.1\|('+UUID+r')\|',text),'UUID')
        labels=('MONTO TOTAL DE LA OPERACIÓN','MONTO TOTAL GRAVADO','MONTO TOTAL EXENTO','MONTO TOTAL DE LAS RETENCIONES','INTERÉS NOMINAL','INTERÉS REAL','PÉRDIDA INFLACIONARIA','ISR RETENIDO (PAGO PROVISIONAL)')
        vals=OpenbankTaxValues(**{key:value(pages[0],label) for key,label in zip(FIELDS,labels)})
        issues=checks(vals)
        return OpenbankTaxPreview(identifier,'pdf',lane,start,end,fp('rfc',issuer),fp('rfc',recipient),fp('product',reference),uuid.lower(),vals,(),tuple(issues),payment_type_reported='ISR RETENIDO (PAGO PROVISIONAL)')

    def read_xml(self,content):
        if not isinstance(content,bytes) or len(content)>8*1024*1024:raise FormatError('XML debe ser bytes de hasta 8 MiB')
        original=content;content=content.lstrip(b'\xef\xbb\xbf \r\n\t')
        # The supplied .txt can be a multipart export, not a bare XML file.
        if content.startswith(b'--'):
            boundary=content.splitlines()[0][2:]
            if not re.fullmatch(rb"[A-Za-z0-9'()+_,./:=?-]{1,70}",boundary):raise FormatError('Separador multipart no reconocido')
            header=b'MIME-Version: 1.0\r\nContent-Type: multipart/form-data; boundary="'+boundary+b'"\r\n\r\n'
            msg=BytesParser(policy=default).parsebytes(header+content)
            parts=list(msg.iter_parts()) if msg.is_multipart() else []
            part=one(parts,'adjunto XML multipart')
            if part.get_content_type() not in ('application/xml','text/xml'):raise FormatError('Adjunto multipart no es XML')
            content=part.get_payload(decode=True)
            if content is None:raise FormatError('XML multipart no decodificable')
        if re.search(br'<!\s*(?:DOCTYPE|ENTITY)\b',content,re.I):raise FormatError('XML con DTD/entidades no permitido')
        if b'\x00' in content:raise FormatError('Codificación XML no soportada')
        try:root=ET.fromstring(content)
        except ET.ParseError as error:raise FormatError('XML de retenciones no legible') from error
        if root.tag!='{'+RET+'}Retenciones' or root.get('Version')!='2.0' or root.get('CveRetenc')!='16':raise FormatError('Tipo/versión XML no soportado')
        def node(path):return one(root.findall(path),'nodo XML '+path)
        def attr(n,key):
            v=n.get(key)
            if v is None:raise FormatError('Atributo XML ausente: '+key)
            return v
        emitter=node('{'+RET+'}Emisor');recipient=node('{'+RET+'}Receptor/{'+RET+'}Nacional')
        period=node('{'+RET+'}Periodo');total=node('{'+RET+'}Totales')
        retained=node('{'+RET+'}Totales/{'+RET+'}ImpRetenidos')
        interest=node('{'+RET+'}Complemento/{'+INT+'}Intereses');stamp=node('{'+RET+'}Complemento/{'+TFD+'}TimbreFiscalDigital')
        if interest.get('Version')!='1.0' or stamp.get('Version')!='1.1':raise FormatError('Complemento XML no soportado')
        if retained.get('ImpuestoRet')!='001':raise FormatError('Retención XML distinta de ISR')
        try:
            first,last,year=[int(attr(period,key)) for key in ('MesIni','MesFin','Ejercicio')]
            if not 1<=first<=last<=12:raise ValueError()
            start=date(year,first,1);end=date(year,last,monthrange(year,last)[1])
        except ValueError as error:raise FormatError('Período XML inválido') from error
        reference=attr(root,'FolioInt');uuid=attr(stamp,'UUID').lower()
        if not re.fullmatch(UUID,uuid):raise FormatError('UUID XML no reconocido')
        values=OpenbankTaxValues(*(amount(attr(total,k)) for k in ('MontoTotOperacion','MontoTotGrav','MontoTotExent','MontoTotRet')),
            *(amount(attr(interest,k)) for k in ('MontIntNominal','MontIntReal','Perdida')),amount(attr(retained,'MontoRet')))
        issues=checks(values);rows=[];ids=set()
        for n in root.findall('{'+RET+'}Addenda/{'+ADD+'}AddendaRetencion/{'+ADD+'}retenciones/{'+ADD+'}addendaRetencionesOpenBank'):
            if n.get('version')!='1.0':raise FormatError('Versión de addenda Openbank no soportada')
            identifier=attr(n,'idMovto');account=attr(n,'numeroCuenta')
            if not identifier or identifier in ids:raise FormatError('ID de movimiento addenda vacío/repetido')
            ids.add(identifier)
            try:when=date.fromisoformat(attr(n,'fecha'))
            except ValueError as error:raise FormatError('Fecha addenda no reconocida') from error
            if not start<=when<=end:issues.append('Addenda contiene fecha fuera del período')
            if account!=reference:issues.append('Cuenta de addenda difiere del folio interno')
            rows.append(OpenbankTaxAddendum(identifier,sha256(('openbank:debit:'+account).encode()).hexdigest(),when,
                amount(attr(n,'monto')),attr(n,'descripcion')))
        if rows and _sum(r.amount for r in rows)!=values.nominal_interest:issues.append('Addenda no suma el interés nominal')
        return OpenbankTaxPreview(sha256(original).hexdigest(),'xml',None,start,end,fp('rfc',attr(emitter,'RfcE')),
            fp('rfc',attr(recipient,'RfcR')),fp('product',reference),uuid,values,tuple(rows),tuple(dict.fromkeys(issues)),payment_type_reported=attr(retained,'TipoPagoRet'))


@dataclass(frozen=True)
class OpenbankTaxFormatReview:
    same_certificate: bool
    issues: tuple[str,...]
    differences: tuple[str,...]
    signature_verified: bool = False


def compare_tax_formats(pdf,xml):
    if pdf.source!='pdf' or xml.source!='xml':raise FormatError('Se requieren PDF y XML')
    keys=('uuid','period_start','period_end','issuer_fingerprint','recipient_fingerprint','product_reference_fingerprint')
    issues=tuple('Identidad/período de comprobante difiere: '+k for k in keys if getattr(pdf,k)!=getattr(xml,k))
    diffs=tuple(k for k in FIELDS if getattr(pdf.values,k)!=getattr(xml.values,k))
    return OpenbankTaxFormatReview(not issues,issues+pdf.issues+xml.issues,diffs)


@dataclass(frozen=True)
class OpenbankTaxMonthlyReview:
    observed_gross: Decimal
    observed_retention: Decimal
    observed_totals_match: bool
    missing_months: tuple[str,...]
    addendum_matches: tuple[str,...]
    unmatched_addendum: tuple[str,...]
    issues: tuple[str,...]
    identity_link_confirmed: bool = False
    ready_to_import: bool = False


def compare_tax_months(certificate,previews,*,xml=None):
    if certificate.source!='pdf' or certificate.lane is None:raise FormatError('Usar PDF con producto explícito para el cotejo mensual')
    docs={};accounts=set();subjects=set();issues=[]
    for p in previews:
        if p.lane!=certificate.lane:continue
        if p.period_end<certificate.period_start or p.period_start>certificate.period_end:continue
        accounts.add(p.account_fingerprint);subjects.add(p.recipient_fingerprint)
        if p.document_id in docs:
            if p!=docs[p.document_id]:raise FormatError('Huella mensual repetida con metadatos incompatibles')
            continue
        docs[p.document_id]=p
    if len(accounts)>1 or len(subjects)>1:raise FormatError('Cotejo Openbank mezcla cuentas o titulares')
    if subjects-{None} and subjects-{None}!={certificate.recipient_fingerprint}:raise FormatError('Receptor de constancia y estados no coincide')
    if None in accounts or None in subjects:issues.append('Identidad mensual no informada')
    bymonth={}
    for p in docs.values():
        if p.period_start.day!=1 or p.period_end!=date(p.period_start.year,p.period_start.month,monthrange(p.period_start.year,p.period_start.month)[1]):raise FormatError('Estado mensual Openbank parcial')
        key=p.period_start.strftime('%Y-%m')
        if key in bymonth:raise FormatError('Versiones diferentes del mismo mes Openbank')
        bymonth[key]=p
        if not p.reconciled:issues.append('Estado mensual Openbank sin conciliar')
    expected=[f'{certificate.period_start.year}-{m:02}' for m in range(certificate.period_start.month,certificate.period_end.month+1)]
    missing=tuple(k for k in expected if k not in bymonth)
    gross=_sum(p.summary.interest for p in docs.values());ret=_sum(p.summary.withholding for p in docs.values())
    match=gross==certificate.values.nominal_interest and ret==certificate.values.retention
    if missing:issues.append('Cobertura anual incompleta aunque coincidan los totales observados')
    if not match:issues.append('Totales mensuales observados difieren de la constancia')
    matches=[];unmatched=[]
    if xml is not None:
        if certificate.lane!="debit":raise FormatError("Cotejo de addenda implementado solo para débito")
        formats=compare_tax_formats(certificate,xml)
        if not formats.same_certificate or formats.issues or formats.differences:raise FormatError('PDF/XML no coinciden o tienen incidencias')
        interest_rows=[(p,r) for p in docs.values() for r in p.rows if r.category=='interest']
        def compatible(e,p,r):return e.account_fingerprint==p.account_fingerprint and e.effective_date==r.effective_date and e.amount==r.deposit and r.withdrawal==0 and e.description=='CREDIT INTEREST'
        for e in xml.addendum:
            candidates=[(p,r) for p,r in interest_rows if compatible(e,p,r)]
            if len(candidates)==1 and sum(compatible(other,*candidates[0]) for other in xml.addendum)==1:matches.append(e.movement_id)
            else:unmatched.append(e.movement_id)
        if unmatched:issues.append('Filas de addenda sin contraparte mensual única')
    issues.extend(certificate.issues)
    issues.append('Referencia de producto PDF no se equipara automáticamente a número de cuenta')
    return OpenbankTaxMonthlyReview(gross,ret,match,missing,tuple(matches),tuple(unmatched),tuple(dict.fromkeys(issues)))


def main(argv=None):
    import argparse,json
    from dataclasses import asdict
    from pathlib import Path
    parser=argparse.ArgumentParser(description='Constancias Openbank PDF/XML locales, sin cálculo de declaración')
    parser.add_argument('file');parser.add_argument('--details',action='store_true');args=parser.parse_args(argv)
    try:
        content=Path(args.file).read_bytes();reader=OpenbankTaxReader()
        result=reader.read_pdf(content) if content.startswith(b'%PDF-') else reader.read_xml(content)
    except (ValueError,OSError) as error:
        print(json.dumps({'status':'error','error':str(error)},ensure_ascii=False));return 2
    out=asdict(result) if args.details else {'source':result.source,'lane':result.lane,
        'period_start':result.period_start,'period_end':result.period_end,'addendum_rows':len(result.addendum),
        'issues':result.issues,'signature_verified':False,'ready_to_import':False}
    print(json.dumps(out,ensure_ascii=False,default=str));return 0


if __name__=='__main__':raise SystemExit(main())
