import streamlit as st
import pandas as pd
from data_loader import load_data
from focus_input import render_focus_input

# --- Page Config ---
st.set_page_config(
    page_title="Trading Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
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


# --- Sidebar Import ---
from workflow_manager import WorkflowManager, ProcessResult
from pathlib import Path
import time

st.sidebar.markdown("---")
st.sidebar.header("Data Import")
uploaded_file = st.sidebar.file_uploader("Upload Broker CSV", type=["csv"])

if uploaded_file is not None:
    if st.sidebar.button("Run Import Process"):
        with st.sidebar.status("Processing...", expanded=True) as status:
            # Init Workflow Manager (assuming run from root, so root is '.')
            # If run from py_dashboard, root is '..'
            # Let's use absolute path relative to this file
            root_dir = Path(__file__).parent.parent.resolve()
            manager = WorkflowManager(root_dir)
            
            st.write(" Saving file...")
            save_path = manager.save_uploaded_file(uploaded_file, uploaded_file.name)
            st.write("✓ File saved.")
            
            st.write(" Running CSV Parser...")
            # Run parser explicitly on the new file to avoid ambiguity
            # We need to modify WorkflowManager to accept path if we want explicit
            # For now, let's rely on auto-discovery or pass the filename if parser accepts relative path?
            # run_csv_parser.py accepts absolute path.
            
            # Re-instantiate manager or modify run_parser to take args?
            # I implemented run_parser to take NO args.
            # I will trust auto-discovery for now as newly uploaded file is newest.
            res_parser = manager.run_parser()
            
            if res_parser.success:
                st.write("✓ Parser finished.")
                st.code(res_parser.output)
            else:
                st.error("Parser failed!")
                st.code(res_parser.error)
                status.update(label="Import Failed", state="error")
                st.stop()
                
            st.write(" Updating History...")
            res_hist = manager.run_portfolio_history()
            
            if res_hist.success:
                st.write("✓ History updated.")
                status.update(label="Import Complete", state="complete")
                time.sleep(1)
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("History update failed!")
                st.code(res_hist.error)
                status.update(label="Import Failed", state="error")
