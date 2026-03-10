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
    rpc_url: str = None
    routescan_api: str | None = None
    
    # Agent
    agent_alias: str | None = None
    agent_pass: str | None = None
    
    # Contracts
    mall_addr: str | None = None
    snowgate_address: str | None = None
    zero_degree_registry_address: str | None = None

    #Worker
    worker_state_file: str = "state.json"
    groq_api_key: str | None = None
    relayer_passphrase: str | None = None

    # EVM
    identity_registry_address: str | None = None
    vendor_shop_address: str | None = ""
    usdc_address: str | None = None
    entrypoint: str | None = None   #    ERC-4337 EntryPoint


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()


# Export for easy import
settings = get_settings()