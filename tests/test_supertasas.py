"""Fictional SuperTasas cash/term snapshots; no private values or passwords."""
from dataclasses import replace
from decimal import Decimal as D
from datetime import date
from io import BytesIO
import unittest
from pypdf import PdfWriter
from finanzas.supertasas import SuperTasasReader,review_supertasas
from finanzas.readers import ReaderError,reader_for
from finanzas.coverage import review_coverage
from tests.test_openbank import synthetic_pdf


def row(day,description,ref,charge='',deposit='',balance='0'):
    return f'{day:<12}{"1":<8}{description:<32}{ref:<14}{charge:<15}{deposit:<15}{balance}'


def source():
    header=row('FECHA','DESCRIPCIONDE LA OPERACIÓN','REFERENCIA','CARGO','ABONO','SALDO')
    return f'''SuperTasas.com marca Crediclub
Núm. de Cuenta: 000111222
Periodo: 01 al 31 de Enero del 2026
Rendimiento bruto en pesos mexicanos $ 1.00
Tasa de interés o rendimiento 7.00 % anual
Total de Comisiones Cobradas 0.00
IVA de Comisiones 0.00
RESUMEN DE MOVIMIENTOS EN CUENTA A LA VISTA
Saldo Inicial 100.00     Saldo Promedio diario 150.00
(+) Abonos 21.00         Intereses Brutos 1.00
(-) Cargos 50.00         Retención ISR .00
(=) Saldo Final 71.00    Intereses Netos 1.00
DETALLE DE MOVIMIENTOS EN CUENTA A LAVISTA
{header}
{row('2026-01-05','ABONO STP','1001',deposit='20',balance='120')}
{row('2026-01-06','APERTURAINVERSION','1002',charge='50',balance='70')}
{row('2026-01-30','PAGORENDIMIENTO CTA.GRAVADO','1003',deposit='1',balance='71')}
RESUMEN DE COMISIONES EN INVERSION A PLAZO
Total de Comisiones Cobradas 0.00
IVA de Comisiones 0.00
RESUMEN DE INVERSIONES A PLAZO VIGENTES
50.00 364 2026-01-06 2027-01-05 5.00 .00 5.00 55.00 10.00 % 10.00%* 6.00%*
* La GAT Real informativa
'''


def read(text=None,lane='investments'):return SuperTasasReader(lane).read_pages([text or source()],'fictitious')


class SuperTasasTests(unittest.TestCase):
    def test_cash_separate_from_term_forecast(self):
        r=read();self.assertTrue(r.reconciled)
        self.assertEqual(r.summary.final,D('71'))
        self.assertEqual(r.contracts[0].projected_gross,D('5.00'))
        self.assertEqual(len(r.entries),2)
        self.assertEqual(len(read(lane='debit').entries),3)
        self.assertEqual(read(lane='debit').account_fingerprint,r.account_fingerprint)
        self.assertFalse(r.ready_to_import)

    def test_blank_initial_is_unknown_not_zero(self):
        r=read(source().replace('Saldo Inicial 100.00','Saldo Inicial       '))
        self.assertIsNone(r.summary.initial)
        self.assertFalse(r.reconciled)
        self.assertTrue(any('no publicado' in i for i in r.issues))

    def test_reported_negative_balance_parentheses_preserved(self):
        s=source().replace("balance placeholder",'unused')
        s=s.replace(row('2026-01-05','ABONO STP','1001',deposit='20',balance='120'),row('2026-01-05','ABONO STP','1001',deposit='20',balance='(120.00)'))
        r=read(s);self.assertEqual(r.rows[0].balance,D('-120.00'))
        self.assertFalse(r.reconciled)
        self.assertEqual(r.summary.final,D('71'))

    def test_paid_term_interest_not_projection_or_principal(self):
        s=source().replace('ABONO STP','PAGOCEDE. INTERESEXCENTO')
        r=read(s)
        self.assertEqual(r.rows[0].category,'term_interest')
        self.assertEqual(r.rows[0].deposit,D('20'))
        self.assertEqual(r.contracts[0].projected_gross,D('5'))
        self.assertEqual(r.summary.gross_interest,D('1'))

    def test_principal_only_maturity_not_forced_to_include_forecast_interest(self):
        r=read(source().replace('5.00 55.00','5.00 50.00'))
        self.assertEqual(r.contracts[0].maturity_amount_form,'principal_only')
        self.assertTrue(r.reconciled)

    def test_published_matured_position_stays_visible_and_blocks_total(self):
        s=source().replace('364 2026-01-06 2027-01-05','364 2025-01-06 2026-01-05')
        r=read(s)
        self.assertTrue(r.detail_reconciled)
        self.assertFalse(r.reconciled)
        self.assertEqual(len(r.contracts),1)

    def test_bad_forecast_does_not_get_corrected(self):
        r=read(source().replace('5.00 .00 5.00','5.00 .00 4.99'))
        self.assertEqual(r.contracts[0].projected_net,D('4.99'))
        self.assertFalse(r.reconciled)

    def test_nonzero_retention_preserved_and_blocks_unsupported_cash_mapping(self):
        r=read(source().replace('Retención ISR .00','Retención ISR .10'))
        self.assertEqual(r.summary.retention,D('.10'))
        self.assertFalse(r.reconciled)

    def test_unknown_investment_concept_is_not_ignored(self):
        r=read(source().replace('APERTURAINVERSION','CONCEPTO DESCONOCIDO'))
        self.assertTrue(any('sin mapeo' in i for i in r.issues))

    def test_missing_header_and_wrong_account_or_period_rejected(self):
        for old,new in [('REFERENCIA','NO COLUMNA'),('Núm. de Cuenta:','Cuenta ausente'),('Enero del 2026','MesRaro del 2026')]:
            with self.assertRaises(ReaderError):read(source().replace(old,new))

    def test_file_duplicates_and_history_candidates_do_not_create_reinvestment(self):
        a=read();h=review_supertasas([a,a])
        self.assertEqual(h.duplicates,('fictitious',))
        self.assertEqual(len(h.candidates),1)
        self.assertEqual(h.candidates[0].kind,'term_opening')
        self.assertEqual(h.candidates[0].status,'candidate_requires_review')

    def test_other_account_or_overlapping_period_cannot_be_mixed(self):
        r=read()
        for other in [replace(r,document_id='other',account_fingerprint='other'),replace(r,document_id='other')]:
            with self.assertRaises(ReaderError):review_supertasas([r,other])

    def test_duplicate_snapshot_not_summed(self):
        s=source();line=next(l for l in s.splitlines() if l.startswith('50.00 364'))
        with self.assertRaises(ReaderError):read(s.replace(line,line+'\n'+line))

    def test_pdf_catalog_and_protected_reader_accept_explicit_password_only(self):
        content=synthetic_pdf([source()])
        self.assertTrue(reader_for('supertasas','investments').read_reconciled_pdf(content).reconciled)
        from pypdf import PdfReader
        writer=PdfWriter();writer.append(PdfReader(BytesIO(content)));writer.encrypt('SYNTHETIC-ONLY')
        buf=BytesIO();writer.write(buf);protected=buf.getvalue()
        with self.assertRaises(ReaderError):SuperTasasReader().read_pdf(protected)
        with self.assertRaises(ReaderError):SuperTasasReader().read_pdf(protected,password='WRONG-FICTITIOUS')
        r=SuperTasasReader().read_pdf(protected,password='SYNTHETIC-ONLY')
        self.assertTrue(r.reconciled)
        self.assertNotIn('SYNTHETIC-ONLY',repr(r))

    def test_coverage_skips_unknown_initial_instead_of_counting_zero(self):
        a=read();b=replace(a,document_id='next',period_start=date(2026,2,1),period_end=date(2026,2,28),summary=replace(a.summary,initial=None))
        r=review_coverage([a,b])
        self.assertEqual(r.continuity_checked,0)
        self.assertTrue(any('no verificable' in i for i in r.issues))


    def test_ambiguous_opening_does_not_assign_same_position_twice(self):
        a=read();opening=a.rows[1]
        b=replace(a,rows=a.rows+(replace(opening,evidence_id='other-row',reference='other-ref'),))
        h=review_supertasas([b])
        self.assertEqual(h.candidates,())
        self.assertTrue(h.issues)


if __name__=='__main__':unittest.main()
