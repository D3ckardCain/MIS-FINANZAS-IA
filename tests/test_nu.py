"""Nu ficticio: resumen conciliado no significa subcuentas importables."""
from decimal import Decimal as D
from dataclasses import replace
from datetime import date
import unittest

from finanzas.nu import NuReader
from finanzas.coverage import review_coverage
from finanzas.readers import reader_for,ReaderError
from tests.test_openbank import synthetic_pdf


def statement(guarantee=True):
    header='En su Cuenta  Total Cajitas'+('  Crédito con garantía' if guarantee else '')
    pools='$5.00  $125.00'+('  $0.00' if guarantee else '')
    return [f"""Nu México Financiera
Saldo inicial $100.00
Depósitos +$50.00
Gastos -$22.00
Comisiones cobradas por Nu $0.00
Dinero generado este mes $2.00
Saldo al generar este estado de cuenta $130.00
Cómo está organizado tu dinero
{header}
{pools}
Disponible 24/7 $25.00
Congelado $100.00
""", """Cuenta Nu: 00011111111
Detalle de movimientos en tu cuenta
FECHA DEL 01 AL 31 ENE 2026 (31 DÍAS)
05 ENE 2026 Depósito en Cajita: FICTICIA -$50.00
05 ENE 2026 Depósito SPEI +$50.00
Nu México Financiera
""", """Cuenta Nu: 00011111111
Detalle de movimientos de tus cajitas
05 ENE 2026 Depósito en Cajita: FICTICIA +$50.00
05 ENE 2026 Congelaste saldo hasta el 05 ABR 2026 en tu Cajita: FICTICIA +$100.00
Nu México Financiera
""", """DINERO GENERADO EN TU CUENTA NU DEL 01 AL 31 ENE 2026 (31 DÍAS)
Dinero generado antes de impuestos (Interés Bruto Anual de 8.3%) $2.10
Impuestos sobre el dinero generado (ISR de 0.9%) -$0.10
Dinero generado este mes $2.00
GANANCIA ANUAL TOTAL ANTES DE IMPUESTOS
GAT Nominal 8.65%
GAT Real 4.55%
"""]


def read(source=None,lane='investments'):
    return NuReader(lane).read_pages(source or statement(),'synthetic')


class NuTests(unittest.TestCase):
    def test_summary_reconciles_without_authorizing_cajita_import(self):
        r=read()
        self.assertTrue(r.summary_reconciled)
        self.assertEqual(r.composition_issues,())
        self.assertFalse(r.detail_reconciled)
        self.assertFalse(r.reconciled)
        self.assertFalse(r.ready_to_import)

    def test_frozen_is_subset_of_cajitas_not_an_extra_asset(self):
        r=read()
        self.assertEqual(r.summary.cajitas_reported,D('125.00'))
        self.assertEqual(r.summary.available_cajitas,D('25.00'))
        self.assertEqual(r.summary.frozen_cajitas,D('100.00'))
        self.assertEqual(r.summary.final,D('130.00'))
        self.assertEqual(r.composition_issues,())

    def test_absent_guarantee_is_not_reported_zero(self):
        self.assertIsNone(read(statement(False)).summary.guarantee_reported)
        self.assertEqual(read().summary.guarantee_reported,D('0.00'))

    def test_snapshot_one_cent_difference_is_preserved(self):
        source=statement();source[0]=source[0].replace('$5.00  $125.00','$4.99  $125.00')
        r=read(source)
        self.assertTrue(r.summary_reconciled)
        self.assertTrue(r.composition_issues)
        self.assertEqual(r.differences[0].reported,D('130.00'))
        self.assertEqual(r.differences[0].calculated,D('129.99'))

    def test_internal_transfer_is_two_evidences_not_two_external_deposits(self):
        r=read();debit=read(lane='debit')
        self.assertEqual(r.summary.deposits,D('50.00'))
        self.assertEqual(len(r.entries),2)
        self.assertEqual(len(debit.entries),2)
        self.assertEqual(debit.entries[0].value_candidates,(D('-50.00'),))
        self.assertEqual(r.entries[0].value_candidates,(D('50.00'),))
        self.assertEqual(r.account_fingerprint,debit.account_fingerprint)

    def test_freeze_maturity_is_candidate_not_income(self):
        e=read().entries[1]
        self.assertEqual(e.category,'freeze_evidence')
        self.assertEqual(e.maturity_candidate,date(2026,4,5))
        self.assertEqual(read().summary.net_income,D('2.00'))

    def test_retention_rate_is_reported_metadata_not_recomputed_tax(self):
        r=read()
        self.assertEqual(r.summary.interest_rate_reported,D('8.3'))
        self.assertEqual(r.summary.isr_rate_reported,D('0.9'))
        self.assertEqual(r.summary.retention_printed,D('-0.10'))
        self.assertEqual(r.summary.retention,D('0.10'))

    def test_zero_retention_does_not_mean_missing(self):
        source=statement();source[-1]=source[-1].replace('$2.10','$2.00').replace('-$0.10','$0.00')
        r=read(source)
        self.assertEqual(r.summary.retention,D('0.00'))
        self.assertTrue(r.summary_reconciled)

    def test_missing_amount_retains_evidence_without_inventing_zero(self):
        source=statement();source[2]=source[2].replace('+$100.00','')
        r=read(source)
        self.assertEqual(len(r.entries),2)
        self.assertEqual(r.entries[-1].value_candidates,())
        self.assertFalse(r.detail_reconciled)

    def test_duplicate_binary_evidence_does_not_inflate_coverage(self):
        r=read();coverage=review_coverage([r,r])
        self.assertEqual(len(coverage.unique_documents),1)
        self.assertEqual(len(coverage.duplicate_documents),1)

    def test_missing_identity_account_period_or_income_fails_closed(self):
        for marker in ['Nu México Financiera','Cuenta Nu:','DEL 01 AL 31 ENE 2026','DINERO GENERADO EN TU CUENTA NU']:
            with self.assertRaises(ReaderError):read([p.replace(marker,'Ausente') for p in statement()])

    def test_pdf_catalog_returns_explicit_partial_preview(self):
        r=reader_for('nu','investments').read_reconciled_pdf(synthetic_pdf(statement()))
        self.assertTrue(r.summary_reconciled)
        self.assertFalse(r.reconciled)
        self.assertEqual(r.period_start,date(2026,1,1))
        self.assertTrue(r.shared_account)


if __name__=='__main__':unittest.main()
