"""Evolución por períodos documentados, sobre la última versión del libro local."""
from datetime import date, timedelta
from decimal import Decimal
import json

from .intake import plain
from .ledger import Kind, Origin, _sum


def report(book):
    # Todas las lecturas pertenecen a la misma instantánea SQLite. No escribe datos.
    nested=book.db.in_transaction
    if not nested:book.db.execute('BEGIN')
    try:return _report(book)
    finally:
        if not nested:book.db.rollback()


def _report(book):
    ledger=book.store.load_ledger()
    current={m.id:m for m in ledger.movements}
    batches={identifier:json.loads(payload) for identifier,payload in book.db.execute(
        'SELECT document_id,plan_json FROM book_batches')}
    pending=set(ledger.pending_transfers())
    assigned=set();accounts=[]
    for account in book.summary()['accounts']:
        history=[];previous=None
        for doc,start,end,initial,final in book.db.execute(
            'SELECT document_id,start,end,initial,final FROM book_periods WHERE account=? AND unit=? ORDER BY start',
            (account['account'],account['unit'])):
            batch=batches[doc]
            selected=[m for m in ledger.movements if m.account==account['account'] and m.unit==account['unit']
                      and start<=m.effective_date.isoformat()<=end]
            assigned.update(m.id for m in selected)
            expected={m['id']:m for m in batch['movements'] if m['account']==account['account'] and m['unit']==account['unit']}
            changed=[]
            for identifier,original in expected.items():
                latest=plain(current[identifier]) if identifier in current else None
                if latest is None or any(latest[key]!=original.get(key) for key in latest):changed.append(identifier)
            extra=[m.id for m in selected if m.id not in expected]
            def total(kinds):return _sum(m.signed_amount for m in selected if m.kind in kinds)
            def capital(kind,origins=None):
                return _sum(m.amount for m in selected if m.kind==kind and (origins is None or m.origin in origins))
            interest=total((Kind.INTEREST,Kind.INTEREST_REVERSAL))
            retained=[m.signed_amount.copy_negate() for m in selected if m.kind in (Kind.WITHHOLDING,Kind.WITHHOLDING_REFUND)]
            tax=_sum(retained) if retained else None
            tax_known=bool(retained) and batch.get('withholding_status')!='unknown'
            interest_known=batch.get('interest_status')!='unknown'
            change=_sum(m.signed_amount for m in selected)
            calculated=_sum((Decimal(initial),change))
            difference=_sum((calculated,Decimal(final).copy_negate()))
            gap=None;boundary=None
            if previous:
                next_day=date.fromisoformat(previous['end'])+timedelta(days=1)
                if next_day<date.fromisoformat(start):gap=dict(start=str(next_day),end=str(date.fromisoformat(start)-timedelta(days=1)))
                elif next_day==date.fromisoformat(start):boundary=str(_sum((Decimal(initial),Decimal(previous['final']).copy_negate())))
            issues=[]
            if difference:issues.append('El libro vigente no concilia con el cierre documental.')
            if changed or extra:issues.append('Los movimientos vigentes difieren del lote confirmado; revisa la evidencia.')
            if boundary is not None and Decimal(boundary):issues.append('La apertura difiere del cierre contiguo anterior.')
            history.append(dict(document_id=doc,source_revision=batch['revision'],start=start,end=end,initial=initial,final=final,
                calculated_final=str(calculated),closing_difference=str(difference),cash_change=str(change),
                contributions=str(capital(Kind.CONTRIBUTION)),withdrawals=str(capital(Kind.WITHDRAWAL)),
                external_contributions=str(capital(Kind.CONTRIBUTION,(Origin.EXTERNAL,Origin.CASHBACK))),
                cashback_contributions=str(capital(Kind.CONTRIBUTION,(Origin.CASHBACK,))),
                own_transfer_in=str(capital(Kind.CONTRIBUTION,(Origin.OWN_TRANSFER,))),
                own_transfer_out=str(capital(Kind.WITHDRAWAL,(Origin.OWN_TRANSFER,))),
                reinvestment_in=str(capital(Kind.CONTRIBUTION,(Origin.REINVESTMENT,))),
                reinvestment_out=str(capital(Kind.WITHDRAWAL,(Origin.REINVESTMENT,))),
                interest=str(interest) if interest_known else None,interest_documented=str(interest),
                withholding=str(tax) if tax_known else None,withholding_documented=str(tax) if tax is not None else None,
                interest_net_of_withholding=str(_sum((interest,tax.copy_negate()))) if interest_known and tax_known else None,
                dividends=str(total((Kind.DIVIDEND,))),foreign_withholding=str(total((Kind.FOREIGN_WITHHOLDING,)).copy_negate()),
                security_proceeds=str(total((Kind.SECURITY_PROCEEDS,))),
                vat_received=str(total((Kind.VAT_RECEIVED,Kind.VAT_RECEIVED_REVERSAL))),
                vat_paid=str(total((Kind.VAT_PAID,Kind.VAT_REFUND)).copy_negate()),
                fees=str(total((Kind.FEE,Kind.FEE_REFUND)).copy_negate()),rewards=str(total((Kind.REWARD,))),
                movements=len(selected),pending_origins=sum(m.origin==Origin.UNKNOWN for m in selected),
                pending_transfer_ids=sorted({m.transfer_id for m in selected if m.transfer_id in pending}),
                changed_movement_ids=sorted(changed),additional_movement_ids=sorted(extra),
                gap_before=gap,boundary_difference=boundary,issues=issues,reconciled=not issues))
            previous=history[-1]
        accounts.append({k:account[k] for k in ('account','institution','unit','lane','role','portfolio','shared_account')}|dict(history=history))
    unassigned=[plain(m) for m in ledger.movements if m.id not in assigned]
    return dict(accounts=accounts,unassigned_movements=unassigned,
        note='Períodos internos de documentos confirmados, no meses reconstruidos. Cada cuenta y moneda se mantiene separada. Aperturas no son aportaciones; cambios de saldo no son rendimiento. Retenciones no son el ISR anual definitivo. Huecos y revisiones no se ajustan automáticamente.')
