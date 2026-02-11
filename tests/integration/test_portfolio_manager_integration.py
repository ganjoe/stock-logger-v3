
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

from py_portfolio_cli.actions import action_update_prices
from py_portfolio_cli.utils import parse_input_decimal
from py_manage_portfolio.service import PortfolioService
from py_portfolio_history.types import Transaction

class TestPortfolioManagerIntegration:



    # -------------------------------------------------------------------------
    # F-PM-200: Live Update Trigger (Service Orchestration)
    # -------------------------------------------------------------------------
    @patch("py_portfolio_cli.actions.render_dashboard")
    @patch("py_portfolio_cli.actions.clear_terminal")
    def test_action_update_prices_calls_service(self, mock_clear, mock_render):
        """Test that action_update_prices calls the service's get_open_positions with update flag."""
        mock_instance = MagicMock()
        mock_instance.get_open_positions.return_value = []
        
        from py_portfolio_cli.actions import action_update_prices
        
        with patch("builtins.input", return_value=""):
            action_update_prices(mock_instance)
        
        # Verify the service was called with update_prices=True
        mock_instance.get_open_positions.assert_called_with(update_prices=True)

    # -------------------------------------------------------------------------
    # F-PM-190: Market Price Display Logic (Interface Verification)
    # -------------------------------------------------------------------------
    @patch("py_portfolio_cli.formatter.PortfolioService")
    def test_list_action_fetches_prices(self, MockService):
        """Test that action_list calls PortfolioService methods correctly."""
        mock_instance = MockService.return_value
        
        from py_manage_portfolio.models import Position, PortfolioSummary
        # Create complete mock position with all required fields
        mock_pos = Position(
            symbol="SYM", isin="LU123", quantity=1.0, 
            direction="LONG", entry_price=100.0, currency="EUR",
            current_price=123.45,
            status_flags=["OK"], stop_loss=95.0, pos_pct=2.5, days_held=10,
            risk_pct=0.5, dist_pct=23.1, initial_risk=16.0
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
            from py_portfolio_cli.formatter import render_dashboard
            render_dashboard(mock_instance)
            
            # Verify the service methods were called
            mock_instance.get_open_positions.assert_called()
            mock_instance.get_summary.assert_called()

    # -------------------------------------------------------------------------
    # calculate_avg_entry: REMOVED (method does not exist on PortfolioService)
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # Robust Decimal Parsing
    # -------------------------------------------------------------------------
    def test_parse_input_decimal(self):
        assert parse_input_decimal("10.50") == 10.5
        assert parse_input_decimal("10,50") == 10.5
        assert parse_input_decimal("1.200,50") == 1200.5
        assert parse_input_decimal("1,200.50") == 1200.5
        assert parse_input_decimal("10") == 10.0

