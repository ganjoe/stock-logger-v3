import streamlit as st
import pandas as pd
import importlib
import py_manage_portfolio.models
import py_manage_portfolio.service

# Force reload modules to pick up class definition changes (e.g. new fields in dataclass)
# This prevents specific Streamlit caching issues during hot-reloading
importlib.reload(py_manage_portfolio.models)
importlib.reload(py_manage_portfolio.service)

from py_manage_portfolio.service import PortfolioService
from pathlib import Path

def render_portfolio_overview():
    """
    Renders the open positions and stop-loss management section.
    """
    st.header("🏢 Portfolio Overview & Risk Management")
    
    # Initialize Service
    # Absolute path to root
    root_dir = Path(__file__).parent.parent.resolve()
    service = PortfolioService(project_root=str(root_dir))
    
    # 1. Fetch Data
    with st.spinner("Fetching portfolio data..."):
        positions = service.get_open_positions()
        summary = service.get_summary()
        
    # 2. Key Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    
    with m1:
        st.metric("Total Invested", f"{summary.total_invested:,.2f} EUR")
    with m2:
        st.metric("Total Risk", f"{summary.total_risk:,.2f} EUR", delta=f"{(summary.total_risk/summary.equity * 100):.1f}% of Equity" if summary.equity else None, delta_color="inverse")
    with m3:
        st.metric("Unrealized P&L", f"{summary.total_unrealized_pl:,.2f} EUR", delta=f"{(summary.total_unrealized_pl/summary.total_invested * 100):.1f}%" if summary.total_invested else None)
    with m4:
        st.metric("Portfolio Health", f"{summary.count_ok} OK / {summary.count_trail} Trail", help="Positions with valid stop loss vs trailing/missing")

    st.markdown("---")
    
    # --- 3. Column Selector (Pinned/Fixed Layout) ---
    st.subheader("🛠️ Column Visibility")
    
    all_cols = ["Symbol", "Direction", "Days", "Qty", "Entry", "Market", "Invest", "Pos %", "P&L", "P&L %", "R", "Stop Loss", "Risk", "Risk %", "Status"]
    
    col_tooltips = {
        "Symbol": "Ticker-Symbol der Aktie. Dient zur eindeutigen Identifikation der Position.",
        "Direction": "Handelsrichtung (LONG oder SHORT). Bestimmt, wie Gewinne und Verluste berechnet werden.",
        "Days": "Haltedauer in Kalendertagen (Heutiges Datum - 1. Einstiegsdatum). Wichtig für 'Time-Stops' nach Minervini.",
        "Qty": "Anzahl der aktuell gehaltenen Stücke/Anteile.",
        "Entry": "Gewichteter durchschnittlicher Einstiegspreis. Basis für die P&L-Berechnung.",
        "Market": "Aktueller Marktpreis (Live-Daten oder letzter bekannter Kurs aus DataFetcher).",
        "Invest": "Aktueller Marktwert der Position (Qty * Marktpreis). Zeigt das gebundene Kapital an.",
        "Pos %": "Anteil der Position am Gesamt-Equity (Invest / Equity * 100). Hilft beim Exposure-Monitoring.",
        "P&L": "Unrealisierter Gewinn oder Verlust in Währung (Währung des Assets).",
        "P&L %": "Prozentualer Gewinn oder Verlust bezogen auf den Einstiegspreis.",
        "R": "Risiko-Multiple (P&L / Risiko). Zeigt an, wie viel des initialen Risikos bereits als Gewinn 'fällig' ist.",
        "Stop Loss": "Aktueller Preis-Level, bei dem die Position glattgestellt wird. Editierbar in der Tabelle.",
        "Risk": "Absolutes Risiko in Währung (abs(Entry - Stop) * Qty). Maximaler Verlust bei Stop-Greifen.",
        "Risk %": "Risiko der Position im Verhältnis zum Gesamt-Equity (Risk / Equity * 100). Wichtig für Kapitalerhalt.",
        "Status": "Status der Position: 'OK' (Risiko aktiv), 'Trail' (Stop im Gewinn / Break-Even erreicht)."
    }
    
    default_cols = ["Symbol", "Days", "Qty", "Market", "Invest", "Pos %", "P&L %", "R", "Stop Loss", "Risk %", "Status"]
    
    # Store selected columns in session state to prevent jumping/resetting
    if "selected_portfolio_cols" not in st.session_state:
        st.session_state.selected_portfolio_cols = default_cols

    # Arrange checkboxes in 2 rows for space-saving
    col_selector_container = st.container()
    with col_selector_container:
        row1 = st.columns(8) # Increased columns to fit more options
        row2 = st.columns(7)
        
        new_selection = []
        for i, col_name in enumerate(all_cols):
            target_row = row1 if i < 8 else row2
            col_idx = i if i < 8 else i - 8
            
            with target_row[col_idx]:
                is_selected = st.checkbox(
                    col_name, 
                    value=(col_name in st.session_state.selected_portfolio_cols),
                    key=f"toggle_{col_name}",
                    help=col_tooltips.get(col_name, "")
                )
                if is_selected:
                    new_selection.append(col_name)
        
        st.session_state.selected_portfolio_cols = new_selection

    st.markdown("---")
    
    # --- 4. Open Positions Table ---
    if not positions:
        st.info("No open positions found in trades.xml.")
        return

    # Convert to DataFrame for display
    data = []
    equity = summary.equity if summary.equity and summary.equity > 0 else 1.0 # Avoid div/0
    
    for p in positions:
        status_val = p.status_flags[0] if p.status_flags else "-"
        invest_val = p.market_value if p.market_value else 0.0
        risk_val = p.initial_risk if p.initial_risk else 0.0
        
        pos_pct = (invest_val / equity) * 100
        risk_pct = (risk_val / equity) * 100
        
        # Robust access to days_held (handle stale class definition)
        days_held = getattr(p, "days_held", 0)
        
        data.append({
            "Symbol": p.symbol,
            "Direction": p.direction,
            "Days": days_held,
            "Qty": p.quantity,
            "Entry": p.entry_price,
            "Market": p.current_price,
            "Invest": invest_val,
            "Pos %": pos_pct,
            "P&L": p.unrealized_pl,
            "P&L %": p.unrealized_pct,
            "R": p.r_multiple,
            "Stop Loss": p.stop_loss,
            "Risk": risk_val,
            "Risk %": risk_pct,
            "Status": status_val
        })
    df_pos = pd.DataFrame(data)
    
    # Check if we are running with stale models
    if positions and not hasattr(positions[0], "days_held"):
         st.warning("⚠️ Data model update detected. Please restart the Streamlit server to see 'Days' correctly.")
    
    # --- Styling Functions ---
    def style_pnl(val):
        color = '#00c853' if val >= 0 else '#ff1744'
        return f'color: {color}; font-weight: bold'

    def style_status(val):
        if val == "OK":
            return 'background-color: rgba(0, 200, 83, 0.1); color: #00c853; font-weight: bold'
        elif val == "Trail":
            return 'background-color: rgba(255, 214, 0, 0.1); color: #ffd600; font-weight: bold'
        return ''

    # Filter columns based on selection
    # Always keep Symbol if it's the anchor, or just use selection
    display_cols = st.session_state.selected_portfolio_cols
    if not display_cols:
        st.warning("Please select at least one column to display.")
        return
        
    df_display = df_pos[display_cols]

    # Apply Styler only to existing columns
    style_subset_pnl = [c for c in ['P&L', 'P&L %', 'R'] if c in display_cols]
    style_subset_status = ['Status'] if 'Status' in display_cols else []
    
    styled_df = df_display.style
    if style_subset_pnl:
        styled_df = styled_df.applymap(style_pnl, subset=style_subset_pnl)
    if style_subset_status:
        styled_df = styled_df.applymap(style_status, subset=style_subset_status)

    # Add alternating row colors (Zebra stripes)
    styled_df = styled_df.set_table_styles([
        {'selector': 'tr:nth-child(even)', 'props': [('background-color', '#1c2025')]},
        {'selector': 'tr:nth-child(odd)', 'props': [('background-color', '#262730')]},
        {'selector': 'td', 'props': [('border', '1px solid #31333F')]},
    ])

    # Formatting percentages and decimals
    format_dict = {}
    if "Invest" in display_cols: format_dict["Invest"] = "{:,.2f}"
    if "Pos %" in display_cols: format_dict["Pos %"] = "{:,.1f}%"
    if "P&L" in display_cols: format_dict["P&L"] = "{:,.2f}"
    if "P&L %" in display_cols: format_dict["P&L %"] = "{:,.1f}%"
    if "R" in display_cols: format_dict["R"] = "{:,.1f}"
    if "Entry" in display_cols: format_dict["Entry"] = "{:,.2f}"
    if "Market" in display_cols: format_dict["Market"] = "{:,.2f}"
    if "Stop Loss" in display_cols: format_dict["Stop Loss"] = "{:,.2f}"
    if "Risk" in display_cols: format_dict["Risk"] = "{:,.2f}"
    if "Risk %" in display_cols: format_dict["Risk %"] = "{:,.1f}%"
    
    if format_dict:
        styled_df = styled_df.format(format_dict)

    st.subheader("Open Positions")
    
    # Column configuration
    full_column_config = {
        "Symbol": st.column_config.TextColumn("Symbol", width="small", disabled=True),
        "Direction": st.column_config.TextColumn("Dir", width="small", disabled=True),
        "Days": st.column_config.NumberColumn("Days", format="%d", disabled=True),
        "Qty": st.column_config.NumberColumn("Qty", format="%.0f", disabled=True),
        "Entry": st.column_config.NumberColumn("Entry", format="%.2f", disabled=True),
        "Market": st.column_config.NumberColumn("Market", format="%.2f", disabled=True),
        "Invest": st.column_config.NumberColumn("Invest", format="%.2f", disabled=True),
        "Pos %": st.column_config.NumberColumn("Pos %", format="%.1f%%", disabled=True),
        "P&L": st.column_config.NumberColumn("P&L", format="%.2f", disabled=True),
        "P&L %": st.column_config.NumberColumn("P&L %", format="%.1f%%", disabled=True),
        "R": st.column_config.NumberColumn("R", format="%.1f", disabled=True),
        "Stop Loss": st.column_config.NumberColumn("Stop Loss", format="%.2f", help="Edit this to update Stop Loss", required=False),
        "Risk": st.column_config.NumberColumn("Risk", format="%.2f", disabled=True),
        "Risk %": st.column_config.NumberColumn("Risk %", format="%.1f%%", disabled=True),
        "Status": st.column_config.TextColumn("Status", width="small", disabled=True)
    }
    # Filter config for selected columns
    current_column_config = {k: v for k, v in full_column_config.items() if k in display_cols}

    # Render with Data Editor
    # height="content" makes the table expand to show all rows without internal scrollbar
    edited_df = st.data_editor(
        styled_df,
        column_config=current_column_config,
        hide_index=True,
        use_container_width=True,
        height="content",
        key="portfolio_editor"
    )
    
    # Check for changes in Stop Loss
    if "Stop Loss" in display_cols:
        # Comparison logic needs careful alignment with original data
        if not edited_df["Stop Loss"].equals(df_pos["Stop Loss"]):
            diff_mask = edited_df["Stop Loss"] != df_pos["Stop Loss"]
            changed_positions = edited_df[diff_mask]
            
            for _, row in changed_positions.iterrows():
                symbol = row["Symbol"]
                new_stop = row["Stop Loss"]
                
                try:
                    stop_val = 0.0 if pd.isna(new_stop) else float(new_stop)
                    if service.update_stop_loss(symbol, stop_val):
                        st.success(f"✓ Updated Stop Loss for {symbol} to {stop_val:.2f}")
                    else:
                        st.error(f"Failed to update {symbol}")
                except Exception as e:
                    st.error(f"Error updating {symbol}: {e}")
                
            st.rerun()

    # 4. Actions
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Refresh Data"):
            st.rerun()
    with col1:
        if st.button("📡 Force Update Prices"):
            with st.status("Fetching live prices..."):
                service.get_open_positions(update_prices=True)
            st.rerun()

