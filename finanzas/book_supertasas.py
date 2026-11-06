"""SuperTasas: efectivo pagado; posiciones a plazo como evidencia sin duplicación."""
from .book import _hash
from .intake import plain
from .ledger import Evidence, Kind, Movement, Origin, _sum
from .storage import movement_id
from .supertasas import SuperTasasReader


def prepare(book,doc,content,*,currency_confirmation=None,password=None):
    identifier=doc['id']
    plan=dict(document_id=identifier,institution='supertasas',revision=doc['revision'],status='blocked',can_confirm=False,
        issues=[],warnings=[],periods=[],movements=[],transfers=[],term_snapshots=[],
        currency_confirmation_required=False,currency_confirmation=None,password_required=False)
    if password is not None and not isinstance(password,str):
        plan['issues'].append('La contraseña debe ser texto.');return plan,()
    for lane in ('debit','investments'):
        view=doc['result']['views'].get(lane,{})
        if view.get('status')!='extracted' or view.get('mode')!='specialized':
            plan['issues'].append('SuperTasas requiere ambas lecturas específicas de efectivo y posiciones.');return plan,()
    try:preview=SuperTasasReader('debit').read_pdf(content,password=password)
    except ValueError as error:
        plan['password_required']='protegido' in str(error)
        plan['issues'].append(str(error));return plan,()
    summary=preview.summary
    plan['issues'].extend(preview.issues)
    plan['term_snapshots']=[plain(c)|dict(as_of=str(preview.period_end),status='documentary_observation',
        source_document=identifier,unit=summary.unit) for c in preview.contracts]
    plan['reported_terms']={key:plain(getattr(summary,key)) for key in ('annual_rate_reported','average_balance')}
    plan['warnings'].extend([
        'Se confirma una sola cuenta de efectivo a la vista. Las dos pestañas no duplican su saldo ni generan una transferencia ficticia.',
        'Las posiciones a plazo se guardan como observaciones fechadas en el plan, con capital y proyecciones; no son nuevas cuentas, cobros ni retenciones pagadas.',
        'Abrir un plazo reduce efectivo y devolver principal lo aporta a la cuenta; su destino/origen queda pendiente, sin atribuir capital externo o reinversión.',
        'El interés a la vista se registra desde su fila una vez. Abonos incluyen ese interés y el resumen no crea un segundo cobro.',
        'Interés/ISR proyectados no sustituyen pagos efectivos ni determinan el impuesto anual. Cobros de interés a plazo sin desglose bruto/retención quedan bloqueados.',
        'Saldos iniciales/finales son anclas documentales. El cierre de efectivo no es el patrimonio total; las posiciones repetidas no se suman entre meses.'])
    if preview.currency_markers and set(preview.currency_markers)!={'MXN'}:
        plan['issues'].append('Moneda SuperTasas distinta o contradictoria; no puede sobrescribirse mediante revisión.')
    elif currency_confirmation not in (None,'MXN'):
        plan['issues'].append('SuperTasas solo admite moneda MXN acreditada o revisada explícitamente.')
    elif summary.unit=='MXN':plan['currency_source']='document'
    elif currency_confirmation=='MXN':
        plan['currency_source']='user_review';plan['currency_confirmation']='MXN'
    else:
        plan['currency_confirmation_required']=True
        plan['issues'].append('Moneda de la cuenta no publicada: requiere revisión expresa MXN, sin deducirla del símbolo dólar o del rendimiento en pesos.')
    if summary.initial is None:
        plan['issues'].append('Sin apertura publicada no se confirma efectivo; no se calcula una apertura supuesta.')
    if any(getattr(summary,k)!=0 for k in ('retention','fees','fees_vat','term_fees','term_fees_vat')):
        plan['issues'].append('Retención o comisiones no nulas requieren detalle de filas específico antes de confirmar.')
    if plan['issues']:
        plan['issues']=list(dict.fromkeys(plan['issues']));return plan,()
    for snapshot in plan['term_snapshots']:snapshot['unit']='MXN'
    account='supertasas:'+preview.account_fingerprint
    period=dict(document_id=identifier,lane='debit',account=account,unit='MXN',start=str(preview.period_start),
        end=str(preview.period_end),initial=str(summary.initial),final=str(summary.final))
    plan['periods'].append(period);book._check_period(plan,period,label='efectivo SuperTasas')
    movements=[]
    for row in preview.rows:
        locator=f'pagina {row.page}, linea {row.line}'
        if row.category=='term_interest':
            plan['issues'].append('Pago a plazo sin desglose acreditado de bruto e ISR: '+locator);continue
        if row.category=='vista_interest':kind=Kind.INTEREST;origin=None;value=row.deposit
        elif row.category in ('incoming_transfer','principal_return'):
            kind=Kind.CONTRIBUTION;origin=Origin.UNKNOWN;value=row.deposit
            if row.withdrawal!=0:plan['issues'].append('Abono SuperTasas en columna de cargo: '+locator)
        elif row.category in ('outgoing_transfer','term_opening'):
            kind=Kind.WITHDRAWAL;origin=Origin.UNKNOWN;value=row.withdrawal
            if row.deposit!=0:plan['issues'].append('Cargo SuperTasas en columna de abono: '+locator)
        else:
            plan['issues'].append('Concepto SuperTasas sin normalización: '+locator);continue
        if value<=0:
            plan['issues'].append('Importe SuperTasas sin sentido positivo acreditado: '+locator);continue
        movement=Movement(movement_id('supertasas',account,'document:'+identifier+':'+locator),account,'MXN',row.effective_date,
            kind,value,Evidence(identifier,locator),origin)
        movements.append(movement);plan['movements'].append(plain(movement)|dict(lane='debit',description=row.description,
            category=row.category,reference=row.reference))
    zero=Movement(movement_id('supertasas',account,'document:'+identifier+':isr-summary'),account,'MXN',preview.period_end,
        Kind.WITHHOLDING,summary.retention,Evidence(identifier,'resumen a la vista: retención ISR cero'))
    movements.append(zero);plan['movements'].append(plain(zero)|dict(lane='debit',description='ISR cero publicado, cuenta a la vista'))
    for label,reported,calculated in (
        ('Cierre',summary.final,_sum((summary.initial,*(m.signed_amount for m in movements)))),
        ('Abonos',summary.deposits,_sum(m.amount for m in movements if m.kind in (Kind.CONTRIBUTION,Kind.INTEREST))),
        ('Cargos',summary.withdrawals,_sum(m.amount for m in movements if m.kind==Kind.WITHDRAWAL)),
        ('Interés bruto a la vista',summary.gross_interest,_sum(m.amount for m in movements if m.kind==Kind.INTEREST))):
        if reported!=calculated:plan['issues'].append(label+' SuperTasas no coincide tras normalizar; no se ajusta.')
    plan['issues']=list(dict.fromkeys(plan['issues']))
    if not plan['issues']:plan.update(status='ready',can_confirm=True)
    plan['state_hash']=book._state_hash();plan['plan_hash']=_hash(plan)
    return plan,tuple(movements)
