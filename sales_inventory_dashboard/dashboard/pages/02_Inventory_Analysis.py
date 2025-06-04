import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import sys
from datetime import date, timedelta
import numpy as np  # For derive_stock_alert_flag

# --- Dynamically adjust Python's import path ---
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scripts.data_loader import load_data_from_gsheet
from scripts.data_analysis import clean_data


# --- INR Formatting Function ---
def format_as_inr(num_val):
    if pd.isna(num_val) or num_val is None:
        return "₹ -"
    try:
        num_val_rounded = round(float(num_val))
    except (ValueError, TypeError):
        return str(num_val)
    prefix = '₹ ';
    num_to_format = abs(int(num_val_rounded))
    if num_val_rounded < 0: prefix = '- ₹ '
    s_int = str(num_to_format)
    if len(s_int) <= 3:
        formatted_integer = s_int
    else:
        last_three = s_int[-3:];
        other_digits = s_int[:-3];
        temp_other_digits = ""
        for i in range(len(other_digits)):
            temp_other_digits += other_digits[i]
            if (len(other_digits) - 1 - i) % 2 == 0 and i != len(other_digits) - 1: temp_other_digits += ","
        formatted_integer = temp_other_digits + ',' + last_three
    return prefix + formatted_integer


# --- Derive Stock Alert Flag ---
def derive_stock_alert_flag(df):
    # Ensure necessary columns are numeric before calculations
    for col in ['Stock Left', 'Reorder Level', 'Max Stock Level']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        else:  # If a crucial column is missing, cannot derive flags accurately
            df['Stock Alert Flag'] = 'N/A (Missing Threshold Data)'
            return df

    conditions = []
    choices = []

    # Only proceed if all necessary columns for conditions are present
    if all(c in df.columns for c in ['Stock Left', 'Reorder Level', 'Max Stock Level']):
        conditions = [
            df['Stock Left'] <= df['Reorder Level'],
            (df['Stock Left'] > df['Reorder Level']) & (df['Stock Left'] <= df['Max Stock Level']),
            df['Stock Left'] > df['Max Stock Level']
        ]
        choices = ['Reorder', 'Optimal', 'Surplus']
        default_choice = 'Unknown'
    elif 'Stock Left' in df.columns and 'Reorder Level' in df.columns:  # Only Reorder Level available
        conditions = [df['Stock Left'] <= df['Reorder Level'], df['Stock Left'] > df['Reorder Level']]
        choices = ['Reorder', 'Sufficient']
        default_choice = 'Unknown'
    elif 'Stock Left' in df.columns:  # Only Stock Left available, cannot determine alerts
        df['Stock Alert Flag'] = 'N/A (Needs Thresholds)'
        return df
    else:  # Not enough data for any meaningful alert
        df['Stock Alert Flag'] = 'N/A (Missing Stock/Threshold Data)'
        return df

    df['Stock Alert Flag'] = np.select(conditions, choices, default=default_choice)
    df.loc[df['Stock Left'].isna(), 'Stock Alert Flag'] = 'N/A (Missing Stock Data)'
    return df


# --- Caching Data ---
@st.cache_data
def get_inventory_analysis_data():
    raw_df = load_data_from_gsheet()
    if raw_df.empty: return pd.DataFrame()
    cleaned_df = clean_data(raw_df)
    if 'Date' in cleaned_df.columns:
        if not pd.api.types.is_datetime64_any_dtype(cleaned_df['Date']):
            cleaned_df['Date'] = pd.to_datetime(cleaned_df['Date'], errors='coerce',
                                                dayfirst=True)  # Explicitly dayfirst
            cleaned_df.dropna(subset=['Date'], inplace=True)  # Drop if date conversion fails

    inventory_numeric_cols = ['Stock Left', 'Days of Inventory', 'Average Inventory', 'Stock Value (Selling Price)',
                              'Stock Value Cost', 'Inventory Turnover', 'Quantity Sold', 'Cost Price', 'Unit Price',
                              'Final Sale', 'Total Cost', 'Reorder Level', 'Max Stock Level']
    for col in inventory_numeric_cols:
        if col in cleaned_df.columns: cleaned_df[col] = pd.to_numeric(cleaned_df[col], errors='coerce')

    inventory_categorical_cols = ['Product', 'Category', 'Movement Label', 'Supplier', 'Region',
                                  'Weekend/Weekday', 'Order Status', 'Customer Name', 'Stock Alert Flag']
    for col in inventory_categorical_cols:  # Ensure Stock Alert Flag is also processed if it comes from source
        if col in cleaned_df.columns:
            cleaned_df[col] = cleaned_df[col].astype(str).fillna('N/A')
            cleaned_df[col] = cleaned_df[col].replace(['nan', 'None', 'NaN', ''], 'N/A')  # Also replace empty strings

    if 'Stock Value Cost' not in cleaned_df.columns and all(
            c in cleaned_df.columns for c in ['Cost Price', 'Stock Left']):
        cleaned_df['Stock Value Cost'] = cleaned_df['Cost Price'].fillna(0) * cleaned_df['Stock Left'].fillna(0)
    if 'Stock Value (Selling Price)' not in cleaned_df.columns and all(
            c in cleaned_df.columns for c in ['Unit Price', 'Stock Left']):
        cleaned_df['Stock Value (Selling Price)'] = cleaned_df['Unit Price'].fillna(0) * cleaned_df[
            'Stock Left'].fillna(0)
    if 'Invoice ID' in cleaned_df.columns: cleaned_df['Invoice ID'] = cleaned_df['Invoice ID'].astype(str)

    # Derive Stock Alert Flag after cleaning other columns
    if 'Stock Alert Flag' not in cleaned_df.columns or cleaned_df[
        'Stock Alert Flag'].nunique() <= 1:  # If not present or not diverse
        cleaned_df = derive_stock_alert_flag(cleaned_df)

    return cleaned_df


# --- Helper function for KPI boxes --- (Copied from previous, ensure it's suitable)
def display_inventory_kpi(label, raw_value, unit_prefix="", unit_suffix="", color="#4A4A4A", is_inr=False,
                          is_percentage=False, is_days=False):
    if pd.isna(raw_value) or raw_value is None:
        formatted_value = "-"
    elif is_inr:
        formatted_value = format_as_inr(raw_value)
    elif is_percentage or ("Rate" in label or "%" in label and isinstance(raw_value, (int, float))):
        formatted_value = f"{float(raw_value):.2f}%"
    elif is_days:
        formatted_value = f"{float(raw_value):.1f}"  # For days, 1 decimal place might be enough
    elif isinstance(raw_value, float) and ("Turnover" in label or "Ratio" in label):
        formatted_value = f"{raw_value:.2f}"
    elif isinstance(raw_value, (int, float)):
        formatted_value = f"{int(raw_value):,}"
    else:
        formatted_value = str(raw_value)
    final_display_value = unit_prefix + formatted_value
    if unit_suffix and not (
            formatted_value.endswith(unit_suffix) or formatted_value.endswith("%")): final_display_value += unit_suffix
    kpi_box_style_base = "padding:20px;border-radius:10px;text-align:center;color:white;box-shadow:2px 2px 8px #0000004D;margin-bottom:15px;"
    html_kpi = f"<div style='{kpi_box_style_base} background-color:{color};'><h3 style='margin-bottom:5px;font-size:1.1em;'>{label}</h3><p style='font-size:2.2em;font-weight:bold;margin-top:0;'>{final_display_value}</p></div>"
    st.markdown(html_kpi, unsafe_allow_html=True)


# --- Main Page Application Logic ---
def display_inventory_analysis():
    st.markdown("<h1 style='text-align: center; color: white;'>📦 Inventory Analysis Dashboard</h1>",
                unsafe_allow_html=True)

    df_inventory_full = get_inventory_analysis_data()
    if df_inventory_full.empty: st.error("Inventory data could not be loaded or is empty after cleaning."); st.stop()

    # --- Initialize Filter States ---
    min_date_val = df_inventory_full['Date'].min().date() if 'Date' in df_inventory_full.columns and not \
    df_inventory_full['Date'].empty else date.today() - timedelta(days=30)
    max_date_val = df_inventory_full['Date'].max().date() if 'Date' in df_inventory_full.columns and not \
    df_inventory_full['Date'].empty else date.today()
    default_date_range_inv = (min_date_val, max_date_val)

    filter_defaults_inv = {
        "ia_date_range": default_date_range_inv, "ia_products": [], "ia_categories": [],
        "ia_customers": [], "ia_stock_alert": []
        # Removed: "ia_weekend_weekday", "ia_region", "ia_supplier" as they were not in the last explicit list for this page.
    }
    for key, def_val in filter_defaults_inv.items():
        if key not in st.session_state: st.session_state[key] = def_val

    # --- Filters UI at the Top (inside an expander) ---
    with st.expander("⚙️ Inventory Dashboard Filters", expanded=False):
        filter_cols_r1 = st.columns(3)
        with filter_cols_r1[0]:
            st.session_state.ia_date_range = st.date_input(
                "Filter by Date Range:", value=st.session_state.ia_date_range,
                min_value=min_date_val, max_value=max_date_val, key="ia_main_date_filter"
            )
        with filter_cols_r1[1]:
            product_opts = ["All"] + sorted(
                df_inventory_full['Product'].dropna().unique()) if 'Product' in df_inventory_full.columns else ["All"]
            st.session_state.ia_products = st.multiselect("Filter by Product(s):", product_opts,
                                                          default=st.session_state.ia_products if st.session_state.ia_products else [
                                                              "All"], key="ia_product_main_filter")
        with filter_cols_r1[2]:
            category_opts = ["All"] + sorted(
                df_inventory_full['Category'].dropna().unique()) if 'Category' in df_inventory_full.columns else ["All"]
            st.session_state.ia_categories = st.multiselect("Filter by Category(s):", category_opts,
                                                            default=st.session_state.ia_categories if st.session_state.ia_categories else [
                                                                "All"], key="ia_category_main_filter")

        filter_cols_r2 = st.columns(3)
        with filter_cols_r2[0]:
            customer_opts = ["All"] + sorted(df_inventory_full[
                                                 'Customer Name'].dropna().unique()) if 'Customer Name' in df_inventory_full.columns else [
                "All"]
            st.session_state.ia_customers = st.multiselect("Filter by Customer(s):", customer_opts,
                                                           default=st.session_state.ia_customers if st.session_state.ia_customers else [
                                                               "All"], key="ia_customer_main_filter")
        with filter_cols_r2[1]:
            stock_alert_opts = ["All"] + sorted(df_inventory_full[
                                                    'Stock Alert Flag'].dropna().unique()) if 'Stock Alert Flag' in df_inventory_full.columns else [
                "All"]
            st.session_state.ia_stock_alert = st.multiselect("Filter by Stock Alert Flag(s):", stock_alert_opts,
                                                             default=st.session_state.ia_stock_alert if st.session_state.ia_stock_alert else [
                                                                 "All"], key="ia_stock_alert_main_filter")

        st.markdown("<br>", unsafe_allow_html=True)
        btn_cols_main = st.columns([1, 1, 4])
        with btn_cols_main[0]:
            if st.button("🧹 Clear All Filters", use_container_width=True, key="ia_clear_all_main_btn"):
                for key, def_val in filter_defaults_inv.items(): st.session_state[key] = def_val
                st.toast("Inventory filters cleared!", icon="🧹");
                st.rerun()
        with btn_cols_main[1]:
            if st.button("🔄 Refresh Data", use_container_width=True, key="ia_refresh_data_main_btn"):
                st.cache_data.clear();
                for key, def_val in filter_defaults_inv.items(): st.session_state[key] = def_val
                st.toast("Inventory data refreshed and filters reset!", icon="✅");
                st.rerun()
    st.markdown("---")

    # --- Apply Filters to DataFrame ---
    df_filtered = df_inventory_full.copy()

    if 'Date' in df_filtered.columns and pd.api.types.is_datetime64_any_dtype(df_filtered['Date']):
        start_date, end_date = st.session_state.ia_date_range
        df_filtered = df_filtered[
            (df_filtered['Date'] >= pd.to_datetime(start_date)) & (df_filtered['Date'] <= pd.to_datetime(end_date))]

    filter_map_inv = {'Product': 'ia_products', 'Category': 'ia_categories', 'Customer Name': 'ia_customers',
                      'Stock Alert Flag': 'ia_stock_alert'}
    for col, state_key in filter_map_inv.items():
        if col in df_filtered.columns and st.session_state.get(state_key) and "All" not in st.session_state[state_key]:
            df_filtered = df_filtered[df_filtered[col].isin(st.session_state[state_key])]

    if df_filtered.empty: st.warning("No inventory data matches the current filter criteria."); st.stop()

    # --- Page Content (KPIs and Charts) ---
    # (CSS and Plotly base layout as before)
    st.markdown(
        """<style> div.styled-chart-container-trigger + div[data-testid="stVerticalBlock"] { background-color: #262730 !important; padding: 20px !important; border-radius: 10px !important; box-shadow: 3px 3px 10px rgba(0,0,0,0.4) !important; margin-bottom: 25px !important; } div.styled-chart-container-trigger + div[data-testid="stVerticalBlock"] h5 { color: white !important; text-align: center !important; margin-top: -10px !important; margin-bottom: 10px !important; } </style>""",
        unsafe_allow_html=True)
    plotly_base_layout_updates = dict(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white',
                                      title_text="", title_x=0.5, title_xanchor='center', title_font_size=16,
                                      xaxis_showgrid=False, yaxis_showgrid=False, margin=dict(t=50, b=40, l=0, r=0))

    st.subheader("📊 Overall Inventory Snapshot")
    kpi_cols1 = st.columns(5);  # ... (KPIs as before, using df_filtered)
    with kpi_cols1[0]:
        display_inventory_kpi("In Stock",
                              df_filtered['Stock Left'].sum() if 'Stock Left' in df_filtered else 0,
                              unit_suffix=" units", color="#17A2B8")
    with kpi_cols1[1]:
        display_inventory_kpi("Stock Value",
                              df_filtered['Stock Value Cost'].sum() if 'Stock Value Cost' in df_filtered else 0,
                              is_inr=True, color="#28A745")
    with kpi_cols1[2]:
        display_inventory_kpi("Number of SKUs", df_filtered['Product'].nunique() if 'Product' in df_filtered else 0,
                              color="#FFC107")
    with kpi_cols1[3]:
        display_inventory_kpi("Avg. Days of Inventory",
                              df_filtered['Days of Inventory'].mean() if 'Days of Inventory' in df_filtered else 0,
                              is_days=True, color="#6F42C1")
    with kpi_cols1[4]:
        display_inventory_kpi("Avg. Inv. Turnover",
                              df_filtered['Inventory Turnover'].mean() if 'Inventory Turnover' in df_filtered else 0,
                              unit_suffix=" ratio", color="#E83E8C")
    st.markdown("---")

    low_stock_items_count = 0
    if 'Stock Alert Flag' in df_filtered.columns: low_stock_flags = ['Low Stock', 'Reorder']; low_stock_df_temp = \
    df_filtered[df_filtered['Stock Alert Flag'].isin(low_stock_flags)]; low_stock_items_count = low_stock_df_temp.shape[
        0]
    status_kpi_col_single = st.columns(1)[0]
    with status_kpi_col_single:
        if low_stock_items_count > 0:
            display_inventory_kpi(f"⚠️ Items Needing Attention", low_stock_items_count, unit_suffix=" item(s)",
                                  color="#DC3545")
        else:
            display_inventory_kpi("✅ Stock Levels Healthy", "No critical stock alerts", color="#28A745")
    st.markdown("---")

    # ... (Sales, Inventory & Turnover Trends section as before, using df_filtered instead of df_filtered_time_sensitive if date filter applies to whole page) ...
    # This chart uses df_filtered, which is already date-filtered if a date range is selected by the user.
    st.subheader("📈 Sales, Inventory & Turnover Trends")
    # ... (Code for fig_combo from previous version, ensuring it uses df_filtered) ...
    st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
    with st.container():
        st.markdown("<h5 style='text-align:center;'>Monthly Sales, Inventory Value, and Avg. Turnover</h5>",
                    unsafe_allow_html=True)
        if 'Date' in df_filtered.columns and all(
                c in df_filtered.columns for c in ['Final Sale', 'Stock Value Cost', 'Inventory Turnover']):
            monthly_df = df_filtered.copy();
            monthly_df.dropna(subset=['Date'], inplace=True)  # Date already datetime
            if not monthly_df.empty and len(monthly_df['Date'].unique()) > 1:
                trends_data = monthly_df.groupby(pd.Grouper(key='Date', freq='M')).agg(
                    Monthly_Sales=('Final Sale', 'sum'), Monthly_Inventory_Value_Cost=('Stock Value Cost', 'sum'),
                    Monthly_Avg_Turnover=('Inventory Turnover', 'mean')).reset_index()
                trends_data['Month_Year_Str'] = trends_data['Date'].dt.strftime('%Y-%b')
                if not trends_data.empty and len(trends_data) > 1:
                    fig_combo = go.Figure();
                    fig_combo.add_trace(
                        go.Bar(x=trends_data['Month_Year_Str'], y=trends_data['Monthly_Sales'], name='Sales',
                               marker_color='royalblue', customdata=trends_data['Monthly_Sales'].apply(format_as_inr),
                               hovertemplate='<b>Month</b>: %{x}<br><b>Sales</b>: %{customdata}<extra></extra>'));
                    fig_combo.add_trace(
                        go.Bar(x=trends_data['Month_Year_Str'], y=trends_data['Monthly_Inventory_Value_Cost'],
                               name='Inventory Value (Cost)', marker_color='lightcoral',
                               customdata=trends_data['Monthly_Inventory_Value_Cost'].apply(format_as_inr),
                               hovertemplate='<b>Month</b>: %{x}<br><b>Inventory Value</b>: %{customdata}<extra></extra>'));
                    fig_combo.add_trace(
                        go.Scatter(x=trends_data['Month_Year_Str'], y=trends_data['Monthly_Avg_Turnover'],
                                   name='Avg. Inventory Turnover', yaxis='y2', mode='lines+markers',
                                   line=dict(color='green', width=2), marker=dict(size=7),
                                   hovertemplate='<b>Month</b>: %{x}<br><b>Avg. Turnover</b>: %{y:.2f}<extra></extra>'))
                    layout_combo = plotly_base_layout_updates.copy();
                    layout_combo['yaxis'] = dict(title='Sales & Inventory Value (₹)', showgrid=False);
                    max_t = trends_data['Monthly_Avg_Turnover'].max() if trends_data[
                        'Monthly_Avg_Turnover'].notna().any() else 10
                    layout_combo['yaxis2'] = dict(title='Avg. Inventory Turnover Ratio', overlaying='y', side='right',
                                                  showgrid=False, range=[0, max(max_t * 1.2, 5)],
                                                  color=plotly_base_layout_updates.get('font_color', 'white'))
                    layout_combo.update(barmode='group',
                                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                        height=450);
                    fig_combo.update_layout(layout_combo);
                    st.plotly_chart(fig_combo, use_container_width=True)
                else:
                    st.info("Not enough distinct monthly data for trends.")
            else:
                st.info("Not enough data with valid Dates for monthly aggregation.")
        else:
            st.info("Date, Final Sale, Stock Value Cost, or Inventory Turnover column missing for trends.")
    st.markdown("---")

    # ... (Other chart sections: Detailed Stock Alerts, Inventory Valuation, Performance & Efficiency, Cancellation Analysis, Data Expander - all using df_filtered) ...
    # These sections are largely the same as the last complete version, just ensure they use df_filtered.
    # For brevity, only showing the changed low stock table section.
    st.subheader("🚨 Detailed Stock Alerts & Status")
    alert_col1, alert_col2 = st.columns(2)
    with alert_col1:
        st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
        with st.container():
            st.markdown("<h5 style='text-align:center;'>Products by Stock Alert</h5>", unsafe_allow_html=True)
            if 'Stock Alert Flag' in df_filtered.columns and not df_filtered.empty:
                alert_counts = df_filtered['Stock Alert Flag'].value_counts().reset_index();
                alert_counts.columns = ['Stock Alert Flag', 'Count']
                if not alert_counts.empty:
                    fig_alerts = px.bar(alert_counts, x='Stock Alert Flag', y='Count', color='Stock Alert Flag',
                                        title="", labels={'Count': 'Number of Products'})
                    fig_alerts.update_layout(**plotly_base_layout_updates, yaxis=dict(showgrid=False), height=350,
                                             showlegend=False)
                    st.plotly_chart(fig_alerts, use_container_width=True)
                else:
                    st.info("No stock alert data for current filters.")
            else:
                st.info("Column 'Stock Alert Flag' not available.")
    with alert_col2:
        st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
        with st.container():
            st.markdown("<h5 style='text-align:center;'>Products with Low Stock (0-9 Units)</h5>",
                        unsafe_allow_html=True)
            if 'Product' in df_filtered.columns and 'Stock Left' in df_filtered.columns and not df_filtered.empty:
                critically_low_stock_df = df_filtered.loc[
                    (df_filtered['Stock Left'] >= 0) & (df_filtered['Stock Left'] <= 9) & (
                        pd.notna(df_filtered['Stock Left']))].sort_values(by='Stock Left', ascending=True)
                if not critically_low_stock_df.empty:
                    display_cols_low_stock = ['Product'];
                    if 'Category' in critically_low_stock_df.columns: display_cols_low_stock.append('Category')
                    display_cols_low_stock.append('Stock Left')
                    if 'Supplier' in critically_low_stock_df.columns: display_cols_low_stock.append('Supplier')
                    if 'Stock Alert Flag' in critically_low_stock_df.columns: display_cols_low_stock.append(
                        'Stock Alert Flag')
                    final_display_cols_low_stock = [col for col in display_cols_low_stock if
                                                    col in critically_low_stock_df.columns]
                    st.dataframe(
                        critically_low_stock_df[final_display_cols_low_stock].style.format({'Stock Left': "{:.0f}"}),
                        use_container_width=True, height=min((len(critically_low_stock_df) + 1) * 35 + 3, 350))
                else:
                    st.info("No products found with stock levels between 0 and 9 units for current filters.")
            else:
                st.info("Required columns (Product, Stock Left) for low stock information missing.")
    st.markdown("---")

    # Cancellation Analysis Section (copied from before, using df_filtered)
    if 'Order Status' in df_filtered.columns and 'Invoice ID' in df_filtered.columns and not df_filtered.empty:
        st.subheader("🚫 Cancellation Analysis")
        CANCELLED_STATUS = "Cancelled"
        df_filtered_cancel = df_filtered.copy();
        df_filtered_cancel['Is_Cancelled'] = (df_filtered_cancel['Order Status'] == CANCELLED_STATUS)
        cancelled_orders_df = df_filtered_cancel[df_filtered_cancel['Is_Cancelled']]
        total_orders_kpi = df_filtered_cancel['Invoice ID'].nunique();
        cancelled_orders_kpi = cancelled_orders_df['Invoice ID'].nunique()
        overall_cancel_rate = (cancelled_orders_kpi / total_orders_kpi * 100) if total_orders_kpi > 0 else 0
        value_cancelled_kpi = cancelled_orders_df['Final Sale'].sum() if 'Final Sale' in cancelled_orders_df else 0
        kpi_cancel_cols = st.columns(3)
        with kpi_cancel_cols[0]:
            display_inventory_kpi("Total Cancelled Orders", cancelled_orders_kpi, color="#FF6B6B")
        with kpi_cancel_cols[1]:
            display_inventory_kpi("Cancellation Rate", overall_cancel_rate, color="#FF6B6B")
        with kpi_cancel_cols[2]:
            display_inventory_kpi("Value of Cancelled", value_cancelled_kpi, is_inr=True, color="#FF6B6B")
        st.markdown("<br>", unsafe_allow_html=True)
        cancel_chart_cols = st.columns(2)
        with cancel_chart_cols[0]:  # Cancellation Rate by Month
            st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True);
            with st.container():
                st.markdown("<h5 style='text-align:center;'>Cancellation Rate by Month</h5>", unsafe_allow_html=True)
                if 'Date' in df_filtered_cancel.columns and not df_filtered_cancel.empty:
                    monthly_c_df = df_filtered_cancel.copy();
                    monthly_c_df['Date'] = pd.to_datetime(monthly_c_df['Date'], errors='coerce');
                    monthly_c_df.dropna(subset=['Date'], inplace=True)
                    if not monthly_c_df.empty and len(monthly_c_df['Date'].unique()) > 1:
                        monthly_c_summary = monthly_c_df.groupby(pd.Grouper(key='Date', freq='M')).agg(
                            Total_Orders_Month=('Invoice ID', 'nunique'),
                            Cancelled_Orders_Month=('Is_Cancelled', 'sum')).reset_index()
                        monthly_c_summary['Cancellation_Rate_Month'] = (
                                    monthly_c_summary['Cancelled_Orders_Month'] / monthly_c_summary[
                                'Total_Orders_Month'] * 100).fillna(0)
                        monthly_c_summary['Month_Year_Str'] = monthly_c_summary['Date'].dt.strftime('%Y-%b')
                        if not monthly_c_summary.empty and len(monthly_c_summary) > 1:
                            fig_c_trend = px.line(monthly_c_summary, x='Month_Year_Str', y='Cancellation_Rate_Month',
                                                  title="", markers=True,
                                                  labels={'Cancellation_Rate_Month': 'Cancellation Rate (%)'});
                            fig_c_trend.update_layout(**plotly_base_layout_updates,
                                                      yaxis=dict(showgrid=False, ticksuffix="%"), height=350);
                            fig_c_trend.update_traces(
                                hovertemplate='<b>Month</b>: %{x}<br><b>Cancellation Rate</b>: %{y:.2f}%<extra></extra>');
                            st.plotly_chart(fig_c_trend, use_container_width=True)
                        else:
                            st.info("Not enough distinct monthly data for cancellation rate trend.")
                    else:
                        st.info("Not enough date data for monthly cancellation rate trend.")
                else:
                    st.info("Date column needed for monthly cancellation trend.")
        with cancel_chart_cols[1]:  # Top 5 Products by Cancellation Count
            st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True);
            with st.container():
                st.markdown("<h5 style='text-align:center;'>Top 5 Products by Cancellation Count</h5>",
                            unsafe_allow_html=True)
                if 'Product' in cancelled_orders_df.columns and not cancelled_orders_df.empty:
                    top_cancelled_prods = cancelled_orders_df['Product'].value_counts().nlargest(5).reset_index();
                    top_cancelled_prods.columns = ['Product', 'Cancellation Count']
                    if not top_cancelled_prods.empty:
                        fig_top_c_prod = px.bar(top_cancelled_prods, x='Product', y='Cancellation Count', title="",
                                                color='Product', labels={'Cancellation Count': 'No. of Cancellations'});
                        fig_top_c_prod.update_layout(**plotly_base_layout_updates, yaxis=dict(showgrid=False),
                                                     height=350, showlegend=False);
                        st.plotly_chart(fig_top_c_prod, use_container_width=True)
                    else:
                        st.info("No cancellation data by product for current filters.")
                else:
                    st.info("Product column or cancellation data missing in filtered data.")
        st.markdown("---")

    if not df_filtered.empty:
        st.subheader("💰 Inventory Valuation")
        val_col1, val_col2 = st.columns(2)
        # ... (Valuation charts code as before, using df_filtered) ...
        with val_col1:
            st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True);
            with st.container():
                st.markdown("<h5 style='text-align:center;'>Stock Value by Category</h5>",
                            unsafe_allow_html=True)
                if 'Category' in df_filtered.columns and 'Stock Value Cost' in df_filtered.columns:
                    cat_val_cost = df_filtered.groupby('Category')['Stock Value Cost'].sum().reset_index();
                    cat_val_cost['Value INR'] = cat_val_cost['Stock Value Cost'].apply(format_as_inr)
                    if not cat_val_cost.empty and cat_val_cost['Stock Value Cost'].sum() > 0:
                        fig_val_cost = px.pie(cat_val_cost, names='Category', values='Stock Value Cost', hole=0.4,
                                              title="", custom_data=['Value INR']);
                        fig_val_cost.update_traces(textposition='inside', textinfo='percent+label',
                                                   hovertemplate="<b>Category:</b> %{label}<br><b>Value (Cost):</b> %{customdata[0]}<br><b>Percentage:</b> %{percent}<extra></extra>");
                        fig_val_cost.update_layout(**plotly_base_layout_updates, yaxis=dict(showgrid=False), height=400,
                                                   showlegend=True);
                        st.plotly_chart(fig_val_cost, use_container_width=True)
                    else:
                        st.info("No data for stock value (cost) by category for current filters.")
                else:
                    st.info("Required columns for stock value (cost) by category missing.")
        with val_col2:
            st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True);
            with st.container():
                st.markdown("<h5 style='text-align:center;'>Top 10 Products by Stock Value</h5>",
                            unsafe_allow_html=True)
                if 'Product' in df_filtered.columns and 'Stock Value Cost' in df_filtered.columns:
                    top_value_products = df_filtered.groupby('Product')['Stock Value Cost'].sum().nlargest(
                        10).sort_values(ascending=True).reset_index();
                    top_value_products['Value INR'] = top_value_products['Stock Value Cost'].apply(format_as_inr)
                    if not top_value_products.empty:
                        fig_top_val = px.bar(top_value_products, y='Product', x='Stock Value Cost', orientation='h',
                                             title="", color='Stock Value Cost', color_continuous_scale='Viridis',
                                             text='Value INR');
                        fig_top_val.update_layout(**plotly_base_layout_updates,
                                                  yaxis=dict(showgrid=False, categoryorder='total ascending'),
                                                  height=400, coloraxis_showscale=False,
                                                  xaxis_title="Stock Value (Cost) (₹)");
                        fig_top_val.update_traces(
                            hovertemplate="<b>Product:</b> %{y}<br><b>Value (Cost):</b> %{text}<extra></extra>");
                        st.plotly_chart(fig_top_val, use_container_width=True)
                    else:
                        st.info("No data for top products by stock value for current filters.")
                else:
                    st.info("Required columns for top products by stock value missing.")
        st.markdown("---")

        st.subheader("⏱️ Inventory Performance & Efficiency")
        perf_col1, perf_col2 = st.columns(2)
        # ... (Performance charts code as before, using df_filtered) ...
        with perf_col1:
            st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True);
            with st.container():
                st.markdown("<h5 style='text-align:center;'>Avg. Inventory Turnover by Category</h5>",
                            unsafe_allow_html=True)
                if 'Category' in df_filtered.columns and 'Inventory Turnover' in df_filtered.columns:
                    cat_turnover = df_filtered.groupby('Category')['Inventory Turnover'].mean().reset_index()
                    if not cat_turnover.empty:
                        fig_turnover = px.bar(cat_turnover.sort_values('Inventory Turnover', ascending=False),
                                              x='Category', y='Inventory Turnover', color='Category', title="",
                                              labels={'Inventory Turnover': 'Average Turnover Ratio'});
                        fig_turnover.update_layout(**plotly_base_layout_updates, yaxis=dict(showgrid=False), height=400,
                                                   showlegend=False);
                        fig_turnover.update_traces(
                            hovertemplate="<b>Category:</b> %{x}<br><b>Avg. Turnover:</b> %{y:.2f}<extra></extra>");
                        st.plotly_chart(fig_turnover, use_container_width=True)
                    else:
                        st.info("No data for inventory turnover by category for current filters.")
                else:
                    st.info("Required columns for inventory turnover missing.")
        with perf_col2:
            st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True);
            with st.container():
                st.markdown("<h5 style='text-align:center;'>Avg. Days of Inventory by Category</h5>",
                            unsafe_allow_html=True)
                if 'Category' in df_filtered.columns and 'Days of Inventory' in df_filtered.columns:
                    cat_doh = df_filtered.groupby('Category')['Days of Inventory'].mean().reset_index()
                    if not cat_doh.empty:
                        fig_doh = px.bar(cat_doh.sort_values('Days of Inventory', ascending=False), x='Category',
                                         y='Days of Inventory', color='Category', title="",
                                         labels={'Days of Inventory': 'Average Days of Inventory'});
                        fig_doh.update_layout(**plotly_base_layout_updates, yaxis=dict(showgrid=False), height=400,
                                              showlegend=False);
                        fig_doh.update_traces(
                            hovertemplate="<b>Category:</b> %{x}<br><b>Avg. DOH:</b> %{y:.2f} days<extra></extra>");
                        st.plotly_chart(fig_doh, use_container_width=True)
                    else:
                        st.info("No data for days of inventory by category for current filters.")
                else:
                    st.info("Required columns for days of inventory missing.")
        st.markdown("<br>", unsafe_allow_html=True)
        if 'Movement Label' in df_filtered.columns:
            st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
            with st.container():
                st.markdown("<h5 style='text-align:center;'>Product Distribution by Movement Label</h5>",
                            unsafe_allow_html=True)
                movement_counts = df_filtered['Movement Label'].value_counts().reset_index();
                movement_counts.columns = ['Movement Label', 'Count']
                if not movement_counts.empty:
                    fig_movement = px.pie(movement_counts, names='Movement Label', values='Count', hole=0.4, title="");
                    fig_movement.update_traces(textposition='outside', textinfo='percent+label');
                    fig_movement.update_layout(**plotly_base_layout_updates, yaxis=dict(showgrid=False), height=450,
                                               showlegend=True);
                    st.plotly_chart(fig_movement, use_container_width=True)
                else:
                    st.info("No movement label data to display for current filters.")
        st.markdown("---")

        with st.expander("View Detailed Inventory Data", expanded=False):
            display_cols = ['Product', 'Category', 'Supplier', 'Stock Left', 'Cost Price', 'Stock Value Cost',
                            'Stock Value (Selling Price)', 'Days of Inventory', 'Inventory Turnover', 'Movement Label',
                            'Stock Alert Flag']
            existing_display_cols = [col for col in display_cols if col in df_filtered.columns]
            df_sample = df_filtered[existing_display_cols].copy()
            formatters = {};
            for col in ['Stock Value Cost', 'Stock Value (Selling Price)', 'Cost Price', 'Unit Price']:
                if col in df_sample.columns: formatters[col] = format_as_inr
            for col in ['Stock Left', 'Days of Inventory']:
                if col in df_sample.columns: formatters[col] = "{:.0f}"
            if 'Inventory Turnover' in df_sample.columns: formatters['Inventory Turnover'] = "{:.2f}"
            st.dataframe(df_sample.style.format(formatters, na_rep='-'))

    else:  # This else corresponds to the main df_filtered.empty() check at the top after filters
        if not ((selected_categories and 'All' not in selected_categories) or \
                (selected_stock_alert_flags and 'All' not in selected_stock_alert_flags)):
            st.info("No inventory data available to display charts based on current filters.")


if __name__ == "__main__":
    display_inventory_analysis()