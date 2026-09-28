# 🌐 FB 1-Click Language Converter (Script Module)

**Version:** 2.3.0  
**Author:** srkBrowser Automation Lab  
**Category:** Facebook Tools  
**Action Type:** Profile Card Modal / Script Store  

---

## ⚡ Overview
The **FB 1-Click Language Converter** is a high-speed, lightweight automation script that allows users to switch any Facebook account language directly from the srkBrowser profile cards or script store in **under 1.5 seconds**.

It utilizes Facebook's internal GraphQL mutation API (`doc_id: 29960775910235124`) to update language preferences server-side with zero manual clicking.

---

## 🎯 Supported Locales
- 🌐 **English (US)** (`en_US`) — Default
- 🇬🇧 **English (UK)** (`en_GB`)
- 🇪🇸 **Español (Latinoamérica)** (`es_LA`)
- 🇫🇷 **Français (France)** (`fr_FR`)
- 🇧🇷 **Português (Brasil)** (`pt_BR`)
- 🇧🇩 **বাংলা (Bengali)** (`bn_IN`)
- 🇸🇦 **العربية (Arabic)** (`ar_AR`)
- 🇮🇳 **हिन्दी (Hindi)** (`hi_IN`)

---

## 🛡️ Anti-Bot Safety
- Built-in human delay timer (0.5s – 10.0s configurable)
- Clean, direct GraphQL payload with active `fb_dtsg` and `c_user` session validation
- Silent Headless mode support for background operations

---

## 📂 File Structure
```text
02_FB_Language_Converter/
├── manifest.json                  # Script metadata & store manifest definition
├── fb_language_converter_engine.py # Core Playwright + GraphQL execution engine
├── fb_lang_convert_modal.py       # High-tech Cyber UI dialog
├── main.py                        # Standalone testing runner
└── README.md                      # Documentation
```
