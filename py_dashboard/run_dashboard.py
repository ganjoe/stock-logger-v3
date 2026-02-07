import streamlit as st
import pandas as pd
from data_loader import load_data
from focus_input import render_focus_input

# --- Page Config ---
st.set_page_config(
    page_title="Trading Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed"
)

import os

                    # --- Load CSS ---
def local_css(file_name):
    # Construct absolute path relative to this script
    script_dir = os.path.dirname(__file__)
    file_path = os.path.join(script_dir, file_name)
    with open(file_path) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("styles.css")

# --- Title ---
st.title("Trading Dashboard")

# --- Data Loading ---
@st.cache_data(ttl=0)  # ttl=0 forces refresh on each run during development
def get_data():
    return load_data()

df, account_summary = get_data()

# --- Layout ---

# 1. Focus Input (Full Width or Top Section)
filter_mask, mode = render_focus_input(df)

if filter_mask is not None:
    df_focus = df[filter_mask]
else:
    df_focus = df
    
st.markdown("---") 

# Placeholder for modules to come
st.info(f"Filtered Data: {len(df_focus)} trades selected. Mode: {mode}")

# 2. Reality Check
from reality_check import render_reality_check
render_reality_check(df, df_focus, account_summary)

# 3. Charts
from charts import render_charts_section
render_charts_section(df_focus, mode)

# 4. Heatmap
from heatmap import render_heatmap
render_heatmap(df)
