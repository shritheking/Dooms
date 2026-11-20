"""
Main entry point for Avengers: Doomsday Booking Alert Bot (Telegram Only).
Orchestrates:
1. Native asyncio monitoring loop (5-minute intervals across dates).
2. Prominent "CHECK DOOMSDAY BOOKINGS" workflow with direct BookMyShow venue link.
3. Convenient Manual Verification Form with One-Click Confirmation.
4. Immediate Telegram alert dispatch with robust duplicate prevention.
5. Displays Last Verification Time and Next Scheduled Check.
6. Modern FastAPI Dashboard with matte black, electric blue, and violet glassmorphism UI.
"""

import sys
import asyncio
import datetime
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from pydantic import BaseModel

import uvicorn
from fastapi import FastAPI, BackgroundTasks, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import Config
from database import Database
from monitor import BookingMonitor
from telegram_bot import TelegramBot

# Ensure log directory exists
log_dir = Config.DATABASE_PATH.parent / "logs"
log_dir.mkdir(exist_ok=True)

# Setup logging with file handler and stream handler
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("main")

# Initialize core services
db = Database()
telegram_client = TelegramBot()
monitor = BookingMonitor(db)

app = FastAPI(title="Avengers: Doomsday Telegram Booking Alert System", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Background Alert Dispatcher & Monitoring Worker
# ---------------------------------------------------------------------------

def dispatch_pending_alerts():
    """
    Check for pending alerts in SQLite and dispatch via Telegram.
    Ensures that once Telegram succeeds, it is marked and never duplicated.
    """
    pending = db.get_pending_alerts()
    if not pending:
        return

    logger.info(f"Processing {len(pending)} pending alert(s)...")

    for show in pending:
        show_id = show["id"]
        logger.info(f"Dispatching Telegram alert for show ID {show_id} (mode={show.get('verification_mode')})...")
        tg_ok = telegram_client.send_alert(show)
        if tg_ok:
            db.mark_alert_sent(show_id)
            db.log_event(
                "SUCCESS",
                "ALERT_TG",
                f"Telegram alert sent for {show['movie_title']} ({show['show_date']} {show['show_time']}) [{show.get('verification_mode')}]",
            )
        else:
            db.mark_alert_error(show_id, "Telegram delivery failed")


async def run_scan_and_alert():
    """Async wrapper to run Playwright scan and dispatch pending alerts."""
    try:
        await monitor.run_full_scan()
        dispatch_pending_alerts()
    except Exception as e:
        logger.error(f"Error in scan and alert cycle: {e}")
        db.log_event("ERROR", "SYSTEM", f"Scan cycle error: {e}")


def trigger_manual_scan_thread():
    """Thread-safe trigger for manual scan from Telegram command."""
    asyncio.run(run_scan_and_alert())


async def async_monitor_scheduler_loop():
    """Continuous native asyncio background loop running full scans at 5-minute intervals."""
    logger.info(f"Monitoring scheduler active. Interval: {Config.CHECK_INTERVAL_SECONDS} seconds.")
    await asyncio.sleep(2)
    # Initial scan on launch
    await run_scan_and_alert()

    while True:
        try:
            await asyncio.sleep(Config.CHECK_INTERVAL_SECONDS)
            await run_scan_and_alert()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in monitor scheduler loop: {e}")
            db.log_event("ERROR", "SYSTEM", f"Scheduler loop encountered exception: {e}")
            await asyncio.sleep(30)


@app.on_event("startup")
async def on_app_startup():
    """Bootstrap background monitoring loop and Telegram polling on application start."""
    logger.info("Initializing Avengers: Doomsday Telegram Alert Bot...")
    telegram_client.start_polling(db, on_manual_check=trigger_manual_scan_thread)
    asyncio.create_task(async_monitor_scheduler_loop())


# ---------------------------------------------------------------------------
# Pydantic Model for Manual Verification
# ---------------------------------------------------------------------------

class ManualVerifyRequest(BaseModel):
    show_date: str
    show_time: str
    operator_name: str
    visually_confirmed: bool
    confirmation_statement: Optional[str] = None
    booking_link: Optional[str] = None
    screen_name: Optional[str] = "4K RGB Laser Atmos (Audi 1)"
    booking_status: Optional[str] = "AVAILABLE"


# ---------------------------------------------------------------------------
# Modern Glassmorphism Dashboard HTML
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Avengers: Doomsday — Booking Alert Command Center</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #07090E;
            --bg-surface: #0E131F;
            --bg-card: rgba(18, 24, 38, 0.75);
            --electric-blue: #00D2FF;
            --electric-blue-glow: rgba(0, 210, 255, 0.35);
            --electric-accent: #0070F3;
            --violet: #8A2BE2;
            --violet-glow: rgba(138, 43, 226, 0.30);
            --text-primary: #F0F6FC;
            --text-secondary: #8B949E;
            --text-muted: #586069;
            --border-glass: rgba(0, 210, 255, 0.16);
            --border-glass-violet: rgba(138, 43, 226, 0.22);
            --success: #00F298;
            --success-glow: rgba(0, 242, 152, 0.3);
            --warning: #FFB800;
            --danger: #FF3B30;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-base);
            background-image: 
                radial-gradient(circle at 15% 15%, rgba(0, 210, 255, 0.09) 0%, transparent 50%),
                radial-gradient(circle at 85% 85%, rgba(138, 43, 226, 0.09) 0%, transparent 50%),
                linear-gradient(180deg, #07090E 0%, #0B0F19 100%);
            color: var(--text-primary);
            font-family: 'Plus Jakarta Sans', sans-serif;
            min-height: 100vh;
            padding: 24px;
            overflow-x: hidden;
        }

        .container {
            max-width: 1380px;
            margin: 0 auto;
        }

        header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-bottom: 24px;
            margin-bottom: 24px;
            border-bottom: 1px solid var(--border-glass);
            flex-wrap: wrap;
            gap: 16px;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .brand-icon {
            width: 52px;
            height: 52px;
            border-radius: 14px;
            background: linear-gradient(135deg, #00D2FF 0%, #8A2BE2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 26px;
            box-shadow: 0 0 24px var(--electric-blue-glow);
        }

        .brand-title h1 {
            font-size: 22px;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: linear-gradient(90deg, #FFFFFF 20%, #00D2FF 65%, #9D4EDD 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .brand-title p {
            font-size: 13px;
            color: var(--text-secondary);
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }

        .btn {
            background: var(--bg-surface);
            color: var(--text-primary);
            border: 1px solid var(--border-glass);
            padding: 10px 18px;
            border-radius: 10px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            text-decoration: none;
            backdrop-filter: blur(8px);
        }

        .btn:hover {
            transform: translateY(-2px);
            border-color: var(--electric-blue);
            box-shadow: 0 0 16px var(--electric-blue-glow);
        }

        .btn-hero-check {
            background: linear-gradient(135deg, #00D2FF 0%, #0070F3 50%, #8A2BE2 100%);
            color: #FFFFFF;
            border: none;
            padding: 12px 24px;
            font-size: 14px;
            font-weight: 800;
            letter-spacing: 0.5px;
            border-radius: 12px;
            box-shadow: 0 0 25px var(--electric-blue-glow);
            text-transform: uppercase;
        }

        .btn-hero-check:hover {
            transform: translateY(-2px) scale(1.02);
            box-shadow: 0 0 32px var(--electric-blue-glow);
        }

        .btn-telegram {
            background: linear-gradient(135deg, rgba(0, 136, 204, 0.25) 0%, rgba(0, 210, 255, 0.25) 100%);
            border: 1px solid #0088CC;
            color: #38B8FF;
        }

        .btn-confirm-live {
            background: linear-gradient(135deg, #00F298 0%, #00C875 100%);
            color: #05140D;
            border: none;
            padding: 14px 28px;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 800;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 10px;
            box-shadow: 0 0 25px var(--success-glow);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .btn-confirm-live:hover {
            transform: translateY(-2px) scale(1.02);
            box-shadow: 0 0 35px var(--success-glow);
        }

        .spotlight-grid {
            display: grid;
            grid-template-columns: 320px 1fr;
            gap: 24px;
            margin-bottom: 24px;
        }

        @media (max-width: 900px) {
            .spotlight-grid {
                grid-template-columns: 1fr;
            }
        }

        .glass-card {
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border-glass);
            border-radius: 18px;
            padding: 22px;
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
            position: relative;
            overflow: hidden;
        }

        .glass-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--electric-blue), var(--violet), transparent);
            opacity: 0.6;
        }

        .movie-card {
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
        }

        .movie-poster-wrap {
            width: 100%;
            height: 340px;
            border-radius: 14px;
            overflow: hidden;
            position: relative;
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.7);
            border: 1px solid var(--border-glass-violet);
            margin-bottom: 16px;
            background: #141724;
        }

        .movie-poster-wrap img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.3s ease;
        }

        .movie-title {
            font-size: 20px;
            font-weight: 800;
            margin-bottom: 6px;
            color: #FFFFFF;
        }

        .cinema-badge {
            display: inline-block;
            background: rgba(0, 210, 255, 0.1);
            color: var(--electric-blue);
            border: 1px solid rgba(0, 210, 255, 0.3);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 12px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }

        .stat-box {
            background: rgba(14, 19, 31, 0.85);
            border: 1px solid var(--border-glass);
            border-radius: 14px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }

        .stat-box:hover {
            border-color: var(--electric-blue);
            transform: translateY(-2px);
        }

        .stat-label {
            font-size: 12px;
            color: var(--text-secondary);
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .stat-value {
            font-size: 20px;
            font-weight: 800;
            color: #FFFFFF;
            font-family: 'JetBrains Mono', monospace;
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 700;
        }

        .status-live {
            background: rgba(0, 242, 152, 0.15);
            color: var(--success);
            border: 1px solid rgba(0, 242, 152, 0.4);
        }

        .status-unavailable {
            background: rgba(255, 184, 0, 0.15);
            color: var(--warning);
            border: 1px solid rgba(255, 184, 0, 0.4);
        }

        .pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: currentColor;
            box-shadow: 0 0 10px currentColor;
            animation: pulse 1.8s infinite;
        }

        @keyframes pulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.4; transform: scale(0.85); }
            100% { opacity: 1; transform: scale(1); }
        }

        /* Prominent Verification Fallback Panel */
        .verification-panel {
            background: linear-gradient(135deg, rgba(14, 19, 31, 0.95) 0%, rgba(18, 24, 38, 0.95) 100%);
            border: 2px solid rgba(0, 210, 255, 0.4);
            border-radius: 20px;
            padding: 24px;
            box-shadow: 0 16px 48px rgba(0, 0, 0, 0.6), 0 0 25px rgba(0, 210, 255, 0.15);
            margin-bottom: 24px;
        }

        .verification-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 14px;
            flex-wrap: wrap;
            gap: 12px;
        }

        .verification-title {
            font-size: 18px;
            font-weight: 800;
            color: #FFFFFF;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-top: 18px;
            margin-bottom: 20px;
        }

        .input-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .input-group label {
            font-size: 12px;
            color: var(--text-secondary);
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .input-control {
            background: #070A12;
            border: 1px solid rgba(0, 210, 255, 0.2);
            padding: 12px 14px;
            border-radius: 10px;
            color: #FFFFFF;
            font-size: 14px;
            outline: none;
            transition: all 0.2s ease;
        }

        .input-control:focus {
            border-color: var(--electric-blue);
            box-shadow: 0 0 12px var(--electric-blue-glow);
        }

        .quick-pills {
            display: flex;
            gap: 8px;
            margin-top: 6px;
            flex-wrap: wrap;
        }

        .pill-btn {
            background: rgba(0, 210, 255, 0.1);
            color: var(--electric-blue);
            border: 1px solid rgba(0, 210, 255, 0.25);
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
        }

        .pill-btn:hover {
            background: var(--electric-blue);
            color: #07090E;
        }

        .content-grid {
            display: grid;
            grid-template-columns: 2fr 1.2fr;
            gap: 24px;
            margin-bottom: 24px;
        }

        @media (max-width: 1024px) {
            .content-grid {
                grid-template-columns: 1fr;
            }
        }

        .section-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 18px;
        }

        .section-title {
            font-size: 16px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
            color: #FFFFFF;
        }

        .table-wrap {
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }

        th {
            text-align: left;
            padding: 12px 14px;
            color: var(--text-secondary);
            font-weight: 600;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        td {
            padding: 14px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            vertical-align: middle;
        }

        tr:hover td {
            background: rgba(0, 210, 255, 0.03);
        }

        .badge-live-verified {
            background: rgba(0, 242, 152, 0.15);
            color: var(--success);
            border: 1px solid rgba(0, 242, 152, 0.5);
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 11px;
        }

        .badge-available {
            background: rgba(0, 242, 152, 0.15);
            color: var(--success);
            border: 1px solid rgba(0, 242, 152, 0.4);
            padding: 4px 10px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 11px;
        }

        .badge-fast {
            background: rgba(255, 184, 0, 0.15);
            color: var(--warning);
            border: 1px solid rgba(255, 184, 0, 0.4);
            padding: 4px 10px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 11px;
        }

        .btn-table {
            padding: 6px 14px;
            font-size: 11px;
            border-radius: 6px;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }

        .log-container {
            max-height: 480px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 10px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            padding-right: 4px;
        }

        .log-item {
            background: rgba(14, 19, 31, 0.7);
            border-left: 3px solid var(--electric-blue);
            padding: 10px 12px;
            border-radius: 0 8px 8px 0;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .log-item.SUCCESS {
            border-left-color: var(--success);
        }

        .log-item.WARNING, .log-item.BLOCKED {
            border-left-color: var(--warning);
        }

        .log-item.ERROR {
            border-left-color: var(--danger);
        }

        .log-time {
            font-size: 10px;
            color: var(--text-muted);
        }

        .log-msg {
            color: var(--text-primary);
            word-break: break-word;
        }

        #toast {
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: rgba(14, 19, 31, 0.95);
            border: 1px solid var(--electric-blue);
            color: #FFFFFF;
            padding: 16px 24px;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6), 0 0 20px var(--electric-blue-glow);
            font-size: 14px;
            display: none;
            z-index: 9999;
            backdrop-filter: blur(12px);
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="brand">
                <div class="brand-icon">⚡</div>
                <div class="brand-title">
                    <h1>AVENGERS: DOOMSDAY BOOKING ALERT</h1>
                    <p>Ritzy Sha Cinemas 4K RGB Laser & Dolby Atmos, Madurai • Telegram Channel Only</p>
                </div>
            </div>
            <div class="header-actions">
                <!-- PROMINENT BUTTON: CHECK DOOMSDAY BOOKINGS -->
                <a href="https://in.bookmyshow.com/cinemas/madurai/ritzy-sha-cinemas-4k-rgb-laser-atmos-madurai/buytickets/RZYM" 
                   target="_blank" 
                   class="btn-hero-check" 
                   id="btnCheckDoomsday">
                    🎟️ CHECK DOOMSDAY BOOKINGS ↗
                </a>
                <button class="btn btn-telegram" onclick="triggerTestTelegram()">
                    <span>✈️ Test Telegram</span>
                </button>
            </div>
        </header>

        <!-- Spotlight & Stats Grid -->
        <div class="spotlight-grid">
            <div class="glass-card movie-card">
                <div class="movie-poster-wrap">
                    <img src="https://images.unsplash.com/photo-1534447677768-be436bb09401?q=80&w=600&auto=format&fit=crop" alt="Avengers Doomsday Poster" id="posterImg">
                </div>
                <span class="cinema-badge">📍 Ritzy Sha Cinemas, Madurai</span>
                <div class="movie-title">Avengers: Doomsday</div>
                <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 8px;">Cinema Code: <code>RZYM</code> • 4K RGB Laser Atmos</p>
                <a href="https://in.bookmyshow.com/cinemas/madurai/ritzy-sha-cinemas-4k-rgb-laser-atmos-madurai/buytickets/RZYM" target="_blank" class="btn btn-table btn-primary" style="margin-top: 6px;">
                    🔗 Open BMS Venue Page ↗
                </a>
            </div>

            <div class="glass-card">
                <div class="section-header">
                    <span class="section-title">📊 Real-Time Monitoring Telemetry</span>
                    <span id="systemStatusPill" class="status-pill status-live">
                        <span class="pulse-dot"></span> <span id="statusText">LIVE VERIFIED</span>
                    </span>
                </div>

                <div class="stats-grid">
                    <div class="stat-box">
                        <span class="stat-label">Last Verification Time</span>
                        <span class="stat-value" id="lastVerificationTime" style="font-size: 13px; color: var(--success);">--:--:--</span>
                    </div>
                    <div class="stat-box">
                        <span class="stat-label">Next Scheduled Check</span>
                        <span class="stat-value" id="nextScheduledCheck" style="font-size: 13px; color: var(--electric-blue);">--:--:--</span>
                    </div>
                    <div class="stat-box">
                        <span class="stat-label">Confirmed Live Shows</span>
                        <span class="stat-value" id="liveVerifiedCount" style="color: var(--success);">0</span>
                    </div>
                    <div class="stat-box">
                        <span class="stat-label">Telegram Alerts Sent</span>
                        <span class="stat-value" id="tgAlertsCount" style="color: var(--electric-blue);">0</span>
                    </div>
                    <div class="stat-box">
                        <span class="stat-label">Monitoring Cadence</span>
                        <span class="stat-value">5 min (24/7)</span>
                    </div>
                    <div class="stat-box">
                        <span class="stat-label">Telegram Channel</span>
                        <span class="stat-value" style="font-size: 13px; color: #38B8FF;">Chat ID 5188160752</span>
                    </div>
                </div>

                <div style="background: rgba(14, 19, 31, 0.9); border: 1px solid var(--border-glass); border-radius: 12px; padding: 14px; margin-top: 14px;">
                    <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;">Last Automated Diagnosis:</div>
                    <div id="lastCheckResult" style="font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--electric-blue);">
                        Initializing monitor engine...
                    </div>
                </div>
            </div>
        </div>

        <!-- CONVENIENT MANUAL VERIFICATION & ONE-CLICK CONFIRMATION PANEL -->
        <div class="verification-panel">
            <div class="verification-header">
                <div class="verification-title">
                    <span>🛡️</span> Visual Booking Verification & One-Click Telegram Dispatch
                </div>
                <a href="https://in.bookmyshow.com/cinemas/madurai/ritzy-sha-cinemas-4k-rgb-laser-atmos-madurai/buytickets/RZYM" 
                   target="_blank" 
                   class="btn btn-primary" 
                   style="font-size: 13px; font-weight: 700;">
                    🌐 Open Ritzy Sha on BMS (RZYM) ↗
                </a>
            </div>

            <div style="background: rgba(255, 68, 68, 0.12); border: 1px solid rgba(255, 68, 68, 0.4); border-radius: 10px; padding: 12px 16px; margin-top: 12px; margin-bottom: 16px; font-size: 13px; color: #FFA8A8; display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 18px;">🛑</span>
                <span><strong>STRICT SAFEGUARD ACTIVE:</strong> Only genuine future booking dates (Asia/Kolkata timezone) are accepted. Past dates, test clicks, and unconfirmed simulations are strictly blocked. All confirmations are logged to the permanent audit trail.</span>
            </div>

            <p style="font-size: 13px; color: var(--text-secondary); line-height: 1.6;">
                Step 1: Click <strong>"CHECK DOOMSDAY BOOKINGS"</strong> above to inspect the live Ritzy Sha Cinemas page.<br>
                Step 2: When real Avengers: Doomsday showtimes appear open with bookable seats, fill in the date and time below.<br>
                Step 3: Check the certification checkbox and click <strong>"CONFIRM BOOKINGS OPEN & SEND TELEGRAM ALERT"</strong>.
            </p>

            <div class="form-grid">
                <div class="input-group">
                    <label>Show Date (Asia/Kolkata)</label>
                    <input type="date" id="manualDate" class="input-control" required>
                </div>
                <div class="input-group">
                    <label>
                        <span>Showtime</span>
                        <span style="font-size: 11px; color: var(--text-muted);">Pick quick time:</span>
                    </label>
                    <input type="text" id="manualTime" class="input-control" placeholder="06:45 PM" value="06:45 PM" required>
                    <div class="quick-pills">
                        <button type="button" class="pill-btn" onclick="setTime('10:15 AM')">10:15 AM</button>
                        <button type="button" class="pill-btn" onclick="setTime('02:30 PM')">02:30 PM</button>
                        <button type="button" class="pill-btn" onclick="setTime('06:45 PM')">06:45 PM</button>
                        <button type="button" class="pill-btn" onclick="setTime('10:00 PM')">10:00 PM</button>
                    </div>
                </div>
                <div class="input-group">
                    <label>Operator Name (Required for Audit Log)</label>
                    <input type="text" id="manualOperator" class="input-control" value="Shri Dharsan" placeholder="Your Name" required>
                </div>
                <div class="input-group">
                    <label>Screen Name</label>
                    <input type="text" id="manualScreen" class="input-control" value="4K RGB Laser Atmos (Audi 1)">
                </div>
                <div class="input-group">
                    <label>Booking Status</label>
                    <select id="manualStatus" class="input-control" style="background: #070A12;">
                        <option value="AVAILABLE">AVAILABLE (Seats Bookable)</option>
                        <option value="FILLING_FAST">FILLING_FAST (Fast Filling)</option>
                    </select>
                </div>
                <div class="input-group" style="grid-column: 1 / -1;">
                    <label>Direct Booking URL</label>
                    <input type="text" id="manualLink" class="input-control" value="https://in.bookmyshow.com/cinemas/madurai/ritzy-sha-cinemas-4k-rgb-laser-atmos-madurai/buytickets/RZYM">
                </div>

                <div style="grid-column: 1 / -1; margin-top: 6px;">
                    <label style="display: flex; align-items: flex-start; gap: 12px; cursor: pointer; background: rgba(0, 210, 255, 0.05); padding: 14px 16px; border-radius: 10px; border: 1px solid rgba(0, 210, 255, 0.3);">
                        <input type="checkbox" id="manualVisualConfirm" style="margin-top: 3px; transform: scale(1.3); accent-color: var(--electric-blue); cursor: pointer;" />
                        <span style="font-size: 13px; color: #FFFFFF; font-weight: 600; line-height: 1.5;">
                            I certify under audit logging that I have opened BookMyShow for Ritzy Sha Cinemas Madurai (RZYM) and visually verified that actual seats are bookable right now for this showtime.
                        </span>
                    </label>
                </div>
            </div>

            <!-- ONE-CLICK CONFIRMATION BUTTON -->
            <button class="btn-confirm-live" onclick="submitOneClickConfirmation()" id="btnConfirmLive">
                <span>⚡ CONFIRM BOOKINGS OPEN & SEND TELEGRAM ALERT</span>
            </button>
        </div>

        <!-- Detected Showtimes & Activity Logs -->
        <div class="content-grid">
            <div class="glass-card">
                <div class="section-header">
                    <span class="section-title">🎟️ Confirmed Live Showtimes (Deduplicated)</span>
                    <span style="font-size: 12px; color: var(--text-secondary);" id="totalShowsSummary">0 shows tracked</span>
                </div>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Showtime</th>
                                <th>Verification</th>
                                <th>Status</th>
                                <th>Telegram Alert</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody id="showsTableBody">
                            <tr>
                                <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">
                                    No live verified showtimes yet. Use the verification form above once bookings open.
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="glass-card">
                <div class="section-header">
                    <span class="section-title">📜 Real-Time Diagnostics & Audit Log</span>
                    <button class="btn" style="padding: 4px 10px; font-size: 11px;" onclick="loadDashboardData()">🔄 Refresh</button>
                </div>
                <div class="log-container" id="logsContainer">
                    <div class="log-item">
                        <span class="log-time">System Startup</span>
                        <span class="log-msg">Connecting to database and telemetry stream...</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Toast UI -->
    <div id="toast">Alert dispatched</div>

    <script>
        document.getElementById('manualDate').valueAsDate = new Date();

        function setTime(t) {
            document.getElementById('manualTime').value = t;
        }

        function showToast(msg, isSuccess = true) {
            const t = document.getElementById('toast');
            t.innerText = msg;
            t.style.borderColor = isSuccess ? '#00F298' : '#FFB800';
            t.style.display = 'block';
            setTimeout(() => { t.style.display = 'none'; }, 5000);
        }

        async function loadDashboardData() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();

                document.getElementById('lastVerificationTime').innerText = data.stats.last_verification_time || 'Not yet verified';
                document.getElementById('nextScheduledCheck').innerText = data.stats.next_scheduled_check || 'In 5 minutes';
                document.getElementById('lastCheckResult').innerText = data.stats.last_check_result || 'N/A';
                document.getElementById('liveVerifiedCount').innerText = data.stats.live_verified_count || 0;
                document.getElementById('tgAlertsCount').innerText = data.stats.tg_sent || 0;

                const statusPill = document.getElementById('systemStatusPill');
                const statusText = document.getElementById('statusText');
                const sourceState = data.stats.source_state || 'SOURCE_UNAVAILABLE';
                statusText.innerText = sourceState;

                if (sourceState === 'LIVE_VERIFIED') {
                    statusPill.className = 'status-pill status-live';
                } else {
                    statusPill.className = 'status-pill status-unavailable';
                }

                // Render Shows Table
                const tbody = document.getElementById('showsTableBody');
                if (data.shows && data.shows.length > 0) {
                    document.getElementById('totalShowsSummary').innerText = `${data.shows.length} shows tracked`;
                    tbody.innerHTML = data.shows.map(s => {
                        let badgeClass = 'badge-available';
                        if (s.booking_status === 'FILLING_FAST') badgeClass = 'badge-fast';
                        if (s.booking_status === 'SOLD_OUT') badgeClass = 'badge-sold';

                        const modeBadge = '<span class="badge-live-verified">🟢 LIVE VERIFIED</span>';
                        const tgSent = s.telegram_alert_sent ? '✅ Delivered' : '⏳ Pending';

                        return `
                            <tr>
                                <td><strong>${s.show_date}</strong></td>
                                <td style="font-family: 'JetBrains Mono', monospace; color: var(--electric-blue);">${s.show_time}</td>
                                <td>${modeBadge}</td>
                                <td><span class="${badgeClass}">${s.booking_status}</span></td>
                                <td style="font-size: 11px;">${tgSent}</td>
                                <td>
                                    <a href="${s.booking_link}" target="_blank" class="btn btn-table btn-primary">
                                        Book Tickets ↗
                                    </a>
                                </td>
                            </tr>
                        `;
                    }).join('');
                } else {
                    document.getElementById('totalShowsSummary').innerText = '0 shows tracked';
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">
                                No live verified showtimes yet.
                            </td>
                        </tr>
                    `;
                }

                // Render Logs
                const logContainer = document.getElementById('logsContainer');
                if (data.logs && data.logs.length > 0) {
                    logContainer.innerHTML = data.logs.map(l => `
                        <div class="log-item ${l.level || ''}">
                            <span class="log-time">[${l.created_at}] ${l.event_type}</span>
                            <span class="log-msg">${l.message}</span>
                        </div>
                    `).join('');
                }
            } catch (e) {
                console.error("Failed to load dashboard data:", e);
            }
        }

        async function triggerTestTelegram() {
            showToast("🚀 Sending test ping to Telegram...");
            try {
                const res = await fetch('/api/test/telegram', { method: 'POST' });
                const r = await res.json();
                showToast(r.success ? "Telegram notification delivered!" : "Telegram failed: " + r.message);
                await loadDashboardData();
            } catch (e) {
                showToast("Failed to test Telegram: " + e, false);
            }
        }

        async function submitOneClickConfirmation() {
            const date = document.getElementById('manualDate').value;
            const time = document.getElementById('manualTime').value;
            const operator = (document.getElementById('manualOperator').value || '').trim();
            const screen = document.getElementById('manualScreen').value;
            const link = document.getElementById('manualLink').value;
            const status = document.getElementById('manualStatus').value;
            const isConfirmed = document.getElementById('manualVisualConfirm').checked;

            if (!date || !time) {
                alert("Please select both Show Date and Showtime.");
                return;
            }

            if (!operator) {
                alert("Please enter Operator Name for the audit log.");
                return;
            }

            if (!isConfirmed) {
                alert("Validation Requirement: You must check the certification checkbox confirming that you visually checked the BookMyShow venue page and confirmed seats are bookable.");
                return;
            }

            const btn = document.getElementById('btnConfirmLive');
            btn.disabled = true;
            btn.innerText = "⏳ VALIDATING & DISPATCHING ALERT...";

            try {
                const res = await fetch('/api/manual-verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        show_date: date,
                        show_time: time,
                        operator_name: operator,
                        visually_confirmed: isConfirmed,
                        screen_name: screen,
                        booking_link: link || undefined,
                        booking_status: status
                    })
                });
                const r = await res.json();

                if (!res.ok) {
                    showToast(`❌ REJECTED: ${r.detail || r.message || 'Validation failed'}`, false);
                } else if (r.duplicate) {
                    showToast(`⚠️ Duplicate Suppressed: This showtime was already alerted at ${r.alert_timestamp}.`, false);
                } else {
                    showToast(`🚨 CONFIRMED! Telegram booking alert dispatched immediately!`, true);
                }
                await loadDashboardData();
            } catch (e) {
                showToast("Verification request failed: " + e, false);
            } finally {
                btn.disabled = false;
                btn.innerHTML = "<span>⚡ CONFIRM BOOKINGS OPEN & SEND TELEGRAM ALERT</span>";
            }
        }

        // Initialize minimum date to today in IST
        try {
            const todayIST = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });
            const dateInput = document.getElementById('manualDate');
            dateInput.min = todayIST;
            if (!dateInput.value || dateInput.value < todayIST) {
                dateInput.value = todayIST;
            }
        } catch (e) {
            console.log("Could not set min date:", e);
        }

        loadDashboardData();
        setInterval(loadDashboardData, 8000);
    </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard_index():
    return HTMLResponse(content=DASHBOARD_HTML, status_code=200)


@app.get("/api/status")
async def get_system_status():
    stats = db.get_summary_stats()
    shows = db.get_all_detected_shows(limit=50)
    # Filter shows for dashboard so only LIVE_VERIFIED shows are presented
    live_shows = [s for s in shows if s.get("verification_mode") == "LIVE_VERIFIED"]
    logs = db.get_recent_logs(limit=40)
    audit_logs = db.get_verification_audit_logs(limit=20)
    return {
        "stats": stats,
        "shows": live_shows,
        "logs": logs,
        "audit_logs": audit_logs,
        "telegram_configured": Config.is_telegram_configured(),
    }


@app.get("/api/audit-logs")
async def get_audit_logs():
    return {"audit_logs": db.get_verification_audit_logs(limit=50)}


@app.post("/api/check-now")
async def manual_check(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_scan_and_alert)
    return {"status": "triggered", "message": "BookMyShow scan initiated in background"}


@app.post("/api/test/telegram")
async def test_telegram():
    result = telegram_client.send_test_message()
    if result["success"]:
        db.log_event("SUCCESS", "ALERT_TG", "Test simulation alert dispatched to Telegram successfully.")
    else:
        db.log_event("ERROR", "ALERT_TG", f"Telegram test dispatch failed: {result['message']}")
    return result


@app.post("/api/manual-verify")
async def manual_verify(req: ManualVerifyRequest, background_tasks: BackgroundTasks, request: Request):
    """
    Operator One-Click Verification Fallback with Strict Validation Safeguards:
    1. Rejects if visually_confirmed is False.
    2. Rejects if operator_name is missing.
    3. Strictly validates show_date and show_time against Asia/Kolkata timezone (rejects past dates).
    4. Records an explicit audit log entry in verification_audit_log.
    5. Deduplicates: if already alerted, suppresses duplicate alert.
    6. Dispatches genuine LIVE_VERIFIED booking alert to Telegram.
    """
    if not req.visually_confirmed:
        raise HTTPException(
            status_code=400,
            detail="Visual verification certification required. You must check the confirmation checkbox after verifying seats on BookMyShow."
        )

    clean_op = (req.operator_name or "").strip()
    if not clean_op or len(clean_op) < 2:
        raise HTTPException(
            status_code=400,
            detail="Operator name is required for verification audit logging."
        )

    client_ip = request.client.host if request.client else "127.0.0.1"

    try:
        show_id, is_new, is_duplicate, show_record, prev_time = monitor.record_manual_verification(
            show_date=req.show_date,
            show_time=req.show_time,
            operator_name=clean_op,
            visually_confirmed=req.visually_confirmed,
            booking_link=req.booking_link,
            screen_name=req.screen_name or "4K RGB Laser Atmos (Audi 1)",
            booking_status=req.booking_status or "AVAILABLE",
            ip_address=client_ip,
        )
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

    if is_duplicate:
        return {
            "status": "duplicate_suppressed",
            "duplicate": True,
            "message": f"Showtime {req.show_date} {req.show_time} was already alerted at {prev_time}. Duplicate notification suppressed.",
            "alert_timestamp": prev_time,
        }

    # Dispatch immediately
    background_tasks.add_task(dispatch_pending_alerts)
    return {
        "status": "confirmed_and_dispatched",
        "duplicate": False,
        "show_id": show_id,
        "verification_mode": "LIVE_VERIFIED",
        "show": show_record,
    }


# ---------------------------------------------------------------------------
# Application Startup Lifecycle
# ---------------------------------------------------------------------------

def run_application():
    """Bootstraps workers and Web server using native asyncio."""
    logger.info(f"Starting Glassmorphism Dashboard on http://{Config.DASHBOARD_HOST}:{Config.DASHBOARD_PORT}")
    config = uvicorn.Config(app, host=Config.DASHBOARD_HOST, port=Config.DASHBOARD_PORT, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    server.run()


if __name__ == "__main__":
    run_application()
