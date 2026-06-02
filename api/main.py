import os
import json
import gspread
import requests
from datetime import datetime
from fastapi import FastAPI, Request, BackgroundTasks
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai

app = FastAPI(title="Dhaba WhatsApp Bot - Production Brain")

# 1. Configure Gemini securely from Environment Variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

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
        # Using the active model you confirmed works locally
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
        # Production look up: Grab stringified JSON from Vercel env
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

def send_production_reply(customer_phone, text_to_send):
    """Sends the compiled reply back to our Render waiter link."""
    RENDER_HELPER_URL = os.getenv("RENDER_HELPER_URL")
    if not RENDER_HELPER_URL:
        print("❌ Error: RENDER_HELPER_URL variable is not set yet.")
        return
        
    url = f"{RENDER_HELPER_URL.rstrip('/')}/send"
    payload = {"to": customer_phone, "message": text_to_send}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"❌ Failed to hit Render outbound channel: {e}")

@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    customer_phone = payload.get("from")
    raw_text = payload.get("body")
    
    background_tasks.add_task(process_pipeline, customer_phone, raw_text)
    return {"status": "success"}

def process_pipeline(customer_phone, raw_text):
    extracted_items = extract_order_with_gemini(raw_text)
    if not extracted_items:
        send_production_reply(customer_phone, "Sorry, I couldn't catch that order clearly. Can you try again?")
        return
        
    total_bill = calculate_total_bill(extracted_items)
    log_to_sheets_production(customer_phone, raw_text, extracted_items, total_bill)
    
    item_lines = "\n".join([f"- {item.title()} x {qty}" for item, qty in extracted_items.items()])
    reply_message = f"🍔 *Dhaba Order Confirmed!*\n\n*Items Ordered:*\n{item_lines}\n\n💰 *Total Amount:* Rs {total_bill}"
    
    send_production_reply(customer_phone, reply_message)