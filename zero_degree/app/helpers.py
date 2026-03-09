from pathlib import Path
import asyncio

# Merchant registry (Manual for MVP, will look up via agent tags in Production)
MERCHANTS = {
    "api,api keys,amazon,licences": "0x143b3De6B3fDD601E26CbEDC4588aBbFfF851EB6",
    "AI_COMPUTE": {"shop": "0xVendorShop_Fuji_Addr", "product_id": 1},
    "DATA_FEED_V1": {"shop": "0xVendorShop_Fuji_Addr", "product_id": 2}
}

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


def find_merchant(keywords: str) -> str | None:
    keywords_lower = keywords.lower()
    for k, addr in MERCHANTS.items():
        if any(word.lower() in keywords_lower for word in k.split(",")):
            return addr
    return None


def decrypt_api_key(encrypted_payload: str):
    """
    Decodes the hex payload from the VendorShop 'ProductDelivered' event.
    """
    try:
        # 1. Clean the '0x' prefix if Routescan/Ape included it
        clean_hex = encrypted_payload[2:] if encrypted_payload.startswith("0x") else encrypted_payload
        
        # 2. Convert hex string back to raw bytes
        raw_bytes = bytes.fromhex(clean_hex)
        
        # 3. Decode bytes back to the original string (e.g., SECRET_ACCESS_KEY_...)
        decrypted_key = raw_bytes.decode('utf-8')
        
        return decrypted_key
    
    except Exception as e:
        return f"Decryption Error: {str(e)}"
