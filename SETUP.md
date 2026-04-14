# 📊 Communication Management Tool
**WhatsApp + Gmail Unified Dashboard**

A GitHub-native tool that fetches and analyzes communications from WhatsApp and Gmail using Claude AI.

---

## 🎯 Features

✅ **Unified Communication Management**
- Fetch messages from WhatsApp Web
- Fetch emails from Gmail API
- View all conversations in one place

✅ **AI-Powered Analysis** (Claude API)
- Summarize conversations automatically
- Extract action items and tasks
- Detect messages requiring responses
- Analyze sentiment and tone

✅ **GitHub-Native Automation**
- Scheduled daily syncs (GitHub Actions)
- Manual on-demand runs
- Results stored in GitHub Issues
- No external hosting required

✅ **Privacy & Security**
- Credentials stored in GitHub Secrets
- Encrypted session storage
- No data sent to external services (except Claude API)

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.9+
- GitHub repository access
- Google OAuth credentials (Gmail API)
- Anthropic API key (Claude API)

### 2. Setup

**Clone or download the repository:**
```bash
git clone https://github.com/your-username/my-first-project
cd my-first-project
```

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Create `.env` file (copy from `.env.example`):**
```bash
cp .env.example .env
```

**Fill in your credentials:**
```
ANTHROPIC_API_KEY=sk-ant-...
GMAIL_CLIENT_ID=...
GMAIL_CLIENT_SECRET=...
```

### 3. GitHub Setup

**Add GitHub Secrets:**
1. Go to Settings → Secrets and variables → Actions
2. Add these secrets:
   - `ANTHROPIC_API_KEY` - Your Claude API key
   - `GMAIL_CLIENT_ID` - From Google Cloud Console
   - `GMAIL_CLIENT_SECRET` - From Google Cloud Console
   - `GMAIL_USER_EMAIL` - Your Gmail address

### 4. Run Locally (Optional)

```bash
python -m src.main
```

This will:
1. Prompt you to scan WhatsApp QR code
2. Authorize Gmail access
3. Fetch messages from both platforms
4. Analyze with Claude API
5. Save results to `results.json`

### 5. GitHub Actions

**Manual trigger:**
- Go to Actions → Manual Trigger - Fetch & Analyze
- Click "Run workflow"
- Check logs for QR code and OAuth link

**Scheduled runs:**
- Configured to run daily at 8 AM UTC
- Modify `.github/workflows/scheduled-fetch.yml` to change schedule
- Results posted to GitHub Issues

---

## 📋 File Structure

```
my-first-project/
├── src/
│   ├── __init__.py
│   ├── main.py                    # Orchestrator
│   ├── fetch_whatsapp.py          # WhatsApp fetcher
│   ├── fetch_gmail.py             # Gmail fetcher
│   ├── analyze_conversations.py   # Claude API integration
│   └── utils.py                   # Helper functions
├── .github/workflows/
│   ├── manual-trigger.yml         # On-demand workflow
│   └── scheduled-fetch.yml        # Daily workflow
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment template
├── .gitignore                     # Git ignore rules
├── claude.md                      # Claude Code documentation
└── SETUP.md                       # Setup guide
```

---

## 🔐 Security

**Best Practices:**
- Never commit `.env` or credentials
- Use GitHub Secrets for all sensitive data
- Sessions are base64-encoded before storage
- No message data is persisted beyond analysis
- Audit GitHub Actions logs for sensitive data

---

## 📈 Limitations & Future Work

### Current Limitations
- WhatsApp sessions expire after ~30 days
- Gmail API: 250 requests/user/second limit
- GitHub Actions: 6-hour timeout per workflow
- Storage: ~1GB per repository

---

**Built with:**
- 🐍 Python
- 🤖 Claude API (Anthropic)
- 📧 Gmail API (Google)
- 📱 Selenium (WhatsApp Web)
- ⚙️ GitHub Actions

**Last Updated:** 2026-04-14
