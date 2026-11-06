"""Hey: pagos de efectivo, observaciones contractuales y renovaciones pendientes."""
from .book import _hash
from .hey import HeyReader
from .intake import plain
from .ledger import Evidence, Kind, Movement, Origin, _sum
from .storage import movement_id


def prepare(book,doc,content,*,currency_confirmation=None,password=None):
    identifier=doc['id']
    plan=dict(document_id=identifier,institution='hey',revision=doc['revision'],status='blocked',can_confirm=False,
        issues=[],warnings=[],periods=[],movements=[],transfers=[],term_snapshots=[],renewal_proposals=[],
        zero_interest_observations=[],currency_confirmation_required=False,currency_confirmation=None,password_required=False)
    if password is not None and not isinstance(password,str):
        plan['issues'].append('La contraseña debe ser texto.');return plan,()
    for lane in ('debit','investments'):
        view=doc['result']['views'].get(lane,{})
        if view.get('status')!='extracted' or view.get('mode')!='specialized':
            plan['issues'].append('Hey requiere ambas lecturas específicas de cuenta y pagarés.');return plan,()
    try:preview=HeyReader().read_pdf(content,password=password)
    except ValueError as error:
        plan['password_required']='protegido' in str(error)
        plan['issues'].append(str(error));return plan,()
    cash=preview.cash_summary;investment=preview.investment_summary
    plan['issues'].extend(preview.cash_issues+preview.investment_issues)
    plan['term_snapshots']=[plain(c)|dict(as_of=str(preview.period_end),status='documentary_observation',unit=cash.unit)
        for c in preview.contracts]
    plan['renewal_proposals']=[plain(r)|dict(status='candidate_requires_review') for r in preview.renewal_proposals]
    plan['investment_summary_observation']=plain(investment)
    plan['portfolio_total_reported']=plain(preview.portfolio_total_reported)
    plan['warnings'].extend([
        'Se confirma la cuenta operativa y sus pagos. Pagarés, devengo y portafolio se guardan como observaciones fechadas, sin otra cuenta contable o saldo patrimonial confirmado.',
        'Principal devuelto aporta a la cuenta y la apertura reduce efectivo. Su origen/destino queda pendiente; no generan interés, capital externo ni contrapartida propia inventados.',
        'Interés bruto e ISR se registran desde las filas cobradas. El interés neto del resumen y las proyecciones no generan otro ingreso o retención.',
        'El devengo ya incluido en el saldo de inversiones no se suma como cobro. Total Vigentes al vencimiento no reemplaza al saldo actual.',
        'Las propuestas de renovación conservan las cuatro evidencias y requieren revisión: no confirman reinversión ni vuelven a registrar el interés.',
        'Se conservan referencias por categoría, fechas, tasas y GAT históricos. Aperturas/cierres son anclas; las observaciones mensuales de contratos no se suman entre meses.'])
    if preview.currency_markers and set(preview.currency_markers)!={'MXN'}:
        plan['issues'].append('Moneda Hey distinta o contradictoria; no puede sobrescribirse mediante revisión.')
    elif currency_confirmation not in (None,'MXN'):
        plan['issues'].append('Hey solo admite moneda MXN acreditada o revisada explícitamente.')
    elif cash.unit=='MXN':plan['currency_source']='document'
    elif currency_confirmation=='MXN':
        plan['currency_source']='user_review';plan['currency_confirmation']='MXN'
    else:
        plan['currency_confirmation_required']=True
        plan['issues'].append('Moneda Hey no publicada: requiere revisión expresa MXN; no se infiere por el símbolo dólar.')
    if cash.commissions!=0:
        plan['issues'].append('Comisión Hey no nula requiere mapeo específico de filas.')
    if plan['issues']:
        plan['issues']=list(dict.fromkeys(plan['issues']));return plan,()
    for snapshot in plan['term_snapshots']:snapshot['unit']='MXN'
    plan['investment_summary_observation']['unit']='MXN'
    account='hey:'+preview.account_fingerprint
    period=dict(document_id=identifier,lane='debit',account=account,unit='MXN',start=str(preview.period_start),
        end=str(preview.period_end),initial=str(cash.initial),final=str(cash.final))
    plan['periods'].append(period);book._check_period(plan,period,label='efectivo Hey')
    movements=[]
    for row in preview.entries:
        locator=f'pagina {row.page}, linea {row.line} ({row.source_extraction})'
        origin=None
        if row.category=='interest_paid':kind=Kind.INTEREST;value=row.credit
        elif row.category=='withholding':kind=Kind.WITHHOLDING;value=row.debit
        elif row.category=='principal_repayment':kind=Kind.CONTRIBUTION;value=row.credit;origin=Origin.UNKNOWN
        elif row.category=='investment_opening':kind=Kind.WITHDRAWAL;value=row.debit;origin=Origin.UNKNOWN
        else:
            plan['issues'].append('Concepto Hey sin normalización: '+locator);continue
        if value==0 and kind==Kind.INTEREST:
            plan['zero_interest_observations'].append(dict(effective_date=str(row.effective_date),contract_id=row.contract_id,locator=locator));continue
        if value<=0 and kind!=Kind.WITHHOLDING:
            plan['issues'].append('Importe Hey sin sentido positivo acreditado: '+locator);continue
        movement=Movement(movement_id('hey',account,'document:'+identifier+':'+locator),account,'MXN',row.effective_date,
            kind,value,Evidence(identifier,locator),origin)
        movements.append(movement);plan['movements'].append(plain(movement)|dict(lane='debit',category=row.category,
            description=row.description,reference=row.reference,contract_id=row.contract_id,source_extraction=row.source_extraction))
    if not any(m.kind==Kind.WITHHOLDING for m in movements):
        if investment.withholding_reported==0:
            zero=Movement(movement_id('hey',account,'document:'+identifier+':isr-summary'),account,'MXN',preview.period_end,
                Kind.WITHHOLDING,investment.withholding_reported,Evidence(identifier,'resumen Hey: ISR cero publicado'))
            movements.append(zero);plan['movements'].append(plain(zero)|dict(lane='debit',description='ISR cero publicado en resumen'))
        else:plan['issues'].append('ISR Hey no nulo sin retención individual acreditada.')
    for label,reported,calculated in (
        ('Cierre',cash.final,_sum((cash.initial,*(m.signed_amount for m in movements)))),
        ('Abonos',cash.credits,_sum(m.amount for m in movements if m.kind in (Kind.CONTRIBUTION,Kind.INTEREST))),
        ('Cargos',_sum((cash.withdrawals,cash.other_debits,cash.commissions)),_sum(m.amount for m in movements if m.kind in (Kind.WITHDRAWAL,Kind.WITHHOLDING))),
        ('ISR pagado',investment.withholding_reported,_sum(m.amount for m in movements if m.kind==Kind.WITHHOLDING)),
        ('Interés neto',investment.interest_reported,_sum(m.signed_amount for m in movements if m.kind in (Kind.INTEREST,Kind.WITHHOLDING)))):
        if reported!=calculated:plan['issues'].append(label+' Hey no coincide tras normalizar; no se ajusta.')
    plan['issues']=list(dict.fromkeys(plan['issues']))
    if not plan['issues']:plan.update(status='ready',can_confirm=True)
    plan['state_hash']=book._state_hash();plan['plan_hash']=_hash(plan)
    return plan,tuple(movements)
