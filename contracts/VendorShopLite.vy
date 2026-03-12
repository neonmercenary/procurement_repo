# @version ^0.4.0
# SPDX-License-Identifier: MIT
# Vendorshop.vy

# --- Interfaces ---
interface IERC20:
    def transferFrom(_from: address, _to: address, _value: uint256) -> bool: nonpayable
    def transfer(_to: address, _value: uint256) -> bool: nonpayable
    def balanceOf(_account: address) -> uint256: view

interface IZeroDegreeRegistry:
    def can_merchant_sell(agentId: uint256) -> bool: view
    def ownerOf(tokenId: uint256) -> address: view
    def is_moderator(sender: address) -> bool: view

interface ISnowGate:
    def settle_session(spender: address, amount: uint256): nonpayable

# --- Structs ---
struct Product:
    price: uint256
    item_name: String[64]
    delivery_type: uint8
    is_active: bool

struct Order:
    buyer: address         # SnowGate
    relayer_used: address  # Internal SNOWGATE ACCOUNTING
    product_id: uint256
    price: uint256
    expires: uint256
    is_completed: bool


# General
registry: public(address)
payment_token: public(address)
merchant_id: public(uint256)
owner: public(address)
delivered: public(HashMap[uint256, address])  # productID → Address
created_at_block: public(uint256)

# CONSTANTS
MAX_BATCH_SIZE: constant(uint256) = 50
MAX_PRODUCTS: constant(uint256) = 1000

# Products
products: public(HashMap[uint256, Product])
active_product_ids: DynArray[uint256, MAX_PRODUCTS]
is_id_active: HashMap[uint256, bool]
next_product_id: uint256

# Orders
orders: public(HashMap[uint256, Order])
next_order_id: public(uint256)

# 1:1 Sale GuardRail, MVP Style
is_order_active: public(bool)


# --- Events ---
event EarningsWithdrawn:
    sender: indexed(address)
    amount: indexed(uint256)

event ProductListed:
    productId: indexed(uint256)
    price: uint256
    item_name: String[64]

event Purchased:
    productId: indexed(uint256)
    buyer: indexed(address)
    seller: indexed(address)  # Buyer Agent ID
    price: uint256

event OrderCreated:
    order_id: indexed(uint256)
    buyer: indexed(address)
    relayer: indexed(address)
    product_id: uint256

event OrderCompleted:
    buyer: indexed(address)     
    merchant: indexed(address)
    order_id: indexed(uint256)
    payload: String[1024]            # The "Good" (API Key, URL, or Hash)

@deploy
def __init__(_registry: address, _payment_token: address, _merchant_id: uint256):
    self.registry = _registry
    self.payment_token = _payment_token
    self.merchant_id = _merchant_id
    self.created_at_block = block.number
    self.owner = msg.sender
    self.next_product_id = 1


# ===========================
#  withdraw earnings
# ===========================
@external
@nonreentrant
def withdraw_earnings(amount: uint256):
    # SECURITY: Only the Merchant (Owner) can withdraw
    assert msg.sender == self.owner, "Only Merchant can withdraw"
    
    # Check balance (just in case)
    current_balance: uint256 = staticcall IERC20(self.payment_token).balanceOf(self)
    assert amount <= current_balance, "Insufficient earnings balance"

    # Move the USDC to the Merchant's wallet
    assert extcall IERC20(self.payment_token).transfer(
        self.owner, 
        amount, 
        default_return_value=True
    ), "Withdrawal transfer failed"

    log EarningsWithdrawn(self.owner, amount)


@external
def set_active(product_id: uint256, status: bool):
    assert msg.sender == self.owner, "Only owner"
    
    if self.products[product_id].is_active != status:
        self.products[product_id].is_active = status
        
        if status:
            if not self.is_id_active[product_id]:
                self.active_product_ids.append(product_id)
                self.is_id_active[product_id] = True
        else:
            self.is_id_active[product_id] = False


# ===========================
#   Orders
# ===========================
@external
def create_order(relayer: address, p_id: uint256, price: uint256):
    """
    Create order. 'buyer' is the payer (SnowGate).
    """
    
    assert staticcall IZeroDegreeRegistry(self.registry).can_merchant_sell(self.merchant_id), "Merchant Offline"
    
    # 2. 1:1 Enforcement (Local to this shop)
    # assert not self.is_order_active, "Order in progress"

    order_id: uint256 = self.next_order_id
    self.orders[order_id] = Order({
        buyer: msg.sender, # SnowGate
        relayer_used: relayer,
        product_id: p_id,
        price: price,
        expires: block.timestamp + 3600,
        is_completed: False
    })
    
    self.next_order_id += 1
    self.is_order_active = True     # Lock the merchant from transacting till order done or reversals etc
    log OrderCreated(order_id, msg.sender, relayer, p_id)



@nonreentrant
@external
def fulfill_order(order_id: uint256, spender_used: address, encrypted_payload: String[1024]):
    """
    Finalizes the trade. 
    1. Pulls USDC from SnowGate Vault.
    2. Signals SnowGate to move budget from 'Locked' to 'Settled'.
    3. Emits delivery event with payload for the Agent.
    """
    assert msg.sender == self.owner, "Only Merchant can fulfill"
    
    order: Order = self.orders[order_id]
    assert not order.is_completed, "Already fulfilled"
    assert block.timestamp <= order.expires, "Order expired"

    # 1. PULL PAYMENT: VendorShop triggers the allowance granted during execute_purchase
    success: bool = extcall IERC20(self.payment_token).transferFrom(
        order.buyer, # This is the SnowGate Contract address
        self, 
        order.price, 
        default_return_value=True
    )
    assert success, "Payment Collection failed"

    # 2. STATE HANDSHAKE: Notify SnowGate that the 'Locked' funds are now 'Settled'
    # This prevents the "Ghost Spending" in the SAP/ERP system.
    extcall ISnowGate(order.buyer).settle_session(order.relayer_used, order.price)

    # 3. Finalize Local State
    self.orders[order_id].is_completed = True
    self.is_order_active = False # Free the merchant for the next transaction
    
    log OrderCompleted(order.buyer, self.owner, order_id, encrypted_payload)

#===========================
# Product
#===========================
@external
@nonreentrant
def list_product(_price: uint256, _item_name: String[64], _type: uint8):
    """
    Lists a new product in the VendorShop.
    The item_name should match the SAP/ERP Line Item description.
    """
    assert msg.sender == self.owner, "Only owner"
    # assert staticcall IZeroDegreeRegistry(self.registry).can_merchant_sell(self.merchant_id), "Merchant not eligible"
    
    p_id: uint256 = self.next_product_id
    
    self.products[p_id] = Product(
        price=_price,
        item_name=_item_name,
        delivery_type=_type,
        is_active=True
    )
    
    self.active_product_ids.append(p_id)
    self.is_id_active[p_id] = True
    
    self.next_product_id += 1
    log ProductListed(p_id, _price, _item_name)


@external
@view
def get_product(product_id: uint256) -> Product:
    p: Product = self.products[product_id]
    # CROSS-CHECK: If the merchant isn't compliant, the product doesn't exist.
    is_valid: bool = staticcall IZeroDegreeRegistry(self.registry).can_merchant_sell(self.merchant_id)
    assert is_valid, "Merchant not in Zero Degree or Under-collateralized"
    return p

    
# Misc
@external
def cleanup_inactive_ids():
    assert msg.sender == self.owner, "Only owner"
    
    new_array: DynArray[uint256, MAX_PRODUCTS] = empty(DynArray[uint256, MAX_PRODUCTS])
    
    for i: uint256 in range(MAX_PRODUCTS):
        if i >= len(self.active_product_ids):
            break
        pid: uint256 = self.active_product_ids[i]
        if self.is_id_active[pid]:
            new_array.append(pid)
    
    self.active_product_ids = new_array

# --- Gas Optimized View Functions ---
@external
@view
def is_merchant_busy() -> bool:
    """
    Checks if the merchant has an active, unfulfilled order that hasn't expired.
    """
    # Check the most recent order
    if self.next_order_id == 0:
        return False
        
    last_order: Order = self.orders[self.next_order_id - 1]
    
    # Busy if: Not completed AND not yet expired
    if not last_order.is_completed and block.timestamp <= last_order.expires:
        return True
        
    return False

@external
@view
def get_products(_start_id: uint256, _count: uint256) -> DynArray[Product, MAX_BATCH_SIZE]:
    count: uint256 = _count
    if count > MAX_BATCH_SIZE:
        count = MAX_BATCH_SIZE
    
    result: DynArray[Product, MAX_BATCH_SIZE] = empty(DynArray[Product, MAX_BATCH_SIZE])
    
    end: uint256 = _start_id + count
    if end > self.next_product_id:
        end = self.next_product_id
    
    for i: uint256 in range(MAX_BATCH_SIZE):
        if _start_id + i >= end:
            break
        result.append(self.products[_start_id + i])
    
    return result

@external
@view
def get_active_products(_offset: uint256, _count: uint256) -> (DynArray[Product, MAX_BATCH_SIZE], DynArray[uint256, MAX_BATCH_SIZE]):
    count: uint256 = _count
    if count > MAX_BATCH_SIZE:
        count = MAX_BATCH_SIZE
    
    products_result: DynArray[Product, MAX_BATCH_SIZE] = empty(DynArray[Product, MAX_BATCH_SIZE])
    ids_result: DynArray[uint256, MAX_BATCH_SIZE] = empty(DynArray[uint256, MAX_BATCH_SIZE])
    
    total_active: uint256 = len(self.active_product_ids)
    if _offset >= total_active:
        return (products_result, ids_result)
    
    added: uint256 = 0
    
    for i: uint256 in range(MAX_PRODUCTS):
        if added >= count:
            break
        if _offset + i >= total_active:
            break
            
        pid: uint256 = self.active_product_ids[_offset + i]
        
        if not self.is_id_active[pid]:
            continue
        
        products_result.append(self.products[pid])
        ids_result.append(pid)
        added += 1
    
    return (products_result, ids_result)

@external
@view
def get_all_active_ids() -> DynArray[uint256, 100]:
    result: DynArray[uint256, 100] = empty(DynArray[uint256, 100])
    
    for i: uint256 in range(MAX_PRODUCTS):
        if len(result) >= 100:
            break
        if i >= len(self.active_product_ids):
            break
        pid: uint256 = self.active_product_ids[i]
        if self.is_id_active[pid]:
            result.append(pid)
    
    return result
