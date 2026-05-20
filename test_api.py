"""
Quick test script for the Gemini API wrapper.

Usage:
    # 1. Start the server first:
    python run.py

    # 2. In another terminal, run tests:
    python test_api.py
"""

import json
import sys

try:
    import requests
except ImportError:
    print("Installing requests...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

BASE = "http://127.0.0.1:8000"


def test_health():
    r = requests.get(f"{BASE}/health")
    print("/health", r.status_code, r.json())
    assert r.status_code == 200
    data = r.json()
    assert "account_status" in data
    print(f"Account status: {data['account_status']}")


def test_models():
    r = requests.get(f"{BASE}/v1/models")
    print("/v1/models", r.status_code, r.json())
    assert r.status_code == 200


def test_chat():
    payload = {
        "model": "gemini",
        "messages": [{"role": "user", "content": "Hello, who are you?"}],
        "stream": False,
    }
    r = requests.post(f"{BASE}/v1/chat/completions", json=payload)
    print("/v1/chat/completions (non-stream)", r.status_code)
    data = r.json()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    assert r.status_code == 200
    assert "choices" in data


def test_chat_stream():
    payload = {
        "model": "gemini",
        "messages": [{"role": "user", "content": "Count from 1 to 5"}],
        "stream": True,
    }
    r = requests.post(f"{BASE}/v1/chat/completions", json=payload, stream=True)
    print("/v1/chat/completions (stream)", r.status_code)
    assert r.status_code == 200
    for line in r.iter_lines():
        if line:
            print(line.decode("utf-8"))


def test_image_gen():
    # Default response_format is b64_json
    payload = {
        "model": "gemini",
        "prompt": "A cat wearing a space suit on the moon",
        "n": 1,
    }
    r = requests.post(f"{BASE}/v1/images/generations", json=payload)
    print("/v1/images/generations (b64)", r.status_code)
    data = r.json()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    assert r.status_code == 200

    images = data.get("data", [])
    assert len(images) > 0, "No image data returned"

    if images[0].get("b64_json"):
        import base64
        img_bytes = base64.b64decode(images[0]["b64_json"])
        print(f"Image received as base64, size={len(img_bytes)} bytes")
        assert len(img_bytes) > 0
    elif images[0].get("url"):
        img_url = images[0]["url"]
        print(f"Image returned as URL: {img_url[:80]}...")
    else:
        print("No image content returned (likely UNAUTHENTICATED)")


def test_image_gen_url():
    # Explicitly request URL format
    payload = {
        "model": "gemini",
        "prompt": "A cat wearing a space suit on the moon",
        "n": 1,
        "response_format": "url",
    }
    r = requests.post(f"{BASE}/v1/images/generations", json=payload)
    print("/v1/images/generations (url)", r.status_code)
    data = r.json()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    assert r.status_code == 200

    images = data.get("data", [])
    if images and images[0].get("url"):
        img_url = images[0]["url"]
        print(f"Downloading local image from: {img_url[:80]}...")
        r2 = requests.get(img_url)
        print("GET image", r2.status_code, r2.headers.get("content-type"))
        assert r2.status_code == 200
        assert r2.headers.get("content-type", "").startswith("image/")
        print(f"Image downloaded successfully, size={len(r2.content)} bytes")
    else:
        print("No image URL returned (likely UNAUTHENTICATED), skipping URL test")




def test_vision_base64():
    # Create a tiny 1x1 red PNG in base64
    b64_png = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )
    payload = {
        "model": "gemini-vision",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What color is this?"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_png}"}},
                ],
            }
        ],
    }
    r = requests.post(f"{BASE}/v1/chat/completions", json=payload)
    print("/v1/chat/completions (vision base64)", r.status_code)
    if r.status_code != 200:
        print("Response text:", r.text[:500])
        assert False, f"Vision request failed with {r.status_code}"
    data = r.json()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    assert r.status_code == 200


def test_refresh_cookie():
    payload = {
        "cookies": {
            "__Secure-1PSID": "g.a000invalid_test",
            "__Secure-1PSIDTS": "sidts-test"
        }
    }
    r = requests.post(f"{BASE}/v1/admin/refresh-cookie", json=payload)
    print("/v1/admin/refresh-cookie", r.status_code)
    data = r.json()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    # We expect either success (if cookie happens to be valid) or 502 error
    assert r.status_code in (200, 502)
    if r.status_code == 200:
        assert data.get("success") is True
        assert "account_status" in data
        print(f"Cookie refresh succeeded: {data['account_status']}")
    else:
        assert "error" in data
        print(f"Cookie refresh failed as expected with invalid test cookie: {data['error']['message'][:100]}")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Gemini API Wrapper")
    print("=" * 60)

    try:
        test_health()
        test_models()
        test_chat()
        test_chat_stream()
        test_image_gen()
        test_image_gen_url()
        test_vision_base64()
        print("\n[OK] All tests passed!")
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
