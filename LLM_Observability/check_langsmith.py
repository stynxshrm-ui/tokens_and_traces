"""Run this in your project folder to diagnose the 403."""
import os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv("LANGSMITH_API_KEY")
old_key = os.getenv("LANGCHAIN_API_KEY")
tracing = os.getenv("LANGSMITH_TRACING")
project = os.getenv("LANGSMITH_PROJECT")

print("LANGSMITH_API_KEY  :", f"{key[:8]}..." if key else "NOT SET ← problem")
print("LANGCHAIN_API_KEY  :", f"{old_key[:8]}..." if old_key else "not set")
print("LANGSMITH_TRACING  :", tracing or "NOT SET")
print("LANGSMITH_PROJECT  :", project or "NOT SET")

if not key and old_key:
    print("\n→ FIX: rename LANGCHAIN_API_KEY to LANGSMITH_API_KEY in your .env")
elif not key:
    print("\n→ FIX: add LANGSMITH_API_KEY=ls__... to your .env")
else:
    print("\n→ Keys look set. Testing API connection...")
    import urllib.request, json
    req = urllib.request.Request(
        "https://api.smith.langchain.com/api/v1/me",
        headers={"x-api-key": key}
    )
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read())
            print(f"   Connected as: {data.get('email') or data.get('username', 'unknown')}")
    except Exception as e:
        print(f"   API call failed: {e}")
        print("   → The key itself may be wrong. Regenerate it at smith.langchain.com → Settings → API Keys")