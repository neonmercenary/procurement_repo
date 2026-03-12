# core/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore extra vars in .env
    )
    
    # Network
    network_string: str = "avalanche:fuji"
    rpc_url: str = "https://api.avax-test.network/ext/bc/C/rpc"
    
    # Agent
    agent_alias: str = None
    agent_pass: str = None

    # Vendor (Mock Implementation)
    vendor_alias_ape:  str | None = None
    vendor_pass_ape:  str | None = None
    
    # API Keys
    web3_alchemy_api_key: str | None = None
    routescan_api: str | None = None
    
    # Database
    database_url: str 
    
    # App
    debug: bool = False
    secret_key: str 

    #Worker
    worker_state_file: str = "state.json"

    # EVM
    identity_registry_address: str | None = None
    usdc_address: str | None = None
    zero_degree_registry_address: str | None = None
    snowgate_address: str | None = None
    entrypoint: str | None = None


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()


# Export for easy import
settings = get_settings()