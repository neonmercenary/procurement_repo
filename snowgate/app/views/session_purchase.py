
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
ZERO_DEGREE_REGISTRY = "0xeB5f3ef568babdf1009b7cf82A7C93F10F979cd6"


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
    "AI_COMPUTE": {"shop": settings.vendor_shop_address, "product_id": 3, "vendor_id": 24},
    "DATA_FEED": {"shop": settings.vendor_shop_address, "product_id": 2, "vendor_id": 24},
    "API_KEY": {'shop': settings.vendor_shop_address, "product_id": 1, "vendor_id": 24}
}


@router.post("/sap-webhook")
async def sap_translator(payload: dict, background_tasks: BackgroundTasks):
    d = payload.get("d", {})
    item = d.get("to_PurchaseRequisitionItem", [{}])[0]
    mat_group = item.get("MaterialGroup")
    mapping = SKU_MAPPING.get(mat_group)

    if not mapping:
        raise HTTPException(status_code=400, detail="SKU not recognized")
    
    # 1. IMMEDIATE EXTRACTION
    price_fiat = float(item.get("PurchaseRequisitionPrice", 0))
    price_usdc = int(price_fiat * 10 ** 6)
    requester = item.get("PurReqnCreatedByUser")
    v_id = mapping["vendor_id"]
    p_id = mapping["product_id"]

    # 2. PRE-FLIGHT CONTRACT CHECKS
    # We do this here to block the '200 OK' if the vault is empty
    with networks.parse_network_choice(settings.network_string):
        snowgate_contract = Contract(settings.snowgate_address)
        
        # Check 1: Vault Liquidity
        if not snowgate_contract.can_afford(price_usdc):
            print(f"🛑 SAP REJECTED: SnowGate Vault at {settings.snowgate_address} is underfunded.")
            raise HTTPException(status_code=400, detail="Corporate Vault Underfunded")
            
        # # Check 2: Merchant Validity (Optional but recommended)
        # registry = Contract(ZERO_DEGREE_REGISTRY)
        # if not registry.can_merchant_sell(v_id):
        #     print(f"🛑 SAP REJECTED: Merchant {v_id} is disabled or unauthorized.")
        #     raise HTTPException(status_code=400, detail="Merchant Unauthorized")

    # 3. PUSH TO BACKGROUND (Only if pre-flight passes)
    background_tasks.add_task(
        execute_sync_procurement, 
        requester, p_id, v_id, price_usdc
    )

    return {"status": "accepted", "sap_pr": d.get("PurchaseRequisition")}

# 2. THE SYNC WRAPPER (Standard 'def', NOT 'async def')
def execute_sync_procurement(requester, p_id, v_id, price_usdc):
    import asyncio
    # This forces the async function to run to completion in the background thread
    asyncio.run(execute_unified_procurement(requester, p_id, v_id, price_usdc))

    
async def execute_unified_procurement(requester, p_id, v_id, price):
    print(f"🚀 Processing SAP Procurement for {requester} | Price: ${convert_to_dollars(price)}")
    
    with networks.parse_network_choice(settings.network_string):
        relayer = accounts.load(settings.agent_alias)
        relayer.set_autosign(True, passphrase=settings.agent_pass)
        
        registry = Contract(ZERO_DEGREE_REGISTRY)
        snowgate_contract = Contract(settings.snowgate_address)
        shop = registry.shop_address(v_id)
        
        # 1. FETCH UPDATED SESSION STATE (Matches new Vyper Struct)
        # Returns: (approved, max_amount, locked_escrow, settled_spent, expires)
        session = snowgate_contract.sessions(relayer.address)
        s_approved = session[0]
        s_max = session[1]
        s_locked = session[2]
        s_settled = session[3]
        s_expires = session[4]
        
        current_time = networks.active_provider.get_block("latest").timestamp
        
        # 2. LOGIC: Calculate True Available Budget
        # Funds are "taken" as soon as they are locked in escrow
        available_budget = s_max - (s_locked + s_settled)
        print("Available Budget:", convert_to_dollars(available_budget))
        
        needs_new_session = (
            not s_approved or 
            s_expires < current_time or 
            available_budget < price
        )
        
        # 3. HANDLE SESSION LIFECYCLE
        if needs_new_session:
            print(f"🔓 Budget exhausted or expired. Creating new SnowGate Session...")
            # Set a high cap (e.g., 10,000 USDC) to avoid frequent re-approvals
            new_cap = max(price * 10, 10_000 * 10**6) 
            snowgate_contract.create_session(new_cap, 7, sender=relayer)
        
        # 4. EXECUTE PURCHASE (Locks funds into Escrow)
        print(f"💸 Locking ${convert_to_dollars(price)} USDC in SnowGate Escrow for Shop {v_id}...")
        try:
            tx = snowgate_contract.execute_purchase(
                relayer.address, 
                shop, 
                p_id, 
                price, 
                sender=relayer
            )
            print(f"✅ Escrow Locked. Order Created: {tx.txn_hash}")
            print("Block Number:", tx.block_number)
        
            
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
            print(f"🔥 PROCUREMENT FAILED: {e}")
            # Try to get more details
            import traceback
            traceback.print_exc()
            raise