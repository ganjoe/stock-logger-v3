import streamlit as st
import plotly.graph_objects as go
import pandas as pd

def render_chart_module(df, chart_type, key_prefix, mode):
    """
    Renders a specific chart module (EUR, PCT, or FAC).
    
    Args:
        df (pd.DataFrame): The data to plot.
        chart_type (str): 'EUR', 'PCT', 'FAC'
        key_prefix (str): Unique key for widgets.
        mode (str): 'Ereignisbasiert' or 'Zeitbasiert'.
    """
    
    # ... (traces definition identical to existing code) ...
    # Define available series for each type with tooltips
    if chart_type == 'EUR':
        available_traces = {
            'Equity': {
                'col': 'Equity', 
                'color': '#00e676', 
                'default': True,
                'help': 'Gesamtvermögen (Cash + Positionen). Formel: Equity = Cash + Total_Assets'
            },
            'Cash': {
                'col': 'Cash', 
                'color': '#2196f3', 
                'default': False,
                'help': 'Verfügbares Bargeld (Buying Power). Erhöht sich durch Verkäufe, Dividenden, Einzahlungen. Reduziert sich durch Käufe, Auszahlungen.'
            },
            'Total Assets': {
                'col': 'Total_Assets', 
                'color': '#ff9800', 
                'default': False,
                'help': 'Liquidationswert aller offenen Positionen (ohne Cash). Formel: Total_Assets = Equity - Cash'
            },
            'PnL': {
                'col': 'Trade_PnL', 
                'color': '#2979ff', 
                'default': False,
                'help': 'Gewinn/Verlust des einzelnen Trades in EUR. Positiv = Gewinn, Negativ = Verlust.'
            },
            'Drawdown': {
                'col': 'Drawdown', 
                'color': '#ff1744', 
                'default': False,
                'help': 'Rückgang vom Höchststand in EUR (bereinigt um Ein-/Auszahlungen). Formel: Adjusted_Equity - High Water Mark'
            }
        }
        y_format = "€%{y:,.0f}"
        title = "Capital Curve (€)"
        
    elif chart_type == 'PCT':
        available_traces = {
            'Winrate (20d)': {
                'col': 'Rolling_Winrate', 
                'color': '#ffd600', 
                'default': True,
                'help': 'Gleitende Gewinnrate über die letzten 20 Trades. Formel: (Anzahl Gewinn-Trades / 20) × 100%'
            },
            'Drawdown %': {
                'col': 'Drawdown_Pct', 
                'color': '#ff1744', 
                'default': False,
                'help': 'Prozentualer Rückgang vom Höchststand (bereinigt um Ein-/Auszahlungen). Formel: Drawdown / High Water Mark × 100%'
            },
            'PnL %': {
                'col': 'PnL_Pct', 
                'color': '#00e676', 
                'default': False,
                'help': 'Relative Performance im gewählten Zeitraum (startet bei 0%). Formel: (Equity - Start_Equity) / Start_Equity × 100%'
            },
            'Investitionsquote': {
                'col': 'Investment_Ratio', 
                'color': '#9c27b0', 
                'default': False,
                'help': 'Anteil des investierten Kapitals am Gesamtvermögen. Formel: Total_Assets / Equity × 100%. Hohe Werte = stark investiert.'
            }
        }
        y_format = "%{y:.1f}%"
        title = "Performance (%)"
        
    elif chart_type == 'FAC':
         available_traces = {
            'R-Value': {
                'col': 'Trade_R', 
                'color': '#aa00ff', 
                'default': True,
                'help': 'Risiko-Rendite-Verhältnis des Trades. Formel: Trade_PnL / Risiko_pro_Trade. R=1 bedeutet: Gewinn = geplantes Risiko.'
            },
            'Trade Count': {
                'col': 'Relative_Trade_Count', 
                'color': '#00bcd4', 
                'default': False,
                'help': 'Kumulative Anzahl der Trades im gewählten Zeitraum (startet bei 0). Zeigt die Trading-Aktivität über Zeit.'
            },
            'Profit Factor': {
                'col': 'Profit_Factor', 
                'color': '#4caf50', 
                'default': False,
                'help': 'Verhältnis Gewinne zu Verlusten (Rolling 20 Trades). Formel: Σ Gewinne / |Σ Verluste|. PF > 1 = profitabel, PF > 2 = sehr gut.'
            }
        }
         y_format = "%{y:.2f}"
         title = "Efficiency Factor"
    
    else:
        return

    # Container structure
    with st.container():
         st.markdown(f"### {title}")
         
         selected_traces = []
         cols = st.columns(len(available_traces))
         
         for i, (label, config) in enumerate(available_traces.items()):
             k = f"{key_prefix}_toggle_{label}"
             with cols[i]:
                 is_checked = st.checkbox(label, value=config['default'], key=k, help=config.get('help', ''))
             if is_checked:
                 selected_traces.append(label)
         
         if not selected_traces:
             st.warning("Select at least one series.")
             return

         # 2. Plot
         fig = go.Figure()
         
         # Calculate PnL_Pct dynamically for the current window (always starts at 0%)
         if 'Equity' in df.columns and len(df) > 0:
             initial_equity = df['Equity'].iloc[0]
             if initial_equity > 0:
                 df = df.copy()  # Avoid modifying original
                 df['PnL_Pct'] = ((df['Equity'] - initial_equity) / initial_equity) * 100
             else:
                 df = df.copy()
                 df['PnL_Pct'] = 0.0
             
             # Calculate Relative_Trade_Count (starts at 0 in each window)
             if 'Trade_Count' in df.columns:
                 initial_count = df['Trade_Count'].iloc[0]
                 df['Relative_Trade_Count'] = df['Trade_Count'] - initial_count
             
             # Calculate Investment_Ratio (Investitionsquote): Total_Assets / Equity * 100
             if 'Total_Assets' in df.columns:
                 mask = df['Equity'] > 0
                 df['Investment_Ratio'] = 0.0
                 df.loc[mask, 'Investment_Ratio'] = (df.loc[mask, 'Total_Assets'] / df.loc[mask, 'Equity']) * 100
             
             # Calculate rolling Profit Factor (sum of wins / abs(sum of losses)) over last 20 trades
             if 'Trade_PnL' in df.columns:
                 # Only consider actual trades (where Trade_PnL != 0)
                 df['Profit_Factor'] = 1.0  # Default
                 trade_mask = df['Trade_PnL'] != 0
                 if trade_mask.sum() > 0:
                     # For rolling calculation, we need to compute on trades only
                     wins = df['Trade_PnL'].clip(lower=0)
                     losses = df['Trade_PnL'].clip(upper=0).abs()
                     rolling_wins = wins.rolling(window=20, min_periods=1).sum()
                     rolling_losses = losses.rolling(window=20, min_periods=1).sum()
                     # Avoid division by zero
                     df['Profit_Factor'] = rolling_wins / rolling_losses.replace(0, 1)
                     df['Profit_Factor'] = df['Profit_Factor'].fillna(1.0).clip(upper=10)  # Cap at 10 for display
         
         # Determin X-Axis
         if mode == "Ereignisbasiert":
             # Use a simple integer sequence for X to show events equidistantly
             # Reset index to get 0..N
             x_data = df.reset_index().index
             x_title = "Event #"
         else:
             x_data = df['Date']
             x_title = "Date"
         
         # Determin X-Axis
         if mode == "Ereignisbasiert":
             # Use a simple integer sequence for X to show events equidistantly
             # Reset index to get 0..N
             x_data = df.reset_index().index
             x_title = "Event #"
         else:
             x_data = df['Date']
             x_title = "Date"

         for label in selected_traces:
             config = available_traces[label]
             col_name = config['col']
             
             # Determine chart type based on label
             # R-Value and PnL are bar charts, everything else is line
             if label == 'R-Value' or label == 'PnL':
                  fig.add_trace(go.Bar(
                     x=x_data, 
                     y=df[col_name],
                     name=label,
                     marker_color=config['color']
                 ))
             else:
                 fig.add_trace(go.Scatter(
                     x=x_data, 
                     y=df[col_name],
                     mode='lines',
                     name=label,
                     line=dict(color=config['color'], width=2)
                 ))
         
         fig.update_layout(
             template="plotly_dark",
             paper_bgcolor='rgba(0,0,0,0)',
             plot_bgcolor='rgba(0,0,0,0)',
             margin=dict(l=0, r=0, t=20, b=0),
             height=300,
             yaxis=dict(tickformat=y_format.replace("%{y:,.0f}", ",.0f").replace("%{y:.1f}%", ".1f").replace("%{y:.2f}R", ".2f")),
             xaxis=dict(showgrid=False, title=x_title),
             showlegend=False
         )
         
         st.plotly_chart(fig, use_container_width=True)

def render_charts_section(df, mode="Zeitbasiert"):
    """Renders the three chart modules."""
    
    # Section 1: EUR
    render_chart_module(df, 'EUR', 'chart_eur', mode)
    st.markdown("---")
    
    # Section 2: PCT
    render_chart_module(df, 'PCT', 'chart_pct', mode)
    st.markdown("---")
    
    # Section 3: FAC
    render_chart_module(df, 'FAC', 'chart_fac', mode)
    st.markdown("---")
    
