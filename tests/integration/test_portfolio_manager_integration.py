
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
    action_update_prices,
    parse_input_decimal
)
from py_manage_portfolio.service import PortfolioService
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
    # F-PM-200: Live Update Trigger (Service Orchestration)
    # -------------------------------------------------------------------------
    @patch("py_manage_portfolio.manage_stoploss.PortfolioService")
    def test_action_update_prices_calls_service(self, MockService):
        """Test that action_update_prices calls the service's get_open_positions with update flag."""
        mock_instance = MockService.return_value
        mock_instance.get_open_positions.return_value = []
        
        from py_manage_portfolio.manage_stoploss import action_update_prices
        
        with patch("builtins.input", return_value=""):
            action_update_prices(mock_instance)
        
        # Verify the service was called with update_prices=True
        mock_instance.get_open_positions.assert_called_with(update_prices=True)

    # -------------------------------------------------------------------------
    # F-PM-190: Market Price Display Logic (Interface Verification)
    # -------------------------------------------------------------------------
    @patch("py_manage_portfolio.manage_stoploss.PortfolioService")
    def test_list_action_fetches_prices(self, MockService):
        """Test that action_list calls PortfolioService methods correctly."""
        mock_instance = MockService.return_value
        
        from py_manage_portfolio.models import PortfolioPosition, PortfolioSummary
        # Create complete mock position with all required fields
        mock_pos = PortfolioPosition(
            symbol="SYM", isin="LU123", quantity=1.0, raw_quantity=1.0, 
            direction="LONG", entry_price=100.0, currency="EUR",
            current_price=123.45, market_value=123.45, unrealized_pl=23.45, unrealized_pct=23.45,
            status_flags=["OK"], stop_loss=95.0, pos_pct=2.5, days_held=10,
            risk_pct=0.5, dist_pct=23.1, r_multiple=1.5
        )
        mock_instance.get_open_positions.return_value = [mock_pos]
        mock_instance.get_summary.return_value = PortfolioSummary(
            total_invested=123.45, total_unrealized_pl=23.45, total_risk=0.0,
            buying_power=5000.0, equity=5123.45, position_count=1,
            count_ok=1, count_warning=0, count_danger=0
        )
        mock_instance.get_risk_settings.return_value = {
            "holding_threshold": 30,
            "default_risk_pct": 1.0,
            "max_equity_risk": 1.25
        }
        
        # Suppress output but verify the service was called
        with patch("builtins.print"):
            from py_manage_portfolio.manage_stoploss import action_list
            action_list()
            
            # Verify the service methods were called
            mock_instance.get_open_positions.assert_called()
            mock_instance.get_summary.assert_called()

    # -------------------------------------------------------------------------
    # Unit Test: calculate_avg_entry
    # -------------------------------------------------------------------------
    def test_calculate_avg_entry(self):
        tranches = [
            {'quantity': 100, 'price': 50},
            {'quantity': 200, 'price': 80}
        ]
        service = PortfolioService(project_root=".")
        avg = service.calculate_avg_entry(tranches)
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

