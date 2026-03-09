# @version ^0.4.0
# SPDX-License-Identifier: MIT
# SnowGate.vy

interface ERC20:
    def approve(spender: address, amount: uint256) -> bool: nonpayable

interface VendorShop:
    def purchase(product_id: uint256, buyer_agent_id: uint256): nonpayable

event SnowGatePurchase:
    shop: indexed(address)
    product_id: indexed(uint256)
    buyer_agent_id: uint256

owner: public(address)
usdc: public(address)

@deploy
def __init__(_payment_token: address):
    self.usdc = _payment_token
    self.owner = msg.sender

@external
def execute_purchase(
    shop: address,
    product_id: uint256,
    buyer_agent_id: uint256,
    price: uint256
):
    """
    SnowGate agent action:
    1. Approve USDC (if not already approved)
    2. Call VendorShop.purchase
    """
    assert msg.sender == self.owner, "Only owner"

    # Approve VendorShop to pull funds from this contract
    success: bool = extcall ERC20(self.usdc).approve(shop, price)
    assert success, "Approve failed"

    # Execute purchase
    extcall VendorShop(shop).purchase(product_id, buyer_agent_id)

    log SnowGatePurchase(shop, product_id, buyer_agent_id)