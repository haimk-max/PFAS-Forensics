#!/bin/bash
set -e

echo "🔐 Communication Tool - GitHub Secrets Setup"
echo "=============================================="
echo ""

# Check if .env.local exists
if [ ! -f ".env.local" ]; then
    echo "❌ .env.local file not found!"
    echo ""
    echo "Setup instructions:"
    echo "1. Copy template: cp .env.secrets .env.local"
    echo "2. Edit: nano .env.local (or your editor)"
    echo "3. Fill in your API keys from:"
    echo "   - Anthropic: https://console.anthropic.com/account/keys"
    echo "   - Gmail: SETUP_SECRETS.md"
    echo ""
    exit 1
fi

echo "✅ .env.local found"
echo ""

# Source the .env.local file
source .env.local

# Check required variables
REQUIRED_VARS=(
    "ANTHROPIC_API_KEY"
    "GMAIL_CLIENT_ID"
    "GMAIL_CLIENT_SECRET"
    "GMAIL_REFRESH_TOKEN"
    "GITHUB_TOKEN"
)

echo "📋 Checking required environment variables..."
for var in "${REQUIRED_VARS[@]}"; do
    value=$(eval echo \$$var)
    if [ -z "$value" ]; then
        echo "❌ Missing: $var"
        exit 1
    else
        # Show first 8 chars + dots (for security)
        safe_value="${value:0:8}..."
        echo "✅ $var=$safe_value"
    fi
done

echo ""
echo "🚀 All variables present! Running secrets setup..."
echo ""

# Check Python and required packages
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Install it first."
    exit 1
fi

# Install required packages
echo "📦 Installing required Python packages..."
pip install -q requests pynacl 2>/dev/null || {
    echo "⚠️  Could not install packages. Try manually:"
    echo "   pip install requests pynacl"
    exit 1
}

echo "✅ Packages ready"
echo ""

# Run the setup script
echo "🔑 Adding secrets to GitHub repository..."
python3 scripts/add_secrets.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Go to: https://github.com/haimk-max/my-first-project/settings/secrets/actions"
echo "2. Verify all 4 secrets are present"
echo "3. Run: gh workflow run manual-trigger.yml"
echo "   (or use GitHub UI: Actions → Manual Trigger → Run workflow)"
echo ""
echo "First run will ask for WhatsApp QR code scan!"
echo "Check logs: Actions → Manual Trigger → Latest run"
echo ""
