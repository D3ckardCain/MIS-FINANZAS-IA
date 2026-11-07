"""Servidor temporal de prueba visual, únicamente con un PDF Nu ficticio."""
from pathlib import Path
import tempfile
from finanzas.app import make_server
from finanzas.intake import Inbox
from tests.test_book_nu import content

if __name__=='__main__':
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'bandeja.sqlite3'
        with Inbox(path) as inbox:inbox.upload(content(),'Nu FICTICIO.pdf')
        with make_server(path) as server:
            print('NU_TEST_URL=http://127.0.0.1:'+str(server.server_port),flush=True)
            server.serve_forever()
