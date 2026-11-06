"""Kapital: flujos operativos, timbrado compensado y pagarés observados."""
from .book import _hash
from .intake import plain
from .kapital import KapitalReader
from .ledger import Evidence, Kind, Movement, Origin, _sum
from .storage import movement_id


def prepare(book,doc,content,*,currency_confirmation=None,password=None):
    identifier=doc['id']
    plan=dict(document_id=identifier,institution='kapital',revision=doc['revision'],status='blocked',can_confirm=False,
        issues=[],warnings=[],periods=[],movements=[],transfers=[],term_snapshots=[],
        currency_confirmation_required=False,currency_confirmation=None,password_required=False)
    if password is not None and not isinstance(password,str):
        plan['issues'].append('La contraseña debe ser texto.');return plan,()
    for lane in ('debit','investments'):
        view=doc['result']['views'].get(lane,{})
        if view.get('status')!='extracted' or view.get('mode')!='specialized':
            plan['issues'].append('Kapital requiere ambas lecturas específicas de efectivo y pagarés.');return plan,()
    try:preview=KapitalReader().read_pdf(content,password=password)
    except ValueError as error:
        plan['password_required']='protegido' in str(error)
        plan['issues'].append(str(error));return plan,()
    cash=preview.cash_summary
    plan['format']=preview.format
    plan['issues'].extend(preview.cash_issues+preview.investment_issues)
    plan['term_snapshots']=[plain(c)|dict(as_of=str(preview.period_end),status='documentary_observation',unit=cash.unit)
        for c in preview.contracts]
    plan['investment_summary_observation']=plain(preview.investment_summary)
    plan['warnings'].extend([
        'Se confirma una cuenta operativa. Pagarés y saldos de inversiones se conservan como observaciones fechadas, sin otra cuenta contable ni patrimonio total confirmado.',
        'Principal devuelto aporta a efectivo y apertura de pagaré lo reduce. Los orígenes/contrapartidas quedan pendientes; no se atribuye capital externo, reinversión o transferencia propia por importe.',
        'Interés e ISR se registran por filas cobradas, sin duplicar depósitos/retiros del resumen o proyecciones de contratos vigentes.',
        'Timbrado y descuento conservan ambas filas. El descuento es devolución de comisión, sin aporte de capital, cashback ni rendimiento; los cargos se muestran netos de esa devolución.',
        'Identificadores contractuales antiguos y nuevos no se fusionan. Tasas, GAT, fechas e impuestos futuros se guardan como publicados; campos ausentes siguen desconocidos.',
        'Apertura y cierre de efectivo son anclas documentales. Observaciones repetidas de pagarés no se suman entre meses.'])
    if preview.currency_markers and set(preview.currency_markers)!={'MXN'}:
        plan['issues'].append('Moneda Kapital distinta o contradictoria; no se sobrescribe con revisión.')
    elif currency_confirmation not in (None,'MXN'):
        plan['issues'].append('Kapital solo admite moneda MXN acreditada o revisada explícitamente.')
    elif cash.unit=='MXN':plan['currency_source']='document'
    elif currency_confirmation=='MXN':
        plan['currency_source']='user_review';plan['currency_confirmation']='MXN'
    else:
        plan['currency_confirmation_required']=True
        plan['issues'].append('Moneda Kapital no publicada: requiere revisión expresa MXN; el símbolo dólar no basta.')
    if cash.interest_component!=0 or cash.retention_component!=0:
        plan['issues'].append('Interés/ISR de cheques no nulo requiere filas específicas antes de confirmar.')
    if preview.format=='legacy' and cash.commissions_reported!=0:
        plan['issues'].append('Comisión del formato anterior requiere mapeo específico.')
    if plan['issues']:
        plan['issues']=list(dict.fromkeys(plan['issues']));return plan,()
    for snapshot in plan['term_snapshots']:snapshot['unit']='MXN'
    plan['investment_summary_observation']['unit']='MXN'
    account='kapital:'+preview.account_fingerprint
    period=dict(document_id=identifier,lane='debit',account=account,unit='MXN',start=str(preview.period_start),
        end=str(preview.period_end),initial=str(cash.initial),final=str(cash.final))
    plan['periods'].append(period);book._check_period(plan,period,label='efectivo Kapital')
    movements=[]
    for row in preview.entries:
        locator=f'pagina {row.page}, linea {row.line}'
        origin=None
        if row.category=='interest_paid':kind=Kind.INTEREST;value=row.credit
        elif row.category=='withholding':kind=Kind.WITHHOLDING;value=row.debit
        elif row.category=='stamp_fee':kind=Kind.FEE;value=row.debit
        elif row.category=='stamp_discount':kind=Kind.FEE_REFUND;value=row.credit
        elif row.category=='investment_opening':kind=Kind.WITHDRAWAL;value=row.debit;origin=Origin.UNKNOWN
        elif row.category=='principal_repayment':kind=Kind.CONTRIBUTION;value=row.credit;origin=Origin.UNKNOWN
        elif row.category in ('cash_movement_unmatched','transfer_unmatched'):
            outgoing=row.debit is not None and row.debit>0
            kind=Kind.WITHDRAWAL if outgoing else Kind.CONTRIBUTION
            value=row.debit if outgoing else row.credit;origin=Origin.UNKNOWN
        else:
            plan['issues'].append('Concepto Kapital sin normalización: '+locator);continue
        if value is None or value<=0:
            plan['issues'].append('Importe Kapital sin sentido positivo acreditado: '+locator);continue
        movement=Movement(movement_id('kapital',account,'document:'+identifier+':'+locator),account,'MXN',row.effective_date,
            kind,value,Evidence(identifier,locator),origin)
        movements.append(movement);plan['movements'].append(plain(movement)|dict(lane='debit',category=row.category,
            description=row.description_printed,reference=row.reference,withdrawal_printed=plain(row.withdrawal_printed)))
    if not any(m.kind==Kind.WITHHOLDING for m in movements):
        reported=cash.retention_component if preview.format=='legacy' else cash.investment_retention_component
        if reported==0:
            zero=Movement(movement_id('kapital',account,'document:'+identifier+':isr-summary'),account,'MXN',preview.period_end,
                Kind.WITHHOLDING,reported,Evidence(identifier,'resumen Kapital: ISR cero publicado'))
            movements.append(zero);plan['movements'].append(plain(zero)|dict(lane='debit',description='ISR cero publicado en resumen'))
        else:plan['issues'].append('ISR Kapital no nulo sin fila acreditada.')
    for label,reported,calculated in (
        ('Cierre',cash.final,_sum((cash.initial,*(m.signed_amount for m in movements)))),
        ('Depósitos',cash.credits,_sum(m.amount for m in movements if m.kind in (Kind.CONTRIBUTION,Kind.INTEREST,Kind.FEE_REFUND))),
        ('Retiros',cash.debits,_sum(m.amount for m in movements if m.kind in (Kind.WITHDRAWAL,Kind.WITHHOLDING,Kind.FEE))),
        ('Comisiones netas',cash.commissions_reported,_sum(m.signed_amount.copy_negate() for m in movements if m.kind in (Kind.FEE,Kind.FEE_REFUND))),
        ('Interés cobrado',cash.interest_component if preview.format=='legacy' else cash.investment_interest_component,_sum(m.amount for m in movements if m.kind==Kind.INTEREST)),
        ('ISR pagado',cash.retention_component if preview.format=='legacy' else cash.investment_retention_component,_sum(m.amount for m in movements if m.kind==Kind.WITHHOLDING))):
        if reported!=calculated:plan['issues'].append(label+' Kapital no coincide tras normalizar; no se ajusta.')
    plan['issues']=list(dict.fromkeys(plan['issues']))
    if not plan['issues']:plan.update(status='ready',can_confirm=True)
    plan['state_hash']=book._state_hash();plan['plan_hash']=_hash(plan)
    return plan,tuple(movements)
