"""YoTePresto: apertura acreditada, pagos múltiples y cancelaciones trazables."""
from datetime import timedelta
from decimal import Decimal,InvalidOperation
from .book import _hash
from .intake import plain
from .ledger import Evidence,Kind,Movement,Origin,_sum
from .storage import movement_id
from .yotepresto import YoTePrestoReader

OPENING_ISSUE='Saldo inicial de efectivo no publicado; candidato aritmético sin confirmar'


def prepare(book,doc,content,*,password=None,currency_confirmation=None,cash_opening_confirmation=None,operation_review=None):
    identifier=doc['id']
    plan=dict(document_id=identifier,institution='yotepresto',revision=doc['revision'],status='blocked',can_confirm=False,
        issues=[],warnings=[],periods=[],movements=[],transfers=[],loan_snapshots=[],arrears_observations=[],
        password_required=False,currency_confirmation_required=False,currency_confirmation=None,
        cash_opening_confirmation_required=False,cash_opening_confirmation=None,cash_opening_candidate=None)
    if password is not None and not isinstance(password,str):
        plan['issues'].append('La contraseña debe ser texto.');return plan,()
    for lane in ('debit','investments'):
        view=doc['result']['views'].get(lane,{})
        if view.get('status')!='extracted' or view.get('mode')!='specialized':
            plan['issues'].append('YoTePresto requiere ambas lecturas específicas.');return plan,()
    try:preview=YoTePrestoReader().read_pdf(content,password=password)
    except ValueError as error:
        plan['password_required']='protegido' in str(error);plan['issues'].append(str(error));return plan,()
    s=preview.summary
    plan['issues'].extend(preview.issues+tuple(i for i in preview.cash_issues if i!=OPENING_ISSUE))
    plan['loan_snapshots']=plain(preview.loans);plan['arrears_observations']=plain(preview.arrears)
    plan['platform_summary_observation']=plain(s)
    gross_payments=_sum(r.amount for r in preview.rows if r.category=='repayment')
    net_payments=_sum((gross_payments,*(r.amount for r in preview.rows if r.category=='payment_cancellation')))
    plan['payment_flow_observation']=dict(reported=str(s.payments_received),gross=str(gross_payments),net=str(net_payments),
        basis='unexplained' if s.payments_received not in (gross_payments,net_payments) else 'indistinguishable' if gross_payments==net_payments else 'gross' if s.payments_received==gross_payments else 'net')
    plan['warnings'].extend([
        'La apertura global no es apertura de efectivo. El candidato aritmético requiere acreditación expresa o cierre contiguo confirmado compatible.',
        'Se confirma una cuenta de efectivo; cartera, acumulados, tasas y atrasos son observaciones, sin nuevos ingresos, cuentas o pérdidas.',
        'Pagos y retenciones múltiples requieren desglose por fila revisado cuando el estado no lo publica. Principal neto cotejado por préstamo; no se reparten totales por proporción.',
        'Interés ordinario/moratorio, IVA recibido, IVA retenido e ISR separados. Comisión con IVA una vez; la ganancia del resumen no genera otro cobro.',
        'Cancelaciones enlazadas a un original compatible elegido: se revierten sus componentes sin reescribirlo ni cancelarlo dos veces. Fondeos/retiros conservan origen pendiente, sin reinversión o capital externo supuestos.'])
    if preview.currency_markers and set(preview.currency_markers)!={'MXN'}:
        plan['issues'].append('Moneda YoTePresto distinta/contradictoria; no se sobrescribe.')
    elif currency_confirmation not in (None,'MXN'):plan['issues'].append('Solo se admite MXN acreditado o revisado.')
    elif s.unit=='MXN':plan['currency_source']='document'
    elif currency_confirmation=='MXN':plan.update(currency_source='user_review',currency_confirmation='MXN')
    else:
        plan['currency_confirmation_required']=True;plan['issues'].append('Moneda no publicada: requiere revisión MXN.')
    account='yotepresto:'+preview.account_fingerprint
    candidate=preview.cash_initial_implied
    if candidate is None and not preview.rows and all(value==0 for value in (s.interest_received_with_vat,s.commission_total,
            s.retention_total,s.funds_added,s.withdrawals,s.investments_made,s.payments_received)):
        candidate=s.available  # Candidato de cierre sin actividad, sujeto a revisión/enlace y tabla vacía explícita.
    plan['cash_opening_candidate']=plain(candidate)
    prior=book.db.execute('SELECT final FROM book_periods WHERE account=? AND end=?',
        (account,str(preview.period_start-timedelta(days=1)))).fetchall()
    if candidate is None or candidate<0:plan['issues'].append('No hay apertura de efectivo verificable dentro del alcance.')
    elif len(prior)==1 and Decimal(prior[0][0])==candidate:
        plan['cash_opening_source']='previous_confirmed_closing'
    elif cash_opening_confirmation is not None:
        try:
            if not isinstance(cash_opening_confirmation,str):raise ValueError()
            value=Decimal(cash_opening_confirmation)
            if not value.is_finite() or value!=candidate:raise ValueError()
            plan.update(cash_opening_source='user_review',cash_opening_confirmation=str(candidate))
        except (InvalidOperation,ValueError):plan['issues'].append('Apertura revisada no coincide con candidato; no se ajusta.')
    else:
        plan['cash_opening_confirmation_required']=True
        plan['issues'].append('Apertura no publicada: acredita el candidato con tus fuentes; no basta que cuadre aritméticamente.')
    from .yotepresto_operations import normalize,check_history
    operations,movements=normalize(book,preview,account,operation_review)
    plan['issues'].extend(operations['issues'])
    plan.update({key:operations[key] for key in ('operation_review','review_rows','operation_events','cancellation_links')})
    plan['movements']=operations['records']
    if plan['issues']:
        plan['issues']=list(dict.fromkeys(plan['issues']));return plan,()
    period=dict(document_id=identifier,lane='debit',account=account,unit='MXN',start=str(preview.period_start),
        end=str(preview.period_end),initial=str(candidate),final=str(s.available))
    plan['periods'].append(period);book._check_period(plan,period,label='efectivo YoTePresto')
    history_issues,checks=check_history(book,preview,account,plan['movements'])
    plan['issues'].extend(history_issues);plan['history_checks']=checks
    movements=list(movements)
    taxes=[r for r in preview.rows if r.category in ('retention','retention_cancellation')]
    if not taxes and s.retention_total==0:
        zero=Movement(movement_id('yotepresto',account,'document:'+identifier+':isr-summary'),account,'MXN',preview.period_end,
            Kind.WITHHOLDING,s.retention_isr,Evidence(identifier,'resumen: ISR cero publicado'))
        movements.append(zero);plan['movements'].append(plain(zero)|dict(lane='debit',description='ISR cero publicado'))
    for label,reported,calculated in (
        ('Cierre efectivo',s.available,_sum((candidate,*(m.signed_amount for m in movements)))),
        ('Interés',_sum((s.ordinary_interest,s.late_interest)),_sum(m.signed_amount for m in movements if m.kind in (Kind.INTEREST,Kind.INTEREST_REVERSAL))),
        ('IVA recibido',_sum((s.interest_vat,s.late_interest_vat)),_sum(m.signed_amount for m in movements if m.kind in (Kind.VAT_RECEIVED,Kind.VAT_RECEIVED_REVERSAL))),
        ('ISR',s.retention_isr,_sum(m.signed_amount.copy_negate() for m in movements if m.kind in (Kind.WITHHOLDING,Kind.WITHHOLDING_REFUND))),
        ('IVA retenido',s.retention_vat,_sum(m.signed_amount.copy_negate() for m in movements if m.kind in (Kind.VAT_PAID,Kind.VAT_REFUND))),
        ('Comisiones con IVA',s.commission_total,_sum(m.signed_amount.copy_negate() for m in movements if m.kind in (Kind.FEE,Kind.FEE_REFUND)))):
        if reported!=calculated:plan['issues'].append(label+' no coincide tras normalizar; no se ajusta.')
    plan['issues']=list(dict.fromkeys(plan['issues']))
    if not plan['issues']:plan.update(status='ready',can_confirm=True)
    plan['state_hash']=book._state_hash();plan['plan_hash']=_hash(plan)
    return plan,tuple(movements)
