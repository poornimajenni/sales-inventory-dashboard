# dashboard/pages/03_Customer_Supplier_Insights.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import sys
from datetime import date, timedelta
from streamlit_plotly_events import plotly_events

# --- Dynamically adjust Python's import path ---
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scripts.data_loader import load_data_from_gsheet
from scripts.data_analysis import clean_data


# --- INR Formatting Function (Rounds to whole numbers) ---
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


# --- Caching Data ---
@st.cache_data
def get_cs_page_data():
    raw_df = load_data_from_gsheet()
    if raw_df.empty: return pd.DataFrame()
    cleaned_df = clean_data(raw_df)
    if 'Date' in cleaned_df.columns:
        if not pd.api.types.is_datetime64_any_dtype(cleaned_df['Date']):
            cleaned_df['Date'] = pd.to_datetime(cleaned_df['Date'], errors='coerce', dayfirst=True)
        cleaned_df.dropna(subset=['Date'], inplace=True)

    numeric_cols_cs = ['Final Sale', 'Supplier Fulfillment Ratio']
    for col in numeric_cols_cs:
        if col in cleaned_df.columns:
            cleaned_df[col] = pd.to_numeric(cleaned_df[col], errors='coerce')

    categorical_cols_cs = ['Customer Name', 'Region', 'Payment Method', 'Customer Flag', 'Weekend/Weekday', 'Product',
                           'Supplier']
    for col in categorical_cols_cs:
        if col in cleaned_df.columns:
            cleaned_df[col] = cleaned_df[col].astype(str).fillna('N/A')
            cleaned_df[col] = cleaned_df[col].replace(['nan', 'None', 'NaN'], 'N/A')

    return cleaned_df


# --- Helper function for KPI boxes ---
def display_cs_kpi(label, raw_value, unit_prefix="", unit_suffix="", color="#20c997", is_inr=False,
                   is_percentage=False):
    if pd.isna(raw_value) or raw_value is None:
        formatted_value = "-"
    elif is_inr:
        formatted_value = format_as_inr(raw_value)
    elif is_percentage or ("Rate" in label or "%" in label and isinstance(raw_value, (int, float))):
        formatted_value = f"{float(raw_value):.2f}%"
    elif isinstance(raw_value, (int, float)):
        formatted_value = f"{int(raw_value):,}"
    else:
        formatted_value = str(raw_value)

    final_display_value = unit_prefix + formatted_value
    if unit_suffix and not formatted_value.endswith(unit_suffix) and not formatted_value.endswith("%"):
        final_display_value += unit_suffix

    kpi_box_style_base = "padding:20px;border-radius:10px;text-align:center;color:white;box-shadow:2px 2px 8px #0000004D;margin-bottom:15px;"
    html_kpi = f"<div style='{kpi_box_style_base} background-color:{color};'><h3 style='margin-bottom:5px;font-size:1.1em;'>{label}</h3><p style='font-size:2.2em;font-weight:bold;margin-top:0;'>{final_display_value}</p></div>"
    st.markdown(html_kpi, unsafe_allow_html=True)


# --- Main Page Application Logic ---
def display_customer_supplier_insights():
    st.markdown("<h1 style='text-align: center; color: white;'>👥 Customer & Supplier Insights</h1>",
                unsafe_allow_html=True)

    st.markdown("""
    <style>
    div.styled-chart-container-trigger + div[data-testid="stVerticalBlock"] {
        background-color: #262730 !important; padding: 20px !important; 
        border-radius: 10px !important; box-shadow: 3px 3px 10px rgba(0, 0, 0, 0.4) !important; 
        margin-bottom: 25px !important;
    }
    div.styled-chart-container-trigger + div[data-testid="stVerticalBlock"] h5 {
        color: white !important; text-align: center !important; 
        margin-top: -10px !important; margin-bottom: 10px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    df_full_cs = get_cs_page_data()
    if df_full_cs.empty: st.warning("Customer & Supplier insights data not available."); st.stop()

    min_data_date_cs = df_full_cs['Date'].min().date() if 'Date' in df_full_cs.columns and not df_full_cs[
        'Date'].empty else date.today() - timedelta(days=30)
    max_data_date_cs = df_full_cs['Date'].max().date() if 'Date' in df_full_cs.columns and not df_full_cs[
        'Date'].empty else date.today()
    default_date_range_cs = (min_data_date_cs, max_data_date_cs)
    default_clicked_customer_val = None

    filter_keys_defaults_cs = {
        "cs_date_filter_val": default_date_range_cs,
        "cs_region_filter_val": "All",
        "cs_flag_filter_val": "All",
        "cs_day_type_filter_val": "All",
        "cs_clicked_customer_filter_val": default_clicked_customer_val
    }
    for key, def_val in filter_keys_defaults_cs.items():
        if key not in st.session_state: st.session_state[key] = def_val

    with st.expander("⚙️ Customer/Supplier Dashboard Filters", expanded=True):
        fcol1, fcol2, fcol3, fcol4 = st.columns(4)
        with fcol1:
            st.session_state.cs_date_filter_val = st.date_input("Date Range:",
                                                                value=st.session_state.cs_date_filter_val,
                                                                min_value=min_data_date_cs, max_value=max_data_date_cs,
                                                                key="cs_page_date_input_widget")
        with fcol2:
            unique_regions_options = ["All"] + sorted(
                df_full_cs["Region"].astype(str).unique()) if "Region" in df_full_cs.columns else ["All"]
            st.session_state.cs_region_filter_val = st.selectbox("Region:", unique_regions_options,
                                                                 key="cs_page_region_filter_widget",
                                                                 index=unique_regions_options.index(
                                                                     st.session_state.cs_region_filter_val) if st.session_state.cs_region_filter_val in unique_regions_options else 0)
        with fcol3:
            unique_flags_options = ["All"] + sorted(
                df_full_cs["Customer Flag"].astype(str).unique()) if "Customer Flag" in df_full_cs.columns and \
                                                                     df_full_cs["Customer Flag"].nunique() > 1 else [
                "All"]
            st.session_state.cs_flag_filter_val = st.selectbox("Customer Flag:", unique_flags_options,
                                                               key="cs_page_flag_filter_widget",
                                                               index=unique_flags_options.index(
                                                                   st.session_state.cs_flag_filter_val) if st.session_state.cs_flag_filter_val in unique_flags_options else 0)
        with fcol4:
            day_types_options = ["All"] + sorted(
                df_full_cs["Weekend/Weekday"].astype(str).unique()) if "Weekend/Weekday" in df_full_cs.columns else [
                "All"]
            st.session_state.cs_day_type_filter_val = st.selectbox("Day Type:", day_types_options,
                                                                   key="cs_page_day_type_filter_widget",
                                                                   index=day_types_options.index(
                                                                       st.session_state.cs_day_type_filter_val) if st.session_state.cs_day_type_filter_val in day_types_options else 0)

        b_col1, b_col2, _ = st.columns([1, 1, 4])
        with b_col1:
            if st.button("🧹 Clear All", key="cs_page_clear_filters_btn_exp", use_container_width=True):
                for key, def_val in filter_keys_defaults_cs.items(): st.session_state[key] = def_val
                st.toast("Filters Cleared!", icon="🧹");
                st.rerun()
        with b_col2:
            if st.button("🔄 Refresh Data", key="cs_page_refresh_data_btn_exp", use_container_width=True):
                st.cache_data.clear()
                for key, def_val in filter_keys_defaults_cs.items(): st.session_state[key] = def_val
                st.toast("Data Refreshed, Filters Reset!", icon="✅");
                st.rerun()

    if st.session_state.get(
            "cs_clicked_customer_filter_val") and st.session_state.cs_clicked_customer_filter_val != default_clicked_customer_val:
        st.info(
            f"Interactive Filter Active: Customer = {st.session_state.cs_clicked_customer_filter_val}. (Click customer bar again or use 'Clear All')")
    st.markdown("---")

    df_filtered = df_full_cs.copy()
    if 'Date' in df_filtered.columns:
        start_date, end_date = st.session_state.cs_date_filter_val
        df_filtered['Date'] = pd.to_datetime(df_filtered['Date'])
        df_filtered = df_filtered[
            (df_filtered['Date'] >= pd.to_datetime(start_date)) & (df_filtered['Date'] <= pd.to_datetime(end_date))]

    if st.session_state.cs_region_filter_val != "All" and "Region" in df_filtered.columns: df_filtered = df_filtered[
        df_filtered["Region"] == st.session_state.cs_region_filter_val]
    if st.session_state.cs_flag_filter_val != "All" and "Customer Flag" in df_filtered.columns: df_filtered = \
    df_filtered[df_filtered["Customer Flag"] == st.session_state.cs_flag_filter_val]
    if st.session_state.cs_day_type_filter_val != "All" and "Weekend/Weekday" in df_filtered.columns: df_filtered = \
    df_filtered[df_filtered["Weekend/Weekday"] == st.session_state.cs_day_type_filter_val]

    active_clicked_customer = st.session_state.get("cs_clicked_customer_filter_val")
    # Apply interactive filter AFTER other filters, so it filters the already filtered data
    # unless it's meant to show only the clicked customer from the full dataset.
    # For now, it filters on df_filtered.
    if active_clicked_customer and active_clicked_customer != default_clicked_customer_val and 'Customer Name' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["Customer Name"] == active_clicked_customer]

    if df_filtered.empty: st.warning("No data available for the selected filter combination."); st.stop()

    kpi_col1_box, kpi_col2_box, kpi_col3_box = st.columns(3)
    with kpi_col1_box:
        display_cs_kpi("Total Unique Customers",
                       df_filtered['Customer Name'].nunique() if 'Customer Name' in df_filtered else 0, color="#20c997")
    with kpi_col2_box:
        display_cs_kpi("Total Unique Suppliers", df_filtered['Supplier'].nunique() if 'Supplier' in df_filtered else 0,
                       color="#ff8c00")
    avg_sfr = df_filtered['Supplier Fulfillment Ratio'].mean() * 100 if 'Supplier Fulfillment Ratio' in df_filtered and \
                                                                        df_filtered[
                                                                            'Supplier Fulfillment Ratio'].notna().any() else 0
    with kpi_col3_box:
        display_cs_kpi("Avg. Supplier Fulfillment", avg_sfr, unit_suffix="%", color="#6f42c1", is_percentage=True)
    st.markdown("---")

    plotly_base_layout_updates = dict(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white',
                                      title_text="", title_x=0.5, title_xanchor='center', title_font_size=16,
                                      margin=dict(t=50, b=40, l=0, r=0))
    gradient_color_scale_dark_blue = ['#0D47A1', '#1552A7', '#1A5CAC', '#1F66B2', '#2470B8', '#297ABE', '#2E84C4',
                                      '#338ECA', '#3898D0', '#3DA2D6']

    st.subheader("👤 Customer Insights")
    cust_col1, cust_col2 = st.columns(2)
    with cust_col1:
        st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
        with st.container():
            st.markdown("<h5 style='text-align:center;'>Top 10 Customers by Revenue</h5>", unsafe_allow_html=True)
            if 'Customer Name' in df_filtered.columns and 'Final Sale' in df_filtered.columns and not df_filtered.empty:
                # Determine source for this chart based on whether a customer is interactively filtered
                # If a customer is clicked, this chart should ideally reflect that single customer's revenue.
                # Otherwise, it shows top 10 from the currently filtered data.
                if active_clicked_customer and active_clicked_customer != default_clicked_customer_val:
                    top_customers_data = \
                    df_filtered[df_filtered['Customer Name'] == active_clicked_customer].groupby('Customer Name')[
                        'Final Sale'].sum()
                else:
                    top_customers_data = df_filtered.groupby('Customer Name')['Final Sale'].sum().nlargest(10)

                top_customers_df = top_customers_data.sort_values(ascending=True).reset_index()
                top_customers_df.columns = ['Customer Name', 'Revenue']  # Ensure column names for px
                top_customers_df['Revenue INR'] = top_customers_df['Revenue'].apply(format_as_inr)

                if not top_customers_df.empty:
                    fig_top_cust = px.bar(top_customers_df,
                                          x='Revenue',
                                          y='Customer Name',
                                          orientation='h',
                                          title="",
                                          labels={'Revenue': 'Revenue (₹)', 'Customer Name': 'Customer Name'},
                                          text='Revenue INR'  # Use formatted INR for hover
                                          )
                    fig_top_cust.update_traces(marker_color='#1E90FF',  # Uniform blue color
                                               hovertemplate="<b>Customer:</b> %{y}<br><b>Revenue:</b> %{text}<extra></extra>")

                    fig_top_cust.update_layout(
                        **plotly_base_layout_updates,
                        xaxis_title='Revenue (₹)',
                        yaxis_title='Customer Name',
                        yaxis_categoryorder='total ascending',
                        height=400
                    )

                    clicked_data = plotly_events(fig_top_cust, click_event=True,
                                                 key="cs_customer_top_rev_click_v3")  # Unique key
                    if clicked_data:
                        clicked_name_event = clicked_data[0]['y']
                        if st.session_state.cs_clicked_customer_filter_val == clicked_name_event:
                            st.session_state.cs_clicked_customer_filter_val = default_clicked_customer_val
                        else:
                            st.session_state.cs_clicked_customer_filter_val = clicked_name_event
                        st.rerun()
                else:
                    st.info("No customer revenue data for current selection.")
            else:
                st.info("Required columns (Customer Name, Final Sale) missing.")

    with cust_col2:
        st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
        with st.container():
            st.markdown("<h5 style='text-align:center;'>Payment Method Distribution</h5>", unsafe_allow_html=True)
            if 'Payment Method' in df_filtered.columns and not df_filtered.empty:
                counts = df_filtered['Payment Method'].value_counts().reset_index();
                counts.columns = ['Payment Method', 'Transactions']
                if not counts.empty:
                    fig_payment = px.pie(counts, names='Payment Method', values='Transactions', hole=0.4, title="")
                    fig_payment.update_layout(**plotly_base_layout_updates, height=400, legend_title_font_color='white',
                                              legend_font_color='white')
                    st.plotly_chart(fig_payment, use_container_width=True)
                else:
                    st.info("No payment method data for current filters.")
            else:
                st.info("Column 'Payment Method' missing.")

    st.markdown("<br>", unsafe_allow_html=True)
    impact_region_col1, impact_region_col2 = st.columns(2)
    with impact_region_col1:
        st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
        with st.container():
            st.markdown("<h5 style='text-align:center;'>⭐ Top 10 Products by Unique Customers</h5>",
                        unsafe_allow_html=True)
            if 'Product' in df_filtered.columns and 'Customer Name' in df_filtered.columns and not df_filtered.empty:
                impact = df_filtered.groupby('Product')['Customer Name'].nunique().nlargest(10).sort_values(
                    ascending=True).reset_index(name='Unique Customer Count')
                if not impact.empty:
                    fig_impact = px.bar(impact, y='Product', x='Unique Customer Count', orientation='h', title="",
                                        color='Unique Customer Count',
                                        color_continuous_scale=gradient_color_scale_dark_blue,
                                        labels={'Unique Customer Count': 'Unique Customers', 'Product': 'Product'})
                    fig_impact.update_layout(**plotly_base_layout_updates, xaxis=dict(showgrid=False),
                                             yaxis=dict(showgrid=False, categoryorder='total ascending'), height=450,
                                             coloraxis_showscale=False)
                    st.plotly_chart(fig_impact, use_container_width=True)
                else:
                    st.info("Not enough data for Top Products by Unique Customers for current filters.")
            else:
                st.info("Required columns (Product, Customer Name) missing.")
    with impact_region_col2:
        st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
        with st.container():
            st.markdown("<h5 style='text-align:center;'>Customers & Revenue by Region</h5>", unsafe_allow_html=True)
            if 'Region' in df_filtered.columns and 'Customer Name' in df_filtered.columns and 'Final Sale' in df_filtered.columns and not df_filtered.empty:
                region_summary = df_filtered.groupby('Region').agg(Unique_Customers=('Customer Name', 'nunique'),
                                                                   Total_Revenue=('Final Sale',
                                                                                  'sum')).reset_index().sort_values(
                    by='Unique_Customers', ascending=False)
                if not region_summary.empty:
                    fig_region = go.Figure()
                    fig_region.add_trace(go.Bar(x=region_summary['Region'], y=region_summary['Unique_Customers'],
                                                name='Unique Customers', marker_color=px.colors.qualitative.Plotly[0]))
                    fig_region.add_trace(go.Scatter(x=region_summary['Region'], y=region_summary['Total_Revenue'],
                                                    name='Total Revenue (₹)', yaxis='y2', mode='lines+markers',
                                                    line=dict(color=px.colors.qualitative.Plotly[1], width=2),
                                                    marker=dict(size=7)))
                    fig_region.update_layout(**plotly_base_layout_updates,
                                             xaxis=dict(showgrid=False, tickangle=-45, title_text="Region"),
                                             yaxis=dict(title_text='No. of Unique Customers', showgrid=False,
                                                        color=px.colors.qualitative.Plotly[0]),
                                             yaxis2=dict(title_text='Total Revenue (₹)', overlaying='y', side='right',
                                                         showgrid=False, color=px.colors.qualitative.Plotly[1]),
                                             height=450,
                                             legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right",
                                                         x=1))
                    st.plotly_chart(fig_region, use_container_width=True)
                else:
                    st.info("Not enough regional data for current filters.")
            else:
                st.info("Required columns for Customers & Revenue by Region missing.")
    st.markdown("---")

    st.subheader("🚚 Supplier Insights")
    st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
    with st.container():
        st.markdown("<h5 style='text-align:center;'>Average Fulfillment Ratio by Supplier</h5>", unsafe_allow_html=True)
        if 'Supplier' in df_filtered.columns and 'Supplier Fulfillment Ratio' in df_filtered.columns and not df_filtered.empty:
            df_s_insights = df_filtered.copy();
            df_s_insights['SFR_Num'] = pd.to_numeric(df_s_insights['Supplier Fulfillment Ratio'], errors='coerce') * 100
            if df_s_insights['SFR_Num'].notna().any():
                avg_fulfill = df_s_insights.groupby('Supplier')['SFR_Num'].mean().sort_values(
                    ascending=False).reset_index().dropna(subset=['SFR_Num'])
                if not avg_fulfill.empty:
                    fig_supplier_fulfill = px.bar(avg_fulfill, x='Supplier', y='SFR_Num', title="",
                                                  labels={'SFR_Num': 'Avg. Fulfillment Ratio (%)'}, color='Supplier')
                    fig_supplier_fulfill.update_layout(**plotly_base_layout_updates,
                                                       xaxis=dict(showgrid=False, tickangle=-45),
                                                       yaxis=dict(showgrid=False, ticksuffix="%"), showlegend=False,
                                                       height=400)
                    st.plotly_chart(fig_supplier_fulfill, use_container_width=True)
                else:
                    st.info("No valid data for Supplier Fulfillment for current filters.")
            else:
                st.info("Supplier Fulfillment Ratio column contains no valid numeric data.")
        else:
            st.info("Required columns for Supplier Fulfillment chart missing.")
    st.markdown("---")

    with st.expander("View Detailed Filtered Data"):
        if not df_filtered.empty:
            st.dataframe(df_filtered.reset_index(drop=True))
        else:
            st.write("No data to display for current filters.")


if __name__ == "__main__":
    display_customer_supplier_insights()