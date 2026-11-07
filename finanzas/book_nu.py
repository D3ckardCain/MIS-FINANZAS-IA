"""Nu: cuenta, Cajitas agregadas y garantía, con distribución acreditada explícita."""
from datetime import timedelta
from decimal import Decimal
import re

from .book import _hash
from .intake import plain
from .ledger import Evidence,Kind,Movement,Origin,_sum
from .nu import NuReader,internal_direction
from .storage import movement_id

# Estas limitaciones se resuelven mediante revisión del agregado, nunca por Cajita.
_REVIEWABLE={
    'Rendimiento neto global Nu sin distribución publicada por Cajita/cuenta/garantía',
    'Saldos iniciales/finales individuales Nu no publicados; cambios por Cajita disponibles sin inventar saldos',
}
_LABELS={'debit':'Cuenta Nu','investments':'Cajitas · agregado','guarantee':'Crédito con garantía'}


def _amount(value):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',value):raise ValueError('Importe revisado Nu inválido; usa texto decimal no negativo.')
    result=Decimal(value)
    if len(result.as_tuple().digits)>36 or result.as_tuple().exponent < -30:raise ValueError('Importe revisado Nu fuera de precisión.')
    return result


def prepare(book,doc,content,*,password=None,currency_confirmation=None,operation_review=None):
    identifier=doc['id']
    plan=dict(document_id=identifier,institution='nu',revision=doc['revision'],status='blocked',can_confirm=False,
        issues=[],warnings=[],periods=[],movements=[],transfers=[],password_required=False,
        currency_confirmation_required=False,currency_confirmation=None,nu_review_required=False,nu_buckets=[],operation_review=None)
    if password is not None and not isinstance(password,str):
        plan['issues'].append('La contraseña debe ser texto.');return plan,()
    if any(doc['result']['views'].get(lane,{}).get('mode')!='specialized' or
           doc['result']['views'].get(lane,{}).get('status')!='extracted' for lane in ('debit','investments')):
        plan['issues'].append('Nu requiere ambas lecturas específicas del estado.');return plan,()
    try:p=NuReader().read_pdf(content,password=password)
    except ValueError as error:
        plan['password_required']='protegido' in str(error);plan['issues'].append(str(error));return plan,()
    s=p.summary
    plan['issues'].extend(p.issues+tuple(i for i in p.detail_issues if i not in _REVIEWABLE))
    plan['nu_summary_observation']=plain(s)
    plan['nu_changes_observation']=plain(p.detail_review.postings)
    plan['nu_freeze_observations']=plain(tuple(e for e in p.investment_events if e.category in ('freeze_evidence','unfreeze_evidence')))
    plan['issuer_reported']=p.issuer_reported
    plan['warnings'].extend([
        'Cuenta y Cajitas se confirman separadas; todas las Cajitas forman un agregado, no saldos individuales inventados. Garantía se conserva aparte cuando está publicada y tiene actividad o saldo.',
        'Aperturas por producto y distribución del interés/ISR no publicadas requieren revisión con fuentes adicionales o apertura enlazada a cierre contiguo confirmado. No basta que los totales cuadren.',
        'Interés e ISR globales se reconocen al cierre del período por resumen; no representan fechas diarias de pago. La distribución por producto es una declaración revisada, no extracción automática del PDF.',
        'Congelar/descongelar es evidencia de liquidez dentro de Cajitas: no crea ingreso, aportación o reinversión. Disponibles/congelados son subconjuntos, no activos adicionales.',
        'SPEI y gastos conservan origen pendiente; no se acredita propiedad externa. Tasas y GAT históricos quedan observados, sin calcular ISR anual ni rentabilidad diaria.'])
    if p.currency_markers and set(p.currency_markers)!={'MXN'}:
        plan['issues'].append('Moneda Nu distinta o contradictoria; no se sobrescribe.')
    elif currency_confirmation not in (None,'MXN'):plan['issues'].append('La revisión de moneda Nu solo admite MXN.')
    elif p.currency_markers:plan['currency_source']='document'
    elif currency_confirmation=='MXN':plan.update(currency_source='user_review',currency_confirmation='MXN')
    else:plan['currency_confirmation_required']=True;plan['issues'].append('Moneda Nu no publicada: requiere revisión MXN.')
    if 'account' not in p.sections_seen:plan['issues'].append('Tabla de movimientos de cuenta Nu ausente.')
    if (s.cajitas_reported or p.investment_events) and 'cajitas' not in p.sections_seen:
        plan['issues'].append('Tabla de movimientos de Cajitas Nu ausente.')
    if s.retention_printed>0 or s.expenses_printed>0 or min(s.initial,s.final,s.deposits,s.gross_income,s.retention,s.cash_reported,s.cajitas_reported)<0:
        plan['issues'].append('Signos del resumen Nu fuera del alcance admitido.')
    if s.guarantee_reported is not None and s.guarantee_reported<0:plan['issues'].append('Garantía Nu negativa fuera del alcance.')
    accounts={key:'nu:'+p.account_fingerprint+':'+key for key in _LABELS}
    finals={'debit':s.cash_reported,'investments':s.cajitas_reported}
    has_guarantee_history=bool(book.db.execute('SELECT 1 FROM book_periods WHERE account=? LIMIT 1',(accounts['guarantee'],)).fetchone())
    if s.guarantee_reported or any(e.section=='guarantee' for e in p.investment_events) or has_guarantee_history:
        if s.guarantee_reported is None:plan['issues'].append('Cierre de garantía Nu ausente; no se convierte en cero.')
        else:finals['guarantee']=s.guarantee_reported
        if 'guarantee' not in p.sections_seen:plan['issues'].append('Tabla de garantía Nu ausente.')
    linked={}
    for pair in p.detail_review.pairs:
        link=_hash([identifier,'nu-own-transfer',pair.account_evidence,pair.investment_evidence])
        linked[pair.account_evidence]=linked[pair.investment_evidence]=link
        plan['transfers'].append(dict(id=link,source_evidence=pair.account_evidence,destination_evidence=pair.investment_evidence,cajita=pair.cajita,amount=str(pair.amount.copy_abs())))
    movements=[]
    def append(bucket,kind,amount,effective,locator,*,origin=None,transfer=None,**metadata):
        if amount==0 and kind!=Kind.WITHHOLDING:return
        account=accounts[bucket]
        m=Movement(movement_id('nu',account,'document:'+identifier+':'+locator),account,'MXN',effective,kind,amount,Evidence(identifier,locator),origin,transfer)
        movements.append(m);plan['movements'].append(plain(m)|dict(lane=bucket,**metadata))
    for e in p.account_events+p.investment_events:
        bucket='debit' if e.section=='account' else 'guarantee' if e.section=='guarantee' else 'investments'
        locator=f'pagina {e.page}, linea {e.line}'
        if e.amount is None or e.amount==0:plan['issues'].append('Importe Nu ausente, ambiguo o cero: '+locator);continue
        if e.category in ('freeze_evidence','unfreeze_evidence'):continue
        internal=internal_direction(e)
        if internal is not None:
            link=linked.get(e.evidence_id)
            if not link:plan['issues'].append('Traspaso Nu sin contraparte única: '+locator);continue
            origin=Origin.OWN_TRANSFER
        elif e.section=='account' and e.category=='transfer_evidence':origin=Origin.UNKNOWN;link=None
        elif e.section=='account' and re.match(r'compra(?: con tarjeta)?\b',e.description_printed,re.I) and e.amount<0:origin=Origin.UNKNOWN;link=None
        else:plan['issues'].append('Concepto Nu sin normalización: '+locator);continue
        if bucket not in finals:plan['issues'].append('Producto Nu sin cierre publicado: '+locator);continue
        append(bucket,Kind.CONTRIBUTION if e.amount>0 else Kind.WITHDRAWAL,e.amount.copy_abs(),e.effective_date,locator,
            origin=origin,transfer=link,description=e.description_printed,cajita=e.cajita,tracking_key=e.tracking_key,date_basis='document_row')
    external=[e for e in p.account_events if internal_direction(e) is None and e.amount is not None]
    if _sum(e.amount for e in external if e.amount>0)!=s.deposits or _sum(e.amount.copy_abs() for e in external if e.amount<0)!=s.expenses_printed.copy_abs():
        plan['issues'].append('Depósitos o gastos Nu del detalle no coinciden por separado con el resumen.')
    prior={}
    for bucket in finals:
        rows=book.db.execute('SELECT final FROM book_periods WHERE account=? AND end=?',
            (accounts[bucket],str(p.period_start-timedelta(days=1)))).fetchall()
        prior[bucket]=Decimal(rows[0][0]) if len(rows)==1 else None
        plan['nu_buckets'].append(dict(key=bucket,label=_LABELS[bucket],final=str(finals[bucket]),
            changes_without_income=str(_sum(m.signed_amount for m in movements if m.account==accounts[bucket])),
            previous_initial=plain(prior[bucket])))
    review=None
    if operation_review is not None:
        try:
            if not isinstance(operation_review,dict) or set(operation_review)!={'nu'}:raise ValueError('Revisión Nu desconocida.')
            review=operation_review['nu']
            if not isinstance(review,dict) or set(review)!={'document_id','revision','buckets'} or review['document_id']!=identifier or type(review['revision']) is not int or review['revision']!=doc['revision']:
                raise ValueError('Revisión Nu de otro documento o versión.')
            if not isinstance(review['buckets'],dict) or set(review['buckets'])!=set(finals):raise ValueError('Productos de revisión Nu incompletos o desconocidos.')
            values={}
            for bucket in finals:
                fields=review['buckets'][bucket]
                if not isinstance(fields,dict) or set(fields)!={'initial','gross_interest','withholding'}:raise ValueError('Desglose Nu incompleto o desconocido.')
                values[bucket]={key:_amount(value) for key,value in fields.items()}
            plan['operation_review']=dict(nu=dict(document_id=identifier,revision=doc['revision'],buckets=plain(values)))
        except ValueError as error:plan['issues'].append(str(error));review=None
    elif s.gross_income==0 and s.retention==0 and all(prior[b] is not None for b in finals):
        values={b:dict(initial=prior[b],gross_interest=Decimal('0'),withholding=Decimal('0')) for b in finals}
        review=True;plan['allocation_source']='zero_global_and_previous_closing'
    if review is None:
        plan['nu_review_required']=True
        plan['issues'].append('Falta acreditar aperturas y distribución Nu de interés/ISR por producto. No se reparte el agregado automáticamente.')
    else:
        plan.setdefault('allocation_source','user_review')
        for field,expected in (('initial',s.initial),('gross_interest',s.gross_income),('withholding',s.retention)):
            if _sum(v[field] for v in values.values())!=expected:plan['issues'].append('Total revisado Nu de '+field+' difiere del resumen publicado.')
        for bucket,v in values.items():
            append(bucket,Kind.INTEREST,v['gross_interest'],p.period_end,'resumen: interés '+bucket,date_basis='period_close_summary',allocation_source=plan['allocation_source'])
            append(bucket,Kind.WITHHOLDING,v['withholding'],p.period_end,'resumen: ISR '+bucket,date_basis='period_close_summary',allocation_source=plan['allocation_source'])
            period=dict(document_id=identifier,lane=bucket,role='cajitas_aggregate' if bucket=='investments' else 'collateral' if bucket=='guarantee' else None,
                account=accounts[bucket],unit='MXN',start=str(p.period_start),end=str(p.period_end),initial=str(v['initial']),final=str(finals[bucket]))
            plan['periods'].append(period);book._check_period(plan,period,label=_LABELS[bucket])
            calculated=_sum((v['initial'],*(m.signed_amount for m in movements if m.account==accounts[bucket])))
            if calculated!=finals[bucket]:plan['issues'].append('Cierre Nu no coincide tras normalizar '+_LABELS[bucket]+'.')
    plan['issues']=list(dict.fromkeys(plan['issues']))
    if not plan['issues']:plan.update(status='ready',can_confirm=True)
    plan['state_hash']=book._state_hash();plan['plan_hash']=_hash(plan)
    return plan,tuple(movements)
