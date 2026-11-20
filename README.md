# 🛡️ Avengers: Doomsday Booking Alert Bot — Ritzy Sha Cinemas, Madurai (Telegram Only)

Automated movie ticket booking alert system engineered in Python to notify you exclusively via **Telegram** the moment *Avengers: Doomsday* tickets open at **Ritzy Sha Cinemas, Madurai**.

---

## 📌 Target Details
* **Movie:** *Avengers: Doomsday*
* **Cinema:** Ritzy Sha Cinemas (4K RGB Laser & Dolby Atmos)
* **Location:** Anna Salai, Gandhi Nagar / Shenoy Nagar, Madurai, Tamil Nadu, India
* **Platform:** BookMyShow
* **Cinema Code:** `RITM`
* **Direct BMS Link:** [https://in.bookmyshow.com/madurai/cinemas/ritzy-sha-cinemas-4k-rgb-laser-atmos-madurai/RITM](https://in.bookmyshow.com/madurai/cinemas/ritzy-sha-cinemas-4k-rgb-laser-atmos-madurai/RITM)
* **Notification Channel:** **Telegram Only** (WhatsApp completely removed)
* **Monitoring Interval:** Every 5 minutes (300 seconds)
* **Monitoring Horizon:** 14 upcoming days

---

## ⚡ Cloudflare Anti-Bot Notice & Live Verification Status

### Live Network Diagnostic
When accessing BookMyShow from a cloud VPS IP address (including Oracle Cloud, AWS, GCP):
1. **Cloudflare Turnstile WAF:** BookMyShow returns `HTTP 403 Forbidden` with a Cloudflare bot challenge (`cf-mitigated: challenge`).
2. **Anti-Bot Compliance:** The bot strictly follows safety and compliance standards:
   * It **never** attempts to solve, click through, or bypass Cloudflare CAPTCHAs.
   * It logs the status as `BLOCKED_BY_CLOUDFLARE` on the dashboard.
   * It avoids hammering the server.
3. **To enable live scraping from your Windows VPS:**
   * **Residential Proxy:** In `.env`, set `BMS_PROXY=http://user:password@residential-proxy-ip:port`. Residential IPs pass Cloudflare verification cleanly.
   * **Run on Home Connection:** Running this bot on your personal home computer connects directly without Turnstile triggers.
   * **Simulate Booking Opening:** You can verify the full alert pipeline anytime by clicking **"Simulate Opening"** on the dashboard or sending `/test` to the Telegram bot.

---

## 📢 Telegram Bot Setup

* **Bot Username:** `@RitzyDoomsdayAlertBot`
* **Bot ID:** `9101491571`
* **Chat ID:** `5188160752`
* **Verified Status:** Tested and confirmed live delivery.

### Alert Message Format:
```text
🚨 AVENGERS: DOOMSDAY BOOKING OPEN!

Cinema: Ritzy Sha Cinemas
Location: Madurai
Movie: Avengers: Doomsday
Show Date: 2026-05-01
Showtime: 06:45 PM
Booking Status: AVAILABLE

🎟️ BOOK YOUR TICKETS:
https://in.bookmyshow.com/booktickets/RITM/SESSION_ID
```

### Interactive Telegram Commands:
* `/start` — View bot information, cinema target, and command reference.
* `/status` — View current monitoring telemetry, total shows, and alert counters.
* `/test` — Dispatches an immediate test booking alert.
* `/check` — Triggers an immediate BookMyShow scan.

---

## 🖥️ Running Directly on Your Windows VPS via Remote Desktop

No Oracle Cloud API keys, OCI SDK credentials, or Meta WhatsApp credentials are required. Everything runs locally on your existing Windows machine.

### Step 1: Connect via Remote Desktop (RDP)
Connect to your Windows VPS desktop using Windows Remote Desktop Connection (`mstsc.exe`).

### Step 2: Open PowerShell
Press `Win + X` and select **Terminal** or **Windows PowerShell**.

Navigate to the project folder:
```powershell
cd C:\Users\opc\.gemini\antigravity\scratch\avengers_booking_bot
```

### Step 3: Verify Environment Configuration (.env)
The `.env` file already contains your Telegram Bot Token and Chat ID:
```env
TELEGRAM_BOT_TOKEN=9101491571:AAE8c4qyg7G99aEXFWTjHHjdIYnrQI4jyGI
TELEGRAM_CHAT_ID=5188160752
```

### Step 4: Run the Test Suite
Verify that all 8 unit, integration, and diagnostic tests pass:
```powershell
.\.venv\Scripts\pytest.exe test_suite.py -v
```

### Step 5: Start the Bot Service
Launch the continuous background runner and watchdog:
```powershell
.\run_service.ps1
```
This runs the bot continuously, checks BookMyShow every 5 minutes, polls for Telegram commands, and restarts automatically if terminated.

### Step 6: Access the Dashboard
Open your browser (or VPS browser) to:
```
http://localhost:8080
```
* **Theme:** Matte black (`#07090E`), Electric blue (`#00D2FF`), Violet highlights (`#8A2BE2`) glassmorphism UI.
* **Controls:** 
  * **🔍 Check BMS Now** — Manual immediate scan across dates.
  * **✈️ Test Telegram** — Sends a live test alert to your Telegram chat.
  * **🧪 Simulate Opening** — Injects a bookable Avengers show to test the live Telegram alert.

---

## ⚙️ Automatic Startup on Windows Reboot

To ensure the bot restarts automatically whenever your Windows VPS reboots:

Open PowerShell as Administrator and run:
```powershell
$Action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-ExecutionPolicy Bypass -File C:\Users\opc\.gemini\antigravity\scratch\avengers_booking_bot\run_service.ps1"
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "AvengersBookingAlertBot" -Action $Action -Trigger $Trigger -Principal $Principal -Description "24/7 Avengers Doomsday Telegram Ticket Alert"
```
