# main.py (SnowGate)
from fastapi import APIRouter, FastAPI, HTTPException, APIRouter, Request, BackgroundTasks
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from groq import Groq
from ape import accounts, Contract, networks, project
from contextlib import asynccontextmanager
import os
import json
import asyncio
import requests
import time
from datetime import datetime
from pathlib import Path
from fastapi.templating import Jinja2Templates
from app.settings import settings
from app.helpers import convert_to_dollars, convert_to_wei, find_merchant

# Illustrative Agent View - This is where the "agent" lives, which in this case is just a simple interface to interact with the SnowGateSession contract. In production, this would be more complex and handle various agent tasks.


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
snowgate =  project.SnowGateSession.at(settings.snowgate_address)
client = Groq(api_key=settings.groq_api_key)

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





@router.get("/")
def agent(request: Request):
    return templates.TemplateResponse("agent.html", {
        "request": request, 
        "snowgate_address": settings.snowgate_address,
        "groq_api_key": settings.groq_api_key
    })


DELIVERY_TYPES = {"Secret": 1, "file": 0, "api": 2}


async def parse_ai(prompt: str):
    system = 'Convert to JSON: {"action": "purchase", "item_type": "api|file|secret", "quantity": number}'
    resp = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        model="openai/gpt-oss-120b",
        response_format={"type": "json_object"}
    )
    return json.loads(resp.choices[0].message.content)




async def purchase_stream(req: UserPrompt):
    try:
        yield json.dumps({"step": "parsing"}) + "\n"
        parsed = await parse_ai(req.prompt)
        
        if parsed.get("action") != "purchase":
            yield json.dumps({"step": "error", "message": "Not a purchase"}) + "\n"
            return
        
        item_type = parsed.get("item_type", "api").lower()
        qty = parsed.get("quantity", 1)
        delivery_type = DELIVERY_TYPES.get(item_type, 0)
        
        yield json.dumps({"step": "parsed", "amount": item_type, "quantity": qty, "item": item_type}) + "\n"
        
        yield json.dumps({"step": "searching", "item": item_type}) + "\n"
        merchant_addr = find_merchant(item_type)
        
        if not merchant_addr:
            yield json.dumps({"step": "error", "message": "No merchant"}) + "\n"
            return
        
        yield json.dumps({"step": "selecting", "address": merchant_addr}) + "\n"
        
        with networks.parse_network_choice(settings.network_string):
            merchant = Contract(merchant_addr)
            products, ids = merchant.get_active_products(0, 50)
            
            match_idx = None
            for i, p in enumerate(products):
                if p.delivery_type == delivery_type and p.is_active:
                    match_idx = i
                    break
            
            if match_idx is None:
                yield json.dumps({"step": "error", "message": f"No {item_type} products available"}) + "\n"
                return
            
            selected = products[match_idx]
            product_id = ids[match_idx]
            total_price = selected.price * qty
            
            yield json.dumps({
                "step": "selected",
                "product_id": int(product_id),
                "price": str(selected.price // 10 ** 6),
                "total": str(total_price)
            }) + "\n"
            
            yield json.dumps({"step": "executing"}) + "\n"
            
            account = accounts.load(settings.agent_alias)
            account.set_autosign(True, passphrase=settings.agent_pass)
            
            snowgate = Contract(settings.snowgate_address)
            
            tx = snowgate.execute_purchase(
                merchant_addr,
                int(product_id),
                merchant.merchant_id(),
                int(total_price),
                sender=account
            )
            
            yield json.dumps({"step": "executing_tx_hash", "tx_hash": tx.txn_hash}) + "\n"
            yield json.dumps({"step": "confirming"}) + "\n"
            
            receipt = tx.await_confirmations()
            
            yield json.dumps({
                "step": "confirmed",
                "tx_hash": tx.txn_hash,
                "block_number": receipt.block_number,
                "gas_used": receipt.gas_used
            }) + "\n"
            
            yield json.dumps({
                "step": "complete",
                "type": item_type,
                "quantity": qty,
                "total_paid": str(total_price),
                "tx": tx.txn_hash
            }) + "\n"
            
    except Exception as e:
        yield json.dumps({"step": "error", "message": str(e)}) + "\n"


@router.post("/parse-buy")
async def parse_buy(req: UserPrompt):
    return StreamingResponse(purchase_stream(req), media_type="application/x-ndjson")


@router.get("/balance")
def get_balance():
    with networks.parse_network_choice(settings.network_string):
        usdc = Contract(settings.usdc_address)
        bal = usdc.balanceOf(settings.snowgate_address)
    return {"balance": str(bal), "usdc": settings.usdc_address}


@router.post("/purchase")
def execute_purchase(req: PurchaseRequest):
    try:
        with networks.parse_network_choice(settings.network_string):
            account = accounts.load(settings.agent_alias)
            account.set_autosign(True, passphrase=settings.agent_pass)

            tx = snowgate.execute_purchase(
                req.shop,
                req.product_id,
                req.buyer_agent_id,
                int(req.price),
                sender=account,
                required_confirmations=1
            )
            
            return {
                "success": True,
                "tx_hash": tx.txn_hash,
                "gas_used": tx.gas_used
            }
            
    except Exception as e:
        raise HTTPException(500, str(e))

