import os
import json
import gspread
from datetime import datetime
from fastapi import FastAPI, Request, BackgroundTasks
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai

app = FastAPI(title="Dhaba WhatsApp Bot - Stealth Logger")

# 1. Configure Gemini securely from Environment Variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("⚠️ Warning: GEMINI_API_KEY is missing!")

# 2. Define the Dhaba Menu & Prices
PRICE_LIST = {
    "vada pav": 20,
    "chai": 15,
    "samosa": 25,
    "misal pav": 80
}

def extract_order_with_gemini(raw_text: str):
    """Uses Gemini to parse unstructured Hindi/English text into clean JSON."""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash") 
        
        prompt = f"""
        You are an AI order extractor for a local Indian Dhaba.
        Your job is to listen to a raw customer message and extract the ordered food items and their exact quantities.
        
        Available items on our menu: {list(PRICE_LIST.keys())}
        
        Convert the text into a clean JSON dictionary where the keys are the exact item names from the menu list above, and values are integers representing the quantity.
        If an item mentioned is not on the menu list, match it to the closest match or ignore it if completely unrelated.
        Do not return any text, markdown format, or backticks. Return ONLY the raw JSON string.

        Customer Message: "{raw_text}"
        """
        response = model.generate_content(prompt)
        clean_json_str = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_json_str)
    except Exception as e:
        print(f"❌ Gemini Error: {e}")
        return None

def calculate_total_bill(extracted_items: dict):
    """Calculates total price based on our price list."""
    total = 0
    if not extracted_items:
        return 0
    for item, qty in extracted_items.items():
        price = PRICE_LIST.get(item.lower(), 0)
        total += price * qty
    return total

def log_to_sheets_production(customer_phone, raw_text, extracted_items, total_amount, status="Pending"):
    """Reads credentials from Environment Variable securely on Vercel."""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        google_creds_json = os.getenv("GOOGLE_CREDS_JSON")
        if not google_creds_json:
            print("❌ Production Sheets Error: GOOGLE_CREDS_JSON env var is empty!")
            return
            
        creds_dict = json.loads(google_creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        
        client = gspread.authorize(creds)
        sheet = client.open("whatbot db").sheet1
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, customer_phone, raw_text, str(extracted_items), f"Rs {total_amount}", status])
        print("✅ Logged directly to Google Sheet in Prod!")
    except Exception as e:
        print(f"❌ Production Sheets Error: {e}")

@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    customer_phone = payload.get("from")
    raw_text = payload.get("body")
    
    # Send to background task so Vercel responds instantly
    background_tasks.add_task(process_pipeline, customer_phone, raw_text)
    return {"status": "success"}

def process_pipeline(customer_phone, raw_text):
    # 1. Ask Gemini to extract items
    extracted_items = extract_order_with_gemini(raw_text)
    
    # 2. SILENT FILTER: If it's a normal chat (no food), ignore it completely
    if not extracted_items:
        print(f"🤫 No food detected. Ignoring message from {customer_phone}")
        return
        
    # 3. If it IS an order, compute the bill and log to Sheets
    total_bill = calculate_total_bill(extracted_items)
    log_to_sheets_production(customer_phone, raw_text, extracted_items, total_bill)
    
    # 4. Print success to Vercel logs, but DO NOT send a WhatsApp reply
    print(f"✅ Order from {customer_phone} silently recorded to Sheets!")