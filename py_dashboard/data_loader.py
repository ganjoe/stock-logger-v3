import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta

def load_data():
    """
    Loads data from journal.csv and prepares the DataFrame and Account Summary.
    """
    # Load CSV
    try:
        df = pd.read_csv("journal.csv", sep=";")
    except FileNotFoundError:
        st.error("journal.csv not found!")
        return pd.DataFrame(), {}
    
    # Combine Date and Time
    df['Date'] = pd.to_datetime(df['date'] + ' ' + df['time'], format="%Y-%m-%d %H:%M:%S")
    
    # Ensure numeric types
    numeric_cols = ['Trade_PnL', 'Trade_R', 'Fee', 'Cashflow', 'Dividend', 'Equity', 'Cash', 'Total_Assets', 'Drawdown', 'Sum_Deposit', 'Sum_Withdrawal', 'Sum_Dividend', 'Trade_Count']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    # --- Derived Metrics for Charts (View Layer) ---
    # These are strictly for visualization and derived from the pre-calculated state
    
    # 1. Drawdown %
    # Drawdown_Eur is in CSV ('Drawdown'). We need Peak Equity to Calc %. 
    # Since Drawdown = Equity - Peak, then Peak = Equity - Drawdown (Double Neg? No, DD is neg).
    # Peak = Equity - Drawdown (since DD is negative value, extracting it adds it back? Let's check sign).
    # In CSV example: Equity 99490, Drawdown -1005. Peak was ~100495. 
    # 99490 - (-1005) = 100495. Correct.
    df['Peak_Equity'] = df['Equity'] - df['Drawdown']
    
    # Avoid div by zero
    df['Drawdown_Pct'] = 0.0
    mask = df['Peak_Equity'] > 0
    df.loc[mask, 'Drawdown_Pct'] = (df.loc[mask, 'Drawdown'] / df.loc[mask, 'Peak_Equity']) * 100
    
    # 2. Rolling Winrate (20 trades)
    # We filter for trades only to calculate this correctly
    df['Is_Win'] = (df['event'] == 'sell') & (df['Trade_PnL'] > 0)
    # We want a rolling winrate on TRADES only. 
    # But we need it mapped back to the main timeline? 
    # Usually simplest is to just calc it on the whole DF? 
    # Non-trade rows are not wins or losses.
    # Approach: Calculate on subset, join back? Or just rolling on boolean column where non-trades are NaN?
    
    trade_mask = df['event'] == 'sell'
    df.loc[trade_mask, 'Rolling_Winrate'] = df.loc[trade_mask, 'Is_Win'].rolling(window=20, min_periods=1).mean() * 100
    df['Rolling_Winrate'] = df['Rolling_Winrate'].ffill().fillna(0.0) # Forward fill for non-trade days
    
    # Note: PnL_Pct is calculated dynamically in charts.py based on the filtered window
    
    # 3. Rename/Alias for compatibility with existing modules if needed,
    # or strictly update modules. Let's alias some for `charts.py` compatibility to match "Logic Free" requirements matrix.
    # Actually, better to stick to new names in modules.
    
    # --- Account Summary ---
    if not df.empty:
        last_row = df.iloc[-1]
        summary = {
            'Net_Worth': last_row['Equity'],
            'Buying_Power': last_row['Equity'], # Simplified, assumes 100% Cash/BP match or ignoring margin
            'Total_Assets': last_row['Equity'], # Simplified
            'Total_Inflows': last_row['Sum_Deposit'],
            'Total_Dividends': last_row['Sum_Dividend']
        }
    else:
        summary = {
            'Net_Worth': 0, 'Buying_Power': 0, 'Total_Assets': 0, 'Total_Inflows': 0, 'Total_Dividends': 0
        }
    
    return df, summary
