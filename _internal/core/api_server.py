import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Any, Dict, Optional, Callable

class LocalAPIServer:
    """
    Lightweight Local REST API Server running on 127.0.0.1:5000.
    Connects standalone bot modules with Core Browser Profile Manager & GUI.
    """
    def __init__(self, profile_mgr: Any, host: str = "127.0.0.1", port: int = 5000) -> None:
        self.profile_mgr = profile_mgr
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.log_callbacks = []

    def register_log_callback(self, cb: Callable[[str, str], None]) -> None:
        """Register GUI callback to receive live log messages from bots."""
        self.log_callbacks.append(cb)

    def _emit_log(self, bot_name: str, message: str) -> None:
        for cb in self.log_callbacks:
            try:
                cb(bot_name, message)
            except Exception:
                pass

    def start(self) -> None:
        api_self = self

        class RequestHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return # Suppress default HTTP console logging

            def _send_json(self, data: Any, status: int = 200) -> None:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode("utf-8"))

            def do_GET(self):
                parsed = urlparse(self.path)
                path = parsed.path.rstrip("/")
                qs = parse_qs(parsed.query)

                if path in ("/landing", "/splash", "/profile_splash", "/newtab"):
                    pid = qs.get("id", [""])[0]
                    req_no = qs.get("no", [""])[0]
                    p_data = api_self.profile_mgr.get_profile_by_id(pid) if api_self.profile_mgr and pid else None
                    if not p_data:
                        p_data = {
                            "id": pid or req_no or "01",
                            "number": req_no or "01",
                            "name": qs.get("name", [f"Profile {req_no or '01'}"])[0],
                            "group": qs.get("group", ["Default"])[0],
                            "tags": qs.get("tag", [""])[0],
                            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
                        }
                    elif req_no:
                        p_data = dict(p_data)
                        p_data["number"] = req_no
                    
                    html_content = render_profile_landing_html(p_data)
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(html_content.encode("utf-8"))
                    return

                if path == "/api/profiles":
                    profiles = api_self.profile_mgr.profiles if api_self.profile_mgr else []
                    self._send_json({"success": True, "profiles": profiles})
                    return

                if path.startswith("/api/profiles/"):
                    pid = path.replace("/api/profiles/", "")
                    p = api_self.profile_mgr.get_profile_by_id(pid) if api_self.profile_mgr else None
                    if p:
                        self._send_json({"success": True, "profile": p})
                    else:
                        self._send_json({"success": False, "error": "Profile not found"}, 404)
                    return

                self._send_json({"success": False, "error": "Endpoint not found"}, 404)

            def do_POST(self):
                parsed = urlparse(self.path)
                path = parsed.path.rstrip("/")
                content_len = int(self.headers.get("Content-Length", 0))
                body_bytes = self.rfile.read(content_len) if content_len > 0 else b""
                try:
                    payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                except Exception:
                    payload = {}

                if path == "/api/logs":
                    bot_name = payload.get("bot_name", "Bot Engine")
                    msg = payload.get("message", "")
                    api_self._emit_log(bot_name, msg)
                    self._send_json({"success": True})
                    return

                if path.startswith("/api/profiles/") and path.endswith("/cookies"):
                    pid = path.replace("/api/profiles/", "").replace("/cookies", "")
                    cookie_str = payload.get("cookie", "")
                    if api_self.profile_mgr and cookie_str:
                        api_self.profile_mgr.update_profile(pid, {"cookie": cookie_str})
                        self._send_json({"success": True})
                    else:
                        self._send_json({"success": False, "error": "Invalid profile or missing cookie"}, 400)
                    return

                self._send_json({"success": False, "error": "Endpoint not found"}, 404)

        for try_port in range(self.port, self.port + 20):
            try:
                self.server = HTTPServer((self.host, try_port), RequestHandler)
                self.port = try_port
                self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
                self.thread.start()
                try:
                    print(f"[Local API Server] Running on http://{self.host}:{self.port}")
                except Exception:
                    pass
                break
            except OSError:
                try:
                    print(f"[Local API Server] Port {try_port} busy, testing fallback port {try_port + 1}...")
                except Exception:
                    pass
            except Exception as err:
                try:
                    print(f"[Local API Server] Failed to start on port {try_port}: {err}")
                except Exception:
                    pass
                break

    def stop(self) -> None:
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
            self.server = None


def render_profile_landing_html(profile_data: Dict[str, Any]) -> str:
    """Render an ultra-modern dark Anti-Detect Profile Dashboard with live status and Google search."""
    raw_num = str(profile_data.get("number", "01")).replace("Profile", "").replace("#", "").strip()
    if raw_num.isdigit():
        num_str = f"{int(raw_num)}"
    else:
        num_str = raw_num or "01"

    p_name = profile_data.get("name", f"Profile {num_str}")
    p_group = profile_data.get("group", "Default")
    p_proxy_type = profile_data.get("proxy_type", "None")
    p_host = profile_data.get("proxy_host", "").strip()
    p_port = profile_data.get("proxy_port", "").strip()

    if p_proxy_type in ("HTTP", "SOCKS5") and p_host:
        proxy_display = f"{p_proxy_type} ({p_host}:{p_port})"
    else:
        proxy_display = "Direct Connection (Local IP)"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>srkBrowser • Profile #{num_str}</title>
  <style>
    * {{
      margin: 0;
      padding: 0;
      box-sizing: border-box;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }}
    body {{
      background: radial-gradient(circle at 50% 20%, #1e1b4b 0%, #0f172a 50%, #0b0f19 100%);
      color: #e2e8f0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: space-between;
      padding: 24px 20px;
      overflow-x: hidden;
    }}

    /* Top Status Bar */
    .top-bar {{
      width: 100%;
      max-width: 960px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 12px;
      padding: 10px 18px;
      background: rgba(30, 41, 59, 0.6);
      border: 1px solid rgba(139, 92, 246, 0.25);
      border-radius: 14px;
      backdrop-filter: blur(12px);
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    }}
    .brand-group {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .brand-title {{
      font-size: 15px;
      font-weight: 800;
      color: #ffffff;
      letter-spacing: 0.5px;
    }}
    .status-chips {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .chip {{
      font-size: 11.5px;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: 8px;
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }}
    .chip-profile {{
      background: linear-gradient(135deg, rgba(124, 58, 237, 0.35), rgba(37, 99, 235, 0.35));
      border: 1px solid rgba(139, 92, 246, 0.5);
      color: #c4b5fd;
    }}
    .chip-proxy {{
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: #6ee7b7;
    }}
    .chip-shield {{
      background: rgba(6, 182, 212, 0.15);
      border: 1px solid rgba(6, 182, 212, 0.4);
      color: #67e8f9;
    }}
    .pulse-dot {{
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #10b981;
      box-shadow: 0 0 8px #10b981;
      animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
      0% {{ transform: scale(0.95); opacity: 0.8; }}
      50% {{ transform: scale(1.2); opacity: 1; }}
      100% {{ transform: scale(0.95); opacity: 0.8; }}
    }}

    /* Main Center Content */
    .main-center {{
      display: flex;
      flex-direction: column;
      align-items: center;
      width: 100%;
      max-width: 640px;
      margin: auto 0;
    }}
    .google-logo {{
      font-size: 68px;
      font-weight: 600;
      letter-spacing: -2px;
      margin-bottom: 26px;
      user-select: none;
      filter: drop-shadow(0 4px 12px rgba(66, 133, 244, 0.2));
    }}
    .google-logo span:nth-child(1) {{ color: #4285f4; }}
    .google-logo span:nth-child(2) {{ color: #ea4335; }}
    .google-logo span:nth-child(3) {{ color: #fbbc05; }}
    .google-logo span:nth-child(4) {{ color: #4285f4; }}
    .google-logo span:nth-child(5) {{ color: #34a853; }}
    .google-logo span:nth-child(6) {{ color: #ea4335; }}

    .search-box {{
      width: 100%;
      position: relative;
    }}
    .search-input {{
      width: 100%;
      height: 52px;
      border-radius: 26px;
      background: rgba(30, 41, 59, 0.85);
      border: 1.5px solid rgba(148, 163, 184, 0.2);
      padding: 0 24px 0 52px;
      font-size: 15.5px;
      color: #ffffff;
      outline: none;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    .search-input:focus {{
      border-color: #8b5cf6;
      background: rgba(30, 41, 59, 0.98);
      box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.25), 0 8px 28px rgba(0, 0, 0, 0.45);
    }}
    .search-icon {{
      position: absolute;
      left: 18px;
      top: 16px;
      width: 20px;
      height: 20px;
      fill: #94a3b8;
    }}

    /* Speed Dial Shortcuts */
    .shortcuts {{
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 12px;
      margin-top: 34px;
      width: 100%;
    }}
    .shortcut-item {{
      display: flex;
      flex-direction: column;
      align-items: center;
      text-decoration: none;
      color: #cbd5e1;
      font-size: 12px;
      font-weight: 500;
      width: 76px;
      padding: 12px 6px;
      border-radius: 12px;
      background: rgba(30, 41, 59, 0.35);
      border: 1px solid rgba(255, 255, 255, 0.05);
      transition: all 0.2s;
    }}
    .shortcut-item:hover {{
      background: rgba(51, 65, 85, 0.7);
      border-color: rgba(139, 92, 246, 0.4);
      transform: translateY(-2px);
      color: #ffffff;
    }}
    .shortcut-icon {{
      width: 44px;
      height: 44px;
      border-radius: 12px;
      background: rgba(15, 23, 42, 0.8);
      border: 1px solid rgba(255, 255, 255, 0.08);
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 8px;
      font-size: 20px;
      font-weight: 700;
    }}

    /* Footer */
    .footer {{
      font-size: 11px;
      color: #64748b;
      letter-spacing: 0.3px;
    }}
  </style>
</head>
<body>
  <!-- Top Bar -->
  <div class="top-bar">
    <div class="brand-group">
      <span class="brand-title">🌐 srkBrowser</span>
    </div>
    <div class="status-chips">
      <span class="chip chip-profile">👑 #{num_str} • {p_name}</span>
      <span class="chip chip-proxy"><span class="pulse-dot"></span>{proxy_display}</span>
      <span class="chip chip-shield">🛡️ Anti-Detect Active</span>
    </div>
  </div>

  <!-- Center Search Box -->
  <div class="main-center">
    <div class="google-logo">
      <span>G</span><span>o</span><span>o</span><span>g</span><span>l</span><span>e</span>
    </div>
    
    <form class="search-box" action="https://www.google.com/search" method="GET">
      <svg class="search-icon" focusable="false" viewBox="0 0 24 24">
        <path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"></path>
      </svg>
      <input class="search-input" type="text" name="q" placeholder="Search Google or enter web address..." autofocus autocomplete="off" />
    </form>

    <!-- Speed Dial Shortcuts -->
    <div class="shortcuts">
      <a class="shortcut-item" href="https://www.google.com">
        <div class="shortcut-icon" style="color:#4285f4;">G</div>
        <span>Google</span>
      </a>
      <a class="shortcut-item" href="https://www.facebook.com">
        <div class="shortcut-icon" style="color:#1877f2;">f</div>
        <span>Facebook</span>
      </a>
      <a class="shortcut-item" href="https://www.youtube.com">
        <div class="shortcut-icon" style="color:#ff0000;">▶</div>
        <span>YouTube</span>
      </a>
      <a class="shortcut-item" href="https://x.com">
        <div class="shortcut-icon" style="color:#ffffff;">𝕏</div>
        <span>Twitter / X</span>
      </a>
      <a class="shortcut-item" href="https://www.amazon.com">
        <div class="shortcut-icon" style="color:#f59e0b;">a</div>
        <span>Amazon</span>
      </a>
      <a class="shortcut-item" href="https://ipinfo.io" target="_blank">
        <div class="shortcut-icon" style="color:#10b981;">🌐</div>
        <span>IP Info</span>
      </a>
      <a class="shortcut-item" href="https://browserleaks.com/webrtc" target="_blank">
        <div class="shortcut-icon" style="color:#06b6d4;">🛡️</div>
        <span>WebRTC</span>
      </a>
    </div>
  </div>

  <!-- Footer -->
  <div class="footer">
    srkBrowser Engine v2.0 • Isolated Anti-Detect Environment
  </div>
</body>
</html>"""
    return html

    return html

