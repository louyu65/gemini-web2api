"""
Minimal test to verify if the cookie works with GeminiClient directly.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests" / "Gemini-API-master" / "src"))

from gemini_webapi import GeminiClient

async def test():
    with open("tests/cookie.json", "r", encoding="utf-8") as f:
        cookies = json.load(f)

    psid = cookies.get("__Secure-1PSID", "")
    psidts = cookies.get("__Secure-1PSIDTS", "")

    extra = {k: v for k, v in cookies.items() if k not in {"__Secure-1PSID", "__Secure-1PSIDTS"}}

    client = GeminiClient(secure_1psid=psid, secure_1psidts=psidts)
    client.cookies = extra  # Set extra cookies via setter

    try:
        await client.init(auto_refresh=False, verbose=True)
        print(f"Account status: {client.account_status.name} ({client.account_status.value})")
        print(f"Account description: {client.account_status.description}")

        output = await client.generate_content("draw a cat")
        print(f"Output text: {getattr(output, 'text', '')}")
        print(f"Output images: {len(getattr(output, 'images', []) or [])}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test())
