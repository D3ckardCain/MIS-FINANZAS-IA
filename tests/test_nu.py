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



class NuDetailTests(unittest.TestCase):
    def test_old_dates_without_year_use_internal_period(self):
        src=statement();src[1]=src[1].replace('05 ENE 2026','05 ENE')
        self.assertEqual(read(src).account_events[0].effective_date,date(2026,1,5))

    def test_year_and_cajita_name_on_next_line(self):
        src=statement();src[2]=src[2].replace('05 ENE 2026 Depósito en Cajita: FICTICIA +$50.00',
            '05 ENE Depósito en Cajita: FICTICIA +$50.00\n2026')
        self.assertEqual(read(src).investment_events[0].cajita,'ficticia')
        self.assertEqual(len(read(src).investment_events),2)

    def test_spei_continues_across_page_footer(self):
        src=statement();src[1]=src[1].replace('Nu México Financiera','Nu México Financiera\nfooter')
        src.insert(2,'Titular ficticio\nCuenta Nu: 00011111111\nFECHA DEL 01 AL 31 ENE 2026\nDepósito SPEI Clave de rastreo FICTICIO123\nNu México Financiera')
        r=read(src)
        self.assertEqual(r.account_events[-1].tracking_key,'FICTICIO123')
        self.assertNotIn('Titular ficticio',r.account_events[-1].description_printed)

    def test_wrapped_name_survives_amount_between_name_parts(self):
        src=statement();src[2]=src[2].replace('Cajita: FICTICIA +$100.00','Cajita: NUMERO -$100.00\n5')
        self.assertEqual(read(src).investment_events[-1].cajita,'numero 5')

    def test_pairs_require_explicit_name_and_opposite_sign(self):
        from finanzas.nu import review_nu_document
        r=review_nu_document(read())
        self.assertEqual(len(r.pairs),1)
        self.assertEqual(r.unmatched_internal,())
        src=statement();src[2]=src[2].replace('Depósito en Cajita: FICTICIA','Depósito en Cajita: OTRA')
        r=review_nu_document(read(src))
        self.assertEqual(r.pairs,())
        self.assertEqual(len(r.unmatched_internal),2)

    def test_ambiguous_same_name_date_amount_not_paired_arbitrarily(self):
        from finanzas.nu import review_nu_document
        src=statement();src[2]=src[2].replace('Nu México Financiera','05 ENE 2026 Depósito en Cajita: FICTICIA +$50.00\nNu México Financiera')
        self.assertEqual(review_nu_document(read(src)).pairs,())

    def test_freeze_and_release_are_neutral_inside_investments(self):
        from finanzas.nu import review_nu_document
        src=statement();src[2]=src[2].replace('+$100.00','-$100.00')
        review=review_nu_document(read(src))
        legs=[p for p in review.postings if p.kind=='freeze']
        self.assertEqual(len(legs),2)
        self.assertEqual(sum(p.amount for p in legs),D('0'))
        self.assertEqual(review.unallocated_net_income,D('2.00'))
        self.assertEqual(review.external_net,D('50.00'))

    def test_invalid_positive_freeze_is_preserved_but_not_posted(self):
        from finanzas.nu import review_nu_document
        review=review_nu_document(read())
        self.assertTrue(any('Congelamiento' in x for x in review.issues))
        self.assertFalse(any(p.kind=='freeze' for p in review.postings))

    def test_external_net_failure_does_not_hide_behind_summary(self):
        from finanzas.nu import review_nu_document
        src=statement();src[1]=src[1].replace('Depósito SPEI +$50.00','Depósito SPEI +$49.00')
        r=read(src)
        self.assertTrue(r.summary_reconciled)
        self.assertTrue(any('Neto externo' in x for x in review_nu_document(r).issues))

    def test_history_duplicates_and_accounts(self):
        from finanzas.nu import review_nu_documents
        r=read();h=review_nu_documents([r,r])
        self.assertEqual(len(h.documents),1)
        self.assertEqual(h.duplicate_documents,('synthetic',))
        with self.assertRaises(ReaderError):review_nu_documents([r,replace(r,document_id='other',account_fingerprint='other')])

    def test_history_rejects_distinct_overlapping_documents(self):
        from finanzas.nu import review_nu_documents
        r=read()
        with self.assertRaises(ReaderError):review_nu_documents([r,replace(r,document_id='other')])

    def test_maturity_match_is_candidate_without_computing_income(self):
        from finanzas.nu import review_nu_documents
        src=statement();src[2]=src[2].replace('05 ABR 2026','05 FEB 2026').replace('+$100.00','-$100.00')
        a=read(src)
        release=replace(a.investment_events[-1],evidence_id='release',effective_date=date(2026,2,5),
            category='unfreeze_evidence',value_candidates=(D('101.00'),),maturity_candidate=None)
        b=replace(a,document_id='feb',period_start=date(2026,2,1),period_end=date(2026,2,28),investment_events=(release,))
        h=review_nu_documents([a,b])
        self.assertEqual(len(h.maturity_candidates),1)
        self.assertEqual(h.maturity_candidates[0].status,'candidate_requires_contract')
        self.assertFalse(hasattr(h.maturity_candidates[0],'interest'))
        ambiguous=replace(b,investment_events=(release,replace(release,evidence_id='second')))
        self.assertEqual(review_nu_documents([a,ambiguous]).maturity_candidates,())

    def test_reversal_with_same_tracking_key_keeps_both_signed_rows(self):
        src=statement();src[1]=src[1].replace('Nu México Financiera',
            '06 ENE 2026 Transferencia SPEI -$7.00\nClave de rastreo FICTICIOREV1\n06 ENE 2026 Transferencia SPEI +$7.00\nClave de rastreo FICTICIOREV1\nNu México Financiera')
        r=read(src);rev=[e for e in r.account_events if e.tracking_key=='FICTICIOREV1']
        self.assertEqual(len(rev),2)
        self.assertEqual([e.amount for e in rev],[D('-7.00'),D('7.00')])
        self.assertEqual(r.detail_review.external_net,D('50.00'))

    def test_empty_zero_statement_can_reconcile_detail_without_enabling_import(self):
        src=statement(False);src[1]=src[1].split('05 ENE',1)[0];src[2]=''
        import re
        src=[re.sub(r'\$\d+\.\d{2}','$0.00',p) for p in src]
        r=read(src)
        self.assertTrue(r.reconciled)
        self.assertFalse(r.ready_to_import)



class NuIssuerTests(unittest.TestCase):
    def test_banking_issuer_variant_preserves_same_account_identity(self):
        src=[p.replace('Nu México Financiera','Nubank, S.A., Institución de Banca Múltiple') for p in statement()]
        r=read(src)
        self.assertEqual(r.issuer_reported,'Nubank, S.A., Institución de Banca Múltiple')
        self.assertEqual(r.account_fingerprint,read().account_fingerprint)
        self.assertEqual(len(r.account_events),2)
        self.assertEqual(len(r.investment_events),2)
        self.assertNotIn('Nubank',r.investment_events[-1].description_printed)
        self.assertTrue(r.summary_reconciled)

    def test_conflicting_or_unknown_issuer_is_not_silently_accepted(self):
        src=statement();src[-1]+='\nNubank, S.A., Institución de Banca Múltiple'
        with self.assertRaises(ReaderError):read(src)
        with self.assertRaises(ReaderError):read([p.replace('Nu México Financiera','Nu de otra entidad') for p in statement()])

    def test_identity_variant_does_not_change_binary_duplicate_rule(self):
        from finanzas.nu import review_nu_documents
        a=read();b=replace(a,issuer_reported='Nubank, S.A., Institución de Banca Múltiple')
        self.assertEqual(len(review_nu_documents([a,b]).documents),1)


    def test_pdf_catalog_accepts_banking_issuer(self):
        src=[p.replace('Nu México Financiera','Nubank, S.A., Institución de Banca Múltiple') for p in statement()]
        r=reader_for('nu','investments').read_reconciled_pdf(synthetic_pdf(src))
        self.assertTrue(r.summary_reconciled)
        self.assertEqual(r.account_fingerprint,read().account_fingerprint)
        self.assertTrue(r.issuer_reported.startswith('Nubank,'))


if __name__=='__main__':unittest.main()
