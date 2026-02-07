import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

def render_focus_input(df):
    """
    Renders the Focus Input tile and returns a boolean mask for the DataFrame.
    
    Args:
        df (pd.DataFrame): The source dataframe containing 'Date'.
        
    Returns:
        pd.Series: Boolean mask representing the selected rows.
    """
    with st.container():
        # Apply CSS class for styling
        st.markdown('<div class="focus-container">', unsafe_allow_html=True)
        st.markdown('<div class="focus-header">Focus Input</div>', unsafe_allow_html=True)
        
        # Mode Selection
        mode = st.radio(
            "Mode",
            options=["Zeitbasiert", "Ereignisbasiert"],
            horizontal=True,
            label_visibility="collapsed"
        )
        
        mask = None
        
        if mode == "Zeitbasiert":
            col_input, col_presets = st.columns([1, 2])
            
            # Default to last 30 days if not set
            # User Request: End date should be current date
            now = datetime.now()
            max_date_data = df['Date'].max() if not df.empty else now
            min_date_data = df['Date'].min() if not df.empty else now
            
            default_end = now
            default_start = default_end - timedelta(days=30)

            if "focus_date_start" not in st.session_state:
                st.session_state.focus_date_start = default_start
            if "focus_date_end" not in st.session_state:
                st.session_state.focus_date_end = default_end

            with col_input:
                col_von, col_bis = st.columns(2)
                with col_von:
                    start_date = st.date_input(
                        "Von",
                        key="focus_date_start",
                        format="DD.MM.YYYY"
                    )
                with col_bis:
                    end_date = st.date_input(
                        "Bis",
                        key="focus_date_end",
                        format="DD.MM.YYYY"
                    )
            
            with col_presets:
                st.write("Presets:")
                cols = st.columns(4)
                
                cols[0].button("1M", on_click=lambda: st.session_state.update(focus_date_start=now - timedelta(days=30), focus_date_end=now))
                cols[1].button("3M", on_click=lambda: st.session_state.update(focus_date_start=now - timedelta(days=90), focus_date_end=now))
                
                # YTD
                start_ytd = datetime(now.year, 1, 1)
                cols[2].button("YTD", on_click=lambda: st.session_state.update(focus_date_start=start_ytd, focus_date_end=now))
                
                cols[3].button("ALL", on_click=lambda: st.session_state.update(focus_date_start=min_date_data, focus_date_end=max_date_data))
            
            # Filter Logic
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            mask = (df['Date'] >= start_dt) & (df['Date'] <= end_dt)
                 
        else: # Ereignisbasiert
            col_input, col_presets = st.columns([1, 2])
            
            if "focus_num_trades" not in st.session_state:
                st.session_state.focus_num_trades = 20

            with col_input:
                num_trades = st.number_input(
                    "Anzahl Trades",
                    min_value=1,
                    max_value=len(df),
                    key="focus_num_trades"
                )
            
            with col_presets:
                st.write("Presets:")
                cols = st.columns(4)
                cols[0].button("10", on_click=lambda: st.session_state.update(focus_num_trades=10))
                cols[1].button("20", on_click=lambda: st.session_state.update(focus_num_trades=20))
                cols[2].button("90", on_click=lambda: st.session_state.update(focus_num_trades=90))
                cols[3].button("ALL", on_click=lambda: st.session_state.update(focus_num_trades=len(df)))
                
            # Filter Logic: Last N trades using Trade_Count column
            # We want the last N closed trades.
            # Max Trade Count in data
            max_tc = df['Trade_Count'].max()
            # Threshold: Show everything associated with trades > (Max - N)
            threshold = max_tc - num_trades
            mask = df['Trade_Count'] > threshold
            
        st.markdown('</div>', unsafe_allow_html=True)
        
        return mask, mode
