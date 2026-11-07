"""Desglose revisado y reversos enlazados; nunca distribuir agregados por proporción."""
from decimal import Decimal,InvalidOperation
from hashlib import sha256
import json
import re
from .intake import plain
from .ledger import DEBIT_KINDS,Evidence,Kind,Movement,Origin,_sum
from .storage import movement_id

PAY_FIELDS=('principal','ordinary_interest','late_interest','ordinary_vat','late_vat')
TAX_FIELDS=('retention_isr','retention_vat')
CANCELS={'payment_cancellation':'repayment','retention_cancellation':'retention',
    'commission_cancellation':'commission','loan_cancellation':'loan_funding'}
REVERSE={Kind.CONTRIBUTION:Kind.WITHDRAWAL,Kind.WITHDRAWAL:Kind.CONTRIBUTION,
    Kind.INTEREST:Kind.INTEREST_REVERSAL,Kind.VAT_RECEIVED:Kind.VAT_RECEIVED_REVERSAL,
    Kind.WITHHOLDING:Kind.WITHHOLDING_REFUND,Kind.VAT_PAID:Kind.VAT_REFUND,Kind.FEE:Kind.FEE_REFUND}


def signed(kind,amount):return amount.copy_negate() if Kind(kind) in DEBIT_KINDS else amount


def historical_events(book,account):
    events={};used=set()
    for raw, in book.db.execute('SELECT b.plan_json FROM book_batches b JOIN book_periods p USING(document_id) WHERE p.account=?',(account,)):
        plan=json.loads(raw)
        used.update(link['original_event_id'] for link in plan.get('cancellation_links',[]))
        if 'operation_events' in plan:
            events.update((e['id'],e) for e in plan['operation_events'] if e['category'] not in CANCELS);continue
        # Compatibilidad: planes anteriores al desglose múltiple conservan localizador y componentes.
        grouped={}
        for m in plan['movements']:
            if m.get('category') not in ('repayment','retention','commission','loan_funding'):continue
            match=re.match(r'pagina (\d+), linea (\d+)',m['evidence']['locator'])
            if not match:continue
            eid=sha256(f"{plan['document_id']}:{match[1]}:{match[2]}".encode()).hexdigest()
            event=grouped.setdefault(eid,dict(id=eid,document_id=plan['document_id'],category=m['category'],reference=m['reference'],
                date=m['effective_date'],loan_id=m['reference'] if m['category']=='repayment' else None,components=[]))
            event['components'].append(dict(id=m['id'],kind=m['kind'],amount=m['amount'],component=m['component']))
        for e in grouped.values():
            e['total']=str(_sum(signed(m['kind'],Decimal(m['amount'])) for m in e['components']));events[e['id']]=e
    return events,used


def normalize(book,p,account,review):
    result=dict(issues=[],review_rows=[],operation_review=dict(payments={},retentions={},cancellations={}),
        operation_events=[],cancellation_links=[],records=[])
    movements=[];rows={r.evidence_id:r for r in p.rows};s=p.summary
    if review is None:review={}
    if not isinstance(review,dict) or set(review)-{'payments','retentions','cancellations'}:
        result['issues'].append('Revisión de operaciones inválida.');return result,()
    expected={'payments':{'repayment'},'retentions':{'retention'},'cancellations':set(CANCELS)}
    for group,kinds in expected.items():
        values=review.get(group,{})
        if not isinstance(values,dict) or any(k not in rows or rows[k].category not in kinds for k in values):
            result['issues'].append('Revisión contiene filas ajenas o desactualizadas: '+group);return result,()
    prior,used=historical_events(book,account)
    latest={m.id:m for m in book.store.load_ledger().movements}
    available={key:event for key,event in prior.items() if all(c['id'] in latest and
        latest[c['id']].account==account and latest[c['id']].kind==Kind(c['kind']) and
        latest[c['id']].amount==Decimal(c['amount']) and latest[c['id']].evidence.document_id==event['document_id'] and
        str(latest[c['id']].effective_date)==event['date'] for c in event['components'])}
    loans={l.loan_id:l for l in p.loans}
    pays=[r for r in p.rows if r.category=='repayment'];taxes=[r for r in p.rows if r.category=='retention']
    auto_pay=None;auto_tax=None
    if len(pays)==1 and not any(r.category=='payment_cancellation' for r in p.rows):
        loan=loans.get(pays[0].reference)
        if loan and loan.opened<p.period_start:
            principal=_sum((loan.initial,-loan.final))
            if principal>=0 and _sum((principal,s.interest_received_with_vat))==pays[0].amount and all(v>=0 for v in
                (s.ordinary_interest,s.late_interest,s.interest_vat,s.late_interest_vat)):
                auto_pay=dict(zip(PAY_FIELDS,(principal,s.ordinary_interest,s.late_interest,s.interest_vat,s.late_interest_vat)))
    if len(taxes)==1 and not any(r.category=='retention_cancellation' for r in p.rows) and s.retention_total is not None:
        if taxes[0].amount==-s.retention_total and s.retention_isr>=0 and s.retention_vat>=0:
            auto_tax=dict(zip(TAX_FIELDS,(s.retention_isr,s.retention_vat)))

    def parse(values,fields):
        if not isinstance(values,dict) or set(values)-set(fields)-{'loan_id'} or set(fields)-set(values):raise ValueError()
        if 'loan_id' in values and not isinstance(values['loan_id'],str):raise ValueError()
        parsed={}
        for key in fields:
            if not isinstance(values[key],str):raise ValueError()
            number=Decimal(values[key])
            if not number.is_finite() or number<0 or len(number.as_tuple().digits)>36 or not -30<=number.as_tuple().exponent<=30:raise ValueError()
            parsed[key]=number
        return parsed

    def add(row,component,kind,amount,origin=None,reversal_of=None,loan_id=None):
        if amount==0 and kind!=Kind.WITHHOLDING:return None
        locator=f'pagina {row.page}, linea {row.line}: {component}'
        m=Movement(movement_id('yotepresto',account,'document:'+p.document_id+':'+locator),account,'MXN',row.effective_date,
            kind,amount,Evidence(p.document_id,locator),origin)
        movements.append(m);record=plain(m)|dict(lane='debit',component=component,category=row.category,description=row.concept,
            reference=row.reference,source_event_id=row.evidence_id,loan_id=loan_id)
        if reversal_of:record['reversal_of']=reversal_of
        result['records'].append(record)
        return dict(id=m.id,kind=kind.value,amount=str(amount),component=component)

    for index,row in enumerate(p.rows):
        eid=row.evidence_id;category=row.category;components=[];loan_id=None
        prompt=dict(id=eid,date=str(row.effective_date),reference=row.reference,description=row.concept,total=str(row.amount))
        if category in ('repayment','retention'):
            payment=category=='repayment';group='payments' if payment else 'retentions';fields=PAY_FIELDS if payment else TAX_FIELDS
            raw=review.get(group,{}).get(eid);auto=auto_pay if payment else auto_tax
            if (payment and row.amount<0) or (not payment and row.amount>0):
                result['issues'].append('Signo incompatible con concepto: '+row.concept);continue
            values=None
            if raw is not None:
                try:
                    values=parse(raw,fields)
                    if _sum(values.values())!=row.amount.copy_abs():raise ValueError()
                    result['operation_review'][group][eid]={k:str(v) for k,v in values.items()}
                except (ValueError,InvalidOperation):result['issues'].append('Desglose revisado inválido o no coincide con total: '+eid);values=None
            elif auto is not None:values=auto
            if payment:
                loan_id=(raw.get('loan_id') if isinstance(raw,dict) else None) or (row.reference if row.reference in loans else None)
                if not isinstance(loan_id,str):loan_id=None
                if loan_id not in loans or (row.reference in loans and loan_id!=row.reference):
                    result['issues'].append('Pago requiere préstamo único acreditado: '+row.reference);values=None
                if raw is not None and values is not None:result['operation_review'][group][eid]['loan_id']=loan_id
            if values is None:
                result['review_rows'].append(prompt|dict(type=group,fields=list(fields),values=raw if isinstance(raw,dict) else {},
                    loans=[dict(id=l.loan_id,status=l.status) for l in p.loans] if payment else [],loan_id=loan_id))
                result['issues'].append('Desglose por operación pendiente: '+row.reference+' · '+str(row.effective_date));continue
            if payment:
                specs=[('principal',Kind.CONTRIBUTION,Origin.UNKNOWN),('ordinary_interest',Kind.INTEREST,None),
                    ('late_interest',Kind.INTEREST,None),('ordinary_vat',Kind.VAT_RECEIVED,None),('late_vat',Kind.VAT_RECEIVED,None)]
            else:specs=[('retention_isr',Kind.WITHHOLDING,None),('retention_vat',Kind.VAT_PAID,None)]
            for key,kind,origin in specs:
                component=add(row,key,kind,values[key],origin,loan_id=loan_id)
                if component:components.append(component)
        elif category in CANCELS:
            target=CANCELS[category];selected=review.get('cancellations',{}).get(eid)
            selected_loan=None
            if isinstance(selected,dict):
                if set(selected)-{'original_event_id','loan_id'}:
                    result['issues'].append('Selección de original inválida.');continue
                selected_loan=selected.get('loan_id');selected=selected.get('original_event_id')
            # Candidatos incluyen originales pendientes de desglose de este documento.
            candidates=dict(available)
            for earlier in p.rows[:index]:
                if earlier.category==target and earlier.evidence_id not in candidates:
                    candidates[earlier.evidence_id]=dict(id=earlier.evidence_id,document_id=p.document_id,category=target,
                        date=str(earlier.effective_date),reference=earlier.reference,total=str(earlier.amount))
            candidates={k:e for k,e in candidates.items() if e['category']==target and e['reference']==row.reference
                and e['date']<=str(row.effective_date) and Decimal(e['total'])==-row.amount and k not in used}
            if not isinstance(selected,str) or selected not in candidates:
                result['review_rows'].append(prompt|dict(type='cancellations',candidates=[dict(id=k,date=e['date'],reference=e['reference'],
                    total=e['total'],document_id=e['document_id']) for k,e in candidates.items()],selected=None,
                    loans=[dict(id=l.loan_id,status=l.status) for l in p.loans] if category=='loan_cancellation' else []))
                result['issues'].append('Cancelación requiere original compatible elegido, sin usarlo dos veces: '+row.reference);continue
            original=available.get(selected)
            if original is None:
                result['issues'].append('Primero acredita el desglose del original seleccionado: '+row.reference);continue
            loan_id=original.get('loan_id')
            if target=='loan_funding':
                if selected_loan is not None:
                    if not isinstance(selected_loan,str) or selected_loan not in loans or (loan_id and loan_id!=selected_loan):
                        result['issues'].append('Préstamo de cancelación no acreditado o contradictorio.');continue
                    loan_id=selected_loan
                if loan_id is None:
                    result['review_rows'].append(prompt|dict(type='cancellations',candidates=[dict(id=selected,date=original['date'],
                        reference=original['reference'],total=original['total'],document_id=original['document_id'])],selected=None,
                        loans=[dict(id=l.loan_id,status=l.status) for l in p.loans]))
                    result['issues'].append('Cancelación de préstamo requiere acreditar el ID del préstamo.');continue
            for old in original['components']:
                kind=REVERSE.get(Kind(old['kind']))
                if kind is None:result['issues'].append('Componente original no reversible.');continue
                component=add(row,old['component'],kind,Decimal(old['amount']),Origin.UNKNOWN if kind in (Kind.CONTRIBUTION,Kind.WITHDRAWAL) else None,
                    reversal_of=old['id'],loan_id=loan_id)
                if component:components.append(component)
            used.add(selected);result['operation_review']['cancellations'][eid]=dict(original_event_id=selected,loan_id=loan_id) if target=='loan_funding' and loan_id else selected
            result['cancellation_links'].append(dict(cancellation_event_id=eid,original_event_id=selected,
                original_document_id=original['document_id'],original_movement_ids=[m['id'] for m in original['components']]))
        elif category in ('funding','withdrawal','loan_funding','commission'):
            incoming=category=='funding'
            if (incoming and row.amount<=0) or (not incoming and row.amount>0):
                result['issues'].append('Signo incompatible con concepto: '+row.concept);continue
            kind=Kind.CONTRIBUTION if incoming else Kind.FEE if category=='commission' else Kind.WITHDRAWAL
            component=add(row,category,kind,row.amount.copy_abs(),None if kind==Kind.FEE else Origin.UNKNOWN)
            if component:components.append(component)
        else:result['issues'].append('Concepto sin normalización: '+row.concept);continue
        total=_sum(signed(m['kind'],Decimal(m['amount'])) for m in components)
        if total!=row.amount:result['issues'].append('Componentes no reconstruyen la fila: '+eid)
        event=dict(id=eid,document_id=p.document_id,category=category,reference=row.reference,date=str(row.effective_date),
            total=str(row.amount),loan_id=loan_id,components=components)
        result['operation_events'].append(event)
        if category not in CANCELS:available[eid]=event
    # Capital de origen publicado: saldo inicial, o prestado si nació este mes con apertura cero.
    for loan in (() if result['review_rows'] else p.loans):
        initial=loan.lent if loan.opened>=p.period_start and loan.initial==0 else loan.initial
        principal=_sum(signed(m['kind'],Decimal(m['amount'])) for m in result['records']
            if m.get('loan_id')==loan.loan_id and (m['component']=='principal' or m['category']=='loan_cancellation'))
        if principal!=_sum((initial,-loan.final)):
            result['issues'].append('Principal neto del préstamo difiere de sus saldos: '+loan.loan_id)
    return result,tuple(movements)


def check_history(book,p,account,records):
    """Cotejar saldos y acumulados en ambos órdenes; no usarlos para repartir pagos."""
    issues=[];checks=[]
    from datetime import date,timedelta
    new_loans=plain(p.loans)
    for raw,start,end in book.db.execute('SELECT b.plan_json,p.start,p.end FROM book_batches b JOIN book_periods p USING(document_id) WHERE p.account=?',(account,)):
        old=json.loads(raw)
        if date.fromisoformat(end)+timedelta(days=1)==p.period_start:
            previous,current=old['loan_snapshots'],new_loans;current_records=records
            if Decimal(old['platform_summary_observation']['final'])!=p.summary.initial:issues.append('Saldo global inicial difiere del cierre anterior YoTePresto.')
        elif p.period_end+timedelta(days=1)==date.fromisoformat(start):
            previous,current=new_loans,old['loan_snapshots'];current_records=old['movements']
            if p.summary.final!=Decimal(old['platform_summary_observation']['initial']):issues.append('Saldo global final difiere de apertura siguiente YoTePresto.')
        else:continue
        aa={l['loan_id']:l for l in previous};bb={l['loan_id']:l for l in current}
        for lid in sorted(aa.keys()&bb.keys()):
            before,after=aa[lid],bb[lid]
            if Decimal(before['final'])!=Decimal(after['initial']):issues.append('Saldo de préstamo no continúa entre meses: '+lid)
            for field,parts in [('principal_paid_cumulative',{'principal'}),
                ('interest_paid_cumulative',{'ordinary_interest','late_interest'}),('interest_vat_cumulative',{'ordinary_vat','late_vat'})]:
                delta=_sum((Decimal(after[field]),-Decimal(before[field])))
                cash=_sum(signed(m['kind'],Decimal(m['amount'])) for m in current_records
                    if (m.get('loan_id') or m.get('reference'))==lid and m.get('component') in parts)
                checks.append(dict(loan_id=lid,field=field,reported_change=str(delta),classified_change=str(cash)))
                if delta!=cash:issues.append('Cambio acumulado no coincide con pagos/cancelaciones del período: '+lid+' · '+field)
    return issues,checks
