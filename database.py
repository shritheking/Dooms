"""
Database module for SQLite storage (Telegram-Only Architecture).
Handles persistence for detected showtimes, Telegram alert delivery status,
verification mode (LIVE_VERIFIED, SOURCE_UNAVAILABLE, SIMULATED),
monitoring status metadata, and activity logs with WAL concurrency safety.
"""

import sqlite3
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from config import Config


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Return a configured sqlite3 connection with WAL mode and row factory."""
    path = db_path or Config.DATABASE_PATH
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Optional[Path] = None):
    """Initialize database tables and indexes."""
    conn = get_connection(db_path)
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS detected_shows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cinema_name TEXT NOT NULL,
            cinema_code TEXT NOT NULL,
            movie_title TEXT NOT NULL,
            show_date TEXT NOT NULL,              -- Format: YYYY-MM-DD
            show_time TEXT NOT NULL,              -- Format: 10:15 AM
            screen_name TEXT NOT NULL,            -- e.g. 4K RGB Laser Atmos
            session_id TEXT,                      -- Optional BMS session ID
            booking_status TEXT NOT NULL,         -- AVAILABLE, FILLING_FAST, SOLD_OUT, UNAVAILABLE
            booking_link TEXT NOT NULL,           -- Direct URL
            verification_mode TEXT NOT NULL,      -- LIVE_VERIFIED, SOURCE_UNAVAILABLE, SIMULATED
            first_detected_at TIMESTAMP NOT NULL,
            last_seen_at TIMESTAMP NOT NULL,
            telegram_alert_sent INTEGER DEFAULT 0,
            telegram_alert_time TIMESTAMP,
            alert_error TEXT,
            UNIQUE(cinema_code, movie_title, show_date, show_time, screen_name, verification_mode)
        );

        CREATE INDEX IF NOT EXISTS idx_shows_lookup 
        ON detected_shows(cinema_code, movie_title, show_date, booking_status);

        CREATE TABLE IF NOT EXISTS system_status (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL
        );

        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL,                  -- INFO, WARNING, ERROR, SUCCESS
            event_type TEXT NOT NULL,             -- CHECK, ALERT_TG, SYSTEM, BLOCKED, MANUAL_VERIFY, ERROR
            message TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_logs_time 
        ON activity_logs(created_at DESC);

        CREATE TABLE IF NOT EXISTS verification_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operator_name TEXT NOT NULL,
            show_date TEXT NOT NULL,              -- YYYY-MM-DD
            show_time TEXT NOT NULL,              -- e.g. 06:45 PM
            cinema_code TEXT NOT NULL,
            booking_link TEXT NOT NULL,
            timestamp_ist TEXT NOT NULL,
            ip_address TEXT,
            action TEXT NOT NULL,                 -- VERIFIED_LIVE, REJECTED_VALIDATION, DUPLICATE_SUPPRESSED
            notes TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_audit_time 
        ON verification_audit_log(id DESC);
        """)
        # Automatic migrations for detected_shows if table previously existed
        for col_def in [
            "verification_mode TEXT DEFAULT 'LIVE_VERIFIED'",
            "confirmed_by TEXT",
            "confirmed_at_ist TEXT",
        ]:
            try:
                conn.execute(f"ALTER TABLE detected_shows ADD COLUMN {col_def}")
            except sqlite3.OperationalError:
                pass  # Already exists
    conn.close()


class Database:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Config.DATABASE_PATH
        init_db(self.db_path)

    def record_showtime(self, show: Dict[str, Any]) -> Tuple[int, bool, bool]:
        """
        Record or update a detected showtime.
        Returns: (show_id, is_new_entry, status_changed_to_bookable)
        """
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cinema_code = show.get("cinema_code", Config.CINEMA_CODE)
        movie_title = show.get("movie_title", Config.MOVIE_TITLE)
        show_date = show["show_date"]
        show_time = show["show_time"]
        screen_name = show.get("screen_name", "Audi 1")
        booking_status = show.get("booking_status", "AVAILABLE").upper()
        booking_link = show.get("booking_link", Config.BMS_VENUE_URL)
        session_id = show.get("session_id", "")
        cinema_name = show.get("cinema_name", Config.CINEMA_NAME)
        verification_mode = show.get("verification_mode", "LIVE_VERIFIED").upper()
        confirmed_by = show.get("confirmed_by")
        confirmed_at_ist = show.get("confirmed_at_ist")

        conn = get_connection(self.db_path)
        try:
            with conn:
                cur = conn.execute(
                    """
                    SELECT id, booking_status, telegram_alert_sent
                    FROM detected_shows
                    WHERE cinema_code = ? AND movie_title = ? AND show_date = ? 
                      AND show_time = ? AND screen_name = ? AND verification_mode = ?
                    """,
                    (cinema_code, movie_title, show_date, show_time, screen_name, verification_mode),
                )
                row = cur.fetchone()

                if row is None:
                    cur = conn.execute(
                        """
                        INSERT INTO detected_shows (
                            cinema_name, cinema_code, movie_title, show_date, show_time,
                            screen_name, session_id, booking_status, booking_link,
                            verification_mode, confirmed_by, confirmed_at_ist,
                            first_detected_at, last_seen_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            cinema_name,
                            cinema_code,
                            movie_title,
                            show_date,
                            show_time,
                            screen_name,
                            session_id,
                            booking_status,
                            booking_link,
                            verification_mode,
                            confirmed_by,
                            confirmed_at_ist,
                            now,
                            now,
                        ),
                    )
                    show_id = cur.lastrowid
                    is_bookable = booking_status in ("AVAILABLE", "FILLING_FAST")
                    return show_id, True, is_bookable
                else:
                    show_id = row["id"]
                    prev_status = row["booking_status"]
                    status_changed_to_bookable = (
                        prev_status not in ("AVAILABLE", "FILLING_FAST")
                        and booking_status in ("AVAILABLE", "FILLING_FAST")
                    )

                    conn.execute(
                        """
                        UPDATE detected_shows
                        SET booking_status = ?,
                            booking_link = ?,
                            last_seen_at = ?,
                            session_id = COALESCE(NULLIF(?, ''), session_id),
                            confirmed_by = COALESCE(?, confirmed_by),
                            confirmed_at_ist = COALESCE(?, confirmed_at_ist)
                        WHERE id = ?
                        """,
                        (booking_status, booking_link, now, session_id, confirmed_by, confirmed_at_ist, show_id),
                    )
                    return show_id, False, status_changed_to_bookable
        finally:
            conn.close()

    def get_pending_alerts(self) -> List[Dict[str, Any]]:
        """
        Fetch showtimes that are bookable (AVAILABLE or FILLING_FAST)
        and haven't had an alert dispatched yet.
        """
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute(
                """
                SELECT id, cinema_name, cinema_code, movie_title, show_date, show_time,
                       screen_name, booking_status, booking_link, session_id,
                       verification_mode, confirmed_by, confirmed_at_ist, telegram_alert_sent
                FROM detected_shows
                WHERE booking_status IN ('AVAILABLE', 'FILLING_FAST')
                  AND telegram_alert_sent = 0
                ORDER BY show_date ASC, show_time ASC
                """
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def mark_alert_sent(self, show_id: int):
        """Mark Telegram alert as successfully delivered."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE detected_shows
                    SET telegram_alert_sent = 1,
                        telegram_alert_time = ?
                    WHERE id = ?
                    """,
                    (now, show_id),
                )
        finally:
            conn.close()

    def mark_alert_error(self, show_id: int, error_msg: str):
        """Record delivery failure without marking as sent, enabling future retry."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE detected_shows
                    SET alert_error = ?
                    WHERE id = ?
                    """,
                    (f"[TELEGRAM {now}] {error_msg}", show_id),
                )
        finally:
            conn.close()

    def log_event(
        self,
        level: str,
        event_type: str,
        message: str,
        details: Optional[str] = None,
    ):
        """Record an activity or diagnostic log in SQLite."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO activity_logs (level, event_type, message, details, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (level.upper(), event_type.upper(), message, details, now),
                )
        finally:
            conn.close()

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch latest activity logs."""
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute(
                """
                SELECT id, level, event_type, message, details, created_at
                FROM activity_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def log_verification_audit(
        self,
        operator_name: str,
        show_date: str,
        show_time: str,
        action: str,
        notes: str = "",
        booking_link: str = "",
        cinema_code: str = "RZYM",
        ip_address: Optional[str] = None,
    ):
        """Record an explicit human verification audit log entry with IST timestamp."""
        # Calculate IST timestamp
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        ist_offset = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        now_ist = now_utc.astimezone(ist_offset).strftime("%Y-%m-%d %H:%M:%S IST")

        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO verification_audit_log (
                        operator_name, show_date, show_time, cinema_code,
                        booking_link, timestamp_ist, ip_address, action, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        operator_name,
                        show_date,
                        show_time,
                        cinema_code,
                        booking_link,
                        now_ist,
                        ip_address or "127.0.0.1",
                        action.upper(),
                        notes,
                    ),
                )
        finally:
            conn.close()

    def get_verification_audit_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch audit log history of all verification actions."""
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute(
                """
                SELECT id, operator_name, show_date, show_time, cinema_code,
                       booking_link, timestamp_ist, ip_address, action, notes
                FROM verification_audit_log
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def purge_past_or_test_shows(self):
        """Purge any obsolete past-date or test shows to eliminate false-positive history."""
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    DELETE FROM detected_shows
                    WHERE show_date < '2026-11-20' OR verification_mode = 'SIMULATED'
                    """
                )
        finally:
            conn.close()

    def get_all_detected_shows(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return all detected shows with verification modes for dashboard display."""
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute(
                """
                SELECT id, cinema_name, movie_title, show_date, show_time, screen_name,
                       booking_status, booking_link, verification_mode,
                       confirmed_by, confirmed_at_ist,
                       first_detected_at, last_seen_at,
                       telegram_alert_sent, telegram_alert_time, alert_error
                FROM detected_shows
                ORDER BY show_date DESC, show_time ASC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def set_status(self, key: str, value: str):
        """Upsert a key-value pair in system_status table."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO system_status (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (key, value, now),
                )
        finally:
            conn.close()

    def get_status(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve a value by key from system_status table."""
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute(
                "SELECT value FROM system_status WHERE key = ?", (key,)
            )
            row = cur.fetchone()
            return row["value"] if row else default
        finally:
            conn.close()

    def is_already_alerted(
        self,
        show_date: str,
        show_time: str,
        screen_name: str,
        cinema_code: Optional[str] = None,
        movie_title: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check whether an alert has already been dispatched for this exact showtime.
        Returns: (is_alerted, alert_timestamp)
        """
        code = cinema_code or Config.CINEMA_CODE
        title = movie_title or Config.MOVIE_TITLE
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute(
                """
                SELECT telegram_alert_sent, telegram_alert_time
                FROM detected_shows
                WHERE cinema_code = ? AND movie_title = ? AND show_date = ? 
                  AND show_time = ? AND screen_name = ? AND telegram_alert_sent = 1
                """,
                (code, title, show_date, show_time, screen_name),
            )
            row = cur.fetchone()
            if row:
                return True, row["telegram_alert_time"]
            return False, None
        finally:
            conn.close()

    def get_summary_stats(self) -> Dict[str, Any]:
        """Return aggregated stats with explicit verification status breakdown."""
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_shows,
                    COALESCE(SUM(CASE WHEN booking_status IN ('AVAILABLE', 'FILLING_FAST') THEN 1 ELSE 0 END), 0) as available_shows,
                    COALESCE(SUM(CASE WHEN verification_mode = 'LIVE_VERIFIED' THEN 1 ELSE 0 END), 0) as live_verified_count,
                    COALESCE(SUM(CASE WHEN verification_mode = 'SIMULATED' THEN 1 ELSE 0 END), 0) as simulated_count,
                    COALESCE(SUM(CASE WHEN telegram_alert_sent = 1 THEN 1 ELSE 0 END), 0) as tg_sent
                FROM detected_shows
                """
            )
            stats = dict(cur.fetchone() or {})
            stats["monitoring_status"] = self.get_status("monitoring_status", "SOURCE_UNAVAILABLE")
            stats["source_state"] = self.get_status("source_state", "SOURCE_UNAVAILABLE")
            stats["last_check_time"] = self.get_status("last_check_time", "Never")
            stats["last_check_result"] = self.get_status("last_check_result", "No checks yet")
            stats["last_verification_time"] = self.get_status("last_verification_time", "Not yet verified")
            stats["next_scheduled_check"] = self.get_status("next_scheduled_check", "Pending")
            return stats
        finally:
            conn.close()
