"""Fondeadora: efectivo operativo; el traspaso no acredita saldo de Bóveda."""
from .book import _hash
from .fondeadora import FondeadoraReader
from .intake import plain
from .ledger import Evidence, Kind, Movement, Origin, _sum
from .storage import movement_id


def prepare(book,doc,content,*,currency_confirmation=None):
    identifier=doc['id']
    plan=dict(document_id=identifier,institution='fondeadora',revision=doc['revision'],status='blocked',can_confirm=False,
        issues=[],warnings=[],periods=[],movements=[],transfers=[],investment_balance=None,
        investment_transfer_evidence=[],currency_confirmation_required=False,currency_confirmation=None)
    view=doc['result']['views'].get('debit',{})
    if view.get('status')!='extracted' or view.get('mode')!='specialized':
        plan['issues'].append('Fondeadora requiere lectura específica de la cuenta operativa.');return plan,()
    try: preview=FondeadoraReader('debit').read_pdf(content)
    except ValueError as error:
        plan['issues'].append(str(error));return plan,()
    summary=preview.summary
    if preview.format!='account_statement' or summary.initial is None or summary.final is None:
        plan['issues'].append('El reporte no acredita apertura/cierre ni rendimiento/ISR: se conserva como evidencia, sin convertir campos ausentes en cero.');return plan,()
    if not preview.reconciled:
        plan['issues'].extend(dict.fromkeys(preview.issues+preview.detail_issues));return plan,()
    if any(getattr(summary,key) is None or getattr(summary,key)!=0 for key in ('interest','withholding','commissions','purchases')):
        plan['issues'].append('Interés, ISR, comisiones o compras requieren mapeo de filas específico; este formato operativo admite esos conceptos solo con cero publicado.');return plan,()
    if preview.currency_markers and set(preview.currency_markers)!={'MXN'}:
        plan['issues'].append('Moneda distinta o contradictoria: la revisión manual no puede sobrescribir la moneda publicada.');return plan,()
    if currency_confirmation not in (None,'MXN'):
        plan['issues'].append('La confirmación operativa solo admite MXN acreditado o revisado expresamente.');return plan,()
    if summary.unit=='MXN':plan['currency_source']='document'
    elif currency_confirmation=='MXN':
        plan['currency_source']='user_review';plan['currency_confirmation']='MXN'
        plan['warnings'].append('Moneda MXN indicada por revisión expresa del usuario, no por el símbolo dólar. Queda registrada en el plan confirmado.')
    else:
        plan['currency_confirmation_required']=True
        plan['issues'].append('El estado no publica la moneda: revisa si corresponde a MXN antes de preparar una importación confirmable.');return plan,()
    account='fondeadora:'+preview.account_fingerprint
    period=dict(document_id=identifier,lane='debit',account=account,unit='MXN',start=str(preview.period_start),
        end=str(preview.period_end),initial=str(summary.initial),final=str(summary.final))
    plan['periods'].append(period);book._check_period(plan,period,label='cuenta operativa Fondeadora')
    movements=[];previous=preview.period_start
    for row in preview.entries:
        locator=f'pagina {row.page}, linea {row.line}'
        if row.effective_date<previous:plan['issues'].append('Secuencia de fechas Fondeadora invertida; no se reordena el dinero para cuadrar.')
        previous=row.effective_date
        if row.debit is None or row.credit is None or (row.debit>0)==(row.credit>0):
            plan['issues'].append('Cargo/abono sin sentido único: '+locator);continue
        if row.category not in ('deposit_unmatched','transfer_unmatched','internal_transfer','term_transfer'):
            plan['issues'].append('Concepto Fondeadora sin normalización: '+locator);continue
        outgoing=row.debit>0
        movement=Movement(movement_id('fondeadora',account,'document:'+identifier+':'+locator),account,'MXN',row.effective_date,
            Kind.WITHDRAWAL if outgoing else Kind.CONTRIBUTION,row.debit if outgoing else row.credit,
            Evidence(identifier,locator),Origin.UNKNOWN)
        movements.append(movement)
        record=plain(movement)|dict(lane='debit',category=row.category,description=row.description)
        plan['movements'].append(record)
        if row.category in ('internal_transfer','term_transfer'):
            plan['investment_transfer_evidence'].append(dict(effective_date=str(row.effective_date),description=row.description,
                amount=str(movement.amount),direction='withdrawal' if outgoing else 'deposit',locator=locator,status='destination_unverified'))
    retained=Movement(movement_id('fondeadora',account,'document:'+identifier+':isr-summary'),account,'MXN',preview.period_end,
        Kind.WITHHOLDING,summary.withholding,Evidence(identifier,'resumen operativo: impuestos retenidos'))
    movements.append(retained);plan['movements'].append(plain(retained)|dict(lane='debit',description='ISR cero publicado en resumen operativo'))
    for label,reported,calculated in (
        ('Cierre',summary.final,_sum((summary.initial,*(m.signed_amount for m in movements)))),
        ('Depósitos',summary.deposits,_sum(m.amount for m in movements if m.kind==Kind.CONTRIBUTION)),
        ('Retiros',summary.withdrawals_or_spending,_sum(m.amount for m in movements if m.kind==Kind.WITHDRAWAL))):
        if reported!=calculated:plan['issues'].append(label+' Fondeadora no coincide tras normalizar; no se ajusta el saldo.')
    plan['reported_terms']={key:plain(getattr(summary,key)) for key in ('annual_rate_reported','gat_nominal','gat_real')}
    plan['issuer_printed']=preview.issuer_printed
    plan['warnings'].extend([
        'Se confirma solo la cuenta operativa. El saldo de Bóveda/Apartados permanece desconocido, incluso si la cuenta operativa cierra en cero.',
        'Un traspaso o Apartado acredita una entrada/salida operativa, no la identidad, propiedad o saldo de la cuenta de destino.',
        'Los orígenes y contrapartidas quedan pendientes: no se inventa capital externo, reinversión ni una transferencia entre las dos pestañas.',
        'Apertura/cierre son anclas documentales; tasas vacías permanecen desconocidas y los reportes sin saldo no equivalen a estados completos.'])
    plan['issues']=list(dict.fromkeys(plan['issues']))
    if not plan['issues']:plan.update(status='ready',can_confirm=True)
    plan['state_hash']=book._state_hash();plan['plan_hash']=_hash(plan)
    return plan,tuple(movements)
