"""Offline tests for the risk gate and ledger. Prices here are stubs, never written to the real ledger."""
import os
import tempfile
import unittest

os.environ["PAPER_DATA_DIR"] = tempfile.mkdtemp()

import ledger  # noqa: E402
import market  # noqa: E402
import server  # noqa: E402

PRICES = {"BTC": 100_000.0, "ETH": 4_000.0, "SOL": 200.0}
market.latest_price = lambda s: PRICES[s.upper()]


class PaperTest(unittest.TestCase):
    def setUp(self):
        for p in (ledger.STATE, ledger.DECISIONS, ledger.EQUITY):
            p.unlink(missing_ok=True)
        os.environ["PAPER_ROUND_ID"] = self.id()

    def new_round(self, n):
        os.environ["PAPER_ROUND_ID"] = f"{self.id()}-{n}"

    def test_buy_fee_and_cap(self):
        self.assertIn("25%", server.buy("BTC", 26, "too big")["refusal"])
        r = server.buy("BTC", 25, "ok")
        self.assertTrue(r["filled"])
        self.assertAlmostEqual(r["fee"], 0.1)
        self.assertAlmostEqual(ledger.load_state()["cash"], 75)

    def test_one_position_and_one_fill_per_round(self):
        server.buy("ETH", 10, "first")
        self.new_round(2)
        self.assertIn("one position", server.buy("SOL", 10, "second")["refusal"])
        self.new_round(3)
        server.sell_all("exit")
        self.assertIn("per round", server.buy("SOL", 10, "same round")["refusal"])

    def test_no_short(self):
        self.assertIn("no shorting", server.sell_all("nothing held")["refusal"])

    def test_roundtrip_fees(self):
        server.buy("SOL", 20, "in")
        self.new_round(2)
        r = server.sell_all("out")
        st = ledger.load_state()
        self.assertAlmostEqual(st["fees_paid"], 0.08 + 19.92 * 0.004)
        self.assertAlmostEqual(r["pnl"], -(0.08 + 19.92 * 0.004))

    def test_daily_fill_limit(self):
        for i in range(6):
            self.new_round(i)
            server.buy("BTC", 5, "in") if i % 2 == 0 else server.sell_all("out")
        self.new_round(99)
        self.assertIn("daily fill limit", server.buy("BTC", 5, "seventh")["refusal"])

    def test_kill_switch(self):
        st = ledger.load_state()
        st["cash"] = 49.0
        ledger.save_state(st)
        self.assertIn("kill switch", server.buy("BTC", 5, "x")["refusal"])

    def test_everything_logged(self):
        server.hold("waiting")
        server.buy("BTC", 1000, "too big")
        log = ledger.read_jsonl(ledger.DECISIONS)
        self.assertEqual([d["status"] for d in log], ["logged", "refused"])
        self.assertEqual(log[1]["reason"], "too big")

    def test_bad_amounts(self):
        for amt in (0, -5, float("nan")):
            self.assertFalse(server.buy("BTC", amt, "bad")["filled"])


if __name__ == "__main__":
    unittest.main()
