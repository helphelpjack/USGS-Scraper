import os
import re
import sys
import requests
from lxml import html
import pandas as pd
from datetime import datetime, timedelta

SITE_NUMBERS = ["02029000", "02030000", "02030500", "02034000", "02035000"]

def clean_value(raw_value):
    # Remove any non-digit, non-comma characters at the end (flags)
    value = re.sub(r'[^\d,.-]', '', raw_value)
    # Remove commas
    value = value.replace(",", "")
    # Convert to float (or int if you prefer)
    try:
        return float(value)
    except ValueError:
        return None

def get_date_range(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)

def scrape_usgs(site_no, date_str):
    url = f"https://waterdata.usgs.gov/nwis/dv?cb_00060=on&format=html&site_no={site_no}&legacy=&referred_module=sw&period=&begin_date={date_str}&end_date={date_str}"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch data for site {site_no} on {date_str}")
        return None

    tree = html.fromstring(response.content)
    tables = tree.xpath('//table')
    
    for table in tables:
        if "Daily Mean Discharge" in table.text_content():
            rows = table.xpath('.//tr')
            for row in rows:
                cells = row.xpath('.//th | .//td')
                cell_values = [cell.text_content().strip() for cell in cells]
                if len(cell_values) >= 2 and cell_values[0].isdigit():
                    return clean_value(cell_values[1])
    print(f"No data found for site {site_no} on {date_str}")
    return None

def is_file_locked(filename):
    """Returns True if file exists and is locked, False otherwise"""
    if not os.path.exists(filename):
        return False
    try:
        with open(filename, 'r+'):
            return False
    except IOError:
        return True

def wait_for_file_unlock(filename):
    """Keep prompting user until file is closed or cancelled"""
    while is_file_locked(filename):
        print(f"\nThe file '{filename}' is currently open. Please close it before continuing.")
        user_input = input("Type 'retry' to check again, or 'cancel' to exit without saving: ").strip().lower()
        if user_input == 'cancel':
            print("Cancelling program without saving data.")
            return False
        elif user_input == 'retry':
            continue
        else:
            print("Invalid input. Please type 'retry' or 'cancel'.")
    return True

def save_to_excel(df, filename, sheet_name):
    if not wait_for_file_unlock(filename):
        return False  # Cancelled by user
    if os.path.exists(filename):
        with pd.ExcelWriter(filename, engine='openpyxl', mode='a', if_sheet_exists='new') as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
    else:
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
    return True

def main():
    
    if len(sys.argv) >= 3 and sys.argv[1] and sys.argv[2]:
        start_date_str = sys.argv[1]
        end_date_str = sys.argv[2]
    elif len(sys.argv) == 2 and sys.argv[1]:
        start_date_str = sys.argv[1]
        end_date_str = start_date_str
    else:
        yesterday_str = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        start_date_str = yesterday_str
        end_date_str = yesterday_str
        print(f"Defaulting to yesterday's date: {yesterday_str}")


    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    except ValueError:
        print("Invalid date format.")
        return

    if start_date > end_date:
        print("Start date must be before end date.")
        return

    all_data = []

    for current_date in get_date_range(start_date, end_date):
        date_str = current_date.strftime("%Y-%m-%d")
        print(f"Scraping {date_str}...")
        row_data = {"Date": date_str}
        for site_no in SITE_NUMBERS:
            value = scrape_usgs(site_no, date_str)
            row_data[site_no] = value
        all_data.append(row_data)

    df = pd.DataFrame(all_data)

    filename = "USGSDataScraped.xlsx"
    sheet_name = f"{start_date_str}_to_{end_date_str}"

    if save_to_excel(df, filename, sheet_name):
        print(f"Data saved to {filename} (sheet: {sheet_name})")
        # Temporary Debug Log
        print(all_data)
    else:
        print("No data written.")

if __name__ == "__main__":
    main()