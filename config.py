"""
Configuration module for Avengers: Doomsday Booking Alert Bot (Telegram Only).
Loads environment variables from .env with secure validation and defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
load_dotenv(BASE_DIR / ".env", override=True)


class Config:
    # -------------------------------------------------------------
    # Telegram Bot Configuration
    # -------------------------------------------------------------
    TELEGRAM_BOT_TOKEN: str = os.getenv(
        "TELEGRAM_BOT_TOKEN",
        "9101491571:AAE8c4qyg7G99aEXFWTjHHjdIYnrQI4jyGI",
    ).strip()
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "5188160752").strip()

    # -------------------------------------------------------------
    # Monitoring Target Configuration
    # -------------------------------------------------------------
    MOVIE_TITLE: str = os.getenv("MOVIE_TITLE", "Avengers: Doomsday").strip()
    CINEMA_NAME: str = os.getenv("CINEMA_NAME", "Ritzy Sha Cinemas").strip()
    CINEMA_CODE: str = os.getenv("CINEMA_CODE", "RZYM").strip()
    LOCATION_CITY: str = os.getenv("LOCATION_CITY", "Madurai").strip()
    LOCATION_STATE: str = os.getenv("LOCATION_STATE", "Tamil Nadu, India").strip()

    # BookMyShow Venue URL (Ritzy Sha Cinemas Madurai)
    BMS_VENUE_URL: str = os.getenv(
        "BMS_VENUE_URL",
        "https://in.bookmyshow.com/cinemas/madurai/ritzy-sha-cinemas-4k-rgb-laser-atmos-madurai/buytickets/RZYM",
    ).strip()

    # Monitoring timing (5 minutes = 300 seconds)
    CHECK_INTERVAL_SECONDS: int = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))
    MONITORING_HORIZON_DAYS: int = int(os.getenv("MONITORING_HORIZON_DAYS", "14"))

    # Database
    DATABASE_PATH: Path = BASE_DIR / os.getenv("DATABASE_NAME", "booking_bot.sqlite")

    # Dashboard Server
    DASHBOARD_HOST: str = os.getenv("DASHBOARD_HOST", "0.0.0.0").strip()
    DASHBOARD_PORT: int = int(os.getenv("DASHBOARD_PORT", "8080"))

    # Optional Proxy Server (e.g. http://user:pass@host:port or residential proxy)
    BMS_PROXY: str = os.getenv("BMS_PROXY", "").strip()

    # Headless mode for Playwright
    HEADLESS_BROWSER: bool = (
        os.getenv("HEADLESS_BROWSER", "true").lower() in ("true", "1", "yes")
    )

    # Logging level
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").strip()

    @classmethod
    def is_telegram_configured(cls) -> bool:
        return bool(cls.TELEGRAM_BOT_TOKEN and cls.TELEGRAM_CHAT_ID)
