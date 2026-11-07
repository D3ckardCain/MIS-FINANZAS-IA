"""YoTePresto: apertura acreditada y pago único documentado por préstamo."""
from datetime import timedelta
from decimal import Decimal,InvalidOperation
from .book import _hash
from .intake import plain
from .ledger import Evidence,Kind,Movement,Origin,_sum
from .storage import movement_id
from .yotepresto import YoTePrestoReader

OPENING_ISSUE='Saldo inicial de efectivo no publicado; candidato aritmético sin confirmar'


def prepare(book,doc,content,*,password=None,currency_confirmation=None,cash_opening_confirmation=None):
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
    plan['warnings'].extend([
        'La apertura global no es apertura de efectivo. El candidato aritmético requiere acreditación expresa o cierre contiguo confirmado compatible.',
        'Se confirma una cuenta de efectivo; cartera, acumulados, tasas y atrasos son observaciones, sin nuevos ingresos, cuentas o pérdidas.',
        'Pago único enlazado a préstamo preexistente: principal cotejado con saldo inicial menos final del préstamo y componentes mensuales cotejados con el pago.',
        'Interés ordinario/moratorio, IVA recibido, IVA retenido e ISR separados. Comisión con IVA una vez; la ganancia del resumen no genera otro cobro.',
        'Fondeo, retiro y préstamo conservan origen pendiente. Sin reinversión o capital externo supuestos; cancelaciones/desgloses múltiples requieren adaptación.'])
    if preview.currency_markers and set(preview.currency_markers)!={'MXN'}:
        plan['issues'].append('Moneda YoTePresto distinta/contradictoria; no se sobrescribe.')
    elif currency_confirmation not in (None,'MXN'):plan['issues'].append('Solo se admite MXN acreditado o revisado.')
    elif s.unit=='MXN':plan['currency_source']='document'
    elif currency_confirmation=='MXN':plan.update(currency_source='user_review',currency_confirmation='MXN')
    else:
        plan['currency_confirmation_required']=True;plan['issues'].append('Moneda no publicada: requiere revisión MXN.')
    account='yotepresto:'+preview.account_fingerprint
    candidate=preview.cash_initial_implied;plan['cash_opening_candidate']=plain(candidate)
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
    supported={'funding','withdrawal','loan_funding','repayment','retention','commission'}
    if any(r.category not in supported for r in preview.rows):plan['issues'].append('Cancelación/concepto sin normalización dentro del alcance.')
    pays=[r for r in preview.rows if r.category=='repayment'];taxes=[r for r in preview.rows if r.category=='retention']
    if len(pays)!=1:plan['issues'].append('Se requiere un pago único para acreditar fecha y desglose mensual.')
    if len(taxes)>1 or (s.retention_total and len(taxes)!=1):plan['issues'].append('Retenciones sin fila única para asignar IVA/ISR.')
    principal=None
    if len(pays)==1:
        matches=[l for l in preview.loans if l.loan_id==pays[0].reference]
        if len(matches)!=1 or matches[0].opened>=preview.period_start:
            plan['issues'].append('Pago sin préstamo preexistente único para acreditar principal.')
        else:
            principal=_sum((matches[0].initial,-matches[0].final))
            if principal<0 or _sum((principal,s.interest_received_with_vat))!=pays[0].amount:
                plan['issues'].append('Principal del préstamo más interés/IVA no coincide con pago; no se reparte por suposición.')
    if plan['issues']:
        plan['issues']=list(dict.fromkeys(plan['issues']));return plan,()
    period=dict(document_id=identifier,lane='debit',account=account,unit='MXN',start=str(preview.period_start),
        end=str(preview.period_end),initial=str(candidate),final=str(s.available))
    plan['periods'].append(period);book._check_period(plan,period,label='efectivo YoTePresto')
    movements=[]
    def add(row,component,kind,amount,origin=None):
        if amount==0 and kind!=Kind.WITHHOLDING:return
        if amount<0:plan['issues'].append('Componente negativo no admitido: '+component);return
        locator=f'pagina {row.page}, linea {row.line}: {component}'
        m=Movement(movement_id('yotepresto',account,'document:'+identifier+':'+locator),account,'MXN',row.effective_date,
            kind,amount,Evidence(identifier,locator),origin)
        movements.append(m);plan['movements'].append(plain(m)|dict(lane='debit',component=component,category=row.category,
            description=row.concept,reference=row.reference))
    for row in preview.rows:
        if row.category=='repayment':
            for key,kind,value,origin in [('principal',Kind.CONTRIBUTION,principal,Origin.UNKNOWN),
                ('ordinary_interest',Kind.INTEREST,s.ordinary_interest,None),('late_interest',Kind.INTEREST,s.late_interest,None),
                ('ordinary_vat',Kind.VAT_RECEIVED,s.interest_vat,None),('late_vat',Kind.VAT_RECEIVED,s.late_interest_vat,None)]:add(row,key,kind,value,origin)
        elif row.category=='retention':
            if row.amount!=-s.retention_total:plan['issues'].append('Fila de retención difiere de desglose mensual.')
            add(row,'retention_isr',Kind.WITHHOLDING,s.retention_isr);add(row,'retention_vat',Kind.VAT_PAID,s.retention_vat)
        elif row.category=='funding':
            if row.amount<=0:plan['issues'].append('Fondeo con signo inesperado.');continue
            add(row,'funding',Kind.CONTRIBUTION,row.amount,Origin.UNKNOWN)
        else:
            if row.amount>=0:plan['issues'].append('Cargo con signo inesperado.');continue
            fee=row.category=='commission'
            add(row,row.category,Kind.FEE if fee else Kind.WITHDRAWAL,row.amount.copy_abs(),None if fee else Origin.UNKNOWN)
    if not taxes and s.retention_total==0:
        zero=Movement(movement_id('yotepresto',account,'document:'+identifier+':isr-summary'),account,'MXN',preview.period_end,
            Kind.WITHHOLDING,s.retention_isr,Evidence(identifier,'resumen: ISR cero publicado'))
        movements.append(zero);plan['movements'].append(plain(zero)|dict(lane='debit',description='ISR cero publicado'))
    for label,reported,calculated in (
        ('Cierre efectivo',s.available,_sum((candidate,*(m.signed_amount for m in movements)))),
        ('Interés',_sum((s.ordinary_interest,s.late_interest)),_sum(m.amount for m in movements if m.kind==Kind.INTEREST)),
        ('IVA recibido',_sum((s.interest_vat,s.late_interest_vat)),_sum(m.amount for m in movements if m.kind==Kind.VAT_RECEIVED)),
        ('ISR',s.retention_isr,_sum(m.amount for m in movements if m.kind==Kind.WITHHOLDING)),
        ('IVA retenido',s.retention_vat,_sum(m.amount for m in movements if m.kind==Kind.VAT_PAID)),
        ('Comisiones con IVA',s.commission_total,_sum(m.amount for m in movements if m.kind==Kind.FEE))):
        if reported!=calculated:plan['issues'].append(label+' no coincide tras normalizar; no se ajusta.')
    plan['issues']=list(dict.fromkeys(plan['issues']))
    if not plan['issues']:plan.update(status='ready',can_confirm=True)
    plan['state_hash']=book._state_hash();plan['plan_hash']=_hash(plan)
    return plan,tuple(movements)
