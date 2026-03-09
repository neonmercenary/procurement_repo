# app/routes/merchants.py
from fastapi import APIRouter, Request, Depends, BackgroundTasks, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import json, os, asyncio
from app.db import get_db
from app.settings import settings
from web3 import Web3
from pydantic import BaseModel, Field
from ape import accounts, project, networks
from fastapi import APIRouter, Request
from app.templates import get_templates
from app.workers.sync_worker import agent_fulfillment_worker

next_product_id = 0
router = APIRouter(
    tags=["zero-degree"],
    responses={404: {"description": "Merchant not found"}}
)
templates = get_templates("app/templates/merchants", "app/templates")
active_workers = {}
next_worker_id = 1
# ============================================================================
# Pydantic Models
# ============================================================================

class DeployVendorShopRequest(BaseModel):
    registry: str
    payment: str
    merchant_id: int
    from_address: str = Field(..., description="The merchant's wallet address", alias="from_")

class ListProductRequest(BaseModel):
    shopAddress: str
    price: str
    uri: str
    delivery_type: int
    from_: str = None

class BuyProductRequest(BaseModel):
    shopAddress: str
    productId: int
    seller: str
    from_: str = None

class EligibilityCheckRequest(BaseModel):
    merchant_shop: str

class StartWorkerRequest(BaseModel):
    shop_address: str
# ============================================================================
# Utility: Load Contract ABIs
# ============================================================================

def load_account_by_address(address: str):
    """Find and load an Ape account by its address."""
    # Normalize address
    target = address.lower()
    
    # Iterate through all accounts
    for account in accounts:
        if account.address.lower() == target:
            return account
    
    # Not found
    raise ValueError(f"No Ape account found for address {address}")

# ============================================================================
# Routes
# ============================================================================
@router.get("/")
def index(request: Request):
    # Sometimes JS Cache can cause issues with loading the correct registry_address, USE CTRL + F5 to hard refresh if you see the wrong address in the form below
    return templates.TemplateResponse("merchant_dashboard.html", {
        "request": request,
        "registry_address": request.app.state.mall.address if request.app.state.mall else None,
        "usdc_address": settings.usdc_address,
        "erc8004_address": settings.identity_registry_address  # Assuming ERC-8004 is the identity registry for this example
    })

@router.get("/add")
def add_moderator(request: Request):
    from ape import Contract, accounts
    admin = accounts.load(settings.agent_alias)
    admin.set_autosign(True, passphrase=settings.agent_pass)
    with networks.parse_network_choice(settings.network_string):
        c = Contract(request.app.state.mall.address)
        c.add_moderator(settings.snowgate_address, sender=admin)

    return {"status": 200, "wallet": settings.snowgate_address}


@router.post("/api/merchant/start-worker")
async def start_worker_for_shop(req: StartWorkerRequest):
    """
    Start the fulfillment worker for an existing VendorShop.
    Called from JavaScript when loading a merchant dashboard.
    """
    shop_address = req.shop_address
    
    try:
        # Verify it's a valid VendorShop contract
        with networks.parse_network_choice(settings.network_string):
            shop_contract = project.VendorShopLite.at(shop_address)
            
            # Try to read basic info to verify contract exists
            try:
                merchant_id = shop_contract.merchant_id()
                owner = shop_contract.owner()
                print(f"Verified shop: merchant_id={merchant_id}, owner={owner}")

            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid VendorShop contract at {shop_address}: {str(e)}"
                )
            
            # Check if worker is already running (optional - track in memory)
            if shop_address in active_workers:
                return JSONResponse({
                    "success": True,
                    "message": "Worker already running",
                    "shop_address": shop_address,
                    "status": "already_active"
                })
            
            # Start the worker
            task = asyncio.create_task(agent_fulfillment_worker(shop_address, shop_contract.created_at_block()))
            active_workers[shop_address] = task
            
            return JSONResponse({
                "success": True,
                "message": "Worker started",
                "shop_address": shop_address,
                "merchant_id": merchant_id,
                "owner": str(owner),
                "status": "started"
            }, status_code=200)
            
    except HTTPException:
        raise
    
    except Exception as e:
        print(f"Error starting worker: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/api/merchant/deploy")
async def deploy_vendor_shop(req: DeployVendorShopRequest):
    """
    Deploy a new VendorShop contract for a merchant using Ape.
    """
    print(f"Registry: {req.registry}")
    print(f"Payment: {req.payment}")
    print(f"Merchant ID: {req.merchant_id}")
    print(f"From: {req.from_address}")  # Now matches the field name
    
    try:
        with networks.parse_network_choice(settings.network_string):
            
            # Load deployer - try configured alias first, then from_address
            deployer = None
            try:
                deployer = load_account_by_address(req.from_address)
                print(f"Loaded deployer from request address: {deployer.address}")
            except Exception as e1:
                print(f"Failed to load {settings.agent_alias}: {e1}")
                
                # Try to load from the request address
                try:
                    # Use the alias or create one from address
                    short_addr = str(req.from_address)[:8]
                    deployer = accounts.load(f"merchant_{short_addr}")
                except Exception as e2:
                    print(f"Failed to load merchant account: {e2}")
                    raise HTTPException(
                        status_code=400, 
                        detail=f"No Ape account found. Configure AGENT_ALIAS in settings or import account for {req.from_address}"
                    )
            
            # Auto-unlock if passphrase configured
            if settings.agent_pass:
                try:
                    deployer.set_autosign(True, passphrase=settings.agent_pass)
                    print("Deployer unlocked with configured passphrase")
                except Exception as e:
                    print(f"Unlock failed: {e}")
            
            # Verify merchant ownership
            registry_contract = project.ZeroDegreeRegistry.at(str(req.registry))
            try:
                owner = registry_contract.owner_of(req.merchant_id)
                print(f"Registry reports owner: {owner}, request from: {req.from_address}")
                
                if owner.lower() != str(req.from_address).lower():
                    raise HTTPException(
                        status_code=403,
                        detail=f"Address {req.from_address} does not own merchant ID {req.merchant_id}. Owner is {owner}."
                    )
            except Exception as e:
                if "does not own" in str(e):
                    raise
                raise HTTPException(
                    status_code=400,
                    detail=f"Registry error: {str(e)}"
                )
            
            # Deploy with auto-sign if possible
            print("Deploying VendorShop...")
            vendor_shop = deployer.deploy(
                    project.VendorShopLite,
                    str(req.registry),
                    str(req.payment),
                    req.merchant_id,
                    gas_limit=5000000,
                    publish=False  # Set to True to verify on explorer
                )
            
            print(f"Deployed to: {vendor_shop.address}")

            # 2. SPAWN THE WORKER: This runs in the background of the FastAPI process
            # We use asyncio.create_task so the API doesn't wait for the worker loop
            if vendor_shop.address not in active_workers:
                active_workers[vendor_shop.address] = asyncio.create_task(agent_fulfillment_worker(vendor_shop.address, vendor_shop.created_at_block))
            
            return JSONResponse({
                "success": True,
                "address": vendor_shop.address,
                "registry": str(req.registry),
                "payment_token": str(req.payment),
                "merchant_id": req.merchant_id,
                "owner": str(req.from_address),
                "deployer": deployer.address,
                "status": "deployed"
            }, status_code=201)
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unhandled error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
  

@router.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file and return IPFS/storage URI.
    For now, saves locally and returns a placeholder URI.
    """
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Save file locally (in production, integrate with IPFS, S3, etc.)
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, file.filename)
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Return placeholder IPFS-like URI
        uri = f"file:///{file_path}"
        return JSONResponse({"uri": uri})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

