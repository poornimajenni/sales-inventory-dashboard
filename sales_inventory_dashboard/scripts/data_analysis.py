import pandas as pd

def clean_data(df):
    # 1. Remove currency symbols and commas from currency columns
    currency_cols = [
        'Total Sale', 'Total Cost', 'Final Sale', 'Stock Value (Selling Price)',
        'Stock Value Cost', 'Net Profit', 'Revenue Lost Due to Discount',
        'Cost Price', 'Effective Selling Price'
    ]
    for col in currency_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(r'[₹,]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 2. Convert percentage columns by removing '%' and converting to float
    percent_cols = [
        'Profit per unit Margin (%)',
        'Discount %',
        'Profit Margin % (After Discount)',
        'Profit %',
        'Cancellation Rate',
        'Order Fulfillment Rate',
        'Supplier Fulfillment Ratio',
        # CORRECTED: 'Revenue Lost Due to Discount' has been removed from this list.
    ]
    for col in percent_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('%', '', regex=False).str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 3. Convert remaining numeric columns
    numeric_cols = [
        'Year', 'Quantity Sold', 'Unit Price', 'Profit per Unit',
        'Profit per Unit (After Discount)', 'Stock Left', 'Days of Inventory',
        'Average Inventory', 'Inventory Turnover',
        # CORRECTED: Added the missing comma between the two columns.
        'Average Daily Sale',
        'Avg. 30 Days order'
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 4. Convert 'Date' column to a real datetime object
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        # CORRECTED: The line below has been removed. It was turning dates back into text.
        # df['Date'] = df['Date'].dt.strftime('%d/%m/%Y')

    return df