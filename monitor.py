"""
Monitoring engine for Avengers: Doomsday at Ritzy Sha Cinemas, Madurai.
Uses Playwright and BeautifulSoup/HTML parsing to check showtimes across dates,
detect bookable states, and avoid false positives.
Complies strictly with safety rules: never bypasses CAPTCHA/anti-bot restrictions.
"""

import json
import re
import datetime
import logging
from typing import List, Dict, Any, Optional, Tuple
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from config import Config

logger = logging.getLogger("monitor")


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
        """Generate list of date strings in YYYYMMDD and YYYY-MM-DD formats for the monitoring horizon."""
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

        # Check keyword parts: "avengers" and "doomsday"
        words = [w for w in re.split(r"\W+", target_title.lower()) if len(w) > 2]
        return all(w in candidate_title.lower() for w in words)

    def parse_html_for_shows(
        self, html_content: str, date_str: str
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
            "raw_matches_count": 0,
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
                extracted_shows = self._extract_from_next_data(data, date_str)
                if extracted_shows:
                    return extracted_shows, meta
            except Exception as e:
                logger.debug(f"Failed to parse __NEXT_DATA__: {e}")

        # 3. DOM Regex/Heuristic extraction for standard BMS HTML layouts
        extracted_shows = self._extract_from_dom_html(html_content, date_str, meta)
        return extracted_shows, meta

    def _extract_from_next_data(
        self, data: Dict[str, Any], date_str: str
    ) -> List[Dict[str, Any]]:
        """Extract movie showtimes from BookMyShow Next.js pageProps."""
        detected = []
        page_props = data.get("props", {}).get("pageProps", {})

        # BMS often structures showtimes under showsData, venueShows, or movies list
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

            # Found target movie! Look for showtimes
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

                # Normalize availability
                # In BMS: "A" = Available, "F" = Fast Filling, "AL" = Almost Full, "Sold Out"
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

                # Construct direct booking link if available
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
                })

        return detected

    def _extract_from_dom_html(
        self, html_content: str, date_str: str, meta: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Fallback DOM-based parser for rendered BMS venue HTML."""
        detected = []
        formatted_date = (
            f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            if len(date_str) == 8
            else date_str
        )

        # Split into movie container blocks (BMS uses elements with movie names or data-event-code)
        # We search if target movie name exists in HTML
        if not self.is_title_match(html_content, self.target_movie):
            return detected

        meta["movie_listed"] = True

        # Regex search for showtime buttons associated with the movie
        # Matches patterns like data-session-id="...", data-availability="A", text="10:15 AM"
        show_pill_pattern = re.compile(
            r'<(?:a|button|div)[^>]*?(?:class="[^"]*?showtime-pill[^"]*?"|data-session-id="([^"]*)")[^>]*?>\s*([\d]{1,2}:[\d]{2}\s*(?:AM|PM|am|pm)?)\s*</(?:a|button|div)>',
            re.IGNORECASE,
        )

        for match in show_pill_pattern.finditer(html_content):
            session_id = match.group(1) or ""
            show_time = match.group(2).strip()

            # Inspect surrounding 200 characters for availability markers
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
            })

        return detected

    async def scan_single_date(
        self, page: Page, date_yyyymmdd: str
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Navigate to BMS venue page for a specific date using Playwright and parse."""
        url = f"{self.base_venue_url}/{date_yyyymmdd}"
        logger.info(f"Checking date {date_yyyymmdd} at {url}")

        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            status_code = resp.status if resp else 0

            # Wait briefly for client-side hydration
            await page.wait_for_timeout(2500)

            title = await page.title()
            content = await page.content()

            if status_code == 403 or "challenge" in content.lower() or "just a moment..." in title.lower():
                logger.warning(
                    f"Date {date_yyyymmdd}: Cloudflare bot protection active on {url} (HTTP {status_code})."
                )
                return [], {"cloudflare_blocked": True, "status_code": status_code}

            shows, meta = self.parse_html_for_shows(content, date_yyyymmdd)
            return shows, meta

        except Exception as e:
            logger.error(f"Error scanning date {date_yyyymmdd}: {e}")
            return [], {"error": str(e)}

    async def run_full_scan(self) -> Dict[str, Any]:
        """
        Execute full scan across all target dates in the monitoring horizon.
        Records shows in the database and prevents duplicate alerts.
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

                # Iterate through dates; if first check is Cloudflare-blocked, avoid useless hammering
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
                            # Persist to database
                            show_id, is_new, is_bookable = self.db.record_showtime(s)
                            if is_new or is_bookable:
                                self.db.log_event(
                                    "INFO",
                                    "CHECK",
                                    f"Detected {s['booking_status']} show for {s['movie_title']} on {s['show_date']} {s['show_time']}",
                                )

                    # Small polite interval between dates
                    await page.wait_for_timeout(1000)

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Browser scan failed: {e}")
            finally:
                if browser:
                    await browser.close()

        # Update system status in database
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        self.db.set_status("last_check_time", now_str)

        if cf_blocked:
            self.db.set_status("monitoring_status", "BLOCKED_BY_CLOUDFLARE")
            self.db.set_status(
                "last_check_result",
                "Cloudflare Turnstile challenge returned (HTTP 403 on Cloud VPS). Anti-bot bypass was NOT attempted. Residential proxy recommended in .env.",
            )
            self.db.log_event(
                "WARNING",
                "BLOCKED",
                "Cloudflare Turnstile challenge returned on BookMyShow. Safe monitoring preserved without illegal bypass.",
            )
        elif error_msg:
            self.db.set_status("monitoring_status", "ERROR")
            self.db.set_status("last_check_result", f"Error: {error_msg}")
        else:
            status_text = (
                f"Scan complete. Found {len(all_detected_shows)} {Config.MOVIE_TITLE} showtimes."
                if all_detected_shows
                else f"Scan complete. {Config.MOVIE_TITLE} ticket booking not yet open."
            )
            self.db.set_status("monitoring_status", "ACTIVE")
            self.db.set_status("last_check_result", status_text)

        return {
            "timestamp": now_str,
            "dates_checked": len(target_dates) if not cf_blocked else 1,
            "detected_shows": all_detected_shows,
            "cloudflare_blocked": cf_blocked,
            "error": error_msg,
        }
