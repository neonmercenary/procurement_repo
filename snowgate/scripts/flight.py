from app.settings import settings
from ape import project, networks, Contract
from ape.contracts import ContractInstance
from ethpm_types import ContractType
from ape.utils import to_checksum_address  # OR: from eth_utils import to_checksum_address

def make_contract(address, abi_list, name="Unknown"):
    """Create a contract instance without any explorer lookups."""
    # Ensure checksum address
    checksum_addr = to_checksum_address(address)
    contract_type = ContractType(abi=abi_list, contractName=name)
    return ContractInstance(checksum_addr, contract_type)

def main():
    with networks.parse_network_choice(settings.network_string):
        sg = Contract(settings.snowgate_address)
        reg = Contract(settings.zero_degree_registry_address)
        shop = Contract(settings.vendor_shop_address)
        
        USDC_ABI = [
            {
                "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "spender", "type": "address"},
                    {"internalType": "uint256", "name": "amount", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "decimals",
                "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
        
        # Pass the raw address, make_contract will checksum it
        usdc = make_contract(settings.usdc_address, USDC_ABI, "USDC")

        print(f"--- 🔎 POLEMARCH DEEP AUDIT ---")
        
        # 1. USDC Check
        bal = usdc.balanceOf(sg.address)
        print(f"💰 Vault Balance: {bal / 1e6} USDC")
        if bal == 0:
            print("❌ FAIL: SnowGate Contract has NO USDC. It cannot 'approve' the shop.")

        # 2. Moderator Check (THE MOST LIKELY FIX)
        is_mod = reg.is_moderator(sg.address)
        print(f"🛡️ Is SnowGate ({sg.address}) a Moderator? {is_mod}")
        if not is_mod:
            print("❌ FAIL: VendorShop will REVERT because SnowGate is not an authorized Moderator.")

        # 3. Registry Merchant Check
        can_sell = reg.can_merchant_sell(24) # Assuming Vendor 24
        print(f"🏪 Can Merchant 24 Sell? {can_sell}")
        
        # 4. Merchant Lock Check
        is_busy = shop.is_merchant_busy()
        print(f"🔒 Is Merchant Busy (Locked)? {is_busy}")
        if is_busy:
            print("❌ FAIL: Merchant is already in a transaction. Clear the order first.")

if __name__ == "__main__":
    main()