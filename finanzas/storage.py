"""Persistencia SQLite local con evidencia múltiple y revisiones sin sobrescritura."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
import sqlite3

from .ledger import Evidence, Kind, Ledger, Movement, Origin


def document_id(content: bytes) -> str:
    if not isinstance(content, bytes) or not content:
        raise ValueError("Se requieren los bytes no vacíos del documento")
    return sha256(content).hexdigest()


def movement_id(institution: str, account: str, reference: str) -> str:
    """Referencia institucional estable o identidad explícitamente revisada."""
    if any(not isinstance(v, str) or not v.strip() for v in (institution, account, reference)):
        raise ValueError("Institución, cuenta y referencia estable requeridas")
    return sha256(json.dumps([institution, account, reference], ensure_ascii=False).encode()).hexdigest()


def _dump(m):
    return json.dumps(dict(id=m.id, account=m.account, unit=m.unit,
        effective_date=m.effective_date.isoformat(), kind=m.kind.value,
        amount=str(m.amount), document_id=m.evidence.document_id,
        locator=m.evidence.locator, origin=m.origin.value if m.origin else None,
        transfer_id=m.transfer_id), sort_keys=True, ensure_ascii=False)


def _read(payload):
    p = json.loads(payload)
    return Movement(id=p["id"], account=p["account"], unit=p["unit"],
        effective_date=date.fromisoformat(p["effective_date"]), kind=Kind(p["kind"]),
        amount=Decimal(p["amount"]), evidence=Evidence(p["document_id"], p["locator"]),
        origin=Origin(p["origin"]) if p["origin"] else None, transfer_id=p["transfer_id"])


_SCHEMA = """
CREATE TABLE documents (
    id TEXT PRIMARY KEY NOT NULL,
    institution TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    supersedes TEXT REFERENCES documents(id),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE reviews (
    seq INTEGER PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id),
    decision TEXT NOT NULL CHECK(decision IN ('approved','rejected','pending')),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE revisions (
    seq INTEGER PRIMARY KEY,
    movement_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK(version > 0),
    payload TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(movement_id, version)
);
CREATE TABLE evidence (
    movement_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    document_id TEXT NOT NULL REFERENCES documents(id),
    locator TEXT NOT NULL,
    PRIMARY KEY(movement_id,version,document_id,locator),
    FOREIGN KEY(movement_id,version) REFERENCES revisions(movement_id,version)
);
CREATE INDEX reviews_document ON reviews(document_id,seq);
"""


class Store:
    """Un escritor por transacción. Instancias separadas releen el estado al escribir."""
    def __init__(self, path=":memory:"):
        self._db = sqlite3.connect(path, isolation_level=None, timeout=5)
        try:
            self._db.execute("PRAGMA foreign_keys=ON")
            version = self._db.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                tables = self._db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
                if tables:
                    raise ValueError("No es una base vacía de MIS-FINANZAS-IA")
                self._db.executescript("BEGIN IMMEDIATE;\n" + _SCHEMA +
                                       "\nPRAGMA user_version=1;\nCOMMIT;")
            elif version != 1:
                raise ValueError("Versión de base no admitida; no se modifica")
        except BaseException:
            self._db.close()
            raise

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @contextmanager
    def _transaction(self):
        if self._db.in_transaction:
            # Permite una confirmación mayor (documento, revisión y lote) atómica.
            number = getattr(self, '_savepoint_number', 0) + 1
            self._savepoint_number = number
            name = 'finanzas_' + str(number)
            self._db.execute('SAVEPOINT ' + name)
            try:
                yield
                self._db.execute('RELEASE ' + name)
            except BaseException:
                self._db.execute('ROLLBACK TO ' + name)
                self._db.execute('RELEASE ' + name)
                raise
            return
        self._db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self._db.execute("COMMIT")
        except BaseException:
            self._db.execute("ROLLBACK")
            raise

    def register_document(self, content: bytes, institution: str,
                          period_start: date, period_end: date, supersedes=None):
        if not isinstance(institution, str) or not institution.strip():
            raise ValueError("Institución requerida")
        if type(period_start) is not date or type(period_end) is not date or period_end < period_start:
            raise ValueError("Período documental inválido")
        identifier = document_id(content)
        if supersedes == identifier:
            raise ValueError("Un documento no puede sustituirse a sí mismo")
        metadata = (institution, period_start.isoformat(), period_end.isoformat(), supersedes)
        with self._transaction():
            previous = self._db.execute(
                "SELECT institution,period_start,period_end,supersedes FROM documents WHERE id=?",
                (identifier,)).fetchone()
            if previous is not None:
                if previous != metadata:
                    raise ValueError("Documento existente con metadatos distintos; revisar")
                return identifier
            self._db.execute("INSERT INTO documents(id,institution,period_start,period_end,supersedes) VALUES(?,?,?,?,?)",
                             (identifier, *metadata))
        return identifier

    def review_document(self, identifier, decision, reason):
        if decision not in ("approved", "rejected", "pending") or not isinstance(reason, str) or not reason.strip():
            raise ValueError("Decisión y motivo requeridos")
        with self._transaction():
            if not self._db.execute("SELECT 1 FROM documents WHERE id=?", (identifier,)).fetchone():
                raise ValueError("Documento no registrado")
            previous = self._db.execute(
                "SELECT decision,reason FROM reviews WHERE document_id=? ORDER BY seq DESC LIMIT 1",
                (identifier,)).fetchone()
            if previous != (decision, reason):
                self._db.execute("INSERT INTO reviews(document_id,decision,reason) VALUES(?,?,?)",
                                 (identifier, decision, reason))

    def _current(self):
        rows = self._db.execute("""
            SELECT r.movement_id,r.version,r.payload FROM revisions r
            JOIN (SELECT movement_id,MAX(version) AS version FROM revisions GROUP BY movement_id) c
            ON r.movement_id=c.movement_id AND r.version=c.version ORDER BY r.seq
        """).fetchall()
        return {identifier: (version, _read(payload)) for identifier, version, payload in rows}

    def load_ledger(self):
        ledger = Ledger()
        for _, movement in self._current().values():
            ledger.record(movement)
        return ledger

    def record_many(self, movements, *, corrections=None):
        """Confirma lote completo; corrections={id: (versión_esperada, motivo)}."""
        movements = tuple(movements)
        corrections = dict(corrections or {})
        if any(not isinstance(m, Movement) for m in movements):
            raise ValueError("El lote requiere movimientos validados")
        if len({m.id for m in movements}) != len(movements):
            raise ValueError("Revisar IDs repetidos dentro del lote")
        if set(corrections) - {m.id for m in movements}:
            raise ValueError("Corrección sin movimiento en el lote")
        with self._transaction():
            current = self._current()
            proposed = {key: m for key, (_, m) in current.items()}
            writes = []
            for movement in movements:
                decision = self._db.execute(
                    "SELECT decision FROM reviews WHERE document_id=? ORDER BY seq DESC LIMIT 1",
                    (movement.evidence.document_id,)).fetchone()
                if decision != ("approved",):
                    raise ValueError("La evidencia requiere documento registrado y aprobado")
                previous = current.get(movement.id)
                correction = corrections.get(movement.id)
                if correction is not None:
                    if (not isinstance(correction, tuple) or len(correction) != 2
                        or type(correction[0]) is not int or not isinstance(correction[1], str)
                        or not correction[1].strip()):
                        raise ValueError("Corrección requiere versión esperada y motivo")
                    if previous is None or previous[0] != correction[0]:
                        raise ValueError("Versión desactualizada; releer antes de corregir")
                same = previous is not None and replace(previous[1], evidence=movement.evidence) == movement
                if previous is not None and not same and correction is None:
                    raise ValueError("Conflicto: usar corrección explícita, no sobrescribir")
                if previous is None and correction is not None:
                    raise ValueError("No se puede corregir un registro inexistente")
                version = previous[0] if same else (previous[0] + 1 if previous else 1)
                reason = correction[1] if correction else "registro inicial revisado"
                writes.append((movement, version, not same, reason))
                proposed[movement.id] = movement
            # Valida el estado final, también para correcciones de ambos lados de un traslado.
            ledger = Ledger()
            for movement in proposed.values():
                ledger.record(movement)
            for movement, version, changed, reason in writes:
                if changed:
                    self._db.execute(
                        "INSERT INTO revisions(movement_id,version,payload,reason) VALUES(?,?,?,?)",
                        (movement.id, version, _dump(movement), reason))
                self._db.execute(
                    "INSERT OR IGNORE INTO evidence(movement_id,version,document_id,locator) VALUES(?,?,?,?)",
                    (movement.id, version, movement.evidence.document_id, movement.evidence.locator))
            return sum(changed for _, _, changed, _ in writes)

    def history(self, identifier):
        return tuple((version, _read(payload), reason) for version, payload, reason in self._db.execute(
            "SELECT version,payload,reason FROM revisions WHERE movement_id=? ORDER BY version", (identifier,)))

    def evidences(self, identifier, version):
        return tuple(Evidence(doc, locator) for doc, locator in self._db.execute(
            "SELECT document_id,locator FROM evidence WHERE movement_id=? AND version=? ORDER BY document_id,locator",
            (identifier, version)))

    def review_history(self, identifier):
        return tuple(self._db.execute(
            "SELECT decision,reason FROM reviews WHERE document_id=? ORDER BY seq", (identifier,)))

    def snapshot(self):
        """Imagen SQLite; contiene datos privados, debe custodiarse fuera de Git."""
        return self._db.serialize()

    @classmethod
    def from_snapshot(cls, data):
        store = cls()
        try:
            store._db.deserialize(data)
            store._db.execute("PRAGMA foreign_keys=ON")
            if store._db.execute("PRAGMA user_version").fetchone() != (1,):
                raise ValueError("Versión de copia no admitida")
            if store._db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise ValueError("Copia inconsistente")
            if store._db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Copia con referencias inválidas")
            store.load_ledger()
            return store
        except BaseException:
            store.close()
            raise

    def backup_to(self, destination):
        """Copia consistente a otro Store vacío; comprueba y escribe atómicamente."""
        if not isinstance(destination, Store) or destination is self:
            raise ValueError("Destino distinto requerido")
        clone = sqlite3.connect(":memory:")
        try:
            self._db.backup(clone)
            with destination._transaction():
                for table in ("documents", "reviews", "revisions", "evidence"):
                    if destination._db.execute("SELECT 1 FROM " + table + " LIMIT 1").fetchone():
                        raise ValueError("El destino debe estar vacío")
                for table in ("documents", "reviews", "revisions", "evidence"):
                    rows = clone.execute("SELECT * FROM " + table).fetchall()
                    count = len(clone.execute("PRAGMA table_info(" + table + ")").fetchall())
                    destination._db.executemany(
                        "INSERT INTO " + table + " VALUES(" + ",".join("?" for _ in range(count)) + ")", rows)
        finally:
            clone.close()
