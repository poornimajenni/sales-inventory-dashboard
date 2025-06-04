# dashboard/app.py
# This is the main entry point for your multi-page application.

import streamlit as st
import os
import sys

# --- Dynamically adjust Python's import path ---
current_file_path = os.path.abspath(__file__)
current_directory = os.path.dirname(current_file_path)
project_root = os.path.dirname(current_directory)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Page Configuration (This should be the first Streamlit command) ---
st.set_page_config(
    page_title="Sales & Inventory Hub", # General title for the whole app
    page_icon="�",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://www.example.com/help', # Replace with your help URL
        'Report a bug': "https://www.example.com/bug", # Replace with your bug report URL
        'About': "# Sales & Inventory Dashboard"
    }
)

# --- Sidebar Content (Visible on all pages) ---
st.sidebar.success("Select a dashboard page from the list above.") # This message might be redundant with the main page text
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.toast("Data has been refreshed successfully!", icon="✅")
    # Optional: Add a small delay and then rerun the current page to reflect changes immediately
    # import time
    # time.sleep(0.5)
    # st.rerun() # Use st.rerun() for newer Streamlit versions

# --- Main Welcome Page Content for app.py ---
# Using the text you provided:
st.markdown("<h1 style='text-align: center; color: white;'>Sales & Inventory Hub 📈</h1>", unsafe_allow_html=True) # Main Title
st.markdown("---") # Horizontal line

st.markdown("""
    <div style='text-align: center; font-size: 1.1em; color: white;'>
    Please use the navigation panel on the left to select a specific dashboard.
    <br><br>
    <strong>Available Dashboards:</strong>
    <ul style='list-style-position: inside; padding-left: 0; text-align: center;'>
        <li style='margin: 5px 0;'>Sales Overview</li>
        <li style='margin: 5px 0;'>Inventory Analysis</li>
        <li style='margin: 5px 0;'>Customer Insights</li>
        <li style='margin: 5px 0;'>Sales Forecast</li>
        <li style='margin: 5px 0;'>Order Lookup</li>
    </ul>
    <br>
    Each dashboard provides detailed insights and visualizations for its respective area.
    <br>
    Remember to use the 'Refresh Data' button in the sidebar if you have updated the source Google Sheet.
    </div>
""", unsafe_allow_html=True)

# Streamlit automatically creates the page navigation in the sidebar
# based on the .py files in the 'pages' subdirectory.