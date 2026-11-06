"""DiDi: una cuenta remunerada; depósitos incluyen el interés ya cobrado."""
from .book import _hash
from .didi import DidiReader
from .intake import plain
from .ledger import Evidence, Kind, Movement, Origin, _sum
from .storage import movement_id


def prepare(book, doc, content):
    identifier=doc['id']
    plan=dict(document_id=identifier,institution='didi',revision=doc['revision'],status='blocked',can_confirm=False,
              issues=[],warnings=[],periods=[],movements=[],transfers=[])
    for lane in ('debit','investments'):
        view=doc['result']['views'].get(lane,{})
        if view.get('status')!='extracted' or view.get('mode')!='specialized':
            plan['issues'].append('DiDi requiere ambas vistas específicas de la misma cuenta.');return plan,()
    try: preview=DidiReader('investments').read_pdf(content)
    except ValueError as error:
        plan['issues'].append(str(error));return plan,()
    if not preview.reconciled:
        plan['issues'].extend(dict.fromkeys(preview.issues+preview.detail_issues));return plan,()
    if not preview.account_fingerprint:
        plan['issues'].append('Falta identidad de cuenta DiDi publicada.');return plan,()
    summary=preview.summary;account='didi:'+preview.account_fingerprint
    period=dict(document_id=identifier,lane='investments',account=account,unit='MXN',
        start=str(preview.period_start),end=str(preview.period_end),initial=str(summary.initial),final=str(summary.final),
        shared_account=True,view_lanes=['debit','investments'])
    plan['periods'].append(period);book._check_period(plan,period,label='cuenta remunerada DiDi')
    movements=[];zero_interest=[]
    for row in preview.entries:
        locator=f'pagina {row.page}, linea {row.line}'
        origin=None
        if row.category=='interest' and row.direction=='deposit': kind=Kind.INTEREST
        elif row.category=='transfer_unmatched' and row.direction in ('deposit','withdrawal'):
            kind=Kind.CONTRIBUTION if row.direction=='deposit' else Kind.WITHDRAWAL
            origin=Origin.UNKNOWN
        else:
            plan['issues'].append('Tipo DiDi sin normalización: '+locator);continue
        if not row.reference:
            plan['issues'].append('Referencia DiDi ausente: '+locator);continue
        if row.amount==0 and kind==Kind.INTEREST:
            zero_interest.append(dict(reference=row.reference,effective_date=str(row.effective_date),locator=locator));continue
        if row.amount<=0:
            plan['issues'].append('Transferencia DiDi sin importe positivo: '+locator);continue
        # El folio identifica evidencia de la cuenta y período, no todos los años.
        reference='period:'+period['start']+':'+period['end']+':'+row.reference
        movement=Movement(movement_id('didi',account,reference),account,'MXN',row.effective_date,kind,row.amount,
                          Evidence(identifier,locator),origin)
        movements.append(movement)
        plan['movements'].append(plain(movement)|dict(lane='investments',shared_account=True,
            reference=row.reference,description='Rendimientos cobrados' if kind==Kind.INTEREST else
            'Transferencia entrante' if row.direction=='deposit' else 'Transferencia saliente'))
    # El formato con retención no nula queda bloqueado por el lector; cero sí está publicado.
    retained=Movement(movement_id('didi',account,'period:'+period['start']+':'+period['end']+':isr-summary'),
        account,'MXN',preview.period_end,Kind.WITHHOLDING,summary.withholding,
        Evidence(identifier,f'pagina {summary.page}: impuesto retenido del resumen'))
    movements.append(retained)
    plan['movements'].append(plain(retained)|dict(lane='investments',shared_account=True,description='ISR publicado en resumen'))
    incoming=_sum(m.amount for m in movements if m.kind==Kind.CONTRIBUTION)
    interest=_sum(m.amount for m in movements if m.kind==Kind.INTEREST)
    checks=[('Cierre',summary.final,_sum((summary.initial,*(m.signed_amount for m in movements)))),
            ('Depósitos incluyendo rendimientos',summary.deposits,_sum((incoming,interest))),
            ('Retiros',summary.withdrawals,_sum(m.amount for m in movements if m.kind==Kind.WITHDRAWAL)),
            ('Rendimientos',summary.interest,interest),
            ('ISR',summary.withholding,_sum(m.amount for m in movements if m.kind==Kind.WITHHOLDING))]
    for label,reported,calculated in checks:
        if reported!=calculated:plan['issues'].append(label+' DiDi no coincide después de normalizar; no se ajusta.')
    plan['zero_interest_observations']=zero_interest
    plan['reported_terms']=dict(annual_rates_reported=plain(preview.annual_rates_reported),
        rate_disclosure=preview.rate_disclosure,average_balance_reported=plain(summary.average))
    plan['warnings'].extend([
        'Ambas pestañas describen la misma cuenta remunerada DiDi: se confirma una sola cuenta y no se crea un traslado entre vistas.',
        'Depósitos del resumen incluye rendimientos: las aportaciones son las entradas de capital, y el interés se registra una sola vez desde su fila.',
        'Transferencias con origen/contrapartida pendientes no se convierten en capital externo ni se enlazan por coincidencia de importe.',
        'Se conservan folios, fechas de cobro, tasas publicadas y texto de escalones/topes; no se aplica una tasa única ni se inventa su vigencia.',
        'Los saldos iniciales son anclas; períodos superpuestos o diferencias se bloquean, sin ajustes ficticios.'])
    plan['issues']=list(dict.fromkeys(plan['issues']))
    if not plan['issues']:plan.update(status='ready',can_confirm=True)
    plan['state_hash']=book._state_hash();plan['plan_hash']=_hash(plan)
    return plan,tuple(movements)
