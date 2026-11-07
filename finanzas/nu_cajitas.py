"""Desglose opcional acreditado por Cajita, sin duplicar el agregado Nu."""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256

from .book import _hash
from .intake import plain
from .ledger import Evidence,Kind,Movement,_sum
from .nu import NuReader
from .readers import fold
from .storage import movement_id


def prepare_individual(book,doc,content,aggregate,*,password=None,currency_confirmation=None,operation_review=None):
    from .book_nu import _amount
    original=deepcopy(operation_review)
    items=None;values=[];error=None;individual=False
    if isinstance(original,dict) and isinstance(original.get('nu'),dict) and 'cajitas' in original['nu']:
        individual=True;items=original['nu'].pop('cajitas')
        try:
            if not isinstance(items,list) or not items:raise ValueError('Acredita al menos una Cajita individual.')
            names=set()
            for row in items:
                if not isinstance(row,dict) or set(row)!={'name','initial','final','gross_interest','withholding'}:raise ValueError('Desglose individual Nu incompleto o desconocido.')
                name=row['name']
                if not isinstance(name,str) or not name.strip() or len(name)>120 or any(ord(c)<32 for c in name):raise ValueError('Nombre de Cajita Nu inválido.')
                name=' '.join(fold(name).split())
                if name in names:raise ValueError('Cajita repetida o nombre normalizado ambiguo.')
                names.add(name)
                values.append(dict(name=name,**{k:_amount(row[k]) for k in ('initial','final','gross_interest','withholding')}))
            if not isinstance(original['nu'].get('buckets'),dict):raise ValueError('Productos Nu inválidos.')
            original['nu']['buckets']['investments']={key:str(_sum(row[key] for row in values)) for key in ('initial','gross_interest','withholding')}
        except ValueError as exc:error=str(exc)
    plan,movements=aggregate(book,doc,content,password=password,currency_confirmation=currency_confirmation,operation_review=original)
    plan['nu_cajita_candidates']=[]
    if 'nu_summary_observation' not in plan:return plan,movements
    p=NuReader().read_pdf(content,password=password)
    names=sorted({e.cajita for e in p.investment_events if e.section=='cajitas' and e.cajita})
    plan['nu_cajita_candidates']=names
    prefix='nu:'+p.account_fingerprint+':'
    history=book.db.execute('SELECT DISTINCT account FROM book_periods WHERE substr(account,1,?)=?',(len(prefix),prefix)).fetchall()
    if not individual:
        if any(a.startswith(prefix+'cajita:') for (a,) in history):
            plan['issues'].append('Este historial Nu usa Cajitas individuales; conserva ese desglose para evitar duplicación.')
    else:
        if any(a==prefix+'investments' for (a,) in history):
            plan['issues'].append('Este historial Nu usa Cajitas agregadas; no se mezcla con saldos individuales sin una transición acreditada.')
        if error:plan['issues'].append(error)
        elif plan.get('operation_review'):
            if not set(names)<={r['name'] for r in values}:plan['issues'].append('Faltan Cajitas con movimientos en el desglose individual revisado.')
            if _sum(r['final'] for r in values)!=p.summary.cajitas_reported:plan['issues'].append('Cierres individuales Nu no suman Total Cajitas publicado.')
            aggregate_account=prefix+'investments'
            retained=[m for m in movements if m.account!=aggregate_account]
            records=[r for r in plan['movements'] if r['account']!=aggregate_account]
            plan['periods']=[r for r in plan['periods'] if r['account']!=aggregate_account]
            keyed={r['name']:r for r in values}
            for name,v in keyed.items():
                suffix=sha256(name.encode()).hexdigest();account=prefix+'cajita:'+suffix;lane='investments:'+suffix
                def append(kind,amount,when,locator,origin=None,transfer=None,**meta):
                    if amount==0 and kind!=Kind.WITHHOLDING:return
                    m=Movement(movement_id('nu',account,'document:'+doc['id']+':'+locator),account,'MXN',when,kind,amount,Evidence(doc['id'],locator),origin,transfer)
                    retained.append(m);records.append(plain(m)|dict(lane=lane,cajita=name,**meta))
                for m,r in zip(movements,plan['movements']):
                    if m.account==aggregate_account and r.get('date_basis')=='document_row' and r.get('cajita')==name:
                        append(m.kind,m.amount,m.effective_date,m.evidence.locator,m.origin,m.transfer_id,date_basis='document_row')
                append(Kind.INTEREST,v['gross_interest'],p.period_end,'resumen revisado: interés Cajita '+suffix,date_basis='period_close_summary',allocation_source='user_review_individual')
                append(Kind.WITHHOLDING,v['withholding'],p.period_end,'resumen revisado: ISR Cajita '+suffix,date_basis='period_close_summary',allocation_source='user_review_individual')
                period=dict(document_id=doc['id'],lane=lane,role='cajita',product_name=name,account=account,unit='MXN',
                    start=str(p.period_start),end=str(p.period_end),initial=str(v['initial']),final=str(v['final']))
                plan['periods'].append(period);book._check_period(plan,period,label='Cajita Nu '+name)
                if _sum((v['initial'],*(m.signed_amount for m in retained if m.account==account)))!=v['final']:
                    plan['issues'].append('Cierre individual Nu incompatible con filas y distribución: '+name)
            # Una Cajita conocida no desaparece del historial por omisión en la revisión.
            current_accounts={r['account'] for r in plan['periods']}
            if any(a.startswith(prefix+'cajita:') and a not in current_accounts for (a,) in history):
                plan['issues'].append('Conserva las Cajitas históricas, incluso con cierre cero; no se omiten saldos desconocidos.')
            plan['movements']=records;movements=tuple(retained)
            plan['operation_review']['nu']['cajitas']=plain(values)
            plan['nu_individual_mode']=True
            plan['warnings'][0]='Cuenta, cada Cajita revisada y garantía se confirman separadas. Total Cajitas solo controla la suma: no crea otra cuenta. Los saldos/distribución individuales son acreditación del usuario, no lectura automática del agregado.'
    plan['issues']=list(dict.fromkeys(plan['issues']))
    plan.update(can_confirm=not plan['issues'],status='blocked' if plan['issues'] else 'ready')
    plan['state_hash']=book._state_hash();plan['plan_hash']=_hash(plan)
    return plan,movements
