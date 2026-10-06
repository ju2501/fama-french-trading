from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stock_ff5.kis import (BrokerError, Credentials, KIS, SEOUL, execute_batch,
                           plan_orders, require_session)


class FakeKIS(KIS):
    def __init__(self, environment="paper", responses=None):
        super().__init__(Credentials(environment, "fake-key", "fake-secret", "12345678", "01"), ".state")
        self.token = "fake-token"
        self.calls, self.responses = [], list(responses or [])

    def _http(self, method, path, payload, headers):
        self.calls.append((method, path, payload, headers))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class KISTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.signal = {"as_of": "2026-10-06", "factor_month": "2026-08-31", "synthetic": False}
        self.orders = [{"symbol": "005930", "side": "buy", "quantity": 2, "limit_price": 70000}]

    def tearDown(self):
        self.temp.cleanup()

    def test_paper_order_wire_contract(self):
        broker = FakeKIS(responses=[({"rt_cd": "0", "output": {"ODNO": "123"}}, {})])
        self.assertEqual(broker.order(**self.orders[0]), "123")
        method, path, payload, headers = broker.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(headers["tr_id"], "VTTC0012U")
        self.assertEqual(payload["ORD_QTY"], "2")
        self.assertEqual(payload["ORD_DVSN"], "00")
        self.assertEqual(payload["EXCG_ID_DVSN_CD"], "KRX")
        self.assertEqual(broker.base_url, "https://openapivts.koreainvestment.com:29443")

    def test_pagination_includes_second_page(self):
        broker = FakeKIS(responses=[
            ({"rt_cd": "0", "output1": [{"pdno": "005930", "hldg_qty": "1", "ord_psbl_qty": "1"}],
              "output2": [{"tot_evlu_amt": "1000000"}], "ctx_area_fk100": "a", "ctx_area_nk100": "b"}, {"tr_cont": "M"}),
            ({"rt_cd": "0", "output1": [{"pdno": "000660", "hldg_qty": "2", "ord_psbl_qty": "1"}],
              "output2": [{"tot_evlu_amt": "1000000"}]}, {"tr_cont": "D"})])
        self.assertEqual(broker.balance()["positions"], {"005930": 1, "000660": 2})
        self.assertEqual(broker.calls[1][3]["tr_cont"], "N")
        self.assertEqual(broker.calls[1][2]["CTX_AREA_NK100"], "b")

    def test_rejected_api_is_not_success(self):
        broker = FakeKIS(responses=[({"rt_cd": "1", "msg_cd": "DENIED"}, {})])
        with self.assertRaises(BrokerError):
            broker.order(**self.orders[0])
        self.assertEqual(len(broker.calls), 1)

    def test_timeout_claim_prevents_duplicate_submission(self):
        broker = FakeKIS(responses=[BrokerError("ambiguous timeout")])
        with self.assertRaises(BrokerError):
            execute_batch(broker, self.orders, self.signal, self.root)
        with self.assertRaisesRegex(BrokerError, "claimed"):
            execute_batch(broker, self.orders, self.signal, self.root)
        self.assertEqual(len(broker.calls), 1)
        state = json.loads(next(self.root.glob("rebalance-*.json")).read_text())
        self.assertEqual(state["status"], "unknown_or_rejected_check_broker")

    def test_accepted_order_is_not_reported_as_filled(self):
        broker = FakeKIS(responses=[({"rt_cd": "0", "output": {"ODNO": "123"}}, {})])
        state = execute_batch(broker, self.orders, self.signal, self.root)
        self.assertEqual(state["status"], "submitted_check_fills")

    def test_live_requires_opt_in(self):
        broker = FakeKIS("live")
        with self.assertRaisesRegex(ValueError, "allow-live"):
            execute_batch(broker, self.orders, self.signal, self.root)
        self.assertFalse(broker.calls)

    def test_synthetic_never_reaches_broker(self):
        broker = FakeKIS()
        with self.assertRaisesRegex(ValueError, "Synthetic"):
            execute_batch(broker, self.orders, {**self.signal, "synthetic": True}, self.root)
        self.assertFalse(broker.calls)

    def test_cash_limit_no_shorting_or_spending_unfilled_sales(self):
        account = {"equity": 1_000_000, "positions": {"005930": 5}, "sellable": {"005930": 3}}
        quotes = {"005930": 70000, "000660": 100000}
        powers = {s: (150000, 10) for s in quotes}
        orders = plan_orders({"000660": 0.8}, account, quotes, powers, 1_000_000, 1_000_000)
        self.assertEqual(next(o for o in orders if o["side"] == "sell")["quantity"], 3)
        self.assertEqual(next(o for o in orders if o["side"] == "buy")["quantity"], 1)

    def test_order_value_cap(self):
        orders = plan_orders({"005930": 0.9}, {"equity": 1_000_000, "positions": {}, "sellable": {}},
                             {"005930": 70000}, {"005930": (1_000_000, 100)}, 1_000_000, 150000)
        self.assertEqual(orders[0]["quantity"], 2)

    def test_invalid_weights_and_quantities(self):
        with self.assertRaises(ValueError):
            plan_orders({"005930": float("nan")}, {}, {}, {}, 100, 100)
        with self.assertRaises(ValueError):
            FakeKIS().order("005930", "buy", -1, 100)

    def test_calendar_and_session_gate(self):
        path = self.root / "sessions.csv"
        path.write_text("date\n2026-10-06\n")
        require_session(datetime(2026, 10, 6, 10, 0, tzinfo=SEOUL), path)
        for stamp in [datetime(2026, 10, 6, 16, 0, tzinfo=SEOUL), datetime(2026, 10, 7, 10, 0, tzinfo=SEOUL)]:
            with self.assertRaises(ValueError):
                require_session(stamp, path)


if __name__ == "__main__":
    unittest.main()
