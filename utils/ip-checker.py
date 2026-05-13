from typing import List, Optional
import httpx
from core.config import logger

PROVIDER_IPS = {
    "paystack": [
        "52.31.139.75",
        "52.49.173.169",
        "52.214.14.220"
    ],
    "flutterwave": [
        "3.249.192.34",
        "52.209.154.143",
        "52.214.14.220"
    ]
}

def is_ip_allowed(ip_address: str, provider: str) -> bool:
    allowed_ips = PROVIDER_IPS.get(provider.lower(), [])
    if not allowed_ips:
        logger.warning(f"No IP whitelist found for provider: {provider}")
        return False
        
    is_allowed = ip_address in allowed_ips
    if not is_allowed:
        logger.warning(f"IP address {ip_address} is not whitelisted for provider {provider}")
        
    return is_allowed

async def fetch_latest_provider_ips(provider: str) -> Optional[List[str]]:
    return None
