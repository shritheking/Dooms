"""
Telegram Bot integration module for Avengers: Doomsday Booking Alert Bot.
Handles sending alerts, test notifications, and polling for user commands (/start, /status, /test, /check).
Clearly distinguishes LIVE_VERIFIED alerts from SIMULATED test alerts to prevent false positives.
"""

import time
import logging
import threading
import requests
from typing import Optional, Dict, Any, Callable
from config import Config

logger = logging.getLogger("telegram_bot")


class TelegramBot:
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or Config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or Config.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self._is_polling = False
        self._polling_thread: Optional[threading.Thread] = None

    def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: Optional[str] = None,
        disable_web_page_preview: bool = False,
    ) -> bool:
        """Send a message via Telegram Bot API."""
        target_chat = chat_id or self.chat_id
        if not self.token or not target_chat:
            logger.warning("Telegram credentials not configured. Skipping message.")
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            resp = requests.post(url, json=payload, timeout=15)
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                logger.info(f"Telegram message successfully sent to chat {target_chat}")
                return True
            else:
                logger.error(f"Telegram API error: {data}")
                return False
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def send_alert(self, show: Dict[str, Any], chat_id: Optional[str] = None) -> bool:
        """
        Send formatted booking alert.
        Strictly differentiates between LIVE_VERIFIED and SIMULATED to avoid false positives.
        """
        cinema = show.get("cinema_name", Config.CINEMA_NAME)
        location = Config.LOCATION_CITY
        movie = show.get("movie_title", Config.MOVIE_TITLE)
        show_date = show.get("show_date", "N/A")
        show_time = show.get("show_time", "N/A")
        status = show.get("booking_status", "AVAILABLE")
        booking_link = show.get("booking_link", Config.BMS_VENUE_URL)
        mode = show.get("verification_mode", "LIVE_VERIFIED").upper()

        if mode == "SIMULATED":
            message = (
                f"🧪 [SIMULATED TEST] AVENGERS: DOOMSDAY ALERT TEST\n\n"
                f"Cinema: {cinema}\n"
                f"Location: {location}\n"
                f"Movie: {movie}\n"
                f"Show Date: {show_date}\n"
                f"Showtime: {show_time}\n"
                f"Status: SIMULATED (No real booking opened)\n\n"
                f"⚠️ Note: This is an intentional simulation to test notification delivery.\n"
                f"Direct link: {booking_link}"
            )
        else:
            # LIVE_VERIFIED
            message = (
                f"🚨 AVENGERS: DOOMSDAY BOOKING OPEN! [LIVE VERIFIED]\n\n"
                f"Cinema: {cinema}\n"
                f"Location: {location}\n"
                f"Movie: {movie}\n"
                f"Show Date: {show_date}\n"
                f"Showtime: {show_time}\n"
                f"Booking Status: {status} (CONFIRMED)\n\n"
                f"🎟️ BOOK YOUR TICKETS:\n"
                f"{booking_link}"
            )

        return self.send_message(
            text=message,
            chat_id=chat_id,
            disable_web_page_preview=False,
        )

    def send_test_message(self, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """Send an interactive test verification message."""
        test_show = {
            "cinema_name": Config.CINEMA_NAME,
            "movie_title": Config.MOVIE_TITLE,
            "show_date": "2026-05-01",
            "show_time": "07:00 PM",
            "booking_status": "AVAILABLE",
            "booking_link": Config.BMS_VENUE_URL,
            "verification_mode": "SIMULATED",
        }
        success = self.send_alert(test_show, chat_id=chat_id)
        return {
            "success": success,
            "channel": "Telegram",
            "chat_id": chat_id or self.chat_id,
            "message": "Test alert dispatched" if success else "Failed to send test alert",
        }

    def start_polling(self, db, on_manual_check: Optional[Callable] = None):
        """Start long-polling in a background thread to handle bot commands."""
        if not self.token:
            logger.warning("Telegram Bot Token is missing. Polling thread disabled.")
            return

        self._is_polling = True
        self._polling_thread = threading.Thread(
            target=self._poll_loop,
            args=(db, on_manual_check),
            daemon=True,
            name="TelegramBotPolling",
        )
        self._polling_thread.start()
        logger.info("Telegram command polling thread started.")

    def stop_polling(self):
        """Stop command polling loop."""
        self._is_polling = False

    def _poll_loop(self, db, on_manual_check: Optional[Callable]):
        last_offset = 0
        while self._is_polling:
            try:
                url = f"{self.base_url}/getUpdates?offset={last_offset}&timeout=20"
                resp = requests.get(url, timeout=30)
                if resp.status_code != 200:
                    time.sleep(5)
                    continue

                data = resp.json()
                if not data.get("ok"):
                    time.sleep(5)
                    continue

                for update in data.get("result", []):
                    last_offset = max(last_offset, update.get("update_id", 0) + 1)
                    message = update.get("message") or update.get("edited_message")
                    if not message:
                        continue

                    chat_id = str(message.get("chat", {}).get("id"))
                    text = (message.get("text") or "").strip()

                    self._handle_command(chat_id, text, db, on_manual_check)

            except requests.exceptions.RequestException:
                time.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected error in Telegram polling: {e}")
                time.sleep(5)

    def _handle_command(
        self,
        chat_id: str,
        text: str,
        db,
        on_manual_check: Optional[Callable],
    ):
        cmd = text.split()[0].lower() if text else ""

        if cmd == "/start":
            welcome_msg = (
                f"🛡️ *Avengers: Doomsday Booking Alert Bot*\n\n"
                f"Target Cinema:\n"
                f"• *Movie:* {Config.MOVIE_TITLE}\n"
                f"• *Cinema:* {Config.CINEMA_NAME} ({Config.CINEMA_CODE})\n"
                f"• *Location:* {Config.LOCATION_CITY}, {Config.LOCATION_STATE}\n"
                f"• *Cadence:* Every {Config.CHECK_INTERVAL_SECONDS // 60} mins\n\n"
                f"Status Verification Modes:\n"
                f"🟢 *LIVE VERIFIED* — Real ticket bookings confirmed.\n"
                f"🟠 *SOURCE UNAVAILABLE* — Cloudflare restriction on cloud VPS IP.\n"
                f"🟣 *SIMULATED* — Test simulation format.\n\n"
                f"Commands:\n"
                f"/status - View current monitor status & diagnosis\n"
                f"/test - Send a test simulation alert\n"
                f"/check - Trigger an immediate booking check\n"
            )
            self.send_message(welcome_msg, chat_id=chat_id, parse_mode="Markdown")

        elif cmd == "/status":
            stats = db.get_summary_stats()
            status_text = (
                f"📊 *System Monitoring Telemetry*\n\n"
                f"• *Source State:* `{stats.get('source_state', 'SOURCE_UNAVAILABLE')}`\n"
                f"• *Last Check Time:* `{stats.get('last_check_time', 'Never')}`\n"
                f"• *Last Result:* `{stats.get('last_check_result', 'N/A')}`\n\n"
                f"Showtimes Breakdown:\n"
                f"• *Live Verified Shows:* `{stats.get('live_verified_count', 0)}`\n"
                f"• *Simulated Shows:* `{stats.get('simulated_count', 0)}`\n"
                f"• *Telegram Alerts Delivered:* `{stats.get('tg_sent', 0)}`\n\n"
                f"ℹ️ *Cloudflare Status:* BookMyShow restricts automated cloud VPS requests. Use the manual verification fallback on the dashboard or RDP browser to confirm live openings."
            )
            self.send_message(status_text, chat_id=chat_id, parse_mode="Markdown")

        elif cmd == "/test":
            self.send_message("🧪 Sending test simulation alert...", chat_id=chat_id)
            self.send_test_message(chat_id=chat_id)

        elif cmd == "/check":
            self.send_message(
                "🔍 Checking BookMyShow venue page...", chat_id=chat_id
            )
            if on_manual_check:
                threading.Thread(target=on_manual_check, daemon=True).start()
            else:
                self.send_message("Manual check trigger not attached.", chat_id=chat_id)
