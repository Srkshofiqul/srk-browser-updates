# 🤖 srkBrowser Facebook Bulk ID Login Bot

Official **Facebook Bulk ID Login Studio** for `srkBrowser` Anti-Detect Browser Platform.

---

## 🌟 Key Features

1. **🔐 Multi-State Login Intelligence:**
   - Detects all Facebook states: Authenticated Feed, 2FA Screen, Wrong Password, Checkpoint/Lock, Device Approval, Captcha Challenge, and Account Chooser.
2. **🔑 Automated 2FA TOTP Generation & Submission:**
   - Automatically calculates 6-digit TOTP codes from 2FA Secret keys and bypasses 2FA prompts seamlessly.
3. **📸 Diagnostic Failure Screenshots:**
   - Automatically captures high-resolution screenshots for any failed profile or unrecognized page into `reports/screenshots/`.
4. **🍪 Automatic Cookie Injection & Session Persistence:**
   - Injects existing cookies or extracts fresh session cookies after successful login.
5. **📊 Automated Timestamped CSV Reports:**
   - Generates detailed execution reports in `reports/` with profile number, status, message, screenshot path, and duration.
6. **🚀 Native srkBrowser Chromium Process Control:**
   - Runs with custom numbered taskbar icons, anti-detect noise spoofing, and clean graceful process termination.

---

## 📂 Project Architecture

```
03_Automation_Bots/01_FB_Bulk_Login/
├── main.py                  # Bot entry point
├── run_test.py              # Studio test runner
├── fb_bulk_login_engine.py  # Playwright multi-threaded browser automation core
├── fb_bulk_login_helpers.py # Multi-state detector, 2FA solver, human simulation & screenshots
├── fb_bulk_login_security.py# srkBrowser heartbeat & VIP license synchronization
├── fb_bulk_login_ui.py      # Dark obsidian studio dashboard UI
└── reports/                 # Output CSV reports & screenshots/
```

---
Developed for **srkBrowser Modular Automation Platform**.
