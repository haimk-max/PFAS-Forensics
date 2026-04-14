# 📊 Communication Management Tool

**Unify WhatsApp + Gmail with AI-powered analysis using Claude API**

A GitHub-native tool that fetches and analyzes communications from WhatsApp and Gmail, extracting actionable insights, summarizing conversations, and tracking pending items — all powered by Claude AI.

---

## 🎯 Features

✅ **Unified Communication Dashboard**
- WhatsApp messages via Selenium automation
- Gmail emails via official Gmail API
- Combined view of all conversations

✅ **AI-Powered Analysis** (Claude Sonnet 4.6)
- Automatic summarization
- Action item extraction
- Unanswered message detection
- Sentiment analysis
- Custom question answering

✅ **GitHub-Native Automation**
- Scheduled daily syncs (GitHub Actions)
- Manual on-demand runs
- Results stored in GitHub Issues
- No external hosting required

✅ **Production-Ready Code**
- Retry logic with exponential backoff
- Session persistence
- Prompt caching for cost optimization
- Adaptive thinking for complex analysis
- Typed exception handling

---

## 🚀 Quick Start

### **1️⃣ Prerequisites**

- Python 3.9+
- GitHub account with repository access
- Anthropic API key (Claude)
- Gmail OAuth credentials

### **2️⃣ Clone & Install**

```bash
git clone https://github.com/haimk-max/my-first-project.git
cd my-first-project

# Install dependencies
pip install -r requirements.txt
```

### **3️⃣ Setup Secrets**

Choose your method:

**Method A: Web UI (Easiest)**
1. Read: `SETUP_SECRETS.md`
2. Go to GitHub Settings → Secrets and variables → Actions
3. Add 4 secrets: `ANTHROPIC_API_KEY`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`

**Method B: Script (Fastest)**
```bash
# Copy template
cp .env.secrets .env.local

# Edit with your values
nano .env.local

# Run setup
make setup-secrets
```

**Method C: Manual (Local Testing)**
```bash
cp .env.secrets .env.local
# Edit .env.local
source .env.local
python -m src.main
```

### **4️⃣ First Run**

**Option A: GitHub Actions**
```bash
make run-workflow
# Or go to Actions → Manual Trigger → Run workflow
```

**Option B: Local**
```bash
# After .env.local setup
make run-local
```

**First Time Only:** Scan WhatsApp QR code in the logs/terminal

---

## 📋 Available Commands

```bash
# Setup
make setup-secrets       # Add secrets to GitHub
make setup-local        # Create .env.local from template

# Development
make install            # Install Python dependencies
make run-local          # Run locally

# Testing & Linting
make test              # Run tests
make lint              # Lint code

# CI/CD
make run-workflow      # Trigger GitHub Action
make check-secrets     # Verify secrets are set

# Cleanup
make clean             # Remove Python cache
```

---

## 📁 Project Structure

```
my-first-project/
├── src/
│   ├── __init__.py
│   ├── main.py                        # Orchestrator
│   ├── fetch_whatsapp.py             # WhatsApp fetcher (Selenium)
│   ├── fetch_gmail.py                # Gmail fetcher (API)
│   ├── analyze_conversations.py      # Claude API integration
│   └── utils.py                      # Helpers
│
├── .github/workflows/
│   ├── manual-trigger.yml            # On-demand workflow
│   └── scheduled-fetch.yml           # Daily workflow
│
├── scripts/
│   ├── add_secrets.py                # GitHub API secret manager
│   └── setup-secrets.sh              # Setup helper
│
├── SETUP_SECRETS.md                  # Detailed secrets guide
├── requirements.txt                  # Python dependencies
├── .env.example                      # Environment template
├── .env.secrets                      # Local secrets template
├── Makefile                          # Command shortcuts
└── README.md                         # This file
```

---

## 🔐 Secrets Configuration

All credentials are stored as **GitHub Secrets** (encrypted, not in code).

| Secret | Source | Instructions |
|--------|--------|--------------|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com/account/keys | Create new API key |
| `GMAIL_CLIENT_ID` | Google Cloud Console | See SETUP_SECRETS.md |
| `GMAIL_CLIENT_SECRET` | Google Cloud Console | See SETUP_SECRETS.md |
| `GMAIL_REFRESH_TOKEN` | OAuth flow (Python script) | See SETUP_SECRETS.md |

**Security:** Never commit real credentials. `.env.local` is in `.gitignore`.

---

## 💻 Usage Examples

### Run Locally (After Setup)

```bash
# Set environment
source .env.local

# Run the main script
python -m src.main

# Or use the Makefile
make run-local
```

### Use in Code

```python
from src.main import CommunicationManager

# Initialize
manager = CommunicationManager()

# Authenticate
manager.authenticate_all()

# Fetch messages
messages = manager.fetch_all_messages()

# Analyze a contact
analysis = manager.analyze_contact("John Doe")
print(analysis["summary"])      # Summary of conversation
print(analysis["action_items"]) # Pending tasks
print(analysis["sentiment"])    # Overall tone
```

### Analyze Specific Conversation

```python
from src.analyze_conversations import ConversationAnalyzer

analyzer = ConversationAnalyzer()

# Summarize
summary = analyzer.summarize(messages)

# Extract action items
items = analyzer.extract_action_items(messages)

# Find unanswered questions
pending = analyzer.detect_unanswered(messages)

# Ask custom question
answer = analyzer.ask_question(messages, "What's the timeline?")
```

---

## 📊 Architecture

```
┌─────────────────────────────────────────────────────┐
│           GitHub Actions (Orchestration)             │
└──────────────┬──────────────────────────┬────────────┘
               │                          │
      ┌────────▼─────────┐     ┌─────────▼────────────┐
      │  Scheduled Sync  │     │  Manual Trigger      │
      │  (daily 8 AM)    │     │  (on-demand)         │
      └────────┬─────────┘     └─────────┬────────────┘
               │                        │
               └────────────┬───────────┘
                            │
                    ┌───────▼────────┐
                    │  main.py       │
                    │  (Orchestrator)│
                    └───────┬────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   ┌────▼────────┐  ┌──────▼──────┐  ┌────────▼─────────┐
   │ WhatsApp    │  │    Gmail    │  │ Claude API      │
   │ (Selenium)  │  │    (API)    │  │ (Sonnet 4.6)    │
   │             │  │             │  │                 │
   │ • QR auth   │  │ • OAuth 2.0 │  │ • Summarize     │
   │ • Chats     │  │ • Threads   │  │ • Extract items │
   │ • Messages  │  │ • Search    │  │ • Sentiment     │
   └────────────┘  └─────────────┘  └─────────────────┘
        │                │                     │
        └────────────────┼─────────────────────┘
                         │
                ┌────────▼────────────┐
                │ GitHub Issues       │
                │ (Results storage)   │
                └─────────────────────┘
```

---

## 🔧 Technology Stack

- **Backend:** Python 3.9+
- **WhatsApp:** Selenium (headless Chrome)
- **Gmail:** Official Gmail API (OAuth 2.0)
- **AI:** Claude Sonnet 4.6 (Anthropic)
- **Automation:** GitHub Actions
- **Storage:** GitHub Issues / Session files

---

## 🧪 Testing

```bash
# Run tests
make test

# Lint code
make lint

# Check secrets are configured
make check-secrets

# View logs from last GitHub Action
gh run view --log
```

---

## 📈 Performance & Cost

### Optimizations

- **Prompt Caching:** System prompts cached → ~90% savings on repeated requests
- **Retry Logic:** Automatic retries on rate limits with exponential backoff
- **Session Reuse:** WhatsApp/Gmail sessions persist → faster subsequent runs
- **Batch Processing:** GitHub Actions runs cost-effective batches

### Costs (Approx.)

| Operation | Cost | Notes |
|-----------|------|-------|
| Summarize (cached) | $0.0001 | Cache hit |
| Extract items | $0.0002 | Structured output |
| Sentiment analysis | $0.00005 | Short response |
| Full analysis | $0.0005 | First run |

> Running daily costs ~$0.15/month with caching

---

## 🐛 Troubleshooting

### "ANTHROPIC_API_KEY not found"
```bash
# Check secret is set
make check-secrets

# Or manually verify
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/haimk-max/my-first-project/actions/secrets
```

### "WhatsApp QR code not appearing"
- Check GitHub Actions logs in detail
- Ensure Chrome/Chromium is available
- Increase `QR_WAIT_TIMEOUT` in `src/fetch_whatsapp.py`

### "Gmail authentication failed"
- Verify `GMAIL_REFRESH_TOKEN` is correct (from Python script)
- Check Gmail API is enabled: https://console.cloud.google.com/apis/api/gmail.googleapis.com
- Try regenerating the token

### "Rate limited by Claude API"
- Built-in retry logic handles this
- Check logs for `Rate limited` messages
- Reduce request frequency if persistent

---

## 🔒 Security Best Practices

✅ **What We Do:**
- Store secrets in GitHub Secrets (encrypted)
- Use OAuth for Gmail (no stored password)
- Base64 encode WhatsApp sessions
- Never log sensitive data
- Use HTTPS for all API calls

✅ **What You Should Do:**
- Never commit `.env.local` or credentials
- Rotate tokens periodically
- Use fine-grained GitHub tokens
- Audit access logs regularly
- Keep dependencies updated

---

## 📝 License

This project is for educational and personal use.

---

## 🤝 Contributing

Contributions welcome! To contribute:

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes and test locally
3. Commit with clear messages
4. Push and create a pull request

---

## 📞 Support

- **Setup Issues:** See `SETUP_SECRETS.md`
- **API Questions:** Check language-specific docs
- **Bugs:** File an issue with logs
- **Feature Requests:** Start a discussion

---

## 🎯 Next Steps

- [ ] Setup GitHub Secrets (`make setup-secrets`)
- [ ] Test locally (`make run-local`)
- [ ] Run first GitHub Action
- [ ] Scan WhatsApp QR code
- [ ] Review results in GitHub Issues
- [ ] Customize analysis prompts
- [ ] Deploy to production

---

**Built with ❤️ using Claude AI, GitHub Actions, and open-source tools.**

*Last updated: 2026-04-14*
