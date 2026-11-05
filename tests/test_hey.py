"""Hey ficticio: cobros, devengo y proyección al vencimiento no son lo mismo."""
from decimal import Decimal as D
from datetime import date
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from finanzas.hey import HeyReader
from finanzas.readers import ReaderError, reader_for, main
from tests.test_openbank import synthetic_pdf


def row(category, reference, debit=None, credit=None, balance="0.00"):
    description = f"10  {('TRA' if 'ISR' in category else 'DOC')} {reference}-{category}"
    return description.ljust(100) + (debit or "").rjust(15) + " "*15 + (credit or "").rjust(15) + " "*15 + balance.rjust(15)


def pages():
    reference="888888880000101"
    first="""Hey, Banco
ESTADO DE CUENTA UNICO del 01 al 30 de NOVIEMBRE 2024
Inversiones
Saldo Anterior  Intereses  Saldo Actual  Intereses Devengados  ISR  %
1002.00  4.00  1005.00  1.00  1.00  100.00
* Los intereses devengados están considerados en su Saldo Actual
Total Portafolio 1005.00
"""
    second="""Hey, Banco
del 01 al 30 de NOVIEMBRE 2024
CUENTA HEY
CLABE 111111111111111111
"""
    second += "DIA CONCEPTO".ljust(100)+"CARGOS".ljust(30)+"ABONOS".ljust(30)+"SALDO\n"
    second += "\n".join((
        row("Pago Cap. de Inversion",reference,credit="1000.00",balance="1000.00"),
        row("Pago Intereses de Inv.",reference,credit="5.00",balance="1005.00"),
        row("Ret. ISR de Inversion",reference,debit="1.00",balance="1004.00"),
        row("Apertura de Inversion Hey PER: 1","888888880000102",debit="1004.00",balance="0.00")))
    second += """
Gráfico Transaccional
Saldo Inicial $0.00
+ Abonos $1005.00
- Retiros $0.00
- Comisiones Efectivamente Cobradas $0.00
- Otros Cargos $1005.00
= Saldo Final $0.00
MANDATO ESPECIAL
"""
    third="""Hey, Banco
del 01 al 30 de NOVIEMBRE 2024
INVERSION TASA COMISION GAT NOMINAL GAT REAL
0000101  6.00%  0.00  6.20%  Antes de impuestos  2.00%  Antes de impuestos
0000102  5.00%  0.00  5.10%  Antes de impuestos  1.00%  Antes de impuestos
CAPITAL + INTERES - ISR = TOTAL INVERSION
13/Oct/2024 0000101 6.00% 28 1000.00 5.00 1.00 1004.00 10/Nov/2024
10/Nov/2024 0000102 5.00% 28 1004.00 4.00 1.00 1007.00 08/Dic/2024
Inversiones Vigentes Total Vigentes 1007.00
"""
    return [first,second,third]


def parsed(source=None,lane="investments"):
    return HeyReader(lane).read_pages(source or pages(),"synthetic")


class HeyTests(unittest.TestCase):
    def test_cash_contracts_and_projection_reconcile_without_import(self):
        r=parsed()
        self.assertTrue(r.reconciled,(r.issues,r.detail_issues))
        self.assertEqual(len(r.entries),4)
        self.assertEqual(len(r.contracts),2)
        self.assertFalse(r.ready_to_import)

    def test_net_reported_interest_does_not_become_gross_then_taxed_again(self):
        r=parsed()
        self.assertEqual(r.investment_summary.interest_reported,D("4.00"))
        self.assertEqual(r.entries[1].credit,D("5.00"))
        self.assertEqual(r.entries[2].debit,D("1.00"))
        self.assertTrue(r.reconciled)

    def test_accrued_and_future_interest_not_counted_as_received(self):
        r=parsed()
        active=next(c for c in r.contracts if c.status_at_cutoff=="active")
        self.assertEqual(r.investment_summary.accrued_included_in_final,D("1.00"))
        self.assertEqual(active.interest_at_maturity,D("4.00"))
        self.assertEqual(active.withholding_at_maturity,D("1.00"))
        self.assertEqual(sum(e.debit for e in r.entries if e.category=="withholding"),D("1.00"))
        self.assertEqual([e.contract_id for e in r.entries if e.category=="interest_paid"],["0000101"])

    def test_reinvestment_is_pending_proposal_with_four_source_rows(self):
        r=parsed();renewal=r.renewal_proposals[0]
        self.assertTrue(renewal.needs_review)
        self.assertEqual(renewal.previous_contract,"0000101")
        self.assertEqual(renewal.next_contract,"0000102")
        self.assertEqual(renewal.reinvested,D("1004.00"))
        self.assertEqual(len(renewal.source_lines),4)

    def test_one_cent_projected_total_difference_does_not_poison_debit_view(self):
        source=pages();source[2]=source[2].replace("Total Vigentes 1007.00","Total Vigentes 1006.99")
        investment=parsed(source);debit=parsed(source,"debit")
        self.assertFalse(investment.reconciled)
        self.assertTrue(debit.reconciled)
        self.assertEqual(investment.differences[-1].reported,D("1006.99"))
        self.assertEqual(investment.differences[-1].calculated,D("1007.00"))

    def test_portfolio_total_is_checked_without_counting_projected_maturity(self):
        source=pages();source[0]=source[0].replace("Total Portafolio 1005.00","Total Portafolio 1004.99")
        r=parsed(source)
        self.assertFalse(r.reconciled)
        self.assertEqual(r.portfolio_total_reported,D("1004.99"))
        self.assertEqual(r.investment_summary.current_contract_total_reported,D("1007.00"))

    def test_reused_contract_reference_has_distinct_economic_categories(self):
        r=parsed()
        self.assertEqual(len(set(e.reference for e in r.entries[:3])),1)
        self.assertEqual(len(set(e.category for e in r.entries[:3])),3)
        self.assertTrue(r.reconciled)

    def test_duplicate_reference_category_is_retained_and_blocks_renewal(self):
        source=pages();extra=next(l for l in source[1].splitlines() if "Pago Cap." in l)
        source[1]=source[1].replace("Gráfico Transaccional",extra+"\nGráfico Transaccional")
        r=parsed(source)
        self.assertEqual(len(r.entries),5)
        self.assertFalse(r.detail_reconciled)
        self.assertEqual(r.renewal_proposals,())

    def test_cash_balance_or_unknown_category_remains_pending(self):
        for original,replacement in (("Pago Intereses de Inv.","Abono desconocido"),("1005.00\n10", "1004.99\n10")):
            source=pages();source[1]=source[1].replace(original,replacement)
            r=parsed(source)
            self.assertFalse(r.detail_reconciled)
            self.assertEqual(r.renewal_proposals,())

    def test_historical_terms_gat_and_dates_are_preserved_per_contract(self):
        r=parsed();a,b=r.contracts
        self.assertEqual(a.annual_rate,D("6.00"))
        self.assertEqual(b.annual_rate,D("5.00"))
        self.assertEqual(b.gat_real,D("1.00"))
        self.assertEqual(b.days,28)
        self.assertEqual(b.maturity,date(2024,12,8))
        self.assertEqual(a.source_extraction,"plain")
        self.assertEqual(r.entries[0].source_extraction,"layout")

    def test_dates_or_rate_contradiction_fails_closed(self):
        for original,replacement in (("08/Dic/2024","09/Dic/2024"),("0000102 5.00% 28","0000102 4.00% 28")):
            source=pages();source[2]=source[2].replace(original,replacement)
            with self.assertRaises(ReaderError):parsed(source)

    def test_missing_identity_summary_or_contract_raises(self):
        for field in ("Hey, Banco","CLABE","Gráfico Transaccional","Total Vigentes"):
            with self.assertRaises(ReaderError):parsed([p.replace(field,"Ausente") for p in pages()])

    def test_contract_paid_amount_mismatch_preserves_both_amounts(self):
        source=pages();source[2]=source[2].replace("1000.00 5.00 1.00 1004.00","1000.00 5.01 1.00 1004.01")
        r=parsed(source)
        self.assertTrue(r.detail_reconciled)
        self.assertFalse(r.reconciled)
        self.assertEqual(r.entries[1].credit,D("5.00"))
        self.assertEqual(r.contracts[0].interest_at_maturity,D("5.01"))

    def test_pdf_catalog_lanes_and_private_default_console(self):
        content=synthetic_pdf(pages())
        a=reader_for("hey","debit").read_reconciled_pdf(content)
        b=reader_for("hey","investments").read_reconciled_pdf(content)
        self.assertTrue(a.reconciled,(a.issues,a.detail_issues))
        self.assertTrue(b.reconciled,(b.issues,b.detail_issues))
        self.assertIsNot(a.summary,b.summary)
        self.assertEqual(a.entries,b.entries)
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"synthetic.pdf";p.write_bytes(content);out=StringIO()
            with contextlib.redirect_stdout(out):main([str(p),"--institution","hey","--lane","investments","--reconcile"])
            self.assertTrue(json.loads(out.getvalue())["reconciled"])
            self.assertNotIn("1004.00",out.getvalue())


if __name__=="__main__":unittest.main()
