"""Casos sintéticos de aceptación; no incluyen estados ni datos personales."""
import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal as D, getcontext
from finanzas.ledger import Evidence, Kind, Ledger, Movement, Origin


def movement(id, account="ahorro_a", kind=Kind.CONTRIBUTION, amount="100", **kwargs):
    return Movement(id=id, account=account, unit=kwargs.pop("unit", "MXN"),
                    effective_date=kwargs.pop("effective_date", date(2026, 1, 5)),
                    kind=kind, amount=D(amount), evidence=Evidence("documento_sintetico", id),
                    origin=kwargs.pop("origin", Origin.EXTERNAL if kind in
                                      (Kind.CONTRIBUTION, Kind.WITHDRAWAL) else None), **kwargs)


class LedgerTests(unittest.TestCase):
    def test_security_receipt_changes_cash_without_capital_or_interest_assumption(self):
        book=Ledger();book.record(movement('cobro',kind=Kind.SECURITY_PROCEEDS,amount='11'))
        self.assertEqual(book.balances()[('ahorro_a','MXN')],D('11'))
        self.assertEqual(book.external_contributions('MXN'),0);self.assertEqual(book.interest_received('MXN'),0)
        self.assertIsNone(book.withholding_recorded('MXN'))

    def test_dividend_and_foreign_tax_do_not_become_interest_or_mexican_isr(self):
        book=Ledger();book.record(movement('div',kind=Kind.DIVIDEND,amount='2',unit='USD'))
        book.record(movement('nra',kind=Kind.FOREIGN_WITHHOLDING,amount='1',unit='USD'))
        self.assertEqual(book.balances()[('ahorro_a','USD')],D('1'))
        self.assertEqual(book.interest_received('USD'),0);self.assertIsNone(book.withholding_recorded('USD'))
        self.assertEqual(book.external_contributions('USD'),0)

    def test_foreign_withholding_zero_requires_explicit_tax_kind(self):
        self.assertEqual(movement('zero',kind=Kind.FOREIGN_WITHHOLDING,amount='0').signed_amount,0)
        with self.assertRaises(ValueError):movement('zero-div',kind=Kind.DIVIDEND,amount='0')

    def test_vat_and_rewards_change_cash_without_capital_interest_or_isr(self):
        book=Ledger()
        for name,kind,amount in [('iva',Kind.VAT_RECEIVED,'.32'),('entero',Kind.VAT_PAID,'.64'),('premio',Kind.REWARD,'1')]:
            book.record(movement(name,kind=kind,amount=amount))
        self.assertEqual(book.balances()[('ahorro_a','MXN')],D('.68'))
        self.assertEqual(book.external_contributions('MXN'),0);self.assertEqual(book.interest_received('MXN'),0)
        self.assertIsNone(book.withholding_recorded('MXN'));self.assertEqual(book.pending_origins(),())

    def test_fee_refund_restores_cash_without_external_capital_or_interest(self):
        book=Ledger();book.record(movement('cargo',kind=Kind.FEE,amount='.01'))
        book.record(movement('devolucion',kind=Kind.FEE_REFUND,amount='.01'))
        self.assertEqual(book.balances()[('ahorro_a','MXN')],0)
        self.assertEqual(book.external_contributions('MXN'),0)
        self.assertEqual(book.interest_received('MXN'),0)
        self.assertEqual(book.pending_origins(),())

    def test_fee_refund_requires_positive_amount_and_no_capital_origin(self):
        for args in ({'amount':'0'},{'amount':'-1'},{'origin':Origin.EXTERNAL}):
            with self.assertRaises(ValueError):movement('invalid',kind=Kind.FEE_REFUND,**args)

    def test_transfer_contribution_at_destination_without_inflating_external_capital(self):
        book = Ledger()
        for m in (movement("aporte"), movement("salida", kind=Kind.WITHDRAWAL, amount="40",
                    origin=Origin.OWN_TRANSFER, transfer_id="t1"),
                  movement("entrada", account="ahorro_b", amount="40",
                    origin=Origin.OWN_TRANSFER, transfer_id="t1")):
            book.record(m)
        self.assertEqual(book.balances(), {("ahorro_a", "MXN"): D("60"), ("ahorro_b", "MXN"): D("40")})
        self.assertEqual(book.external_contributions("MXN"), D("100"))
        self.assertEqual(book.pending_transfers(), ())

    def test_missing_statement_preserves_real_side_until_counterpart_arrives(self):
        book = Ledger()
        entry = movement("entrada", origin=Origin.OWN_TRANSFER, transfer_id="t1")
        book.record(entry)
        self.assertEqual(book.pending_transfers(), ("t1",))
        self.assertEqual(book.balances()[("ahorro_a", "MXN")], D("100"))
        book.record(movement("salida", account="ahorro_b", kind=Kind.WITHDRAWAL,
                             origin=Origin.OWN_TRANSFER, transfer_id="t1",
                             effective_date=date(2026, 1, 4)))
        self.assertEqual(book.pending_transfers(), ())

    def test_incompatible_counterpart_is_rejected_without_erasing_pending_side(self):
        for changes in ({"amount": "99"}, {"unit": "USD"}, {"account": "ahorro_a"},
                        {"kind": Kind.CONTRIBUTION}, {"origin": Origin.REINVESTMENT}):
            with self.subTest(changes=changes):
                book = Ledger()
                book.record(movement("in", origin=Origin.OWN_TRANSFER, transfer_id="t"))
                args = dict(account="ahorro_b", kind=Kind.WITHDRAWAL,
                            origin=Origin.OWN_TRANSFER, transfer_id="t")
                args.update(changes)
                with self.assertRaises(ValueError):
                    book.record(movement("out", **args))
                self.assertEqual(len(book.movements), 1)
                self.assertEqual(book.pending_transfers(), ("t",))

    def test_reinvestment_moves_net_cash_and_does_not_recognize_interest_twice(self):
        book = Ledger()
        events = [
            movement("initial"),
            movement("yield", kind=Kind.INTEREST, amount="10"),
            movement("tax", kind=Kind.WITHHOLDING, amount="1"),
            movement("renew_out", kind=Kind.WITHDRAWAL, amount="109",
                     origin=Origin.REINVESTMENT, transfer_id="renew"),
            movement("renew_in", account="contrato_nuevo", amount="109",
                     origin=Origin.REINVESTMENT, transfer_id="renew")]
        for m in events:
            book.record(m)
        self.assertEqual(book.interest_received("MXN"), D("10"))
        self.assertEqual(book.withholding_recorded("MXN"), D("1"))
        self.assertEqual(book.external_contributions("MXN"), D("100"))
        self.assertEqual(book.balances()[("contrato_nuevo", "MXN")], D("109"))

    def test_cashback_is_contribution_with_its_own_origin_not_interest(self):
        book = Ledger()
        book.record(movement("cashback", amount="3", origin=Origin.CASHBACK))
        self.assertEqual(book.external_contributions("MXN"), D("3"))
        self.assertEqual(book.interest_received("MXN"), D("0"))
        self.assertEqual(book.movements[0].origin, Origin.CASHBACK)

    def test_idempotence_and_conflict_never_silently_overwrite(self):
        book = Ledger()
        m = movement("stable_id")
        self.assertTrue(book.record(m))
        self.assertFalse(book.record(m))
        with self.assertRaises(ValueError):
            book.record(replace(m, amount=D("101")))
        self.assertEqual(book.balances()[("ahorro_a", "MXN")], D("100"))

    def test_unknown_withholding_is_distinct_from_documented_zero(self):
        book = Ledger()
        self.assertIsNone(book.withholding_recorded("MXN"))
        book.record(movement("zero", kind=Kind.WITHHOLDING, amount="0"))
        self.assertEqual(book.withholding_recorded("MXN"), D("0"))

    def test_unknown_origin_is_kept_pending_not_counted_as_external(self):
        book = Ledger()
        book.record(movement("unknown", origin=Origin.UNKNOWN))
        self.assertEqual(book.pending_origins(), ("unknown",))
        self.assertEqual(book.external_contributions("MXN"), D("0"))
        self.assertEqual(book.balances()[("ahorro_a", "MXN")], D("100"))

    def test_opening_balance_is_not_new_contribution(self):
        book = Ledger()
        book.record(movement("opening", kind=Kind.OPENING, amount="500"))
        self.assertEqual(book.external_contributions("MXN"), D("0"))
        self.assertEqual(book.balances()[("ahorro_a", "MXN")], D("500"))

    def test_units_and_crypto_precision_are_kept_separate(self):
        book = Ledger()
        book.record(movement("peso", amount="1"))
        book.record(movement("crypto", account="wallet_btc", unit="BTC", amount="0.00000001"))
        self.assertEqual(book.balances()[("wallet_btc", "BTC")], D("0.00000001"))
        with self.assertRaises(ValueError):
            book.record(movement("wrong_unit", unit="BTC"))

    def test_effective_date_controls_balance_not_import_order(self):
        book = Ledger()
        book.record(movement("later", effective_date=date(2026, 1, 20)))
        book.record(movement("earlier", amount="20", effective_date=date(2026, 1, 1)))
        self.assertEqual(book.balances(date(2026, 1, 10))[("ahorro_a", "MXN")], D("20"))

    def test_invalid_amounts_and_incomplete_provenance_are_rejected(self):
        for amount in ("NaN", "Infinity", "-1", "0"):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                movement("bad", amount=amount)
        with self.assertRaises(ValueError):
            replace(movement("bad"), amount=1.25)
        with self.assertRaises(ValueError):
            Evidence("", "p1")

    def test_context_does_not_round_large_crypto_amounts(self):
        book = Ledger()
        book.record(movement("large", amount="12345678901234567890.1234567890123456"))
        book.record(movement("small", amount="0.0000000000000001"))
        old = getcontext().prec
        try:
            getcontext().prec = 8
            self.assertEqual(book.balances()[("ahorro_a", "MXN")],
                             D("12345678901234567890.1234567890123457"))
        finally:
            getcontext().prec = old

    def test_withdrawal_keeps_precision_under_a_small_global_context(self):
        book = Ledger()
        book.record(movement("out", kind=Kind.WITHDRAWAL, amount="1234567890.123456789"))
        old = getcontext().prec
        try:
            getcontext().prec = 8
            self.assertEqual(book.balances()[("ahorro_a", "MXN")], D("-1234567890.123456789"))
        finally:
            getcontext().prec = old

    def test_noncapital_movements_cannot_smuggle_an_origin(self):
        with self.assertRaises(ValueError):
            movement("interest", kind=Kind.INTEREST, origin="capital_externo")

    def test_third_leg_cannot_reuse_a_reconciled_transfer(self):
        book = Ledger()
        book.record(movement("a", origin=Origin.OWN_TRANSFER, transfer_id="t"))
        book.record(movement("b", account="ahorro_b", kind=Kind.WITHDRAWAL,
                             origin=Origin.OWN_TRANSFER, transfer_id="t"))
        with self.assertRaises(ValueError):
            book.record(movement("c", account="ahorro_c", origin=Origin.OWN_TRANSFER, transfer_id="t"))


if __name__ == "__main__":
    unittest.main()
