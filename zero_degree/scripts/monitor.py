ABI = [
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "name": "sender",
                            "type": "address"
                        },
                        {
                            "indexed": True,
                            "name": "amount",
                            "type": "uint256"
                        }
                    ],
                    "name": "EarningsWithdrawn",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "name": "productId",
                            "type": "uint256"
                        },
                        {
                            "indexed": False,
                            "name": "price",
                            "type": "uint256"
                        },
                        {
                            "indexed": False,
                            "name": "item_name",
                            "type": "string"
                        }
                    ],
                    "name": "ProductListed",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "name": "productId",
                            "type": "uint256"
                        },
                        {
                            "indexed": True,
                            "name": "buyer",
                            "type": "address"
                        },
                        {
                            "indexed": True,
                            "name": "seller",
                            "type": "address"
                        },
                        {
                            "indexed": False,
                            "name": "price",
                            "type": "uint256"
                        }
                    ],
                    "name": "Purchased",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "name": "order_id",
                            "type": "uint256"
                        },
                        {
                            "indexed": True,
                            "name": "buyer",
                            "type": "address"
                        },
                        {
                            "indexed": True,
                            "name": "product_id",
                            "type": "uint256"
                        }
                    ],
                    "name": "OrderCreated",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "name": "buyer",
                            "type": "address"
                        },
                        {
                            "indexed": True,
                            "name": "merchant",
                            "type": "address"
                        },
                        {
                            "indexed": True,
                            "name": "merchant_id",
                            "type": "uint256"
                        },
                        {
                            "indexed": False,
                            "name": "payload",
                            "type": "string"
                        }
                    ],
                    "name": "ProductDelivered",
                    "type": "event"
                },
                {
                    "inputs": [
                        {
                            "name": "amount",
                            "type": "uint256"
                        }
                    ],
                    "name": "withdraw_earnings",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "name": "product_id",
                            "type": "uint256"
                        },
                        {
                            "name": "status",
                            "type": "bool"
                        }
                    ],
                    "name": "set_active",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "name": "buyer",
                            "type": "address"
                        },
                        {
                            "name": "p_id",
                            "type": "uint256"
                        },
                        {
                            "name": "price",
                            "type": "uint256"
                        }
                    ],
                    "name": "create_order",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "name": "order_id",
                            "type": "uint256"
                        },
                        {
                            "name": "encrypted_payload",
                            "type": "string"
                        }
                    ],
                    "name": "fulfill_order",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "name": "_price",
                            "type": "uint256"
                        },
                        {
                            "name": "_item_name",
                            "type": "string"
                        },
                        {
                            "name": "_type",
                            "type": "uint8"
                        }
                    ],
                    "name": "list_product",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "name": "product_id",
                            "type": "uint256"
                        }
                    ],
                    "name": "get_product",
                    "outputs": [
                        {
                            "components": [
                                {
                                    "name": "price",
                                    "type": "uint256"
                                },
                                {
                                    "name": "item_name",
                                    "type": "string"
                                },
                                {
                                    "name": "delivery_type",
                                    "type": "uint8"
                                },
                                {
                                    "name": "is_active",
                                    "type": "bool"
                                }
                            ],
                            "name": "",
                            "type": "tuple"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [],
                    "name": "cleanup_inactive_ids",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [],
                    "name": "is_merchant_busy",
                    "outputs": [
                        {
                            "name": "",
                            "type": "bool"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "name": "_start_id",
                            "type": "uint256"
                        },
                        {
                            "name": "_count",
                            "type": "uint256"
                        }
                    ],
                    "name": "get_products",
                    "outputs": [
                        {
                            "components": [
                                {
                                    "name": "price",
                                    "type": "uint256"
                                },
                                {
                                    "name": "item_name",
                                    "type": "string"
                                },
                                {
                                    "name": "delivery_type",
                                    "type": "uint8"
                                },
                                {
                                    "name": "is_active",
                                    "type": "bool"
                                }
                            ],
                            "name": "",
                            "type": "tuple[]"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "name": "_offset",
                            "type": "uint256"
                        },
                        {
                            "name": "_count",
                            "type": "uint256"
                        }
                    ],
                    "name": "get_active_products",
                    "outputs": [
                        {
                            "components": [
                                {
                                    "name": "price",
                                    "type": "uint256"
                                },
                                {
                                    "name": "item_name",
                                    "type": "string"
                                },
                                {
                                    "name": "delivery_type",
                                    "type": "uint8"
                                },
                                {
                                    "name": "is_active",
                                    "type": "bool"
                                }
                            ],
                            "name": "",
                            "type": "tuple[]"
                        },
                        {
                            "name": "",
                            "type": "uint256[]"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [],
                    "name": "get_all_active_ids",
                    "outputs": [
                        {
                            "name": "",
                            "type": "uint256[]"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [],
                    "name": "registry",
                    "outputs": [
                        {
                            "name": "",
                            "type": "address"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [],
                    "name": "payment_token",
                    "outputs": [
                        {
                            "name": "",
                            "type": "address"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [],
                    "name": "merchant_id",
                    "outputs": [
                        {
                            "name": "",
                            "type": "uint256"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [],
                    "name": "owner",
                    "outputs": [
                        {
                            "name": "",
                            "type": "address"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "name": "arg0",
                            "type": "uint256"
                        }
                    ],
                    "name": "delivered",
                    "outputs": [
                        {
                            "name": "",
                            "type": "address"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [],
                    "name": "created_at_block",
                    "outputs": [
                        {
                            "name": "",
                            "type": "uint256"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "name": "arg0",
                            "type": "uint256"
                        }
                    ],
                    "name": "products",
                    "outputs": [
                        {
                            "components": [
                                {
                                    "name": "price",
                                    "type": "uint256"
                                },
                                {
                                    "name": "item_name",
                                    "type": "string"
                                },
                                {
                                    "name": "delivery_type",
                                    "type": "uint8"
                                },
                                {
                                    "name": "is_active",
                                    "type": "bool"
                                }
                            ],
                            "name": "",
                            "type": "tuple"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "name": "arg0",
                            "type": "uint256"
                        }
                    ],
                    "name": "orders",
                    "outputs": [
                        {
                            "components": [
                                {
                                    "name": "buyer",
                                    "type": "address"
                                },
                                {
                                    "name": "product_id",
                                    "type": "uint256"
                                },
                                {
                                    "name": "price",
                                    "type": "uint256"
                                },
                                {
                                    "name": "is_completed",
                                    "type": "bool"
                                },
                                {
                                    "name": "expires",
                                    "type": "uint256"
                                }
                            ],
                            "name": "",
                            "type": "tuple"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [],
                    "name": "next_order_id",
                    "outputs": [
                        {
                            "name": "",
                            "type": "uint256"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [],
                    "name": "is_order_active",
                    "outputs": [
                        {
                            "name": "",
                            "type": "bool"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "name": "_registry",
                            "type": "address"
                        },
                        {
                            "name": "_payment_token",
                            "type": "address"
                        },
                        {
                            "name": "_merchant_id",
                            "type": "uint256"
                        }
                    ],
                    "stateMutability": "nonpayable",
                    "type": "constructor"
                }
            ]


import time
from web3 import Web3
from eth_account import Account

# 1. SETUP
RPC_URL = "https://api.avax-test.network/ext/bc/C/rpc"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Load your PK directly for the sprint (Keep it in .env)
PRIVATE_KEY = "YOUR_AGENT_PRIVATE_KEY"
agent = Account.from_key(PRIVATE_KEY)

# Contract Config
SHOP_ADDRESS = "0x87254613A0AFa45A78eEF2aF294ba6b50EDb783b"
# Paste your VendorShopLite ABI here (Copy from .build/VendorShopLite.json)
SHOP_ABI = ABI

shop_contract = w3.eth.contract(address=SHOP_ADDRESS, abi=SHOP_ABI)

def monitor_and_fulfill(start_block):
    last_block = start_block
    print(f"🚀 Web3 Agent Online. Scanning from {last_block}...")

    while True:
        try:
            current_block = w3.eth.block_number
            if last_block >= current_block:
                time.sleep(5)
                continue

            # Get logs directly from the node
            logs = shop_contract.events.OrderCreated().get_logs(fromBlock=last_block + 1, toBlock=current_block)

            for log in logs:
                order_id = log.args.order_id
                print(f"🎯 Order Detected: {order_id}. Signing fulfillment...")
                
                # Build Transaction
                tx = shop_contract.functions.fulfill_order(
                    order_id, 
                    f"SIG_OK_{order_id}"
                ).build_transaction({
                    'from': agent.address,
                    'nonce': w3.eth.get_transaction_count(agent.address),
                    'gas': 500000,
                    'gasPrice': w3.eth.gas_price
                })

                # Sign and Send
                signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                print(f"✅ Fulfillment Sent: {tx_hash.hex()}")

            last_block = current_block
        except Exception as e:
            print(f"⚠️ Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    monitor_and_fulfill(52534311) # Use the current block from your logs