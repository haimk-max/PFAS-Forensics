"""
Claude API integration for conversation analysis
Uses claude-sonnet-4-6 with prompt caching and adaptive thinking
"""

import json
import logging
import os
import re
import time
from typing import List, Dict, Optional

import anthropic

logger = logging.getLogger(__name__)

# Stable system prompt — cached to avoid paying full price on every call
_SYSTEM_PROMPT = """You are an expert communication analyst specializing in extracting
actionable insights from conversations. You are precise, concise, and always respond
in valid JSON when asked. You handle conversations from multiple platforms (WhatsApp,
Gmail) and can identify patterns, action items, sentiment, and pending items accurately."""

MODEL = "claude-sonnet-4-6"
MAX_RETRIES = 3
RETRY_BACKOFF = [2, 4, 8]


def _retry(func, retries=MAX_RETRIES, backoff=RETRY_BACKOFF):
    """Retry func with exponential backoff on rate-limit and server errors."""
    last_exc = None
    for attempt in range(retries):
        try:
            return func()
        except anthropic.RateLimitError as e:
            last_exc = e
            retry_after = int(e.response.headers.get("retry-after", backoff[attempt]))
            logger.warning(f"Rate limited. Retrying after {retry_after}s (attempt {attempt + 1})")
            time.sleep(retry_after)
        except anthropic.InternalServerError as e:
            last_exc = e
            wait = backoff[attempt] if attempt < len(backoff) else backoff[-1]
            logger.warning(f"Server error {e.status_code}. Retrying in {wait}s (attempt {attempt + 1})")
            time.sleep(wait)
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.BadRequestError):
            raise  # Non-retryable
    raise last_exc


class ConversationAnalyzer:
    """Analyze conversations using Claude API with prompt caching."""

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.client = anthropic.Anthropic(api_key=api_key)

    def summarize(self, messages: List[Dict]) -> Optional[str]:
        """Summarize a conversation. Uses streaming for long responses."""
        if not messages:
            return "No messages to summarize."

        logger.info("Summarizing conversation...")
        conversation_text = self._format_messages(messages)

        def _call():
            with self.client.messages.stream(
                model=MODEL,
                max_tokens=1024,
                thinking={"type": "adaptive"},
                system=[
                    {
                        "type": "text",
                        "text": _SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Summarize the following conversation in 3–5 sentences. "
                            "Focus on key topics discussed, decisions made, and overall tone.\n\n"
                            f"{conversation_text}"
                        ),
                    }
                ],
            ) as stream:
                return stream.get_final_message()

        try:
            response = _retry(_call)
            summary = next(
                (b.text for b in response.content if b.type == "text"), ""
            )
            logger.info(
                "✓ Summarized — cache_read=%d, cache_write=%d",
                response.usage.cache_read_input_tokens,
                response.usage.cache_creation_input_tokens,
            )
            return summary
        except Exception as e:
            logger.error(f"Failed to summarize: {e}")
            return None

    def extract_action_items(self, messages: List[Dict]) -> List[str]:
        """Extract action items from a conversation."""
        if not messages:
            return []

        logger.info("Extracting action items...")
        conversation_text = self._format_messages(messages)

        def _call():
            return self.client.messages.create(
                model=MODEL,
                max_tokens=512,
                system=[
                    {
                        "type": "text",
                        "text": _SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Extract all action items, tasks, and commitments from the following "
                            "conversation. Return ONLY a valid JSON array of strings, nothing else.\n\n"
                            f"Conversation:\n{conversation_text}\n\n"
                            'Example output: ["Call John by Friday", "Send the report"]'
                        ),
                    }
                ],
            )

        try:
            response = _retry(_call)
            text = next((b.text for b in response.content if b.type == "text"), "[]")
            match = re.search(r"\[.*?\]", text, re.DOTALL)
            if match:
                items = json.loads(match.group())
                logger.info(f"✓ Extracted {len(items)} action items")
                return items
        except Exception as e:
            logger.error(f"Failed to extract action items: {e}")

        return []

    def detect_unanswered(self, messages: List[Dict]) -> List[str]:
        """Detect messages or questions that have not received a response."""
        if not messages:
            return []

        logger.info("Detecting unanswered messages...")
        conversation_text = self._format_messages(messages)

        def _call():
            return self.client.messages.create(
                model=MODEL,
                max_tokens=512,
                system=[
                    {
                        "type": "text",
                        "text": _SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Identify all unanswered questions, requests, or messages that require "
                            "a response in the following conversation. "
                            "Return ONLY a valid JSON array of strings, nothing else.\n\n"
                            f"Conversation:\n{conversation_text}\n\n"
                            'Example output: ["Did you receive the files?", "Can we meet Tuesday?"]'
                        ),
                    }
                ],
            )

        try:
            response = _retry(_call)
            text = next((b.text for b in response.content if b.type == "text"), "[]")
            match = re.search(r"\[.*?\]", text, re.DOTALL)
            if match:
                items = json.loads(match.group())
                logger.info(f"✓ Found {len(items)} unanswered messages")
                return items
        except Exception as e:
            logger.error(f"Failed to detect unanswered messages: {e}")

        return []

    def analyze_sentiment(self, messages: List[Dict]) -> str:
        """Return overall sentiment: 'positive', 'negative', or 'neutral'."""
        if not messages:
            return "neutral"

        logger.info("Analyzing sentiment...")
        conversation_text = self._format_messages(messages)

        def _call():
            return self.client.messages.create(
                model=MODEL,
                max_tokens=10,
                system=[
                    {
                        "type": "text",
                        "text": _SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Analyze the overall sentiment of the conversation below. "
                            "Reply with exactly ONE word: positive, negative, or neutral.\n\n"
                            f"{conversation_text}"
                        ),
                    }
                ],
            )

        try:
            response = _retry(_call)
            raw = next((b.text for b in response.content if b.type == "text"), "neutral")
            sentiment = raw.strip().lower().split()[0]
            if sentiment not in ("positive", "negative", "neutral"):
                sentiment = "neutral"
            logger.info(f"✓ Sentiment: {sentiment}")
            return sentiment
        except Exception as e:
            logger.error(f"Failed to analyze sentiment: {e}")
            return "unknown"

    def ask_question(self, messages: List[Dict], question: str) -> Optional[str]:
        """Answer an arbitrary question about the conversation."""
        if not messages:
            return "No messages to analyze."

        logger.info(f"Answering: {question}")
        conversation_text = self._format_messages(messages)

        def _call():
            with self.client.messages.stream(
                model=MODEL,
                max_tokens=1024,
                thinking={"type": "adaptive"},
                system=[
                    {
                        "type": "text",
                        "text": _SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Conversation:\n{conversation_text}\n\n"
                            f"Question: {question}"
                        ),
                    }
                ],
            ) as stream:
                return stream.get_final_message()

        try:
            response = _retry(_call)
            answer = next((b.text for b in response.content if b.type == "text"), "")
            logger.info("✓ Question answered")
            return answer
        except Exception as e:
            logger.error(f"Failed to answer question: {e}")
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _format_messages(self, messages: List[Dict]) -> str:
        """Format messages into a readable conversation transcript."""
        lines = []
        for msg in messages:
            sender = msg.get("sender", "Unknown")
            body = msg.get("body", "")
            timestamp = msg.get("timestamp", msg.get("date", ""))
            platform = msg.get("platform", "")
            prefix = f"[{platform}] " if platform else ""
            lines.append(f"{prefix}[{timestamp}] {sender}: {body}")
        return "\n".join(lines)
