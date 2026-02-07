import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

def render_heatmap(df):
    """
    Renders the Monthly Heatmap tiles.
    Uses a custom HTML/CSS grid or Plotly Heatmap. 
    Given the requirement for text inside tiles (Date, Winrate, PnL), 
    Plotly Heatmap texttemplate is good, or a CSS Grid.
    CSS Grid gives more control over the "Square" look and complex content.
    Let's use a CSS Grid approach via Streamlit columns for simplicity and good integration,
    or a collection of highly styled metrics.
    
    Actually, Plotly Heatmap is robust for "Year vs Month" grids.
    But requirement says: "square symbols... containing text: date, winrate, pnl".
    A pure CSS grid is likely best for this "Tile" feel.
    """
    
    st.markdown("### Monthly Performance Heatmap")
    
    if df.empty:
        st.info("No data available for heatmap.")
        return

    # 1. Resample Data to Monthly
    df_monthly = df.set_index('Date').resample('ME').agg({
        'Trade_PnL': 'sum',
        'Trade_R': 'count' # Just to count trades
    })
    
    # Calculate Winrate per month
    # Need to iterate or do complex groupby
    monthly_stats = []
    
    # Group by Year-Month
    df['YearMonth'] = df['Date'].dt.to_period('M')
    grouped = df.groupby('YearMonth')
    
    for period, group in grouped:
        wins = len(group[group['Trade_PnL'] > 0])
        total = len(group)
        winrate = (wins / total * 100) if total > 0 else 0
        pnl = group['Trade_PnL'].sum()
        
        monthly_stats.append({
            'Period': period,
            'Year': period.year,
            'Month': period.month,
            'MonthName': period.strftime('%b'),
            'PnL': pnl,
            'Winrate': winrate,
            'Trades': total
        })
    
    stats_df = pd.DataFrame(monthly_stats)
    
    if stats_df.empty:
        st.write("No monthly stats.")
        return

    # Get unique years and months
    years = sorted(stats_df['Year'].unique(), reverse=True)
    months = list(range(1, 13))  # Jan to Dec
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # Create pivot table: rows = months, columns = years
    # Render as grid: Columns = Years, Rows = Months
    
    # Header row with year labels
    header_cols = st.columns([0.5] + [1] * len(years))
    header_cols[0].markdown("**Monat**")
    for i, year in enumerate(years):
        header_cols[i + 1].markdown(f"**{year}**")
    
    # Data rows: one per month
    for month in months:
        row_cols = st.columns([0.5] + [1] * len(years))
        row_cols[0].markdown(f"**{month_names[month-1]}**")
        
        for i, year in enumerate(years):
            # Find data for this month/year
            cell_data = stats_df[(stats_df['Year'] == year) & (stats_df['Month'] == month)]
            
            with row_cols[i + 1]:
                if cell_data.empty:
                    # No data for this cell
                    st.markdown("<div style='height:80px; background:rgba(128,128,128,0.1); border-radius:4px;'></div>", unsafe_allow_html=True)
                else:
                    row = cell_data.iloc[0]
                    bg_color = "rgba(0, 200, 83, 0.2)" if row['PnL'] >= 0 else "rgba(255, 23, 68, 0.2)"
                    border_color = "#00c853" if row['PnL'] >= 0 else "#ff1744"
                    text_color = "#00c853" if row['PnL'] >= 0 else "#ff1744"
                    
                    html = f"""
                    <div style="
                        background-color: {bg_color};
                        border: 1px solid {border_color};
                        border-radius: 4px;
                        padding: 6px;
                        text-align: center;
                        height: 80px;
                        display: flex;
                        flex-direction: column;
                        justify-content: center;
                    ">
                        <div style="font-size: 0.8em; margin-bottom: 2px;">
                            WR: {row['Winrate']:.0f}%
                        </div>
                        <div style="color: {text_color}; font-weight: bold; font-size: 1em;">
                            €{row['PnL']:,.0f}
                        </div>
                        <div style="font-size: 0.7em; color: #aaa;">
                            ({row['Trades']} Trds)
                        </div>
                    </div>
                    """
                    st.markdown(html, unsafe_allow_html=True)
