import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os # We only add the 'os' library to help find the file

# --- This is the only part that changes ---
# Instead of the full "D:/..." path, we build it automatically.
# This finds the path to your credentials file no matter where your project folder is.
CREDENTIALS_FILE = os.path.join(
    os.path.dirname(__file__), # Gets the current folder ('script')
    '..',                      # Goes up one level to the main project folder
    'credentials',             # Goes into the 'credentials' folder
    'service_account.json'     # The file name
)
# --- End of change ---

# Setup credentials and client
def load_data_from_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # We use the new CREDENTIALS_FILE variable here
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)

    # Load Google Sheet
    sheet = client.open("sales and inventory data").sheet1

    # Read all rows
    data = sheet.get_all_values()

    # Use first row as header
    headers = data[0]
    rows = data[1:]

    # Create DataFrame
    df = pd.DataFrame(rows, columns=headers)

    return df

if __name__ == "__main__":
    df = load_data_from_gsheet()
    print("Data loaded from Google Sheets:")
    print(df)