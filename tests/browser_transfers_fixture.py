"""Dos instituciones ficticias con un traspaso pendiente para probar la interfaz."""
from pathlib import Path
import tempfile
from finanzas.app import make_server
from finanzas.intake import Inbox
from finanzas.book import FinancialBook
from tests.test_book_transfers import destination
from tests.test_book_bancoppel import content

if __name__=='__main__':
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'bandeja.sqlite3'
        with Inbox(path) as inbox,FinancialBook(path) as book:
            for data in (content(),destination()):
                doc=inbox.upload(data,'Ejemplo FICTICIO.pdf');plan=book.preview(doc['id'])
                book.confirm(doc['id'],revision=1,plan_hash=plan['plan_hash'])
        with make_server(path) as server:
            print('TEST_URL=http://127.0.0.1:'+str(server.server_port),flush=True)
            server.serve_forever()
