
import sys
import os
import unittest

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from py_manage_portfolio.service import PortfolioService

class TestManagePortfolioWizard(unittest.TestCase):
    def test_add_paper_position_in_live_context(self):
        """
        Regression test for crash when adding paper position while in live context.
        Simulates the logic fixed in run_manage_portfolio.py
        """
        # 1. Init Live Service
        service = PortfolioService(project_root=".", context="live")
        
        # 2. Simulate Wizard Logic: Switch to Paper Service for saving
        target_service = service
        if service.context != "paper":
            target_service = PortfolioService(project_root=service.project_root, context="paper")
            
        self.assertEqual(target_service.context, "paper")
        
        # 3. Add Paper Position
        symbol = "TEST_WIZ"
        try:
            result = target_service.add_paper_position(
                symbol=symbol,
                entry_price=100.0,
                stop_loss=90.0,
                risk_pct=1.0,
                quantity=10
            )
            
            self.assertNotIn("error", result)
            self.assertEqual(result['symbol'], symbol)
            self.assertEqual(result['qty'], 10)
            
        finally:
            # Cleanup
            target_service.delete_paper_position(symbol)

if __name__ == "__main__":
    unittest.main()
