"""
Claude API integration for conversation analysis
Handles summarization, action item extraction, and sentiment analysis
"""

import os
import json
import logging
from typing import List, Dict, Optional
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class ConversationAnalyzer:
    """Analyze conversations using Claude API"""

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.client = Anthropic()
        self.model = "claude-3-5-sonnet-20241022"

    def summarize(self, messages: List[Dict]) -> Optional[str]:
        """Summarize a conversation using Claude"""
        logger.info("Summarizing conversation...")

        if not messages:
            return "No messages to summarize"

        try:
            # Format messages for Claude
            conversation_text = self._format_messages(messages)

            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system="You are a helpful assistant that summarizes conversations concisely and accurately.",
                messages=[
                    {
                        "role": "user",
                        "content": f"Please summarize this conversation:\n\n{conversation_text}",
                    }
                ],
            )

            summary = message.content[0].text
            logger.info("✓ Conversation summarized")
            return summary

        except Exception as e:
            logger.error(f"Failed to summarize conversation: {e}")
            return None

    def extract_action_items(self, messages: List[Dict]) -> List[str]:
        """Extract action items from a conversation"""
        logger.info("Extracting action items...")

        if not messages:
            return []

        try:
            conversation_text = self._format_messages(messages)

            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system="You are a helpful assistant that extracts action items from conversations. Return only a JSON list of action items.",
                messages=[
                    {
                        "role": "user",
                        "content": f"Extract action items from this conversation and return as a JSON list:\n\n{conversation_text}\n\nReturn ONLY a valid JSON array of strings.",
                    }
                ],
            )

            try:
                response_text = message.content[0].text
                # Try to parse JSON from response
                import re

                json_match = re.search(r"\[.*\]", response_text, re.DOTALL)
                if json_match:
                    action_items = json.loads(json_match.group())
                    logger.info(f"✓ Extracted {len(action_items)} action items")
                    return action_items
            except json.JSONDecodeError:
                logger.warning("Could not parse action items as JSON")

            return []

        except Exception as e:
            logger.error(f"Failed to extract action items: {e}")
            return []

    def detect_unanswered(self, messages: List[Dict]) -> List[str]:
        """Detect messages that need a response"""
        logger.info("Detecting unanswered messages...")

        if not messages:
            return []

        try:
            conversation_text = self._format_messages(messages)

            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system="You are a helpful assistant that identifies questions and messages requiring responses. Return only a JSON list.",
                messages=[
                    {
                        "role": "user",
                        "content": f"Identify messages in this conversation that require a response (questions, requests, etc). Return as a JSON array:\n\n{conversation_text}\n\nReturn ONLY a valid JSON array.",
                    }
                ],
            )

            try:
                response_text = message.content[0].text
                import re

                json_match = re.search(r"\[.*\]", response_text, re.DOTALL)
                if json_match:
                    unanswered = json.loads(json_match.group())
                    logger.info(f"✓ Found {len(unanswered)} unanswered messages")
                    return unanswered
            except json.JSONDecodeError:
                logger.warning("Could not parse unanswered messages as JSON")

            return []

        except Exception as e:
            logger.error(f"Failed to detect unanswered messages: {e}")
            return []

    def analyze_sentiment(self, messages: List[Dict]) -> Optional[str]:
        """Analyze overall sentiment of a conversation"""
        logger.info("Analyzing sentiment...")

        if not messages:
            return "neutral"

        try:
            conversation_text = self._format_messages(messages)

            message = self.client.messages.create(
                model=self.model,
                max_tokens=100,
                system="You are a sentiment analyst. Return only one word: positive, negative, or neutral.",
                messages=[
                    {
                        "role": "user",
                        "content": f"Analyze the overall sentiment of this conversation and respond with only ONE word (positive, negative, or neutral):\n\n{conversation_text}",
                    }
                ],
            )

            sentiment = message.content[0].text.strip().lower()
            logger.info(f"✓ Sentiment analyzed: {sentiment}")
            return sentiment

        except Exception as e:
            logger.error(f"Failed to analyze sentiment: {e}")
            return "unknown"

    def ask_question(self, messages: List[Dict], question: str) -> Optional[str]:
        """Ask a question about a conversation"""
        logger.info(f"Answering question: {question}")

        if not messages:
            return "No messages to analyze"

        try:
            conversation_text = self._format_messages(messages)

            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system="You are a helpful assistant answering questions about conversations.",
                messages=[
                    {
                        "role": "user",
                        "content": f"Here's a conversation:\n\n{conversation_text}\n\nQuestion: {question}",
                    }
                ],
            )

            answer = message.content[0].text
            logger.info("✓ Question answered")
            return answer

        except Exception as e:
            logger.error(f"Failed to answer question: {e}")
            return None

    def _format_messages(self, messages: List[Dict]) -> str:
        """Format messages for Claude API"""
        formatted = []

        for msg in messages:
            sender = msg.get("sender", "Unknown")
            body = msg.get("body", "")
            timestamp = msg.get("timestamp", "")

            formatted.append(f"[{timestamp}] {sender}: {body}")

        return "\n".join(formatted)
