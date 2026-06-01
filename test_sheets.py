import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# 1. Define the scope of access
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

def test_sheet_connection():
    try:
        print("Connecting to Google Sheets...")
        # 2. Authenticate using your JSON key
        creds = ServiceAccountCredentials.from_json_keyfile_name("google_creds.json", scope)
        client = gspread.authorize(creds)
        
        # 3. Open the specific Google Sheet (make sure the name matches exactly!)
        sheet = client.open("whatbot db").sheet1
        
        # 4. Create fake order data
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fake_order = [
            timestamp, 
            "919876543210", 
            "Bhaiya 2 vada pav aur 1 chai dena", 
            "{'vada pav': 2, 'chai': 1}", 
            "Rs 55", 
            "Pending"
        ]
        
        # 5. Insert the data into the next empty row
        sheet.append_row(fake_order)
        print("✅ Success! Check your Google Sheet. The fake order should be there.")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_sheet_connection()