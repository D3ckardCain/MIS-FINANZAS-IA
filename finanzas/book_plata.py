"""Plata: dos productos, cashback y retenciones de filas sin doble conteo global."""
from .book import _hash
from .intake import plain
from .ledger import Evidence, Kind, Movement, Origin, _sum
from .plata import PlataReader
from .storage import movement_id


def prepare(book,doc,content):
    identifier=doc['id']
    plan=dict(document_id=identifier,institution='plata',revision=doc['revision'],status='blocked',can_confirm=False,
              issues=[],warnings=[],periods=[],movements=[],transfers=[])
    for lane in ('debit','investments'):
        view=doc['result']['views'].get(lane,{})
        if view.get('status')!='extracted' or view.get('mode')!='specialized':
            plan['issues'].append('Plata requiere sus dos vistas específicas para confirmar ambos productos.');return plan,()
    try: preview=PlataReader().read_pdf(content)
    except ValueError as error:
        plan['issues'].append(str(error));return plan,()
    plan['issues'].extend(preview.aggregate_issues)
    linked={}
    for pair in preview.transfer_candidates:
        transfer=_hash([identifier,'plata-own-transfer',pair.source_evidence,pair.destination_evidence])
        if pair.source_evidence in linked or pair.destination_evidence in linked:
            plan['issues'].append('Una evidencia Plata participa en más de un traspaso.');continue
        linked[pair.source_evidence]=linked[pair.destination_evidence]=transfer
        plan['transfers'].append(dict(id=transfer,source_evidence=pair.source_evidence,
            destination_evidence=pair.destination_evidence,amount=str(pair.amount),
            cashback_origin_candidate=pair.cashback_origin_candidate))
    movements=[];terms={}
    for lane,product in (('debit',preview.debit),('investments',preview.investments)):
        summary=product.summary
        plan['issues'].extend(product.issues+product.timing_issues)
        if any(a.posting_date>b.posting_date for a,b in zip(product.rows,product.rows[1:])):
            plan['issues'].append('Fechas de cargo Plata no cronológicas en '+lane+'.')
        if summary.commissions_printed!=0 or summary.vat_withheld_printed!=0:
            plan['issues'].append('Comisiones/IVA Plata no nulos requieren mapeo específico de sus filas.')
        account='plata:'+product.account_fingerprint
        period=dict(document_id=identifier,lane=lane,account=account,unit='MXN',start=str(preview.period_start),
            end=str(preview.period_end),initial=str(summary.initial),final=str(summary.final))
        plan['periods'].append(period);book._check_period(plan,period,label='producto Plata '+lane)
        for row in product.rows:
            locator=f'pagina {row.page}, linea {row.line}'
            if row.currency!='MXN' or row.exchange_rate!=1:
                plan['issues'].append('Moneda o conversión Plata requiere revisión: '+locator);continue
            kind=Kind.WITHDRAWAL if row.amount<0 else Kind.CONTRIBUTION
            origin=Origin.UNKNOWN;transfer=None
            if row.category=='interest_received':kind=Kind.INTEREST;origin=None
            elif row.category=='isr_withholding':kind=Kind.WITHHOLDING;origin=None
            elif row.category=='cashback_contribution':origin=Origin.CASHBACK
            elif row.category in ('own_transfer_out','own_transfer_in'):
                transfer=linked.get(row.evidence_id)
                if not transfer:
                    plan['issues'].append('Traspaso propio Plata sin pareja única: '+lane+', '+locator);continue
                origin=Origin.OWN_TRANSFER
            elif row.category not in ('spei_in','spei_out'):
                plan['issues'].append('Concepto Plata sin normalización: '+locator);continue
            if row.amount==0 and kind!=Kind.WITHHOLDING:
                plan['issues'].append('Importe cero Plata sin tipo admitido: '+locator);continue
            movement=Movement(movement_id('plata',account,'document:'+identifier+':'+locator),account,'MXN',
                row.posting_date,kind,row.amount.copy_abs(),Evidence(identifier,locator),origin,transfer)
            movements.append(movement)
            plan['movements'].append(plain(movement)|dict(lane=lane,description=row.description,category=row.category,
                operation_date=str(row.operation_date),posting_date=str(row.posting_date),reference=row.reference,
                outside_period=row.outside_period))
        if not any(m.kind==Kind.WITHHOLDING and m.account==account for m in movements):
            if summary.isr_withheld_printed==0:
                zero=Movement(movement_id('plata',account,'document:'+identifier+':isr-summary'),account,'MXN',
                    preview.period_end,Kind.WITHHOLDING,summary.isr_withheld_printed.copy_abs(),
                    Evidence(identifier,'resumen '+lane+': ISR retenido'))
                movements.append(zero);plan['movements'].append(plain(zero)|dict(lane=lane,description='ISR cero publicado en resumen'))
            else:plan['issues'].append('ISR Plata no nulo sin fila individual en '+lane+'.')
        selected=[m for m in movements if m.account==account]
        for label,reported,calculated in (
            ('Cierre',summary.final,_sum((summary.initial,*(m.signed_amount for m in selected)))),
            ('Depósitos y rendimientos',summary.deposits_and_income,_sum(m.amount for m in selected if m.kind in (Kind.CONTRIBUTION,Kind.INTEREST))),
            ('Interés',summary.gross_income_reported,_sum(m.amount for m in selected if m.kind==Kind.INTEREST)),
            ('ISR',summary.isr_withheld_printed.copy_abs(),_sum(m.amount for m in selected if m.kind==Kind.WITHHOLDING))):
            if reported!=calculated:plan['issues'].append(label+' Plata no coincide tras normalizar '+lane+'; no se ajusta.')
        terms[lane]={key:plain(getattr(summary,key)) for key in
            ('annual_rate_reported','average_balance_reported','gat_nominal_reported','gat_real_reported')}
    plan['reported_terms']=terms
    plan['aggregate_isr_basis']=preview.aggregate_isr_basis
    plan['aggregate_reported']=plain(preview.aggregate)
    plan['annex_pages']=plain(preview.annex_pages)
    plan['warnings'].extend([
        'Débito y ahorro son productos distintos: se guardan dos cuentas; el total Plata solo sirve de control, sin generar una tercera cuenta.',
        'Cashback es aportación con origen cashback. Su traspaso a ahorro reduce débito y aporta a ahorro, sin capital externo adicional.',
        'Interés e ISR se registran desde las filas; depósitos/rendimientos combinados, ISR informativo global y anexo fiscal no generan movimientos adicionales.',
        'La fecha efectiva usa el cargo publicado, conservando también operación y período. Filas posteriores al corte bloquean todo el lote; no se cambian de fecha.',
        'Los SPEI conservan origen pendiente. Referencias ausentes siguen desconocidas y las evidencias se identifican por documento/página/línea, sin deduplicar por importe.',
        'No se infiere reinversión por dejar el interés en ahorro; tasas y GAT son datos históricos publicados.'])
    plan['issues']=list(dict.fromkeys(plan['issues']))
    if not plan['issues']:plan.update(status='ready',can_confirm=True)
    plan['state_hash']=book._state_hash();plan['plan_hash']=_hash(plan)
    return plan,tuple(movements)
