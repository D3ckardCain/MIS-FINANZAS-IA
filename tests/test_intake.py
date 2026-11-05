"""Flujo de la aplicación con archivos ficticios y reapertura real en disco."""
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from finanzas.app import make_server
from finanzas.intake import Inbox, analyze, plain
from finanzas.imaging import ImageEvidence, OcrLine
from tests.test_openbank import synthetic_pdf
from tests.test_plata import source


def pdf(): return synthetic_pdf([p.replace('−','-') for p in source()])


class IntakeTests(unittest.TestCase):
    def test_detects_content_runs_two_views_preserves_cutoff_warning(self):
        result=analyze(pdf())
        self.assertEqual(result['institution'],'plata')
        self.assertEqual(result['views']['debit']['mode'],'specialized')
        self.assertEqual(result['views']['investments']['data']['summary']['final'],'120.80')
        self.assertTrue(result['views']['investments']['issues'])
        self.assertNotIn('debit',result['views']['investments']['data'])
        self.assertFalse(result['views']['debit']['ready_to_import'])

    def test_filename_does_not_override_content_and_duplicate_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'inbox.sqlite3'
            with Inbox(path) as inbox:
                doc=inbox.upload(pdf(),'../Nu-diciembre-2030.pdf')
                self.assertEqual(doc['result']['institution'],'plata')
                self.assertEqual(doc['filename'],'Nu-diciembre-2030.pdf')
                original=inbox.original(doc['id'])
            with Inbox(path) as inbox:
                again=inbox.upload(original,'otro-nombre.pdf')
                self.assertTrue(again['duplicate'])
                self.assertEqual(len(inbox.list()),1)
                self.assertEqual(inbox.list()[0]['periods'],[('2026-04-01','2026-04-30')])
                self.assertEqual(inbox.original(doc['id']),original)

    def test_review_is_versioned_keeps_alerts_and_no_financial_ledger(self):
        with tempfile.TemporaryDirectory() as tmp, Inbox(Path(tmp)/'inbox.db') as inbox:
            doc=inbox.upload(pdf(),'test.pdf')
            reviewed=inbox.review(doc['id'],expected_revision=1,decision='reviewed')
            self.assertEqual(reviewed['review'],'reviewed')
            self.assertEqual(reviewed['result'],doc['result'])
            with self.assertRaises(ValueError):inbox.review(doc['id'],expected_revision=1,decision='reviewed')
            revised=inbox.reprocess(doc['id'],expected_revision=2)
            self.assertEqual(revised['review'],'pending')
            tables={row[0] for row in inbox.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertNotIn('revisions',tables)

    def test_wrong_institution_and_unknown_content_stay_pending(self):
        self.assertEqual(analyze(pdf(),institution='nu')['status'],'needs_institution')
        result=analyze(synthetic_pdf(['Sin institucion identificable']))
        self.assertEqual(result['views'],{})
        self.assertIsNone(result['institution'])

    def test_transfer_counterparty_does_not_replace_explicit_issuer(self):
        for issuer,expected in [('Emitido por Openbank Mexico','openbank'),('Nu Mexico Financiera Cuenta Nu','nu')]:
            result=analyze(synthetic_pdf([issuer+'\nTransferencia desde BanCoppel']))
            self.assertEqual(result['institution'],expected)
        ambiguous=analyze(synthetic_pdf(['Nu Mexico Financiera\nEmitido por Openbank Mexico']))
        self.assertIsNone(ambiguous['institution'])

    def test_encrypted_original_kept_password_never_persisted(self):
        from pypdf import PdfReader,PdfWriter
        writer=PdfWriter();reader=PdfReader(BytesIO(pdf()))
        for page in reader.pages:writer.add_page(page)
        writer.encrypt('fictitious-secret')
        out=BytesIO();writer.write(out)
        with tempfile.TemporaryDirectory() as tmp, Inbox(Path(tmp)/'inbox.db') as inbox:
            first=inbox.upload(out.getvalue(),'protected.pdf')
            self.assertEqual(first['result']['status'],'needs_password')
            second=inbox.reprocess(first['id'],expected_revision=1,password='fictitious-secret')
            self.assertEqual(second['result']['institution'],'plata')
            self.assertEqual(second['result']['views']['debit']['mode'],'documentary')
            payload=inbox.db.execute('SELECT result FROM intake_files').fetchone()[0]
            self.assertNotIn('fictitious-secret',payload)

    def test_scanned_pdf_not_silently_treated_as_zero(self):
        from pypdf import PdfWriter
        writer=PdfWriter();writer.add_blank_page(width=200,height=200)
        out=BytesIO();writer.write(out)
        self.assertEqual(analyze(out.getvalue())['status'],'needs_ocr')

    def test_ocr_detection_cached_once_and_both_lanes(self):
        class Engine:
            calls=0
            def read(self,content):
                self.calls+=1
                return ImageEvidence(sha256(content).hexdigest(),(100,100),(100,100),False,'PNG','eng',
                    (OcrLine('line','Banco Plata',Decimal('99'),(0,0,100,10)),),())
        engine=Engine();result=analyze(b'fake-image-for-injected-ocr',engine=engine)
        self.assertEqual(engine.calls,1)
        self.assertEqual(result['institution'],'plata')
        self.assertEqual(result['views']['debit']['mode'],'ocr')

    def test_decimal_unknown_and_category_persistence(self):
        self.assertEqual(plain({'known':Decimal('0.00'),'unknown':None}),{'known':'0.00','unknown':None})
        with tempfile.TemporaryDirectory() as tmp, Inbox(Path(tmp)/'inbox.db') as inbox:
            inbox.set_group('supertasas','SOFOMes')
            self.assertEqual(next(x for x in inbox.catalog()['institutions'] if x['key']=='supertasas')['category'],'SOFOMes')
            with self.assertRaises(ValueError):inbox.set_group('supertasas','inventada')


class LocalHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.server=make_server(Path(self.tmp.name)/'inbox.db')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
        self.token=self.request('/api/state')['token']

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()

    def request(self,path,body=None,*,raw=False,token=True,headers=None):
        extra=headers or {}
        if token:extra['X-Local-Token']=getattr(self,'token','')
        data=body if raw else json.dumps(body).encode() if body is not None else None
        req=Request(self.url+path,data=data,headers=extra)
        with urlopen(req,timeout=10) as response:return json.loads(response.read())

    def test_upload_reopen_download_duplicate_and_review_end_to_end(self):
        doc=self.request('/api/upload',pdf(),raw=True,headers={'X-Filename':'ficticio.pdf'})
        self.assertEqual(doc['result']['institution'],'plata')
        self.assertTrue(self.request('/api/upload',pdf(),raw=True)['duplicate'])
        self.assertEqual(self.request('/api/state')['documents'][0]['filename'],'ficticio.pdf')
        with urlopen(self.url+'/api/documents/'+doc['id']+'/original') as response:self.assertEqual(response.read(),pdf())
        reviewed=self.request('/api/documents/'+doc['id']+'/review',{'revision':1,'decision':'reviewed'})
        self.assertEqual(reviewed['review'],'reviewed')

    def test_rejects_external_origin_host_and_missing_mutation_token(self):
        for headers in ({'Origin':'https://untrusted.example'}, {'Host':'untrusted.example'}):
            with self.assertRaises(HTTPError) as caught:self.request('/api/state',headers=headers)
            self.assertEqual(caught.exception.code,403)
        with self.assertRaises(HTTPError) as caught:self.request('/api/upload',pdf(),raw=True,token=False)
        self.assertEqual(caught.exception.code,403)

    def test_static_app_and_invalid_route(self):
        with urlopen(self.url) as response:
            self.assertIn(b'Archivo financiero',response.read())
            self.assertIn("script-src 'self'",response.headers['Content-Security-Policy'])
        with self.assertRaises(HTTPError) as caught:self.request('/api/absent')
        self.assertEqual(caught.exception.code,404)


if __name__=='__main__':unittest.main()
