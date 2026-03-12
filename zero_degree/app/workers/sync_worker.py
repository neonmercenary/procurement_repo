import os
import json
import asyncio
import requests
from app.settings import settings
from ape import networks, accounts, Contract
from app.helpers import encrypt_delivery_payload
    
CONTRACT_ADDRESS = settings.snowgate_address
AGENT_ALIAS = settings.agent_alias
AGENT_PASSWORD = settings.agent_pass    # This is not secure for production! Consider using a vault or secure secrets manager.
NETWORK_STRING = settings.network_string
STATE_FILE = settings.worker_state_file
IDENTITY_REGISTRY = settings.identity_registry_address or "0x1aB8e9c3b1C2e5D7F4A9E6B8C3D2f5A6E7F8g9h0" # Replace with actual address after deployment
ROUTESCAN_API = "https://api.routescan.io/v2/network/testnet/evm/43113/etherscan/api"   # Routescan V2 API for Fuji
SLEEP = 5
ORDER_CREATED_TOPIC = "0xf9e17940e547201709f9aaacdec8ab3566601c60d8f5affb54f74b79b0b50b13"


def load_state():   
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"last_synced_block": 0}

def save_state(block_num):
    with open(STATE_FILE, "w") as f:
        json.dump({"last_synced_block": block_num}, f)

def load_shop_state(shop_address: str): 
    filename = f"state_{shop_address[:10]}.json" # Unique file per shop
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"last_synced_block": 0}

def save_shop_state(shop_address: str, block_num: int):
    filename = f"state_{shop_address[:10]}.json"
    with open(filename, "w") as f:
        json.dump({"last_synced_block": block_num}, f)


async def agent_fulfillment_worker(shop_address, start_block):
    """
    Monitors a specific VendorShop for OrderCreated events and fulfills them.
    @dev: in production this is managed by the agent
    """
    print(f"🤖 Agent Bot Online: Monitoring Orders for Shop @ {shop_address}")
    
    # Load Merchant Account (The fulfiller)
    merchant = accounts.load(settings.vendor_alias_ape)
    merchant.set_autosign(True, passphrase=settings.agent_pass)

    while True:
        try:
            # 1. RE-SYNC STATE: Load cursor from local storage/db
            state = load_shop_state(shop_address)
            last_processed_block = state.get("last_synced_block") or start_block

            with networks.parse_network_choice(settings.network_string):
                shop_contract = Contract(shop_address)
                current_head = networks.active_provider.get_block("latest").number
                
                # Use a 3-block safety buffer to ensure log stability
                safe_target = current_head - 10

                if last_processed_block >= safe_target:
                    print(f"😴 Caught up to head (Block {safe_target}). Sleeping...")
                    await asyncio.sleep(SLEEP)
                    continue

                from_block = int(last_processed_block) + 1
                to_block = safe_target

                print(f"🔍 Scanning Safe Range: {from_block} to {to_block} (Chain Head: {current_head})")
                
                params = {
                    "module": "logs",
                    "action": "getLogs",
                    "address": str(shop_address),
                    "fromBlock": str(from_block),
                    "toBlock": str(to_block),
                    "apikey": "build_games_2026"
                }

                response = requests.get(settings.routescan_api, params=params, timeout=10)
                data = response.json()

                if data.get("status") == "1":
                    results = data.get("result", [])
                    for tx in results:
                        # Scan topics directly instead of relying on ape's decoded event_name
                        topics = tx.get("topics", [])
                        if topics and topics[0].lower() == ORDER_CREATED_TOPIC.lower():
                            order_id = int(topics[1], 16)
                            buyer = "0x" + topics[2][-40:] # Extract last 40 chars for address
                            relayer_addr = "0x" + topics[3][-40:]
                            print(f"🎯 RAW MATCH: Found Order {order_id} for Buyer {buyer}")
                            print(f"📦 NEW ORDER: ID {order_id} | Buyer: {buyer}")

                            # 2. GENERATE & ENCRYPT PAYLOAD
                            raw_payload = f"API_KEY_{os.urandom(4).hex()}"
                            encrypted_stuff = encrypt_delivery_payload(raw_payload)

                            print(f"🔐 Encrypting delivery for Order {order_id}...")

                            try:
                                # 3. ATOMIC FULFILLMENT: Trigger the Vyper Handshake
                                # Arg 1: order_id
                                # Arg 2: spender_used (The SnowGate address used for settlement)
                                # Arg 3: encrypted_payload
                                print(f"📡 Sending fulfill_order tx for Order {order_id}...")

                                shop_contract.fulfill_order(
                                    order_id, 
                                    relayer_addr, 
                                    encrypted_stuff, 
                                    sender=merchant, 
                                    gas_limit=1000000 
                                )
                                print(f"✅ SUCCESS: Order {order_id} fulfilled and funds settled.")

                            except Exception as e:
                                print(f"❌ FULFILLMENT REVERTED: {e}")

                new_cursor = to_block - 10 

                # Ensure we never go backwards behind the absolute start
                if new_cursor < last_processed_block:
                    # If the range was small, just move forward slightly or stay put
                    new_cursor = to_block - 2 

                save_shop_state(shop_address, new_cursor)
                last_processed_block = new_cursor
                
                print(f"📍 Cursor held at: {new_cursor} (Buffered 5 blocks for indexer)")
            
        except Exception as e:
            print(f"⚠️ Agent Worker Heartbeat Error: {e}")
        
        await asyncio.sleep(SLEEP)