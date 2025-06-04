# pages/04_Order_Lookup.py

import streamlit as st
import pandas as pd
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


# --- INR Formatting Function (copied from other pages for consistency) ---
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
def get_order_lookup_data():
    """
    Loads and cleans data, ensuring all necessary columns for order lookup are present.
    """
    raw_df = load_data_from_gsheet()
    if raw_df.empty:
        return pd.DataFrame()

    cleaned_df = clean_data(raw_df)

    if 'Date' in cleaned_df.columns:
        if not pd.api.types.is_datetime64_any_dtype(cleaned_df['Date']):
            cleaned_df['Date'] = pd.to_datetime(cleaned_df['Date'], errors='coerce')

    if 'Invoice ID' in cleaned_df.columns:
        cleaned_df['Invoice ID'] = cleaned_df['Invoice ID'].astype(str).fillna('N/A')
        cleaned_df['Invoice ID'] = cleaned_df['Invoice ID'].replace(['nan', 'None', 'NaN'], 'N/A')

    numeric_cols = ['Quantity Sold', 'Unit Price', 'Total Sale', 'Total Cost',
                    'Profit per Unit', 'Discount %', 'Final Sale',
                    'Profit per Unit (After Discount)']
    for col in numeric_cols:
        if col in cleaned_df.columns:
            cleaned_df[col] = pd.to_numeric(cleaned_df[col], errors='coerce')

    categorical_cols = ['Product', 'Category', 'Customer Name', 'Payment Method',
                        'Region', 'Supplier', 'Order Status']
    for col in categorical_cols:
        if col in cleaned_df.columns:
            cleaned_df[col] = cleaned_df[col].astype(str).fillna('N/A')
            cleaned_df[col] = cleaned_df[col].replace(['nan', 'None', 'NaN'], 'N/A')

    return cleaned_df


# --- Main Page Application Logic ---
def display_order_lookup():
    st.markdown("<h1 style='text-align: center; color: white;'>🔍 Order Lookup</h1>",
                unsafe_allow_html=True)
    st.markdown("---")

    df_orders_full = get_order_lookup_data()

    if df_orders_full.empty:
        st.error("Order data could not be loaded. Please check the data source or refresh.")
        st.stop()

    # --- Order Lookup Input ---
    if 'search_invoice_id' not in st.session_state:
        st.session_state.search_invoice_id = ""

    invoice_id_to_search = st.text_input(
        "Enter Invoice ID:",
        value=st.session_state.search_invoice_id,
        key="order_lookup_text_input"
    )

    lookup_button = st.button("Look Up Order", key="order_lookup_button")
    st.markdown("---")

    if lookup_button and invoice_id_to_search:
        st.session_state.search_invoice_id = invoice_id_to_search

        if 'Invoice ID' not in df_orders_full.columns:
            st.error("'Invoice ID' column not found in the dataset.")
            st.stop()

        # Corrected comparison logic
        order_details_df = df_orders_full[
            df_orders_full['Invoice ID'].str.strip().str.lower() == invoice_id_to_search.strip().lower()]

        if not order_details_df.empty:
            st.success(f"Found Order: {invoice_id_to_search}")

            st.subheader("📋 Order Summary")
            order_summary = {}
            first_item = order_details_df.iloc[0]

            order_summary["Invoice ID"] = invoice_id_to_search  # Use the searched ID for consistency
            if 'Date' in first_item and pd.notna(first_item['Date']):
                order_summary["Order Date"] = pd.to_datetime(first_item['Date']).strftime('%Y-%m-%d')
            if 'Customer Name' in first_item:
                order_summary["Customer Name"] = first_item['Customer Name']
            if 'Order Status' in first_item:
                order_summary["Order Status"] = first_item['Order Status']

            total_order_value = order_details_df['Final Sale'].sum() if 'Final Sale' in order_details_df.columns else 0
            total_items_in_order = order_details_df[
                'Quantity Sold'].sum() if 'Quantity Sold' in order_details_df.columns else 0

            summary_cols = st.columns(2)
            with summary_cols[0]:
                for key, value in order_summary.items():
                    st.write(f"**{key}:** {value}")
            with summary_cols[1]:
                st.write(f"**Total Order Value:** {format_as_inr(total_order_value)}")
                st.write(
                    f"**Total Items in Order:** {int(total_items_in_order) if pd.notna(total_items_in_order) else 'N/A'}")
                if 'Payment Method' in first_item:
                    st.write(f"**Payment Method:** {first_item['Payment Method']}")
                if 'Region' in first_item:
                    st.write(f"**Region:** {first_item['Region']}")

            st.subheader("🛍️ Product Details in this Order")
            product_display_cols = ['Product', 'Category', 'Quantity Sold', 'Unit Price', 'Discount %', 'Final Sale']
            if 'Profit per Unit (After Discount)' in order_details_df.columns:
                product_display_cols.append('Profit per Unit (After Discount)')
            if 'Supplier' in order_details_df.columns:
                product_display_cols.append('Supplier')

            existing_product_cols = [col for col in product_display_cols if col in order_details_df.columns]

            if existing_product_cols:
                formatters = {}
                money_cols = ['Unit Price', 'Final Sale', 'Profit per Unit (After Discount)']
                for m_col in money_cols:
                    if m_col in order_details_df.columns: formatters[m_col] = format_as_inr
                if 'Quantity Sold' in order_details_df.columns: formatters['Quantity Sold'] = "{:.0f}"
                if 'Discount %' in order_details_df.columns: formatters['Discount %'] = "{:.2%}"

                st.dataframe(order_details_df[existing_product_cols].style.format(formatters, na_rep='-'),
                             use_container_width=True)
            else:
                st.info("No specific product detail columns found to display for this order.")

        else:
            st.warning(f"No order found with Invoice ID: {invoice_id_to_search}")
    elif lookup_button and not invoice_id_to_search:
        st.warning("Please enter an Invoice ID to look up.")


if __name__ == "__main__":
    display_order_lookup()