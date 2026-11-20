# 🛡️ Avengers: Doomsday Booking Alert Bot — Ritzy Sha Cinemas, Madurai (Telegram Only)

Automated movie ticket booking alert system engineered in Python to notify you exclusively via **Telegram** the moment *Avengers: Doomsday* tickets open at **Ritzy Sha Cinemas, Madurai**.

---

## 📌 Target Details
* **Movie:** *Avengers: Doomsday*
* **Cinema:** Ritzy Sha Cinemas (4K RGB Laser & Dolby Atmos)
* **Location:** Anna Salai, Gandhi Nagar / Shenoy Nagar, Madurai, Tamil Nadu, India
* **Platform:** BookMyShow
* **Cinema Code:** `RZYM`
* **Direct BMS Link:** [https://in.bookmyshow.com/cinemas/madurai/ritzy-sha-cinemas-4k-rgb-laser-atmos-madurai/buytickets/RZYM](https://in.bookmyshow.com/cinemas/madurai/ritzy-sha-cinemas-4k-rgb-laser-atmos-madurai/buytickets/RZYM)
* **Notification Channel:** **Telegram Only** (WhatsApp completely removed)
* **Monitoring Interval:** Every 5 minutes (300 seconds)
* **Monitoring Horizon:** 14 upcoming days
* **Timezone Standard:** `Asia/Kolkata` (IST, UTC+5:30)

---

## 🛑 Strict Safeguards & Date Validation (Asia/Kolkata)

To eliminate false-positive alerts, past dates, or accidental test alerts:

1. **Past Date & Time Rejection:**
   * Validated strictly against `Asia/Kolkata` timezone.
   * Any booking date before today in IST (e.g., `2026-05-01`, `2026-05-02`) is automatically rejected with HTTP 400.
   * If today's date is entered, any showtime prior to the current IST clock time is rejected.
2. **Visual Certification Required:**
   * A `LIVE_VERIFIED` alert is only dispatched when the operator explicitly certifies visual confirmation on the official BookMyShow page.
   * Requires non-empty Operator Name for audit tracking.
3. **Simulation Isolation:**
   * Simulated test notifications are strictly isolated with `🧪 [SIMULATED TEST ONLY - NOT A REAL BOOKING]` and can never be labeled as `LIVE_VERIFIED`.
4. **Permanent Audit Trail:**
   * All verifications and rejected attempts are permanently recorded in `verification_audit_log` with IST timestamp, operator name, show details, and action status.
5. **Deduplication:**
   * Prevents repeat alerts for already-notified showtimes.

---

## ⚡ Cloudflare Anti-Bot Notice & Live Verification Status

### Live Network Diagnostic
When accessing BookMyShow from a cloud VPS IP address (including Oracle Cloud, AWS, GCP):
1. **Cloudflare Turnstile WAF:** BookMyShow returns a Cloudflare bot challenge.
2. **Anti-Bot Compliance:** The bot strictly follows safety and compliance standards:
   * It **never** attempts to solve, click through, or bypass Cloudflare CAPTCHAs.
   * It accurately logs the status as `SOURCE_UNAVAILABLE` on the dashboard.
3. **Convenient Visual Verification Fallback:**
   * Click **"CHECK DOOMSDAY BOOKINGS"** on the dashboard to open Ritzy Sha's live BookMyShow page.
   * If showtimes are open, certify and confirm via the form to immediately dispatch the Telegram alert.

---

## 📢 Telegram Bot Setup

* **Bot Username:** `@RitzyDoomsdayAlertBot`
* **Bot ID:** `9101491571`
* **Chat ID:** `5188160752`
* **Verified Status:** Tested and confirmed live delivery.

### Live Verified Alert Format:
```text
🚨 AVENGERS: DOOMSDAY BOOKING OPEN! [LIVE VERIFIED]

Cinema: Ritzy Sha Cinemas (RZYM)
Location: Madurai
Movie: Avengers: Doomsday
Show Date: [Valid Future Date]
Showtime: [Time] IST
Screen: 4K RGB Laser Atmos (Audi 1)
Booking Status: AVAILABLE (CONFIRMED)

👤 Visually Confirmed By: [Operator Name]
🕒 Confirmed At: [Timestamp] IST

🎟️ BOOK YOUR TICKETS NOW:
https://in.bookmyshow.com/cinemas/madurai/ritzy-sha-cinemas-4k-rgb-laser-atmos-madurai/buytickets/RZYM
```

### Simulated Test Alert Format:
```text
🧪 [SIMULATED TEST ONLY - NOT A REAL BOOKING]
⚠️ THIS IS A TEST PING TO VERIFY TELEGRAM DELIVERY.
NO REAL TICKETS ARE CURRENTLY BOOKABLE.
...
```

### Interactive Telegram Commands:
* `/start` — View bot information, cinema target, and command reference.
* `/status` — View current monitoring telemetry, total shows, and alert counters.
* `/test` — Dispatches an immediate test simulation alert.
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

### Step 3: Run the Test Suite
Verify that all 13 unit, integration, and safeguard tests pass:
```powershell
.\.venv\Scripts\python.exe -m pytest -v test_suite.py
```

### Step 4: 24/7 Background Service & Startup Execution
The application automatically starts upon Windows login via the startup VBS launcher at:
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AvengersBookingBot.vbs`

To manually restart or run the background service with watchdog recovery:
```powershell
.\run_service.ps1
```
The glassmorphism dashboard is accessible at: `http://localhost:8080`.

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
