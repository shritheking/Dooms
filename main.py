"""
Main entry point for Avengers: Doomsday Booking Alert Bot (Telegram Only).
Orchestrates:
1. Periodic Playwright monitoring loop (checks every 5 minutes across dates).
2. Telegram bot command polling (/start, /status, /test, /check).
3. Telegram alert dispatch with duplicate prevention.
4. Modern FastAPI Dashboard with matte black, electric blue, and violet glassmorphism UI.
"""

import asyncio
import datetime
import logging
import threading
import time
from typing import Optional, Dict, Any

import uvicorn
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import Config
from database import Database
from monitor import BookingMonitor
from telegram_bot import TelegramBot

# Setup logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
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
        logger.info(f"Dispatching Telegram alert for show ID {show_id}...")
        tg_ok = telegram_client.send_alert(show)
        if tg_ok:
            db.mark_alert_sent(show_id)
            db.log_event(
                "SUCCESS",
                "ALERT_TG",
                f"Telegram alert sent for {show['movie_title']} ({show['show_date']} {show['show_time']})",
            )
        else:
            db.mark_alert_error(show_id, "Telegram delivery failed")


def execute_scan_synchronous():
    """Wrapper to run async Playwright scan inside a standard thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(monitor.run_full_scan())
        dispatch_pending_alerts()
        return result
    finally:
        loop.close()


def monitor_scheduler_loop():
    """Continuous background loop running full scans at configured 5-minute intervals."""
    logger.info(f"Monitoring scheduler active. Interval: {Config.CHECK_INTERVAL_SECONDS} seconds.")
    # Run immediate initial check on launch
    time.sleep(2)
    execute_scan_synchronous()

    while True:
        try:
            time.sleep(Config.CHECK_INTERVAL_SECONDS)
            execute_scan_synchronous()
        except Exception as e:
            logger.error(f"Error in monitor scheduler loop: {e}")
            db.log_event("ERROR", "SYSTEM", f"Scheduler loop encountered exception: {e}")
            time.sleep(30)


# ---------------------------------------------------------------------------
# Modern Glassmorphism Dashboard HTML (Telegram Focused)
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Avengers: Doomsday — Telegram Booking Alert Center</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #07090E;
            --bg-surface: #0E131F;
            --bg-card: rgba(18, 24, 38, 0.75);
            --electric-blue: #00D2FF;
            --electric-blue-glow: rgba(0, 210, 255, 0.25);
            --electric-accent: #0070F3;
            --violet: #8A2BE2;
            --violet-glow: rgba(138, 43, 226, 0.25);
            --text-primary: #F0F6FC;
            --text-secondary: #8B949E;
            --text-muted: #586069;
            --border-glass: rgba(0, 210, 255, 0.14);
            --border-glass-violet: rgba(138, 43, 226, 0.20);
            --success: #00F298;
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
                radial-gradient(circle at 15% 20%, rgba(0, 210, 255, 0.08) 0%, transparent 45%),
                radial-gradient(circle at 85% 80%, rgba(138, 43, 226, 0.08) 0%, transparent 45%),
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
            width: 50px;
            height: 50px;
            border-radius: 12px;
            background: linear-gradient(135deg, #00D2FF 0%, #8A2BE2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 26px;
            box-shadow: 0 0 20px var(--electric-blue-glow);
        }

        .brand-title h1 {
            font-size: 22px;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: linear-gradient(90deg, #FFFFFF 30%, #00D2FF 70%, #9D4EDD 100%);
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
            padding: 10px 20px;
            border-radius: 10px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            backdrop-filter: blur(8px);
        }

        .btn:hover {
            transform: translateY(-2px);
            border-color: var(--electric-blue);
            box-shadow: 0 0 16px var(--electric-blue-glow);
        }

        .btn-primary {
            background: linear-gradient(135deg, rgba(0, 210, 255, 0.25) 0%, rgba(138, 43, 226, 0.25) 100%);
            border: 1px solid var(--electric-blue);
            color: #00D2FF;
        }

        .btn-telegram {
            background: linear-gradient(135deg, rgba(0, 136, 204, 0.25) 0%, rgba(0, 210, 255, 0.25) 100%);
            border: 1px solid #0088CC;
            color: #38B8FF;
        }

        .btn-telegram:hover {
            border-color: #38B8FF;
            box-shadow: 0 0 16px rgba(0, 136, 204, 0.4);
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

        .movie-poster-wrap:hover img {
            transform: scale(1.03);
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
            font-size: 22px;
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

        .status-active {
            background: rgba(0, 242, 152, 0.15);
            color: var(--success);
            border: 1px solid rgba(0, 242, 152, 0.3);
        }

        .status-warning {
            background: rgba(255, 184, 0, 0.15);
            color: var(--warning);
            border: 1px solid rgba(255, 184, 0, 0.3);
        }

        .status-error {
            background: rgba(255, 59, 48, 0.15);
            color: var(--danger);
            border: 1px solid rgba(255, 59, 48, 0.3);
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

        .content-grid {
            display: grid;
            grid-template-columns: 2fr 1.2fr;
            gap: 24px;
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

        .badge-sold {
            background: rgba(255, 59, 48, 0.15);
            color: var(--danger);
            border: 1px solid rgba(255, 59, 48, 0.4);
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

        .info-alert {
            background: rgba(0, 136, 204, 0.12);
            border: 1px solid rgba(0, 210, 255, 0.25);
            border-radius: 12px;
            padding: 14px 18px;
            font-size: 13px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 12px;
            color: #38B8FF;
        }

        #toast {
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: rgba(14, 19, 31, 0.95);
            border: 1px solid var(--electric-blue);
            color: #FFFFFF;
            padding: 14px 20px;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6), 0 0 20px var(--electric-blue-glow);
            font-size: 13px;
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
                    <h1>AVENGERS: DOOMSDAY ALERT BOT</h1>
                    <p>Ritzy Sha Cinemas 4K RGB Laser & Dolby Atmos, Madurai • Telegram Channel Only</p>
                </div>
            </div>
            <div class="header-actions">
                <button class="btn btn-primary" onclick="triggerManualCheck()" id="btnCheck">
                    <span id="checkSpinner" style="display:none;">⏳</span>
                    <span>🔍 Check BMS Now</span>
                </button>
                <button class="btn btn-telegram" onclick="triggerTestTelegram()">
                    <span>✈️ Test Telegram</span>
                </button>
                <button class="btn" onclick="simulateBookingOpen()" title="Simulate Avengers booking open for test">
                    <span>🧪 Simulate Opening</span>
                </button>
            </div>
        </header>

        <!-- Informational banner -->
        <div class="info-alert">
            <span>🛡️</span>
            <div>
                <strong>Telegram Alert Channel Active:</strong> Connected to Telegram Bot (<code>@RitzyDoomsdayAlertBot</code>, Chat ID: <code>5188160752</code>). Checking Ritzy Sha Cinemas BookMyShow listing every 5 minutes across the 14-day horizon.
            </div>
        </div>

        <!-- Spotlight & Stats Grid -->
        <div class="spotlight-grid">
            <!-- Movie Poster Card -->
            <div class="glass-card movie-card">
                <div class="movie-poster-wrap">
                    <img src="https://images.unsplash.com/photo-1534447677768-be436bb09401?q=80&w=600&auto=format&fit=crop" alt="Avengers Doomsday Poster" id="posterImg">
                </div>
                <span class="cinema-badge">📍 Ritzy Sha Cinemas, Madurai</span>
                <div class="movie-title">Avengers: Doomsday</div>
                <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 8px;">Target Code: <code>RITM</code> • 4K RGB Laser Atmos</p>
                <a href="https://in.bookmyshow.com/madurai/cinemas/ritzy-sha-cinemas-4k-rgb-laser-atmos-madurai/RITM" target="_blank" class="btn btn-table btn-primary" style="margin-top: 6px;">
                    🔗 Open BMS Cinema Page ↗
                </a>
            </div>

            <!-- Stats & Status Details -->
            <div class="glass-card">
                <div class="section-header">
                    <span class="section-title">📊 Real-Time Monitoring Telemetry</span>
                    <span id="systemStatusPill" class="status-pill status-active">
                        <span class="pulse-dot"></span> <span id="statusText">ACTIVE</span>
                    </span>
                </div>

                <div class="stats-grid">
                    <div class="stat-box">
                        <span class="stat-label">Last Check Time</span>
                        <span class="stat-value" id="lastCheckTime" style="font-size: 15px;">--:--:--</span>
                    </div>
                    <div class="stat-box">
                        <span class="stat-label">Check Cadence</span>
                        <span class="stat-value">5 min</span>
                    </div>
                    <div class="stat-box">
                        <span class="stat-label">Available Shows</span>
                        <span class="stat-value" id="availShowsCount" style="color: var(--success);">0</span>
                    </div>
                    <div class="stat-box">
                        <span class="stat-label">Telegram Alerts Sent</span>
                        <span class="stat-value" id="tgAlertsCount" style="color: var(--electric-blue);">0</span>
                    </div>
                    <div class="stat-box">
                        <span class="stat-label">Telegram Status</span>
                        <span class="stat-value" style="font-size: 14px; color: #38B8FF;">Chat ID 5188160752</span>
                    </div>
                    <div class="stat-box">
                        <span class="stat-label">Monitoring Horizon</span>
                        <span class="stat-value">14 Days</span>
                    </div>
                </div>

                <div style="background: rgba(14, 19, 31, 0.9); border: 1px solid var(--border-glass); border-radius: 12px; padding: 14px; margin-top: 14px;">
                    <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;">Last Scan Diagnosis:</div>
                    <div id="lastCheckResult" style="font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--electric-blue);">
                        Initializing monitor engine...
                    </div>
                </div>
            </div>
        </div>

        <!-- Detected Showtimes & Activity Logs -->
        <div class="content-grid">
            <!-- Shows Table -->
            <div class="glass-card">
                <div class="section-header">
                    <span class="section-title">🎟️ Detected Showtimes & Booking State</span>
                    <span style="font-size: 12px; color: var(--text-secondary);" id="totalShowsSummary">0 shows tracked</span>
                </div>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Showtime</th>
                                <th>Screen</th>
                                <th>Booking Status</th>
                                <th>Telegram Alert</th>
                                <th>Direct Action</th>
                            </tr>
                        </thead>
                        <tbody id="showsTableBody">
                            <tr>
                                <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">
                                    No Avengers: Doomsday showtimes detected yet. Booking has not opened on BookMyShow.
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Activity Logs -->
            <div class="glass-card">
                <div class="section-header">
                    <span class="section-title">📜 System Activity & Diagnostics</span>
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
        function showToast(msg) {
            const t = document.getElementById('toast');
            t.innerText = msg;
            t.style.display = 'block';
            setTimeout(() => { t.style.display = 'none'; }, 4000);
        }

        async function loadDashboardData() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();

                // Update Stats
                document.getElementById('lastCheckTime').innerText = data.stats.last_check_time || 'Never';
                document.getElementById('lastCheckResult').innerText = data.stats.last_check_result || 'N/A';
                document.getElementById('availShowsCount').innerText = data.stats.available_shows || 0;
                document.getElementById('tgAlertsCount').innerText = data.stats.tg_sent || 0;

                // Status pill
                const statusPill = document.getElementById('systemStatusPill');
                const statusText = document.getElementById('statusText');
                const status = data.stats.monitoring_status || 'IDLE';
                statusText.innerText = status;

                if (status === 'ACTIVE') {
                    statusPill.className = 'status-pill status-active';
                } else if (status.includes('BLOCKED')) {
                    statusPill.className = 'status-pill status-warning';
                } else {
                    statusPill.className = 'status-pill status-error';
                }

                // Render Shows Table
                const tbody = document.getElementById('showsTableBody');
                if (data.shows && data.shows.length > 0) {
                    document.getElementById('totalShowsSummary').innerText = `${data.shows.length} shows tracked`;
                    tbody.innerHTML = data.shows.map(s => {
                        let badgeClass = 'badge-available';
                        if (s.booking_status === 'FILLING_FAST') badgeClass = 'badge-fast';
                        if (s.booking_status === 'SOLD_OUT') badgeClass = 'badge-sold';

                        const tgSent = s.telegram_alert_sent ? '✅ Sent' : '⏳ Pending';

                        return `
                            <tr>
                                <td><strong>${s.show_date}</strong></td>
                                <td style="font-family: 'JetBrains Mono', monospace; color: var(--electric-blue);">${s.show_time}</td>
                                <td><span style="font-size:11px; color:var(--text-secondary);">${s.screen_name}</span></td>
                                <td><span class="${badgeClass}">${s.booking_status}</span></td>
                                <td style="font-size: 11px;">${tgSent}</td>
                                <td>
                                    <a href="${s.booking_link}" target="_blank" class="btn btn-table btn-primary">
                                        Book Now ↗
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
                                No Avengers: Doomsday showtimes detected yet. Booking has not opened on BookMyShow.
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

        async function triggerManualCheck() {
            const btn = document.getElementById('btnCheck');
            const spinner = document.getElementById('checkSpinner');
            spinner.style.display = 'inline';
            btn.disabled = true;

            showToast("🔍 Triggering BookMyShow scan across dates...");
            try {
                const res = await fetch('/api/check-now', { method: 'POST' });
                const r = await res.json();
                showToast("Check completed: " + (r.result?.last_check_result || "Success"));
                await loadDashboardData();
            } catch (e) {
                showToast("Error executing scan: " + e);
            } finally {
                spinner.style.display = 'none';
                btn.disabled = false;
            }
        }

        async function triggerTestTelegram() {
            showToast("🚀 Sending test alert to Telegram...");
            try {
                const res = await fetch('/api/test/telegram', { method: 'POST' });
                const r = await res.json();
                showToast(r.success ? "Telegram notification delivered!" : "Telegram failed: " + r.message);
                await loadDashboardData();
            } catch (e) {
                showToast("Failed to test Telegram: " + e);
            }
        }

        async function simulateBookingOpen() {
            showToast("🧪 Simulating Avengers booking opening...");
            try {
                const res = await fetch('/api/simulate-show', { method: 'POST' });
                const r = await res.json();
                showToast("Simulation triggered! Alert dispatched to Telegram.");
                await loadDashboardData();
            } catch (e) {
                showToast("Simulation failed: " + e);
            }
        }

        // Auto refresh every 8 seconds
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
    logs = db.get_recent_logs(limit=40)
    return {
        "stats": stats,
        "shows": shows,
        "logs": logs,
        "telegram_configured": Config.is_telegram_configured(),
    }


@app.post("/api/check-now")
async def manual_check(background_tasks: BackgroundTasks):
    background_tasks.add_task(execute_scan_synchronous)
    return {"status": "triggered", "message": "BookMyShow scan initiated in background"}


@app.post("/api/test/telegram")
async def test_telegram():
    result = telegram_client.send_test_message()
    if result["success"]:
        db.log_event("SUCCESS", "ALERT_TG", "Test alert dispatched to Telegram successfully.")
    else:
        db.log_event("ERROR", "ALERT_TG", f"Telegram test dispatch failed: {result['message']}")
    return result


@app.post("/api/simulate-show")
async def simulate_show(background_tasks: BackgroundTasks):
    """
    Simulation endpoint to verify the full end-to-end alert pipeline.
    Inserts a realistic bookable showtime and immediately dispatches alerts to Telegram.
    """
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    mock_show = {
        "cinema_name": Config.CINEMA_NAME,
        "cinema_code": Config.CINEMA_CODE,
        "movie_title": Config.MOVIE_TITLE,
        "show_date": tomorrow,
        "show_time": "06:45 PM",
        "screen_name": "4K RGB Laser Atmos (Audi 1)",
        "session_id": "SIM998877",
        "booking_status": "AVAILABLE",
        "booking_link": f"https://in.bookmyshow.com/booktickets/{Config.CINEMA_CODE}/SIM998877",
    }
    show_id, is_new, is_bookable = db.record_showtime(mock_show)
    db.log_event(
        "INFO",
        "CHECK",
        f"Simulated bookable show created for {mock_show['movie_title']} ({mock_show['show_date']} {mock_show['show_time']})",
    )
    background_tasks.add_task(dispatch_pending_alerts)
    return {
        "status": "success",
        "show_id": show_id,
        "is_new": is_new,
        "show": mock_show,
    }


# ---------------------------------------------------------------------------
# Application Startup Lifecycle
# ---------------------------------------------------------------------------

def run_application():
    """Bootstraps workers, Telegram poller, and Web server."""
    logger.info("Initializing Avengers: Doomsday Telegram Alert Bot...")

    # Start Telegram command polling thread (/start, /status, /test, /check)
    telegram_client.start_polling(db, on_manual_check=execute_scan_synchronous)

    # Start background monitoring loop thread (5-minute intervals)
    scheduler_thread = threading.Thread(
        target=monitor_scheduler_loop,
        daemon=True,
        name="BookingMonitorScheduler",
    )
    scheduler_thread.start()

    logger.info(f"Starting Glassmorphism Dashboard on http://{Config.DASHBOARD_HOST}:{Config.DASHBOARD_PORT}")
    uvicorn.run(app, host=Config.DASHBOARD_HOST, port=Config.DASHBOARD_PORT, log_level="warning")


if __name__ == "__main__":
    run_application()
