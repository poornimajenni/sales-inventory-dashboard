# pages/01_Sales_Overview.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import sys
from datetime import date, timedelta

# --- Dynamically adjust Python's import path ---
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scripts.data_loader import load_data_from_gsheet
from scripts.data_analysis import clean_data


# --- INR Formatting Function (Updated to round to whole numbers) ---
def format_as_inr(num_val):
    if pd.isna(num_val) or num_val is None:
        return "₹ -"
    try:
        num_val_rounded = round(float(num_val))
    except (ValueError, TypeError):
        return str(num_val)

    prefix = '₹ '
    num_to_format = abs(int(num_val_rounded))

    if num_val_rounded < 0:
        prefix = '- ₹ '

    s_int = str(num_to_format)

    if len(s_int) <= 3:
        formatted_integer = s_int
    else:
        last_three = s_int[-3:]
        other_digits = s_int[:-3]
        temp_other_digits = ""
        for i in range(len(other_digits)):
            temp_other_digits += other_digits[i]
            if (len(other_digits) - 1 - i) % 2 == 0 and i != len(other_digits) - 1:
                temp_other_digits += ","
        formatted_integer = temp_other_digits + ',' + last_three

    return prefix + formatted_integer


# --- Caching Data ---
@st.cache_data
def get_sales_overview_data():
    raw_df = load_data_from_gsheet()
    if raw_df.empty:
        return pd.DataFrame()
    cleaned_df = clean_data(raw_df)

    if 'Date' in cleaned_df.columns:
        if not pd.api.types.is_datetime64_any_dtype(cleaned_df['Date']):
            cleaned_df['Date'] = pd.to_datetime(cleaned_df['Date'], errors='coerce')
            cleaned_df.dropna(subset=['Date'], inplace=True)

    numeric_cols = ['Final Sale', 'Total Cost', 'Revenue Lost Due to Discount',
                    'Profit per Unit (After Discount)', 'Quantity Sold',
                    'Profit Margin % (After Discount)', 'Discount %', 'Unit Price']
    for col in numeric_cols:
        if col in cleaned_df.columns:
            cleaned_df[col] = pd.to_numeric(cleaned_df[col], errors='coerce')

    if 'Invoice ID' in cleaned_df.columns:
        cleaned_df['Invoice ID'] = cleaned_df['Invoice ID'].astype(str)

    if all(col in cleaned_df.columns for col in ['Profit per Unit (After Discount)', 'Quantity Sold']):
        cleaned_df['Calculated Net Profit per Transaction'] = cleaned_df['Profit per Unit (After Discount)'].fillna(0) * \
                                                              cleaned_df['Quantity Sold'].fillna(0)
    elif all(col in cleaned_df.columns for col in ['Final Sale', 'Total Cost']):
        cleaned_df['Calculated Net Profit per Transaction'] = cleaned_df['Final Sale'].fillna(0) - cleaned_df[
            'Total Cost'].fillna(0)
        if 'Revenue Lost Due to Discount' in cleaned_df.columns:
            cleaned_df['Calculated Net Profit per Transaction'] -= cleaned_df['Revenue Lost Due to Discount'].fillna(0)
    return cleaned_df


# --- Helper function for KPI boxes ---
def display_kpi(label, raw_value, color="#20c997"):
    if label == "Avg. Order Value":
        if pd.isna(raw_value) or raw_value is None:
            formatted_value = "-"
        else:
            try:
                # No Rupee symbol, standard comma, 2 decimals for AOV
                formatted_value = f"{float(raw_value):,.2f}"
            except (ValueError, TypeError):
                formatted_value = str(raw_value)
    elif label == "Total Units Sold":
        if pd.isna(raw_value) or raw_value is None:
            formatted_value = "-"
        else:
            try:
                formatted_value = f"{int(raw_value):,}"  # Integer with standard comma
            except (ValueError, TypeError):
                formatted_value = str(raw_value)
    elif "Margin" in label or "%" in label:
        if pd.isna(raw_value) or raw_value is None:
            formatted_value = "- %"
        else:
            try:
                formatted_value = f"{float(raw_value):.2f}%"
            except (ValueError, TypeError):
                formatted_value = str(raw_value)
    elif isinstance(raw_value, (int, float)):
        formatted_value = format_as_inr(raw_value)
    else:
        formatted_value = str(raw_value)

    kpi_box_style_base = "padding:20px;border-radius:10px;text-align:center;color:white;box-shadow:2px 2px 8px #0000004D;margin-bottom:15px;"
    html_kpi = f"<div style='{kpi_box_style_base} background-color:{color};'><h3 style='margin-bottom:5px;font-size:1.1em;'>{label}</h3><p style='font-size:2.2em;font-weight:bold;margin-top:0;'>{formatted_value}</p></div>"
    st.markdown(html_kpi, unsafe_allow_html=True)


# --- Main Page Application Logic ---
def display_sales_overview():
    st.markdown("<h1 style='text-align: center; color: white;'>📈 Advanced Sales Overview</h1>",
                unsafe_allow_html=True)

    df_full = get_sales_overview_data()

    if df_full.empty:
        st.warning("Sales overview data could not be loaded. Please check the data source or refresh.")
        st.stop()

    # --- Initialize Filter States ---
    min_data_date = df_full['Date'].min().date() if 'Date' in df_full.columns and not df_full[
        'Date'].empty else date.today() - timedelta(days=30)
    max_data_date = df_full['Date'].max().date() if 'Date' in df_full.columns and not df_full[
        'Date'].empty else date.today()
    default_date_range = (min_data_date, max_data_date)

    filter_keys_defaults = {
        "so_date_range": default_date_range,
        "so_weekend_weekday": [], "so_product": [], "so_category": [],
        "so_customer": [], "so_supplier": []
    }
    for key, def_val in filter_keys_defaults.items():
        if key not in st.session_state: st.session_state[key] = def_val

    # --- Filter UI Elements (Inside an Expander) ---
    with st.expander("⚙️ Dashboard Filters", expanded=False):
        filter_cols_r1 = st.columns([2, 1, 1])
        with filter_cols_r1[0]:
            st.session_state.so_date_range = st.date_input(
                "Date Range",
                value=st.session_state.so_date_range,
                min_value=min_data_date,
                max_value=max_data_date,
                key="main_date_filter"
            )
        with filter_cols_r1[1]:
            weekend_weekday_options = sorted(
                df_full['Weekend/Weekday'].dropna().unique()) if 'Weekend/Weekday' in df_full.columns else []
            if weekend_weekday_options:
                st.session_state.so_weekend_weekday = st.multiselect("Weekend/Weekday", weekend_weekday_options,
                                                                     default=st.session_state.so_weekend_weekday,
                                                                     key="main_ww_filter")
        with filter_cols_r1[2]:
            product_options = sorted(df_full['Product'].dropna().unique()) if 'Product' in df_full.columns else []
            if product_options:
                st.session_state.so_product = st.multiselect("Product(s)", product_options,
                                                             default=st.session_state.so_product,
                                                             key="main_prod_filter")

        filter_cols_r2 = st.columns(3)
        with filter_cols_r2[0]:
            category_options = sorted(df_full['Category'].dropna().unique()) if 'Category' in df_full.columns else []
            if category_options:
                st.session_state.so_category = st.multiselect("Category(s)", category_options,
                                                              default=st.session_state.so_category,
                                                              key="main_cat_filter")
        with filter_cols_r2[1]:
            customer_options = sorted(
                df_full['Customer Name'].dropna().unique()) if 'Customer Name' in df_full.columns else []
            if customer_options:
                st.session_state.so_customer = st.multiselect("Customer(s)", customer_options,
                                                              default=st.session_state.so_customer,
                                                              key="main_cust_filter")
        with filter_cols_r2[2]:
            supplier_options = sorted(df_full['Supplier'].dropna().unique()) if 'Supplier' in df_full.columns else []
            if supplier_options:
                st.session_state.so_supplier = st.multiselect("Supplier(s)", supplier_options,
                                                              default=st.session_state.so_supplier,
                                                              key="main_supp_filter")

        st.markdown("<br>", unsafe_allow_html=True)
        btn_cols = st.columns([1, 1, 4])
        with btn_cols[0]:
            if st.button("🧹 Clear All Filters", use_container_width=True, key="expander_clear_button"):
                for key, def_val in filter_keys_defaults.items():
                    st.session_state[key] = def_val
                st.toast("Filters Cleared!", icon="🧹")
                st.rerun()
        with btn_cols[1]:
            if st.button("🔄 Refresh Data", use_container_width=True, key="expander_refresh_button"):
                st.cache_data.clear()
                for key, def_val in filter_keys_defaults.items():
                    st.session_state[key] = def_val
                st.toast("Data Refreshed & Filters Cleared!", icon="✅")
                st.rerun()

    st.markdown("---")

    # --- Apply Filters ---
    df_filtered = df_full.copy()
    start_date, end_date = st.session_state.so_date_range
    if 'Date' in df_filtered.columns:
        df_filtered['Date'] = pd.to_datetime(df_filtered['Date'])
        df_filtered = df_filtered[
            (df_filtered['Date'] >= pd.to_datetime(start_date)) & (df_filtered['Date'] <= pd.to_datetime(end_date))]

    if st.session_state.so_weekend_weekday and 'Weekend/Weekday' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Weekend/Weekday'].isin(st.session_state.so_weekend_weekday)]
    if st.session_state.so_product and 'Product' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Product'].isin(st.session_state.so_product)]
    if st.session_state.so_category and 'Category' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Category'].isin(st.session_state.so_category)]
    if st.session_state.so_customer and 'Customer Name' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Customer Name'].isin(st.session_state.so_customer)]
    if st.session_state.so_supplier and 'Supplier' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Supplier'].isin(st.session_state.so_supplier)]

    if df_filtered.empty:
        st.warning("No data matches the current filter criteria.")
        st.stop()

    st.markdown("""
    <style>
    div.styled-chart-container-trigger + div[data-testid="stVerticalBlock"] {
        background-color: #262730 !important; padding: 20px !important; 
        border-radius: 10px !important; 
        box-shadow: 3px 3px 10px rgba(0, 0, 0, 0.4) !important; 
        margin-bottom: 25px !important;
    }
    div.styled-chart-container-trigger + div[data-testid="stVerticalBlock"] h5 {
        color: white !important; text-align: center !important; 
        margin-top: -10px !important; margin-bottom: 10px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    plotly_layout_updates = dict(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white',
        title_text="",
        title_x=0.5, title_xanchor='center', title_font_size=18,
        xaxis=dict(showgrid=False), yaxis=dict(showgrid=False)
    )
    plotly_layout_no_title_margin = {**plotly_layout_updates, "margin": dict(t=30)}

    gradient_color_scale_dark_blue = [
        '#0D47A1', '#1552A7', '#1A5CAC', '#1F66B2', '#2470B8',
        '#297ABE', '#2E84C4', '#338ECA', '#3898D0', '#3DA2D6'
    ]

    # --------------------------------------------------------------------------
    # Section 1: KPIs
    # --------------------------------------------------------------------------
    kpi_cols_r1 = st.columns(4)

    total_revenue = df_filtered['Final Sale'].sum() if 'Final Sale' in df_filtered.columns else 0
    net_profit = df_filtered['Calculated Net Profit per Transaction'].sum(
        skipna=True) if 'Calculated Net Profit per Transaction' in df_filtered.columns else 0
    net_profit_margin = (net_profit / total_revenue * 100) if total_revenue else 0

    avg_order_value = 0
    if 'Invoice ID' in df_filtered.columns and df_filtered['Invoice ID'].nunique() > 0 and total_revenue > 0:
        avg_order_value = total_revenue / df_filtered['Invoice ID'].nunique()

    with kpi_cols_r1[0]:
        display_kpi("Total Revenue", total_revenue, "#17A2B8")
    with kpi_cols_r1[1]:
        display_kpi("Net Profit", net_profit, "#28A745")
    with kpi_cols_r1[2]:
        display_kpi("Net Profit Margin", net_profit_margin, "#FFC107")
    with kpi_cols_r1[3]:
        display_kpi("Avg. Order Value", avg_order_value, "#6F42C1")

    kpi_cols_r2 = st.columns(3)
    total_cost = df_filtered['Total Cost'].sum() if 'Total Cost' in df_filtered.columns else 0
    total_units_sold = df_filtered['Quantity Sold'].sum(skipna=True) if 'Quantity Sold' in df_filtered.columns else 0
    total_discounts_impact = df_filtered[
        'Revenue Lost Due to Discount'].sum() if 'Revenue Lost Due to Discount' in df_filtered.columns else 0

    with kpi_cols_r2[0]:
        display_kpi("Total Cost", total_cost, "#DC3545")
    with kpi_cols_r2[1]:
        display_kpi("Total Units Sold", int(total_units_sold) if pd.notna(total_units_sold) else 0, "#20C997")
    with kpi_cols_r2[2]:
        display_kpi("Discounts Impact", total_discounts_impact, "#6610F2")

    st.markdown("---")

    # --------------------------------------------------------------------------
    # Section 2: Sales & Profitability Trends
    # --------------------------------------------------------------------------
    st.subheader("📉 Sales & Profitability Trends")
    trend_col1, trend_col2 = st.columns(2)

    with trend_col1:
        st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
        with st.container():
            st.markdown("<h5 style='text-align:center;'>Sales, Cost & Net Profit Over Time</h5>",
                        unsafe_allow_html=True)
            if 'Date' in df_filtered.columns and all(c in df_filtered.columns for c in ['Final Sale', 'Total Cost',
                                                                                        'Calculated Net Profit per Transaction']) and not df_filtered.empty:
                df_trends = df_filtered.copy();
                df_trends['Date_Month'] = df_trends['Date'].dt.to_period("M")
                daily_trends = df_trends.groupby('Date_Month').agg(Total_Revenue=('Final Sale', 'sum'),
                                                                   Total_Cost_Trend=('Total Cost', 'sum'),
                                                                   Total_Net_Profit=(
                                                                       'Calculated Net Profit per Transaction',
                                                                       'sum')).reset_index()
                daily_trends['Date'] = daily_trends['Date_Month'].dt.to_timestamp()
                daily_trends['Total_Revenue_INR'] = daily_trends['Total_Revenue'].apply(format_as_inr)
                daily_trends['Total_Cost_Trend_INR'] = daily_trends['Total_Cost_Trend'].apply(format_as_inr)
                daily_trends['Total_Net_Profit_INR'] = daily_trends['Total_Net_Profit'].apply(format_as_inr)
                if not daily_trends.empty:
                    fig_trends = go.Figure()
                    fig_trends.add_trace(
                        go.Scatter(x=daily_trends['Date'], y=daily_trends['Total_Revenue'], mode='lines+markers',
                                   name='Revenue', line=dict(color='#17A2B8'),
                                   customdata=daily_trends['Total_Revenue_INR'],
                                   hovertemplate='<b>Date</b>: %{x|%b %Y}<br><b>Revenue</b>: %{customdata}<extra></extra>'))
                    fig_trends.add_trace(
                        go.Scatter(x=daily_trends['Date'], y=daily_trends['Total_Cost_Trend'], mode='lines+markers',
                                   name='Cost', line=dict(color='#DC3545'),
                                   customdata=daily_trends['Total_Cost_Trend_INR'],
                                   hovertemplate='<b>Date</b>: %{x|%b %Y}<br><b>Cost</b>: %{customdata}<extra></extra>'))
                    fig_trends.add_trace(
                        go.Scatter(x=daily_trends['Date'], y=daily_trends['Total_Net_Profit'], mode='lines+markers',
                                   name='Net Profit', line=dict(color='#28A745'),
                                   customdata=daily_trends['Total_Net_Profit_INR'],
                                   hovertemplate='<b>Date</b>: %{x|%b %Y}<br><b>Net Profit</b>: %{customdata}<extra></extra>'))
                    fig_trends.update_layout(**plotly_layout_no_title_margin, height=400,
                                             yaxis_title="Amount (₹)")  # title_text="" is inherited
                    st.plotly_chart(fig_trends, use_container_width=True)
                else:
                    st.info("No trend data for selected filters.")
            else:
                st.info("Required columns missing for trends chart.")
    with trend_col2:
        st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
        with st.container():
            st.markdown("<h5 style='text-align:center;'>Net Profit Margin % Over Time</h5>", unsafe_allow_html=True)
            if 'Date' in df_filtered.columns and 'Profit Margin % (After Discount)' in df_filtered.columns and not df_filtered.empty:
                df_margin = df_filtered.copy();
                df_margin['Date_Month'] = df_margin['Date'].dt.to_period("M")
                df_margin['Profit Margin Display'] = df_margin['Profit Margin % (After Discount)'] * 100
                daily_margin = df_margin.groupby('Date_Month')['Profit Margin Display'].mean().reset_index()
                daily_margin['Date'] = daily_margin['Date_Month'].dt.to_timestamp()
                if not daily_margin.empty:
                    fig_margin_trend = px.line(daily_margin, x='Date', y='Profit Margin Display', markers=True,
                                               title="", labels={'Profit Margin Display': 'Avg. Net Profit Margin (%)'})
                    fig_margin_trend.update_layout(**plotly_layout_no_title_margin, height=400,
                                                   yaxis_ticksuffix="%")  # title_text="" is inherited
                    fig_margin_trend.update_traces(line_color='#FFC107',
                                                   hovertemplate='<b>Date</b>: %{x|%b %Y}<br><b>Avg. Margin</b>: %{y:.2f}%<extra></extra>')
                    st.plotly_chart(fig_margin_trend, use_container_width=True)
                else:
                    st.info("No margin trend data for selected filters.")
            else:
                st.info("Required columns missing for margin trend.")
    st.markdown("---")

    st.subheader("📦 Product Insights")
    prod_col1, prod_col2 = st.columns(2)
    with prod_col1:
        st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
        with st.container():
            st.markdown("<h5 style='text-align:center;'>Top 10 Products by Net Profit</h5>", unsafe_allow_html=True)
            if 'Product' in df_filtered.columns and 'Calculated Net Profit per Transaction' in df_filtered.columns and not df_filtered.empty:
                product_profit_df = df_filtered.groupby('Product')[
                    'Calculated Net Profit per Transaction'].sum().nlargest(10).sort_values(
                    ascending=True).reset_index()
                product_profit_df['Net Profit INR'] = product_profit_df['Calculated Net Profit per Transaction'].apply(
                    format_as_inr)
                if not product_profit_df.empty:
                    fig_prod_profit = px.bar(product_profit_df, y='Product', x='Calculated Net Profit per Transaction',
                                             orientation='h', title="", color='Calculated Net Profit per Transaction',
                                             color_continuous_scale=gradient_color_scale_dark_blue,
                                             custom_data=['Net Profit INR'])
                    fig_prod_profit.update_layout(**plotly_layout_no_title_margin, height=400,
                                                  coloraxis_showscale=False,
                                                  xaxis_title="Net Profit (₹)")  # title_text="" is inherited
                    fig_prod_profit.update_traces(
                        hovertemplate='<b>Product</b>: %{y}<br><b>Net Profit</b>: %{customdata[0]}<extra></extra>')
                    st.plotly_chart(fig_prod_profit, use_container_width=True)
                else:
                    st.info("No top products data for selected filters.")
            else:
                st.info("Required columns missing for top products chart.")
    with prod_col2:
        st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
        with st.container():
            st.markdown("<h5 style='text-align:center;'>Sales by Product Category</h5>", unsafe_allow_html=True)
            if 'Category' in df_filtered.columns and 'Final Sale' in df_filtered.columns and not df_filtered.empty:
                category_sales_df = df_filtered.groupby('Category')['Final Sale'].sum().sort_values(
                    ascending=False).reset_index()
                category_sales_df['Final Sale INR'] = category_sales_df['Final Sale'].apply(format_as_inr)
                if not category_sales_df.empty:
                    fig_cat_sales = px.bar(category_sales_df, x='Category', y='Final Sale', title="", color='Category',
                                           color_discrete_sequence=px.colors.qualitative.Pastel,
                                           custom_data=['Final Sale INR'])
                    fig_cat_sales.update_layout(**plotly_layout_no_title_margin, height=400, showlegend=False,
                                                yaxis_title="Total Revenue (₹)")  # title_text="" is inherited
                    fig_cat_sales.update_traces(
                        hovertemplate='<b>Category</b>: %{x}<br><b>Revenue</b>: %{customdata[0]}<extra></extra>')
                    st.plotly_chart(fig_cat_sales, use_container_width=True)
                else:
                    st.info("No category sales data for selected filters.")
            else:
                st.info("Required columns missing for category sales chart.")
    st.markdown("---")
    prod_col3, prod_col4 = st.columns(2)
    with prod_col3:
        st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
        with st.container():
            st.markdown("<h5 style='text-align:center;'>Net Profit by Product Category</h5>", unsafe_allow_html=True)
            if 'Category' in df_filtered.columns and 'Calculated Net Profit per Transaction' in df_filtered.columns and not df_filtered.empty:
                category_profit_df = df_filtered.groupby('Category')[
                    'Calculated Net Profit per Transaction'].sum().sort_values(ascending=False).reset_index()
                category_profit_df['Net Profit INR'] = category_profit_df[
                    'Calculated Net Profit per Transaction'].apply(format_as_inr)
                if not category_profit_df.empty:
                    fig_cat_profit = px.bar(category_profit_df, x='Category', y='Calculated Net Profit per Transaction',
                                            color='Category', color_discrete_sequence=px.colors.qualitative.Bold,
                                            custom_data=['Net Profit INR'], title="")
                    fig_cat_profit.update_layout(**plotly_layout_no_title_margin, height=400, showlegend=False,
                                                 yaxis_title="Total Net Profit (₹)")  # title_text="" is inherited
                    fig_cat_profit.update_traces(
                        hovertemplate='<b>Category</b>: %{x}<br><b>Net Profit</b>: %{customdata[0]}<extra></extra>')
                    st.plotly_chart(fig_cat_profit, use_container_width=True)
                else:
                    st.info("No category profit data for selected filters.")
            else:
                st.info("Required columns missing for category profit chart.")
    with prod_col4:
        st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
        with st.container():
            st.markdown("<h5 style='text-align:center;'>Discount % vs. Profit Margin % (Products)</h5>",
                        unsafe_allow_html=True)
            if all(c in df_filtered.columns for c in ['Product', 'Discount %', 'Profit Margin % (After Discount)',
                                                      'Final Sale']) and not df_filtered.empty:
                product_analysis = df_filtered.groupby('Product').agg(Avg_Discount_Percent=('Discount %', 'mean'),
                                                                      Avg_Profit_Margin_Percent=(
                                                                          'Profit Margin % (After Discount)', 'mean'),
                                                                      Total_Sales=('Final Sale',
                                                                                   'sum')).dropna().reset_index()
                product_analysis['Avg_Discount_Percent_Display'] = product_analysis['Avg_Discount_Percent'] * 100
                product_analysis['Avg_Profit_Margin_Percent_Display'] = product_analysis[
                                                                            'Avg_Profit_Margin_Percent'] * 100
                product_analysis['Total_Sales_INR'] = product_analysis['Total_Sales'].apply(format_as_inr)
                if not product_analysis.empty:
                    fig_scatter_profit = px.scatter(product_analysis, x='Avg_Discount_Percent_Display',
                                                    y='Avg_Profit_Margin_Percent_Display', title="", size='Total_Sales',
                                                    color='Product', hover_name='Product',
                                                    custom_data=['Total_Sales_INR'],
                                                    labels={'Avg_Discount_Percent_Display': 'Average Discount (%)',
                                                            'Avg_Profit_Margin_Percent_Display': 'Average Profit Margin (%)'})
                    fig_scatter_profit.update_layout(**plotly_layout_no_title_margin, height=450, showlegend=True,
                                                     legend_title_text='Product')  # title_text="" is inherited
                    fig_scatter_profit.update_traces(
                        hovertemplate='<b>Product</b>: %{hovertext}<br><b>Avg. Discount</b>: %{x:.2f}%<br><b>Avg. Profit Margin</b>: %{y:.2f}%<br><b>Total Sales</b>: %{customdata[0]}<extra></extra>')
                    st.plotly_chart(fig_scatter_profit, use_container_width=True)
                else:
                    st.info("No data for discount vs. profit margin scatter plot.")
            else:
                st.info("Required columns missing for scatter plot.")
    st.markdown("---")

    st.subheader("🌍 Regional Sales Performance")
    region_col1, region_col2 = st.columns(2)
    with region_col1:
        st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
        with st.container():
            st.markdown("<h5 style='text-align:center;'>Net Profit by Region</h5>", unsafe_allow_html=True)
            if 'Region' in df_filtered.columns and 'Calculated Net Profit per Transaction' in df_filtered.columns and not df_filtered.empty:
                region_profit_df = df_filtered.groupby('Region')[
                    'Calculated Net Profit per Transaction'].sum().sort_values(ascending=False).reset_index()
                region_profit_df['Net Profit INR'] = region_profit_df['Calculated Net Profit per Transaction'].apply(
                    format_as_inr)
                if not region_profit_df.empty:
                    fig_reg_profit = px.bar(region_profit_df, x='Region', y='Calculated Net Profit per Transaction',
                                            title="", color='Region',
                                            color_discrete_sequence=px.colors.qualitative.Set2,
                                            custom_data=['Net Profit INR'])
                    fig_reg_profit.update_layout(**plotly_layout_no_title_margin, height=400, showlegend=False,
                                                 yaxis_title="Total Net Profit (₹)")  # title_text="" is inherited
                    fig_reg_profit.update_traces(
                        hovertemplate='<b>Region</b>: %{x}<br><b>Net Profit</b>: %{customdata[0]}<extra></extra>')
                    st.plotly_chart(fig_reg_profit, use_container_width=True)
                else:
                    st.info("No regional profit data for selected filters.")
            else:
                st.info("Required columns missing for regional profit chart.")
    with region_col2:
        st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
        with st.container():
            st.markdown("<h5 style='text-align:center;'>Total Revenue by Region</h5>", unsafe_allow_html=True)
            if 'Region' in df_filtered.columns and 'Final Sale' in df_filtered.columns and not df_filtered.empty:
                region_sales_df = df_filtered.groupby('Region')['Final Sale'].sum().sort_values(
                    ascending=False).reset_index()
                region_sales_df['Final Sale INR'] = region_sales_df['Final Sale'].apply(format_as_inr)
                if not region_sales_df.empty:
                    fig_reg_sales = px.bar(region_sales_df, x='Region', y='Final Sale', title="", color='Region',
                                           color_discrete_sequence=px.colors.qualitative.Vivid,
                                           custom_data=['Final Sale INR'])
                    fig_reg_sales.update_layout(**plotly_layout_no_title_margin, height=400, showlegend=False,
                                                yaxis_title="Total Revenue (₹)")  # title_text="" is inherited
                    fig_reg_sales.update_traces(
                        hovertemplate='<b>Region</b>: %{x}<br><b>Revenue</b>: %{customdata[0]}<extra></extra>')
                    st.plotly_chart(fig_reg_sales, use_container_width=True)
                else:
                    st.info("No regional sales data for selected filters.")
            else:
                st.info("Required columns missing for regional sales chart.")
    st.markdown("---")

    st.subheader("💸 Discount Analysis")
    discount_col1, discount_col2 = st.columns([1, 2])
    with discount_col1:
        if 'Revenue Lost Due to Discount' in df_filtered.columns:
            total_revenue_lost = df_filtered['Revenue Lost Due to Discount'].sum()
            display_kpi("Revenue Lost to Discount", total_revenue_lost, "#E07A5F")
        else:
            st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
            with st.container():
                st.info("Column 'Revenue Lost Due to Discount' missing for KPI.")
    with discount_col2:
        st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
        with st.container():
            st.markdown("<h5 style='text-align:center;'>Revenue Lost to Discount by Category</h5>",
                        unsafe_allow_html=True)
            if 'Category' in df_filtered.columns and 'Revenue Lost Due to Discount' in df_filtered.columns and not df_filtered.empty:
                discount_by_cat_df = df_filtered.groupby('Category')['Revenue Lost Due to Discount'].sum().sort_values(
                    ascending=False).reset_index()
                discount_by_cat_df['Revenue Lost INR'] = discount_by_cat_df['Revenue Lost Due to Discount'].apply(
                    format_as_inr)
                if not discount_by_cat_df.empty:
                    fig_disc_cat = px.bar(discount_by_cat_df, x='Category', y='Revenue Lost Due to Discount', title="",
                                          color='Category', color_discrete_sequence=px.colors.qualitative.Antique,
                                          custom_data=['Revenue Lost INR'])
                    fig_disc_cat.update_layout(**plotly_layout_no_title_margin, height=400, showlegend=False,
                                               yaxis_title="Revenue Lost (₹)")  # title_text="" is inherited
                    fig_disc_cat.update_traces(
                        hovertemplate='<b>Category</b>: %{x}<br><b>Revenue Lost</b>: %{customdata[0]}<extra></extra>')
                    st.plotly_chart(fig_disc_cat, use_container_width=True)
                else:
                    st.info("No discount by category data for selected filters.")
            else:
                st.info("Required columns missing for discount by category chart.")
    st.markdown("---")

    with st.expander("View Filtered Sales & Inventory Data Sample"):
        if not df_filtered.empty:
            df_display_sample = df_filtered.sample(min(100, len(df_filtered)))
            monetary_columns_in_df = [
                'Final Sale', 'Total Cost', 'Revenue Lost Due to Discount',
                'Profit per Unit (After Discount)', 'Unit Price',
                'Calculated Net Profit per Transaction',
                'Stock Value (Selling Price)', 'Stock Value Cost'
            ]
            cols_to_format_inr = {col: format_as_inr for col in monetary_columns_in_df if
                                  col in df_display_sample.columns}
            style_dict = cols_to_format_inr.copy()
            if 'Quantity Sold' in df_display_sample.columns: style_dict['Quantity Sold'] = "{:.0f}"
            if 'Discount %' in df_display_sample.columns: style_dict['Discount %'] = "{:.2%}"
            if 'Profit Margin % (After Discount)' in df_display_sample.columns: style_dict[
                'Profit Margin % (After Discount)'] = "{:.2%}"
            st.dataframe(df_display_sample.style.format(style_dict, na_rep='-'))
        else:
            st.write("No data to display in the sample table for the current filters.")


if __name__ == "__main__":
    display_sales_overview()