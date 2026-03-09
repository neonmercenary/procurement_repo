# scripts/deploy_snowgate.py
from ape import accounts, project, networks
import click
from app.settings import settings
from pathlib import Path
from app.helpers import update_env_key

def main():
    account = accounts.load("spv_admin")
    account.set_autosign(True, passphrase=settings.agent_pass)
    
    print(f"\n🔗 Connecting to {settings.network_string}...")
    with networks.parse_network_choice(settings.network_string) as provider:
        # Load account (configured in ape-config.yaml or accounts folder)
        
        
        click.echo(f"Deployer: {account.address}")
        click.echo(f"Balance: {account.balance / 1e18} AVAX")
        
        # USDC address (AVAX or Custom)
        # usdc_address = click.prompt("USDC address", default=settings.usdc_address)
        
        # Deploy
        click.echo("Deploying Contract...")
        
        snowgate = account.deploy(
            project.SnowGateSession,
            settings.usdc_address,       # USDC Address
            "FC Bayern Munich",  # Company Name
            "12345",              # Company ID
            # gas_limit=500_000,     # Optional: Set a custom gas limit
            # publish=True        # For verification on block explorers (if supported by the network, but doesnt work for vyper)
        )
        
        click.echo(f"✅ Deployed to: {snowgate.address}")
    
    # Save to file
    update_env_key("SNOWGATE_ADDRESS", snowgate.address)
    click.echo("Saved to .env")
    
    return snowgate


