# main.py (SnowGate)
from fastapi import APIRouter, FastAPI, HTTPException, APIRouter, Request, BackgroundTasks
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from ape import accounts, Contract, networks
from contextlib import asynccontextmanager
import os
import json
import requests
import asyncio
from datetime import datetime
from pathlib import Path
from fastapi.templating import Jinja2Templates
from app.settings import settings
from app.views import agent, session_purchase
from app.helpers import decrypt_api_key

router = APIRouter(tags=["snowgate"])
templates = Jinja2Templates(directory="app/templates")

# Config
SNOWGATE_ADDRESS = settings.snowgate_address
USDC_ADDRESS = settings.usdc_address
NETWORK = settings.network_string
RELAYER_ACCOUNT = settings.agent_alias
snowgate = None

# State management
STATE_DIR = Path("./monitor_states")
STATE_DIR.mkdir(exist_ok=True)

# Store active monitoring tasks
active_monitors: dict[str, asyncio.Task] = {}


def get_state_file(shop_address: str) -> Path:
    """Get state file path for a shop"""
    safe_addr = shop_address.lower().replace("0x", "")
    return STATE_DIR / f"shop_{safe_addr}.json"


def load_state(shop_address: str) -> dict:
    """Load saved state for a shop"""
    state_file = get_state_file(shop_address)
    if state_file.exists():
        try:
            with open(state_file, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Failed to load state: {e}")
    return {
        "last_processed_block": 0,
        "event_count": 0,
        "last_event_time": None,
        "started_at": None,
        "total_runtime_minutes": 0
    }


def save_state(shop_address: str, state: dict):
    """Save state to file"""
    state_file = get_state_file(shop_address)
    try:
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to save state: {e}")


def clear_state(shop_address: str):
    """Clear saved state for a shop"""
    state_file = get_state_file(shop_address)
    if state_file.exists():
        state_file.unlink()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global snowgate
    with networks.parse_network_choice(NETWORK):
        snowgate = Contract(SNOWGATE_ADDRESS)
    print(f"✅ Loaded SnowGate at {SNOWGATE_ADDRESS}")



    yield
    
    # Shutdown - cancel all monitors
    for shop, task in active_monitors.items():
        print(f"Cancelling monitor for {shop}")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    print("👋 Shutting down")


app = FastAPI(title="SnowGate API", lifespan=lifespan)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent.router, prefix="/agent")
app.include_router(session_purchase.router, prefix="/session")


class PurchaseRequest(BaseModel):
    shop: str
    product_id: int
    buyer_agent_id: int
    price: str


class ShopAddress(BaseModel):
    address: str


class UserPrompt(BaseModel):
    prompt: str


class BuyRequest(BaseModel):
    prompt: str
    userAddress: str


class PurchaseAction(BaseModel):
    action: str
    product: str
    quantity: Optional[int] = 1


@app.get("/")
def root(request: Request):
    return templates.TemplateResponse("base.html", {
        "request": request, 
        "status": "SnowGate API", 
        "snowgate_address": SNOWGATE_ADDRESS,
        "usdc_address": USDC_ADDRESS,
        "rpc_url": settings.rpc_url
    })


@app.post("/monitor")
async def start_monitoring(data: ShopAddress):
    """Start monitoring a shop for ProductDelivered events"""
    shop_addr = data.address.lower()
    
    # Cancel existing if running
    if shop_addr in active_monitors:
        if not active_monitors[shop_addr].done():
            active_monitors[shop_addr].cancel()
        del active_monitors[shop_addr]
    
    # Start new background task
    task = asyncio.create_task(delivery_monitoring_worker(shop_addr))
    active_monitors[shop_addr] = task
    
    return {
        "status": "started",
        "shop": shop_addr,
        "message": "Delivery monitoring started"
    }


@app.delete("/monitor/{shop_addr}")
async def stop_monitoring(shop_addr: str):
    """Stop monitoring a specific shop"""
    shop_addr = shop_addr.lower()
    
    if shop_addr in active_monitors:
        active_monitors[shop_addr].cancel()
        try:
            await active_monitors[shop_addr]
        except asyncio.CancelledError:
            pass
        del active_monitors[shop_addr]
        return {"status": "stopped", "shop": shop_addr}
    
    raise HTTPException(status_code=404, detail="Monitor not found")


@app.get("/monitor/state/{shop_address}")
async def get_monitor_state(shop_address: str):
    """Get saved state for a shop"""
    state = load_state(shop_address)
    return {
        "shop": shop_address,
        "state": state,
        "state_file_exists": get_state_file(shop_address).exists()
    }


@app.delete("/monitor/state/{shop_address}")
async def clear_monitor_state(shop_address: str):
    """Clear saved state for a shop (fresh start)"""
    clear_state(shop_address)
    return {"status": "cleared", "shop": shop_address}


@app.get("/monitor/states")
async def list_all_states():
    """List all saved monitor states"""
    states = []
    for f in STATE_DIR.glob("shop_*.json"):
        addr = f.stem.replace("shop_", "")
        try:
            with open(f) as file:
                data = json.load(file)
                states.append({
                    "shop": f"0x{addr}",
                    "events": data.get("event_count", 0),
                    "last_block": data.get("last_processed_block", 0),
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                })
        except:
            pass
    return {"states": states}




async def delivery_monitoring_worker(shop_address):
    print(f"📦 Delivery Monitor Online: Tracking VendorShop @ {shop_address}")
    
    # 1. Load state - persist strictly
    state = load_state(shop_address)
    last_processed_block = state.get("last_processed_block", 0)

    if last_processed_block == 0:
        with networks.parse_network_choice(NETWORK):
            # Fallback to contract creation or a safe recent height
            last_processed_block = Contract(shop_address).created_at_block()
            print(f"🏗️ Starting from Contract Creation: {last_processed_block}")

    while True:
        with networks.parse_network_choice(NETWORK):
            try:
                # Get the absolute current height
                current_chain_height = networks.active_provider.get_block("latest").number
                
                # If we are already caught up, just wait
                if last_processed_block >= current_chain_height:
                    print(f"💤 Caught up to head ({current_chain_height}). Waiting...")
                    await asyncio.sleep(10)
                    continue

                print(f"🔍 Scanning: {last_processed_block + 1} -> {current_chain_height}")
                
                params = {
                    "module": "account",
                    "action": "txlist",
                    "address": shop_address,
                    "startblock": str(last_processed_block + 1),
                    "endblock": str(current_chain_height),
                    "sort": "asc",
                    "apikey": "any-string-works"
                }

                response = requests.get(settings.routescan_api, params=params)
                data = response.json()

                if data.get("status") == "1":
                    tx_list = data.get("result", [])
                    for tx in tx_list:
                        tx_hash = tx['hash']
                        receipt = networks.active_provider.get_receipt(tx_hash)
                        
                        if receipt.status == 1:
                            for event in receipt.events:
                                if event.event_name == "OrderCompleted":
                                    args = event.event_arguments
                                    order_id = args.get("order_id")
                                    payload = args.get("payload")
                                    
                                    print(f"🎯 Delivery Detected: Order {order_id}!")
                                    # Use await here if you want the logs to stay in order for the video
                                    await relay_delivery_to_sap(order_id, payload, tx_hash, shop_address)

                        # Increment only after successful processing of the tx block
                        last_processed_block = int(tx['blockNumber'])
                
                # IMPORTANT: Only move to the chain height if we've checked the range
                # No more 'jumps' that bypass the API's indexed data
                last_processed_block = current_chain_height
                
                # 4. Save State strictly
                state["last_processed_block"] = last_processed_block
                state["last_sync"] = datetime.now().isoformat()
                save_state(shop_address, state)
                
            except Exception as e:
                print(f"⚠️ Delivery Worker Error: {e}")
        
        await asyncio.sleep(10) # 10s is perfect for Fuji indexing time
            



async def relay_delivery_to_sap(order_id, payload, tx_hash, shop_address):
    # 1. Use 'localhost' or '0.0.0.0' if 127.0.0.1 is being refused
    callback_url = "http://localhost:8081/receive_payload" 
    
    # 2. Add explicit headers to satisfy FastAPI's requirements
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    data = {
        "sap_pr": str(order_id),
        "status": "DELIVERED",
        "tx_hash": f"https://testnet.snowtrace.io/tx/{tx_hash}",
        "payload": decrypt_api_key(payload)
    }
    
    try:
        # 3. Use a slightly longer timeout just in case of local lag
        # Ensure you are using 'requests' (synchronous) or 'httpx' (async)
        # Since this is an 'async def', 'httpx' is technically better, but 'requests' works
        res = requests.post(callback_url, json=data, headers=headers, timeout=10)
        
        if res.status_code == 200:
            print(f"✅ SAP NOTIFIED: Order {order_id} successfully closed in ERP.")
            clear_state(shop_address)
            print(f"🧹 State cleared for {shop_address}. System ready for next PR.")
        else:
            print(f"⚠️ SAP responded with error {res.status_code}: {res.text}")

    except requests.exceptions.ConnectionError:
        # Try the alternative address if the first one fails
        print("🔄 Primary connection failed, trying fallback to 0.0.0.0...")
        try:
            fallback_url = "http://0.0.0.0:8081/receive_payload"
            requests.post(fallback_url, json=data, headers=headers, timeout=5)
        except Exception as fe:
            print(f"🚨 CALLBACK FAILED: Total silence from SAP. {fe}")



@app.get("/health")
def health():
    return {"status": "ok", "snowgate": SNOWGATE_ADDRESS}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)