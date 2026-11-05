"""Fictional Openbank PDF/XML certificates and account history."""
from dataclasses import replace
from decimal import Decimal as D
import unittest
from finanzas.openbank import OpenbankDebitReader,OpenbankInvestmentReader,FormatError
from finanzas.openbank_tax import OpenbankTaxReader,compare_tax_formats,compare_tax_months,RET,INT,TFD,ADD
from finanzas.coverage import review_coverage
from tests.test_openbank import page,table_row,synthetic_pdf


UID='11111111-2222-3333-4444-555555555555'


def pdf_pages():
    return ['''Cuenta Débito Open Light
Número de cliente 1000000001
RFC BBB010101BBB
Aquí está la constancia fiscal
Periodo que ampara la constancia: enero a diciembre de 2026
MONTO TOTAL DE LA OPERACIÓN $ 2.00
MONTO TOTAL GRAVADO $ 2.00
MONTO TOTAL EXENTO $ 0.00
MONTO TOTAL DE LAS RETENCIONES $ 0.00
CLAVE DE RETENCIÓN 16
INTERÉS NOMINAL $ 2.00
INTERÉS REAL $ 1.50
PÉRDIDA INFLACIONARIA $ 0.00
ISR RETENIDO (PAGO PROVISIONAL) $ 0.00
Emitido por Openbank, RFC: AAA010101AAA
''','Folio interno 1000000001\n|1.1|'+UID+'|2027-01-01T00:00:00|FICTICIO|SELLOFICTICIO|']


def xml_text():
    return f'''<r:Retenciones xmlns:r="{RET}" xmlns:i="{INT}" xmlns:t="{TFD}" xmlns:a="{ADD}" Version="2.0" CveRetenc="16" FolioInt="1000000001">
<r:Emisor RfcE="AAA010101AAA"/><r:Receptor><r:Nacional RfcR="BBB010101BBB"/></r:Receptor>
<r:Periodo MesIni="01" MesFin="12" Ejercicio="2026"/>
<r:Totales MontoTotOperacion="2.00" MontoTotGrav="2.00" MontoTotExent="0.00" MontoTotRet="0.00"><r:ImpRetenidos ImpuestoRet="001" MontoRet="0.00" TipoPagoRet="04"/></r:Totales>
<r:Complemento><i:Intereses Version="1.0" MontIntNominal="2.00" MontIntReal="1.50" Perdida="0.00"/><t:TimbreFiscalDigital Version="1.1" UUID="{UID}"/></r:Complemento>
<r:Addenda><a:AddendaRetencion><a:retenciones><a:addendaRetencionesOpenBank version="1.0" numeroCuenta="1000000001" fecha="2026-01-05" monto="2.00" descripcion="CREDIT INTEREST" idMovto="123456789012345.000001"/></a:retenciones></a:AddendaRetencion></r:Addenda>
</r:Retenciones>'''


def monthly():
    src=page('Cuenta Débito Open Light',[table_row('05/01/26','Abono de intereses','$ 2.00','','$ 2.00')],initial='0.00',final='2.00',interest='2.00')
    src+='\nNúmero de cuenta 1000000001\nRFC BBB010101BBB'
    return OpenbankDebitReader().read_pages([src],'month')


def cert():return OpenbankTaxReader().read_pages(pdf_pages(),'certificate')


class OpenbankTaxTests(unittest.TestCase):
    def test_pdf_keeps_product_period_and_annual_values_without_entries(self):
        c=cert();self.assertEqual(c.lane,'debit')
        self.assertEqual(c.values.nominal_interest,D('2.00'))
        self.assertEqual(c.issues,())
        self.assertFalse(c.signature_verified);self.assertFalse(c.ready_to_import)
        self.assertFalse(hasattr(c,'rows'))

    def test_xml_addendum_preserves_exact_string_id_and_is_not_new_income(self):
        x=OpenbankTaxReader().read_xml(xml_text().encode())
        self.assertEqual(x.addendum[0].movement_id,'123456789012345.000001')
        self.assertEqual(x.values.nominal_interest,D('2.00'))
        self.assertEqual(x.payment_type_reported,'04')
        self.assertIsNone(x.lane)
        self.assertFalse(x.ready_to_import)
        self.assertEqual(x.issues,())

    def test_multipart_txt_and_bare_xml_are_same_certificate_distinct_evidence(self):
        data=xml_text().encode();wrapped=b'--fictitious\r\nContent-Disposition: form-data; name="document"; filename="f.xml"\r\nContent-Type: application/xml\r\n\r\n'+data+b'\r\n--fictitious--\r\n'
        reader=OpenbankTaxReader();a=reader.read_xml(data);b=reader.read_xml(wrapped)
        self.assertEqual(a.uuid,b.uuid);self.assertEqual(a.values,b.values)
        self.assertNotEqual(a.document_id,b.document_id)
        self.assertTrue(compare_tax_formats(cert(),b).same_certificate)

    def test_multipart_multiple_parts_not_arbitrarily_selected(self):
        part=b'Content-Type: application/xml\n\n'+xml_text().encode()+b'\n'
        with self.assertRaises(FormatError):OpenbankTaxReader().read_xml(b'--abc\n'+part+b'--abc\n'+part+b'--abc--\n')

    def test_dtd_entities_and_wrong_root_rejected_without_network(self):
        for content in ['<!DOCTYPE a [<!ENTITY b SYSTEM "file:///no">]>'+xml_text(),'<other/>',xml_text().replace('Version="2.0"','Version="3.0"')]:
            with self.assertRaises(FormatError):OpenbankTaxReader().read_xml(content.encode())

    def test_duplicate_addendum_id_requires_review(self):
        s=xml_text();row=s.split('<a:addendaRetencionesOpenBank',1)[1].split('/>',1)[0]
        s=s.replace('</a:retenciones>','<a:addendaRetencionesOpenBank'+row+'/></a:retenciones>')
        with self.assertRaises(FormatError):OpenbankTaxReader().read_xml(s.encode())

    def test_xml_unknown_amount_and_missing_required_node_rejected(self):
        for content in [xml_text().replace('MontoTotRet="0.00"','MontoTotRet="NaN"'),xml_text().replace('<r:Periodo','<r:Another')]:
            with self.assertRaises(FormatError):OpenbankTaxReader().read_xml(content.encode())

    def test_addendum_sum_and_period_mismatch_preserved_as_issues(self):
        s=xml_text().replace('monto="2.00"','monto="1.99"').replace('fecha="2026-01-05"','fecha="2025-01-05"')
        x=OpenbankTaxReader().read_xml(s.encode())
        self.assertEqual(len(x.issues),2)
        self.assertEqual(x.addendum[0].amount,D('1.99'))

    def test_wrong_uuid_or_product_not_paired_by_equal_amount(self):
        x=OpenbankTaxReader().read_xml(xml_text().encode())
        for c in [replace(cert(),uuid='other'),replace(cert(),product_reference_fingerprint='other')]:
            self.assertFalse(compare_tax_formats(c,x).same_certificate)
            with self.assertRaises(FormatError):compare_tax_months(c,[monthly()],xml=x)

    def test_pdf_xml_one_cent_difference_is_not_corrected(self):
        x=OpenbankTaxReader().read_xml(xml_text().replace('MontIntReal="1.50"','MontIntReal="1.51"').encode())
        r=compare_tax_formats(cert(),x)
        self.assertTrue(r.same_certificate)
        self.assertEqual(r.differences,('real_interest',))

    def test_monthly_observed_totals_match_without_claiming_full_annual_coverage(self):
        x=OpenbankTaxReader().read_xml(xml_text().encode());r=compare_tax_months(cert(),[monthly()],xml=x)
        self.assertTrue(r.observed_totals_match)
        self.assertEqual(len(r.missing_months),11)
        self.assertEqual(r.addendum_matches,('123456789012345.000001',))
        self.assertEqual(r.unmatched_addendum,())
        self.assertFalse(r.identity_link_confirmed);self.assertFalse(r.ready_to_import)

    def test_wrong_monthly_holder_not_assumed_from_product_or_amount(self):
        with self.assertRaises(FormatError):compare_tax_months(cert(),[replace(monthly(),recipient_fingerprint='other')])

    def test_duplicate_file_counted_once_but_other_version_same_month_rejected(self):
        p=monthly();r=compare_tax_months(cert(),[p,p])
        self.assertEqual(r.observed_gross,D('2.00'))
        with self.assertRaises(FormatError):compare_tax_months(cert(),[p,replace(p,document_id='other')])

    def test_pdf_end_to_end(self):
        r=OpenbankTaxReader().read_pdf(synthetic_pdf(pdf_pages()))
        self.assertEqual(r.values,cert().values)


class OpenbankHistoryTests(unittest.TestCase):
    def test_explicit_debit_identity_and_parent_investment_identity_are_distinct(self):
        p=monthly();src=page('Apartado Open',[],initial='0.00')
        a=OpenbankInvestmentReader().read_pages([src,'Número de cuenta 1000000001\nRFC BBB010101BBB'],'same')
        self.assertNotEqual(a.account_fingerprint,p.account_fingerprint)
        self.assertEqual(a.recipient_fingerprint,p.recipient_fingerprint)
        self.assertEqual(a.identity_source,'parent_debit_account_and_product')
        self.assertEqual(review_coverage([p,p]).duplicate_documents,('month',))
        with self.assertRaises(ValueError):review_coverage([p,a])

    def test_absent_identity_is_unknown(self):
        a=OpenbankInvestmentReader().read_pages([page('Apartado Open',[],initial='0.00')],'fictitious')
        self.assertIsNone(a.account_fingerprint)
        with self.assertRaises(ValueError):review_coverage([a])

    def test_zero_summary_may_explicitly_omit_table(self):
        src=page('Apartado Open',[],initial='0.00').split('Detalle de tus transacciones')[0]+'\nFecha Comisiones'
        a=OpenbankInvestmentReader().read_pages([src],'fictitious',raw_pages=[src])
        self.assertTrue(a.reconciled);self.assertEqual(a.rows,())

    def test_absent_table_never_hides_nonzero_cash_or_malformed_rows(self):
        src=page('Apartado Open',[],initial='0.00').split('Detalle de tus transacciones')[0]
        for text in [src.replace('Saldo final $ 0.00','Saldo final $ 1.00'),src+'\n05/01/26 movimiento',src+'\nOperación desconocida $ 1.00']:
            with self.assertRaises(FormatError):OpenbankInvestmentReader().read_pages([text],'fictitious')


    def test_recipient_in_second_column_is_identified(self):
        source=page('Cuenta Débito Open Light',[],initial='0.00')+'\nDirección ficticia                  RFC BBB010101BBB\nNúmero de cuenta 1000000001'
        p=OpenbankDebitReader().read_pages([source],'fake')
        self.assertEqual(p.recipient_fingerprint,cert().recipient_fingerprint)

    def test_same_binary_id_cannot_hide_changed_summary(self):
        p=monthly()
        with self.assertRaises(FormatError):compare_tax_months(cert(),[p,replace(p,summary=replace(p.summary,interest=D('1.99')))])

    def test_xml_console_omits_amounts_and_fiscal_ids(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from contextlib import redirect_stdout
        from io import StringIO
        from finanzas.openbank_tax import main
        with TemporaryDirectory() as folder:
            p=Path(folder)/'fictitious.txt';p.write_text(xml_text());out=StringIO()
            with redirect_stdout(out):self.assertEqual(main([str(p)]),0)
            self.assertNotIn('2.00',out.getvalue())
            self.assertNotIn(UID,out.getvalue())
            self.assertNotIn('123456789012345',out.getvalue())


    def test_unknown_addendum_product_not_assumed_to_be_debit(self):
        c=replace(cert(),lane='investments')
        with self.assertRaises(FormatError):compare_tax_months(c,[],xml=OpenbankTaxReader().read_xml(xml_text().encode()))


if __name__=='__main__':unittest.main()
