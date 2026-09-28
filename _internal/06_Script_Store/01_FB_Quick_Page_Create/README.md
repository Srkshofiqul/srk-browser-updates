# ⚡ FB 1-Click Quick Page Creator Script

**Module ID:** `fb_quick_page_create`  
**Version:** `2.2.0`  
**Category:** Facebook Automation Tools / Profile Card Scripts  
**Target:** 1-Click Page Creation directly from `srkBrowser` profile cards  

---

## 🌟 Features
1. **1-Click Execution from Profile Cards**:
   - Integrates a `📄+` Quick Page Create icon directly on each browser profile card.
2. **Dual Mode Creation**:
   - 🎲 **Random Mode**: Auto-generates smart, natural brand names and categories with 1 click.
   - ✏️ **Custom Mode**: Allows entering custom page names and selecting any verified Facebook category (`Digital Creator`, `Personal Blog`, `Health/beauty`, `Shopping & Retail`, etc.).
3. **High-Speed Stealth Mutation**:
   - Creates the page in **~1.5 seconds** directly in Facebook's backend.
   - 100% invisible on screen with zero interference.
4. **Direct ID & Permanent Link Capture**:
   - Instantly captures the created Page ID and permanent page link (`https://www.facebook.com/profile.php?id=...`).

---

## 📁 Package Contents
- `manifest.json`: Script metadata, permissions, and profile card trigger definitions.
- `quick_page_creator_modal.py`: Frameless cyber-themed interactive dialog with Random vs Custom mode.
- `quick_page_creator_engine.py`: 1-Click background Playwright mutation executor.
- `quick_page_creator_inject.js`: Optimized stealth injection script with dynamic category support.
- `main.py`: Standalone test launcher.

---

## 🚀 Testing Standalone:
```powershell
python 06_Script_Store/01_FB_Quick_Page_Create/main.py
```
