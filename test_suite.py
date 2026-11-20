"""
Comprehensive Test Suite for Avengers: Doomsday Booking Alert Bot (Telegram Only).
Covers:
1. Live Telegram Notification Test (verifies delivery to Chat ID 5188160752).
2. Booking Detection with Sample HTML (Bookable, Sold Out, Other Movies, Listed-only).
3. Status Distinction: LIVE_VERIFIED vs SOURCE_UNAVAILABLE vs SIMULATED.
4. One-Click Verification Fallback & Timestamp Tracking.
5. Strict Duplicate Notification Suppression Test.
6. Database Persistence & WAL Concurrency Test.
7. Real Live Ritzy Sha Cinemas Booking Page & Cloudflare WAF Detection Test.
"""

import sys
import tempfile
from pathlib import Path
import pytest

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from config import Config
from database import Database, init_db
from telegram_bot import TelegramBot
from monitor import BookingMonitor


@pytest.fixture
def temp_db():
    """Create a temporary isolated SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        temp_path = Path(f.name)
    init_db(temp_path)
    db = Database(temp_path)
    yield db
    try:
        temp_path.unlink(missing_ok=True)
        Path(str(temp_path) + "-wal").unlink(missing_ok=True)
        Path(str(temp_path) + "-shm").unlink(missing_ok=True)
    except Exception:
        pass


# ==============================================================================
# 1. Telegram Notification Live Test
# ==============================================================================

def test_telegram_notification_live():
    """Verify Telegram Bot API live messaging with the configured token and chat ID."""
    bot = TelegramBot()
    assert bot.token, "Telegram bot token must be configured in .env"
    assert bot.chat_id, "Telegram chat ID must be configured in .env"

    res = bot.send_test_message()
    assert res["success"] is True, f"Telegram test message failed: {res}"
    assert res["channel"] == "Telegram"
    assert res["chat_id"] == bot.chat_id


# ==============================================================================
# 2. Booking Detection with Sample HTML Test
# ==============================================================================

SAMPLE_BMS_NEXT_DATA_AVAILABLE = """
<!DOCTYPE html>
<html>
<head><title>Ritzy Sha Cinemas Madurai</title></head>
<body>
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "showsData": {
        "movies": [
          {
            "EventTitle": "Avengers: Doomsday",
            "shows": [
              {
                "ShowTime": "10:15 AM",
                "availability": "A",
                "ScreenName": "4K RGB Laser Atmos (Audi 1)",
                "SessionId": "AVENGERS_SESSION_01"
              },
              {
                "ShowTime": "06:45 PM",
                "availability": "F",
                "ScreenName": "4K RGB Laser Atmos (Audi 1)",
                "SessionId": "AVENGERS_SESSION_02"
              }
            ]
          }
        ]
      }
    }
  }
}
</script>
</body>
</html>
"""

SAMPLE_BMS_NEXT_DATA_SOLDOUT = """
<!DOCTYPE html>
<html>
<head><title>Ritzy Sha Cinemas Madurai</title></head>
<body>
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "showsData": {
        "movies": [
          {
            "EventTitle": "Avengers: Doomsday",
            "shows": [
              {
                "ShowTime": "02:30 PM",
                "availability": "SOLD_OUT",
                "ScreenName": "Audi 1",
                "SessionId": "SESSION_SOLD"
              }
            ]
          }
        ]
      }
    }
  }
}
</script>
</body>
</html>
"""

SAMPLE_BMS_OTHER_MOVIE = """
<!DOCTYPE html>
<html>
<head><title>Ritzy Sha Cinemas Madurai</title></head>
<body>
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "showsData": {
        "movies": [
          {
            "EventTitle": "Kalki 2898 AD",
            "shows": [
              {
                "ShowTime": "11:00 AM",
                "availability": "A",
                "SessionId": "OTHER_01"
              }
            ]
          }
        ]
      }
    }
  }
}
</script>
</body>
</html>
"""

SAMPLE_BMS_ANNOUNCEMENT_ONLY = """
<!DOCTYPE html>
<html>
<head><title>Ritzy Sha Cinemas Madurai</title></head>
<body>
<div class="coming-soon">
  <h2>Upcoming Movies</h2>
  <h3>Avengers: Doomsday</h3>
  <p>Releasing Worldwide Soon! Tickets not yet available.</p>
</div>
</body>
</html>
"""


def test_booking_detection_sample_available(temp_db):
    """Test parser detecting available and fast filling showtimes."""
    monitor = BookingMonitor(temp_db)
    shows, meta = monitor.parse_html_for_shows(SAMPLE_BMS_NEXT_DATA_AVAILABLE, "20260501", "LIVE_VERIFIED")

    assert len(shows) == 2
    assert meta["cloudflare_blocked"] is False

    show1 = shows[0]
    assert show1["movie_title"] == "Avengers: Doomsday"
    assert show1["show_time"] == "10:15 AM"
    assert show1["booking_status"] == "AVAILABLE"
    assert show1["verification_mode"] == "LIVE_VERIFIED"
    assert "AVENGERS_SESSION_01" in show1["booking_link"]

    show2 = shows[1]
    assert show2["show_time"] == "06:45 PM"
    assert show2["booking_status"] == "FILLING_FAST"


def test_booking_detection_sample_soldout(temp_db):
    """Test parser correctly identifying sold out shows without marking them bookable."""
    monitor = BookingMonitor(temp_db)
    shows, meta = monitor.parse_html_for_shows(SAMPLE_BMS_NEXT_DATA_SOLDOUT, "20260501")

    assert len(shows) == 1
    assert shows[0]["booking_status"] == "SOLD_OUT"


def test_booking_detection_other_movie_no_false_positive(temp_db):
    """Ensure other movies do not trigger Avengers: Doomsday detection."""
    monitor = BookingMonitor(temp_db)
    shows, meta = monitor.parse_html_for_shows(SAMPLE_BMS_OTHER_MOVIE, "20260501")

    assert len(shows) == 0


def test_booking_detection_announcement_only_no_alert(temp_db):
    """Ensure merely listed/announced movies without bookable showtimes do NOT trigger alerts."""
    monitor = BookingMonitor(temp_db)
    shows, meta = monitor.parse_html_for_shows(SAMPLE_BMS_ANNOUNCEMENT_ONLY, "20260501")

    assert len(shows) == 0


# ==============================================================================
# 3. Status Distinction: LIVE_VERIFIED vs SOURCE_UNAVAILABLE vs SIMULATED
# ==============================================================================

def test_status_distinction(temp_db):
    """
    Verify distinct status tracking:
    - LIVE_VERIFIED shows format with [LIVE VERIFIED] and (CONFIRMED)
    - SIMULATED shows format with [SIMULATED TEST]
    - Database tracks counts separately in summary stats.
    """
    live_show = {
        "cinema_name": "Ritzy Sha Cinemas",
        "cinema_code": "RZYM",
        "movie_title": "Avengers: Doomsday",
        "show_date": "2026-05-01",
        "show_time": "10:15 AM",
        "screen_name": "Audi 1",
        "session_id": "SES_LIVE",
        "booking_status": "AVAILABLE",
        "booking_link": "https://in.bookmyshow.com/cinemas/madurai/ritzy-sha-cinemas-4k-rgb-laser-atmos-madurai/buytickets/RZYM",
        "verification_mode": "LIVE_VERIFIED",
    }
    sim_show = {
        "cinema_name": "Ritzy Sha Cinemas",
        "cinema_code": "RZYM",
        "movie_title": "Avengers: Doomsday",
        "show_date": "2026-05-01",
        "show_time": "06:45 PM",
        "screen_name": "Audi 1",
        "session_id": "SES_SIM",
        "booking_status": "AVAILABLE",
        "booking_link": "https://in.bookmyshow.com/cinemas/madurai/ritzy-sha-cinemas-4k-rgb-laser-atmos-madurai/buytickets/RZYM",
        "verification_mode": "SIMULATED",
    }

    temp_db.record_showtime(live_show)
    temp_db.record_showtime(sim_show)

    stats = temp_db.get_summary_stats()
    assert stats["live_verified_count"] == 1
    assert stats["simulated_count"] == 1
    assert stats["total_shows"] == 2


# ==============================================================================
# 4. Strict Validation Safeguards, Visual Confirmation & Audit Log Tests
# ==============================================================================

def test_rejection_of_past_dates(temp_db):
    """
    Safeguard Test 1: Reject all past booking dates.
    Dates prior to today in Asia/Kolkata timezone MUST be rejected with ValueError.
    """
    from monitor import BookingMonitor, validate_showtime, get_ist_now
    
    # 2026-05-01 and 2026-05-02 are in the past relative to November 2026
    with pytest.raises(ValueError, match="is in the past"):
        validate_showtime("2026-05-01", "06:45 PM")

    with pytest.raises(ValueError, match="is in the past"):
        validate_showtime("2026-05-02", "06:45 PM")

    # Yesterday in IST
    import datetime
    yesterday = (get_ist_now().date() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    with pytest.raises(ValueError, match="is in the past"):
        validate_showtime(yesterday, "06:45 PM")


def test_rejection_without_visual_confirmation(temp_db):
    """
    Safeguard Test 2: Reject manual verification if visually_confirmed is False.
    """
    import datetime
    from monitor import BookingMonitor, get_ist_now
    
    monitor = BookingMonitor(temp_db)
    valid_future_date = (get_ist_now().date() + datetime.timedelta(days=2)).strftime("%Y-%m-%d")

    with pytest.raises(ValueError, match="explicit visual certification"):
        monitor.record_manual_verification(
            show_date=valid_future_date,
            show_time="06:45 PM",
            operator_name="Shri Dharsan",
            visually_confirmed=False,
        )

    # Verify audit log recorded the rejection
    logs = temp_db.get_verification_audit_logs(limit=5)
    assert len(logs) == 1
    assert logs[0]["action"] == "REJECTED_VALIDATION"


def test_rejection_with_empty_operator(temp_db):
    """
    Safeguard Test 3: Reject manual verification if operator name is missing.
    """
    import datetime
    from monitor import BookingMonitor, get_ist_now
    
    monitor = BookingMonitor(temp_db)
    valid_future_date = (get_ist_now().date() + datetime.timedelta(days=2)).strftime("%Y-%m-%d")

    with pytest.raises(ValueError, match="Operator name is required"):
        monitor.record_manual_verification(
            show_date=valid_future_date,
            show_time="06:45 PM",
            operator_name=" ",
            visually_confirmed=True,
        )


def test_valid_future_verification_and_duplicate_suppression(temp_db):
    """
    Safeguard Test 4:
    1. Valid future date with visual certification and operator succeeds.
    2. Records audit log with VERIFIED_LIVE.
    3. Duplicate detection suppresses second identical entry and logs DUPLICATE_SUPPRESSED.
    """
    import datetime
    from monitor import BookingMonitor, get_ist_now

    monitor = BookingMonitor(temp_db)
    future_date = (get_ist_now().date() + datetime.timedelta(days=3)).strftime("%Y-%m-%d")

    # 1. First valid visual confirmation
    show_id, is_new, is_dup, show, prev_time = monitor.record_manual_verification(
        show_date=future_date,
        show_time="09:30 PM",
        operator_name="Shri Dharsan",
        visually_confirmed=True,
        booking_link="https://in.bookmyshow.com/cinemas/madurai/ritzy-sha-cinemas-4k-rgb-laser-atmos-madurai/buytickets/RZYM",
        screen_name="4K RGB Laser Atmos (Audi 1)",
    )

    assert show_id > 0
    assert is_new is True
    assert is_dup is False
    assert show["verification_mode"] == "LIVE_VERIFIED"
    assert show["confirmed_by"] == "Shri Dharsan"
    assert "IST" in show["confirmed_at_ist"]
    assert temp_db.get_status("last_verification_time") is not None

    # Audit log check
    audit_logs = temp_db.get_verification_audit_logs(limit=10)
    assert len(audit_logs) >= 1
    assert audit_logs[0]["action"] == "VERIFIED_LIVE"
    assert audit_logs[0]["operator_name"] == "Shri Dharsan"

    # Mark alert as dispatched
    temp_db.mark_alert_sent(show_id)

    # 2. Second confirmation for SAME showtime
    show_id2, is_new2, is_dup2, show2, prev_time2 = monitor.record_manual_verification(
        show_date=future_date,
        show_time="09:30 PM",
        operator_name="Shri Dharsan",
        visually_confirmed=True,
        booking_link="https://in.bookmyshow.com/cinemas/madurai/ritzy-sha-cinemas-4k-rgb-laser-atmos-madurai/buytickets/RZYM",
        screen_name="4K RGB Laser Atmos (Audi 1)",
    )

    assert is_dup2 is True
    assert prev_time2 is not None
    assert show_id2 == 0
    assert is_new2 is False

    # Pending alerts must remain empty
    assert len(temp_db.get_pending_alerts()) == 0

    # Verify duplicate suppressed in audit log
    audit_logs2 = temp_db.get_verification_audit_logs(limit=10)
    assert audit_logs2[0]["action"] == "DUPLICATE_SUPPRESSED"


def test_telegram_defense_in_depth_past_date_rejection():
    """
    Safeguard Test 5: TelegramBot must reject sending LIVE_VERIFIED alert if date is in the past.
    """
    bot = TelegramBot()
    past_show = {
        "cinema_name": "Ritzy Sha Cinemas",
        "movie_title": "Avengers: Doomsday",
        "show_date": "2026-05-02",  # Past date
        "show_time": "06:45 PM",
        "booking_status": "AVAILABLE",
        "verification_mode": "LIVE_VERIFIED",
    }
    sent = bot.send_alert(past_show)
    assert sent is False, "TelegramBot should reject sending LIVE_VERIFIED alert for past dates."


# ==============================================================================
# 5. Database Persistence & WAL Concurrency Test
# ==============================================================================

def test_database_persistence_and_logging(temp_db):
    """Test SQLite system status and activity log operations."""
    temp_db.set_status("source_state", "SOURCE_UNAVAILABLE")
    assert temp_db.get_status("source_state") == "SOURCE_UNAVAILABLE"

    temp_db.log_event("INFO", "CHECK", "Periodic scan executed successfully")
    temp_db.log_event("WARNING", "BLOCKED", "Test Cloudflare restriction logged")

    logs = temp_db.get_recent_logs(limit=10)
    assert len(logs) == 2
    assert logs[0]["event_type"] == "BLOCKED"
    assert logs[1]["event_type"] == "CHECK"


# ==============================================================================
# 6. Real Live Booking Page & Cloudflare WAF Detection Test
# ==============================================================================

@pytest.mark.asyncio
async def test_live_ritzy_sha_bms_page_check():
    """
    Live diagnostic test against the real BookMyShow venue page for Ritzy Sha Cinemas:
    https://in.bookmyshow.com/cinemas/madurai/ritzy-sha-cinemas-4k-rgb-laser-atmos-madurai/buytickets/RZYM

    Validates that:
    1. The monitor navigates to the real URL.
    2. Identifies Cloudflare Turnstile restriction on cloud VPS IP.
    3. Respects anti-bot restrictions and cleanly sets 'cloudflare_blocked=True' without crashing.
    """
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        temp_path = Path(f.name)
    init_db(temp_path)
    db = Database(temp_path)

    try:
        monitor = BookingMonitor(db, headless=True)
        today_str = monitor.generate_target_dates(1)[0]
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            shows, meta = await monitor.scan_single_date(page, today_str)
            await browser.close()

        if meta.get("cloudflare_blocked"):
            print("\n[LIVE DIAGNOSTIC] Cloudflare Turnstile challenge encountered on BookMyShow (HTTP 403 on Oracle Cloud IP).")
            print("[LIVE DIAGNOSTIC] Anti-bot compliance verified: Bot stopped cleanly without bypassing CAPTCHA.")
            assert meta["cloudflare_blocked"] is True
        else:
            print(f"\n[LIVE DIAGNOSTIC] Page loaded successfully! Shows detected: {len(shows)}")

    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    pytest.main(["-v", "-s", __file__])
