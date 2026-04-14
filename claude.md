# Communication Management Tool - Claude.md

## Project Overview

**Goal:** Build a GitHub-native tool that unifies WhatsApp + Gmail communication management with AI analysis.

**Scope:** 
- Read WhatsApp + Gmail messages
- Search conversations with specific contacts
- Summarize and analyze using Claude API
- Track action items and pending responses
- Completely GitHub-based (no external hosting)

---

## Architecture

```
GitHub Repo
├── Python Scripts (src/)
│   ├── fetch_whatsapp.py  (Selenium automation)
│   ├── fetch_gmail.py     (Gmail API)
│   ├── analyze_conversations.py (Claude API)
│   └── main.py (orchestration)
├── GitHub Actions
│   ├── scheduled-fetch.yml (daily sync)
│   └── manual-trigger.yml (on-demand)
└── Storage: GitHub Issues/Discussions
```

## Tech Stack

- **Language:** Python 3.9+
- **WhatsApp:** Selenium (headless browser)
- **Gmail:** Google Gmail API (OAuth 2.0)
- **AI:** Claude API (Sonnet-4.6 model)
- **Automation:** GitHub Actions
- **Storage:** GitHub Issues

## Key Components

### Python Modules

**fetch_whatsapp.py**
- Authenticate via QR code (Selenium)
- Extract chat list and messages
- Save to JSON format

**fetch_gmail.py**
- OAuth authentication
- Fetch email threads
- Extract message bodies

**analyze_conversations.py**
- Use Claude API for analysis
- Summarize conversations
- Extract action items
- Detect unanswered messages

**main.py**
- Orchestrate data fetching
- Call Claude API
- Format and store results

### GitHub Actions Workflows

**scheduled-fetch.yml**
- Runs daily (configurable)
- Fetches latest messages
- Posts summary to GitHub Issues

**manual-trigger.yml**
- Triggered manually from UI
- Accepts contact/query parameters
- Runs immediately

## Authentication & Secrets

Required GitHub Secrets:
- `ANTHROPIC_API_KEY` - Claude API key
- `GMAIL_CLIENT_ID` - From Google Cloud Console
- `GMAIL_CLIENT_SECRET` - From Google Cloud Console
- `GMAIL_REFRESH_TOKEN` - Generated after first OAuth
- `WHATSAPP_SESSION` - Encoded session (auto-saved)

## Development Guidelines

### Adding Features
1. New features should go in `src/` directory
2. Update `requirements.txt` for new dependencies
3. Test locally before pushing
4. Update GitHub Actions if workflow changes

### Debugging
- Check GitHub Actions logs for QR codes (WhatsApp)
- Check GitHub Actions logs for OAuth URLs (Gmail)
- Use environment variables for local testing

### Claude API Best Practices
- Use `claude-3-5-sonnet-20241022` for balance
- Implement prompt templates for consistency
- Cache conversation history when possible
- Monitor token usage for cost optimization

## Next Steps

- [ ] Phase 1: Setup Python structure
- [ ] Phase 2: Implement WhatsApp fetching
- [ ] Phase 3: Implement Gmail fetching
- [ ] Phase 4: Implement Claude analysis
- [ ] Phase 5: Setup GitHub Actions

---

**Model:** claude-sonnet-4-6 (for execution)
**Status:** In Planning
**Last Updated:** 2026-04-14
