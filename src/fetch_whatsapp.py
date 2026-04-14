"""
WhatsApp Web fetcher using Selenium
Handles authentication and message retrieval
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
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

from .utils import save_session, load_session, get_timestamp

logger = logging.getLogger(__name__)


class WhatsAppFetcher:
    """Fetch data from WhatsApp Web"""

    def __init__(self):
        self.driver = None
        self.session_file = os.getenv("WHATSAPP_SESSION_FILE", "whatsapp_session.json")
        self.authenticated = False

    def authenticate(self) -> bool:
        """Authenticate with WhatsApp using QR code"""
        logger.info("Starting WhatsApp authentication...")

        try:
            # Initialize Chrome in headless mode
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)

            # Navigate to WhatsApp Web
            self.driver.get("https://web.whatsapp.com")
            logger.info("WhatsApp Web opened. Waiting for QR code scan...")

            # Wait for authentication (max 120 seconds)
            # This is where the user scans the QR code
            wait = WebDriverWait(self.driver, 120)

            # Wait for chat list to be visible (indicates successful login)
            wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@data-testid='chat-list']")
                )
            )

            logger.info("✓ WhatsApp authentication successful!")
            self.authenticated = True

            # Save session
            self._save_session()

            return True

        except Exception as e:
            logger.error(f"WhatsApp authentication failed: {e}")
            return False
        finally:
            if self.driver:
                self.driver.quit()

    def fetch_chats(self) -> List[Dict]:
        """Fetch all chats from WhatsApp"""
        logger.info("Fetching WhatsApp chats...")

        if not self.authenticated:
            logger.warning("Not authenticated. Attempting to restore session...")
            if not self._restore_session():
                return []

        chats = []

        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.get("https://web.whatsapp.com")

            # Wait for chat list
            wait = WebDriverWait(self.driver, 30)
            wait.until(
                EC.presence_of_all_elements_located((By.XPATH, "//div[@data-testid='chat']"))
            )

            # Get all chats
            chat_elements = self.driver.find_elements(By.XPATH, "//div[@data-testid='chat']")

            for chat_element in chat_elements:
                try:
                    chat_name = chat_element.find_element(
                        By.XPATH, ".//span[@title]"
                    ).get_attribute("title")
                    chat_preview = chat_element.text

                    chats.append(
                        {
                            "id": chat_name,
                            "name": chat_name,
                            "preview": chat_preview,
                            "platform": "whatsapp",
                            "fetched_at": get_timestamp(),
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to extract chat: {e}")
                    continue

            logger.info(f"✓ Fetched {len(chats)} WhatsApp chats")
            return chats

        except Exception as e:
            logger.error(f"Failed to fetch chats: {e}")
            return chats
        finally:
            if self.driver:
                self.driver.quit()

    def fetch_messages(self, chat_id: str, limit: int = 50) -> List[Dict]:
        """Fetch messages from a specific chat"""
        logger.info(f"Fetching messages from chat: {chat_id}")

        messages = []

        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.get("https://web.whatsapp.com")

            # Wait for chat list and click on chat
            wait = WebDriverWait(self.driver, 30)
            chat_element = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, f"//span[@title='{chat_id}']")
                )
            )
            chat_element.click()

            # Wait for messages to load
            wait.until(
                EC.presence_of_all_elements_located(
                    (By.XPATH, "//div[@data-testid='msg-container']")
                )
            )

            # Get messages
            message_elements = self.driver.find_elements(
                By.XPATH, "//div[@data-testid='msg-container']"
            )

            for msg_element in message_elements[:limit]:
                try:
                    sender = msg_element.find_element(By.XPATH, ".//span[@data-testid='msg-meta']").text
                    body = msg_element.find_element(By.XPATH, ".//span[@class='selectable-text']").text

                    messages.append(
                        {
                            "chat_id": chat_id,
                            "sender": sender,
                            "body": body,
                            "platform": "whatsapp",
                            "timestamp": get_timestamp(),
                        }
                    )
                except Exception as e:
                    logger.debug(f"Failed to extract message: {e}")
                    continue

            logger.info(f"✓ Fetched {len(messages)} messages from {chat_id}")
            return messages

        except Exception as e:
            logger.error(f"Failed to fetch messages from {chat_id}: {e}")
            return messages
        finally:
            if self.driver:
                self.driver.quit()

    def _save_session(self):
        """Save WhatsApp session for reuse"""
        # Note: WhatsApp Web.js doesn't allow direct session saving,
        # but Selenium cookies can be used
        try:
            if self.driver:
                cookies = self.driver.get_cookies()
                save_session({"cookies": cookies}, self.session_file)
                logger.info("Session saved")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")

    def _restore_session(self) -> bool:
        """Restore WhatsApp session from saved file"""
        # Note: Session restoration requires re-scanning QR code
        # This is a placeholder for future enhancement
        logger.warning("Session restoration not yet implemented for Selenium")
        return False
