
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import sys
import os

# Add Dashboard path
DASHBOARD_PATH = "/Users/daniel/stock-logger-dashboard/py_dashboard"
if DASHBOARD_PATH not in sys.path:
    sys.path.append(DASHBOARD_PATH)

# Import the module to test
import data_loader

class TestDashboardMetrics(unittest.TestCase):
    
    @patch('data_loader.pd.read_csv')
    def test_net_inflows_calculation(self, mock_read_csv):
        # Create a mock DataFrame simulating journal.csv
        data = {
            'date': ['2025-01-01', '2025-01-02'],
            'time': ['12:00:00', '13:00:00'],
            'Trade_PnL': [0.0, 100.0],
            'Sum_Deposit': [15000.0, 15000.0],
            'Sum_Withdrawal': [2000.0, 2000.0],
            'Sum_Dividend': [50.0, 50.0],
            'Sum_Fee': [142.50, 142.50],
            'Equity': [13050.0, 13150.0],
            'event': ['deposit', 'sell'],
            'Trade_R': [0.0, 1.0], 'Fee': [0.0, 2.0], 'Cashflow': [0.0, 0.0], 'Dividend': [0.0, 0.0], 
            'Cash': [13050.0, 13150.0], 'Total_Assets': [0.0, 0.0], 'Drawdown': [0.0, 0.0], 'Trade_Count': [0, 1],
            'Open_Positions': [0, 1]
        }
        mock_df = pd.DataFrame(data)
        mock_read_csv.return_value = mock_df
        
        # Call function
        df, summary = data_loader.load_data()
        
        # In reality_check, calculate_kpis is used. I'll test it indirectly or just ensure summary is ok.
        # But wait, reality_check is what calculates TotalTrades. 
        # I'll add a check to the test to verify reality_check logic too if possible.
        import reality_check
        kpis = reality_check.calculate_kpis(df)
        
        self.assertEqual(summary['Total_Inflows'], 13000.0)
        self.assertEqual(summary['Total_Fees'], 142.50)
        self.assertEqual(kpis['TotalTrades'], 1)

if __name__ == '__main__':
    unittest.main()
