
# session_purchase.py (SnowGate) this is the router for /session, handles webhook and possibly sending back to the sap
from fastapi import APIRouter, FastAPI, HTTPException, APIRouter, Request, BackgroundTasks
from pydantic import BaseModel
from ape import networks, accounts, Contract, project
import json, httpx
from typing import Optional
from ape import accounts, Contract, networks
from fastapi.templating import Jinja2Templates
from app.settings import settings
from ape import networks, Contract
from fastapi import HTTPException, BackgroundTasks
from app.helpers import convert_to_dollars, convert_to_wei, find_merchant

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
snowgate = project.SnowGateSession.at(settings.snowgate_address)


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


@router.get("/session")
def session(request: Request):
    return templates.TemplateResponse("session.html", {
        "request": request,
        "snowgate_address": settings.snowgate_address,
    })


# Your internal mapping of SAP Material Groups to On-Chain SKUs
SKU_MAPPING = {
    "AI_COMPUTE": {"shop": settings.vendor_shop_address, "product_id": 3, "vendor_id": 23},
    "DATA_FEED": {"shop": settings.vendor_shop_address, "product_id": 2, "vendor_id": 23},
    "API_KEY": {'shop': settings.vendor_shop_address, "product_id": 1, "vendor_id": 23}
}


@router.post("/sap-webhook")
async def sap_translator(payload: dict, background_tasks: BackgroundTasks):
    d = payload.get("d", {})
    item = d.get("to_PurchaseRequisitionItem", [{}])[0]
    mat_group = item.get("MaterialGroup")
    mapping = SKU_MAPPING.get(mat_group)

    if not mapping:
        raise HTTPException(status_code=400, detail="SKU not recognized")

    # 1. IMMEDIATE EXTRACTION (No Network Calls)
    price_fiat = float(item.get("PurchaseRequisitionPrice", 0))
    price_usdc = int(price_fiat * 10 ** 6)
    requester = item.get("PurReqnCreatedByUser")
    v_id = mapping["vendor_id"]
    p_id = mapping["product_id"]

    # 2. PUSH EVERYTHING TO BACKGROUND
    # This returns '200 OK' to the SAP Simulator IMMEDIATELY
    background_tasks.add_task(
        execute_sync_procurement, # New wrapper function
        requester, p_id, v_id, price_usdc
    )

    return {"status": "accepted", "sap_pr": d.get("PurchaseRequisition")}

# 2. THE SYNC WRAPPER (Standard 'def', NOT 'async def')
def execute_sync_procurement(requester, p_id, v_id, price_usdc):
    import asyncio
    # This forces the async function to run to completion in the background thread
    asyncio.run(execute_unified_procurement(requester, p_id, v_id, price_usdc))

    

async def execute_unified_procurement(requester, p_id, v_id, price):
    print("Executing Procurement from requester:", requester)
    
    with networks.parse_network_choice(settings.network_string):
        relayer = accounts.load(settings.agent_alias)
        relayer.set_autosign(True, passphrase=settings.agent_pass)
        registry = Contract(settings.zero_degree_registry_address)
        snowgate_contract = Contract(settings.snowgate_address)
        usdc_contract = Contract(settings.usdc_address)
        linked_shop = registry.shop_address(v_id)
        shop = linked_shop
        shop_contract = Contract(shop)
        
        # === DIAGNOSTICS ===
        print(f"\n🔍 DIAGNOSTICS:")
        
        # 3. Check merchant status
        can_sell = registry.can_merchant_sell(v_id, sender=relayer)
        print(f"  Merchant {v_id} can sell: {can_sell}")
        
        # 4. Check session
        session = snowgate_contract.sessions(relayer.address, sender=relayer)
        print(f"  Relayer session: approved={session[0]}, max={session[1]}, spent={session[2]}, expires={session[3]}")
        
        # 5. Check shop is linked to merchant
        
        print("Snowgate Address:", settings.snowgate_address)
        print(f"  Merchant {v_id} linked shop: {linked_shop}")
        print(f"  Expected shop: {shop}")
        print(f"  Match: {linked_shop.lower() == shop.lower()}")
        
        # Fail fast if prerequisites not met
        # if sg_balance < price:
        #     raise Exception(f"SnowGate underfunded: {sg_balance} < {price}")

        if not can_sell:
            raise Exception(f"Merchant {v_id} cannot sell")
        

        # Check session - returns tuple: (approved, max_amount, spent, expires)
        session = snowgate_contract.sessions(relayer.address)
        session_approved = session[0]
        session_max = session[1]
        session_spent = session[2]
        session_expires = session[3]
        current_time = networks.active_provider.get_block("latest").timestamp
        
        print(f"Session state: approved={session_approved}, max={session_max}, spent={session_spent}, expires={session_expires}")
        
        # ✅ FIXED: Create session if NOT approved OR EXPIRED or INSUFFICIENT REMAINING BUDGET
        remaining_budget = session_max - session_spent
        needs_session = (
            not session_approved or 
            session_expires < current_time or 
            remaining_budget < price
        )
        
        if needs_session:
            # ✅ Create session with LARGE CAP - this is a "vault spending cap" not per-transaction
            # Use a large buffer (e.g., 10x price or a fixed large amount)
            new_budget = price * 1000  # At least 1000 USDC or 10x price
            
            print(f"🔓 Creating/Extending SnowGate Session with budget: {new_budget}")
            
            # Relayer creates session for themselves (they are the "buyer" in the session system)
            snowgate_contract.create_session(new_budget, 7, sender=relayer, gas_limit=300_000)
            print(f"✅ Session created")
            
            # Re-fetch session to confirm
            new_session = snowgate_contract.sessions(relayer.address)
            print(f"New session: max={new_session[1]}, spent={new_session[2]}")

        # ✅ CRITICAL: Ensure relayer has approved SnowGate to spend their USDC
        # But wait - the USDC should be IN SnowGate, not with relayer
        # So actually, SnowGate needs to have approved the Shop to pull from IT
        
        # Execute purchase
        print(f"💸 Executing purchase for SKU #{p_id}...")
        try:
            # The buyer is relayer.address (the session holder)
            # SnowGate uses ITS OWN USDC vault to approve the shop
            tx = snowgate_contract.execute_purchase(
                relayer.address,  # buyer = session owner
                shop, 
                p_id, 
                price, 
                sender=relayer,
                # gas_limit=8_000_000
            )
            confirmed_block = tx.block_number
            print(f"✅ Purchase executed: {tx.txn_hash}")
            print(f"📦 Confirmed in Block: {confirmed_block}")
            
        
            
            # --- THE TRIGGER: Wake up the Delivery Monitor ---
            # We hit the localhost /monitor endpoint to start the background task
            async with httpx.AsyncClient() as client:
                try:
                    monitor_url = f"http://localhost:8001/monitor"
                    response = await client.post(monitor_url, json={"address": shop})
                    if response.status_code == 200: pass

                except Exception as monitor_err:
                    print(f"⚠️ Could not auto-trigger monitor: {monitor_err}")

        except Exception as e:
            print(f"🔥 EXECUTION FAILURE: {e}")
            # Try to get more details
            import traceback
            traceback.print_exc()
            raise