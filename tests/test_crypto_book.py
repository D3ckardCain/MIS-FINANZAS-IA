"""Registro cripto ficticio: identidades, activos, comisiones y observaciones."""
from pathlib import Path
import copy
import tempfile
import unittest
from unittest.mock import patch

from finanzas.crypto_book import CryptoBook
from finanzas.book import FinancialBook
from finanzas.intake import Inbox
from tests.test_crypto_images import spot
from tests.test_images import picture,evidence,FixedEngine
from tests import test_intake


def capture(platform='BingX',extra=''):
    lines=spot(platform)+([extra] if extra else [])
    return picture(lines),FixedEngine(evidence(lines))


def review(**changes):
    data=dict(account='Cuenta principal',kind='spot_buy',occurred_at='2026-01-05T12:00:00+00:00',status='executed',verified=True,
        order_id='Order-AbC-001',trade_id='Fill-XyZ-001',base_asset='BTC',quote_asset='USDT',quantity='0.0025',quote_amount='75.00',fee_amount='0.03',fee_asset='USDT')
    data.update(changes);return data


def yield_review():
    return dict(account='Cuenta principal',kind='yield',occurred_at='2026-01-06T12:00:00Z',status='paid',verified=True,
        transaction_id='pago-FICTICIO-001',asset='USDT',amount='0.25',fee_amount='0',fee_asset='USDT')


def derivative_review():
    return dict(account='Cuenta principal',kind='derivative',occurred_at='2026-01-06T12:00:00Z',status='executed',verified=True,
        order_id='orden-FICTICIA',trade_id='ejecucion-FICTICIA',pair='BTC/USDT',contracts='2',contracts_unit='CONTRACTS',
        settlement_asset='USDT',realized_pnl='-3',unrealized_pnl='8',funding='-0.02',fee_amount='0.01',fee_asset='USDT')


def bot_review():
    return dict(account='Cuenta principal',kind='bot_summary',occurred_at='2026-01-06T12:00:00Z',status='snapshot',verified=True,
        bot_id='bot-FICTICIO',profit_amount='5',asset='USDT')


class CryptoBookTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'bandeja.sqlite3'
        self.doc=self.upload();self.book=CryptoBook(self.path);self.addCleanup(self.book.close)

    def upload(self,platform='BingX',extra=''):
        raw,engine=capture(platform,extra)
        with Inbox(self.path) as inbox:return inbox.upload(raw,'captura-FICTICIA.png',engine=engine)

    def confirm(self,doc=None,r=None):
        doc=doc or self.doc;r=r or review();p=self.book.preview(doc['id'],review=r,revision=doc['revision'])
        self.assertTrue(p['can_confirm'],p['issues'])
        return self.book.confirm(doc['id'],revision=doc['revision'],review=r,plan_hash=p['plan_hash'])

    def test_ocr_is_candidate_only_and_review_required(self):
        p=self.book.preview(self.doc['id']);self.assertFalse(p['can_confirm']);self.assertTrue(p['candidates'])
        self.assertEqual(self.book.summary()['operations'],[])
        p=self.book.preview(self.doc['id'],review=review(verified=False));self.assertFalse(p['can_confirm'])

    def test_buy_records_native_flows_and_fee_without_bank_balance_or_mexican_income(self):
        result=self.confirm();s=self.book.summary()
        self.assertEqual(len(s['operations']),1);self.assertEqual(s['documents'],1)
        changes={r['asset']:r['recorded_change'] for r in s['asset_changes']};self.assertEqual(changes,dict(BTC='0.0025',USDT='-75.03'))
        self.assertEqual(result['operation']['account'],'cuenta principal')
        with FinancialBook(self.path) as bank:self.assertEqual(bank.summary()['documents'],0)
        self.assertNotIn('balance',s);self.assertNotIn('realized_gain',s)

    def test_sell_and_fee_in_third_asset_do_not_convert_or_merge_units(self):
        self.confirm(r=review(kind='spot_sell',fee_amount='0.1',fee_asset='BNB'))
        changes={r['asset']:r['recorded_change'] for r in self.book.summary()['asset_changes']}
        self.assertEqual(changes,dict(BTC='-0.0025',USDT='75',BNB='-0.1'))

    def test_fee_missing_is_unknown_and_explicit_zero_is_distinct(self):
        self.confirm(r=review(fee_amount=None,fee_asset=None));s=self.book.summary()
        self.assertEqual(s['unknown_fee_operations'],1);self.assertIsNone(s['operations'][0]['fee_amount'])
        other=self.upload(extra='segunda ejecución');self.confirm(other,review(trade_id='Fill-002',fee_amount='0.00',fee_asset='BTC'))
        self.assertEqual(self.book.summary()['unknown_fee_operations'],1)
        self.assertEqual(next(o['fee_amount'] for o in self.book.summary()['operations'] if o['trade_id']=='Fill-002'),'0')

    def test_same_fill_two_images_add_evidence_not_another_operation(self):
        first=self.confirm();crop=self.upload(extra='Variante ficticia recortada')
        p=self.book.preview(crop['id'],review=review(quote_amount='75',quantity='0.0025000'))
        self.assertTrue(p['duplicate_operation']);self.confirm(crop,review(quote_amount='75',quantity='0.0025000'))
        s=self.book.summary();self.assertEqual(len(s['operations']),1);self.assertEqual(s['documents'],2)
        self.assertEqual(len(s['operations'][0]['sources']),2)
        self.assertEqual(s['operations'][0]['id'],first['operation_id'])

    def test_same_order_different_fills_and_accounts_remain_distinct(self):
        self.confirm()
        for i,r in enumerate((review(trade_id='Fill-002'),review(account='Otra subcuenta'))):self.confirm(self.upload(extra='distinta '+str(i)),r)
        self.assertEqual(len(self.book.summary()['operations']),3)
        self.assertEqual({r['account'] for r in self.book.summary()['asset_changes']},{'cuenta principal','otra subcuenta'})

    def test_platforms_and_usd_usdt_remain_separate(self):
        self.confirm();pionex=self.upload('Pionex');self.confirm(pionex,review(quote_asset='USD',fee_asset='USD'))
        s=self.book.summary();self.assertEqual(len(s['operations']),2)
        self.assertEqual({r['asset'] for r in s['asset_changes']},{'BTC','USDT','USD'})
        self.assertEqual({r['platform'] for r in s['asset_changes']},{'bingx','pionex'})

    def test_conflicting_same_identity_cannot_overwrite_or_double_values(self):
        self.confirm();crop=self.upload(extra='Conflicto ficticio');p=self.book.preview(crop['id'],review=review(quantity='0.003'))
        self.assertFalse(p['can_confirm']);self.assertTrue(any('identidad' in i for i in p['issues']))
        with self.assertRaises(ValueError):self.book.confirm(crop['id'],revision=1,review=review(quantity='0.003'),plan_hash='fake')
        self.assertEqual(self.book.summary()['documents'],1)

    def test_status_order_only_unknown_units_and_invalid_numbers_block(self):
        for r in (review(trade_id=''),review(status='cancelled'),review(base_asset='USDT'),review(quantity='NaN'),review(quantity=0.2),
                  review(quantity='-1'),review(quote_amount='0'),review(fee_amount='-0.01'),review(fee_amount='0',fee_asset=None),review(occurred_at='2026-01-05T12:00:00'),review(occurred_at='2026-01-05T12:00:00.0000001Z')):
            self.assertFalse(self.book.preview(self.doc['id'],review=r)['can_confirm'],r)
        r=review();r['inventado']='0';self.assertFalse(self.book.preview(self.doc['id'],review=r)['can_confirm'])

    def test_offset_required_and_equivalent_instants_deduplicate_without_guessing_user_zone(self):
        self.confirm();crop=self.upload(extra='Misma hora con desplazamiento explícito')
        self.confirm(crop,review(occurred_at='2026-01-05T05:00:00-07:00'))
        self.assertEqual(len(self.book.summary()['operations']),1)
        self.assertEqual(self.book.summary()['operations'][0]['occurred_at'],'2026-01-05T12:00:00+00:00')

    def test_precision_preserved_beyond_float_and_default_decimal_context(self):
        quantity='0.123456789012345678901234567890';self.confirm(r=review(quantity=quantity,fee_amount='0.000000000000000000000000000001',fee_asset='BTC'))
        delta=next(r['recorded_change'] for r in self.book.summary()['asset_changes'] if r['asset']=='BTC')
        self.assertEqual(delta,'0.123456789012345678901234567889')

    def test_yield_paid_transaction_changes_only_native_asset_without_sale(self):
        self.confirm(r=yield_review());s=self.book.summary()
        self.assertEqual(s['operations'][0]['kind'],'yield');self.assertEqual(s['asset_changes'][0]['recorded_change'],'0.25')
        self.assertEqual(s['asset_changes'][0]['asset'],'USDT')

    def test_derivative_and_bot_pnl_are_observations_not_spot_balances_or_yield(self):
        self.confirm(r=derivative_review());self.confirm(self.upload(extra='Resumen ficticio bot'),bot_review())
        s=self.book.summary();self.assertEqual(s['asset_changes'],[])
        self.assertEqual({r['kind'] for r in s['operations']},{'derivative','bot_summary'})
        self.assertTrue(all(not r['effects'] for r in s['operations']))
        self.assertEqual(next(r['realized_pnl'] for r in s['operations'] if r['kind']=='derivative'),'-3')

    def test_missing_pnl_unit_and_unknown_bot_profit_do_not_turn_into_zero(self):
        r=derivative_review();r['settlement_asset']=None
        self.assertFalse(self.book.preview(self.doc['id'],review=r)['can_confirm'])
        r=bot_review();r.update(profit_amount=None,asset=None);self.confirm(r=r)
        self.assertIsNone(self.book.summary()['operations'][0]['profit_amount'])

    def test_failed_evidence_write_rolls_back_operation_then_retry_reopen_is_idempotent(self):
        original=self.book._save_evidence
        def fail(*args):original(*args);raise ValueError('Fallo ficticio')
        with patch.object(self.book,'_save_evidence',side_effect=fail):
            with self.assertRaises(ValueError):self.confirm()
        self.assertEqual(self.book.summary()['documents'],0);self.assertEqual(self.book.summary()['operations'],[])
        self.confirm();self.assertTrue(self.book.confirm(self.doc['id'],revision=1,review=None,plan_hash='retry')['duplicate'])
        with CryptoBook(self.path) as reopened:self.assertEqual(reopened.summary()['documents'],1)

    def test_revision_hash_and_new_operation_invalidate_stale_plan(self):
        p=self.book.preview(self.doc['id'],review=review())
        with self.assertRaises(ValueError):self.book.confirm(self.doc['id'],revision=1,review=review(quote_amount='76'),plan_hash=p['plan_hash'])
        self.confirm(self.upload(extra='Otra operación'),review(trade_id='Fill-002'))
        with self.assertRaises(ValueError):self.book.confirm(self.doc['id'],revision=1,review=review(),plan_hash=p['plan_hash'])
        with Inbox(self.path) as inbox:inbox.review(self.doc['id'],expected_revision=1,decision='reviewed')
        with self.assertRaises(ValueError):self.book.confirm(self.doc['id'],revision=1,review=review(),plan_hash=p['plan_hash'])


    def test_non_crypto_pdf_cannot_be_manually_registered_as_capture(self):
        from tests.test_book import content
        with Inbox(self.path) as inbox:doc=inbox.upload(content(),'FICTICIO.pdf')
        p=self.book.preview(doc['id'],review=review());self.assertFalse(p['can_confirm'])
        self.assertEqual(self.book.summary()['operations'],[])

    def test_snapshot_identity_uses_bot_time_and_separate_fills_keep_id_case(self):
        self.confirm(r=bot_review())
        second=bot_review();second['occurred_at']='2026-01-07T12:00:00Z'
        self.confirm(self.upload(extra='Bot en otra fecha'),second)
        self.confirm(self.upload(extra='Ejecución mayúscula'),review(trade_id='FILL-001'))
        self.confirm(self.upload(extra='Ejecución minúscula'),review(trade_id='fill-001'))
        self.assertEqual(len(self.book.summary()['operations']),4)


class CryptoHttpTests(unittest.TestCase):
    setUp=test_intake.LocalHttpTests.setUp
    tearDown=test_intake.LocalHttpTests.tearDown
    request=test_intake.LocalHttpTests.request

    def test_real_ocr_capture_review_plan_confirm_and_registry_http(self):
        raw,_=capture();doc=self.request('/api/upload',raw,raw=True)
        from urllib.request import urlopen
        with urlopen(self.url+'/api/documents/'+doc['id']+'/image') as image:
            self.assertEqual(image.headers['Content-Type'],'image/png');self.assertEqual(image.read(),raw)
        p=self.request('/api/documents/'+doc['id']+'/crypto-plan');self.assertFalse(p['can_confirm'])
        p=self.request('/api/documents/'+doc['id']+'/crypto-plan',dict(revision=1,review=review()))
        self.assertTrue(p['can_confirm'],p['issues'])
        self.request('/api/documents/'+doc['id']+'/crypto-confirm',dict(revision=1,review=review(),plan_hash=p['plan_hash']))
        registry=self.request('/api/crypto');self.assertEqual(registry['documents'],1);self.assertEqual(len(registry['operations']),1)
        self.assertEqual(self.request('/api/book')['documents'],0)


if __name__=='__main__':unittest.main()
