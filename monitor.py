"""
Monitoring engine for Avengers: Doomsday at Ritzy Sha Cinemas, Madurai.
Uses Playwright and BeautifulSoup/HTML parsing to check showtimes across dates.
Enforces strict anti-bot compliance: NEVER bypasses Cloudflare CAPTCHAs or anti-bot restrictions.
Accurately categorizes state as LIVE_VERIFIED or SOURCE_UNAVAILABLE to eliminate false alerts.
Includes a Manual Booking-Page Verification Fallback for Remote Desktop operators.
"""

import json
import re
import datetime
import logging
from typing import List, Dict, Any, Optional, Tuple
from playwright.async_api import async_playwright, Page
from config import Config

logger = logging.getLogger("monitor")


def get_ist_timezone() -> datetime.tzinfo:
    """Return Asia/Kolkata timezone with reliable fallback."""
    try:
        import zoneinfo
        return zoneinfo.ZoneInfo("Asia/Kolkata")
    except Exception:
        return datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="Asia/Kolkata")


def get_ist_now() -> datetime.datetime:
    """Return current timezone-aware datetime in Asia/Kolkata (IST)."""
    return datetime.datetime.now(get_ist_timezone())


def validate_showtime(show_date: str, show_time: str) -> Tuple[datetime.datetime, str, str]:
    """
    Strict validation for booking dates and showtimes against Asia/Kolkata (IST) timezone.
    Safeguards:
    1. Rejects all past dates (show_date < today_ist).
    2. Rejects past showtimes on today's date (show_datetime < now_ist).
    3. Rejects dates excessively far in advance (> 60 days).
    4. Validates date and time format strictly.

    Returns:
        (show_datetime_ist, formatted_date_str, formatted_time_str)
    Raises:
        ValueError if the date or time is invalid or in the past.
    """
    clean_date = (show_date or "").strip()
    clean_time = (show_time or "").strip()

    if not clean_date:
        raise ValueError("Show date is required.")
    if not clean_time:
        raise ValueError("Showtime is required.")

    # Parse date
    parsed_date: Optional[datetime.date] = None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", clean_date):
        try:
            parsed_date = datetime.datetime.strptime(clean_date, "%Y-%m-%d").date()
        except ValueError as e:
            raise ValueError(f"Invalid date '{clean_date}': {e}")
    elif re.match(r"^\d{8}$", clean_date):
        try:
            parsed_date = datetime.datetime.strptime(clean_date, "%Y%m%d").date()
        except ValueError as e:
            raise ValueError(f"Invalid date '{clean_date}': {e}")
    else:
        raise ValueError(f"Invalid date format '{clean_date}'. Expected YYYY-MM-DD (e.g. 2026-11-21).")

    # Parse time
    parsed_time_obj: Optional[datetime.time] = None
    time_formats = [
        "%I:%M %p",  # 06:45 PM or 6:45 PM
        "%I:%M%p",   # 06:45PM
        "%H:%M",     # 18:45
        "%I %p",     # 7 PM
    ]
    for fmt in time_formats:
        try:
            dt_tmp = datetime.datetime.strptime(clean_time.upper(), fmt)
            parsed_time_obj = dt_tmp.time()
            break
        except ValueError:
            continue

    if not parsed_time_obj:
        raise ValueError(
            f"Invalid showtime format '{clean_time}'. Expected formats like '06:45 PM' or '18:45'."
        )

    ist_tz = get_ist_timezone()
    now_ist = datetime.datetime.now(ist_tz)
    show_dt_ist = datetime.datetime.combine(parsed_date, parsed_time_obj, tzinfo=ist_tz)

    formatted_date_str = parsed_date.strftime("%Y-%m-%d")
    formatted_time_str = show_dt_ist.strftime("%I:%M %p")

    # Rule 1: Check date is not in the past
    if parsed_date < now_ist.date():
        raise ValueError(
            f"Booking date {formatted_date_str} is in the past! "
            f"Today in India (Asia/Kolkata) is {now_ist.strftime('%Y-%m-%d')}."
        )

    # Rule 2: Check full show datetime is not in the past
    if show_dt_ist < now_ist:
        raise ValueError(
            f"Showtime {formatted_date_str} {formatted_time_str} IST is in the past! "
            f"Current time in India (Asia/Kolkata) is {now_ist.strftime('%Y-%m-%d %I:%M %p IST')}."
        )

    # Rule 3: Check date is within reasonable advance booking horizon (60 days)
    max_advance = now_ist.date() + datetime.timedelta(days=60)
    if parsed_date > max_advance:
        raise ValueError(
            f"Show date {formatted_date_str} exceeds maximum advance booking horizon (max {max_advance.strftime('%Y-%m-%d')})."
        )

    return show_dt_ist, formatted_date_str, formatted_time_str


class BookingMonitor:
    def __init__(self, db, headless: Optional[bool] = None, proxy: Optional[str] = None):
        self.db = db
        self.headless = Config.HEADLESS_BROWSER if headless is None else headless
        self.proxy = proxy or Config.BMS_PROXY
        self.target_movie = Config.MOVIE_TITLE
        self.cinema_name = Config.CINEMA_NAME
        self.cinema_code = Config.CINEMA_CODE
        self.base_venue_url = Config.BMS_VENUE_URL

    def generate_target_dates(self, days_horizon: Optional[int] = None) -> List[str]:
        """Generate list of date strings in YYYYMMDD format for the monitoring horizon."""
        horizon = days_horizon or Config.MONITORING_HORIZON_DAYS
        today = datetime.date.today()
        dates = []
        for i in range(horizon):
            d = today + datetime.timedelta(days=i)
            dates.append(d.strftime("%Y%m%d"))
        return dates

    @staticmethod
    def is_title_match(candidate_title: str, target_title: str) -> bool:
        """Fuzzy match movie title to prevent false positives and naming discrepancies."""
        if not candidate_title:
            return False

        def clean(s: str) -> str:
            return re.sub(r"[^a-zA-Z0-9]", "", s).lower()

        c_clean = clean(candidate_title)
        t_clean = clean(target_title)

        if t_clean in c_clean or c_clean in t_clean:
            return True

        words = [w for w in re.split(r"\W+", target_title.lower()) if len(w) > 2]
        return all(w in candidate_title.lower() for w in words)

    def parse_html_for_shows(
        self, html_content: str, date_str: str, verification_mode: str = "LIVE_VERIFIED"
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Parse HTML or JSON state from a BookMyShow venue page.
        Returns:
            shows: List of detected showtime dictionaries
            meta: Dict containing status flags (e.g. cloudflare_blocked, page_found, etc.)
        """
        meta = {
            "cloudflare_blocked": False,
            "page_found": True,
            "movie_listed": False,
        }
        shows: List[Dict[str, Any]] = []

        # 1. Detect anti-bot / Cloudflare Challenge
        if "cf-mitigated" in html_content.lower() or (
            "just a moment..." in html_content.lower() and "cloudflare" in html_content.lower()
        ) or "challenge-running" in html_content.lower():
            meta["cloudflare_blocked"] = True
            logger.warning("Cloudflare challenge encountered on BookMyShow venue page.")
            return shows, meta

        # 2. Check for Next.js __NEXT_DATA__
        next_data_match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            html_content,
            re.DOTALL,
        )
        if next_data_match:
            try:
                json_str = next_data_match.group(1).strip()
                data = json.loads(json_str)
                extracted_shows = self._extract_from_next_data(data, date_str, verification_mode)
                if extracted_shows:
                    return extracted_shows, meta
            except Exception as e:
                logger.debug(f"Failed to parse __NEXT_DATA__: {e}")

        # 3. DOM Regex extraction for standard BMS HTML layouts
        extracted_shows = self._extract_from_dom_html(html_content, date_str, meta, verification_mode)
        return extracted_shows, meta

    def _extract_from_next_data(
        self, data: Dict[str, Any], date_str: str, verification_mode: str
    ) -> List[Dict[str, Any]]:
        """Extract movie showtimes from BookMyShow Next.js pageProps."""
        detected = []
        page_props = data.get("props", {}).get("pageProps", {})

        movies_data = (
            page_props.get("showsData", {})
            or page_props.get("movies", [])
            or page_props.get("venueDetails", {}).get("movies", [])
        )

        movie_list = []
        if isinstance(movies_data, list):
            movie_list = movies_data
        elif isinstance(movies_data, dict):
            movie_list = movies_data.get("movies", []) or movies_data.get("arrEvents", [])

        for movie_entry in movie_list:
            movie_name = (
                movie_entry.get("EventTitle")
                or movie_entry.get("name")
                or movie_entry.get("title")
                or ""
            )

            if not self.is_title_match(movie_name, self.target_movie):
                continue

            shows_list = (
                movie_entry.get("shows")
                or movie_entry.get("arrShowTimes")
                or movie_entry.get("timings")
                or []
            )

            for show_item in shows_list:
                time_str = (
                    show_item.get("ShowTime")
                    or show_item.get("time")
                    or show_item.get("timeStr")
                    or ""
                )
                if not time_str:
                    continue

                raw_status = (
                    show_item.get("availability")
                    or show_item.get("status")
                    or show_item.get("BookType")
                    or "AVAILABLE"
                ).upper()

                if raw_status in ("A", "AVAILABLE"):
                    booking_status = "AVAILABLE"
                elif raw_status in ("F", "FILLING_FAST", "AL"):
                    booking_status = "FILLING_FAST"
                elif raw_status in ("S", "SOLD_OUT", "SOLDOUT"):
                    booking_status = "SOLD_OUT"
                else:
                    booking_status = "AVAILABLE"

                screen = (
                    show_item.get("ScreenName")
                    or show_item.get("screen")
                    or "4K RGB Laser Atmos"
                )
                session_id = str(show_item.get("SessionId") or show_item.get("id") or "")

                direct_link = (
                    f"https://in.bookmyshow.com/booktickets/{self.cinema_code}/{session_id}"
                    if session_id
                    else self.base_venue_url
                )

                detected.append({
                    "cinema_name": self.cinema_name,
                    "cinema_code": self.cinema_code,
                    "movie_title": self.target_movie,
                    "show_date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}" if len(date_str) == 8 else date_str,
                    "show_time": time_str,
                    "screen_name": screen,
                    "session_id": session_id,
                    "booking_status": booking_status,
                    "booking_link": direct_link,
                    "verification_mode": verification_mode,
                })

        return detected

    def _extract_from_dom_html(
        self, html_content: str, date_str: str, meta: Dict[str, Any], verification_mode: str
    ) -> List[Dict[str, Any]]:
        """Fallback DOM-based parser for rendered BMS venue HTML."""
        detected = []
        formatted_date = (
            f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            if len(date_str) == 8
            else date_str
        )

        if not self.is_title_match(html_content, self.target_movie):
            return detected

        meta["movie_listed"] = True

        show_pill_pattern = re.compile(
            r'<(?:a|button|div)[^>]*?(?:class="[^"]*?showtime-pill[^"]*?"|data-session-id="([^"]*)")[^>]*?>\s*([\d]{1,2}:[\d]{2}\s*(?:AM|PM|am|pm)?)\s*</(?:a|button|div)>',
            re.IGNORECASE,
        )

        for match in show_pill_pattern.finditer(html_content):
            session_id = match.group(1) or ""
            show_time = match.group(2).strip()

            start_pos = max(0, match.start() - 100)
            end_pos = min(len(html_content), match.end() + 100)
            snippet = html_content[start_pos:end_pos].lower()

            if "sold" in snippet or "sold-out" in snippet:
                status = "SOLD_OUT"
            elif "filling" in snippet or "fast" in snippet or 'avail="f"' in snippet:
                status = "FILLING_FAST"
            else:
                status = "AVAILABLE"

            direct_link = (
                f"https://in.bookmyshow.com/booktickets/{self.cinema_code}/{session_id}"
                if session_id
                else self.base_venue_url
            )

            detected.append({
                "cinema_name": self.cinema_name,
                "cinema_code": self.cinema_code,
                "movie_title": self.target_movie,
                "show_date": formatted_date,
                "show_time": show_time,
                "screen_name": "4K RGB Laser Atmos",
                "session_id": session_id,
                "booking_status": status,
                "booking_link": direct_link,
                "verification_mode": verification_mode,
            })

        return detected

    async def scan_single_date(
        self, page: Page, date_yyyymmdd: str
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Navigate to BMS venue page for a specific date using Playwright and parse."""
        url = f"{self.base_venue_url}/{date_yyyymmdd}"
        logger.info(f"Checking date {date_yyyymmdd} at {url}")

        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            status_code = resp.status if resp else 0

            await page.wait_for_timeout(2000)

            title = await page.title()
            content = await page.content()

            if status_code == 403 or "challenge" in content.lower() or "just a moment..." in title.lower():
                logger.warning(
                    f"Date {date_yyyymmdd}: Cloudflare bot restriction active on {url} (HTTP {status_code})."
                )
                return [], {"cloudflare_blocked": True, "status_code": status_code}

            shows, meta = self.parse_html_for_shows(content, date_yyyymmdd, "LIVE_VERIFIED")
            return shows, meta

        except Exception as e:
            logger.error(f"Error scanning date {date_yyyymmdd}: {e}")
            return [], {"error": str(e)}

    async def run_full_scan(self) -> Dict[str, Any]:
        """
        Execute full scan across all target dates in the monitoring horizon.
        Accurately records SOURCE_UNAVAILABLE when Cloudflare is encountered.
        Never generates false-positive alerts.
        """
        target_dates = self.generate_target_dates()
        all_detected_shows = []
        cf_blocked = False
        error_msg = None

        launch_kwargs: Dict[str, Any] = {"headless": self.headless}
        if self.proxy:
            launch_kwargs["proxy"] = {"server": self.proxy}

        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(**launch_kwargs)
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/128.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1366, "height": 768},
                    locale="en-IN",
                    timezone_id="Asia/Kolkata",
                )
                page = await context.new_page()

                for idx, date_str in enumerate(target_dates):
                    shows, meta = await self.scan_single_date(page, date_str)

                    if meta.get("cloudflare_blocked"):
                        cf_blocked = True
                        logger.warning(
                            "Cloudflare challenge detected on Oracle Cloud IP. Halting scan loop to comply with anti-bot policy."
                        )
                        break

                    if shows:
                        for s in shows:
                            all_detected_shows.append(s)
                            show_id, is_new, is_bookable = self.db.record_showtime(s)
                            if is_new or is_bookable:
                                self.db.log_event(
                                    "INFO",
                                    "CHECK",
                                    f"Detected {s['booking_status']} show for {s['movie_title']} on {s['show_date']} {s['show_time']}",
                                )

                    await page.wait_for_timeout(1000)

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Browser scan failed: {e}")
            finally:
                if browser:
                    await browser.close()

        now = datetime.datetime.now(datetime.timezone.utc)
        now_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")
        next_check = (now + datetime.timedelta(seconds=Config.CHECK_INTERVAL_SECONDS)).strftime("%Y-%m-%d %H:%M:%S UTC")
        self.db.set_status("last_check_time", now_str)
        self.db.set_status("next_scheduled_check", next_check)

        if cf_blocked:
            self.db.set_status("monitoring_status", "SOURCE_UNAVAILABLE")
            self.db.set_status("source_state", "SOURCE_UNAVAILABLE")
            self.db.set_status(
                "last_check_result",
                "SOURCE_UNAVAILABLE: Cloudflare Turnstile protection active on BookMyShow (Cloud VPS IP). Anti-bot bypass disabled per policy. Manual verification fallback active.",
            )
            self.db.log_event(
                "WARNING",
                "BLOCKED",
                "Automated check met Cloudflare Turnstile. Status set to SOURCE_UNAVAILABLE without bypass.",
            )
        elif error_msg:
            self.db.set_status("monitoring_status", "ERROR")
            self.db.set_status("last_check_result", f"Error: {error_msg}")
        else:
            self.db.set_status("monitoring_status", "LIVE_VERIFIED" if all_detected_shows else "ACTIVE")
            self.db.set_status("source_state", "LIVE_VERIFIED" if all_detected_shows else "ACCESSIBLE")
            status_text = (
                f"LIVE_VERIFIED: Found {len(all_detected_shows)} {Config.MOVIE_TITLE} showtimes."
                if all_detected_shows
                else f"ACCESSIBLE: Scan complete. {Config.MOVIE_TITLE} ticket booking not yet open."
            )
            self.db.set_status("last_check_result", status_text)

        return {
            "timestamp": now_str,
            "dates_checked": len(target_dates) if not cf_blocked else 1,
            "detected_shows": all_detected_shows,
            "cloudflare_blocked": cf_blocked,
            "source_status": "SOURCE_UNAVAILABLE" if cf_blocked else ("LIVE_VERIFIED" if all_detected_shows else "ACCESSIBLE"),
            "error": error_msg,
        }

    def record_manual_verification(
        self,
        show_date: str,
        show_time: str,
        operator_name: str,
        visually_confirmed: bool,
        booking_link: Optional[str] = None,
        screen_name: str = "4K RGB Laser Atmos (Audi 1)",
        booking_status: str = "AVAILABLE",
        ip_address: Optional[str] = None,
    ) -> Tuple[int, bool, bool, Dict[str, Any], Optional[str]]:
        """
        Operator Visual Booking-Page Verification:
        Enforces strict safeguards:
        1. visually_confirmed must be explicitly True.
        2. operator_name must be non-empty.
        3. show_date and show_time must be strictly in the future in Asia/Kolkata (IST).
        4. Logs audit entry in verification_audit_log for every attempt.
        5. Prevents duplicate notifications.
        Returns: (show_id, is_new, is_duplicate, show_record, prev_alert_time)
        """
        # Guard 1: Require explicit visual certification
        if not visually_confirmed:
            self.db.log_verification_audit(
                operator_name=operator_name or "Unknown",
                show_date=show_date,
                show_time=show_time,
                action="REJECTED_VALIDATION",
                notes="Rejected: Visual confirmation checkbox was not checked.",
                ip_address=ip_address,
            )
            raise ValueError(
                "Manual verification requires explicit visual certification that actual seats are bookable on BookMyShow."
            )

        # Guard 2: Require valid operator name
        clean_operator = (operator_name or "").strip()
        if not clean_operator or len(clean_operator) < 2:
            self.db.log_verification_audit(
                operator_name="Anonymous",
                show_date=show_date,
                show_time=show_time,
                action="REJECTED_VALIDATION",
                notes="Rejected: Missing or invalid operator name.",
                ip_address=ip_address,
            )
            raise ValueError("Operator name is required for verification audit logging.")

        # Guard 3: Validate booking status
        clean_status = (booking_status or "AVAILABLE").upper()
        if clean_status not in ("AVAILABLE", "FILLING_FAST"):
            raise ValueError(f"Cannot verify booking with non-bookable status '{clean_status}'.")

        # Guard 4: Strictly validate date/time in Asia/Kolkata timezone
        try:
            show_dt_ist, valid_date, valid_time = validate_showtime(show_date, show_time)
        except ValueError as val_err:
            self.db.log_verification_audit(
                operator_name=clean_operator,
                show_date=show_date,
                show_time=show_time,
                action="REJECTED_VALIDATION",
                notes=f"Rejected date/time validation: {val_err}",
                ip_address=ip_address,
            )
            raise

        # Guard 5: Duplicate check
        is_dup, prev_time = self.db.is_already_alerted(
            show_date=valid_date,
            show_time=valid_time,
            screen_name=screen_name,
            cinema_code=self.cinema_code,
            movie_title=self.target_movie,
        )

        link = booking_link or self.base_venue_url
        ist_now_str = get_ist_now().strftime("%Y-%m-%d %I:%M %p IST")

        show_record = {
            "cinema_name": self.cinema_name,
            "cinema_code": self.cinema_code,
            "movie_title": self.target_movie,
            "show_date": valid_date,
            "show_time": valid_time,
            "screen_name": screen_name,
            "session_id": "MANUAL_VERIFIED",
            "booking_status": clean_status,
            "booking_link": link,
            "verification_mode": "LIVE_VERIFIED",
            "confirmed_by": clean_operator,
            "confirmed_at_ist": ist_now_str,
        }

        self.db.set_status("last_verification_time", ist_now_str)

        if is_dup:
            logger.info(f"Show {valid_date} {valid_time} was already alerted at {prev_time}. Suppressing duplicate.")
            self.db.log_verification_audit(
                operator_name=clean_operator,
                show_date=valid_date,
                show_time=valid_time,
                action="DUPLICATE_SUPPRESSED",
                notes=f"Already alerted at {prev_time}. Alert suppressed.",
                booking_link=link,
                cinema_code=self.cinema_code,
                ip_address=ip_address,
            )
            self.db.log_event(
                "INFO",
                "MANUAL_VERIFY",
                f"Manual verification for {valid_date} {valid_time} suppressed duplicate alert (already sent at {prev_time}).",
            )
            return 0, False, True, show_record, prev_time

        show_id, is_new, is_bookable = self.db.record_showtime(show_record)
        self.db.set_status("monitoring_status", "LIVE_VERIFIED")
        self.db.set_status("source_state", "LIVE_VERIFIED")
        self.db.set_status(
            "last_check_result",
            f"LIVE_VERIFIED: Confirmed by {clean_operator} for {valid_date} at {valid_time}",
        )
        self.db.log_verification_audit(
            operator_name=clean_operator,
            show_date=valid_date,
            show_time=valid_time,
            action="VERIFIED_LIVE",
            notes=f"Live booking visually confirmed on BookMyShow ({link}). Alert queued.",
            booking_link=link,
            cinema_code=self.cinema_code,
            ip_address=ip_address,
        )
        self.db.log_event(
            "SUCCESS",
            "MANUAL_VERIFY",
            f"Operator {clean_operator} visually verified live booking: {valid_date} {valid_time} at {link}",
        )
        return show_id, is_new, False, show_record, None
