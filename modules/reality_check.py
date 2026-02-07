import streamlit as st
import pandas as pd

def calculate_kpis(df):
    """Calculates basic KPIs for a given dataframe."""
    if df.empty:
        return {
            'Winrate': 0.0,
            'ProfitFactor': 0.0,
            'AvgR': 0.0,
            'AvgLoss': 0.0
        }
    
    wins = df[df['Trade_PnL'] > 0]
    losses = df[df['Trade_PnL'] <= 0]
    
    # Filter out non-trade rows (PnL 0) if they are not actual losses? 
    # CSV spec: Trade_PnL is 0 for deposits/divs. We should filter `event` == 'sell' or 'buy' (if we track open PnL? No, CSV is realized).
    # Assuming 'sell' generates the PnL.
    # Better: Filter where Trade_PnL != 0 OR event is trade type.
    # Simplest: wins > 0, losses < 0. (Breakeven trades = 0? Need to handle).
    # Let's use event type filter strictly.
    trades_only = df[df['event'] == 'sell']
    wins = trades_only[trades_only['Trade_PnL'] > 0]
    losses = trades_only[trades_only['Trade_PnL'] <= 0]
    
    winrate = (len(wins) / len(trades_only)) * 100 if len(trades_only) > 0 else 0
    
    gross_profit = wins['Trade_PnL'].sum()
    gross_loss = abs(losses['Trade_PnL'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    avg_r = trades_only['Trade_R'].mean()
    avg_loss = losses['Trade_PnL'].mean() if not losses.empty else 0.0
    
    return {
        'Winrate': winrate,
        'ProfitFactor': profit_factor,
        'AvgR': avg_r,
        'AvgLoss': avg_loss
    }

def get_status(kpis):
    """Determines the Minervini Status based on KPIs."""
    pf = kpis['ProfitFactor']
    wr = kpis['Winrate']
    
    # Logic based on requirements
    # RED: PF < 1.0
    # YELLOW: PF 1.0 - 2.0
    # GREEN: PF > 2.0 and WR > 40.0
    
    text = "UNKNOWN"
    color_class = "status-green"
    
    if pf < 1.0:
        text = "CHOP FEST: CASH IS KING / SIT ON HANDS"
        color_class = "status-red"
    elif pf >= 1.0 and pf < 2.0:
        text = "EVALUATION MODE: PILOT BUYS ONLY"
        color_class = "status-yellow"
    elif pf >= 2.0 and wr > 40.0:
        text = "POWER PLAY: AGGRESSIVE EXPOSURE / PYRAMIDING"
        color_class = "status-green"
    else:
        text = "EVALUATION MODE: PILOT BUYS ONLY"
        color_class = "status-yellow"
        
    return text, color_class

def render_reality_check(df_all, df_focus, account_summary):
    """
    Renders the Reality Check tile.
    """
    # 1. Account Summary (Outside functionality of Focus Input logic usually, but here displayed)
    # Using container for styling if needed, currently just columns
    st.markdown("### Account Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net Worth", f"€{account_summary['Net_Worth']:,.0f}")
    c2.metric("Total Inflows", f"€{account_summary['Total_Inflows']:,.0f}")
    c3.metric("Total Dividends", f"€{account_summary['Total_Dividends']:,.0f}")
    # c4 Reserved or remove
    # c4.metric("Buying Power", f"€{account_summary['Buying_Power']:,.0f}") 
    # Let's stick to Requirements: Dividend KPI explicitly requested.
    
    st.markdown("---")
    
    # 2. Stats & Status
    stats_all = calculate_kpis(df_all)
    stats_focus = calculate_kpis(df_focus)
    
    status_text, status_class = get_status(stats_focus)
    
    c_left, c_right = st.columns([2, 1])
    
    with c_left:
        st.markdown("### Reality Check")
        
        # Header
        h1, h2, h3 = st.columns([2, 1, 1])
        h1.markdown("**Metric**")
        h2.markdown("**All Time**")
        h3.markdown("**Focus**")
        
        # Rows
        def render_row(label, val_all, val_focus, fmt="{:.2f}"):
            r1, r2, r3 = st.columns([2, 1, 1])
            r1.write(label)
            r2.write(fmt.format(val_all))
            r3.write(fmt.format(val_focus))
            
        render_row("Winrate (%)", stats_all['Winrate'], stats_focus['Winrate'], "{:.1f}%")
        render_row("Profit Factor", stats_all['ProfitFactor'], stats_focus['ProfitFactor'], "{:.2f}")
        render_row("Avg. R-Value", stats_all['AvgR'], stats_focus['AvgR'], "{:.2f}R")
        render_row("Avg. Loss (€)", stats_all['AvgLoss'], stats_focus['AvgLoss'], "€{:,.0f}")

    with c_right:
         st.markdown(f"""
            <div class="metric-container">
                <div style="margin-bottom: 0.5rem; color: #888;">Current Market Status</div>
                <div class="status-badge {status_class}">
                    {text_status_formatting(status_text)}
                </div>
            </div>
         """, unsafe_allow_html=True)

def text_status_formatting(text):
    return text.replace("/", "<br>")
