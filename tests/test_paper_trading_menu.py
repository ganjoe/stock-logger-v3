"""
Integration tests for Paper Trading Menu (CLI V3).
Tests the interaction between CLI action functions and PortfolioService.

Updated to match the refactored module structure:
- cli.py for action handlers
- wizard.py for wizard steps
- formatter.py for render_dashboard (patched out)
"""
import unittest
import sys
import os
from unittest.mock import patch, MagicMock
from io import StringIO
from datetime import datetime

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from py_manage_portfolio.service import PortfolioService
from py_portfolio_cli.actions import (
    action_init_paper, 
    action_clear_paper, 
    action_edit_paper_metrics,
    action_edit_paper_position
)
from py_portfolio_cli.wizard import wizard_step_1_get_context
from py_riskmanagement import MinerviniSizer


class TestPaperTradingMenu(unittest.TestCase):
    def setUp(self):
        self.service = PortfolioService(project_root=".", context="sim")
        self.service.clear_paper_portfolio()

    def tearDown(self):
        self.service.clear_paper_portfolio()

    def test_wizard_paper_metrics(self):
        """ Test [2] Minervini Wizard (Paper) - check exposure calculation """
        # Add a position via the actual API
        self.service.add_position_sim("TEST", 10, 100.0, datetime.now().strftime("%Y-%m-%d"))
        
        sizer = MinerviniSizer(self.service.project_root)
        
        # Mock inputs: Enter, Enter, Enter (accept defaults)
        with patch('builtins.input', side_effect=['', '', '']):
            ctx = wizard_step_1_get_context(self.service, sizer, source="paper")
        
        # Context should reflect exposure from the position
        # Exposure = qty * current_price (10 * current_price)
        self.assertGreater(ctx.current_exposure, 0)

    def test_init_from_live(self):
        """ Test [3] Copy Live Portfolio """
        # The init_from_live method connects to broker and copies state.
        # We mock the internal broker fetch to avoid actual connection.
        with patch.object(self.service, 'init_from_live') as mock_init:
            mock_init.return_value = None
            # Inputs: 'y' (Confirm), '' (Enter after finish)
            with patch('builtins.input', side_effect=['y', '']):
                with patch('py_manage_portfolio.cli.render_dashboard'):
                    action_init_paper(self.service)
                    mock_init.assert_called_once()

    def test_edit_simulated_position(self):
        """ Test [5] Edit Simulated Position """
        self.service.add_position_sim("EDITME", 10, 100.0, datetime.now().strftime("%Y-%m-%d"))
        
        # Scenario: Select pos 1, then edit Qty (choice 3) to 20
        inputs = ['1', '3', '20', ''] 
        
        with patch('builtins.input', side_effect=inputs):
            with patch('py_manage_portfolio.cli.render_dashboard'):
                action_edit_paper_position(self.service)

    def test_clear_simulated_positions(self):
        """ Test [6] Clear Simulated Positions """
        self.service.add_position_sim("DELME", 10, 100.0, datetime.now().strftime("%Y-%m-%d"))
        
        # Inputs: 'y' (confirm), '' (enter after list)
        with patch('builtins.input', side_effect=['y', '']): 
             with patch('py_manage_portfolio.cli.render_dashboard'):
                action_clear_paper(self.service)
        
        positions = self.service.get_open_positions()
        self.assertEqual(len(positions), 0)

    def test_adjust_metrics(self):
        """ Test [7] Adjust Metrics """
        # Set new equity to 50000, exposure to 5000
        # Inputs: '50000', '5000', '' (enter after list)
        inputs = ['50000', '5000', ''] 
        
        with patch('builtins.input', side_effect=inputs):
            with patch('py_manage_portfolio.cli.render_dashboard'):
                action_edit_paper_metrics(self.service)
        
        # _get_journal_metrics recalculates equity = cash + position_exposure
        # Cash was set to 50000 - 5000 = 45000. No positions → exposure=0 → equity = 45000
        equity, cash, exposure = self.service._get_journal_metrics()
        self.assertEqual(cash, 45000.0)

if __name__ == '__main__':
    unittest.main()
