"""Aceptación de persistencia y auditoría con datos exclusivamente sintéticos."""
from dataclasses import replace
from datetime import date
from decimal import Decimal
import os
from pathlib import Path
import tempfile
import unittest

from finanzas.ledger import Evidence, Kind, Origin
from finanzas.storage import Store, document_id, movement_id
from tests.test_ledger import movement


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.addCleanup(self.store.close)
        self.doc = self.register(b"estado ficticio")
        self.approve(self.doc)

    def register(self, content, **kwargs):
        return self.store.register_document(content, "institucion_ficticia",
                                           date(2026, 1, 1), date(2026, 1, 31), **kwargs)

    def approve(self, doc):
        self.store.review_document(doc, "approved", "revision sintetica completada")

    def m(self, id="op1", **kwargs):
        result = movement(id, **kwargs)
        return replace(result, evidence=Evidence(self.doc, "pagina 1, fila " + id))

    def test_document_fingerprint_ignores_filename_and_blocks_metadata_conflict(self):
        self.assertEqual(self.register(b"estado ficticio"), self.doc)
        self.assertEqual(document_id(b"estado ficticio"), self.doc)
        with self.assertRaises(ValueError):
            self.store.register_document(b"estado ficticio", "otra", date(2026, 1, 1), date(2026, 1, 31))

    def test_unregistered_or_unapproved_document_cannot_enter_ledger(self):
        doc = self.register(b"pendiente")
        for identifier in (doc, "desconocido"):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                self.store.record_many([replace(self.m(), evidence=Evidence(identifier, "p1"))])
        self.assertEqual(self.store.load_ledger().movements, ())

    def test_repeated_import_is_idempotent_including_equivalent_decimal(self):
        self.assertEqual(self.store.record_many([self.m(amount="100.00")]), 1)
        self.assertEqual(self.store.record_many([self.m(amount="100")]), 0)
        self.assertEqual(len(self.store.history("op1")), 1)
        self.assertEqual(len(self.store.evidences("op1", 1)), 1)

    def test_overlapping_documents_share_one_operation_and_preserve_both_sources(self):
        self.store.record_many([self.m()])
        other = self.register(b"estado ficticio solapado")
        self.approve(other)
        second = replace(self.m(), evidence=Evidence(other, "p2 fila 3"))
        self.assertEqual(self.store.record_many([second]), 0)
        self.assertEqual(self.store.load_ledger().external_contributions("MXN"), Decimal("100"))
        self.assertEqual(len(self.store.evidences("op1", 1)), 2)

    def test_stable_id_requires_real_reference_not_document_date_amount_guess(self):
        self.assertEqual(movement_id("banco", "cuenta", "ref1"), movement_id("banco", "cuenta", "ref1"))
        self.assertNotEqual(movement_id("banco", "cuenta", "ref1"), movement_id("banco", "cuenta", "ref2"))
        self.assertNotEqual(movement_id("banco", "cuenta", "ref1"), movement_id("banco", "otra", "ref1"))
        with self.assertRaises(ValueError):
            movement_id("banco", "cuenta", "")

    def test_conflict_does_not_silently_overwrite(self):
        self.store.record_many([self.m()])
        with self.assertRaises(ValueError):
            self.store.record_many([self.m(amount="101")])
        self.assertEqual(self.store.load_ledger().balances()[("ahorro_a", "MXN")], Decimal("100"))

    def test_explicit_correction_preserves_old_value_evidence_and_reason(self):
        self.store.record_many([self.m()])
        self.store.record_many([self.m(amount="101")], corrections={"op1": (1, "importe revisado")})
        history = self.store.history("op1")
        self.assertEqual([m.amount for _, m, _ in history], [Decimal("100"), Decimal("101")])
        self.assertEqual(history[1][2], "importe revisado")
        self.assertEqual(len(self.store.evidences("op1", 1)), 1)
        self.assertEqual(len(self.store.evidences("op1", 2)), 1)
        self.assertEqual(self.store.load_ledger().balances()[("ahorro_a", "MXN")], Decimal("101"))

    def test_stale_revision_is_rejected(self):
        self.store.record_many([self.m()])
        self.store.record_many([self.m(amount="101")], corrections={"op1": (1, "revision uno")})
        with self.assertRaises(ValueError):
            self.store.record_many([self.m(amount="102")], corrections={"op1": (1, "revision obsoleta")})
        self.assertEqual(len(self.store.history("op1")), 2)

    def test_batch_failure_leaves_no_partial_movements_or_evidence(self):
        self.store.record_many([self.m()])
        with self.assertRaises(ValueError):
            self.store.record_many([self.m("new"), self.m(amount="999")])
        self.assertEqual(self.store.history("new"), ())
        self.assertEqual(self.store.evidences("new", 1), ())
        self.assertEqual(len(self.store.load_ledger().movements), 1)

    def test_transfer_corrections_validate_final_state_atomically(self):
        outgoing = self.m("out", kind=Kind.WITHDRAWAL, origin=Origin.OWN_TRANSFER, transfer_id="t")
        incoming = self.m("in", account="ahorro_b", origin=Origin.OWN_TRANSFER, transfer_id="t")
        self.store.record_many([outgoing, incoming])
        with self.assertRaises(ValueError):
            self.store.record_many([replace(outgoing, amount=Decimal("90"))],
                                   corrections={"out": (1, "solo un lado")})
        self.assertEqual(len(self.store.history("out")), 1)
        self.store.record_many([replace(outgoing, amount=Decimal("90")),
                                replace(incoming, amount=Decimal("90"))],
                               corrections={"out": (1, "ambos lados"), "in": (1, "ambos lados")})
        self.assertEqual(self.store.load_ledger().pending_transfers(), ())
        self.assertEqual(self.store.load_ledger().balances()[("ahorro_b", "MXN")], Decimal("90"))

    def test_document_revision_requires_approval_and_does_not_auto_replace_movements(self):
        self.store.record_many([self.m()])
        new = self.register(b"version corregida", supersedes=self.doc)
        with self.assertRaises(ValueError):
            self.store.record_many([replace(self.m(), amount=Decimal("101"), evidence=Evidence(new, "p1"))],
                                   corrections={"op1": (1, "corregido")})
        self.assertEqual(len(self.store.history("op1")), 1)
        self.approve(new)
        self.store.record_many([replace(self.m(), amount=Decimal("101"), evidence=Evidence(new, "p1"))],
                               corrections={"op1": (1, "corregido")})
        self.assertEqual(self.store.history("op1")[1][1].evidence.document_id, new)

    def test_review_history_preserved_and_revocation_does_not_erase_past(self):
        self.store.record_many([self.m()])
        self.store.review_document(self.doc, "rejected", "requiere nueva revision")
        with self.assertRaises(ValueError):
            self.store.record_many([self.m("new")])
        self.assertEqual(len(self.store.review_history(self.doc)), 2)
        self.assertEqual(len(self.store.load_ledger().movements), 1)

    def test_recovery_in_new_connection_preserves_precision_origin_and_pending(self):
        self.store.record_many([
            self.m("crypto", account="wallet_btc", unit="BTC", amount="0.000000000000000000000000001"),
            self.m("pending", origin=Origin.OWN_TRANSFER, transfer_id="unfinished"),
            self.m("zero", kind=Kind.WITHHOLDING, amount="0"),
        ])
        image = self.store.snapshot()
        self.store.close()
        self.store = Store.from_snapshot(image)
        self.addCleanup(self.store.close)
        book = self.store.load_ledger()
        self.assertEqual(book.balances()[("wallet_btc", "BTC")], Decimal("0.000000000000000000000000001"))
        self.assertEqual(book.pending_transfers(), ("unfinished",))
        self.assertEqual(book.withholding_recorded("MXN"), Decimal("0"))

    def test_backup_preserves_history_and_restores_to_a_new_store(self):
        self.store.record_many([self.m()])
        self.store.record_many([self.m(amount="101")], corrections={"op1": (1, "correccion")})
        with Store() as backup:
            self.store.backup_to(backup)
            self.assertEqual(backup.history("op1"), self.store.history("op1"))
            self.assertEqual(backup.evidences("op1", 1), self.store.evidences("op1", 1))
            self.assertEqual(backup.review_history(self.doc), self.store.review_history(self.doc))
            with Store.from_snapshot(backup.snapshot()) as restored:
                self.assertEqual(restored.load_ledger().balances(), self.store.load_ledger().balances())

    def test_backup_never_overwrites_nonempty_destination(self):
        with Store() as backup:
            backup.register_document(b"no borrar", "otra", date(2026, 1, 1), date(2026, 1, 2))
            with self.assertRaises(ValueError):
                self.store.backup_to(backup)
            backup.review_document(document_id(b"no borrar"), "approved", "conservar")

    def test_document_cannot_supersede_itself(self):
        with self.assertRaises(ValueError):
            self.register(b"auto referencia", supersedes=document_id(b"auto referencia"))

    def test_corrupt_snapshot_rejected(self):
        with self.assertRaises(Exception):
            Store.from_snapshot(b"esto no es sqlite")

    def test_duplicate_ids_inside_batch_rejected(self):
        with self.assertRaises(ValueError):
            self.store.record_many([self.m(), self.m()])
        self.assertEqual(self.store.load_ledger().movements, ())

    def test_document_period_and_correction_reason_are_validated(self):
        with self.assertRaises(ValueError):
            self.store.register_document(b"periodo malo", "banco", date(2026, 2, 1), date(2026, 1, 1))
        self.store.record_many([self.m()])
        with self.assertRaises(ValueError):
            self.store.record_many([self.m(amount="101")], corrections={"op1": (1, "")})

    @unittest.skipIf(os.environ.get("FINANZAS_TEST_NO_DISK") == "1",
                     "Entorno de verificacion sin escritura en disco")
    def test_separate_connections_see_latest_committed_state_and_reject_stale_correction(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "shared.sqlite3")
            with Store(path) as first, Store(path) as second:
                doc = first.register_document(b"dos conexiones", "banco", date(2026, 1, 1), date(2026, 1, 31))
                first.review_document(doc, "approved", "prueba sintetica")
                m = replace(self.m(), evidence=Evidence(doc, "p1"))
                first.record_many([m])
                second.record_many([replace(m, amount=Decimal("101"))],
                                   corrections={"op1": (1, "segunda conexion")})
                with self.assertRaises(ValueError):
                    first.record_many([replace(m, amount=Decimal("102"))],
                                      corrections={"op1": (1, "vista antigua")})
                self.assertEqual(first.load_ledger().external_contributions("MXN"), Decimal("101"))

    @unittest.skipIf(os.environ.get("FINANZAS_TEST_NO_DISK") == "1",
                     "Entorno de verificacion sin escritura en disco")
    def test_file_close_reopen_and_backup_file(self):
        with tempfile.TemporaryDirectory() as directory:
            original = str(Path(directory) / "original.sqlite3")
            backup = str(Path(directory) / "respaldo.sqlite3")
            with Store(original) as store:
                doc = store.register_document(b"prueba disco", "banco", date(2026, 1, 1), date(2026, 1, 31))
                store.review_document(doc, "approved", "prueba sintetica")
                store.record_many([replace(self.m(), evidence=Evidence(doc, "p1"))])
            with Store(original) as store, Store(backup) as destination:
                self.assertEqual(store.load_ledger().external_contributions("MXN"), Decimal("100"))
                store.backup_to(destination)
            with Store(backup) as restored:
                self.assertEqual(restored.load_ledger().external_contributions("MXN"), Decimal("100"))


if __name__ == "__main__":
    unittest.main()
