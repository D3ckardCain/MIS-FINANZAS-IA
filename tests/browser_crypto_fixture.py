"""Captura ficticia BingX para probar el registro cripto en navegador."""
from pathlib import Path
import tempfile
from finanzas.app import make_server
from finanzas.intake import Inbox
from tests.test_crypto_images import spot
from tests.test_images import picture
from finanzas.imaging import LocalOcr

if __name__=='__main__':
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'bandeja.sqlite3'
        raw=picture(spot(**{'Total':'75.00 USDT'}))
        with Inbox(path) as inbox:inbox.upload(raw,'BingX FICTICIO.png',engine=LocalOcr(languages='eng'))
        with make_server(path) as server:
            print('TEST_URL=http://127.0.0.1:'+str(server.server_port),flush=True)
            server.serve_forever()
