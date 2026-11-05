"""Fictitious Plata products, signed continuations, cashback and cutoff."""
from decimal import Decimal as D
from datetime import date
import unittest
from dataclasses import replace
from finanzas.plata import PlataReader
from finanzas.readers import reader_for,ReaderError
from tests.test_openbank import synthetic_pdf

A='111111111111111111';B='222222222222222222'
HEADER=f'{"Fecha de operación":<25}{"Fecha de cargo":<25}{"Descripción":<40}{"Moneda":<15}{"Tipo de Cambio":<15}{"Referencia":<17}Monto'


def row(op,post,desc,amount):return f'{op:<25}{post:<25}{desc:<40}{"MXN":<15}{"1.00":<15}{"—":<17}{amount}'


def source():
    debit=f'''Banco Plata
No. de Cuenta: 000111222
Periodo 01 abr 2026 al 30 abr 2026
Plata Cuenta CLABE: {A}
Saldo anterior $0.00
Retiros $0.00
Comisiones $0.00
IVA retenido $0.00
Otros cargos −$10.00
Depósitos y rendimientos $10.00
ISR retenido $0.00
Saldo final $0.00
Tasa bruta de interés 7%
Rendimientos $0.00
Comportamiento
Saldo anterior $0.00
'''
    savings=f'''Ahorro Flexible CLABE: {B}
Saldo anterior $100.00
Retiros $0.00
Comisiones $0.00
IVA retenido $0.00
Depósitos y rendimientos $21.00
ISR retenido −$0.20
Saldo final $120.80
Tasa bruta de interés 12%
Rendimientos $2.00
Total
Saldo anterior $100.00
Retiros $0.00
Comisiones $0.00
IVA retenido $0.00
Otros cargos −$10.20
Depósitos y rendimientos $31.00
ISR retenido −$0.20
Saldo final $120.80
'''
    movements=f'Movimientos de Plata Cuenta CLABE: {A}\n{HEADER}\n'
    movements+=row('20 abr 2026','20 abr 2026','Cashback','$10.00')+'\n'
    movements+=row('20 abr 2026','20 abr 2026','Transferencia entre','−')+'\n'
    movements+=' '*50+f'{"cuentas propias":<87}$10.00\n'
    movements+=f'Movimientos de Ahorro Flexible CLABE: {B}\n{HEADER}\n'
    movements+=row('15 abr 2026','15 abr 2026','Pago por','$9.00')+'\n'+' '*50+'transferencia SPEI\n'
    movements+=row('20 abr 2026','20 abr 2026','Depósito desde','$10.00')+'\n'+' '*50+'cuenta propia\n'
    movements+=row('01 may 2026','01 may 2026','Impuestos','−$0.20')+'\n'+' '*50+'Retenidos (ISR)\n'
    movements+=row('01 may 2026','01 may 2026','Rendimientos','$2.00')+'\n'
    annex='Comprobante fiscal\nServicios de facturación $0.01\nSubtotal $0.01\nTotal $0.00\n'
    return [debit,savings,movements,annex]


def read(pages=None,lane='investments'):return PlataReader(lane).read_pages(pages or source(),'fictitious')


class PlataTests(unittest.TestCase):
    def test_two_products_distinct_identities_one_relationship(self):
        a=read();b=read(lane='debit')
        self.assertNotEqual(a.account_fingerprint,b.account_fingerprint)
        self.assertEqual(a.relationship_fingerprint,b.relationship_fingerprint)
        self.assertEqual(len(a.entries),4);self.assertEqual(len(b.entries),2)
        self.assertFalse(a.ready_to_import)

    def test_split_negative_amount_and_description_are_preserved(self):
        r=read();out=r.debit.rows[1]
        self.assertEqual(out.amount,D('-10'))
        self.assertEqual(out.description,'Transferencia entre cuentas propias')
        self.assertEqual(out.category,'own_transfer_out')

    def test_cashback_is_contribution_origin_not_interest(self):
        r=read();cashback=r.debit.rows[0]
        self.assertEqual(cashback.category,'cashback_contribution')
        self.assertEqual(r.debit.summary.gross_income_reported,D('0.00'))
        self.assertEqual(len(r.transfer_candidates),1)
        self.assertEqual(r.transfer_candidates[0].cashback_origin_candidate,cashback.evidence_id)
        self.assertEqual(r.transfer_candidates[0].status,'candidate_requires_review')

    def test_aggregate_isr_not_subtracted_twice(self):
        r=read()
        self.assertTrue(r.summary_reconciled)
        self.assertEqual(r.aggregate_isr_basis,'arithmetic_included_in_other_charges')
        self.assertEqual(r.aggregate.final,D('120.80'))
        self.assertEqual(r.aggregate.isr_withheld_printed,D('-0.20'))

    def test_deposits_include_interest_without_new_extra_credit(self):
        r=read();self.assertEqual(r.summary.deposits_and_income,D('21.00'))
        self.assertEqual(sum(e.amount for e in r.rows if e.amount>0),D('21.00'))
        self.assertEqual(sum(e.amount for e in r.rows),D('20.80'))

    def test_booking_after_cutoff_not_moved_to_statement_end(self):
        r=read();e=r.rows[-1]
        self.assertEqual(r.period_end,date(2026,4,30))
        self.assertEqual(e.operation_date,date(2026,5,1))
        self.assertEqual(e.posting_date,date(2026,5,1))
        self.assertTrue(e.outside_period)
        self.assertTrue(r.summary_reconciled)
        self.assertFalse(r.reconciled)
        self.assertTrue(read(lane='debit').reconciled)

    def test_invoice_not_converted_to_bank_fee(self):
        r=read();self.assertEqual(r.annex_pages,(4,))
        self.assertEqual(len(r.rows),4)
        self.assertEqual(r.summary.commissions_printed,D('0'))

    def test_missing_reference_is_unknown_and_same_amount_rows_remain_distinct(self):
        s=source();line=row('15 abr 2026','15 abr 2026','Pago por','$9.00')
        s[2]=s[2].replace(line+'\n'+' '*50+'transferencia SPEI',2*(line+'\n'+' '*50+'transferencia SPEI\n'))
        r=read(s);matches=[e for e in r.rows if e.amount==D('9')]
        self.assertEqual(len(matches),2)
        self.assertTrue(all(e.reference is None for e in matches))
        self.assertNotEqual(matches[0].evidence_id,matches[1].evidence_id)
        self.assertFalse(r.summary_reconciled)

    def test_ambiguous_transfer_not_paired_arbitrarily(self):
        s=source();line=row('20 abr 2026','20 abr 2026','Depósito desde','$10.00')+'\n'+' '*50+'cuenta propia\n'
        s[2]=s[2].replace(line,line+line)
        self.assertEqual(read(s).transfer_candidates,())

    def test_unknown_currency_or_concept_stays_pending(self):
        for old,new in [('MXN','USD'),('Pago por','Otro concepto')]:
            r=read([p.replace(old,new) for p in source()])
            self.assertFalse(r.reconciled)
            self.assertTrue(r.issues)

    def test_contradictory_clabe_missing_summary_or_bad_row_rejected(self):
        s=source();s[2]=s[2].replace('CLABE: '+B,'CLABE: '+A)
        with self.assertRaises(ReaderError):read(s)
        with self.assertRaises(ReaderError):read(source()[1:])
        s=source();s[2]=s[2].replace('1.00','NoFx')
        with self.assertRaises(ReaderError):read(s)

    def test_zero_isr_does_not_imply_a_distinguishable_aggregate_basis(self):
        s=source();s=[p.replace('−$0.20','$0.00').replace('−$10.20','−$10.00').replace('$120.80','$121.00') for p in s]
        r=read(s)
        self.assertEqual(r.aggregate_isr_basis,'indistinguishable_zero_retention')
        self.assertEqual(r.summary.isr_withheld_printed,D('0'))

    def test_continuation_header_is_not_a_malformed_movement(self):
        pages=source()
        pages[1]+='\n  01 abr 2026 — 30 abr 2026 (30 días)   No. de Cuenta:\n'
        r=read(pages)
        self.assertTrue(r.summary_reconciled)

    def test_pdf_catalog_end_to_end(self):
        r=reader_for('plata','investments').read_reconciled_pdf(synthetic_pdf([p.replace('−','-') for p in source()]))
        self.assertEqual(r.period_start,date(2026,4,1))
        self.assertTrue(r.summary_reconciled)
        self.assertEqual(len(r.transfer_candidates),1)


if __name__=='__main__':unittest.main()
