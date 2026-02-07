
import unittest
import sys
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from py_portfolio_history.portfolio_history import main

from unittest.mock import MagicMock, patch

class TestALMCompliance(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.input_file = Path(self.test_dir) / "input_trades.xml"
        self.output_file = Path(self.test_dir) / "output_history.xml"
        
        # Mock MarketDataManager globally for the test
        self.patcher = patch('py_portfolio_history.portfolio_history.MarketDataManager')
        self.MockMarketData = self.patcher.start()
        
        # Configure the mock instance
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
        self.assertTrue(self.output_file.exists(), "Output XML not generated")
        return ET.parse(self.output_file).getroot()

    # -------------------------------------------------------------------------
    # F-CALC-120: HoldingDays
    # -------------------------------------------------------------------------
    def test_holding_days_calculation(self):
        xml_input = """<TradeLog>
          <Trades>
            <Trade id="t1" isin="HOLDTEST">
              <Meta><Date>01.01.2026</Date><Time>12:00:00</Time></Meta>
              <Instrument><Symbol>HOLD</Symbol><Currency>EUR</Currency></Instrument>
              <Execution><Quantity>10</Quantity><Price>100,00</Price><Commission>-1,00</Commission><Proceeds>-1001,00</Proceeds></Execution>
            </Trade>
            <Trade id="t2" isin="HOLDTEST">
              <Meta><Date>11.01.2026</Date><Time>12:00:00</Time></Meta>
              <Instrument><Symbol>HOLD</Symbol><Currency>EUR</Currency></Instrument>
              <Execution><Quantity>10</Quantity><Price>110,00</Price><Commission>-1,00</Commission><Proceeds>-1101,00</Proceeds></Execution>
            </Trade>
          </Trades>
          <DepositsWithdrawals></DepositsWithdrawals>
          <Dividends></Dividends>
        </TradeLog>"""
        
        root = self.run_workflow(xml_input)
        
        pos1 = root.find(".//Change[@id='t1']//Position[Symbol='HOLD']")
        self.assertIsNotNone(pos1)
        # Usually day 0
        self.assertEqual(pos1.find("HoldingDays").text, "0")
        
        pos2 = root.find(".//Change[@id='t2']//Position[Symbol='HOLD']")
        self.assertIsNotNone(pos2)
        # 11.01 minus 01.01 = 10 days
        self.assertEqual(pos2.find("HoldingDays").text, "10")

    # -------------------------------------------------------------------------
    # F-LOGIC-010: AvgEntryPrice
    # -------------------------------------------------------------------------
    def test_avg_entry_price_calculation(self):
        xml_input = """<TradeLog>
          <Trades>
            <Trade id="t1" isin="AVGTEST">
              <Meta><Date>01.01.2026</Date><Time>10:00:00</Time></Meta>
              <Instrument><Symbol>AVG</Symbol><Currency>EUR</Currency></Instrument>
              <Execution><Quantity>10</Quantity><Price>100,00</Price><Commission>0</Commission><Proceeds>-1000</Proceeds></Execution>
            </Trade>
            <Trade id="t2" isin="AVGTEST">
              <Meta><Date>02.01.2026</Date><Time>10:00:00</Time></Meta>
              <Instrument><Symbol>AVG</Symbol><Currency>EUR</Currency></Instrument>
              <Execution><Quantity>10</Quantity><Price>200,00</Price><Commission>0</Commission><Proceeds>-2000</Proceeds></Execution>
            </Trade>
          </Trades>
          <DepositsWithdrawals></DepositsWithdrawals>
          <Dividends></Dividends>
        </TradeLog>"""
        root = self.run_workflow(xml_input)
        pos2 = root.find(".//Change[@id='t2']//Position[Symbol='AVG']")
        self.assertEqual(pos2.find("AvgEntryPrice").text, "150.00")

    # -------------------------------------------------------------------------
    # F-DATA-050 / ICD-DAT-042: AccumulatedFees
    # -------------------------------------------------------------------------
    def test_accumulated_fees(self):
        xml_input = """<TradeLog>
          <Trades>
            <Trade id="t1" isin="FEETEST">
              <Meta><Date>01.01.2026</Date><Time>10:00:00</Time></Meta>
              <Instrument><Symbol>FEE</Symbol><Currency>EUR</Currency></Instrument>
              <Execution><Quantity>10</Quantity><Price>100,00</Price><Commission>-10,00</Commission><Proceeds>-1010</Proceeds></Execution>
            </Trade>
            <Trade id="t2" isin="FEETEST">
              <Meta><Date>02.01.2026</Date><Time>10:00:00</Time></Meta>
              <Instrument><Symbol>FEE</Symbol><Currency>EUR</Currency></Instrument>
              <Execution><Quantity>-5</Quantity><Price>120,00</Price><Commission>-2,00</Commission><Proceeds>598</Proceeds></Execution>
            </Trade>
          </Trades>
          <DepositsWithdrawals></DepositsWithdrawals>
          <Dividends></Dividends>
        </TradeLog>"""
        root = self.run_workflow(xml_input)
        pos2 = root.find(".//Change[@id='t2']//Position")
        # -10 total fees for 10 units = 1 per unit.
        # Remaining 5 units = 5.00 fees.
        self.assertEqual(pos2.find("AccumulatedFees").text, "5.00")

    # -------------------------------------------------------------------------
    # F-CALC-050: PnL Metrics
    # -------------------------------------------------------------------------
    def test_pnl_metrics(self):
        xml_input = """<TradeLog>
          <Trades>
            <Trade id="t1" isin="PNLTEST">
              <Meta><Date>01.01.2026</Date><Time>10:00:00</Time></Meta>
              <Instrument><Symbol>PNL</Symbol><Currency>EUR</Currency></Instrument>
              <Execution><Quantity>10</Quantity><Price>100,00</Price><Commission>-5,00</Commission><Proceeds>-1005</Proceeds></Execution>
            </Trade>
            <Trade id="t2" isin="PNLTEST">
              <Meta><Date>02.01.2026</Date><Time>12:00:00</Time></Meta>
              <Instrument><Symbol>PNL</Symbol><Currency>EUR</Currency></Instrument>
              <Execution><Quantity>-10</Quantity><Price>110,00</Price><Commission>-5,00</Commission><Proceeds>1095</Proceeds></Execution>
            </Trade>
          </Trades>
          <DepositsWithdrawals></DepositsWithdrawals>
          <Dividends></Dividends>
        </TradeLog>"""
        root = self.run_workflow(xml_input)
        perf = root.find(".//Change[@id='t2']//Snapshot/Performance")
        
        self.assertEqual(perf.find("Trading").text, "100.00")
        self.assertEqual(perf.find("Real").text, "90.00")
        self.assertEqual(perf.find("Accounting").text, "90.00")

    # -------------------------------------------------------------------------
    # F-CALC-060: Portfolio KPIs (WinRate, ProfitFactor)
    # -------------------------------------------------------------------------
    def test_portfolio_kpis(self):
        # 1. Win: +10 Trading PnL (Real: +8)
        # 2. Loss: -10 Trading PnL (Real: -12)
        # Total Real PnL: -4.
        # WinRate: 1 Win / 2 Trades = 50.00%
        # ProfitFactor: GrossWin(8) / GrossLoss(12) = 0.67
        xml_input = """<TradeLog>
          <Trades>
            <Trade id="t1" isin="KPI1"><Meta><Date>01.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>A</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>1</Quantity><Price>100</Price><Commission>-1</Commission></Execution></Trade>
            <Trade id="t2" isin="KPI1"><Meta><Date>02.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>A</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>-1</Quantity><Price>110</Price><Commission>-1</Commission></Execution></Trade>
            
            <Trade id="t3" isin="KPI2"><Meta><Date>03.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>B</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>1</Quantity><Price>100</Price><Commission>-1</Commission></Execution></Trade>
            <Trade id="t4" isin="KPI2"><Meta><Date>04.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>B</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>-1</Quantity><Price>90</Price><Commission>-1</Commission></Execution></Trade>
          </Trades>
          <DepositsWithdrawals></DepositsWithdrawals><Dividends></Dividends>
        </TradeLog>"""
        
        root = self.run_workflow(xml_input)
        perf = root.findall(".//Snapshot/Performance")[-1] # Final state
        
        self.assertEqual(perf.find("WinRate").text, "50.00")
        self.assertEqual(perf.find("ProfitFactor").text, "1.00")

    # -------------------------------------------------------------------------
    # F-CALC-130: Total Trades Statistics
    # -------------------------------------------------------------------------
    def test_total_trades_stats(self):
        # Using same input as KPIs (2 closed trades)
        xml_input = """<TradeLog>
          <Trades>
            <Trade id="t1" isin="KPI1"><Meta><Date>01.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>A</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>1</Quantity><Price>100</Price><Commission>-1</Commission></Execution></Trade>
            <Trade id="t2" isin="KPI1"><Meta><Date>02.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>A</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>-1</Quantity><Price>110</Price><Commission>-1</Commission></Execution></Trade>
            
            <Trade id="t3" isin="KPI2"><Meta><Date>03.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>B</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>1</Quantity><Price>100</Price><Commission>-1</Commission></Execution></Trade>
          </Trades>
          <DepositsWithdrawals></DepositsWithdrawals><Dividends></Dividends>
        </TradeLog>"""
        
        root = self.run_workflow(xml_input)
        
        perf_t2 = root.find(".//Change[@id='t2']//Performance")
        total_trades = perf_t2.find("TotalTrades")
        self.assertIsNotNone(total_trades, "TotalTrades node missing in Performance")
        
        self.assertEqual(total_trades.find("ClosedTrades").text, "1")
        self.assertEqual(total_trades.find("OpenPositions").text, "0")
        self.assertEqual(total_trades.find("Transactions").text, "2") # Buy + Sell

        perf_t3 = root.find(".//Change[@id='t3']//Performance")
        total_trades_t3 = perf_t3.find("TotalTrades")
        
        self.assertEqual(total_trades_t3.find("ClosedTrades").text, "1")
        self.assertEqual(total_trades_t3.find("OpenPositions").text, "1")
        self.assertEqual(total_trades_t3.find("Transactions").text, "3")


    # -------------------------------------------------------------------------
    # F-LOGIC-010: LIFO Matching
    # -------------------------------------------------------------------------
    def test_lifo_matching_logic(self):
        # Buy 1: 10 @ 100
        # Buy 2: 10 @ 110
        # Sell: 10 @ 115
        # LIFO: Matches Buy 2 (Cost 1100). Gross PnL = (115-110)*10 = 50.
        # FIFO (Legacy): Would match Buy 1 (Cost 1000). Gross PnL = (115-100)*10 = 150.
        xml_input = """<TradeLog>
          <Trades>
            <Trade id="t1" isin="LIFO"><Meta><Date>01.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>L</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>10</Quantity><Price>100</Price><Commission>0</Commission></Execution></Trade>
            <Trade id="t2" isin="LIFO"><Meta><Date>02.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>L</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>10</Quantity><Price>110</Price><Commission>0</Commission></Execution></Trade>
            <Trade id="t3" isin="LIFO"><Meta><Date>03.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>L</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>-10</Quantity><Price>115</Price><Commission>0</Commission></Execution></Trade>
          </Trades>
          <DepositsWithdrawals></DepositsWithdrawals><Dividends></Dividends>
        </TradeLog>"""
        root = self.run_workflow(xml_input)
        
        perf = root.find(".//Change[@id='t3']//Performance")
        trading_pnl = perf.find("Trading").text
        
        self.assertEqual(trading_pnl, "50.00", "LIFO mismatch: PnL should be 50 (from 110 entry), not 150 (from 100 entry)")

    # -------------------------------------------------------------------------
    # F-LOGIC-026: Dividend Inflows
    # -------------------------------------------------------------------------
    def test_dividends_as_inflows(self):
        xml_input = """<TradeLog>
          <Trades></Trades>
          <DepositsWithdrawals>
             <Transaction id="d1"><Date>01.01.2026</Date><Desc>Dep</Desc><Amount>1000</Amount><Currency>EUR</Currency></Transaction>
          </DepositsWithdrawals>
          <Dividends>
             <Dividend id="div1" date="02.01.2026" symbol="S" amount="50" currency="EUR" isin="S1"/>
          </Dividends>
        </TradeLog>"""
        root = self.run_workflow(xml_input)
        
        # After Dividend
        snap = root.find(".//Change[@id='div1']//Snapshot")
        inflows = snap.find("Inflows").text
        
        # 1000 Deposit + 50 Dividend = 1050 Total Inflows
        self.assertEqual(inflows, "1050.00", "Dividends should be counted as Inflows")
        
        # Accounting PnL should also increase (it's profit)
        acc_pnl = snap.find("Performance/Accounting").text
        self.assertEqual(acc_pnl, "50.00", "Dividends should contribute to Accounting PnL")

    # -------------------------------------------------------------------------
    # F-CALC-070: Invested = Market Value
    # -------------------------------------------------------------------------
    def test_invested_is_market_value(self):
        # Invested should be Exposure (Price * Qty), NOT Cost Basis.
        # Scenario: Buy 10 @ 100 (Cost 1000). Price goes to 200. Invested should be 2000.
        xml_input = """<TradeLog>
          <Trades>
            <Trade id="t1" isin="MKT"><Meta><Date>01.01.2026</Date><Time>10:00:00</Time></Meta><Instrument><Symbol>M</Symbol><Currency>EUR</Currency></Instrument><Execution><Quantity>10</Quantity><Price>100</Price><Commission>0</Commission></Execution></Trade>
          </Trades>
          <DepositsWithdrawals><Transaction id="d1"><Date>01.01.2026</Date><Amount>5000</Amount><Currency>EUR</Currency></Transaction></DepositsWithdrawals>
          <Dividends></Dividends>
        </TradeLog>"""
        
        # Override Mock to return Price 200 on later date
        # We need to simulate price update. The Workflow runs linear.
        # But MockMarketData is configured in setup. We can dynamically change it if we mock correctly.
        # Or better: The test runs workflow once.
        # BUT: The workflow calls get_market_price for each event.
        # The mock returns constant 0.00 from setup.
        # Let's adjust Mock behavior for this specific test inside the test function using side_effect?
        # But 'main' is imported. The mock in setUp patches 'py_portfolio_history.portfolio_history.MarketDataManager'.
        
        # We need a predictable mock.
        self.MockMarketData.return_value.get_market_price.side_effect = lambda isin, sym, date: Decimal("200") if isin=="MKT" else Decimal("100")
        
        root = self.run_workflow(xml_input)
        
        snap = root.find(".//Change[@id='t1']//Snapshot")
        invested = snap.find("Invested").text
        
        # 10 units * 200 Price = 2000 Invested
        self.assertEqual(invested, "2000.00", "Invested should be Market Value (Exposure)")

if __name__ == '__main__':
    unittest.main()
