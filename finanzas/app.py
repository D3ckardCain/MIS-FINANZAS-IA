"""Aplicación web local sin servicios externos: python -m finanzas.app."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
from urllib.parse import unquote, urlsplit

from .intake import Inbox, MAX_UPLOAD

WEB = Path(__file__).with_name('web')


def make_server(path, port=0):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Nunca escribir nombres, claves ni documentos en logs HTTP.

        def reply(self, status, body, mime='application/json; charset=utf-8', **headers):
            if not isinstance(body, bytes): body = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            for key, value in headers.items(): self.send_header(key.replace('_', '-'), value)
            self.end_headers()
            self.wfile.write(body)

        def authorized(self, mutate=False):
            # Host exacto impide acceso mediante DNS rebinding; origen/token cierran POST externos.
            expected = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != expected:
                self.reply(403, {'error': 'Acceso local requerido'}); return False
            origin = self.headers.get('Origin')
            if origin and origin != 'http://'+expected:
                self.reply(403, {'error': 'Origen no permitido'}); return False
            if mutate and not secrets.compare_digest(self.headers.get('X-Local-Token', ''), token):
                self.reply(403, {'error': 'Vuelve a abrir la aplicación'}); return False
            return True

        def do_GET(self):
            if not self.authorized(): return
            route = urlsplit(self.path).path
            try:
                if route in ('/', '/app.js', '/app.css'):
                    name = 'index.html' if route == '/' else route[1:]
                    mime = {'index.html': 'text/html', 'app.js': 'text/javascript', 'app.css': 'text/css'}[name]
                    self.reply(200, (WEB/name).read_bytes(), mime+'; charset=utf-8'); return
                with Inbox(path) as inbox:
                    if route == '/api/state':
                        self.reply(200, dict(token=token, catalog=inbox.catalog(), documents=inbox.list())); return
                    if route.startswith('/api/documents/'):
                        parts = route.split('/')
                        identifier = parts[3]
                        if len(parts) == 5 and parts[4] == 'original':
                            data = inbox.original(identifier)
                            mime = 'application/pdf' if data[:1024].lstrip().startswith(b'%PDF-') else 'application/octet-stream'
                            self.reply(200, data, mime, Content_Disposition='attachment; filename="documento-original"'); return
                        if len(parts) == 4:
                            self.reply(200, inbox.get(identifier)); return
                self.reply(404, {'error': 'Ruta no encontrada'})
            except ValueError as error:
                self.reply(404, {'error': str(error)})

        def do_POST(self):
            if not self.authorized(mutate=True): return
            route = urlsplit(self.path).path
            try:
                length = int(self.headers.get('Content-Length', '0'))
                maximum = MAX_UPLOAD if route == '/api/upload' else 8192
                if not 0 < length <= maximum:
                    self.reply(413, {'error': 'Archivo vacío o tamaño no admitido (máximo 32 MiB)'}); return
                content = self.rfile.read(length)
                if len(content) != length: raise ValueError('Carga incompleta: reintenta')
                with Inbox(path) as inbox:
                    if route == '/api/upload':
                        self.reply(201, inbox.upload(content, unquote(self.headers.get('X-Filename', 'documento')))); return
                    payload = json.loads(content)
                    if route == '/api/group':
                        inbox.set_group(payload['institution'], payload['category'])
                        self.reply(200, inbox.catalog()); return
                    parts = route.split('/')
                    if len(parts) == 5 and parts[:3] == ['', 'api', 'documents']:
                        identifier, action = parts[3:]
                        if action == 'reprocess':
                            result = inbox.reprocess(identifier, expected_revision=payload['revision'],
                                institution=payload.get('institution') or None, password=payload.get('password') or None)
                            self.reply(200, result); return
                        if action == 'review':
                            self.reply(200, inbox.review(identifier, expected_revision=payload['revision'], decision=payload['decision'])); return
                self.reply(404, {'error': 'Ruta no encontrada'})
            except (ValueError, KeyError, TypeError) as error:
                self.reply(400, {'error': str(error) if isinstance(error, ValueError) else 'Solicitud no válida'})
            except Exception:
                self.reply(500, {'error': 'No fue posible procesar el archivo. El original existente se conserva; revisa formato y dependencias.'})

    server = HTTPServer(('127.0.0.1', port), Handler)
    server.timeout = 1
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description='MIS FINANZAS-IA · aplicación local')
    default = Path(os.environ.get('LOCALAPPDATA') or Path.home())/'MIS-FINANZAS-IA'/'bandeja.sqlite3'
    parser.add_argument('--data', type=Path, default=default)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args(argv)
    with make_server(args.data, args.port) as server:
        url = f'http://127.0.0.1:{server.server_port}'
        print('MIS FINANZAS-IA: '+url, flush=True)
        if not args.no_browser:
            import webbrowser
            webbrowser.open(url)
        try: server.serve_forever()
        except KeyboardInterrupt: pass


if __name__ == '__main__': main()
