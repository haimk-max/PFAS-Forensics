# 🔐 GitHub Secrets Setup Guide

This guide walks you through adding the required secrets to your GitHub repository.

## 📋 Required Secrets

1. **ANTHROPIC_API_KEY** — Your Claude API key
2. **GMAIL_CLIENT_ID** — From Google Cloud Console
3. **GMAIL_CLIENT_SECRET** — From Google Cloud Console  
4. **GMAIL_REFRESH_TOKEN** — Generated via OAuth

---

## Option 1: Web UI (Easiest)

### Step 1: Open Repository Settings

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"**

### Step 2: Add Each Secret

**For ANTHROPIC_API_KEY:**
- Name: `ANTHROPIC_API_KEY`
- Value: `sk-ant-xxxxx...` (from https://console.anthropic.com/account/keys)
- Click **Add secret**

**For GMAIL_CLIENT_ID:**
- Name: `GMAIL_CLIENT_ID`
- Value: `xxxxx.apps.googleusercontent.com`
- Click **Add secret**

**For GMAIL_CLIENT_SECRET:**
- Name: `GMAIL_CLIENT_SECRET`
- Value: `GOCSPX-xxxxx`
- Click **Add secret**

**For GMAIL_REFRESH_TOKEN:**
- Name: `GMAIL_REFRESH_TOKEN`
- Value: (see "Getting Gmail Refresh Token" below)
- Click **Add secret**

---

## Option 2: GitHub API (via Script)

### Prerequisites

```bash
pip install requests pynacl
```

### Usage

```bash
# Set environment variables with your values
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export GMAIL_CLIENT_ID="xxxxx.apps.googleusercontent.com"
export GMAIL_CLIENT_SECRET="GOCSPX-xxxxx"
export GMAIL_REFRESH_TOKEN="xxxxx"

# Set GitHub token (must have 'repo' scope)
export GITHUB_TOKEN="ghp_xxxxx"

# Run the script
python3 scripts/add_secrets.py
```

---

## Getting Gmail Credentials

### Step 1: Create Google Cloud Project

1. Go to: https://console.cloud.google.com
2. Click **Create Project**
3. Name: "Communication Tool"
4. Click **Create**

### Step 2: Enable Gmail API

1. In the left sidebar, click **APIs & Services** → **Library**
2. Search for "Gmail API"
3. Click on it and click **Enable**

### Step 3: Create OAuth Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Application type: **Desktop application**
4. Click **Create**
5. Click the download icon to download the JSON file
6. Save it as `credentials.json`

### Step 4: Generate Refresh Token

Run this Python script:

```python
from google.auth.oauthlib.flow import InstalledAppFlow
import json

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

flow = InstalledAppFlow.from_client_secrets_file(
    "credentials.json",  # The file you downloaded
    SCOPES
)

creds = flow.run_local_server(port=0)

print("=== Copy these to GitHub Secrets ===")
print(f"GMAIL_CLIENT_ID={creds.client_id}")
print(f"GMAIL_CLIENT_SECRET={creds.client_secret}")
print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
```

**This will:**
1. Open a browser asking you to sign in with Google
2. Ask for permission to access Gmail
3. Print the credentials you need

---

## Verification

To verify secrets are set correctly:

```bash
# List all secrets (names only, not values)
curl -H "Authorization: token YOUR_GITHUB_TOKEN" \
  https://api.github.com/repos/haimk-max/my-first-project/actions/secrets
```

You should see:
```json
{
  "secrets": [
    {"name": "ANTHROPIC_API_KEY", ...},
    {"name": "GMAIL_CLIENT_ID", ...},
    {"name": "GMAIL_CLIENT_SECRET", ...},
    {"name": "GMAIL_REFRESH_TOKEN", ...}
  ]
}
```

---

## Testing

Once secrets are set:

1. Go to **Actions** tab in your repository
2. Click **Manual Trigger - Fetch & Analyze Communications**
3. Click **Run workflow**
4. Monitor the logs in real-time

**First run:** You'll see a QR code in the logs for WhatsApp scanning

---

## Troubleshooting

### "No ANTHROPIC_API_KEY found"
- Check that the secret name is exactly `ANTHROPIC_API_KEY` (case-sensitive)
- Verify it's in the **Actions** secrets, not Environment secrets

### "Gmail authentication failed"
- Verify `GMAIL_REFRESH_TOKEN` is set correctly
- Check that Gmail API is enabled in Google Cloud Console
- Try regenerating the token (run the Python script again)

### "WhatsApp QR code not showing"
- Check GitHub Actions logs for the build step
- Make sure Chromium/Chrome is available in the runner environment
- Increase the `QR_WAIT_TIMEOUT` in `src/fetch_whatsapp.py` if needed

---

## Security Best Practices

✅ **Do:**
- Use repository secrets for sensitive data
- Rotate refresh tokens periodically
- Never commit `.env` files or credentials
- Use fine-grained GitHub tokens with minimal scopes

❌ **Don't:**
- Put API keys in code or comments
- Share secret values in PRs or issues
- Use the same token across multiple repos
- Commit `credentials.json` from Google

---

**Need help?** Check the logs in GitHub Actions → Manual Trigger workflow.
