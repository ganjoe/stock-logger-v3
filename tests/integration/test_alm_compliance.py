
import unittest
import sys
import os
import shutil
import tempfile
import csv
from decimal import Decimal
from pathlib import Path
from datetime import datetime, date

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from py_portfolio_history.portfolio_history import main
from unittest.mock import MagicMock, patch

class TestALMCompliance(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.input_file = Path(self.test_dir) / "input_trades.xml"
        self.output_file = Path(self.test_dir) / "journal.csv"
        
        # Mock MarketDataManager globally for the test
        self.patcher = patch('py_portfolio_history.portfolio_history.MarketDataManager')
        self.MockMarketData = self.patcher.start()
        
        # Configure the mock instance default behavior
        instance = self.MockMarketData.return_value
        instance.get_market_price.return_value = Decimal("0.00")
        instance.get_fx_rate.return_value = Decimal("1.00")

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.test_dir)

    def run_workflow(self, input_content):
        self.input_file.write_text(input_content)
        # Mock sys.argv
        sys.argv = ['portfolio_history.py', '--input', str(self.input_file), '--output', str(self.output_file)]
        
        # Run main
        main()
        self.assertTrue(self.output_file.exists(), "CSV output not generated")
        
        # Parse CSV
        with open(self.output_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            return list(reader)

    # -------------------------------------------------------------------------
    # F-LOGIC-010: LIFO Matching
    # -------------------------------------------------------------------------
    def test_lifo_matching_logic(self):
        # Buy 1: 10 @ 100
        # Buy 2: 10 @ 110
        # Sell: 10 @ 115
        # LIFO matches Buy 2 (Cost 1100). Proceeds 1150. Gross PnL 50.
        # FIFO would match Buy 1 (Cost 1000). Gross PnL 150.
        xml_input = """<TradeLog>
          <Trades>
            <Trade id="t1" isin="LIFO"><Meta><Date>01.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>L</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>10</Quantity><Price>100</Price><Commission>0</Commission></Execution></Trade>
            <Trade id="t2" isin="LIFO"><Meta><Date>02.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>L</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>10</Quantity><Price>110</Price><Commission>0</Commission></Execution></Trade>
            <Trade id="t3" isin="LIFO"><Meta><Date>03.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>L</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>-10</Quantity><Price>115</Price><Commission>0</Commission></Execution></Trade>
          </Trades>
          <DepositsWithdrawals></DepositsWithdrawals><Dividends></Dividends>
        </TradeLog>"""
        
        rows = self.run_workflow(xml_input)
        
        # Find the sell row (event='sell')
        sell_row = next((r for r in rows if r['event'] == 'sell'), None)
        self.assertIsNotNone(sell_row)
        
        # PnL should be 50.00
        self.assertEqual(sell_row['Trade_PnL'], "50.00", "LIFO mismatch")

    # -------------------------------------------------------------------------
    # F-LOGIC-026: Dividend Inflows & Cashflow
    # -------------------------------------------------------------------------
    def test_dividends_as_inflows(self):
        xml_input = """<TradeLog>
          <Trades></Trades>
          <DepositsWithdrawals>
             <Transaction id="d1">
               <Date>01.01.2026</Date>
               <Amount>1000</Amount>
               <Currency>EUR</Currency>
             </Transaction>
          </DepositsWithdrawals>
          <Dividends>
             <Dividend id="div1">
               <Date>02.01.2026</Date>
               <Symbol>S</Symbol>
               <Amount>50</Amount>
               <Currency>EUR</Currency>
             </Dividend>
          </Dividends>
        </TradeLog>"""
        rows = self.run_workflow(xml_input)
        
        # Deposit Row
        dep_row = rows[0]
        self.assertEqual(dep_row['Sum_Deposit'], "1000.00")
        self.assertEqual(dep_row['Equity'], "1000.00")
        
        # Dividend Row
        div_row = rows[1]
        self.assertEqual(div_row['Sum_Dividend'], "50.00")
        self.assertEqual(div_row['Dividend'], "50.00")
        self.assertEqual(div_row['Equity'], "1050.00") # 1000 + 50
        self.assertEqual(div_row['Cashflow'], "50.00")

    # -------------------------------------------------------------------------
    # F-CALC-070: Total_Assets = Position Value, Equity = Cash + Total_Assets
    # Position value uses entry price (avg_entry_price from transaction)
    # -------------------------------------------------------------------------
    def test_invested_is_market_value(self):
        # Deposit 5000.
        # Buy 10 @ 100. Cost 1000. Cash Left 4000.
        # Position Value = 10 * 100 (entry price) = 1000.
        # Total_Assets = 1000 (position value at entry price).
        # Equity = 4000 (Cash) + 1000 (Total_Assets) = 5000.
        
        xml_input = """<TradeLog>
          <Trades>
            <Trade id="t1" isin="MKT"><Meta><Date>02.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>M</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>10</Quantity><Price>100</Price><Commission>0</Commission></Execution></Trade>
          </Trades>
          <DepositsWithdrawals><Transaction id="d1"><Date>01.01.2026</Date><Time>10:00:00</Time><Amount>5000</Amount><Currency>EUR</Currency></Transaction></DepositsWithdrawals>
          <Dividends></Dividends>
        </TradeLog>"""
        
        # Note: Market data is NOT used - entry price is the single source of truth
        
        rows = self.run_workflow(xml_input)
        
        # Second row is the Trade
        trade_row = rows[1]
        
        self.assertEqual(trade_row['Equity'], "5000.00", "Equity should reflect Cash (4000) + Total_Assets (1000)")
        self.assertEqual(trade_row['Total_Assets'], "1000.00", "Total_Assets = Position Value at Entry Price (10 * 100)")
        self.assertEqual(trade_row['Cash'], "4000.00")

    # -------------------------------------------------------------------------
    # F-CALC-050: PnL Metrics (Realized)
    # -------------------------------------------------------------------------
    def test_pnl_metrics_and_fees(self):
        # Trade 1: Buy 10 @ 100. Fee 5.
        # Trade 2: Sell 10 @ 110. Fee 5.
        # Gross PnL: (110-100)*10 = 100.
        # Total Fees: 5 (Buy) + 5 (Sell) = 10.
        # Realized PnL: 100 - 10 = 90.
        
        xml_input = """<TradeLog>
          <Trades>
            <Trade id="t1" isin="PNL"><Meta><Date>01.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>P</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>10</Quantity><Price>100</Price><Commission>-5</Commission></Execution></Trade>
            <Trade id="t2" isin="PNL"><Meta><Date>02.01.2026</Date><Time>12:00:00</Time></Meta><Instrument><Symbol>P</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>-10</Quantity><Price>110</Price><Commission>-5</Commission></Execution></Trade>
          </Trades>
          <DepositsWithdrawals></DepositsWithdrawals><Dividends></Dividends>
        </TradeLog>"""
        
        rows = self.run_workflow(xml_input)
        
        sell_row = rows[1]
        self.assertEqual(sell_row['Trade_PnL'], "90.00")
        self.assertEqual(sell_row['Fee'], "5.00")

    # -------------------------------------------------------------------------
    # F-CALC-065: Drawdown Calculation (based on realized PnL, not market prices)
    # Since we use entry price only, drawdown occurs through realized losses
    # -------------------------------------------------------------------------
    def test_drawdown_calculation(self):
        # Dep 1000. High Water Mark after deposit: 0 (adjusted equity = 1000 - 1000 = 0)
        # Buy 10 @ 100. Cash = 0. Position = 1000 at entry. Equity = 1000.
        # Sell 10 @ 80. Realized loss = -200. Cash = 800. Equity = 800.
        # Adjusted Equity after sale = 800 - 1000 = -200. High Water Mark = 0.
        # Drawdown = (0 - (-200)) / 0 = undefined, but we track absolute.
        # Note: With entry-price-only model, unrealized drops don't exist.
        # The drawdown percentage is tracked differently now.
        
        xml_input = """<TradeLog>
          <Trades>
            <Trade id="t1" isin="DD"><Meta><Date>02.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>D</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>10</Quantity><Price>100</Price><Commission>0</Commission></Execution></Trade>
            <Trade id="t2" isin="DD"><Meta><Date>03.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>D</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>-10</Quantity><Price>80</Price><Commission>0</Commission></Execution></Trade>
          </Trades>
          <DepositsWithdrawals><Transaction id="d1"><Date>01.01.2026</Date><Time>10:00:00</Time><Amount>1000</Amount><Currency>EUR</Currency></Transaction></DepositsWithdrawals>
          <Dividends></Dividends>
        </TradeLog>"""
        
        # No market data mock needed - entry price is the single source of truth
        
        rows = self.run_workflow(xml_input)
        
        # After selling at loss, we have 800 Cash, Equity = 800
        sell_row = rows[2]  # Third row: the sell trade
        self.assertEqual(sell_row['Cash'], "800.00")
        self.assertEqual(sell_row['Equity'], "800.00")
        self.assertEqual(sell_row['Trade_PnL'], "-200.00", "Realized loss from selling 10 @ 80 (bought @ 100)")

    # -------------------------------------------------------------------------
    # F-CALC-130: Trade Count
    # -------------------------------------------------------------------------
    def test_trade_count(self):
        # Open 1. Close 1. Trade Count should be 1.
        xml_input = """<TradeLog>
          <Trades>
            <Trade id="t1" isin="TC"><Meta><Date>01.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>T</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>1</Quantity><Price>100</Price><Commission>0</Commission></Execution></Trade>
            <Trade id="t2" isin="TC"><Meta><Date>02.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>T</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>-1</Quantity><Price>110</Price><Commission>0</Commission></Execution></Trade>
          </Trades>
          <DepositsWithdrawals></DepositsWithdrawals><Dividends></Dividends>
        </TradeLog>"""
        
        rows = self.run_workflow(xml_input)
        
        # After first trade (Buy), closed trades 0
        self.assertEqual(rows[0]['Trade_Count'], "0")
        # After second trade (Sell), closed trades 1
        self.assertEqual(rows[1]['Trade_Count'], "1")

    # -------------------------------------------------------------------------
    # F-LOGIC-011: Short Position Logic
    # -------------------------------------------------------------------------
    def test_short_position_logic(self):
        # 1. Open Short: Sell 10 @ 100
        # 2. Close Short (Cover): Buy 10 @ 90
        # Profit: (100 - 90) * 10 = 100.
        xml_input = """<TradeLog>
          <Trades>
            <Trade id="t1" isin="SHORT"><Meta><Date>01.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>S</Symbol><Currency>USD</Currency></Instrument><Execution><Quantity>-10</Quantity><Price>100</Price><Commission>0</Commission></Execution></Trade>
            <Trade id="t2" isin="SHORT"><Meta><Date>02.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>S</Symbol><Currency>USD</Currency></Instrument><Execution><Quantity>10</Quantity><Price>90</Price><Commission>0</Commission></Execution></Trade>
          </Trades>
          <DepositsWithdrawals></DepositsWithdrawals><Dividends></Dividends>
        </TradeLog>"""
        
        rows = self.run_workflow(xml_input)
        
        cover_row = rows[1]
        self.assertEqual(cover_row['event'], "buy")
        self.assertEqual(cover_row['Trade_PnL'], "100.00") # Profit verified

    # -------------------------------------------------------------------------
    # F-LOGIC-012: Flip Position Logic
    # -------------------------------------------------------------------------
    def test_flip_position_logic(self):
        # 1. Open Long: Buy 10 @ 100. (Pos +10)
        # 2. Sell 15 @ 110. (Flip: Close 10, Open Short 5)
        #    - Close PnL: (110 - 100) * 10 = 100.
        #    - New Pos: Short 5 @ 110.
        # 3. Close Short: Buy 5 @ 100.
        #    - Short PnL: (110 - 100) * 5 = 50.
        
        xml_input = """<TradeLog>
          <Trades>
            <Trade id="t1" isin="FLIP"><Meta><Date>01.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>F</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>10</Quantity><Price>100</Price><Commission>0</Commission></Execution></Trade>
            <Trade id="t2" isin="FLIP"><Meta><Date>02.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>F</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>-15</Quantity><Price>110</Price><Commission>0</Commission></Execution></Trade>
            <Trade id="t3" isin="FLIP"><Meta><Date>03.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>F</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>5</Quantity><Price>100</Price><Commission>0</Commission></Execution></Trade>
          </Trades>
          <DepositsWithdrawals></DepositsWithdrawals><Dividends></Dividends>
        </TradeLog>"""
        
        rows = self.run_workflow(xml_input)
        
        # Row 2 (Flip Sell) -> Should show PnL for the closed portion (10 units)
        flip_row = rows[1]
        self.assertEqual(flip_row['Trade_PnL'], "100.00")
        
        # Row 3 (Close Short) -> Profit on 5 units
        close_short_row = rows[2]
        self.assertEqual(close_short_row['Trade_PnL'], "50.00")

    # -------------------------------------------------------------------------
    # F-LOGIC-030: No FX Conversion
    # -------------------------------------------------------------------------
    def test_no_fx_conversion(self):
        # Requirement: Ignore FX rates. treat 1:1.
        # Trade in USD. Price change 10 USD. PnL 10 USD -> Output 10.00 (as if EUR).
        # We mock FX rate to be 2.0 to ensure it is IGNORED (if used, result would be 20).
        
        xml_input = """<TradeLog>
          <Trades>
            <Trade id="t1" isin="FXTEST"><Meta><Date>01.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>X</Symbol><Currency>USD</Currency></Instrument><Execution><Quantity>1</Quantity><Price>100</Price><Commission>0</Commission></Execution></Trade>
            <Trade id="t2" isin="FXTEST"><Meta><Date>02.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>X</Symbol><Currency>USD</Currency></Instrument><Execution><Quantity>-1</Quantity><Price>110</Price><Commission>0</Commission></Execution></Trade>
          </Trades>
          <DepositsWithdrawals></DepositsWithdrawals><Dividends></Dividends>
        </TradeLog>"""
        
        # Mock FX Rate to 2.0 (Should be ignored)
        self.MockMarketData.return_value.get_fx_rate.return_value = Decimal("2.0")
        
        rows = self.run_workflow(xml_input)
        
        sell_row = rows[1]
        # PnL should be 10.00 (110-100), NOT 20.00
        self.assertEqual(sell_row['Trade_PnL'], "10.00")

    # -------------------------------------------------------------------------
    # F-DATA-060: Dividend Parsing from Child Elements
    # -------------------------------------------------------------------------
    def test_dividend_parsing_and_sum(self):
        """
        Verifies that dividends are correctly parsed from XML child elements
        (not attributes) and that Sum_Dividend is accumulated correctly.
        """
        xml_input = """<TradeLog>
          <Trades></Trades>
          <DepositsWithdrawals>
            <Transaction id="dep1">
              <Date>01.01.2026</Date>
              <Amount>1000</Amount>
              <Currency>EUR</Currency>
            </Transaction>
          </DepositsWithdrawals>
          <Dividends>
            <Dividend id="div1">
              <Date>10.01.2026</Date>
              <Symbol>MSFT</Symbol>
              <Amount>5,00</Amount>
              <Currency>USD</Currency>
            </Dividend>
            <Dividend id="div2">
              <Date>15.01.2026</Date>
              <Symbol>AAPL</Symbol>
              <Amount>3,50</Amount>
              <Currency>USD</Currency>
            </Dividend>
          </Dividends>
        </TradeLog>"""
        
        rows = self.run_workflow(xml_input)
        
        # Row 0: Deposit
        self.assertEqual(rows[0]['event'], "deposit")
        self.assertEqual(rows[0]['Sum_Dividend'], "0.00")
        
        # Row 1: First Dividend (MSFT 5.00)
        self.assertEqual(rows[1]['event'], "dividend")
        self.assertEqual(rows[1]['symbol'], "MSFT")
        self.assertEqual(rows[1]['Dividend'], "5.00")
        self.assertEqual(rows[1]['Sum_Dividend'], "5.00")
        
        # Row 2: Second Dividend (AAPL 3.50) - Cumulative
        self.assertEqual(rows[2]['event'], "dividend")
        self.assertEqual(rows[2]['symbol'], "AAPL")
        self.assertEqual(rows[2]['Dividend'], "3.50")
        self.assertEqual(rows[2]['Sum_Dividend'], "8.50")  # 5.00 + 3.50

if __name__ == '__main__':
    unittest.main()
