"""
Gmail API fetcher using official Google API
Handles OAuth authentication and message retrieval with retry logic
"""

import base64
import logging
import os
import time
from typing import Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .utils import get_timestamp

logger = logging.getLogger(__name__)

# Gmail API scopes (read-only)
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

MAX_RETRIES = 3
RETRY_BACKOFF = [2, 4, 8]   # seconds


def _retry(func, retries=MAX_RETRIES, backoff=RETRY_BACKOFF):
    """Run func with exponential backoff on transient HttpError failures."""
    for attempt in range(retries):
        try:
            return func()
        except HttpError as e:
            # 429 / 5xx are retryable; 4xx (except 429) are not
            if e.resp.status in (429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = backoff[attempt] if attempt < len(backoff) else backoff[-1]
                logger.warning(
                    f"Gmail API error {e.resp.status} on attempt {attempt + 1}. "
                    f"Retrying in {wait}s..."
                )
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            if attempt == retries - 1:
                raise
            wait = backoff[attempt] if attempt < len(backoff) else backoff[-1]
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
            time.sleep(wait)


class GmailFetcher:
    """Fetch data from Gmail using official API with retry and pagination support."""

    TOKEN_FILE = "gmail_token.json"

    def __init__(self):
        self.service = None
        self.creds: Optional[Credentials] = None
        self.authenticated = False

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self) -> bool:
        """Authenticate with Gmail.

        Strategy (in order):
        1. Load existing token from ``gmail_token.json``
        2. Refresh if expired (using saved refresh_token)
        3. Build credentials from env vars (CI / GitHub Actions path)
        Returns True on success.
        """
        logger.info("Starting Gmail authentication...")

        try:
            self.creds = self._load_token()

            if self.creds and self.creds.valid:
                logger.info("✓ Using valid saved Gmail token")
            elif self.creds and self.creds.expired and self.creds.refresh_token:
                logger.info("Refreshing expired Gmail token...")
                self.creds.refresh(Request())
                self._save_token()
            else:
                # Try building from environment variables (GitHub Actions)
                self.creds = self._creds_from_env()
                if not self.creds:
                    logger.error(
                        "Gmail credentials not available.\n"
                        "Set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, and GMAIL_REFRESH_TOKEN "
                        "as environment variables (or place gmail_token.json in the project root)."
                    )
                    return False
                # Immediately refresh to get a valid access token
                self.creds.refresh(Request())
                self._save_token()

            self.service = build("gmail", "v1", credentials=self.creds)
            logger.info("✓ Gmail authenticated successfully!")
            self.authenticated = True
            return True

        except Exception as e:
            logger.error(f"Gmail authentication failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Public fetch methods
    # ------------------------------------------------------------------

    def fetch_threads(
        self,
        max_results: int = 10,
        query: str = "is:unread",
        label_ids: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Return a list of thread summaries matching *query*.

        Args:
            max_results: Maximum number of threads to return.
            query:       Gmail search query (default: unread messages).
            label_ids:   Optional list of label IDs to filter by.
        """
        logger.info(f"Fetching Gmail threads — query='{query}', max={max_results}")
        self._require_auth()

        threads: List[Dict] = []
        page_token: Optional[str] = None

        while len(threads) < max_results:
            batch_size = min(max_results - len(threads), 100)

            def _list(pt=page_token, bs=batch_size):
                params = dict(userId="me", maxResults=bs, q=query)
                if label_ids:
                    params["labelIds"] = label_ids
                if pt:
                    params["pageToken"] = pt
                return self.service.users().threads().list(**params).execute()

            result = _retry(_list)
            page_token = result.get("nextPageToken")

            for thread_stub in result.get("threads", []):
                thread_id = thread_stub["id"]
                summary = self._fetch_thread_summary(thread_id)
                if summary:
                    threads.append(summary)
                if len(threads) >= max_results:
                    break

            if not page_token:
                break

        logger.info(f"✓ Fetched {len(threads)} Gmail threads")
        return threads

    def fetch_messages(self, thread_id: str, limit: int = 50) -> List[Dict]:
        """Return messages from a specific thread."""
        logger.info(f"Fetching messages from thread: {thread_id}")
        self._require_auth()

        def _get():
            return self.service.users().threads().get(
                userId="me", id=thread_id, format="full"
            ).execute()

        try:
            thread = _retry(_get)
        except Exception as e:
            logger.error(f"Failed to fetch thread {thread_id}: {e}")
            return []

        messages = []
        for msg_info in thread.get("messages", [])[:limit]:
            msg = self._parse_message(msg_info, thread_id)
            if msg:
                messages.append(msg)

        logger.info(f"✓ Fetched {len(messages)} messages from thread {thread_id}")
        return messages

    def search_messages(self, contact: str, max_results: int = 20) -> List[Dict]:
        """Search all threads involving a specific contact (name or email)."""
        query = f"from:{contact} OR to:{contact}"
        return self.fetch_threads(max_results=max_results, query=query)

    def list_labels(self) -> List[Dict]:
        """Return all Gmail labels for the authenticated user."""
        self._require_auth()

        def _get():
            return self.service.users().labels().list(userId="me").execute()

        try:
            result = _retry(_get)
            labels = result.get("labels", [])
            logger.info(f"✓ Found {len(labels)} Gmail labels")
            return labels
        except Exception as e:
            logger.error(f"Failed to list labels: {e}")
            return []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_thread_summary(self, thread_id: str) -> Optional[Dict]:
        """Fetch header-only summary for a single thread."""
        def _get():
            return self.service.users().threads().get(
                userId="me", id=thread_id, format="metadata",
                metadataHeaders=["Subject", "From", "Date"]
            ).execute()

        try:
            thread = _retry(_get)
        except Exception as e:
            logger.warning(f"Skipping thread {thread_id}: {e}")
            return None

        messages = thread.get("messages", [])
        if not messages:
            return None

        last = messages[-1]
        headers = {
            h["name"]: h["value"]
            for h in last.get("payload", {}).get("headers", [])
        }

        return {
            "id": thread_id,
            "subject": headers.get("Subject", "(No Subject)"),
            "sender": headers.get("From", "Unknown"),
            "date": headers.get("Date", get_timestamp()),
            "message_count": len(messages),
            "platform": "gmail",
            "fetched_at": get_timestamp(),
        }

    def _parse_message(self, msg_info: Dict, thread_id: str) -> Optional[Dict]:
        """Extract structured data from a raw Gmail message object."""
        try:
            headers = {
                h["name"]: h["value"]
                for h in msg_info.get("payload", {}).get("headers", [])
            }
            body = self._extract_body(msg_info)
            return {
                "id": msg_info.get("id"),
                "thread_id": thread_id,
                "sender": headers.get("From", "Unknown"),
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", get_timestamp()),
                "body": body,
                "platform": "gmail",
                "timestamp": get_timestamp(),
            }
        except Exception as e:
            logger.debug(f"Could not parse message {msg_info.get('id')}: {e}")
            return None

    def _extract_body(self, message: Dict) -> str:
        """Recursively extract the plain-text body from a message payload."""
        def _decode(data: str) -> str:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

        def _walk(payload: Dict) -> Optional[str]:
            mime = payload.get("mimeType", "")
            if mime == "text/plain":
                data = payload.get("body", {}).get("data", "")
                return _decode(data) if data else None
            for part in payload.get("parts", []):
                result = _walk(part)
                if result:
                    return result
            return None

        payload = message.get("payload", {})
        text = _walk(payload)
        return text if text else "(No text body)"

    def _load_token(self) -> Optional[Credentials]:
        if os.path.exists(self.TOKEN_FILE):
            try:
                return Credentials.from_authorized_user_file(self.TOKEN_FILE, SCOPES)
            except Exception as e:
                logger.debug(f"Could not load token file: {e}")
        return None

    def _save_token(self):
        try:
            with open(self.TOKEN_FILE, "w") as f:
                f.write(self.creds.to_json())
            logger.debug(f"Gmail token saved to {self.TOKEN_FILE}")
        except Exception as e:
            logger.warning(f"Could not save Gmail token: {e}")

    def _creds_from_env(self) -> Optional[Credentials]:
        """Build Credentials from environment variables (GitHub Actions / CI)."""
        client_id = os.getenv("GMAIL_CLIENT_ID")
        client_secret = os.getenv("GMAIL_CLIENT_SECRET")
        refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")

        if not all([client_id, client_secret, refresh_token]):
            return None

        return Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )

    def _require_auth(self):
        if not self.authenticated or not self.service:
            raise RuntimeError("GmailFetcher is not authenticated. Call authenticate() first.")
