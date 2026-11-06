"""Fintual: efectivo confirmado, fondos valuados e ISR informativo separados."""
from .book import _hash
from .fintual import FintualInvestmentReader
from .intake import plain
from .ledger import Evidence, Kind, Movement, Origin, _sum
from .storage import movement_id


def prepare(book,doc,content,*,password=None):
    identifier=doc['id']
    plan=dict(document_id=identifier,institution='fintual',revision=doc['revision'],status='blocked',can_confirm=False,
        issues=[],warnings=[],periods=[],movements=[],transfers=[],fund_initial_positions=[],fund_final_positions=[],
        password_required=False,withholding_status='unknown',withholding_basis='informative_unallocated')
    if password is not None and not isinstance(password,str):
        plan['issues'].append('La contraseña debe ser texto.');return plan,()
    view=doc['result']['views'].get('investments',{})
    if view.get('status')!='extracted' or view.get('mode')!='specialized':
        plan['issues'].append('Fintual requiere la lectura específica del portafolio.');return plan,()
    try:preview=FintualInvestmentReader().read_pdf(content,password=password)
    except ValueError as error:
        plan['password_required']='protegido' in str(error)
        plan['issues'].append(str(error));return plan,()
    summary=preview.summary
    plan['issues'].extend(preview.issues+preview.detail_issues)
    plan['fund_initial_positions']=plain(preview.initial_positions)
    plan['fund_final_positions']=plain(preview.final_positions)
    plan['fund_summary_observation']=plain(summary)
    plan['withholding_reported_observation']=plain(summary.withholding_reported)
    plan['warnings'].extend([
        'Se confirma solo el efectivo del portafolio, no una cuenta bancaria ni una segunda cuenta por cada pestaña. Valores, pendientes y total del portafolio quedan como observaciones documentales.',
        'Compra reduce efectivo y venta lo aporta con origen pendiente; no se atribuye capital externo, ganancia realizada, reinversión o transferencia propia por importe.',
        'Valuación, variación, costo promedio y rendimiento porcentual no son interés cobrado. No se calcula ganancia realizada o costo fiscal desde estas observaciones.',
        'ISR informativo se conserva publicado sin generar otro cargo de efectivo. Retención de efectivo y neto permanecen desconocidos hasta acreditar su asignación, incluso si la cifra informativa es cero.',
        'Comisión e IVA se registran desde sus columnas una vez; resúmenes, porcentajes y posiciones no generan movimientos adicionales.',
        'Apertura/cierre de efectivo son anclas del período. Posiciones repetidas no se suman entre meses; fechas de liquidación sueltas no se interpretan como otra operación.'])
    for position in preview.initial_positions+preview.final_positions:
        if position.units<0 or position.price<0 or position.market_value<0 or (position.average_cost is not None and position.average_cost<0):
            plan['issues'].append('Posición Fintual con unidades/precio/valor/costo negativos: requiere otro formato.')
    if summary.withholding_reported<0:
        plan['issues'].append('ISR informativo Fintual negativo requiere revisión.')
    if plan['issues']:
        plan['issues']=list(dict.fromkeys(plan['issues']));return plan,()
    account='fintual:'+preview.account_fingerprint
    period=dict(document_id=identifier,lane='investments',role='fund_cash',account=account,unit=summary.unit,
        start=str(preview.period_start),end=str(preview.period_end),initial=str(summary.initial_cash),final=str(summary.final_cash))
    plan['periods'].append(period);book._check_period(plan,period,label='efectivo de portafolio Fintual')
    movements=[]
    for row in preview.entries:
        locator=f'pagina {row.page}, linea {row.line}'
        if row.amount<=0 or row.commission<0 or row.vat<0:
            plan['issues'].append('Importe, comisión o IVA Fintual con signo/valor no admitido: '+locator);continue
        if row.category not in ('deposit','withdrawal','purchase','sale'):
            plan['issues'].append('Concepto Fintual sin normalización: '+locator);continue
        kind=Kind.WITHDRAWAL if row.category in ('withdrawal','purchase') else Kind.CONTRIBUTION
        for component,kind_,amount,origin in (
            ('amount',kind,row.amount,Origin.UNKNOWN),('commission',Kind.FEE,row.commission,None),('vat',Kind.FEE,row.vat,None)):
            if amount==0:continue
            evidence=locator+': '+component
            movement=Movement(movement_id('fintual',account,'document:'+identifier+':'+evidence),account,summary.unit,
                row.effective_date,kind_,amount,Evidence(identifier,evidence),origin)
            movements.append(movement);plan['movements'].append(plain(movement)|dict(lane='investments',role='fund_cash',
                category=row.category,component=component))
    for label,reported,calculated in (
        ('Cierre de efectivo',summary.final_cash,_sum((summary.initial_cash,*(m.signed_amount for m in movements)))),
        ('Depósitos',summary.deposits,_sum(row.amount for row in preview.entries if row.category=='deposit')),
        ('Retiros',summary.withdrawals,_sum(row.amount for row in preview.entries if row.category=='withdrawal')),
        ('Comisiones',summary.commissions_reported,_sum(row.commission for row in preview.entries))):
        if reported!=calculated:plan['issues'].append(label+' Fintual no coincide tras normalizar; no se ajusta.')
    plan['issues']=list(dict.fromkeys(plan['issues']))
    if not plan['issues']:plan.update(status='ready',can_confirm=True)
    plan['state_hash']=book._state_hash();plan['plan_hash']=_hash(plan)
    return plan,tuple(movements)
