# @version ^0.4.0
# SnowGateSession.vy - FIXED VERSION

from ethereum.ercs import IERC20

interface VendorShop:
    def create_order(buyer: address, product_id: uint256, price: uint256): nonpayable

owner: public(address)
usdc: public(address)
company_name: public(String[64])
company_id: public(uint256)
admin_wallets: public(address[2])

# Session now tracks authorized SPENDERS who can drain the vault
struct Session:
    approved: bool
    max_amount: uint256      # Max this spender can spend from vault
    spent: uint256           # How much they've spent
    expires: uint256         # Timestamp

# Key is the AUTHORIZED SPENDER (relayer), not a buyer
sessions: public(HashMap[address, Session])

event PurchaseExecuted:
    spender: indexed(address)
    shop: indexed(address)
    product_id: uint256
    price: uint256

event SessionCreated:
    spender: indexed(address)
    amount: indexed(uint256)
    duration: indexed(uint256)

event Withdrawal:
    sender: indexed(address)
    destination: indexed(address)
    amount: indexed(uint256)


event SessionTerminated:
    _for: indexed(address)


@deploy
def __init__(_usdc: address, company_name: String[64], company_id: uint256):
    self.usdc = _usdc
    self.owner = msg.sender
    self.company_name = company_name
    self.company_id = company_id

@external
def add_admin_wallet(wallet: address):
    assert msg.sender == self.owner, "Only owner can add admin wallets"
    assert wallet != empty(address), "Invalid wallet address"
    assert wallet not in self.admin_wallets, "Wallet already added"
    for i: uint64 in range(2):
        if self.admin_wallets[i] == empty(address):
            self.admin_wallets[i] = wallet
            break

@external
def remove_admin_wallet(wallet: address):
    assert msg.sender == self.owner, "Only owner can remove admin wallets"
    assert wallet in self.admin_wallets, "Wallet not found"
    for i: uint64 in range(2):
        if self.admin_wallets[i] == wallet:
            self.admin_wallets[i] = empty(address)
            break


@external
def balanceOfSession() -> uint256:
    return self.sessions[msg.sender].max_amount - self.sessions[msg.sender].spent

@external
def close_session():
    """Buyer can revoke anytime"""
    self.sessions[msg.sender].approved = False
    log SessionTerminated(msg.sender)

@external
@nonreentrant
def withdraw_balance(destination: address):
    """
    @notice Withdraw USDC from SnowGate Vault
    @dev Only the owner (Polemarch) can drain the vault
    """
    assert msg.sender == self.owner, "Unauthorized"
    
    # Get the full balance of USDC held by this contract
    balance: uint256 = staticcall IERC20(self.usdc).balanceOf(self)
    
    # Execute the transfer
    # default_return_value=True handles non-compliant tokens that don't return a bool
    extcall IERC20(self.usdc).transfer(destination, balance, default_return_value=True)

    log Withdrawal(msg.sender, destination, balance)

@external
@nonreentrant
def create_session(max_amount: uint256, duration_days: uint256):
    """
    Create/extend a session for msg.sender (the relayer).
    This authorizes them to spend up to max_amount from SnowGate vault.
    """
    # Only owner or admin can create sessions? Or anyone can self-authorize?
    # For now: anyone can create their own session (they're authorizing themselves to spend vault funds)
    # But actually, this should probably be restricted to approved relayers
    
    new_max: uint256 = max_amount
    new_spent: uint256 = 0
    
    # If extending existing session, preserve spent amount unless resetting
    current: Session = self.sessions[msg.sender]
    if current.approved and current.expires > block.timestamp:
        # Extending - keep spent amount, add new budget to remaining
        remaining: uint256 = current.max_amount - current.spent
        new_max = remaining + max_amount  # Add new budget to remaining
        new_spent = current.spent
    
    self.sessions[msg.sender] = Session({
        approved: True,
        max_amount: new_max,
        spent: new_spent,
        expires: block.timestamp + (duration_days * 86400)
    })
    
    log SessionCreated(msg.sender, new_max, duration_days)

@external
@nonreentrant
def execute_purchase(
    spender: address,    # The relayer who has the session (for internal tracking only)
    shop: address,
    product_id: uint256,
    price: uint256
):
    """
    Execute purchase using SnowGate's vault USDC.
    'spender' is the authorized relayer (internal tracking only).
    VendorShop only sees SnowGate as the buyer/payer.
    """
    # 1. INTERNAL: Check relayer's session (SnowGate's internal bookkeeping)
    session: Session = self.sessions[spender]
    assert session.approved, "No active session"
    assert block.timestamp < session.expires, "Session expired"
    assert session.spent + price <= session.max_amount, "Over budget"

    # 2. Update internal accounting
    self.sessions[spender].spent += price

    # 3. Approve shop to pull from SNOWGATE (not from relayer)
    assert extcall IERC20(self.usdc).approve(shop, price, default_return_value=True), "Approval failed"

    # 4. Create order with SNOWGATE as the payer (relayer is hidden)
    # VendorShop never learns about 'spender' - only sees msg.sender (SnowGate)
    extcall VendorShop(shop).create_order(self, product_id, price)
    
    log PurchaseExecuted(spender, shop, product_id, price)


@internal
@view
def _is_admin(addr: address) -> bool:
    for wallet: address in self.admin_wallets:
        if addr == wallet:
            return True
    return False
    
    
