"""Bandeja local persistente: originales, detección y resultados de ambos lectores.

El archivo se guarda una vez por SHA-256. La revisión documental no escribe
movimientos en el ledger ni transforma observaciones en operaciones económicas.
"""
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import sqlite3

from .readers import PROFILES, reader_for, fold

MAX_UPLOAD = 32 * 1024 * 1024
CATEGORIES = ('Bancos', 'SOFIPOs', 'SOFOMes', 'Instituciones de préstamo',
              'Acciones', 'Criptomonedas', 'FIBRAs', 'Fondos y deuda', 'Por clasificar')
# Agrupación de navegación; no determina régimen fiscal ni naturaleza jurídica histórica.
GROUPS = dict.fromkeys(('bancoppel', 'openbank', 'plata', 'mifel', 'hey', 'kapital'), 'Bancos')
GROUPS.update(nu='SOFIPOs', didi='SOFIPOs', doopla='Instituciones de préstamo',
              yotepresto='Instituciones de préstamo', alpaca='Acciones',
              bingx='Criptomonedas', pionex='Criptomonedas',
              fintual='Fondos y deuda', cetesdirecto='Fondos y deuda')
NAMES = {p.key: p.name for p in PROFILES} | {'bingx': 'BingX', 'pionex': 'Pionex'}


def plain(value):
    """Sin float: conserva todos los importes como cadenas decimales exactas."""
    if is_dataclass(value):
        return plain(asdict(value))
    if isinstance(value, (Decimal, date, datetime)):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError('Resultado documental no serializable')


def _candidates(text):
    text = fold(text)
    found = [p.key for p in PROFILES if re.search(p.identity, text)]
    found += [key for key in ('bingx', 'pionex') if re.search(r'\b'+key+r'\b', text)]
    # Una contraparte SPEI puede nombrar a otro banco. Priorizar declaración
    # explícita del emisor; nunca elegir por el saldo o el nombre del archivo.
    issuer_patterns = {'nu': r'nu mexico financiera',
                       'openbank': r'emitido por openbank',
                       'bancoppel': r'bancoppel,?\s+s\.?\s*a\.?[, ]'}
    issuers = [key for key, pattern in issuer_patterns.items() if key in found and re.search(pattern, text)]
    if len(issuers) == 1:
        return issuers
    return found


def analyze(content, *, institution=None, password=None, engine=None):
    """Detecta por contenido, nunca por el nombre. Contraseña solo en memoria."""
    if not isinstance(content, bytes) or not content or len(content) > MAX_UPLOAD:
        raise ValueError('Archivo vacío o mayor de 32 MiB')
    if institution and institution not in NAMES:
        raise ValueError('Institución no admitida')
    identifier = sha256(content).hexdigest()
    result = dict(id=identifier, institution=None, candidates=[], format=None,
                  status='needs_institution', issues=[], views={})
    pages, evidence = None, None
    if content[:1024].lstrip().startswith(b'%PDF-'):
        from pypdf import PdfReader
        pdf = PdfReader(BytesIO(content))
        result['format'] = 'pdf'
        if pdf.is_encrypted:
            if not password or not pdf.decrypt(password):
                result.update(status='needs_password', issues=['PDF protegido: introduce su contraseña para procesarlo.'])
                return result
        pages = tuple((p.extract_text(extraction_mode='layout') or '') if '/Contents' in p else '' for p in pdf.pages)
        text = '\n'.join(pages)
        result['page_count'] = len(pages)
        if not text.strip():
            result.update(status='needs_ocr', issues=['PDF sin texto: requiere OCR de páginas; no se ha interpretado como estado vacío.'])
            return result
    else:
        from .imaging import LocalOcr
        evidence = (engine or LocalOcr()).read(content)
        result['format'] = 'image'
        text = '\n'.join(line.text for line in evidence.lines)
        result['ocr'] = plain(evidence)
    found = _candidates(text)
    result['candidates'] = found
    if institution:
        if institution not in found:
            result['issues'] = ['La institución elegida no está acreditada por el contenido.']
            return result
    elif len(found) == 1:
        institution = found[0]
    else:
        result['issues'] = ['Institución no reconocida o ambigua: selecciona una para verificarla.']
        return result
    result['institution'] = institution
    for lane in ('debit', 'investments'):
        if institution in ('bingx', 'pionex') and lane == 'debit':
            result['views'][lane] = dict(status='not_applicable', issues=['No aplica cuenta bancaria de débito.'])
            continue
        reader = reader_for(institution, lane)
        try:
            if evidence is not None:
                class CachedOcr:
                    def read(self, _): return evidence
                preview = reader.read_image(content, engine=CachedOcr())
                mode = 'ocr'
            elif institution in ('bingx', 'pionex'):
                raise ValueError('Este lector requiere una captura de la operación.')
            else:
                try:
                    if institution == 'supertasas':
                        from .supertasas import SuperTasasReader
                        preview = SuperTasasReader(lane).read_pdf(content, password=password)
                    elif institution == 'hey':
                        from .hey import HeyReader
                        preview = HeyReader(lane).read_pdf(content, password=password)
                    elif institution == 'kapital':
                        from .kapital import KapitalReader
                        preview = KapitalReader(lane).read_pdf(content, password=password)
                    elif institution == 'doopla':
                        from .doopla import DooplaReader
                        preview = DooplaReader(lane).read_pdf(content, password=password)
                    elif institution == 'fintual' and lane == 'investments':
                        from .fintual import FintualInvestmentReader
                        preview = FintualInvestmentReader().read_pdf(content, password=password)
                    else:
                        preview = reader.read_reconciled_pdf(content)
                    mode = 'specialized'
                except ValueError as specialized_error:
                    preview = reader.read_pages(pages, identifier)
                    mode = 'documentary'
                    fallback_issue = str(specialized_error)
            data = plain(preview)
            issues = list(getattr(preview, 'issues', ()))
            for attr in ('detail_issues', 'timing_issues'):
                issues.extend(getattr(preview, attr, ()))
            if mode == 'documentary':
                issues.insert(0, 'Lectura documental; conciliación específica pendiente: '+fallback_issue)
            # Plata contiene ambas vistas; guardar solo la seleccionada y el agregado.
            if institution == 'plata' and mode == 'specialized':
                data = {k: v for k, v in data.items() if k not in ('debit', 'investments')}
                data.update(summary=plain(preview.summary), rows=plain(preview.rows),
                            account_fingerprint=preview.account_fingerprint)
            result['views'][lane] = dict(status='extracted', mode=mode, data=data,
                issues=list(dict.fromkeys(issues)), reconciled=bool(getattr(preview, 'reconciled', False)),
                ready_to_import=False)
        except ValueError as error:
            result['views'][lane] = dict(status='unreadable', issues=[str(error)])
    result['status'] = 'pending_review'
    return result


class Inbox:
    """Archivo y resultados en una transacción SQLite, separado del ledger existente."""
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS intake_files (
                id TEXT PRIMARY KEY, filename TEXT NOT NULL, original BLOB NOT NULL,
                result TEXT NOT NULL, revision INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS intake_reviews (
                seq INTEGER PRIMARY KEY, document_id TEXT NOT NULL,
                revision INTEGER NOT NULL, decision TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS intake_groups (institution TEXT PRIMARY KEY, category TEXT NOT NULL);
        ''')

    def close(self): self.db.close()
    def __enter__(self): return self
    def __exit__(self, *args): self.close()

    def catalog(self):
        groups = GROUPS | dict(self.db.execute('SELECT institution,category FROM intake_groups'))
        return dict(categories=CATEGORIES, institutions=[dict(key=k, name=n,
            category=groups.get(k, 'Por clasificar')) for k, n in NAMES.items()])

    def set_group(self, institution, category):
        if institution not in NAMES or category not in CATEGORIES:
            raise ValueError('Institución o categoría no admitida')
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO intake_groups VALUES(?,?)', (institution, category))

    def upload(self, content, filename, *, institution=None, password=None, engine=None):
        if not isinstance(content, bytes) or not content or len(content) > MAX_UPLOAD:
            raise ValueError('Archivo vacío o mayor de 32 MiB')
        identifier = sha256(content).hexdigest()
        previous = self.db.execute('SELECT id FROM intake_files WHERE id=?', (identifier,)).fetchone()
        if previous:
            return self.get(identifier) | {'duplicate': True}
        try:
            result = analyze(content, institution=institution, password=password, engine=engine)
        except ValueError as error:
            result = dict(id=identifier, institution=None, candidates=[], format=None,
                          status='unreadable', issues=[str(error)], views={})
        filename = str(filename).replace('\\', '/').split('/')[-1][:200] or 'documento'
        with self.db:
            self.db.execute('INSERT INTO intake_files(id,filename,original,result,revision) VALUES(?,?,?,?,1)',
                            (identifier, filename, content, json.dumps(result, ensure_ascii=False)))
        return self.get(identifier) | {'duplicate': False}

    def reprocess(self, identifier, *, expected_revision, institution=None, password=None, engine=None):
        row = self.db.execute('SELECT * FROM intake_files WHERE id=?', (identifier,)).fetchone()
        if row is None: raise ValueError('Documento no encontrado')
        if row['revision'] != expected_revision: raise ValueError('Documento cambió: vuelve a abrirlo')
        result = analyze(bytes(row['original']), institution=institution, password=password, engine=engine)
        with self.db:
            changed = self.db.execute('UPDATE intake_files SET result=?,revision=revision+1 WHERE id=? AND revision=?',
                (json.dumps(result, ensure_ascii=False), identifier, expected_revision)).rowcount
            if changed != 1: raise ValueError('Documento cambió: vuelve a abrirlo')
        return self.get(identifier)

    def review(self, identifier, *, expected_revision, decision):
        if decision not in ('reviewed', 'pending'): raise ValueError('Decisión no admitida')
        # Revisar no elimina alertas ni convierte extracción en movimientos del ledger.
        with self.db:
            changed = self.db.execute('UPDATE intake_files SET revision=revision+1 WHERE id=? AND revision=?',
                                     (identifier, expected_revision)).rowcount
            if changed != 1: raise ValueError('Documento cambió o no existe: vuelve a abrirlo')
            self.db.execute('INSERT INTO intake_reviews(document_id,revision,decision) VALUES(?,?,?)',
                            (identifier, expected_revision+1, decision))
        return self.get(identifier)

    def get(self, identifier):
        row = self.db.execute('SELECT id,filename,result,revision,created_at FROM intake_files WHERE id=?', (identifier,)).fetchone()
        if row is None: raise ValueError('Documento no encontrado')
        latest = self.db.execute('SELECT decision FROM intake_reviews WHERE document_id=? AND revision=? ORDER BY seq DESC LIMIT 1',
                                 (identifier, row['revision'])).fetchone()
        return dict(id=row['id'], filename=row['filename'], revision=row['revision'], created_at=row['created_at'],
                    review=latest['decision'] if latest else 'pending', result=json.loads(row['result']))

    def list(self):
        items = []
        for row in self.db.execute('SELECT id FROM intake_files ORDER BY created_at DESC,id'):
            doc = self.get(row['id']); result = doc['result']
            periods = set()
            for view in result['views'].values():
                data = view.get('data', {})
                data = data.get('document_preview') or data
                if data.get('period_start') and data.get('period_end'):
                    periods.add((data['period_start'], data['period_end']))
                periods.update(tuple(x) for x in data.get('periods', []))
            items.append({k: v for k, v in doc.items() if k != 'result'} | dict(
                institution=result['institution'], status=result['status'], format=result['format'],
                periods=sorted(periods), issues=sum(len(v.get('issues', [])) for v in result['views'].values())+len(result['issues'])))
        return items

    def original(self, identifier):
        row = self.db.execute('SELECT original FROM intake_files WHERE id=?', (identifier,)).fetchone()
        if row is None: raise ValueError('Documento no encontrado')
        return bytes(row['original'])
