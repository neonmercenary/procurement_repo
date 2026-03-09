import os
from fastapi import FastAPI, HTTPException 
from pathlib import Path
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization


def convert_to_dollars(amount: int) -> float:
    """Convert amount in cents to dollars."""
    return amount / 10 ** 6

def convert_to_wei(amount: float) -> int:
    """Convert amount in dollars to wei (cents)."""
    return int(amount * 10 ** 6)


def update_env_key(key, value, env_path=".env"):
    path = Path(env_path)

    lines = []
    key_found = False

    if path.exists():
        with open(path, "r") as f:
            for line in f:
                if line.startswith(f"{key}="):
                    lines.append(f"{key}={value}\n")
                    key_found = True
                else:
                    lines.append(line)

    if not key_found:
        lines.append(f"{key}={value}\n")

    with open(path, "w") as f:
        f.writelines(lines)


def require_contract(contract_attr: str, app=FastAPI):
    """Decorator/route dependency to ensure contract is available."""
    def checker():
        contract = getattr(app.state, contract_attr, None)
        if contract is None:
            raise HTTPException(
                status_code=503,
                detail=f"Service unavailable: {contract_attr} contract not connected"
            )
        return contract
    return checker


def encrypt_delivery_payload(file_hash: str):
    """
    MVP FIX: Just hex-encode the hash. 
    In the real world, we'd fetch the RSA key from the Registry.
    """
    # Simply return the hex of the hash to satisfy the contract's 'bytes' input
    return "0x" + file_hash.encode().hex()
