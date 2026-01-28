import xml.etree.ElementTree as ET
import pandas as pd
import re

def create_html_dashboard(xml_file, html_file):
    """
    Reads portfolio data from an XML file and creates a styled HTML dashboard.

    Args:
        xml_file (str): The path to the input XML file.
        html_file (str): The path to the output HTML file.
    """
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        # --- Extract Summary Data ---
        start_date = root.findtext("Summary/ReportParams/StartDate", "N/A")
        end_date = root.findtext("Summary/ReportParams/EndDate", "N/A")
        total_invested = root.findtext("Summary/Inflow", "0.0")
        asset_value = root.findtext("Summary/AssetValue", "0.0")
        total_portfolio_value = root.findtext("Summary/TotalPortfolioValue", "0.0")
        
        cash_value = root.findtext("Summary/CashValue", "N/A")
        cash_balances_str = f"{cash_value} EUR" if cash_value != "N/A" else "N/A"

        # --- Extract Period Metrics ---
        # [Update] RealizedPnL is now a single aggregated value in EUR
        realized_pnl_node = root.find("Summary/PeriodMetrics/RealizedPnL")
        realized_pnl_str = f"{realized_pnl_node.text} {realized_pnl_node.get('currency', 'EUR')}" if realized_pnl_node is not None else "0,00 EUR"

        # [Update] Breakdown fields
        realized_gains = root.findtext("Summary/PeriodMetrics/RealizedGains", "0,00")
        realized_losses = root.findtext("Summary/PeriodMetrics/RealizedLosses", "0,00")
        unrealized_gains = root.findtext("Summary/UnrealizedGains", "0,00")
        unrealized_losses = root.findtext("Summary/UnrealizedLosses", "0,00")

        dividends_node = root.find("Summary/PeriodMetrics/Dividends")
        if dividends_node is not None:
            dividends_str = f"{dividends_node.text} {dividends_node.get('currency', 'EUR')}"
        else:
            dividends_str = "0.0"

        # --- Extract Position Data ---
        positions_data = []
        all_headers = set()
        
        position_nodes = root.findall("Positions/Position")
        if position_nodes:
            # First pass: get all possible headers from all positions
            for pos in position_nodes:
                for child in pos:
                    all_headers.add(child.tag)
            
            # Define a preferred order if possible, otherwise sort
            preferred_order = ['Symbol', 'Currency', 'Quantity', 'AvgEntryPrice', 'InvestedCapital', 'MarkPrice', 'PositionValue', 'UnrealizedPnL']
            ordered_headers = sorted(list(all_headers), key=lambda x: preferred_order.index(x) if x in preferred_order else len(preferred_order))


            # Second pass: extract data
            for pos in position_nodes:
                pos_data = {header: pos.findtext(header, "N/A") for header in ordered_headers}
                positions_data.append(pos_data)

        df = pd.DataFrame(positions_data)
        if not df.empty:
            df = df[ordered_headers] # Ensure column order
            
            # Prettify column headers
            df.columns = [col.replace('InvestedCapital_EUR_Cost', 'Invested Capital (EUR)').replace('_', ' ') for col in df.columns]

        # --- Generate HTML ---
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Portfolio Dashboard</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                    background-color: #121212;
                    color: #e0e0e0;
                    margin: 0;
                    padding: 20px;
                }}
                .dashboard {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .card {{
                    background-color: #1e1e1e;
                    border: 1px solid #333;
                    border-radius: 8px;
                    padding: 20px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                }}
                .card h3 {{
                    margin-top: 0;
                    color: #bb86fc;
                }}
                .card p {{
                    font-size: 1.5em;
                    margin: 0;
                }}
                h1 {{
                    text-align: center;
                    color: #03dac6;
                    margin-bottom: 30px;
                }}
                .table-container {{
                    background-color: #1e1e1e;
                    border-radius: 8px;
                    padding: 20px;
                    overflow-x: auto;
                }}
                .dataframe-table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                .dataframe-table th, .dataframe-table td {{
                    padding: 12px 15px;
                    text-align: left;
                    border-bottom: 1px solid #333;
                }}
                .dataframe-table th {{
                    background-color: #bb86fc;
                    color: #121212;
                }}
                .dataframe-table tbody tr:nth-of-type(even) {{
                    background-color: #232323;
                }}
                .dataframe-table tbody tr:hover {{
                    background-color: #3a3a3a;
                }}
            </style>
        </head>
        <body>
            <h1>Portfolio Dashboard</h1>
            <p style="text-align:center; margin-bottom: 30px;">Date Range: {start_date} to {end_date}</p>

            <div class="dashboard">
                <div class="card">
                    <h3>Total Invested Capital</h3>
                    <p>{total_invested}</p>
                </div>
                <div class="card">
                    <h3>Asset Value</h3>
                    <p>{asset_value}</p>
                </div>
                <div class="card">
                    <h3>Total Portfolio Value</h3>
                    <p>{total_portfolio_value}</p>
                </div>
                <div class="card">
                    <h3>Cash Balances</h3>
                    <p>{cash_balances_str}</p>
                </div>
                <div class="card">
                    <h3>Period Realized PnL</h3>
                    <p>{realized_pnl_str}</p>
                </div>
                <div class="card">
                    <h3>Realized Gains / Losses</h3>
                    <p style="color: #4caf50;">+{realized_gains}</p>
                    <p style="color: #cf6679;">{realized_losses}</p>
                </div>
                <div class="card">
                    <h3>Unrealized Gains / Losses</h3>
                    <p style="color: #4caf50;">+{unrealized_gains}</p>
                    <p style="color: #cf6679;">{unrealized_losses}</p>
                </div>
                <div class="card">
                    <h3>Period Dividends</h3>
                    <p>{dividends_str}</p>
                </div>
            </div>

            <div class="table-container">
                <h2>Open Positions</h2>
                {df.to_html(index=False, border=0, classes="dataframe-table") if not df.empty else "<p>No positions found.</p>"}
            </div>
            
            <footer>
                <p>Generated by viewer.py</p>
            </footer>

        </body>
        </html>
        """

        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"Successfully generated '{html_file}'")

    except FileNotFoundError:
        print(f"Error: The file '{xml_file}' was not found.")
    except ET.ParseError:
        print(f"Error: Could not parse the XML file '{xml_file}'. Check its format.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    create_html_dashboard("portfolio.xml", "portfolio.html")