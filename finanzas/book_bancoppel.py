"""Normalización de cuenta de paso BanCoppel, separada de productos de inversión."""
from .bancoppel import BanCoppelDebitReader
from .book import _hash
from .intake import plain
from .ledger import Evidence, Kind, Movement, Origin, _sum
from .storage import movement_id


def prepare(book, doc, content):
    identifier=doc['id']
    plan=dict(document_id=identifier,institution='bancoppel',revision=doc['revision'],status='blocked',can_confirm=False,
              issues=[],warnings=[],periods=[],movements=[],transfers=[])
    view=doc['result']['views'].get('debit',{})
    if view.get('status')!='extracted' or view.get('mode')!='specialized':
        plan['issues'].append('BanCoppel requiere lectura específica del débito; no se confirma evidencia genérica.');return plan,()
    try: preview=BanCoppelDebitReader().read_pdf(content)
    except ValueError as error:
        plan['issues'].append(str(error));return plan,()
    if not preview.reconciled:
        plan['issues'].extend(dict.fromkeys(preview.issues+preview.detail_issues));return plan,()
    if not preview.account_fingerprint:
        plan['issues'].append('Falta identidad de cuenta BanCoppel publicada.');return plan,()
    if preview.unit!='MXN':
        plan['issues'].append('Falta moneda nacional explícita o hay moneda contradictoria: no se supone MXN.');return plan,()
    account='bancoppel:'+preview.account_fingerprint
    summary=preview.summary
    period=dict(document_id=identifier,lane='debit',account=account,unit='MXN',
        start=str(preview.period_start),end=str(preview.period_end),initial=str(summary.initial),final=str(summary.final),role='transit')
    plan['periods'].append(period);book._check_period(plan,period,label='cuenta de paso')
    movements=[]
    capital={'transfer','transfer_return','cash_deposit','debit_movement'}
    for row in preview.entries:
        locator=f'pagina {row.page}, linea {row.line}'
        origin=None
        if row.direction not in ('deposit','withdrawal'):
            plan['issues'].append('Dirección BanCoppel sin conciliar: '+locator);continue
        if row.category=='interest' and row.direction=='deposit': kind=Kind.INTEREST
        elif row.category in ('commission','commission_vat') and row.direction=='withdrawal':kind=Kind.FEE
        elif row.category in capital:
            kind=Kind.CONTRIBUTION if row.direction=='deposit' else Kind.WITHDRAWAL
            origin=Origin.UNKNOWN
        else:
            plan['issues'].append('Concepto BanCoppel sin normalización: '+locator);continue
        movement=Movement(movement_id('bancoppel',account,'document:'+identifier+':'+locator),account,'MXN',
            row.effective_date,kind,row.amount,Evidence(identifier,locator),origin)
        movements.append(movement)
        plan['movements'].append(plain(movement)|dict(lane='debit',role='transit',
            category=row.category,description=row.description))
    # Cero explícito en el bloque de intereses: evidencia, sin cargo monetario extra.
    retained=Movement(movement_id('bancoppel',account,'document:'+identifier+':isr-summary'),account,'MXN',
        preview.period_end,Kind.WITHHOLDING,summary.withholding,Evidence(identifier,f'pagina {summary.page}: retención del resumen'))
    movements.append(retained)
    plan['movements'].append(plain(retained)|dict(lane='debit',role='transit',description='ISR publicado en resumen'))
    def total(kind,category=None):
        return _sum(m.amount for m,record in zip(movements,plan['movements'])
                    if m.kind==kind and (category is None or record.get('category')==category))
    checks=[('Cierre',summary.final,_sum((summary.initial,*(m.signed_amount for m in movements)))),
            ('Depósitos',summary.deposits,total(Kind.CONTRIBUTION)),
            ('Retiros',summary.withdrawals,total(Kind.WITHDRAWAL)),
            ('Interés',summary.interest_gross,total(Kind.INTEREST)),
            ('Comisiones',summary.commissions,total(Kind.FEE,'commission')),
            ('IVA de comisiones',summary.commission_vat,total(Kind.FEE,'commission_vat')),
            ('ISR',summary.withholding,total(Kind.WITHHOLDING))]
    for name,reported,calculated in checks:
        if reported!=calculated:plan['issues'].append(name+' BanCoppel no coincide después de normalizar; no se ajusta.')
    plan['reported_terms']=dict(annual_rate_reported=plain(summary.annual_rate_reported))
    plan['warnings'].extend([
        'Cuenta de paso: efectivo, SPEI, traspasos y devoluciones son aportaciones/reducciones, no rendimientos.',
        'El origen del capital y las contrapartidas permanecen pendientes; no se acredita capital externo ni vínculo propio solo por fecha o importe.',
        'Comisiones e IVA de comisiones se registran una sola vez desde las filas, como cargos operativos, separados del ISR.',
        'Solo un pago de interés explícito se registra como interés; no se inventa rendimiento ni se usa una tasa para estimarlo.',
        'Las fechas MM/DD se resuelven con el período interno, incluido el cambio de año; el detalle inverso conserva su evidencia.',
        'Solo se confirma débito. La pestaña de inversiones no genera un producto, saldo ni traslado adicional.'])
    plan['issues']=list(dict.fromkeys(plan['issues']))
    if not plan['issues']:plan.update(status='ready',can_confirm=True)
    plan['state_hash']=book._state_hash();plan['plan_hash']=_hash(plan)
    return plan,tuple(movements)
