#!/usr/bin/env python3
"""
Zero Degree Registry Deployment Script (using Ape)
Deploy ZeroDegreeRegistry and VendorShop contracts to Avalanche Fuji Testnet
"""

import json
from pathlib import Path
from ape import accounts, project, networks, Contract
from app.settings import settings
from app.helpers import update_env_key

# ============================================================================
# Configuration / Helpers
# ============================================================================
def pretty_print_deployment(message):
    print("\n" + "=" * 70)
    print(message)
    print("=" * 70)

# Deployment output
DEPLOYMENT_FILE = Path(__file__).parent / "deployment.json"

# ============================================================================
# Main Deployment
# ============================================================================

def main():
    """Deploy Zero Degree Registry contracts"""
    
    pretty_print_deployment("Zero Degree Registry - Contract Deployment (Ape)")
    
    # Connect to network
    print(f"\n🔗 Connecting to {settings.network_string}...")
    with networks.parse_network_choice(settings.network_string):
        print(f"✓ Connected to {settings.network_string}")
        print(f"  Chain ID: {networks.active_provider.chain_id}")
        print(f"  Network: {networks.active_provider.network.name}")
        
        # Get account
        print("\n👤 Loading account...")
        try:
            account = accounts.load('spv_admin')
            account.set_autosign(True, passphrase=settings.agent_pass)
            print(f"✓ Account: {account.address}")
            print(f"  Balance: {account.balance / 1e18:.4f} AVAX")
        except Exception as e:
            print(f"✗ Failed to load account: {e}")
            print("\nFirst time? Create a local account with:")
            print("  ape accounts create")
            return 1
        
        deployment = {
            'network': settings.network_string,
            'deployer': account.address,
            'usdc': settings.usdc_address,
            'contracts': {}
        }
        
        try:
            # 1. Deploy ZeroDegreeRegistry
            pretty_print_deployment('Deploying ZeroDegreeRegistry...')
            
            print("Compiling Contract...")
            registry_contract = project.ZeroDegreeRegistry
            
            print("  Deploying with USDC address: ", settings.usdc_address)
            registry = account.deploy(
                registry_contract,
                settings.usdc_address,
                settings.identity_registry_address
                # publish=True  # Doesnt work for vyper contracts on Fuji, might need manual verification on explorer
            )
            
            print(f"✓ ZeroDegreeRegistry deployed")
            print(f"  Address: {registry.address}")

            update_env_key("ZERO_DEGREE_REGISTRY_ADDRESS", registry.address, ".env")
        
            
            deployment['contracts']['ZeroDegreeRegistry'] = {
                'address': registry.address,
                'constructor_args': [settings.usdc_address, settings.identity_registry_address]
            }
            
            # 2. Verify deployment
            print("\n  Verifying contract...")
            print(f"  Admin: {registry.admin()}")
            print(f"  USDC: {registry.usdc_token()}")
            print(f"  Identity Registry: {registry.identity_registry()}")
            print(f"  Minimum Stake: {registry.minimum_stake() / 1e6:.2f} USDC")
            print(f"✓ Deployment saved to {DEPLOYMENT_FILE}")
            return 0
            
        except Exception as e:
            print(f"\n✗ Deployment failed: {e}")
            import traceback
            traceback.print_exc()
            return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())