# FB 1-Click Auto Re-login (`FBRL`)

**Script ID:** `fb_relogin`  
**Short Name:** `FBRL`  
**Version:** `1.0.0`  
**Category:** `Facebook Tools`  

## Overview
Automated 1-Click Facebook session recovery and re-authentication script for srkBrowser Desktop.
Designed to operate directly on the user's active, live browser session over Chrome DevTools Protocol (CDP).

## Key Features
1. **Smart Context First Inspection:**
   - Detects if the current tab is already on Facebook's Continue screen.
   - If Continue screen is present, bypasses redundant cookie injection and directly enters the password from database.
2. **Pure Python 2FA TOTP Solver:**
   - Instant RFC-6238 6-digit one-time password generation from profile's 2FA secret key.
3. **Session Cookie Persistence:**
   - Harvests fresh session cookies upon successful login.
   - Synchronizes back to SQLite database, Chromium SQLite cookie store, and `sr_cookie_injector` extension.
4. **Compact Card Badge:**
   - Shows as `🔑 FBRL` directly on the profile card.
