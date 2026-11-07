"""CETESdirecto: efectivo liquidado y cobros sin asignación supuesta de principal."""
from .book import _hash
from .cetesdirecto import CetesDirectoInvestmentReader
from .intake import plain
from .ledger import Evidence,Kind,Movement,Origin,_sum
from .storage import movement_id


def prepare(book,doc,content,*,password=None):
    identifier=doc['id']
    plan=dict(document_id=identifier,institution='cetesdirecto',revision=doc['revision'],status='blocked',can_confirm=False,
        issues=[],warnings=[],periods=[],movements=[],transfers=[],security_initial_positions=[],security_final_positions=[],
        security_receipts=[],password_required=False)
    if password is not None and not isinstance(password,str):
        plan['issues'].append('La contraseña debe ser texto.');return plan,()
    view=doc['result']['views'].get('investments',{})
    if view.get('status')!='extracted' or view.get('mode')!='specialized':
        plan['issues'].append('CETESdirecto requiere lectura específica del portafolio.');return plan,()
    try:preview=CetesDirectoInvestmentReader().read_pdf(content,password=password)
    except ValueError as error:
        plan['password_required']='protegido' in str(error);plan['issues'].append(str(error));return plan,()
    s=preview.summary;plan['issues'].extend(preview.issues+preview.detail_issues)
    plan['security_initial_positions']=plain(preview.initial_positions);plan['security_final_positions']=plain(preview.final_positions)
    plan['security_summary_observation']=plain(s);plan['reported_results_observation']=plain(preview.reported_results)
    plan['interest_reported_observation']=str(s.interest_period)
    plan['interest_status']='unknown' if s.interest_period!=0 or any(r.kind in ('amortization','sale') for r in preview.entries) else 'documented_zero'
    plan['warnings'].extend([
        'Se confirma el efectivo del portafolio, no la suma de cartera y efectivo. Posiciones, precios, resultados y acumulados quedan como observaciones.',
        'Venta/amortización se registra como cobro de valores sin desglose de capital/interés. No se obtiene el capital desde precio o valuación inicial; tampoco se crea un interés adicional desde el resumen.',
        'Interés del período se conserva como cifra informativa separada del interés cobrado clasificado. Si hay cobros sin asignación o interés informado no asignado, interés clasificado/neto quedan desconocidos, no cero.',
        'Compras reducen efectivo; entradas/salidas de efectivo conservan origen pendiente. No se confirma capital externo, reinversión o contrapartida propia por coincidencia de importe.',
        'ISR se registra desde sus cargos una vez; acumulados anuales y resultados BONDDIA/ENERFIN/GUBER no generan retenciones o cobros adicionales.',
        'La fecha efectiva es la liquidación publicada y se conserva también el registro. Registro anterior al mes con liquidación dentro del mes no cambia sus fechas. Liquidación fuera del período bloquea el lote.'])
    if s.withholding_period<0:plan['issues'].append('ISR negativo requiere otro concepto, sin corregir signo.')
    previous=preview.period_start
    for r in preview.entries:
        if not preview.period_start<=r.settled<=preview.period_end:plan['issues'].append('Liquidación CETESdirecto fuera del período de efectivo.')
        if r.settled<previous:plan['issues'].append('Liquidaciones fuera del orden publicado; no se reordenan para cuadrar.')
        previous=r.settled
        outgoing=r.kind in ('cash_out','purchase','withholding')
        if (outgoing and (r.credit!=0 or r.debit<0 or (r.debit==0 and r.kind!='withholding'))) or (not outgoing and (r.debit!=0 or r.credit<=0)):
            plan['issues'].append('Código/columna de cargo-abono CETESdirecto incompatibles.')
    if plan['issues']:
        plan['issues']=list(dict.fromkeys(plan['issues']));return plan,()
    account='cetesdirecto:'+preview.account_fingerprint
    period=dict(document_id=identifier,lane='investments',role='fund_cash',account=account,unit=s.unit,
        start=str(preview.period_start),end=str(preview.period_end),initial=str(s.initial_cash),final=str(s.final_cash))
    plan['periods'].append(period);book._check_period(plan,period,label='efectivo CETESdirecto')
    movements=[]
    for r in preview.entries:
        origin=None
        if r.kind=='withholding':kind=Kind.WITHHOLDING;amount=r.debit
        elif r.kind in ('sale','amortization'):kind=Kind.SECURITY_PROCEEDS;amount=r.credit
        elif r.kind=='cash_in':kind=Kind.CONTRIBUTION;amount=r.credit;origin=Origin.UNKNOWN
        elif r.kind in ('cash_out','purchase'):kind=Kind.WITHDRAWAL;amount=r.debit;origin=Origin.UNKNOWN
        else:plan['issues'].append('Código CETESdirecto sin normalización: '+r.operation);continue
        locator=f'pagina {r.page}, linea {r.line}'
        m=Movement(movement_id('cetesdirecto',account,'document:'+identifier+':'+locator),account,s.unit,r.settled,
            kind,amount,Evidence(identifier,locator),origin)
        movements.append(m);record=plain(m)|dict(lane='investments',role='fund_cash',category=r.kind,folio=r.folio,
            registered=str(r.registered),settled=str(r.settled),issuer=r.issuer,series=r.series,operation=r.operation)
        plan['movements'].append(record)
        if kind==Kind.SECURITY_PROCEEDS:plan['security_receipts'].append(dict(folio=r.folio,operation=r.operation,issuer=r.issuer,
            series=r.series,settled=str(r.settled),amount=str(amount),allocation_status='principal_interest_unallocated',locator=locator))
    if not any(m.kind==Kind.WITHHOLDING for m in movements) and s.withholding_period==0:
        zero=Movement(movement_id('cetesdirecto',account,'document:'+identifier+':isr-summary'),account,s.unit,preview.period_end,
            Kind.WITHHOLDING,s.withholding_period,Evidence(identifier,'resumen: ISR del período cero publicado'))
        movements.append(zero);plan['movements'].append(plain(zero)|dict(lane='investments',role='fund_cash',description='ISR cero publicado'))
    for label,reported,calculated in (
        ('Cierre efectivo',s.final_cash,_sum((s.initial_cash,*(m.signed_amount for m in movements)))),
        ('Entradas de efectivo',s.cash_in,_sum(m.amount for m in movements if m.kind==Kind.CONTRIBUTION)),
        ('Salidas de efectivo',s.cash_out,_sum(r.debit for r in preview.entries if r.kind=='cash_out')),
        ('ISR del período',s.withholding_period,_sum(m.amount for m in movements if m.kind==Kind.WITHHOLDING))):
        if reported!=calculated:plan['issues'].append(label+' no coincide tras normalizar; no se ajusta.')
    plan['issues']=list(dict.fromkeys(plan['issues']))
    if not plan['issues']:plan.update(status='ready',can_confirm=True)
    plan['state_hash']=book._state_hash();plan['plan_hash']=_hash(plan)
    return plan,tuple(movements)
