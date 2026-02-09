import unittest
import sys
import os
from unittest.mock import patch, MagicMock
from io import StringIO

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from py_manage_portfolio.service import PortfolioService
from py_manage_portfolio.manage_stoploss import (
    wizard_step_1_get_context, 
    action_init_paper, 
    action_clear_paper, 
    action_edit_paper_metrics,
    action_edit_paper_position
)
from py_manage_portfolio.sizer import MinerviniSizer

class TestPaperTradingMenu(unittest.TestCase):
    def setUp(self):
        self.service = PortfolioService(project_root=".", context="paper")
        self.service.clear_paper_portfolio()
        # Ensure we have a clean journal for testing metrics
        if os.path.exists(self.service.journal_file):
            os.remove(self.service.journal_file)

    def tearDown(self):
        self.service.clear_paper_portfolio()
        if os.path.exists(self.service.journal_file):
            os.remove(self.service.journal_file)

    def test_wizard_paper_metrics(self):
        """ Test [2] Minervini Wizard (Paper) - check exposure calculation """
        # Add a position
        self.service.add_paper_position("TEST", 100.0, 90.0, 1.0, quantity=10)
        
        sizer = MinerviniSizer(self.service.project_root)
        
        # Mock get_open_positions to strictly return what we expect, avoiding live data fetch
        with patch.object(self.service, 'get_open_positions') as mock_get:
            mock_pos = MagicMock()
            mock_pos.market_value = 1000.0
            mock_get.return_value = [mock_pos]
            
            # Mock inputs: Enter, Enter, Enter (accept defaults)
            with patch('builtins.input', side_effect=['', '', '']):
                ctx = wizard_step_1_get_context(self.service, sizer, source="paper")
            
            # Context should reflect the 1000 exposure from the position
            self.assertEqual(ctx.current_exposure, 1000.0)

    def test_init_from_live(self):
        """ Test [3] Copy Live Portfolio """
        # Only works if live trades.xml exists. 
        # We can mock shutil.copy2 to verify it's called
        with patch('shutil.copy2') as mock_copy:
            # Inputs: 'y' (Confirm), '' (Enter after finish)
            with patch('builtins.input', side_effect=['y', '']):
                action_init_paper(self.service)
                # Should have called copy twice (trades.xml and risk data)
                self.assertTrue(mock_copy.called)
                self.assertGreaterEqual(mock_copy.call_count, 1)

    def test_edit_simulated_position(self):
        """ Test [5] Edit Simulated Position """
        self.service.add_paper_position("EDITME", 100.0, 90.0, 1.0, quantity=10)
        
        # Scenario: Select pos 1, then edit Qty (choice 3) to 20
        # inputs: 
        # 1. '1' (Select pos 1)
        # 2. '3' (Edit Qty)
        # 3. '20' (New Qty)
        # 4. '' (Press Enter after update)
        inputs = ['1', '3', '20', ''] 
        
        with patch('builtins.input', side_effect=inputs):
            # We also need to patch action_list to avoid printing to real stdout
            # AND action_list calls get_open_positions which calls print...
            # The test should mock print to avoid clutter, but it's fine.
            with patch('py_manage_portfolio.manage_stoploss.action_list'):
                action_edit_paper_position(self.service)

    def test_clear_simulated_positions(self):
        """ Test [6] Clear Simulated Positions """
        self.service.add_paper_position("DELME", 100.0, 90.0, 1.0, quantity=10)
        
        # Inputs: 'y' (confirm), '' (enter after list)
        with patch('builtins.input', side_effect=['y', '']): 
             with patch('py_manage_portfolio.manage_stoploss.action_list'):
                action_clear_paper(self.service)
        
        positions = self.service.get_open_positions()
        self.assertEqual(len(positions), 0)

    def test_adjust_metrics(self):
        """ Test [7] Adjust Metrics """
        # Set new equity to 50000, exposure to 5000
        # Inputs: '50000', '5000', '' (enter after list)
        inputs = ['50000', '5000', ''] 
        
        with patch('builtins.input', side_effect=inputs):
            with patch('py_manage_portfolio.manage_stoploss.action_list'):
                action_edit_paper_metrics(self.service)
        
        # Verify journal update
        equity, _, assets = self.service._get_journal_metrics()
        self.assertEqual(equity, 50000.0)
        self.assertEqual(assets, 5000.0)

if __name__ == '__main__':
    unittest.main()
