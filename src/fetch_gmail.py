"""
Gmail API fetcher using official Google API
Handles OAuth authentication and message retrieval
"""

import os
import json
import logging
from typing import List, Dict, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.oauthlib.flow import InstalledAppFlow
from google.api_core import retry
from google.api_core.gapic_v1 import client_info as grpc_client_info
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .utils import save_session, load_session, get_timestamp

logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailFetcher:
    """Fetch data from Gmail using official API"""

    def __init__(self):
        self.service = None
        self.creds = None
        self.authenticated = False

    def authenticate(self) -> bool:
        """Authenticate with Gmail using OAuth 2.0"""
        logger.info("Starting Gmail authentication...")

        try:
            # Check for saved token
            if os.path.exists("gmail_token.json"):
                self.creds = Credentials.from_authorized_user_file("gmail_token.json", SCOPES)

            # If not valid, refresh or get new
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    logger.info("Refreshing Gmail token...")
                    self.creds.refresh(Request())
                else:
                    logger.error(
                        "Gmail OAuth credentials not found. "
                        "Set up credentials in Google Cloud Console."
                    )
                    return False

                # Save the refreshed token
                with open("gmail_token.json", "w") as token:
                    token.write(self.creds.to_json())

            # Build Gmail service
            self.service = build("gmail", "v1", credentials=self.creds)
            logger.info("✓ Gmail authentication successful!")
            self.authenticated = True

            return True

        except Exception as e:
            logger.error(f"Gmail authentication failed: {e}")
            return False

    def fetch_threads(self, max_results: int = 10) -> List[Dict]:
        """Fetch email threads from Gmail"""
        logger.info(f"Fetching Gmail threads (max: {max_results})...")

        if not self.authenticated or not self.service:
            logger.error("Not authenticated with Gmail")
            return []

        threads = []

        try:
            # Get list of threads
            results = self.service.users().threads().list(
                userId="me",
                maxResults=max_results,
                q="is:unread",  # Get unread emails
            ).execute()

            thread_list = results.get("threads", [])

            for thread_info in thread_list:
                try:
                    thread_id = thread_info.get("id")

                    # Get thread details
                    thread = self.service.users().threads().get(
                        userId="me",
                        id=thread_id,
                        format="full",
                    ).execute()

                    # Extract sender and subject
                    messages = thread.get("messages", [])
                    if messages:
                        last_message = messages[-1]
                        headers = last_message.get("payload", {}).get("headers", [])

                        subject = next(
                            (h.get("value") for h in headers if h.get("name") == "Subject"),
                            "No Subject"
                        )
                        sender = next(
                            (h.get("value") for h in headers if h.get("name") == "From"),
                            "Unknown"
                        )

                        threads.append(
                            {
                                "id": thread_id,
                                "subject": subject,
                                "sender": sender,
                                "message_count": len(messages),
                                "platform": "gmail",
                                "fetched_at": get_timestamp(),
                            }
                        )

                except Exception as e:
                    logger.warning(f"Failed to process thread {thread_info.get('id')}: {e}")
                    continue

            logger.info(f"✓ Fetched {len(threads)} Gmail threads")
            return threads

        except HttpError as error:
            logger.error(f"An error occurred: {error}")
            return threads

    def fetch_messages(self, thread_id: str, limit: int = 50) -> List[Dict]:
        """Fetch messages from a specific thread"""
        logger.info(f"Fetching messages from thread: {thread_id}")

        if not self.authenticated or not self.service:
            logger.error("Not authenticated with Gmail")
            return []

        messages = []

        try:
            # Get thread
            thread = self.service.users().threads().get(
                userId="me",
                id=thread_id,
                format="full",
            ).execute()

            # Extract messages
            for message_info in thread.get("messages", [])[:limit]:
                try:
                    msg_id = message_info.get("id")
                    headers = message_info.get("payload", {}).get("headers", [])

                    sender = next(
                        (h.get("value") for h in headers if h.get("name") == "From"),
                        "Unknown"
                    )
                    subject = next(
                        (h.get("value") for h in headers if h.get("name") == "Subject"),
                        ""
                    )
                    date = next(
                        (h.get("value") for h in headers if h.get("name") == "Date"),
                        get_timestamp()
                    )

                    # Extract message body
                    body = self._extract_message_body(message_info)

                    messages.append(
                        {
                            "id": msg_id,
                            "thread_id": thread_id,
                            "sender": sender,
                            "subject": subject,
                            "body": body,
                            "date": date,
                            "platform": "gmail",
                            "timestamp": get_timestamp(),
                        }
                    )

                except Exception as e:
                    logger.warning(f"Failed to extract message {message_info.get('id')}: {e}")
                    continue

            logger.info(f"✓ Fetched {len(messages)} messages from thread {thread_id}")
            return messages

        except HttpError as error:
            logger.error(f"An error occurred: {error}")
            return messages

    def _extract_message_body(self, message: Dict) -> str:
        """Extract the text body from a Gmail message"""
        try:
            payload = message.get("payload", {})

            # Check if message has parts (multipart)
            if "parts" in payload:
                for part in payload.get("parts", []):
                    if part.get("mimeType") == "text/plain":
                        data = part.get("body", {}).get("data", "")
                        if data:
                            import base64
                            return base64.urlsafe_b64decode(data).decode("utf-8")
            else:
                # Simple message without parts
                data = payload.get("body", {}).get("data", "")
                if data:
                    import base64
                    return base64.urlsafe_b64decode(data).decode("utf-8")

            return "(No text body)"

        except Exception as e:
            logger.debug(f"Failed to extract message body: {e}")
            return "(Could not extract body)"
