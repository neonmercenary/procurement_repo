import os, logging, asyncio
from ape import networks, accounts, project, Contract
from fastapi import FastAPI
from app.settings import settings


logger = logging.getLogger(__name__)

# Constants - Load from .env for the real build
NETWORK_STRING = settings.network_string
AGENT_ALIAS = settings.agent_alias
AGENT_PASS = settings.agent_pass
SNOWGATE_ADDR = settings.snowgate_address
ZERO_DEGREE_REGISTRY_ADDR = settings.zero_degree_registry_address
USDC_ADDR = settings.usdc_address

async def init_blockchain(app: FastAPI):
    """
    Initializes the persistent blockchain provider and loads identity/contracts.
    Attached to the FastAPI lifespan.
    """
    print(f"🔗 Connecting to {NETWORK_STRING}...")
    
    # 1. Establish the Provider Context
    # We keep the context manager open for the duration of the app life
    app.state.provider_context = networks.parse_network_choice(NETWORK_STRING)
    app.state.provider_context.__enter__()
    
    # 2. Load the Agent Account
    try:
        agent = accounts.load(AGENT_ALIAS)
        # set_autosign allows the worker to sign transactions without human prompts
        agent.set_autosign(True, passphrase=AGENT_PASS)
        app.state.agent = agent
        print(f"🤖 Agent '{AGENT_ALIAS}' loaded ({agent.address})")

    except Exception as e:
        print(f"❌ Failed to load agent: {e}")
        raise e

    # 3. Load Contracts (ERC-8004 Identity Registry and ZeroDegreeRegistry)
    try:
        
        # Attempt to connect to ERC-8004 Contract
        if settings.identity_registry_address:
            app.state.identity_registry = Contract(settings.identity_registry_address)
            logger.info(f"✅ Identity Registry connected at {settings.identity_registry_address}")
        else:
            app.state.identity_registry = None
            logger.warning(f"⚠️  Identity Registry not found at {settings.identity_registry_address} - running without Identity Registry")
            
        # Attempt to connect to Mall/Registry
        if ZERO_DEGREE_REGISTRY_ADDR:
            app.state.mall = Contract(ZERO_DEGREE_REGISTRY_ADDR)
            logger.info(f"✅ ZeroDegreeRegistry connected at {ZERO_DEGREE_REGISTRY_ADDR}")
        else:
            app.state.mall = None
            logger.warning(f"⚠️  ZeroDegreeRegistry not found at {ZERO_DEGREE_REGISTRY_ADDR} - running without registry")
            
    except Exception as e:
        # Catch any Ape network errors and continue
        logger.error(f"❌ Blockchain init error: {e}")
        app.state.mall = None
    
    print(f"✅ Contracts Linked: ZeroDegree@{ZERO_DEGREE_REGISTRY_ADDR}")

def close_blockchain(app: FastAPI):
    """Safely disconnects from the blockchain network."""
    print("🔌 Disconnecting from blockchain...")
    if hasattr(app.state, "provider_context"):
        app.state.provider_context.__exit__(None, None, None)