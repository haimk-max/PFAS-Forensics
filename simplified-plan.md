# SIMPLIFIED EXECUTION PLAN

## Summary
Build a GitHub-native WhatsApp + Gmail communication management tool using Python, Claude API, and GitHub Actions.

## Phase 1: Project Structure & Setup
**Files to create:**
- `src/__init__.py`
- `src/main.py` - Entry point
- `src/fetch_whatsapp.py` - WhatsApp data fetcher
- `src/fetch_gmail.py` - Gmail data fetcher
- `src/analyze_conversations.py` - Claude API integration
- `src/utils.py` - Helper functions
- `requirements.txt` - Python dependencies
- `.env.example` - Template for environment variables
- `.gitignore` - Ignore sensitive files

**Key dependencies:**
```
selenium
google-auth
google-auth-oauthlib
google-api-python-client
anthropic
PyGithub
python-dotenv
```

## Phase 2: WhatsApp Integration
**File: `src/fetch_whatsapp.py`**

Key functions:
- `authenticate_whatsapp()` - QR code login via Selenium
- `get_chats()` - List all chats
- `get_messages(chat_id)` - Get messages from chat
- `save_session()` - Save session for reuse

Selenium setup:
- Headless Chrome/Chromium
- Wait for QR code in logs
- Auto-save session after login

## Phase 3: Gmail Integration
**File: `src/fetch_gmail.py`**

Key functions:
- `authenticate_gmail()` - OAuth setup
- `get_threads()` - List email threads
- `get_messages(thread_id)` - Get thread messages
- `save_token()` - Save refresh token

OAuth flow:
- First run: Generate auth URL → save token
- Subsequent runs: Use saved token

## Phase 4: Claude API Analysis
**File: `src/analyze_conversations.py`**

Key functions:
- `summarize_chat(contact, messages)` - Use Claude to summarize
- `extract_action_items(messages)` - Find pending tasks
- `detect_unanswered(messages)` - Find messages needing response
- `analyze_sentiment(messages)` - Conversation tone analysis

Claude integration:
- Model: `claude-3-5-sonnet-20241022`
- System prompt for consistent analysis
- Token-efficient prompts

## Phase 5: GitHub Actions Automation
**Files to create:**
- `.github/workflows/scheduled-fetch.yml` - Daily sync
- `.github/workflows/manual-trigger.yml` - On-demand run

Workflow features:
- Retrieve credentials from GitHub Secrets
- Run Python scripts
- Post results to GitHub Issues
- Save session files to repo (encrypted)

---

## Critical Path

1. ✅ Create project structure
2. ✅ Setup requirements.txt
3. ✅ Implement WhatsApp fetch (Phase 2)
4. ✅ Implement Gmail fetch (Phase 3)
5. ✅ Implement Claude analysis (Phase 4)
6. ✅ Create GitHub Actions workflows (Phase 5)
7. ✅ Test end-to-end

## Testing Checklist

- [ ] QR code appears in GitHub Actions logs
- [ ] WhatsApp session is saved
- [ ] Gmail OAuth flow works
- [ ] Claude API summarizes conversations
- [ ] Results post to GitHub Issues
- [ ] Scheduled workflow runs daily
- [ ] Manual trigger works

---

**Status:** Ready for implementation
**Model for execution:** claude-sonnet-4-6
