"""Planes revisables y confirmación financiera atómica sobre el ledger.

Los saldos iniciales son anclas documentales, no nuevas aportaciones. Esto
permite incorporar meses fuera de orden sin duplicar aperturas ni inventar
movimientos durante huecos de cobertura.
"""
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

from .intake import Inbox, plain
from .ledger import Evidence, Kind, Movement, Origin, _sum
from .openbank import OpenbankDebitReader, OpenbankInvestmentReader, transfer_candidates
from .storage import Store, movement_id


def _hash(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class FinancialBook:
    def __init__(self, inbox_path):
        self.inbox_path = Path(inbox_path)
        self.store = Store(self.inbox_path.with_name(self.inbox_path.name + '.ledger.sqlite3'))
        self.db = self.store._db
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS book_batches (
                document_id TEXT PRIMARY KEY REFERENCES documents(id),
                source_revision INTEGER NOT NULL, plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS book_periods (
                document_id TEXT NOT NULL REFERENCES documents(id), lane TEXT NOT NULL,
                account TEXT NOT NULL, unit TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL,
                initial TEXT NOT NULL, final TEXT NOT NULL,
                PRIMARY KEY(document_id,lane)
            );
        ''')

    def close(self): self.store.close()
    def __enter__(self): return self
    def __exit__(self, *args): self.close()

    def _state_hash(self):
        return _hash(dict(periods=self.db.execute('SELECT * FROM book_periods ORDER BY document_id,lane').fetchall(),
            revisions=self.db.execute('SELECT movement_id,version,payload FROM revisions ORDER BY seq').fetchall()))

    def _existing(self, identifier):
        found=self.db.execute('SELECT plan_json FROM book_batches WHERE document_id=?',(identifier,)).fetchone()
        if found:
            return json.loads(found[0]) | dict(status='imported', can_confirm=False)

    def preview(self, identifier, *, currency_confirmation=None, expected_revision=None, password=None):
        with Inbox(self.inbox_path) as inbox:
            doc=inbox.get(identifier)
            if expected_revision is not None and (type(expected_revision) is not int or expected_revision!=doc['revision']):
                raise ValueError('Revisión desactualizada: vuelve a abrir el documento.')
            existing=self._existing(identifier)
            if existing: return existing
            plan,_=self._plan(doc,inbox.original(identifier),currency_confirmation=currency_confirmation,password=password)
            return plan

    def _plan(self, doc, content, *, currency_confirmation=None, password=None):
        if doc['result']['institution']=='hey' and doc['result']['format']=='pdf':
            from .book_hey import prepare
            return prepare(self,doc,content,currency_confirmation=currency_confirmation,password=password)
        if doc['result']['institution']=='supertasas' and doc['result']['format']=='pdf':
            from .book_supertasas import prepare
            return prepare(self,doc,content,currency_confirmation=currency_confirmation,password=password)
        if doc['result']['institution']=='plata' and doc['result']['format']=='pdf':
            from .book_plata import prepare
            return prepare(self,doc,content)
        if doc['result']['institution']=='fondeadora' and doc['result']['format']=='pdf':
            from .book_fondeadora import prepare
            return prepare(self,doc,content,currency_confirmation=currency_confirmation)
        if doc['result']['institution']=='didi' and doc['result']['format']=='pdf':
            from .book_didi import prepare
            return prepare(self,doc,content)
        if doc['result']['institution']=='bancoppel' and doc['result']['format']=='pdf':
            from .book_bancoppel import prepare
            return prepare(self,doc,content)
        if doc['result']['institution']=='mifel' and doc['result']['format']=='pdf':
            return self._mifel_plan(doc,content)
        identifier=doc['id']
        plan=dict(document_id=identifier, revision=doc['revision'], status='blocked', can_confirm=False,
                  issues=[], warnings=[], periods=[], movements=[], transfers=[])
        if doc['result']['institution']!='openbank' or doc['result']['format']!='pdf':
            plan['issues'].append('La confirmación financiera de este formato todavía no está implementada.');return plan,()
        previews={}
        for lane,cls in (('debit',OpenbankDebitReader),('investments',OpenbankInvestmentReader)):
            view=doc['result']['views'].get(lane,{})
            if view.get('status')!='extracted':
                plan['warnings'].append('Vista '+lane+': no disponible; excluida del lote financiero.')
                continue
            if view.get('mode')!='specialized':
                plan['warnings'].append('Vista '+lane+': lectura documental excluida del lote financiero.');continue
            try: preview=cls().read_pdf(content)
            except ValueError as error:
                plan['issues'].append(str(error));continue
            if not preview.reconciled:
                plan['issues'].extend(preview.issues);continue
            if not preview.account_fingerprint:
                plan['issues'].append('Falta identidad de cuenta publicada: no se inventa una cuenta.');continue
            previews[lane]=preview
        if not previews:
            plan['issues'].append('No hay vistas conciliadas con identidad verificable.');return plan,()
        if len({(p.period_start,p.period_end) for p in previews.values()})!=1:
            plan['issues'].append('Las dos vistas publican períodos diferentes.');return plan,()
        linked={}
        if len(previews)==2:
            for source,target in transfer_candidates(previews['debit'],previews['investments']):
                transfer=_hash([identifier,'internal',source,target])
                linked['debit',source]=transfer;linked['investments',target]=transfer
                plan['transfers'].append(dict(id=transfer,source=source,destination=target))
        movements=[]
        internal={'to_investments','from_investments','from_debit','to_debit'}
        for lane,preview in previews.items():
            account='openbank:'+preview.account_fingerprint
            period=dict(document_id=identifier,lane=lane,account=account,unit='MXN',
                start=str(preview.period_start),end=str(preview.period_end),
                initial=str(preview.summary.initial),final=str(preview.summary.final))
            plan['periods'].append(period)
            previous=self.db.execute('SELECT start,end,initial,final FROM book_periods WHERE account=? ORDER BY start',(account,)).fetchall()
            for start,end,initial,final in previous:
                if start<=period['end'] and end>=period['start']:
                    plan['issues'].append('Período superpuesto en '+lane+': revisar documentos antes de duplicar operaciones.')
                if date.fromisoformat(end)+timedelta(days=1)==preview.period_start and Decimal(final)!=preview.summary.initial:
                    plan['issues'].append('Saldo inicial no coincide con cierre anterior en '+lane+'.')
                if preview.period_end+timedelta(days=1)==date.fromisoformat(start) and Decimal(initial)!=preview.summary.final:
                    plan['issues'].append('Saldo final no coincide con apertura siguiente en '+lane+'.')
            for row in preview.rows:
                outgoing=row.withdrawal>0
                kind=Kind.WITHDRAWAL if outgoing else Kind.CONTRIBUTION
                origin=Origin.UNKNOWN
                transfer=None
                if row.category=='interest': kind=Kind.INTEREST;origin=None
                elif row.category in internal:
                    transfer=linked.get((lane,row.locator))
                    if not transfer:
                        plan['issues'].append('Transferencia propia sin pareja única: '+lane+', '+row.locator)
                        continue
                    origin=Origin.OWN_TRANSFER
                elif row.category!='debit_movement':
                    plan['issues'].append('Concepto sin normalización: '+row.locator);continue
                reference='document:'+identifier+':'+row.locator
                movement=Movement(movement_id('openbank',account,reference),account,'MXN',row.effective_date,
                    kind,row.withdrawal if outgoing else row.deposit,Evidence(identifier,row.locator),origin,transfer)
                movements.append(movement)
                plan['movements'].append(plain(movement)|dict(lane=lane,description=row.description))
            # El cero está publicado: no significa retención desconocida ni es un cargo adicional.
            zero=Movement(movement_id('openbank',account,'document:'+identifier+':isr-summary'),account,'MXN',
                preview.period_end,Kind.WITHHOLDING,preview.summary.withholding,Evidence(identifier,'resumen '+lane+': impuestos retenidos'))
            movements.append(zero);plan['movements'].append(plain(zero)|dict(lane=lane,description='ISR publicado en resumen'))
            net=_sum(m.signed_amount for m in movements if m.account==account)
            if _sum((preview.summary.initial,net))!=preview.summary.final:
                plan['issues'].append('Normalización no reconstruye el saldo final en '+lane+'.')
        if any(m.origin==Origin.UNKNOWN for m in movements):
            plan['warnings'].append('Entradas/salidas de débito sin origen acreditado quedan pendientes; no cuentan como capital externo confirmado.')
        plan['warnings'].append('Saldos iniciales guardados como anclas de cada período, sin convertirlos en aportaciones ni sumarlos entre meses.')
        plan['warnings'].append('Las referencias por documento/página/línea no prueban identidad entre PDFs; períodos superpuestos requieren revisión.')
        plan['issues']=list(dict.fromkeys(plan['issues']))
        if not plan['issues']:
            plan.update(status='ready',can_confirm=True)
        plan['state_hash']=self._state_hash()
        plan['plan_hash']=_hash(plan)
        return plan,tuple(movements)

    def _mifel_plan(self, doc, content):
        from .mifel import MifelReader
        identifier=doc['id']
        plan=dict(document_id=identifier,institution='mifel',revision=doc['revision'],status='blocked',can_confirm=False,
                  issues=[],warnings=[],periods=[],movements=[],transfers=[],payment_groups=[])
        # Las dos pestañas describen una misma cuenta remunerada, no dos cuentas.
        for lane in ('debit','investments'):
            view=doc['result']['views'].get(lane,{})
            if view.get('status')!='extracted' or view.get('mode')!='specialized':
                plan['issues'].append('Mifel requiere ambas vistas específicas de la cuenta compartida.');return plan,()
        try: preview=MifelReader('investments').read_pdf(content)
        except ValueError as error:
            plan['issues'].append(str(error));return plan,()
        if not preview.reconciled:
            plan['issues'].extend(dict.fromkeys(preview.issues+preview.detail_issues));return plan,()
        if not preview.account_fingerprint:
            plan['issues'].append('Falta identidad de la cuenta remunerada Mifel.');return plan,()
        account='mifel:'+preview.account_fingerprint
        period=dict(document_id=identifier,lane='investments',account=account,unit=preview.summary.unit,
            start=str(preview.period_start),end=str(preview.period_end),
            initial=str(preview.summary.initial),final=str(preview.summary.final),
            shared_account=True,view_lanes=['debit','investments'])
        plan['periods'].append(period)
        self._check_period(plan,period)
        movements=[];zero_interest=[]
        for row in preview.entries:
            locator=f'pagina {row.page}, linea {row.line}'
            origin=None
            if row.category=='interest_paid': kind=Kind.INTEREST;value=row.credit
            elif row.category=='withholding': kind=Kind.WITHHOLDING;value=row.debit
            elif row.category=='transfer_unmatched':
                kind=Kind.CONTRIBUTION if row.credit is not None else Kind.WITHDRAWAL
                value=row.credit if row.credit is not None else row.debit
                origin=Origin.UNKNOWN
            else:
                plan['issues'].append('Concepto Mifel sin normalización: '+locator);continue
            if value is None:
                plan['issues'].append('Importe Mifel sin columna acreditada: '+locator);continue
            if value==0 and kind==Kind.INTEREST:
                zero_interest.append(dict(reference=row.reference,effective_date=str(row.effective_date),locator=locator))
                continue
            if value==0 and kind!=Kind.WITHHOLDING:
                plan['issues'].append('Transferencia Mifel de importe cero requiere revisión: '+locator);continue
            # No se supone que un folio sea globalmente único en todos los ejercicios.
            reference='period:'+period['start']+':'+period['end']+':'+row.reference
            movement=Movement(movement_id('mifel',account,reference),account,preview.summary.unit,row.effective_date,
                kind,value,Evidence(identifier,locator),origin)
            movements.append(movement)
            plan['movements'].append(plain(movement)|dict(lane='investments',shared_account=True,
                reference=row.reference,description=row.description_printed,
                accrual_start=plain(row.accrual_start),accrual_end=plain(row.accrual_end)))
        if not any(m.kind==Kind.WITHHOLDING for m in movements) and preview.summary.withholding==0:
            zero=Movement(movement_id('mifel',account,'period:'+period['start']+':'+period['end']+':isr-summary'),
                account,preview.summary.unit,preview.period_end,Kind.WITHHOLDING,Decimal('0'),
                Evidence(identifier,'resumen cuenta remunerada: ISR retenido'))
            movements.append(zero)
            plan['movements'].append(plain(zero)|dict(lane='investments',shared_account=True,description='ISR cero publicado en resumen'))
        plan['payment_groups']=plain(preview.income_groups)
        plan['zero_interest_observations']=zero_interest
        plan['reported_terms']={key:plain(getattr(preview.summary,key)) for key in
            ('annual_rate_reported','gat_nominal','gat_real','average_balance')}
        if _sum((preview.summary.initial,*(m.signed_amount for m in movements)))!=preview.summary.final:
            plan['issues'].append('La normalización Mifel no reconstruye su cierre; no se ajusta el saldo.')
        if _sum(m.amount for m in movements if m.kind==Kind.INTEREST)!=preview.summary.gross_interest:
            plan['issues'].append('Interés Mifel normalizado no coincide con el resumen.')
        if _sum(m.amount for m in movements if m.kind==Kind.WITHHOLDING)!=preview.summary.withholding:
            plan['issues'].append('ISR Mifel normalizado no coincide con el resumen.')
        plan['warnings'].extend([
            'Débito e inversiones muestran la misma cuenta remunerada Mifel: se importa una sola vez, sin traspaso ficticio entre pestañas.',
            'El cobro conserva su fecha publicada; el rango remunerado se guarda aparte aunque alcance otro mes o un fin de semana.',
            'Interés bruto e ISR se registran por sus filas; el grupo de rendimiento neto y el resumen no generan cobros o retenciones adicionales.',
            'Las tasas/GAT son los valores históricos del estado, sin recalcular devengo ni impuesto anual.',
            'Los saldos iniciales son anclas documentales. Los períodos superpuestos se bloquean y los huecos permanecen visibles.'])
        if any(m.origin==Origin.UNKNOWN for m in movements):
            plan['warnings'].append('Aportaciones/retiros SPEI quedan con origen pendiente; no se acredita capital externo ni contrapartida propia por coincidencia de importe.')
        plan['issues']=list(dict.fromkeys(plan['issues']))
        if not plan['issues']:plan.update(status='ready',can_confirm=True)
        plan['state_hash']=self._state_hash();plan['plan_hash']=_hash(plan)
        return plan,tuple(movements)

    def _check_period(self, plan, period, label='cuenta remunerada'):
        previous=self.db.execute('SELECT start,end,initial,final FROM book_periods WHERE account=? ORDER BY start',
                                 (period['account'],)).fetchall()
        for start,end,initial,final in previous:
            if start<=period['end'] and end>=period['start']:
                plan['issues'].append('Período superpuesto en '+label+': revisar documentos antes de duplicar operaciones.')
            if date.fromisoformat(end)+timedelta(days=1)==date.fromisoformat(period['start']) and Decimal(final)!=Decimal(period['initial']):
                plan['issues'].append('Saldo inicial no coincide con cierre anterior en '+label+'.')
            if date.fromisoformat(period['end'])+timedelta(days=1)==date.fromisoformat(start) and Decimal(initial)!=Decimal(period['final']):
                plan['issues'].append('Saldo final no coincide con apertura siguiente en '+label+'.')

    def confirm(self, identifier, *, revision, plan_hash, currency_confirmation=None, password=None):
        # Bloquea cambios de la bandeja mientras se comprueba y confirma el plan.
        # Solo la base financiera se modifica: un único commit abarca todo el lote.
        with Inbox(self.inbox_path) as inbox:
            inbox.db.execute('BEGIN IMMEDIATE')
            try:
                doc=inbox.get(identifier)
                with self.store._transaction():
                    existing=self._existing(identifier)
                    if existing: return existing | dict(duplicate=True)
                    if type(revision) is not int or revision!=doc['revision']:
                        raise ValueError('Revisión desactualizada: vuelve a preparar la importación.')
                    content=inbox.original(identifier)
                    plan,movements=self._plan(doc,content,currency_confirmation=currency_confirmation,password=password)
                    if not plan['can_confirm']: raise ValueError('El plan contiene problemas pendientes; no se importó nada.')
                    if plan_hash!=plan['plan_hash']:
                        raise ValueError('El plan o el libro cambió: vuelve a preparar la importación.')
                    starts=[date.fromisoformat(p['start']) for p in plan['periods']]
                    ends=[date.fromisoformat(p['end']) for p in plan['periods']]
                    self.store.register_document(content,doc['result']['institution'],min(starts),max(ends))
                    self.store.review_document(identifier,'approved','Confirmación explícita del plan financiero '+plan_hash)
                    self.store.record_many(movements)
                    for p in plan['periods']:
                        self.db.execute('INSERT INTO book_periods VALUES(?,?,?,?,?,?,?,?)',tuple(p[k] for k in
                            ('document_id','lane','account','unit','start','end','initial','final')))
                    self.db.execute('INSERT INTO book_batches(document_id,source_revision,plan_hash,plan_json) VALUES(?,?,?,?)',
                                    (identifier,revision,plan_hash,json.dumps(plan,ensure_ascii=False)))
                return plan | dict(status='imported',can_confirm=False,duplicate=False)
            finally:
                inbox.db.rollback()  # No modifica originales ni resultados de extracción.

    def summary(self):
        ledger=self.store.load_ledger()
        accounts=[]
        for account,unit,lane in self.db.execute('SELECT DISTINCT account,unit,lane FROM book_periods ORDER BY account'):
            periods=self.db.execute('SELECT start,end,initial,final FROM book_periods WHERE account=? ORDER BY start',(account,)).fetchall()
            gaps=[]
            for previous,next_ in zip(periods,periods[1:]):
                if date.fromisoformat(previous[1])+timedelta(days=1)<date.fromisoformat(next_[0]):
                    gaps.append(dict(start=str(date.fromisoformat(previous[1])+timedelta(days=1)),end=str(date.fromisoformat(next_[0])-timedelta(days=1))))
            selected=[m for m in ledger.movements if m.account==account]
            institution=account.split(':',1)[0]
            accounts.append(dict(account=account,institution=institution,lane=lane,unit=unit,shared_account=institution in ('mifel','didi'),
                role='transit' if institution=='bancoppel' else None,
                first_period=periods[0][0],through=periods[-1][1],closing=periods[-1][3],
                periods=len(periods),gaps=gaps,
                interest=str(_sum(m.amount for m in selected if m.kind==Kind.INTEREST)),
                withholding=str(_sum(m.amount for m in selected if m.kind==Kind.WITHHOLDING)),
                interest_net_of_withholding=str(_sum(m.signed_amount for m in selected if m.kind in (Kind.INTEREST,Kind.WITHHOLDING))),
                charges_fees_and_vat=str(_sum(m.amount for m in selected if m.kind==Kind.FEE)),
                pending_origins=sum(m.origin==Origin.UNKNOWN for m in selected)))
        return dict(accounts=accounts,documents=self.db.execute('SELECT COUNT(*) FROM book_batches').fetchone()[0],
            movements=len(ledger.movements),note='Cierres documentales por cuenta y fecha; intereses y retenciones de períodos importados. No acredita historia completa ni saldo actual de mercado.')
