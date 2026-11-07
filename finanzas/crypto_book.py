"""Registro local revisado de operaciones cripto, separado de saldos bancarios."""
from datetime import datetime,timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from .book import _hash
from .intake import Inbox
from .ledger import _sum

_COMMON={'account','kind','occurred_at','status','verified'}
_FIELDS={
    'spot_buy':{'order_id','trade_id','base_asset','quote_asset','quantity','quote_amount','fee_amount','fee_asset'},
    'spot_sell':{'order_id','trade_id','base_asset','quote_asset','quantity','quote_amount','fee_amount','fee_asset'},
    'yield':{'transaction_id','asset','amount','fee_amount','fee_asset'},
    'derivative':{'order_id','trade_id','pair','contracts','contracts_unit','settlement_asset','realized_pnl','unrealized_pnl','funding','fee_amount','fee_asset'},
    'bot_summary':{'bot_id','profit_amount','asset'},
}


def _text(value,label,limit=120):
    if not isinstance(value,str) or not value.strip() or len(value)>limit or any(ord(c)<32 for c in value):raise ValueError(label+' requerido o inválido.')
    return value.strip()


def _asset(value):
    value=_text(value,'Activo',20).upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9._-]{0,19}',value):raise ValueError('Activo/unidad inválido.')
    return value


def _amount(value,*,signed=False,positive=False):
    if not isinstance(value,str) or not re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?' if signed else r'[0-9]+(?:\.[0-9]+)?',value):raise ValueError('Importe decimal explícito requerido; ausencia no es cero.')
    v=Decimal(value)
    if len(v.as_tuple().digits)>36 or v.as_tuple().exponent < -30 or (positive and v<=0):raise ValueError('Importe fuera de rango o precisión.')
    return _number(v)


def _number(value):
    if not value:return '0'
    text=format(value,'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def _canonical(platform,r):
    if not isinstance(r,dict) or r.get('kind') not in _FIELDS:raise ValueError('Selecciona un tipo cripto admitido.')
    kind=r['kind']
    if set(r)!=_COMMON|_FIELDS[kind]:raise ValueError('Campos cripto incompletos o desconocidos.')
    if r['verified'] is not True:raise ValueError('Verifica los datos con la captura antes de preparar.')
    account=' '.join(_text(r['account'],'Cuenta o subcuenta').casefold().split())
    local=_text(r['occurred_at'],'Fecha/hora con zona',50)
    if re.search(r'\d{2}:\d{2}:\d{2}[.,]\d{7}',local):raise ValueError('Precisión temporal superior a microsegundos; no se trunca automáticamente.')
    try:when=datetime.fromisoformat(local.replace('Z','+00:00'))
    except ValueError as exc:raise ValueError('Fecha/hora ISO inválida.') from exc
    if when.tzinfo is None or when.utcoffset() is None:raise ValueError('La fecha requiere un desplazamiento horario explícito; no se supone la zona del usuario.')
    occurred=when.astimezone(timezone.utc).isoformat()
    expected='snapshot' if kind=='bot_summary' else 'paid' if kind=='yield' else 'executed'
    if r['status']!=expected:raise ValueError('Estado incompatible: se exige ejecución, pago o fotografía de resumen explícitos.')
    data=dict(platform=platform,account=account,kind=kind,occurred_at=occurred,status=expected)
    effects=[]
    def effect(asset,amount,component):effects.append(dict(asset=asset,amount=_number(amount),component=component))
    if kind.startswith('spot_'):
        for k in ('order_id','trade_id'):data[k]=_text(r[k],k)
        for k in ('base_asset','quote_asset'):data[k]=_asset(r[k])
        if data['base_asset']==data['quote_asset']:raise ValueError('Activos base y cotizado deben ser distintos.')
        for k in ('quantity','quote_amount'):data[k]=_amount(r[k],positive=True)
        buy=kind=='spot_buy';q=Decimal(data['quantity']);quote=Decimal(data['quote_amount'])
        effect(data['base_asset'],q if buy else q.copy_negate(),'base')
        effect(data['quote_asset'],quote.copy_negate() if buy else quote,'quote')
        identity=('spot',data['order_id'],data['trade_id'])
    elif kind=='yield':
        data.update(transaction_id=_text(r['transaction_id'],'ID de pago'),asset=_asset(r['asset']),amount=_amount(r['amount'],positive=True))
        effect(data['asset'],Decimal(data['amount']),'yield');identity=('yield',data['transaction_id'])
    elif kind=='derivative':
        for k in ('order_id','trade_id','pair'):data[k]=_text(r[k],k)
        data.update(contracts=_amount(r['contracts'],positive=True),contracts_unit=_asset(r['contracts_unit']))
        data['settlement_asset']=_asset(r['settlement_asset']) if r['settlement_asset'] is not None else None
        for k in ('realized_pnl','unrealized_pnl','funding'):
            data[k]=_amount(r[k],signed=True) if r[k] is not None else None
            if data[k] is not None and data['settlement_asset'] is None:raise ValueError('PnL/funding requieren activo de liquidación explícito.')
        identity=('derivative',data['order_id'],data['trade_id'])
    else:
        data['bot_id']=_text(r['bot_id'],'ID del bot');data['asset']=_asset(r['asset']) if r['asset'] is not None else None
        data['profit_amount']=_amount(r['profit_amount'],signed=True) if r['profit_amount'] is not None else None
        if data['profit_amount'] is not None and data['asset'] is None:raise ValueError('Beneficio de bot requiere unidad explícita.')
        identity=('bot_summary',data['bot_id'],occurred)
    if kind!='bot_summary':
        data['fee_amount']=_amount(r['fee_amount']) if r['fee_amount'] is not None else None
        data['fee_asset']=_asset(r['fee_asset']) if r['fee_asset'] is not None else None
        if (data['fee_amount'] is None)!=(data['fee_asset'] is None):raise ValueError('Comisión y su activo deben acreditarse juntos, o quedar ambos desconocidos.')
        if data['fee_amount'] is not None and kind!='derivative' and Decimal(data['fee_amount']):effect(data['fee_asset'],Decimal(data['fee_amount']).copy_negate(),'fee')
    identifier=_hash([platform,account,*identity])
    return identifier,data,effects


class CryptoBook:
    def __init__(self,inbox_path):
        self.path=Path(inbox_path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path.with_name(self.path.name+'.crypto.sqlite3'),isolation_level=None,timeout=5)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS crypto_operations(id TEXT PRIMARY KEY,canonical_json TEXT NOT NULL,effects_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS crypto_evidence(document_id TEXT PRIMARY KEY,operation_id TEXT NOT NULL REFERENCES crypto_operations(id),source_revision INTEGER NOT NULL,review_json TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        ''')
    def close(self):self.db.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def _state(self):return _hash(dict(operations=self.db.execute('SELECT * FROM crypto_operations ORDER BY id').fetchall(),evidence=self.db.execute('SELECT * FROM crypto_evidence ORDER BY document_id').fetchall()))
    def _existing(self,identifier):
        row=self.db.execute('SELECT operation_id,source_revision FROM crypto_evidence WHERE document_id=?',(identifier,)).fetchone()
        return dict(status='confirmed',can_confirm=False,document_id=identifier,operation_id=row[0],revision=row[1],duplicate=True,issues=[]) if row else None
    def _plan(self,doc,review):
        p=dict(document_id=doc['id'],revision=doc['revision'],status='blocked',can_confirm=False,issues=[],candidates=[],review=review,
            warnings=['La captura no acredita saldo ni historia completa. Revisión obligatoria; una orden no equivale a una ejecución.',
                'Spot y pagos documentados generan variaciones por activo, no saldo actual, ganancia realizada, conversión MXN ni ISR anual.',
                'Futuros y resúmenes de bot se conservan como observaciones: sus PnL/funding no se suman al efectivo ni al resultado spot. Comisión ausente permanece desconocida.'])
        result=doc['result'];platform=result.get('institution');view=result['views'].get('investments',{})
        if platform not in ('bingx','pionex') or result.get('format')!='image' or view.get('status')!='extracted' or view.get('mode')!='ocr':
            p['issues'].append('Se requiere captura BingX/Pionex con lectura OCR disponible.');return p
        p['platform']=platform;p['candidates']=view.get('data',{}).get('fields',[]);p['ocr_issues']=view.get('issues',[])
        if review is None:p['issues'].append('Completa y acredita los datos de la operación.');return p
        try:identifier,data,effects=_canonical(platform,review)
        except (ValueError,TypeError,OverflowError) as error:p['issues'].append(str(error));return p
        p.update(operation_id=identifier,operation=data,effects=effects)
        prior=self.db.execute('SELECT canonical_json FROM crypto_operations WHERE id=?',(identifier,)).fetchone()
        if prior and json.loads(prior[0])!=data:p['issues'].append('La misma identidad de ejecución/pago ya tiene datos distintos; no se sobrescribe ni se duplica.');return p
        p.update(duplicate_operation=bool(prior),state_hash=self._state(),status='ready',can_confirm=True)
        p['plan_hash']=_hash(p);return p
    def preview(self,identifier,*,review=None,revision=None):
        with Inbox(self.path) as inbox:
            doc=inbox.get(identifier)
            if revision is not None and (type(revision) is not int or revision!=doc['revision']):raise ValueError('Versión documental desactualizada.')
            return self._existing(identifier) or self._plan(doc,review)
    def confirm(self,identifier,*,revision,review,plan_hash):
        with Inbox(self.path) as inbox:
            inbox.db.execute('BEGIN IMMEDIATE');self.db.execute('BEGIN IMMEDIATE')
            try:
                existing=self._existing(identifier)
                if existing:return existing
                doc=inbox.get(identifier)
                if type(revision) is not int or revision!=doc['revision']:raise ValueError('Versión documental desactualizada.')
                p=self._plan(doc,review)
                if not p['can_confirm'] or p['plan_hash']!=plan_hash:raise ValueError('El plan cambió o contiene pendientes; no se registró nada.')
                if not p['duplicate_operation']:self.db.execute('INSERT INTO crypto_operations VALUES(?,?,?)',(p['operation_id'],json.dumps(p['operation'],sort_keys=True),json.dumps(p['effects'])))
                self._save_evidence(identifier,p['operation_id'],revision,review)
                self.db.commit();return p|dict(status='confirmed',can_confirm=False,duplicate=False)
            finally:
                if self.db.in_transaction:self.db.rollback()
                inbox.db.rollback()
    def _save_evidence(self,identifier,operation,revision,review):
        self.db.execute('INSERT INTO crypto_evidence(document_id,operation_id,source_revision,review_json) VALUES(?,?,?,?)',(identifier,operation,revision,json.dumps(review,ensure_ascii=False)))
    def summary(self):
        self.db.execute('BEGIN')
        try:
            operations=[];groups={}
            for identifier,canonical,effects in self.db.execute('SELECT * FROM crypto_operations'):
                data=json.loads(canonical);effects=json.loads(effects)
                sources=[dict(document_id=doc,revision=rev) for doc,rev in self.db.execute('SELECT document_id,source_revision FROM crypto_evidence WHERE operation_id=? ORDER BY document_id',(identifier,))]
                operations.append(data|dict(id=identifier,effects=effects,sources=sources))
                for e in effects:
                    key=(data['platform'],data['account'],e['asset']);groups.setdefault(key,[]).append(Decimal(e['amount']))
            operations.sort(key=lambda o:(o['occurred_at'],o['id']))
            deltas=[dict(platform=p,account=a,asset=asset,recorded_change=_number(_sum(values))) for (p,a,asset),values in sorted(groups.items())]
            return dict(operations=operations,asset_changes=deltas,documents=self.db.execute('SELECT COUNT(*) FROM crypto_evidence').fetchone()[0],
                unknown_fee_operations=sum(o['kind']!='bot_summary' and o['fee_amount'] is None for o in operations),
                note='Variaciones de operaciones registradas, no saldos. Historial y aperturas no acreditados; comisiones desconocidas hacen parcial el neto. Activos/plataformas/cuentas permanecen separados. Futuros y bots son observaciones sin efecto patrimonial automático.')
        finally:self.db.rollback()
