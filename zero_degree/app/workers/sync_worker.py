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
    print(f"🤖 Agent Bot Online: Monitoring Orders for Shop @ {shop_address}")
    
    merchant = accounts.load("alt_user")
    merchant.set_autosign(True, passphrase=settings.agent_pass)
    shop_contract = Contract(shop_address)

    while True:
        try:
            # 1. RE-SYNC STATE ON EVERY LOOP
            # This ensures that if the worker restarts, it knows exactly where it left off.
            state = load_shop_state(shop_address)
            last_processed_block = state.get("last_synced_block") or start_block()

            with networks.parse_network_choice(settings.network_string):
                # 2. GET ACTUAL CHAIN HEAD
                current_head = networks.active_provider.get_block("latest").number
                
                # Use a 3-block safety buffer to allow RPC indexing to catch up
                # This prevents "Missing latest block" and "extraData" errors
                safe_target = current_head - 3

                if last_processed_block >= safe_target:
                    # Already caught up to the safe head, wait for new blocks
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
                    "apikey": "rs_1dfb052e4d7d981e0d29286e" 
                }

                # Add a timeout to the request to avoid hanging the loop
                response = requests.get(settings.routescan_api, params=params, timeout=10)
                data = response.json()

                if data.get("status") == "1":
                    results = data.get("result", [])
                    for tx in results:
                        # Parse block number safely
                        tx_block = int(tx['blockNumber'], 16 if '0x' in tx['blockNumber'] else 10)
                        
                        # Guard against re-processing logs in the same range
                        if tx_block <= last_processed_block:
                            continue

                        receipt = networks.active_provider.get_receipt(tx['transactionHash'])
                        # block_timestamp = networks.active_provider.get_block(receipt.block_number).timestamp
                        
                        if receipt.status == 1:
                            for event in receipt.events:
                                if event.event_name == "OrderCreated":
                                    # if event.event_arguments.get("expires") < block_timestamp:
                                    #     print(f"⚠️ Order {order_id} EXPIRED. Initiating SnowGate reversal...")
                                    #     pass

                                    order_id = event.event_arguments.get("order_id")
                                    print(f"📦 NEW ORDER DETECTED: ID {order_id}")

                                    # Generate and Encrypt Payload
                                    raw_payload = f"KEY_{os.urandom(4).hex()}"
                                    encrypted_stuff = encrypt_delivery_payload(raw_payload)

                                    try:
                                        # 3. ATOMIC FULFILLMENT
                                        # We use an explicit gas_limit to bypass estimation issues on Avalanche
                                        shop_contract.fulfill_order(
                                            order_id, 
                                            encrypted_stuff, 
                                            sender=merchant, 
                                            gas_limit=1000000
                                        )
                                        print(f"✅ SUCCESS: Order {order_id} settled on-chain.")
                                    except Exception as e:
                                        print(f"❌ FULFILLMENT REVERTED: {e}")

                        # Update local cursor and persistent state per log found
                        last_processed_block = tx_block - 6
                        save_shop_state(shop_address, last_processed_block)
                
                # 4. ADVANCE CURSOR TO THE END OF THE SCANNED RANGE
                # Even if no logs were found, we move to to_block so we don't scan it again.
                last_processed_block = to_block
                save_shop_state(shop_address, last_processed_block)
            
        except Exception as e:
            print(f"⚠️ Agent Worker Heartbeat Error: {e}")
            # Standard sleep before retry on error
        
        await asyncio.sleep(SLEEP)