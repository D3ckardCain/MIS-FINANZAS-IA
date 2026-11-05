"""Kapital ficticio: cambio de formato, proyecciones y timbrado compensado."""
from decimal import Decimal as D
from dataclasses import replace
from datetime import date
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from finanzas.kapital import KapitalReader,review_kapital_documents
from finanzas.readers import ReaderError,reader_for,main
from tests.test_openbank import synthetic_pdf


def legacy():
    first="""KAPITAL
Período 01-Ago-2025 al 31-Ago-2025
CLABE 111111111111111111
RESUMEN DEL PERIODO
(+) Saldo Inicial $ 0.00
(+) Depósitos en Efectivo $ 0.00
(+) Depósitos de Cheques $ 0.00
(+) Transferencias Recibidas $ 1000.00
(+) Otros Abonos a su Cuenta $ 0.00
(+) Intereses Ganados $ 0.00
(-) Retiros Efectivo Sucursal y Cajeros Automaticos $ 0.00
(-) Cheques Cobrados $ 0.00
(-) Transferencias Enviadas $ 0.00
(-) Otros Cargos a su Cuenta $ 0.00
(-) I.V.A. Cobrado $ 0.00
(-) Retenciones de I.S.R. $ 0.00
(-) Saldo Final $ 0.00
(-) Comisiones Cobradas $ 0.00
(-)Compras en Establecimientos $ 0.00
Saldo al Inicio $ 0.00
( - ) Movimientos del Mes $ 0.00
(+) Movimientos del Mes $ 1000.00
Saldo al Final $ 1000.00
DETALLE DE INVERSIONES (MONEDA NACIONAL)
LD0001  PAGARÉ FICTICIO  360 DIAS  06-Ago-2025  01-Ago-2026  $ 1000.00  10 %  10.00 %  6.00 %  $ 100.00
DETALLE DE MOVIMIENTOS (MONEDA NACIONAL)
06-Ago-2025  TRANSFERENCIA RECIBIDA  FT0001  $ 1000.00  $ 0.00  $ 1000.00
06-Ago-2025  APERTURA PAGARÉ  LD0001  $ 0.00  $ -1000.00  $ 0.00
"""
    return [first]


def current(month=7):
    matured=month==8
    def cashrow(day,ref,description,credit=None,debit=None,balance="0.00"):
        return (f'{day}  {ref}  {description}'.ljust(116)+(credit or '').rjust(18)+(debit or '').rjust(20)+balance.rjust(20))
    head="PRODUCTOS".ljust(30)+"SALDO/VALOR".ljust(23)+"INTERESES".ljust(17)+"COMISIONES".ljust(15)+"IVA".ljust(10)+"SALDO/VALOR".ljust(22)+"%".ljust(13)+"SALDO".ljust(20)+"ISR"
    principal_final="2000.00" if matured else "3000.00"
    portfolio="PAGARE (3)".ljust(30)+"3000.00".rjust(14)
    portfolio=portfolio.ljust(95)+principal_final.rjust(14)
    first=f"""KAPITAL
Período DEL 2026-{month:02}-01 AL 2026-{month:02}-31
CLABE 111111111111111111
{head}
{portfolio}
CUENTA DE CHEQUES
Saldo Inicial 0.00 MN
+ Depósitos {'1100.01' if matured else '0.01'} MN
- Retiros {'10.01' if matured else '0.01'} MN
+ Intereses Brutos Cheques 0.00
- I.S.R. Retenido Cheques 0.00
+ Intereses Brutos de Inversiones {'100.00' if matured else '0.00'}
vencidas
- I.S.R. Retenido de Inversiones {'10.00' if matured else '0.00'}
vencidas
- Comisiones Efectivamente 0.00
Cobradas
Saldo Final {'1090.00' if matured else '0.00'}
Saldo mínimo requerido 0.00
"""
    first += "DÍA  FOLIO  CONCEPTO".ljust(116)+"DEPÓSITOS".ljust(20)+"RETIROS".ljust(20)+"SALDO\n"
    rows=[]
    if matured:
        rows += [cashrow(1,"100001","PAGO CAP. DE INVERSIÓN",credit="1000.00",balance="1000.00"),
                 cashrow(1,"100001","PAGO INTERESES DE INV.",credit="100.00",balance="1100.00"),
                 cashrow(1,"100001","RET. ISR DE INVERSIÓN",debit="10.00",balance="1090.00")]
    rows += [cashrow(31,"100002","COMISIÓN POR TIMBRADO FISCAL",debit="0.01",balance="1089.99" if matured else "0.01-"),
             cashrow(31,"100002","DESCUENTO POR TIMBRADO FISCAL",credit="0.01",balance="1090.00" if matured else "0.00")]
    first += '\n'.join(rows)+"\nTotal\nINVERSIÓN A PLAZO\n"
    second="Pagarés Vigentes\n"
    def contract(key,principal,opened,maturity,interest,tax,net):
        return f"""GAT 10.00% NOMINAL ANTES DE IMPUESTOS  GAT REAL 6.10%  Moneda MN  No. de Inversión {key}
TASA BRUTA CAPITAL INICIO VENCIMIENTO DÍAS TASA NETA INTERÉS ISR TOTAL NETO
10.0000%  {principal}  {opened}  {maturity}  360  9.0000  {interest}  {tax}  {net}
Total Vigentes {net}
"""
    if not matured:second+=contract("11111100026001","1000.00","2025-08-06","2026-08-01","100.00","10.00","1090.00")
    second+=contract("11111100026002","2000.00","2025-11-01","2026-10-27","200.00","20.00","2180.00")
    return [first,second]


def read(source=None):return KapitalReader().read_pages(source or current(),"synthetic")


class KapitalTests(unittest.TestCase):
    def test_legacy_investment_opening_reduces_cash_without_external_withdrawal(self):
        r=read(legacy())
        self.assertTrue(r.reconciled,(r.cash_issues,r.investment_issues))
        self.assertEqual(r.cash_summary.investment_principal_outflow,D("1000.00"))
        self.assertEqual(r.entries[1].category,"investment_opening")
        self.assertEqual(r.entries[1].withdrawal_printed,D("-1000.00"))
        self.assertEqual(r.entries[1].debit,D("1000.00"))

    def test_legacy_forecast_retention_and_net_are_unknown_not_zero(self):
        r=read(legacy());c=r.contracts[0]
        self.assertIsNone(c.retention_at_maturity)
        self.assertIsNone(c.net_at_maturity)
        self.assertEqual(c.interest_at_maturity,D("100.00"))
        self.assertEqual(r.cash_summary.interest_component,D("0.00"))

    def test_timbrado_charge_and_discount_same_folio_are_both_preserved(self):
        r=read()
        self.assertTrue(r.reconciled,(r.cash_issues,r.investment_issues))
        self.assertEqual(len(r.entries),2)
        self.assertEqual(r.entries[0].reference,r.entries[1].reference)
        self.assertEqual(r.entries[0].category,"stamp_fee")
        self.assertEqual(r.entries[1].category,"stamp_discount")
        self.assertEqual(r.cash_summary.commissions_reported,D("0.00"))
        self.assertEqual(r.entries[0].debit,D("0.01"))

    def test_trailing_negative_balance_is_a_real_intermediate_balance(self):
        r=read()
        self.assertEqual(r.entries[0].balance,D("-0.01"))
        self.assertEqual(r.entries[1].balance,D("0.00"))
        self.assertTrue(r.detail_reconciled)

    def test_maturity_components_are_already_in_deposits_withdrawals(self):
        r=read(current(8))
        self.assertTrue(r.reconciled,(r.cash_issues,r.investment_issues))
        self.assertEqual(r.cash_summary.final,D("1090.00"))
        self.assertEqual(r.cash_summary.investment_interest_component,D("100.00"))
        self.assertEqual(r.cash_summary.investment_retention_component,D("10.00"))
        self.assertEqual(r.investment_summary.final,D("2000.00"))

    def test_future_interest_and_retention_are_not_current_cash(self):
        r=read()
        self.assertEqual(r.contracts[0].retention_at_maturity,D("10.00"))
        self.assertEqual(r.cash_summary.investment_retention_component,D("0.00"))
        self.assertFalse(any(e.category=="interest_paid" for e in r.entries))
        self.assertFalse(r.ready_to_import)

    def test_contract_id_change_creates_proposal_without_replacing_identifiers(self):
        old=read(legacy());new=replace(read(),document_id="new")
        review=review_kapital_documents([old,new])
        proposal=review.contract_alias_proposals[0]
        self.assertEqual(proposal.previous_id,"LD0001")
        self.assertEqual(proposal.next_id,"11111100026001")
        self.assertTrue(proposal.needs_review)
        self.assertEqual(old.contracts[0].id,"LD0001")

    def test_repeated_snapshots_yield_one_maturity_proposal(self):
        first=replace(read(),document_id="first")
        second=replace(first,document_id="copy-version")
        paid=replace(read(current(8)),document_id="paid")
        review=review_kapital_documents([first,second,paid,paid])
        self.assertEqual(len(review.maturity_proposals),1)
        self.assertTrue(review.maturity_proposals[0].matches_forecast)
        self.assertTrue(review.maturity_proposals[0].needs_review)
        self.assertEqual(len(review.cash_coverage.duplicate_documents),1)

    def test_changed_forecast_retention_does_not_overwrite_payment(self):
        before=read();changed=replace(before.contracts[0],retention_at_maturity=D("9.00"))
        before=replace(before,document_id="forecast",contracts=(changed,before.contracts[1]))
        paid=replace(read(current(8)),document_id="paid")
        review=review_kapital_documents([before,paid]);proposal=review.maturity_proposals[0]
        self.assertFalse(proposal.matches_forecast)
        self.assertEqual(proposal.forecast_retention,D("9.00"))
        self.assertEqual(proposal.retention_paid,D("10.00"))

    def test_one_cent_contract_net_difference_stays_pending(self):
        source=current();source[1]=source[1].replace("1090.00","1089.99")
        r=read(source)
        self.assertFalse(r.reconciled)
        self.assertTrue(r.detail_reconciled)
        self.assertEqual(r.contracts[0].net_at_maturity,D("1089.99"))

    def test_repeated_reference_category_is_not_deleted(self):
        source=current();row=next(l for l in source[0].splitlines() if "COMISIÓN POR" in l)
        source[0]=source[0].replace("\nTotal\n","\n"+row+"\nTotal\n")
        r=read(source)
        self.assertEqual(len(r.entries),3)
        self.assertFalse(r.detail_reconciled)

    def test_missing_table_is_not_treated_as_empty_activity(self):
        source=legacy();source[0]=source[0].split("DETALLE DE MOVIMIENTOS (MONEDA NACIONAL)")[0]
        self.assertFalse(read(source).detail_reconciled)

    def test_missing_identity_account_summary_or_footer_fails_closed(self):
        for marker in ("KAPITAL","CLABE","CUENTA DE CHEQUES","Total Vigentes"):
            with self.assertRaises(ReaderError):
                read([p.replace(marker,"Ausente") for p in current()])

    def test_dates_and_historical_rate_preserved_per_contract(self):
        r=read();c=r.contracts[0]
        self.assertEqual(c.days,360)
        self.assertEqual(c.annual_rate,D("10.0000"))
        self.assertEqual(c.opened,date(2025,8,6))
        self.assertEqual(c.maturity,date(2026,8,1))
        self.assertEqual(c.net_rate_reported,D("9.0000"))

    def test_unknown_concept_is_pending_without_fictitious_adjustment(self):
        source=current();original="COMISIÓN POR TIMBRADO FISCAL"
        source[0]=source[0].replace(original,"OTRO CARGO".ljust(len(original)))
        r=read(source)
        self.assertFalse(r.detail_reconciled)
        self.assertEqual(len(r.entries),2)

    def test_pdf_catalog_views_and_private_default_console(self):
        content=synthetic_pdf(current())
        debit=reader_for("kapital","debit").read_reconciled_pdf(content)
        investment=reader_for("kapital","investments").read_reconciled_pdf(content)
        self.assertTrue(debit.reconciled,(debit.cash_issues,debit.investment_issues))
        self.assertTrue(investment.reconciled)
        self.assertEqual(debit.contracts,investment.contracts)
        self.assertIsNot(debit.summary,investment.summary)
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"synthetic.pdf";p.write_bytes(content);out=StringIO()
            with contextlib.redirect_stdout(out):main([str(p),"--institution","kapital","--lane","investments","--reconcile"])
            self.assertTrue(json.loads(out.getvalue())["reconciled"])
            self.assertNotIn("1090.00",out.getvalue())


if __name__=="__main__":unittest.main()
