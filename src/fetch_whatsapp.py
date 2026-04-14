"""
WhatsApp Web fetcher using Selenium
Handles authentication and message retrieval with retry logic and session persistence
"""

import os
import json
import logging
import time
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

from .utils import save_session, load_session, get_timestamp

logger = logging.getLogger(__name__)

QR_WAIT_TIMEOUT = 120       # seconds to wait for QR code scan
PAGE_LOAD_TIMEOUT = 30      # seconds to wait for page elements
MAX_RETRIES = 3             # max retry attempts
RETRY_BACKOFF = [2, 4, 8]   # exponential backoff in seconds


def _retry(func, retries=MAX_RETRIES, backoff=RETRY_BACKOFF):
    """Run func with exponential backoff on failure"""
    for attempt in range(retries):
        try:
            return func()
        except Exception as e:
            if attempt == retries - 1:
                raise
            wait = backoff[attempt] if attempt < len(backoff) else backoff[-1]
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
            time.sleep(wait)


def _build_driver() -> webdriver.Chrome:
    """Build a headless Chrome driver"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,800")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    return driver


class WhatsAppFetcher:
    """Fetch data from WhatsApp Web with retry logic and session persistence"""

    def __init__(self):
        self.driver = None
        self.session_file = os.getenv("WHATSAPP_SESSION_FILE", "whatsapp_session.json")
        self.authenticated = False

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self) -> bool:
        """Authenticate with WhatsApp using QR code.

        Logs a clear message so the QR code URL can be scanned from
        GitHub Actions logs or a local terminal.
        """
        logger.info("Starting WhatsApp authentication...")

        try:
            self.driver = _build_driver()
            self.driver.get("https://web.whatsapp.com")

            # Try to restore a saved session first
            if self._inject_cookies():
                logger.info("Session cookies injected - refreshing page...")
                self.driver.refresh()
                if self._wait_for_chat_list(timeout=20):
                    logger.info("✓ Restored previous WhatsApp session")
                    self.authenticated = True
                    return True
                logger.info("Saved session expired - falling back to QR code")

            # Fresh login: wait for user to scan QR code
            logger.info(
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "  ACTION REQUIRED: Open WhatsApp on your phone\n"
                "  and scan the QR code at https://web.whatsapp.com\n"
                "  Waiting up to %d seconds...\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                QR_WAIT_TIMEOUT,
            )

            if not self._wait_for_chat_list(timeout=QR_WAIT_TIMEOUT):
                logger.error("QR code was not scanned in time")
                return False

            logger.info("✓ WhatsApp authenticated successfully!")
            self.authenticated = True
            self._save_session()
            return True

        except Exception as e:
            logger.error(f"WhatsApp authentication failed: {e}")
            return False
        finally:
            self._quit_driver()

    # ------------------------------------------------------------------
    # Public fetch methods
    # ------------------------------------------------------------------

    def fetch_chats(self) -> List[Dict]:
        """Return a list of all visible chats."""
        logger.info("Fetching WhatsApp chats...")

        def _fetch():
            self.driver = _build_driver()
            self._open_whatsapp()
            wait = WebDriverWait(self.driver, PAGE_LOAD_TIMEOUT)
            wait.until(
                EC.presence_of_all_elements_located((By.XPATH, "//div[@data-testid='chat']"))
            )
            elements = self.driver.find_elements(By.XPATH, "//div[@data-testid='chat']")

            chats = []
            for el in elements:
                chat = self._extract_chat(el)
                if chat:
                    chats.append(chat)
            return chats

        try:
            chats = _retry(_fetch)
            logger.info(f"✓ Fetched {len(chats)} WhatsApp chats")
            return chats
        except Exception as e:
            logger.error(f"Failed to fetch chats after retries: {e}")
            return []
        finally:
            self._quit_driver()

    def fetch_messages(self, chat_id: str, limit: int = 50) -> List[Dict]:
        """Return the last `limit` messages from a named chat."""
        logger.info(f"Fetching messages from chat: {chat_id}")

        def _fetch():
            self.driver = _build_driver()
            self._open_whatsapp()
            wait = WebDriverWait(self.driver, PAGE_LOAD_TIMEOUT)

            # Click into the target chat
            chat_el = wait.until(
                EC.element_to_be_clickable((By.XPATH, f"//span[@title='{chat_id}']"))
            )
            chat_el.click()

            # Wait for messages to load
            wait.until(
                EC.presence_of_all_elements_located(
                    (By.XPATH, "//div[@data-testid='msg-container']")
                )
            )
            msg_elements = self.driver.find_elements(
                By.XPATH, "//div[@data-testid='msg-container']"
            )

            messages = []
            for el in msg_elements[:limit]:
                msg = self._extract_message(el, chat_id)
                if msg:
                    messages.append(msg)
            return messages

        try:
            messages = _retry(_fetch)
            logger.info(f"✓ Fetched {len(messages)} messages from '{chat_id}'")
            return messages
        except Exception as e:
            logger.error(f"Failed to fetch messages from '{chat_id}' after retries: {e}")
            return []
        finally:
            self._quit_driver()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _open_whatsapp(self):
        """Navigate to WhatsApp Web and restore cookies if available."""
        self.driver.get("https://web.whatsapp.com")
        if self._inject_cookies():
            self.driver.refresh()
        if not self._wait_for_chat_list(timeout=PAGE_LOAD_TIMEOUT):
            raise TimeoutException("WhatsApp chat list did not load. Re-authentication needed.")

    def _wait_for_chat_list(self, timeout: int) -> bool:
        """Return True when the chat list is visible within `timeout` seconds."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, "//div[@data-testid='chat-list']"))
            )
            return True
        except TimeoutException:
            return False

    def _extract_chat(self, element) -> Optional[Dict]:
        """Extract structured data from a chat list element."""
        try:
            name = element.find_element(By.XPATH, ".//span[@title]").get_attribute("title")
            preview = element.text
            return {
                "id": name,
                "name": name,
                "preview": preview,
                "platform": "whatsapp",
                "fetched_at": get_timestamp(),
            }
        except Exception as e:
            logger.debug(f"Could not extract chat element: {e}")
            return None

    def _extract_message(self, element, chat_id: str) -> Optional[Dict]:
        """Extract structured data from a message element."""
        try:
            sender = element.find_element(
                By.XPATH, ".//span[@data-testid='msg-meta']"
            ).text
            body = element.find_element(
                By.XPATH, ".//span[contains(@class,'selectable-text')]"
            ).text
            return {
                "chat_id": chat_id,
                "sender": sender,
                "body": body,
                "platform": "whatsapp",
                "timestamp": get_timestamp(),
            }
        except Exception as e:
            logger.debug(f"Could not extract message element: {e}")
            return None

    def _save_session(self):
        """Persist browser cookies for the next run."""
        try:
            if self.driver:
                cookies = self.driver.get_cookies()
                save_session({"cookies": cookies}, self.session_file)
                logger.info(f"Session saved to {self.session_file}")
        except Exception as e:
            logger.warning(f"Could not save session: {e}")

    def _inject_cookies(self) -> bool:
        """Load saved cookies into the current browser session."""
        data = load_session(self.session_file)
        if not data or "cookies" not in data:
            return False
        try:
            for cookie in data["cookies"]:
                # Selenium requires the domain to match before adding cookies
                try:
                    self.driver.add_cookie(cookie)
                except Exception:
                    pass  # some cookies may be rejected - that's fine
            return True
        except Exception as e:
            logger.debug(f"Cookie injection failed: {e}")
            return False

    def _quit_driver(self):
        """Safely quit the Selenium driver."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
