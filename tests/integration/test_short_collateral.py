import unittest
from decimal import Decimal
from datetime import datetime
from py_portfolio_history.calculator import PortfolioCalculator
from py_portfolio_history.types import Transaction
from py_portfolio_history.market_data import MarketDataManager

class TestShortCollateral(unittest.TestCase):
    def setUp(self):
        # Mock Market Data (not used for this logic but required for init)
        self.market_data = MarketDataManager("./data/market")
        self.calc = PortfolioCalculator(self.market_data)

    def test_short_sell_collateral_logic(self):
        """
        Verify F-LOGIC-040: Short Sale proceeds are held as Collateral, not Cash.
        Scenario based on 4GLD case:
        1. Buy 10 @ 100.
        2. Sell 100 @ 110. (Close 10 Long, Open 90 Short).
        3. Buy 90 @ 120. (Close 90 Short with Loss).
        """
        
        # 1. Buy 10 @ 100 EUR
        t1 = Transaction(
            id="1", date=datetime(2025, 1, 1), type="BUY",
            symbol="TEST", isin="TEST", quantity=Decimal("10"), price=Decimal("100"),
            commission=Decimal("0"), currency="EUR"
        )
        self.calc.process_transaction(t1)
        
        # Expect: Cash -1000, 0 Collateral
        self.assertEqual(self.calc.cash_balance_eur, Decimal("-1000"))
        self.assertEqual(self.calc.collateral_balance_eur, Decimal("0"))
        
        # 2. Sell 100 @ 110 EUR (Flip)
        # - Close 10 Long @ 110 -> Cash +1100. (Net Cash: +100)
        # - Open 90 Short @ 110 -> Collateral +9900. Cash Unchanged (Fees 0).
        t2 = Transaction(
            id="2", date=datetime(2025, 1, 2), type="SELL",
            symbol="TEST", isin="TEST", quantity=Decimal("100"), price=Decimal("110"),
            commission=Decimal("0"), currency="EUR"
        )
        snap = self.calc.process_transaction(t2)
        
        # Cash should be -1000 + 1100 = 100.
        # It should NOT include the 9900 short proceeds!
        self.assertEqual(self.calc.cash_balance_eur, Decimal("100"))
        self.assertEqual(self.calc.collateral_balance_eur, Decimal("9900"))
        
        # Check Snapshot Equity
        # Equity = Cash (100) + Collateral (9900) + Market Value (-90 * 110 = -9900)
        # Equity = 100 + 9900 - 9900 = 100.
        # This matches the realized profit of 10 * (110-100) = 100. Correct.
        self.assertEqual(snap.total_equity, Decimal("100"))
        
        # 3. Buy 90 @ 120 (Cover Short with Loss)
        # Cost to cover: 90 * 120 = 10800.
        # Collateral Released: 9900.
        # Net Cash Impact: +9900 - 10800 = -900.
        # New Cash Balance: 100 - 900 = -800.
        t3 = Transaction(
            id="3", date=datetime(2025, 1, 3), type="BUY",
            symbol="TEST", isin="TEST", quantity=Decimal("90"), price=Decimal("120"),
            commission=Decimal("0"), currency="EUR"
        )
        snap = self.calc.process_transaction(t3)
        
        self.assertEqual(self.calc.collateral_balance_eur, Decimal("0"))
        self.assertEqual(self.calc.cash_balance_eur, Decimal("-800"))
        
        # Total PnL:
        # Trade 1 (Long): +100
        # Trade 2 (Short): 90 * (110 - 120) = -900
        # Net PnL = -800. Equity matches Cash (-800).
        self.assertEqual(snap.total_equity, Decimal("-800"))

if __name__ == '__main__':
    unittest.main()
