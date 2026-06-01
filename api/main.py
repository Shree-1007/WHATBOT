import os
import gspread
from datetime import datetime
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import PlainTextResponse
from oauth2client.service_account import ServiceAccountCredentials

app = FastAPI(title="Dhaba WhatsApp Bot")

# 1. Configuration & Secrets
# These will be set in Vercel's Environment Variables later
VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "dhaba_bot_secret_2026")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")

# 2. Google Sheets Setup
# This tells the server how to log into your database
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

def log_to_sheets(customer_phone, raw_text, extracted_items, total_amount, status="Pending"):
    try:
        # Assumes google_creds.json is in the root folder of your project
        creds = ServiceAccountCredentials.from_json_keyfile_name("google_creds.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open("Dhaba Orders V1").sheet1
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_data = [timestamp, customer_phone, raw_text, extracted_items, total_amount, status]
        
        sheet.append_row(row_data)
        print(f"Logged order for {customer_phone} to Sheets.")
    except Exception as e:
        print(f"Failed to log to Sheets: {e}")

# 3. Server Health Check
@app.get("/")
def read_root():
    return {"status": "online", "message": "Dhaba Bot is running on Vercel"}

# 4. Meta Webhook Verification (Required by WhatsApp)
@app.get("/webhook", response_class=PlainTextResponse)
def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verified successfully!")
        return challenge
    return Response(content="Verification failed", status_code=403)

# 5. Catch Incoming WhatsApp Messages
@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    
    # We use BackgroundTasks so we can reply to Meta instantly (preventing the 5-sec timeout)
    background_tasks.add_task(process_message, payload)
    
    return {"status": "success"}

# 6. The Brain: Process the message in the background
def process_message(payload: dict):
    try:
        # Dig safely through Meta's deeply nested JSON payload
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        
        if "messages" in value:
            message = value["messages"][0]
            
            # Ensure it is a text message (ignoring images/audio for V1)
            if message.get("type") == "text":
                customer_phone = message["from"]
                raw_text = message["text"]["body"]
                
                print(f"New message from {customer_phone}: {raw_text}")
                
                # --- GEMINI AI PLACEHOLDER ---
                # We will write the Gemini API call here next to parse the raw_text.
                # For now, we are hardcoding a fake extraction just to test the pipeline.
                fake_extracted_items = "{'vada pav': 1, 'chai': 2}"
                fake_total = "Rs 45"
                
                # Log it directly to your Google Sheet
                log_to_sheets(
                    customer_phone=customer_phone,
                    raw_text=raw_text,
                    extracted_items=fake_extracted_items,
                    total_amount=fake_total
                )
                
    except Exception as e:
        print(f"Error processing message: {e}")