import pandas as pd
import requests
from io import StringIO
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

# Google Sheets setup
SPREADSHEET_ID = "1pkLXZNj0nf32gU1EFBD38Qa0-NpdQZ-_"
SHEET_NAME = "SELIC historico"  # Change if your target sheet has a different name

# URL of the dataset
url = "https://www.tesourotransparente.gov.br/ckan/dataset/f0468ecc-ae97-4287-89c2-6d8139fb4343/resource/e5f90e3a-8f8d-4895-9c56-4bb2f7877920/download/VendasTesouroDireto.csv"

# Fetch the CSV file from the URL
response = requests.get(url)
if response.status_code == 200:
    # Load the CSV data into a Pandas DataFrame
    csv_data = StringIO(response.text)
    df = pd.read_csv(csv_data, sep=";")  # Adjust the separator if necessary
else:
    print("Failed to fetch the data. Status code:", response.status_code)
    exit()

# Ensure the column names are stripped of any leading/trailing spaces
df.columns = df.columns.str.strip()

# Convert 'Data Venda' and 'Vencimento do Titulo' to datetime format
df['Data Venda'] = pd.to_datetime(df['Data Venda'], format="%d/%m/%Y", errors='coerce')
df['Vencimento do Titulo'] = pd.to_datetime(df['Vencimento do Titulo'], format="%d/%m/%Y", errors='coerce')

# Drop rows with missing or invalid 'Data Venda'
df = df.dropna(subset=['Data Venda', 'Vencimento do Titulo'])

# Today's date
today = pd.Timestamp.today()

# Function to get closest row to today for a given set of filters
def get_closest_row(titulo_filter, vencimento_filter):
    filtered_df = df[
        (df['Tipo Titulo'] == titulo_filter) &
        (df['Vencimento do Titulo'].dt.year.isin(vencimento_filter))
    ]

    # Check if any rows match the filter
    if filtered_df.empty:
        print(f"No data found for {titulo_filter} with Vencimento {vencimento_filter}")
        return None

    # Sort by the closest 'Data Venda' to today
    filtered_df['Date Difference'] = (filtered_df['Data Venda'] - today).abs()
    closest_row = filtered_df.loc[filtered_df['Date Difference'].idxmin()]

    # Drop the helper column 'Date Difference'
    closest_row = closest_row.drop(labels=['Date Difference'])
    
    return closest_row

# Fetch closest rows for desired filters
selic_2025 = get_closest_row('Tesouro Selic', [2025])
selic_2026 = get_closest_row('Tesouro Selic', [2026])
selic_2027 = get_closest_row('Tesouro Selic', [2027])
prefixado_2027 = get_closest_row('Tesouro Prefixado', [2027])

# Collect results
results = [selic_2025, selic_2026, selic_2027, prefixado_2027]
results = [res for res in results if res is not None]

# Format results as a DataFrame
results_df = pd.DataFrame(results)

# Google Sheets Authentication
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"  # Optional, if needed
]

# Load credentials from GitHub secret (TS_CREDENTIALS)
credentials_json = os.getenv("TS_CREDENTIALS")  # Get credentials from GitHub secret

# Ensure that the credentials JSON string is loaded properly
if credentials_json is None:
    print("Error: Credentials not found in GitHub Secrets.")
    exit()

# Load the credentials from the environment variable (as a string)
credentials_info = json.loads(credentials_json)
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, scope)

# Authorize and create a client to interact with Google Sheets
client = gspread.authorize(credentials)

# Open the Google Sheet
try:
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
except gspread.exceptions.SpreadsheetNotFound as e:
    print(f"Error: Unable to find the spreadsheet with ID {SPREADSHEET_ID}")
    exit()
except gspread.exceptions.WorksheetNotFound as e:
    print(f"Error: Unable to find the worksheet {SHEET_NAME}")
    exit()

# Clear existing data in the sheet
sheet.clear()

# Add the new data (including column names and values)
sheet.update([results_df.columns.values.tolist()] + results_df.values.tolist())

print("Google Sheet updated successfully!")
