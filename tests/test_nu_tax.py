"""Fictional Nu certificate: no personal source documents or monetary fixtures."""
from calendar import monthrange
from dataclasses import replace
from datetime import date
from decimal import Decimal as D
from contextlib import redirect_stdout
from io import StringIO
from tempfile import TemporaryDirectory
from pathlib import Path
import json
import unittest

from finanzas.nu_tax import NuTaxReader,compare_nu_tax,main
from finanzas.readers import ReaderError
from tests.test_nu import read
from tests.test_openbank import synthetic_pdf


def certificate():
    first='''Nu México Financiera, S.A. de C.V., S.F.P.
RFC: AAA010101AAA
DATOS FISCALES DEL CLIENTE
Titular ficticio
RFC BBB010101BBB
CONSTANCIA DE PERCEPCIONES Y RETENCIONES DE INTERESES
Cantidades en moneda nacional Periodo: 1-12 del 2025
Monto total de la operación $25.20
Monto total gravado $2.00
Monto total exento $23.20
Monto total de las retenciones $1.20
TOTAL DE IMPUESTOS RETENIDOS
Base del impuesto retenido $2.00
Impuesto retenido 01 - ISR
Monto retenido en el periodo $1.20
Tipo de pago retenido Pago provisional
DATOS SOBRE LOS INTERESES
Interés sistema financiero SI
Interes retirados en el periodo NO
Operaciones financieras derivadas NO
Interés nominal $25.20
Interés real $18.10
Pérdida inflacionaria $0.30
DATOS DEL RETENEDOR
RFC: AAA010101AAA
'''
    chain='||2.0|SERIE_FICTICIA|FOLIO_FICTICIO|2026-01-01T00:00:00|00000|16|AAA010101AAA|NU MEXICO FINANCIERA|601|Nacional|BBB010101BBB|FICTICIO|00000|01|12|2025|25.20|2.00|23.20|1.20|2.00|001|1.20|04|1.0|SI|NO|NO|25.20|18.10|0.30||'
    second='CADENA ORIGINAL DEL COMPLEMENTO DE CERTIFICACIÓN DIGITAL DEL SAT:\n'+chain+'\nSELLO DIGITAL DEL EMISOR: ficticio\nFOLIO DEL SAT (UUID): 11111111-2222-3333-4444-555555555555'
    return [first,second]


def tax(pages=None):return NuTaxReader().read_pages(pages or certificate(),'fictitious-certificate')


def months():
    base=read();out=[]
    for m in range(1,13):
        out.append(replace(base,document_id=f'month-{m}',period_start=date(2025,m,1),
            period_end=date(2025,m,monthrange(2025,m)[1])))
    return out


class NuTaxTests(unittest.TestCase):
    def test_visible_and_chain_are_preserved_separately(self):
        r=tax()
        self.assertEqual(r.values.nominal_interest,D('25.20'))
        self.assertEqual(r.chain_values,r.values)
        self.assertEqual(r.period_start,date(2025,1,1))
        self.assertEqual(r.period_end,date(2025,12,31))
        self.assertTrue(r.internally_consistent)
        self.assertFalse(r.signature_verified)
        self.assertFalse(r.ready_to_import)
        self.assertEqual(r.payment_type_reported,'Pago provisional')
        self.assertEqual(r.payment_code_reported,'04')
        self.assertEqual(r.chain_page,2)
        self.assertFalse(hasattr(r,'entries'))

    def test_one_cent_real_interest_difference_is_not_corrected(self):
        src=certificate();src[1]=src[1].replace('|18.10|','|18.11|')
        r=tax(src)
        self.assertFalse(r.internally_consistent)
        self.assertEqual(r.values.real_interest,D('18.10'))
        self.assertEqual(r.chain_values.real_interest,D('18.11'))
        self.assertEqual(r.differences[0].check,'Portada frente a cadena: real_interest')

    def test_exempt_sum_and_chain_difference_both_reported(self):
        src=certificate();src[0]=src[0].replace('exento $23.20','exento $23.19')
        r=tax(src)
        self.assertEqual(len(r.differences),2)
        self.assertEqual(r.values.exempt,D('23.19'))

    def test_inflation_loss_is_not_subtracted_by_invented_identity(self):
        r=tax()
        self.assertEqual(r.values.inflation_loss,D('0.30'))
        self.assertTrue(r.internally_consistent)
        self.assertNotEqual(r.values.nominal_interest-r.values.inflation_loss,r.values.real_interest)

    def test_missing_duplicate_amount_or_unknown_chain_fails_closed(self):
        for old,new in [('Interés nominal $25.20','Interés nominal ausente'),
            ('Interés nominal $25.20','Interés nominal $25.20\nInterés nominal $25.20'),
            ('||2.0|','||3.0|')]:
            with self.subTest(old=old):
                with self.assertRaises(ReaderError):tax([p.replace(old,new) for p in certificate()])

    def test_wrong_period_and_party_are_not_linked(self):
        for old,new in [('|01|12|2025|','|02|12|2025|'),('|BBB010101BBB|','|CCC010101CCC|')]:
            src=certificate();src[1]=src[1].replace(old,new)
            with self.assertRaises(ReaderError):tax(src)

    def test_partial_annual_period_uses_reported_months(self):
        src=[p.replace('1-12 del 2025','3-12 del 2025').replace('|01|12|2025|','|03|12|2025|') for p in certificate()]
        r=tax(src)
        self.assertEqual(r.period_start,date(2025,3,1))
        self.assertEqual(len(compare_nu_tax(r,months()).statement_ids),10)

    def test_matching_monthly_totals_never_create_annual_income(self):
        r=compare_nu_tax(tax(),months())
        self.assertTrue(r.monthly_totals_match)
        self.assertEqual(r.monthly_gross,D('25.20'))
        self.assertEqual(r.monthly_retention,D('1.20'))
        self.assertFalse(r.identity_link_confirmed)
        self.assertFalse(r.ready_to_import)
        self.assertFalse(hasattr(r,'entries'))

    def test_monthly_binary_duplicate_counted_once(self):
        source=months();r=compare_nu_tax(tax(),source+[source[0]])
        self.assertTrue(r.monthly_totals_match)
        self.assertEqual(len(r.statement_ids),12)

    def test_missing_month_does_not_become_annual_difference(self):
        r=compare_nu_tax(tax(),months()[1:])
        self.assertEqual(r.missing_months,('2025-01',))
        self.assertFalse(r.monthly_totals_match)
        self.assertEqual(r.differences,())

    def test_two_distinct_files_for_same_month_require_review(self):
        source=months()
        with self.assertRaises(ReaderError):compare_nu_tax(tax(),source+[replace(source[0],document_id='other')])
        with self.assertRaises(ReaderError):compare_nu_tax(tax(),source+[replace(source[0],document_id='other',account_fingerprint='other')])

    def test_partial_month_not_used_as_full_month(self):
        source=months();source[0]=replace(source[0],period_start=date(2025,1,2))
        with self.assertRaises(ReaderError):compare_nu_tax(tax(),source)

    def test_internal_difference_not_hidden_by_matching_months(self):
        src=certificate();src[1]=src[1].replace('|18.10|','|18.11|');c=tax(src)
        r=compare_nu_tax(c,months())
        self.assertTrue(r.monthly_totals_match)
        self.assertTrue(any('diferencias internas' in x for x in r.issues))
        self.assertFalse(r.ready_to_import)

    def test_generic_rfc_flags_contextual_comparison(self):
        c=tax([p.replace('BBB010101BBB','XAXX010101000') for p in certificate()])
        self.assertTrue(c.generic_recipient)
        self.assertTrue(any('RFC genérico' in x for x in compare_nu_tax(c,months()).issues))

    def test_true_monthly_retention_difference_is_preserved(self):
        source=months();source[0]=replace(source[0],summary=replace(source[0].summary,retention=D('0.09')))
        r=compare_nu_tax(tax(),source)
        self.assertFalse(r.monthly_totals_match)
        self.assertEqual(r.differences[0].visible,D('1.20'))
        self.assertEqual(r.differences[0].compared,D('1.19'))

    def test_pdf_and_cli_default_hide_private_amounts_and_ids(self):
        content=synthetic_pdf(certificate())
        r=NuTaxReader().read_pdf(content)
        self.assertEqual(r.values,tax().values)
        with TemporaryDirectory() as folder:
            p=Path(folder)/'certificate.pdf';p.write_bytes(content);out=StringIO()
            with redirect_stdout(out):self.assertEqual(main([str(p)]),0)
            d=json.loads(out.getvalue())
            self.assertNotIn('25.20',out.getvalue())
            self.assertNotIn('11111111',out.getvalue())
            self.assertFalse(d['signature_verified'])
            self.assertFalse(d['ready_to_import'])


if __name__=='__main__':unittest.main()
