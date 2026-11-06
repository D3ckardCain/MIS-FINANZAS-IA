"""Doopla: efectivo por componente; cartera y cobranza como evidencia fechada."""
from datetime import date, timedelta
from decimal import Decimal
import json
from .book import _hash
from .doopla import DooplaReader
from .intake import plain
from .ledger import Evidence, Kind, Movement, Origin, _sum
from .storage import movement_id


def prepare(book,doc,content,*,currency_confirmation=None,password=None):
    identifier=doc['id']
    plan=dict(document_id=identifier,institution='doopla',revision=doc['revision'],status='blocked',can_confirm=False,
        issues=[],warnings=[],periods=[],movements=[],transfers=[],loan_snapshots=[],arrears_observations=[],
        currency_confirmation_required=False,currency_confirmation=None,password_required=False)
    if password is not None and not isinstance(password,str):
        plan['issues'].append('La contraseña debe ser texto.');return plan,()
    for lane in ('debit','investments'):
        view=doc['result']['views'].get(lane,{})
        if view.get('status')!='extracted' or view.get('mode')!='specialized':
            plan['issues'].append('Doopla requiere ambas lecturas específicas de efectivo y cartera.');return plan,()
    try:preview=DooplaReader().read_pdf(content,password=password)
    except ValueError as error:
        plan['password_required']='protegido' in str(error)
        plan['issues'].append(str(error));return plan,()
    summary=preview.summary
    plan['issues'].extend(preview.issues+preview.detail_issues)
    plan['loan_snapshots']=[plain(loan)|dict(as_of=str(preview.period_end),status_observation='documentary_observation',unit=summary.unit) for loan in preview.loans]
    plan['arrears_observations']=plain(preview.arrears)
    plan['platform_summary_observation']=plain(summary)
    plan['commission_components_observation']={key:plain(getattr(summary,key)) for key in ('commission','commission_vat')}
    plan['withholding_status']='unknown' if summary.withholding is None else 'documented'
    plan['warnings'].extend([
        'Se confirma una cuenta de efectivo de la plataforma; débito no crea una cuenta bancaria adicional. Cartera y atrasos se conservan como observaciones, no como otro saldo contable.',
        'Cada pago se desglosa en principal, interés e IVA. Principal recuperado/cancelación aportan a efectivo y la inversión lo reduce, sin origen externo, contrapartida propia o reinversión supuestos.',
        'IVA recibido, IVA pagado, ISR y comisiones son conceptos separados. Recompensa es otro ingreso, no cashback, aportación de capital o interés.',
        'El cargo de comisión agrupado incluye su IVA una sola vez; el desglose publicado se conserva como observación sin generar cargos duplicados.',
        'ISR ausente permanece desconocido: no se genera cero, neto definitivo ni impuesto anual supuesto. Totales acumulados de préstamos y atrasos no crean cobros, pérdidas o intereses nuevos.',
        'Se conservan signos y fechas impresos, incluso si las filas no aparecen en orden cronológico. No se redondean discrepancias ni se cambia el signo de IVA para cuadrar.'])
    if preview.currency_markers and set(preview.currency_markers)!={'MXN'}:
        plan['issues'].append('Moneda Doopla distinta o contradictoria; no se sobrescribe con revisión.')
    elif currency_confirmation not in (None,'MXN'):
        plan['issues'].append('Doopla solo admite moneda MXN acreditada o revisada explícitamente.')
    elif summary.unit=='MXN':plan['currency_source']='document'
    elif currency_confirmation=='MXN':
        plan['currency_source']='user_review';plan['currency_confirmation']='MXN'
    else:
        plan['currency_confirmation_required']=True
        plan['issues'].append('Moneda Doopla no publicada: requiere revisión expresa MXN; el símbolo dólar no basta.')
    # Los guiones no se convierten en importes cero en componentes de pagos.
    if any(any(getattr(row,k) is None for k in ('principal','interest','vat')) for row in preview.entries if row.category=='payment'):
        plan['issues'].append('Pago Doopla con componentes desconocidos: se requiere desglose completo de principal/interés/IVA.')
    if plan['issues']:
        plan['issues']=list(dict.fromkeys(plan['issues']));return plan,()
    for snapshot in plan['loan_snapshots']:snapshot['unit']='MXN'
    plan['platform_summary_observation']['unit']='MXN'
    account='doopla:'+preview.account_fingerprint
    period=dict(document_id=identifier,lane='debit',account=account,unit='MXN',start=str(preview.period_start),
        end=str(preview.period_end),initial=str(summary.cash_initial),final=str(summary.cash_final))
    plan['periods'].append(period);book._check_period(plan,period,label='efectivo Doopla')
    # Comprobar el anexo repetido en ambas direcciones para meses fuera de orden.
    fields=('alias','payments','investment','received','interest','interest_vat','repaid_principal','pending_principal')
    snapshot=lambda rows:sorted(tuple(r[k] for k in fields) for r in rows)
    activity=any(r.category in ('investment','cancellation') or (r.category=='payment' and r.principal!=0) for r in preview.entries)
    plan['loan_capital_activity']=activity
    for saved_json, in book.db.execute('SELECT b.plan_json FROM book_batches b JOIN book_periods p USING(document_id) WHERE p.account=?',(account,)):
        saved=json.loads(saved_json);old=saved['periods'][0]
        before=date.fromisoformat(old['end'])+timedelta(days=1)==preview.period_start
        after=preview.period_end+timedelta(days=1)==date.fromisoformat(old['start'])
        if (before or after) and ((activity if before else saved.get('loan_capital_activity',False)) and
                snapshot(plan['loan_snapshots'])==snapshot(saved.get('loan_snapshots',[]))):
            plan['issues'].append('Cartera Doopla repetida entre meses consecutivos con movimientos de capital: revisar vigencia del anexo.')
        if before and Decimal(saved['platform_summary_observation']['final'])!=summary.initial:
            plan['issues'].append('Valor inicial de plataforma no coincide con cierre anterior Doopla.')
        if after and Decimal(saved['platform_summary_observation']['initial'])!=summary.final:
            plan['issues'].append('Valor final de plataforma no coincide con apertura siguiente Doopla.')
    movements=[]
    def append(row,component,kind,value,origin=None):
        if value==0 and kind!=Kind.WITHHOLDING:return
        locator=f'pagina {row.page}, linea {row.line}: {component}'
        movement=Movement(movement_id('doopla',account,'document:'+identifier+':'+locator),account,'MXN',row.effective_date,
            kind,value,Evidence(identifier,locator),origin)
        movements.append(movement);plan['movements'].append(plain(movement)|dict(lane='debit',category=row.category,
            component=component,description=row.label,alias=row.alias))
    for row in preview.entries:
        if row.category=='payment':
            append(row,'principal',Kind.CONTRIBUTION,row.principal,Origin.UNKNOWN)
            append(row,'interest',Kind.INTEREST,row.interest)
            append(row,'vat',Kind.VAT_RECEIVED,row.vat)
        elif row.category in ('deposit','cancellation'):
            append(row,row.category,Kind.CONTRIBUTION,row.total,Origin.UNKNOWN)
        elif row.category in ('withdrawal','investment'):
            append(row,row.category,Kind.WITHDRAWAL,row.total.copy_abs(),Origin.UNKNOWN)
        elif row.category in ('vat','late_vat'):append(row,row.category,Kind.VAT_PAID,row.total.copy_abs())
        elif row.category=='withholding':append(row,'withholding',Kind.WITHHOLDING,row.total.copy_abs())
        elif row.category=='commission':append(row,'commission_including_vat',Kind.FEE,row.total.copy_abs())
        elif row.category=='reward':append(row,'reward',Kind.REWARD,row.total)
        else:plan['issues'].append('Concepto Doopla sin normalización: '+row.label)
    if summary.withholding==0 and not any(m.kind==Kind.WITHHOLDING for m in movements):
        zero=Movement(movement_id('doopla',account,'document:'+identifier+':isr-summary'),account,'MXN',preview.period_end,
            Kind.WITHHOLDING,summary.withholding,Evidence(identifier,'resumen Doopla: ISR cero publicado'))
        movements.append(zero);plan['movements'].append(plain(zero)|dict(lane='debit',description='ISR cero publicado en resumen'))
    for label,reported,calculated in (
        ('Cierre efectivo',summary.cash_final,_sum((summary.cash_initial,*(m.signed_amount for m in movements)))),
        ('Interés cobrado',summary.interest,_sum(m.amount for m in movements if m.kind==Kind.INTEREST)),
        ('IVA recibido',summary.interest_vat,_sum(m.amount for m in movements if m.kind==Kind.VAT_RECEIVED)),
        ('Recompensas',summary.rewards,_sum(m.amount for m in movements if m.kind==Kind.REWARD)),
        ('Comisión con IVA',_sum((summary.commission,summary.commission_vat)),_sum(m.amount for m in movements if m.kind==Kind.FEE))):
        if reported!=calculated:plan['issues'].append(label+' Doopla no coincide tras normalizar; no se ajusta.')
    if summary.withholding is not None and summary.withholding!=_sum(m.amount for m in movements if m.kind==Kind.WITHHOLDING):
        plan['issues'].append('ISR Doopla no coincide tras normalizar.')
    plan['issues']=list(dict.fromkeys(plan['issues']))
    if not plan['issues']:plan.update(status='ready',can_confirm=True)
    plan['state_hash']=book._state_hash();plan['plan_hash']=_hash(plan)
    return plan,tuple(movements)
