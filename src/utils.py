"""
Utility functions for Communication Management Tool
"""

import os
import json
import logging
import base64
from typing import Optional, Dict, Any
from datetime import datetime


def setup_logging(log_level: str = None) -> logging.Logger:
    """Setup logging configuration"""
    log_level = log_level or os.getenv("LOG_LEVEL", "INFO")

    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    return logging.getLogger(__name__)


def load_credentials(key: str) -> Optional[str]:
    """Load credential from environment variable"""
    value = os.getenv(key)
    if not value:
        logging.warning(f"Credential not found: {key}")
    return value


def save_session(session_data: Dict[str, Any], filename: str):
    """Save session data to file (encoded for security)"""
    try:
        json_str = json.dumps(session_data)
        encoded = base64.b64encode(json_str.encode()).decode()

        with open(filename, "w") as f:
            f.write(encoded)

        logging.info(f"Session saved to {filename}")
    except Exception as e:
        logging.error(f"Failed to save session: {e}")


def load_session(filename: str) -> Optional[Dict[str, Any]]:
    """Load session data from file (decode from base64)"""
    try:
        if not os.path.exists(filename):
            logging.warning(f"Session file not found: {filename}")
            return None

        with open(filename, "r") as f:
            encoded = f.read()

        json_str = base64.b64decode(encoded).decode()
        return json.loads(json_str)
    except Exception as e:
        logging.error(f"Failed to load session: {e}")
        return None


def format_message(message: Dict[str, Any]) -> str:
    """Format message for display"""
    timestamp = message.get("timestamp", "Unknown")
    sender = message.get("sender", "Unknown")
    body = message.get("body", "")

    return f"[{timestamp}] {sender}: {body}"


def get_timestamp() -> str:
    """Get current timestamp as string"""
    return datetime.now().isoformat()


def is_debug_mode() -> bool:
    """Check if debug mode is enabled"""
    return os.getenv("DEBUG", "False").lower() == "true"
