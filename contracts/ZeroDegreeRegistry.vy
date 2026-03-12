# @version ^0.4.0
# SPDX-License-Identifier: MIT
# ZeroDegreeRegistry.vy

# ============================================================================
# ERC interfaces
# ============================================================================
interface ERC8004:
    def ownerOf(tokenId: uint256) -> address: view

interface ERC20:
    def transferFrom(sender: address, receiver: address, amount: uint256) -> bool: nonpayable
    def transfer(receiver: address, amount: uint256) -> bool: nonpayable


# ============================================================================
# Constants & Events
# ============================================================================
MAX_TAG_COUNT: constant(uint256) = 3
MAX_TAG_LEN: constant(uint256) = 32
DEFAULT_SPENDING_CAP: constant(uint256) = 10 * 10 ** 6


event AdminUpdated:
    old_admin: indexed(address)
    new_admin: indexed(address)

event AgentRegistered:
    agent_id: indexed(uint256)
    owner: indexed(address)

event MerchantRegistered:
    agent_id: indexed(uint256)
    tags: DynArray[String[MAX_TAG_LEN], MAX_TAG_COUNT]

event MinimumStakeUpdated:
    old_amount: uint256
    new_amount: uint256

event ModeratorAdded:
    new_mod: indexed(address)

event TagsUpdated:
    agent_id: indexed(uint256)
    tags: DynArray[String[MAX_TAG_LEN], MAX_TAG_COUNT]

event MerchantBanned:
    agent_id: indexed(uint256)

event MerchantUnbanned:
    agent_id: indexed(uint256)

event MerchantBusy:
    agent_id: indexed(uint256)

event MerchantFree:
    agent_id: indexed(uint256)

event StakeDeposited:
    agent_id: indexed(uint256)
    amount: uint256

event StakeSlashed:
    agent_id: indexed(uint256)
    amount: uint256

event StakeWithdrawn:
    agent_id: indexed(uint256)
    amount: uint256
    recipient: indexed(address)

event ShopLinked:
    agent_id: indexed(uint256)
    shop_address: indexed(address)

# ============================================================================
# Storage
# ============================================================================

owner_of: public(HashMap[uint256, address])
is_merchant: public(HashMap[uint256, bool])
is_banned: public(HashMap[uint256, bool])
stake: public(HashMap[uint256, uint256])
shop_address: public(HashMap[uint256, address])
merchant_tags: public(HashMap[uint256, DynArray[String[MAX_TAG_LEN], MAX_TAG_COUNT]])
tx_spending_cap: public(HashMap[uint256, uint256])

# Config
minimum_stake: public(uint256)
admin: public(address)
is_moderator: public(HashMap[address, bool])
usdc_token: public(address)
identity_registry: public(address)
merchant_active: public(HashMap[uint256, bool])


# ============================================================================
# Constructor
# ============================================================================

@deploy
def __init__(usdc_token: address, identity_registry: address):
    self.admin = msg.sender
    self.usdc_token = usdc_token
    self.identity_registry = identity_registry
    self.minimum_stake = 1 * 10**6  # 1 USDC

# ============================================================================
# Merchant Lifecycle
# ============================================================================

@external
def register_agent(agent_id: uint256):
    """Mirror identity from ERC-8004."""
    actual_owner: address = staticcall ERC8004(self.identity_registry).ownerOf(agent_id)
    assert msg.sender == actual_owner, "Not the ERC-8004 owner"
    assert self.owner_of[agent_id] == empty(address), "Agent already mirrored"

    self.owner_of[agent_id] = msg.sender
    log AgentRegistered(agent_id, msg.sender)


@external
def register_merchant(agent_id: uint256, tags: DynArray[String[MAX_TAG_LEN], MAX_TAG_COUNT]):
    """Transition mirrored agent to merchant with tags."""
    assert self.owner_of[agent_id] == msg.sender, "Only owner"
    assert not self.is_merchant[agent_id], "Already merchant"
    assert len(tags) <= MAX_TAG_COUNT, "Too many tags"
    
    # Validate tag lengths
    for tag: String[MAX_TAG_LEN] in tags:
        assert len(tag) <= MAX_TAG_LEN, "Tag too long"
        assert len(tag) > 0, "Empty tag not allowed"
    
    self.is_merchant[agent_id] = True
    self.merchant_active[agent_id] = True  # ✅ ADD THIS LINE
    self.merchant_tags[agent_id] = tags
    self.tx_spending_cap[agent_id] = DEFAULT_SPENDING_CAP
    
    log MerchantRegistered(agent_id, tags)

@external
def update_tags(agent_id: uint256, tags: DynArray[String[MAX_TAG_LEN], MAX_TAG_COUNT]):
    """Update metadata tags after registration."""
    assert self.owner_of[agent_id] == msg.sender, "Only owner"
    assert self.is_merchant[agent_id], "Not a merchant"
    assert len(tags) <= MAX_TAG_COUNT, "Too many tags"
    
    # Validate tag lengths
    for tag: String[MAX_TAG_LEN] in tags:
        assert len(tag) <= MAX_TAG_LEN, "Tag too long"
        assert len(tag) > 0, "Empty tag not allowed"
    
    self.merchant_tags[agent_id] = tags
    self.merchant_active[agent_id] = True
    log TagsUpdated(agent_id, tags)

# ============================================================================
# Economics & Shop Management
# ============================================================================

@external
@nonreentrant
def deposit_stake(agent_id: uint256, amount: uint256):
    assert self.owner_of[agent_id] == msg.sender, "Only owner"
    extcall ERC20(self.usdc_token).transferFrom(msg.sender, self, amount)
    self.stake[agent_id] += amount
    self.is_merchant[agent_id] = True
    log StakeDeposited(agent_id, amount)

@external
@nonreentrant
def withdraw_stake(agent_id: uint256, amount: uint256):
    """Withdraw USDC stake. Cannot withdraw below minimum if still merchant."""
    assert self.owner_of[agent_id] == msg.sender, "Only owner"
    assert self.stake[agent_id] >= amount, "Insufficient stake"
    
    # If withdrawing as active merchant, must maintain minimum or withdraw all
    if self.is_merchant[agent_id] and not self.is_banned[agent_id]:
        remaining: uint256 = self.stake[agent_id] - amount
        assert remaining >= self.minimum_stake or remaining == 0, "Would drop below minimum stake"
    
    self.stake[agent_id] -= amount
    extcall ERC20(self.usdc_token).transfer(msg.sender, amount)
    log StakeWithdrawn(agent_id, amount, msg.sender)

@external
def link_shop(agent_id: uint256, shop_address: address):
    assert self.owner_of[agent_id] == msg.sender, "Only owner"
    assert self.is_merchant[agent_id], "Not a merchant"
    self.shop_address[agent_id] = shop_address
    log ShopLinked(agent_id, shop_address)

# ============================================================================
# View Functions
# ============================================================================
@external
@view
def can_merchant_sell(agent_id: uint256) -> bool:
    return (
        self.is_merchant[agent_id] 
        and self.merchant_active[agent_id]
        and not self.is_banned[agent_id] 
        and self.stake[agent_id] >= self.minimum_stake
    )

@view
@external
def get_tags(agent_id: uint256) -> DynArray[String[MAX_TAG_LEN], MAX_TAG_COUNT]:
    return self.merchant_tags[agent_id]

# ============================================================================
# Admin Config
# ============================================================================
@external
def add_moderator(mod: address):
    assert msg.sender == self.admin, "Admin only"
    self.is_moderator[mod] = True


@external
def toggle_merchant_status(vendor_id: uint256, status: bool):
    """Admin or Moderator flips the 'Open/Closed' sign for a merchant."""
    assert msg.sender == self.admin or self.is_moderator[msg.sender], "Unauthorized"
    self.merchant_active[vendor_id] = status

@external
def set_minimum_stake(amount: uint256):
    assert msg.sender == self.admin, "Only admin"
    log MinimumStakeUpdated(self.minimum_stake, amount)
    self.minimum_stake = amount

@external
def ban_merchant(agent_id: uint256):
    assert msg.sender == self.admin, "Only admin"
    self.is_banned[agent_id] = True
    log MerchantBanned(agent_id)

@external
def unban_merchant(agent_id: uint256):
    assert msg.sender == self.admin, "Only admin"
    self.is_banned[agent_id] = False
    log MerchantUnbanned(agent_id)

@external
@nonreentrant
def slash_merchant(agent_id: uint256, amount: uint256):
    assert msg.sender == self.admin, "Only admin"
    assert self.stake[agent_id] >= amount, "Insufficient stake"
    self.stake[agent_id] -= amount
    extcall ERC20(self.usdc_token).transfer(self.admin, amount)
    log StakeSlashed(agent_id, amount)