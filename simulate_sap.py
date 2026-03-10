import requests
import threading
import time
import uvicorn
from fastapi import FastAPI, Request

# --- CONFIGURATION ---
FASTAPI_URL = "http://localhost:8001/session/sap-webhook"
LISTENER_PORT = 8081
CALLBACK_URL = f"http://localhost:{LISTENER_PORT}/receive_payload"

app = FastAPI()

# The EXACT OData structure an S/4HANA system sends
SAP_DATA = {
    "d": {
        "PurchaseRequisition": "1004592",
        "PurchaseRequisitionType": "NB",
        "SourceSystem": "S4_HANA_CLOUD",
        "to_PurchaseRequisitionItem": [
            {
                "PurchaseRequisitionItem": "10",
                "PurReqnCreatedByUser": "thomas.muller@company.com",
                "RequestedQuantity": "1.000",
                "BaseUnit": "EA",
                "PurchaseRequisitionPrice": "1.00",
                "Currency": "USDC",
                "MaterialGroup": "API_KEY",
                "CostCenter": "CC_AI_MOG_01",
                "YY1_AgentID_PRI": "23",
                "YY1_VendorShop_PRI": "0xVendorShopAddress",
                "YY1_CallbackURL_PRI": CALLBACK_URL 
            }
        ]
    }
}

# --- HELPERS ---
def decrypt_api_key(encrypted_payload: str):
    # If it's already a readable KEY_, just return it!
    if encrypted_payload.startswith("KEY_"):
        return encrypted_payload
        
    try:
        # Otherwise, try to decode from hex
        clean_hex = encrypted_payload[2:] if encrypted_payload.startswith("0x") else encrypted_payload
        return bytes.fromhex(clean_hex).decode('utf-8')
    except Exception:
        # If all else fails, just show the raw data
        return encrypted_payload

@app.post("/receive_payload")
async def receive_payload(request: Request):
    data = await request.json()
    
    print("\n" + "💎" * 20)
    print("ERP: INBOUND RECEIPT DETECTED")
    print(f"🔗 TX Hash: {data.get('tx_hash')}")
    
    # Get the payload and clean it up
    raw_payload = data.get('payload', '')
    final_asset = decrypt_api_key(raw_payload)
    
    print(f"🔐 Asset Delivered: {final_asset}")
    print("💎" * 20 + "\n")
    
    return {"status": "ACKNOWLEDGE"}

# --- 2. THE TRIGGER (Sends to SnowGate) ---
def trigger_procurement():
    # Wait for the Uvicorn server to start up
    time.sleep(3) 
    print(f"🛰️ OUTBOUND: Sending PR {SAP_DATA['d']['PurchaseRequisition']} to SnowGate...")
    print("Data sent (SAP Standard):", SAP_DATA)
    try:
        # 30s timeout to account for Avalanche RPC latency
        response = requests.post(FASTAPI_URL, json=SAP_DATA, timeout=30)
        if response.status_code in [200, 202]:
            print(f"✅ MIDDLEWARE ACCEPTED: {response.json().get('status')}")
            print("⏳ WAITING FOR ON-CHAIN FINALITY (Check this terminal for results)...")
        else:
            print(f"❌ REJECTED: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"🚨 CONNECTION ERROR: {e}")

# --- 3. THE EXECUTION ---
if __name__ == "__main__":
    # Start the Trigger in a separate thread so it doesn't block the server
    threading.Thread(target=trigger_procurement, daemon=True).start()

    # Start the FastAPI Listener
    print(f"🛰️ SAP Emulator listening on port {LISTENER_PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=LISTENER_PORT, log_level="error")