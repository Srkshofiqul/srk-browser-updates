# -*- coding: utf-8 -*-
"""
🛡️ Facebook Bulk Page Creator - Local Proxy Bridge & Dynamic Router
Author: srkBrowser Automation Lab
Description: Lightweight, pure Python standard library HTTP/HTTPS proxy gateway
supporting dynamic on-the-fly switching between Direct PC Internet and Upstream
Residential Proxies (e.g. DataImpulse) with zero third-party dependencies.
"""

import socket
import select
import threading
import base64
import re
import time
import urllib.request
import urllib.error
from typing import Optional, Tuple, Dict, Any, List


def parse_proxy_string(raw_str: str) -> Optional[Dict[str, Any]]:
    """
    Parses proxy string in common formats:
    - user:pass@host:port
    - http://user:pass@host:port
    - host:port:user:pass
    - host:port
    Returns dict: {'host': str, 'port': int, 'user': str, 'pass': str, 'auth_header': str} or None.
    """
    if not raw_str or not str(raw_str).strip():
        return None

    s = str(raw_str).strip()
    # Strip protocol prefix if present
    s = re.sub(r"^(?:https?|socks5?|socks)://", "", s, flags=re.IGNORECASE)

    host = ""
    port = 0
    user = ""
    password = ""

    # Format 1: user:password@host:port
    if "@" in s:
        parts = s.split("@", 1)
        auth_part = parts[0]
        host_port_part = parts[1]
        
        if ":" in auth_part:
            u_p = auth_part.split(":", 1)
            user, password = u_p[0], u_p[1]
        else:
            user = auth_part

        if ":" in host_port_part:
            h_p = host_port_part.split(":", 1)
            host = h_p[0].strip()
            try:
                port = int(h_p[1].strip())
            except ValueError:
                return None
        else:
            host = host_port_part.strip()
            port = 80

    # Format 2: host:port:user:pass OR host:port
    else:
        parts = s.split(":")
        if len(parts) == 4:
            host = parts[0].strip()
            try:
                port = int(parts[1].strip())
            except ValueError:
                return None
            user = parts[2].strip()
            password = parts[3].strip()
        elif len(parts) == 2:
            host = parts[0].strip()
            try:
                port = int(parts[1].strip())
            except ValueError:
                return None
        else:
            return None

    if not host or port <= 0 or port > 65535:
        return None

    auth_header = ""
    if user:
        token = base64.b64encode(f"{user}:{password}".encode("latin1")).decode("ascii")
        auth_header = f"Basic {token}"

    return {
        "host": host,
        "port": port,
        "user": user,
        "pass": password,
        "auth_header": auth_header,
        "raw": s
    }


def test_proxy_connection(proxy_str: str, timeout: float = 8.0) -> Tuple[bool, str, str]:
    """
    Tests proxy connectivity by querying an external IP reflection API.
    Returns: (success: bool, ip_or_error: str, country_or_detail: str)
    """
    p_info = parse_proxy_string(proxy_str)
    if not p_info:
        return False, "Invalid proxy format (Use user:pass@host:port or host:port:user:pass)", ""

    proxy_url = f"http://{p_info['user']}:{p_info['pass']}@{p_info['host']}:{p_info['port']}" if p_info['user'] else f"http://{p_info['host']}:{p_info['port']}"
    
    proxy_handler = urllib.request.ProxyHandler({
        'http': proxy_url,
        'https': proxy_url
    })
    opener = urllib.request.build_opener(proxy_handler)

    test_endpoints = [
        ("http://api.ipify.org", "plain"),
        ("http://ifconfig.me/ip", "plain"),
        ("http://ip-api.com/json", "json")
    ]

    for url, fmt in test_endpoints:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with opener.open(req, timeout=timeout) as resp:
                data = resp.read().decode("utf-8", errors="ignore").strip()
                if fmt == "plain":
                    ip_match = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", data)
                    if ip_match:
                        detected_ip = ip_match.group(1)
                        # Extract country hint from username if DataImpulse
                        country_hint = ""
                        m_cr = re.search(r"__cr\.([a-zA-Z]{2})", p_info['user'])
                        if m_cr:
                            country_hint = m_cr.group(1).upper()
                        return True, detected_ip, country_hint or "Residential"
                elif fmt == "json":
                    import json
                    j = json.loads(data)
                    detected_ip = j.get("query", "")
                    country = j.get("countryCode", "") or j.get("country", "")
                    if detected_ip:
                        return True, detected_ip, country
        except Exception:
            continue

    return False, "Connection timed out or credentials rejected", ""


def test_multiple_proxies(proxy_list: List[str], timeout: float = 6.0) -> Dict[str, Any]:
    """
    Tests multiple proxies concurrently using ThreadPoolExecutor.
    Returns dict:
      {
        'total': int,
        'success_count': int,
        'failed_count': int,
        'results': List[Dict[str, Any]]
      }
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    clean_list = [p.strip() for p in proxy_list if p and p.strip() and not p.strip().startswith("#")]
    if not clean_list:
        return {"total": 0, "success_count": 0, "failed_count": 0, "results": []}

    results: List[Dict[str, Any]] = []
    max_workers = min(len(clean_list), 10)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_proxy = {
            executor.submit(test_proxy_connection, p, timeout): p
            for p in clean_list
        }
        for future in as_completed(future_to_proxy):
            p_str = future_to_proxy[future]
            try:
                ok, ip_or_err, country = future.result()
                results.append({
                    "proxy": p_str,
                    "ok": ok,
                    "ip_or_err": ip_or_err,
                    "country": country
                })
            except Exception as e:
                results.append({
                    "proxy": p_str,
                    "ok": False,
                    "ip_or_err": str(e),
                    "country": ""
                })

    success_count = sum(1 for r in results if r["ok"])
    failed_count = len(results) - success_count

    return {
        "total": len(results),
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results
    }


class LocalProxyBridge:
    """
    Local HTTP/HTTPS Proxy Gateway running on 127.0.0.1.
    Supports dynamic on-the-fly toggling between DIRECT (PC Internet) and
    UPSTREAM (DataImpulse / custom residential proxy).
    """

    def __init__(self, upstream_proxy: Optional[str] = None, initial_mode: str = "DIRECT") -> None:
        self.upstream_info = parse_proxy_string(upstream_proxy) if upstream_proxy else None
        self.mode = initial_mode.upper()  # 'DIRECT' or 'UPSTREAM'
        self.server_socket: Optional[socket.socket] = None
        self.port: int = 0
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._active_connections: List[Tuple[socket.socket, socket.socket]] = []
        self._lock = threading.Lock()

    def set_upstream_proxy(self, proxy_str: str) -> bool:
        """Updates the upstream proxy configuration."""
        parsed = parse_proxy_string(proxy_str)
        if parsed:
            with self._lock:
                self.upstream_info = parsed
            return True
        return False

    def set_mode(self, mode: str) -> None:
        """
        Dynamically changes routing mode:
        'DIRECT': Routes through local PC internet (0 proxy bandwidth).
        'UPSTREAM': Routes through upstream proxy.
        Recycles active tunnel sockets so subsequent requests immediately adopt new route.
        """
        new_mode = mode.upper()
        with self._lock:
            if self.mode != new_mode:
                self.mode = new_mode
                # Recycle active connections so Chrome creates new connections taking the new route
                self._recycle_active_tunnels()

    def get_mode(self) -> str:
        with self._lock:
            return self.mode

    def _recycle_active_tunnels(self) -> None:
        """Closes active tunnels so subsequent requests immediately adopt the new route."""
        to_close = list(self._active_connections)
        self._active_connections.clear()
        for c_sock, r_sock in to_close:
            try:
                c_sock.close()
            except Exception:
                pass
            try:
                r_sock.close()
            except Exception:
                pass

    def start(self) -> int:
        """Starts the local proxy server on an ephemeral free port."""
        if self.is_running:
            return self.port

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Bind to 127.0.0.1 and port 0 to let OS assign a free port
        self.server_socket.bind(("127.0.0.1", 0))
        self.port = self.server_socket.getsockname()[1]
        self.server_socket.listen(128)
        self.is_running = True

        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        return self.port

    def stop(self) -> None:
        """Gracefully shuts down the local proxy bridge."""
        self.is_running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        self._recycle_active_tunnels()

    def _accept_loop(self) -> None:
        while self.is_running:
            try:
                client_sock, _ = self.server_socket.accept()
                client_sock.settimeout(60.0)
                t = threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True)
                t.start()
            except Exception:
                if not self.is_running:
                    break

    def _handle_client(self, client_sock: socket.socket) -> None:
        remote_sock: Optional[socket.socket] = None
        try:
            # Read client initial request line & headers
            req_data = b""
            while b"\r\n\r\n" not in req_data:
                chunk = client_sock.recv(4096)
                if not chunk:
                    break
                req_data += chunk
                if len(req_data) > 65536:
                    break

            if not req_data:
                client_sock.close()
                return

            header_end = req_data.find(b"\r\n\r\n")
            if header_end == -1:
                client_sock.close()
                return

            raw_headers = req_data[:header_end].decode("latin1", errors="ignore")
            extra_body = req_data[header_end + 4:]
            lines = raw_headers.split("\r\n")
            if not lines:
                client_sock.close()
                return

            request_line = lines[0]
            parts = request_line.split(" ")
            if len(parts) < 3:
                client_sock.close()
                return

            method, target, version = parts[0].upper(), parts[1], parts[2]

            with self._lock:
                current_mode = self.mode
                up_info = dict(self.upstream_info) if self.upstream_info else None

            # --- HTTPS CONNECT TUNNEL (e.g. www.facebook.com:443) ---
            if method == "CONNECT":
                dest_host, dest_port = self._parse_host_port(target, default_port=443)

                # ROUTE A: DIRECT (Local PC Internet)
                if current_mode == "DIRECT" or not up_info:
                    remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    remote_sock.settimeout(30.0)
                    remote_sock.connect((dest_host, dest_port))
                    client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")

                # ROUTE B: UPSTREAM PROXY (DataImpulse / Residential)
                else:
                    remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    remote_sock.settimeout(30.0)
                    remote_sock.connect((up_info["host"], up_info["port"]))

                    # Send CONNECT request to upstream proxy with Auth
                    connect_req = f"CONNECT {dest_host}:{dest_port} HTTP/1.1\r\nHost: {dest_host}:{dest_port}\r\n"
                    if up_info.get("auth_header"):
                        connect_req += f"Proxy-Authorization: {up_info['auth_header']}\r\n"
                    connect_req += "Proxy-Connection: keep-alive\r\n\r\n"

                    remote_sock.sendall(connect_req.encode("latin1"))

                    # Read upstream proxy response
                    up_resp = b""
                    while b"\r\n\r\n" not in up_resp:
                        c = remote_sock.recv(2048)
                        if not c:
                            break
                        up_resp += c
                        if len(up_resp) > 8192:
                            break

                    first_line = up_resp.split(b"\r\n")[0].decode("latin1", errors="ignore")
                    if " 200 " in first_line or first_line.startswith("HTTP/1.1 200") or first_line.startswith("HTTP/1.0 200"):
                        client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                    else:
                        client_sock.sendall(up_resp)
                        client_sock.close()
                        remote_sock.close()
                        return

                # Bidirectional raw TLS pipe between browser and destination
                self._pipe_sockets(client_sock, remote_sock)

            # --- PLAIN HTTP REQUEST (e.g. GET http://...) ---
            else:
                dest_host, dest_port = self._parse_host_port(target, default_port=80)
                if current_mode == "DIRECT" or not up_info:
                    remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    remote_sock.settimeout(30.0)
                    remote_sock.connect((dest_host, dest_port))
                    remote_sock.sendall(req_data)
                else:
                    remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    remote_sock.settimeout(30.0)
                    remote_sock.connect((up_info["host"], up_info["port"]))
                    # Inject Proxy-Authorization if not present
                    if up_info.get("auth_header"):
                        auth_line = f"Proxy-Authorization: {up_info['auth_header']}\r\n"
                        modified_req = req_data[:header_end] + b"\r\n" + auth_line.encode("latin1") + b"\r\n" + extra_body
                        remote_sock.sendall(modified_req)
                    else:
                        remote_sock.sendall(req_data)

                self._pipe_sockets(client_sock, remote_sock)

        except Exception:
            pass
        finally:
            try:
                client_sock.close()
            except Exception:
                pass
            if remote_sock:
                try:
                    remote_sock.close()
                except Exception:
                    pass

    def _parse_host_port(self, target: str, default_port: int) -> Tuple[str, int]:
        target = re.sub(r"^https?://", "", target, flags=re.IGNORECASE).split("/")[0]
        if ":" in target:
            h, p = target.split(":", 1)
            try:
                return h.strip(), int(p.strip())
            except ValueError:
                return h.strip(), default_port
        return target.strip(), default_port

    def _pipe_sockets(self, s1: socket.socket, s2: socket.socket) -> None:
        conn_pair = (s1, s2)
        with self._lock:
            self._active_connections.append(conn_pair)

        try:
            s1.setblocking(False)
            s2.setblocking(False)
            sockets = [s1, s2]
            while self.is_running:
                r, _, w = select.select(sockets, [], sockets, 40.0)
                if w:
                    break
                if not r:
                    break
                for s in r:
                    data = s.recv(16384)
                    if not data:
                        return
                    other = s2 if s is s1 else s1
                    other.sendall(data)
        except Exception:
            pass
        finally:
            with self._lock:
                if conn_pair in self._active_connections:
                    self._active_connections.remove(conn_pair)
