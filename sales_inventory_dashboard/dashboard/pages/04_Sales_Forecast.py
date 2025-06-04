# pages/04_Sales_Forecast.py

import streamlit as st
import pandas as pd
import os
import sys
from datetime import timedelta, date
from prophet import Prophet
from prophet.plot import plot_plotly, plot_components_plotly
import plotly.graph_objects as go

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
def get_base_data_for_forecast():
    raw_df = load_data_from_gsheet()
    if raw_df.empty:
        return pd.DataFrame()

    cleaned_df = clean_data(raw_df)

    required_cols = ['Date', 'Final Sale', 'Product', 'Category']
    for col in required_cols:
        if col not in cleaned_df.columns:
            print(f"Error: Dataset must contain '{col}' column for forecasting.")
            return pd.DataFrame()

    if not pd.api.types.is_datetime64_any_dtype(cleaned_df['Date']):
        cleaned_df['Date'] = pd.to_datetime(cleaned_df['Date'], errors='coerce')
    cleaned_df.dropna(subset=['Date'], inplace=True)

    cleaned_df['Final Sale'] = pd.to_numeric(cleaned_df['Final Sale'], errors='coerce')
    cleaned_df.dropna(subset=['Final Sale'], inplace=True)

    cleaned_df['Product'] = cleaned_df['Product'].astype(str).fillna('N/A')
    cleaned_df['Category'] = cleaned_df['Category'].astype(str).fillna('N/A')

    return cleaned_df.sort_values(by='Date')


# --- Main Page Application Logic ---
def display_sales_forecast():
    st.markdown("<h1 style='text-align: center; color: white;'>🔮 Sales Forecast Analysis</h1>",
                unsafe_allow_html=True)
    st.markdown("---")

    df_base = get_base_data_for_forecast()

    if df_base.empty:
        st.warning(
            "Sales data could not be loaded or is unsuitable for forecasting. Ensure 'Date', 'Final Sale', 'Product', and 'Category' columns exist and have valid data.")
        st.stop()

    st.sidebar.header("Forecast Settings")

    product_options = ["All Products"] + sorted(df_base['Product'].unique())
    if 'forecast_product' not in st.session_state:
        st.session_state.forecast_product = "All Products"
    selected_product = st.sidebar.selectbox(
        "Select Product:", product_options,
        index=product_options.index(
            st.session_state.forecast_product) if st.session_state.forecast_product in product_options else 0,
        key="forecast_product_widget"
    )
    st.session_state.forecast_product = selected_product

    disable_category_select = (selected_product != "All Products")

    if selected_product != "All Products":
        product_s_categories = df_base[df_base['Product'] == selected_product][
            'Category'].unique() if 'Category' in df_base.columns else []
        if len(product_s_categories) >= 1:
            category_options_display = list(product_s_categories)
        else:
            category_options_display = ["N/A (Product has no category)"]
        if "forecast_category_val" not in st.session_state or st.session_state.forecast_category_val not in category_options_display:
            st.session_state.forecast_category_val = category_options_display[0]
    else:
        category_options_display = ["All Categories"] + sorted(
            df_base['Category'].unique()) if 'Category' in df_base.columns else ["All Categories"]
        if "forecast_category_val" not in st.session_state or st.session_state.forecast_category_val not in category_options_display:
            st.session_state.forecast_category_val = "All Categories"

    current_cat_idx = 0
    if st.session_state.forecast_category_val in category_options_display:
        current_cat_idx = category_options_display.index(st.session_state.forecast_category_val)

    selected_category = st.sidebar.selectbox(
        "Select Category:", options=category_options_display,
        index=current_cat_idx,
        key="forecast_category_widget",
        disabled=disable_category_select
    )
    if not disable_category_select:
        st.session_state.forecast_category_val = selected_category

    default_forecast_days = 30
    forecast_days = st.sidebar.number_input(
        "Number of days to forecast:", min_value=7, max_value=365 * 2,
        value=default_forecast_days, step=7, key="forecast_days_input"
    )

    df_to_filter = df_base.copy()
    forecast_item_name = "Overall Sales"

    if st.session_state.forecast_product != "All Products":
        df_to_filter = df_to_filter[df_to_filter['Product'] == st.session_state.forecast_product]
        forecast_item_name = f"Sales for Product: {st.session_state.forecast_product}"
    elif st.session_state.get("forecast_category_val",
                              "All Categories") != "All Categories" and not disable_category_select:
        df_to_filter = df_to_filter[df_to_filter['Category'] == st.session_state.forecast_category_val]
        forecast_item_name = f"Sales for Category: {st.session_state.forecast_category_val}"

    if df_to_filter.empty:
        prophet_df = pd.DataFrame(columns=['ds', 'y'])
    else:
        prophet_df = df_to_filter.groupby(df_to_filter['Date'].dt.date)['Final Sale'].sum().reset_index()
        prophet_df.columns = ['ds', 'y']
        prophet_df['ds'] = pd.to_datetime(prophet_df['ds'])
        prophet_df = prophet_df.sort_values(by='ds')

    if st.sidebar.button("Generate Forecast", key="generate_forecast_button"):
        if prophet_df.empty or len(prophet_df) < 20:
            st.error(
                f"Insufficient historical data for '{forecast_item_name}' to generate a reliable forecast (requires at least ~20 daily data points after filtering).")
        else:
            try:
                with st.spinner(f"Generating forecast for {forecast_item_name}... This might take a moment."):
                    model = Prophet(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False)
                    model.fit(prophet_df)
                    future = model.make_future_dataframe(periods=int(forecast_days))
                    forecast = model.predict(future)

                st.success(f"Forecast for {forecast_item_name} generated successfully!")
                st.markdown("---")

                st.subheader(f"📈 Forecast Plot: {forecast_item_name}")
                st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
                with st.container():
                    fig_forecast = plot_plotly(model, forecast)
                    fig_forecast.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white',
                        xaxis_title="Date",
                        yaxis_title="Forecasted Sales (₹)",
                        yaxis=dict(tickprefix="₹ ", showgrid=False)
                    )
                    st.plotly_chart(fig_forecast, use_container_width=True)

                st.markdown("---")
                st.subheader(f"📊 Forecast Components: {forecast_item_name}")
                st.markdown('<div class="styled-chart-container-trigger"></div>', unsafe_allow_html=True)
                with st.container():
                    fig_components = plot_components_plotly(model, forecast)
                    fig_components.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                                 font_color='white')

                    # Apply rounding and optional prefix to y-axes of component plot
                    for axis_name in fig_components.layout:
                        if axis_name.startswith('yaxis'):
                            fig_components.layout[axis_name].showgrid = False
                            fig_components.layout[axis_name].tickformat = ".0f"  # Round to whole number
                            # Add prefix only to the main trend component's y-axis (usually 'yaxis' or 'yaxis1')
                            if axis_name == 'yaxis':  # Trend component usually uses the primary y-axis
                                fig_components.layout[axis_name].tickprefix = "₹ "

                    st.plotly_chart(fig_components, use_container_width=True)

                st.markdown("---")
                with st.expander("View Forecast Data (Future Periods)"):
                    forecast_display = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(
                        int(forecast_days)).copy()
                    forecast_display['ds'] = forecast_display['ds'].dt.strftime('%Y-%m-%d')
                    for col_forecast in ['yhat', 'yhat_lower', 'yhat_upper']:
                        if col_forecast in forecast_display.columns:
                            forecast_display[col_forecast] = forecast_display[col_forecast].apply(format_as_inr)
                    st.dataframe(forecast_display)

            except Exception as e:
                st.error(f"An error occurred during forecasting for {forecast_item_name}: {e}")
                st.error("Common issues: Insufficient data, non-numeric 'y' values, or problems with date formats.")
    else:
        st.info("Select product/category, adjust forecast period in the sidebar, and click 'Generate Forecast'.")
        st.markdown(f"#### Historical Daily Sales Preview for: {forecast_item_name}")
        if not prophet_df.empty:
            df_preview = prophet_df.tail().copy()
            df_preview.rename(columns={'ds': 'Date', 'y': 'Daily Sales'}, inplace=True)

            styled_df_preview = df_preview.style.format({
                "Daily Sales": format_as_inr,
                "Date": lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else 'N/A'
            })
            st.dataframe(styled_df_preview, use_container_width=True)
        else:
            st.write(
                f"No historical data to preview for '{forecast_item_name.replace('Sales for ', '') if forecast_item_name != 'Overall Sales' else 'Overall Sales'}' based on current selections.")


if __name__ == "__main__":
    st.markdown("""
    <style>
    div.styled-chart-container-trigger + div[data-testid="stVerticalBlock"] {
        background-color: #262730 !important; padding: 20px !important; 
        border-radius: 10px !important; 
        box-shadow: 3px 3px 10px rgba(0, 0, 0, 0.4) !important; 
        margin-bottom: 25px !important;
    }
    </style>
    """, unsafe_allow_html=True)
    display_sales_forecast()