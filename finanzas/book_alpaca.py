"""Alpaca: efectivo USD, dividendos e impuesto extranjero; posiciones observadas."""
from .alpaca import AlpacaReader
from .book import _hash
from .intake import plain
from .ledger import Evidence, Kind, Movement, Origin, _sum
from .storage import movement_id


def prepare(book,doc,content,*,password=None):
    identifier=doc['id']
    plan=dict(document_id=identifier,institution='fintual',reader_profile='alpaca',custodian='alpaca',portfolio_unit='USD',revision=doc['revision'],status='blocked',can_confirm=False,
        issues=[],warnings=[],periods=[],movements=[],transfers=[],stock_positions=[],memo_observations=[],
        password_required=False,withholding_status='unknown',withholding_basis='foreign_tax_separate_from_mexican_isr')
    if password is not None and not isinstance(password,str):
        plan['issues'].append('La contraseña debe ser texto.');return plan,()
    for lane in ('debit','investments'):
        view=doc['result']['views'].get(lane,{})
        if view.get('status')!='extracted' or view.get('mode')!='specialized':
            plan['issues'].append('Alpaca requiere ambas lecturas específicas del portafolio.');return plan,()
    try:preview=AlpacaReader().read_pdf(content,password=password)
    except ValueError as error:
        plan['password_required']='protegido' in str(error)
        plan['issues'].append(str(error));return plan,()
    summary=preview.summary
    plan['issues'].extend(preview.issues+preview.detail_issues)
    plan['stock_positions']=plain(preview.positions)
    plan['stock_summary_observation']=plain(summary)
    plan['trade_observations']=plain(tuple(r for r in preview.entries if r.category in ('buy','sell')))
    plan['memo_observations']=plain(tuple(r for r in preview.entries if r.category=='memo'))
    plan['warnings'].extend([
        'Se confirma una cuenta de efectivo USD del portafolio, sin otra cuenta por pestaña. Acciones/ETF, costo y resultados reportados quedan como observaciones, sin sumar su valuación al cierre de efectivo.',
        'Compra reduce efectivo y venta lo aporta con origen pendiente. No se calcula ganancia realizada, costo por lote, reinversión o capital externo desde el importe de venta.',
        'Dividendos e intereses cobrados son ingresos separados. Retención extranjera es un cargo distinto del ISR mexicano: no se calcula acreditamiento, conversión a MXN o declaración anual.',
        'Las cifras del período generan los controles; los acumulados del año, resultados realizados y plusvalías observadas no originan nuevos cobros.',
        'Comisiones de operaciones y cargos de la sección Fees se registran una vez y se contrastan con sus resúmenes. Memopost solo puede excluirse de efectivo si importe y comisión publicados son cero.',
        'Original, fecha publicada y evidencias por sección/página/línea se conservan. Operaciones iguales legítimas no se deduplican por fecha, símbolo o importe.'])
    cash={x.label:x.current for x in summary.cash}
    holdings=dict(summary.account_values)
    for label in ('Short','Options','Fixed Income'):
        if holdings.get(label)!=0:plan['issues'].append('Alpaca: '+label+' no nulo/desconocido requiere otro alcance contable.')
    cash_position=next((p for p in preview.positions if p.symbol=='*Cash'),None)
    if cash_position is None or cash_position.market_value!=cash.get('Ending Value'):
        plan['issues'].append('Efectivo de Holdings no coincide con Ending Value; no se ajusta.')
    if any(p.symbol!='*Cash' and ((p.quantity is not None and p.quantity<0) or (p.price is not None and p.price<0)) for p in preview.positions):
        plan['issues'].append('Posición corta o precio negativo Alpaca fuera del alcance.')
    if any(r.amount is None or r.commission is None or r.commission<0 for r in preview.entries if r.category in ('buy','sell')):
        plan['issues'].append('Operación Alpaca con importe/comisión desconocido o negativo.')
    if any(r.amount!=0 or r.commission!=0 for r in preview.entries if r.category=='memo'):
        plan['issues'].append('Memopost Alpaca con efecto monetario desconocido/no nulo: requiere clasificación.')
    if plan['issues']:
        plan['issues']=list(dict.fromkeys(plan['issues']));return plan,()
    account='alpaca:'+preview.account_fingerprint
    period=dict(document_id=identifier,lane='investments',role='fund_cash',account=account,unit=summary.unit,
        start=str(preview.period_start),end=str(preview.period_end),initial=str(cash['Beginning Balance']),final=str(cash['Ending Value']))
    plan['periods'].append(period);book._check_period(plan,period,label='efectivo USD Alpaca')
    movements=[]
    def append(row,component,kind,value,origin=None):
        if value==0 and kind!=Kind.FOREIGN_WITHHOLDING:return
        locator=f'pagina {row.page}, linea {row.line}: {component}'
        movement=Movement(movement_id('alpaca',account,'document:'+identifier+':'+locator),account,summary.unit,row.effective_date,
            kind,value,Evidence(identifier,locator),origin)
        movements.append(movement);plan['movements'].append(plain(movement)|dict(lane='investments',role='fund_cash',
            category=row.category,component=component,description=row.description,symbol=row.symbol))
    for row in preview.entries:
        if row.category=='memo':continue
        if row.amount is None:
            plan['issues'].append('Importe monetario Alpaca desconocido.');continue
        if row.category in ('dividend','interest'):
            if row.amount<0:plan['issues'].append('Ingreso Alpaca negativo requiere ajuste específico.');continue
            append(row,'income',Kind.DIVIDEND if row.category=='dividend' else Kind.INTEREST,row.amount)
        elif row.category=='foreign_withholding':
            if row.amount>0:plan['issues'].append('Devolución de impuesto extranjero requiere otro concepto.');continue
            append(row,'foreign_tax',Kind.FOREIGN_WITHHOLDING,row.amount.copy_abs())
        elif row.category=='fee':
            if row.amount>=0:plan['issues'].append('Cargo Alpaca con signo inesperado.');continue
            append(row,'fee',Kind.FEE,row.amount.copy_abs())
        elif row.category in ('buy','sell'):
            append(row,'trade_cash',Kind.WITHDRAWAL if row.category=='buy' else Kind.CONTRIBUTION,row.amount.copy_abs(),Origin.UNKNOWN)
            append(row,'trade_commission',Kind.FEE,row.commission)
        else:plan['issues'].append('Concepto Alpaca sin normalización: '+row.label)
    for label,reported,calculated in (
        ('Cierre',cash['Ending Value'],_sum((cash['Beginning Balance'],*(m.signed_amount for m in movements)))),
        ('Cost and Fees',cash['Cost and Fees'],_sum(r.commission for r in preview.entries if r.category in ('buy','sell'))),
        ('Addition',cash['Addition'],_sum(m.amount for m in movements if m.kind in (Kind.INTEREST,Kind.DIVIDEND))),
        ('Subtraction',cash['Subtraction'],_sum(r.amount.copy_abs() for r in preview.entries if r.category in ('fee','foreign_withholding') and r.amount is not None))):
        if reported!=calculated:plan['issues'].append(label+' Alpaca no coincide tras normalizar; no se ajusta.')
    plan['issues']=list(dict.fromkeys(plan['issues']))
    if not plan['issues']:plan.update(status='ready',can_confirm=True)
    plan['state_hash']=book._state_hash();plan['plan_hash']=_hash(plan)
    return plan,tuple(movements)
