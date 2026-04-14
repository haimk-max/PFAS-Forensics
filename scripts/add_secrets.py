#!/usr/bin/env python3
"""
Add GitHub Secrets via GitHub API
Requires: GITHUB_TOKEN environment variable with 'repo' scope
"""

import os
import sys
import json
import base64
import requests
from urllib.parse import urljoin

REPO_OWNER = "haimk-max"
REPO_NAME = "my-first-project"
API_BASE = "https://api.github.com"

def get_repo_public_key():
    """Get the repository's public key for encrypting secrets."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("❌ GITHUB_TOKEN not set. Set it with:")
        print("   export GITHUB_TOKEN=ghp_xxxxx")
        sys.exit(1)

    url = urljoin(API_BASE, f"/repos/{REPO_OWNER}/{REPO_NAME}/actions/secrets/public-key")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to get public key: {response.text}")
        sys.exit(1)

    return response.json()

def encrypt_secret(value: str, public_key: str) -> str:
    """Encrypt a secret value using the repository's public key."""
    try:
        from nacl import utils, public
        public_key_obj = public.PublicKey(public_key, encoder=base64.b64decode)
        sealed_box = public.SealedBox(public_key_obj)
        encrypted = sealed_box.encrypt(value.encode())
        return base64.b64encode(encrypted.ciphertext).decode()
    except ImportError:
        print("❌ PyNaCl not installed. Install with: pip install pynacl")
        sys.exit(1)

def create_secret(name: str, value: str, public_key_data: dict):
    """Create or update a secret in the repository."""
    token = os.getenv("GITHUB_TOKEN")

    # Encrypt the value
    encrypted_value = encrypt_secret(value, public_key_data["key"])

    url = urljoin(API_BASE, f"/repos/{REPO_OWNER}/{REPO_NAME}/actions/secrets/{name}")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    payload = {
        "encrypted_value": encrypted_value,
        "key_id": public_key_data["key_id"],
    }

    response = requests.put(url, json=payload, headers=headers)
    if response.status_code in (201, 204):
        print(f"✅ Created/updated secret: {name}")
        return True
    else:
        print(f"❌ Failed to create secret {name}: {response.text}")
        return False

def main():
    """Main entry point."""
    print("🔐 GitHub Secrets Manager")
    print("-" * 50)

    # Get public key
    print("\n1️⃣  Retrieving repository public key...")
    public_key_data = get_repo_public_key()
    print(f"   Key ID: {public_key_data['key_id']}")

    # List of secrets to create
    secrets = {
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "GMAIL_CLIENT_ID": os.getenv("GMAIL_CLIENT_ID"),
        "GMAIL_CLIENT_SECRET": os.getenv("GMAIL_CLIENT_SECRET"),
        "GMAIL_REFRESH_TOKEN": os.getenv("GMAIL_REFRESH_TOKEN"),
    }

    # Filter out None values
    secrets = {k: v for k, v in secrets.items() if v is not None}

    if not secrets:
        print("\n❌ No secrets provided. Set environment variables:")
        print("   export ANTHROPIC_API_KEY=sk-ant-...")
        print("   export GMAIL_CLIENT_ID=xxxxx.apps.googleusercontent.com")
        print("   export GMAIL_CLIENT_SECRET=GOCSPX-xxxxx")
        print("   export GMAIL_REFRESH_TOKEN=xxxxx")
        sys.exit(1)

    print(f"\n2️⃣  Creating {len(secrets)} secret(s)...")
    for name, value in secrets.items():
        if value:
            create_secret(name, value, public_key_data)
        else:
            print(f"⏭️  Skipping {name} (empty value)")

    print("\n✅ Done! Secrets are now available in GitHub Actions.")

if __name__ == "__main__":
    main()
