"""
Main orchestrator for Communication Management Tool
Coordinates WhatsApp, Gmail, and Claude API interactions
"""

import os
import json
import logging
from typing import Optional, Dict, List
from dotenv import load_dotenv

from .fetch_whatsapp import WhatsAppFetcher
from .fetch_gmail import GmailFetcher
from .analyze_conversations import ConversationAnalyzer
from .utils import setup_logging, load_credentials

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class CommunicationManager:
    """Main class to manage WhatsApp + Gmail communication"""

    def __init__(self):
        """Initialize all components"""
        self.logger = setup_logging()
        self.whatsapp = WhatsAppFetcher()
        self.gmail = GmailFetcher()
        self.analyzer = ConversationAnalyzer()

    def authenticate_all(self) -> bool:
        """Authenticate with WhatsApp and Gmail"""
        self.logger.info("Starting authentication process...")

        try:
            # Authenticate WhatsApp
            self.logger.info("Authenticating WhatsApp...")
            self.whatsapp.authenticate()
            self.logger.info("✓ WhatsApp authenticated")

            # Authenticate Gmail
            self.logger.info("Authenticating Gmail...")
            self.gmail.authenticate()
            self.logger.info("✓ Gmail authenticated")

            return True
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            return False

    def fetch_all_messages(self) -> Dict[str, List]:
        """Fetch messages from both platforms"""
        self.logger.info("Fetching messages from WhatsApp and Gmail...")

        data = {
            "whatsapp": [],
            "gmail": [],
            "timestamp": None,
        }

        try:
            # Fetch WhatsApp
            self.logger.info("Fetching WhatsApp messages...")
            data["whatsapp"] = self.whatsapp.fetch_chats()

            # Fetch Gmail
            self.logger.info("Fetching Gmail messages...")
            data["gmail"] = self.gmail.fetch_threads()

            data["timestamp"] = str(__import__("datetime").datetime.now())
            self.logger.info(f"✓ Fetched {len(data['whatsapp'])} WhatsApp chats")
            self.logger.info(f"✓ Fetched {len(data['gmail'])} Gmail threads")

            return data
        except Exception as e:
            self.logger.error(f"Failed to fetch messages: {e}")
            return data

    def analyze_contact(self, contact_id: str) -> Dict:
        """Analyze conversations with a specific contact"""
        self.logger.info(f"Analyzing conversations with contact: {contact_id}")

        result = {
            "contact_id": contact_id,
            "summary": None,
            "action_items": [],
            "unanswered": [],
            "sentiment": None,
        }

        try:
            # Get messages for this contact
            messages = self._get_contact_messages(contact_id)

            if not messages:
                self.logger.warning(f"No messages found for {contact_id}")
                return result

            # Analyze with Claude
            result["summary"] = self.analyzer.summarize(messages)
            result["action_items"] = self.analyzer.extract_action_items(messages)
            result["unanswered"] = self.analyzer.detect_unanswered(messages)
            result["sentiment"] = self.analyzer.analyze_sentiment(messages)

            self.logger.info(f"✓ Analysis complete for {contact_id}")
            return result

        except Exception as e:
            self.logger.error(f"Analysis failed for {contact_id}: {e}")
            return result

    def search_conversations(self, query: str) -> List[Dict]:
        """Search for messages matching a query"""
        self.logger.info(f"Searching for: {query}")
        # TODO: Implement search functionality
        return []

    def _get_contact_messages(self, contact_id: str) -> List[Dict]:
        """Get all messages from a contact (both platforms)"""
        # TODO: Implement message retrieval
        return []

    def save_results(self, data: Dict, filename: str = "results.json"):
        """Save analysis results to file"""
        try:
            with open(filename, "w") as f:
                json.dump(data, f, indent=2, default=str)
            self.logger.info(f"✓ Results saved to {filename}")
        except Exception as e:
            self.logger.error(f"Failed to save results: {e}")


def main():
    """Main entry point"""
    manager = CommunicationManager()

    # Authenticate
    if not manager.authenticate_all():
        logger.error("Authentication failed. Exiting.")
        return

    # Fetch messages
    messages = manager.fetch_all_messages()

    # Save results
    manager.save_results(messages)

    logger.info("✓ Communication manager completed successfully")


if __name__ == "__main__":
    main()
