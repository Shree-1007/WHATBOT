import os
import json
import gspread
from datetime import datetime
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import PlainTextResponse
from oauth2client.service_account import ServiceAccountCredentials

app = FastAPI(title="Dhaba WhatsApp Bot")

# 1. Configuration & Secrets from Vercel Environment Variables
VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "dhaba_bot_secret_2026")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")

# 2. Google Sheets Authentication Scope
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

def log_to_sheets(customer_phone, raw_text, extracted_items, total_amount, status="Pending"):
    try:
        # Fetch the JSON credentials from Vercel's environment variables
        google_creds_json = os.getenv("GOOGLE_CREDS_JSON")
        
        if not google_creds_json:
            print("❌ Error: GOOGLE_CREDS_JSON environment variable is missing on Vercel!")
            return
            
        # Parse the JSON string into a Python dictionary
        creds_dict = json.loads(google_creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        
        # Authorize and open the specific spreadsheet: "whatbot db"
        client = gspread.authorize(creds)
        sheet = client.open("whatbot db").sheet1
        
        # Prepare the row data
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_data = [timestamp, customer_phone, raw_text, extracted_items, total_amount, status]
        
        # Append the row to your Google Sheet
        sheet.append_row(row_data)
        print(f"✅ Successfully logged order for {customer_phone} to 'whatbot db'.")
        
    except Exception as e:
        print(f"❌ Failed to log to Sheets: {e}")

# 3. Server Health Check Endpoint
@app.get("/")
def read_root():
    return {"status": "online", "message": "Dhaba Bot is running on Vercel"}

# 4. Meta Webhook Verification Handler (GET)
@app.get("/webhook", response_class=PlainTextResponse)
def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook verified successfully by Meta!")
        return challenge
    return Response(content="Verification failed", status_code=403)

# 5. Live Incoming WhatsApp Messages Handler (POST)
@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    
    # Send the payload to processing in the background to reply to Meta instantly (200 OK)
    background_tasks.add_task(process_message, payload)
    
    return {"status": "success"}

# 6. Background Processing Pipeline
def process_message(payload: dict):
    try:
        # Navigate Meta's JSON schema safely
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        
        if "messages" in value:
            message = value["messages"][0]
            
            # Ensure we are only dealing with text messages for now
            if message.get("type") == "text":
                customer_phone = message["from"]
                raw_text = message["text"]["body"]
                
                print(f"📥 New message from {customer_phone}: '{raw_text}'")
                
                # --- GEMINI AI PLACEHOLDER ---
                # This placeholder mimics the extraction structure until we implement the model logic
                fake_extracted_items = "{'vada pav': 1, 'chai': 2}"
                fake_total = "Rs 45"
                
                # Forward to Google Sheets function
                log_to_sheets(
                    customer_phone=customer_phone,
                    raw_text=raw_text,
                    extracted_items=fake_extracted_items,
                    total_amount=fake_total
                )
                
    except Exception as e:
        print(f"❌ Error processing message webhook payload: {e}")