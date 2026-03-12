# @version ^0.4.0
# SPDX-License-Identifier: MIT

from ethereum.ercs import IERC20

interface IVendorShop:
    def create_order(buyer: address, product_id: uint256, price: uint256): nonpayable

# ============================================================================
# STRUCTS & EVENTS
# ============================================================================
struct Session:
    approved: bool
    max_amount: uint256    # The total credit limit for this session
    locked_escrow: uint256 # Funds reserved for active/pending orders
    settled_spent: uint256 # Actual finalized spending after delivery
    expires: uint256

event SessionCreated:
    spender: indexed(address)
    limit: uint256
    expiry: uint256

event PurchaseInitiated:
    spender: indexed(address)
    shop: indexed(address)
    amount: uint256

event SessionSettled:
    spender: indexed(address)
    amount: uint256

event SessionVoided:
    spender: indexed(address)
    amount: uint256

event SessionTerminated:
    _for: indexed(address)

event Withdrawal:
    sender: indexed(address)
    destination: indexed(address)
    amount: uint256

# ============================================================================
# STORAGE
# ============================================================================
owner: public(address)
usdc: public(address)
company_name: public(String[64])
company_id: public(uint256)
admin_wallet: public(HashMap[address, bool])
sessions: public(HashMap[address, Session])

# ============================================================================
# CONSTRUCTOR
# ============================================================================
@deploy
def __init__(_usdc: address, _name: String[64], _id: uint256):
    self.usdc = _usdc
    self.owner = msg.sender
    self.company_name = _name
    self.company_id = _id

# ============================================================================
# GUARD
# ============================================================================
@internal
@view
def _has_sufficient_balance(amount: uint256) -> bool:
    """Check if the contract itself holds enough USDC."""
    current_balance: uint256 = staticcall IERC20(self.usdc).balanceOf(self)
    return current_balance >= amount

@external
@view
def can_afford(amount: uint256) -> bool:
    """Public view for FastAPI to check liquidity before submittig TX."""
    return self._has_sufficient_balance(amount)

# ============================================================================
# SESSION MANAGEMENT
# ============================================================================
@external
def create_session(max_amount: uint256, duration_days: uint256):
    """Initializes or extends a spending session for the relayer/spender."""
    current: Session = self.sessions[msg.sender]
    new_expiry: uint256 = block.timestamp + (duration_days * 86400)
    
    # Preserve existing spent/locked metrics if extending
    self.sessions[msg.sender] = Session({
        approved: True,
        max_amount: max_amount,
        locked_escrow: current.locked_escrow,
        settled_spent: current.settled_spent,
        expires: new_expiry
    })
    
    log SessionCreated(msg.sender, max_amount, new_expiry)

@external
def close_session():
    """Spender or admin can revoke session immediately."""
    self.sessions[msg.sender].approved = False
    log SessionTerminated(msg.sender)

@external
@nonreentrant
def execute_purchase(spender: address, shop: address, product_id: uint256, price: uint256):
    """
    Called by the Relayer. Moves funds into Escrow (Locked state).
    Prevents 'Ghost Spending' by not finalizing until delivery.
    """
    session: Session = self.sessions[spender]
    
    assert session.approved, "No active session"
    assert block.timestamp < session.expires, "Session expired"

    # HARD GUARD: Revert early if the vault is empty
    assert self._has_sufficient_balance(price), "SnowGate: Insufficient USDC in vault"
    
    # Check if total allocation (Settled + Locked + Current Request) fits in budget
    assert (session.settled_spent + session.locked_escrow + price) <= session.max_amount, "Over total budget"

    # 1. Lock the funds internally
    self.sessions[spender].locked_escrow += price

    # 2. Grant allowance to the Shop (Shop pulls from SnowGate, not the relayer)
    assert extcall IERC20(self.usdc).approve(shop, price, default_return_value=True), "Approval failed"

    # 3. Create the order with SnowGate  as the payer
    extcall IVendorShop(shop).create_order(spender, product_id, price)
    
    log PurchaseInitiated(spender, shop, price)

# ============================================================================
# SETTLEMENT & REVERSION (STATE-AWARE LOGIC)
# ============================================================================
@external
def settle_session(spender: address, amount: uint256):
    """
    HANDSHAKE: Called by VendorShop upon successful fulfillment.
    Moves funds from 'locked_escrow' to 'settled_spent'.
    """

    session: Session = self.sessions[spender]
    assert session.locked_escrow >= amount, "SnowGate: Spender has no locked escrow to settle"

    self.sessions[spender].locked_escrow -= amount
    self.sessions[spender].settled_spent += amount
    log SessionSettled(spender, amount)

    
@external
def void_escrow(spender: address, amount: uint256):
    """
    REVERSION: Releases locked funds back to available budget if delivery fails.
    """
    assert msg.sender == self.owner or self._is_admin(msg.sender), "Unauthorized"
    
    session: Session = self.sessions[spender]
    assert session.locked_escrow >= amount, "Nothing to void"

    self.sessions[spender].locked_escrow -= amount
    log SessionVoided(spender, amount)

# ============================================================================
# ADMIN & VIEWS
# ============================================================================
@external
@view
def balanceOfSession(spender: address) -> uint256:
    """Returns true available budget (Max - [Settled + Locked])"""
    session: Session = self.sessions[spender]
    return session.max_amount - (session.settled_spent + session.locked_escrow)

@external
def add_admin_wallet(wallet: address):
    assert msg.sender == self.owner, "Only owner"
    assert not self.admin_wallet[wallet], 'Already an Admin' 
    self.admin_wallet[wallet] = True

@external
def remove_admin_wallet(wallet: address):
    assert msg.sender == self.owner, "Only owner"
    assert self.admin_wallet[wallet], 'Not an Admin' 
    self.admin_wallet[wallet] = False

@internal
@view
def _is_admin(addr: address) -> bool:
    return self.admin_wallet[addr]

@external
@nonreentrant
def withdraw_vault(destination: address):
    """Owner drain for corporate re-allocation."""
    assert msg.sender == self.owner, "Unauthorized"
    balance: uint256 = staticcall IERC20(self.usdc).balanceOf(self)
    extcall IERC20(self.usdc).transfer(destination, balance, default_return_value=True)
    log Withdrawal(msg.sender, destination, balance)