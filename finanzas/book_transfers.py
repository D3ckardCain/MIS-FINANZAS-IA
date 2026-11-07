"""Conciliación explícita de traspasos propios entre cuentas confirmadas."""
from dataclasses import replace
import json
import re

from .book import _hash
from .intake import plain
from .ledger import Kind,Origin
from .readers import fold

_ALLOWED={'transfer','transfer_return','transfer_unmatched','deposit_unmatched','deposit','withdrawal','cash_in','cash_out','funds_added','spei_in','spei_out'}
_DENIED={'purchase','sale','repayment','loan','loan_funding','payment','principal','security_proceeds'}


def eligible(m,record):
    if m.origin!=Origin.UNKNOWN or m.kind not in (Kind.CONTRIBUTION,Kind.WITHDRAWAL) or m.transfer_id:return False
    if not record or record.get('kind')!=m.kind.value or record.get('account')!=m.account or record.get('unit')!=m.unit or record.get('evidence')!=plain(m.evidence):return False
    text=fold(record.get('description',''))
    if record.get('category') in _DENIED or record.get('component')=='principal':return False
    if re.search(r'\b(compra|venta|prestamo|amortizacion|dividendo|interes)\b',text):return False
    return record.get('category') in _ALLOWED or bool(re.search(r'\b(spei|transferencia|traspaso)\b',text))


def _same_source(m,expected):
    return all(value==expected.get(key) for key,value in plain(m).items() if key not in ('origin','transfer_id'))


def _records(book):
    return {r['id']:r for (data,) in book.db.execute('SELECT plan_json FROM book_batches') for r in json.loads(data)['movements']}


def _overview(book):
    records=_records(book);current=book.store._current()
    candidates=[]
    for identifier,(version,m) in current.items():
        if eligible(m,records.get(identifier)):
            candidates.append(plain(m)|dict(version=version,institution='fintual' if m.account.split(':')[0]=='alpaca' else m.account.split(':')[0],
                description=records[identifier].get('description',''),reference=records[identifier].get('reference')))
    outgoing=[r for r in candidates if r['kind']==Kind.WITHDRAWAL.value]
    incoming=[r for r in candidates if r['kind']==Kind.CONTRIBUTION.value]
    matches=[dict(outgoing_id=a['id'],incoming_id=b['id']) for a in outgoing for b in incoming
             if a['account']!=b['account'] and a['unit']==b['unit'] and current[a['id']][1].amount==current[b['id']][1].amount]
    links=[]
    for (payload,) in book.db.execute('SELECT plan_json FROM book_transfer_links ORDER BY rowid DESC'):
        p=json.loads(payload);a=current.get(p['outgoing']['id']);b=current.get(p['incoming']['id'])
        valid=bool(a and b and a[1].origin==b[1].origin==Origin.OWN_TRANSFER and a[1].transfer_id==b[1].transfer_id==p['transfer_id']
            and a[1].kind==Kind.WITHDRAWAL and b[1].kind==Kind.CONTRIBUTION and a[1].account!=b[1].account and a[1].unit==b[1].unit and a[1].amount==b[1].amount
            and _same_source(a[1],p['outgoing']) and _same_source(b[1],p['incoming']))
        links.append(p|dict(status='linked' if valid else 'needs_review'))
    return dict(outgoing=outgoing,incoming=incoming,matches=matches,links=links,
        note='Coincidencia de importe/moneda no acredita propiedad. Revisa ambas evidencias. Solo traspasos completos de igual importe/unidad; comisiones, conversiones y tramos permanecen pendientes. Las fechas de ambas cuentas se conservan.')


def _plan(book,outgoing_id,incoming_id,ownership_confirmed):
    if not isinstance(outgoing_id,str) or not isinstance(incoming_id,str):raise ValueError('Selecciona los dos movimientos.')
    p=dict(status='blocked',can_confirm=False,issues=[],ownership_confirmed=ownership_confirmed is True)
    current=book.store._current();a=current.get(outgoing_id);b=current.get(incoming_id)
    if not a or not b:raise ValueError('Movimiento no encontrado; actualiza el libro.')
    records=_records(book);out=a[1];inc=b[1]
    p.update(outgoing=plain(out)|dict(version=a[0]),incoming=plain(inc)|dict(version=b[0]),transfer_id=_hash(['cross-account-own',outgoing_id,incoming_id]))
    if out.kind!=Kind.WITHDRAWAL or inc.kind!=Kind.CONTRIBUTION or out.account==inc.account or out.unit!=inc.unit or out.amount!=inc.amount:
        p['issues'].append('Traspaso incompatible: debe reducir una cuenta y aportar a otra con igual importe y moneda.')
    linked=book.db.execute('SELECT plan_json FROM book_transfer_links WHERE transfer_id=?',(p['transfer_id'],)).fetchone()
    original=json.loads(linked[0]) if linked else None
    if linked and not p['issues'] and out.origin==inc.origin==Origin.OWN_TRANSFER and out.transfer_id==inc.transfer_id==p['transfer_id'] and _same_source(out,original['outgoing']) and _same_source(inc,original['incoming']):
        return p|dict(status='linked',duplicate=True)
    if not eligible(out,records.get(outgoing_id)) or not eligible(inc,records.get(incoming_id)):
        p['issues'].append('Movimiento no elegible o ya vinculado; compras, cobros de préstamos y orígenes conocidos no se reclasifican.')
    if ownership_confirmed is not True:p['issues'].append('Falta verificar con ambas evidencias que las cuentas y el dinero son propios.')
    p['state_hash']=book._state_hash()
    if not p['issues']:p.update(status='ready',can_confirm=True)
    p['plan_hash']=_hash(p)
    return p


def confirm(book,outgoing_id,incoming_id,ownership_confirmed,plan_hash):
    with book.store._transaction():
        p=plan(book,outgoing_id,incoming_id,ownership_confirmed)
        if p['status']=='linked':return p|dict(duplicate=True)
        if not p['can_confirm'] or p['plan_hash']!=plan_hash:raise ValueError('El plan o el libro cambió; revisa ambas evidencias y prepara otra vez.')
        current=book.store._current();rows=[];corrections={}
        for key in ('outgoing','incoming'):
            identifier=p[key]['id'];version,m=current[identifier]
            rows.append(replace(m,origin=Origin.OWN_TRANSFER,transfer_id=p['transfer_id']))
            corrections[identifier]=(version,'Traspaso propio acreditado con ambas evidencias; plan '+plan_hash)
        book.store.record_many(rows,corrections=corrections)
        book.db.execute('INSERT INTO book_transfer_links VALUES(?,?,?,?)',
            (p['transfer_id'],outgoing_id,incoming_id,json.dumps(p,ensure_ascii=False)))
        return p|dict(status='linked',can_confirm=False,duplicate=False)


def _snapshot(book,fn,*args):
    nested=book.db.in_transaction
    if not nested:book.db.execute('BEGIN')
    try:return fn(book,*args)
    finally:
        if not nested:book.db.rollback()


def overview(book):return _snapshot(book,_overview)


def plan(book,outgoing_id,incoming_id,ownership_confirmed):return _snapshot(book,_plan,outgoing_id,incoming_id,ownership_confirmed)
