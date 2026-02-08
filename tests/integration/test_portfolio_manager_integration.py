
import pytest
import json
import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path
from datetime import date

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from py_manage_portfolio.manage_stoploss import (
    get_open_positions, 
    action_update_prices,
    calculate_avg_entry,
    parse_input_decimal
)
from py_manage_portfolio.price_service import PortfolioPriceService, PriceMetadata
from py_portfolio_history.types import Transaction

class TestPortfolioManagerIntegration:

    # -------------------------------------------------------------------------
    # F-PM-180: PortfolioPriceService Integration (Service Loading)
    # -------------------------------------------------------------------------
    @patch("py_manage_portfolio.price_service.DataFetcherService")
    def test_price_service_loads_from_service(self, MockFetcher, tmp_path):
        isin = "LU0490618542"
        # Mock result from DataFetcherService
        mock_asset = MagicMock()
        mock_asset.isin = isin
        mock_asset.symbol = "XDEF.DE"
        mock_asset.market_price = 32.50
        mock_asset.currency = "EUR"
        mock_asset.last_update = "2026-02-06"
        
        MockFetcher.return_value.get_asset.return_value = mock_asset
        
        service = PortfolioPriceService()
        prices = service.get_cached_prices([isin])
        
        # ASSERT
        assert isin in prices
        assert prices[isin].price == 32.50
        assert prices[isin].symbol == "XDEF.DE"
        assert prices[isin].source == "Service"

    # -------------------------------------------------------------------------
    # F-PM-200: Live Update Trigger (CLI Command Construction)
    # -------------------------------------------------------------------------
    def test_action_update_prices_triggers_correct_command(self):
        open_positions = {
            "AAPL": {"isin": "US123", "quantity": Decimal("10")},
            "MSFT": {"isin": "US456", "quantity": Decimal("5")}
        }
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            
            action_update_prices(open_positions)
            
            # ASSERT
            args, kwargs = mock_run.call_args
            cmd = args[0]
            
            assert "py_datafetcher.datafetcher" in cmd
            assert "--mode" in cmd
            assert "update" in cmd
            assert "--assets" in cmd
            
            # Check if assets are correctly formatted ISIN:TICKER
            assets_arg = cmd[cmd.index("--assets") + 1]
            assert "US123:AAPL" in assets_arg
            assert "US456:MSFT" in assets_arg
            assert "--verbose" in cmd, "Should include verbose flag (F-PM-210)"

    # -------------------------------------------------------------------------
    # F-PM-190: Market Price Display Logic (Interface Verification)
    # -------------------------------------------------------------------------
    @patch("py_manage_portfolio.manage_stoploss.PortfolioService")
    def test_list_action_fetches_prices(self, MockService):
        # Mocking the service to return a specific price
        mock_instance = MockService.return_value
        
        from py_manage_portfolio.models import PortfolioPosition, PortfolioSummary
        mock_pos = PortfolioPosition(
            symbol="SYM", isin="LU123", quantity=1.0, raw_quantity=1.0, 
            direction="LONG", entry_price=100.0, currency="EUR",
            current_price=123.45, market_value=123.45, unrealized_pl=23.45, unrealized_pct=23.45,
            status_flags=["OK"]
        )
        mock_instance.get_open_positions.return_value = [mock_pos]
        mock_instance.get_summary.return_value = PortfolioSummary(
            total_invested=123.45, total_unrealized_pl=23.45, total_risk=0.0,
            buying_power=5000.0, equity=5123.45, position_count=1,
            count_ok=1, count_trail=0, count_missing=0
        )
        
        # We don't want to actually print or input, just verify the call happened
        with patch("builtins.print") as mock_print:
            from py_manage_portfolio.manage_stoploss import action_list
            action_list()
            
            # Verify the service was called
            mock_instance.get_open_positions.assert_called()
            
            # Verify the price appears in the output
            # Look for "123.5" somewhere in a print call (rounded to 1 decimal)
            found = False
            for call in mock_print.call_args_list:
                if "123.5" in str(call):
                    found = True
                    break
            assert found, "Market price 123.5 should be printed in the list view"

    # -------------------------------------------------------------------------
    # Unit Test: calculate_avg_entry
    # -------------------------------------------------------------------------
    def test_calculate_avg_entry(self):
        tranches = [
            {'quantity': 100, 'price': 50},
            {'quantity': 200, 'price': 80}
        ]
        avg = calculate_avg_entry(tranches)
        # (100*50 + 200*80) / 300 = (5000 + 16000) / 300 = 21000 / 300 = 70.0
        assert avg == Decimal("70.0")

    # -------------------------------------------------------------------------
    # Robust Decimal Parsing
    # -------------------------------------------------------------------------
    def test_parse_input_decimal(self):
        assert parse_input_decimal("10.50") == 10.5
        assert parse_input_decimal("10,50") == 10.5
        assert parse_input_decimal("1.200,50") == 1200.5
        assert parse_input_decimal("1,200.50") == 1200.5
        assert parse_input_decimal("10") == 10.0

