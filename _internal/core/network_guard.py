"""
srkBrowser - High-Performance Zero-Lag Network Guard & Connectivity Monitor
Python 3.13 / PySide6 Desktop Application
Developer: Srk Shofiqul (srbrowser.com)
"""

import os
import time
import socket
import ctypes
from typing import Optional
from PySide6.QtCore import QThread, Signal, QObject


# In-memory cache to prevent redundant socket calls in rapid succession
_last_check_time: float = 0.0
_cached_online_status: bool = True
_CACHE_TTL_SEC: float = 1.8


def is_internet_available(timeout_sec: float = 1.2, force_refresh: bool = False) -> bool:
    """
    Checks if active internet connection is accessible.
    
    Step 1: Uses Windows native wininet.dll (InternetGetConnectedState) for 0ms link check.
            If the network interface is disconnected, returns False instantly with 0ms latency.
    Step 2: If link is up, tests socket connection to trusted DNS IPs (8.8.8.8:53 or 1.1.1.1:53)
            with a short timeout. Results are cached for 1.8s to eliminate redundant socket overhead.
    """
    global _last_check_time, _cached_online_status

    now = time.time()
    if not force_refresh and (now - _last_check_time) < _CACHE_TTL_SEC:
        return _cached_online_status

    # 1. Native Windows Link Status Check (Instant 0ms check)
    if os.name == "nt":
        try:
            flags = ctypes.c_ulong()
            connected = ctypes.windll.wininet.InternetGetConnectedState(ctypes.byref(flags), 0)
            if not connected:
                _cached_online_status = False
                _last_check_time = now
                return False
        except Exception:
            pass

    # 2. Socket Handshake Verification to reliable DNS servers
    test_hosts = [
        ("8.8.8.8", 53),   # Google Public DNS
        ("1.1.1.1", 53),   # Cloudflare Public DNS
    ]

    for host, port in test_hosts:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout_sec)
            sock.connect((host, port))
            sock.close()
            _cached_online_status = True
            _last_check_time = now
            return True
        except (socket.timeout, socket.error, OSError):
            continue

    _cached_online_status = False
    _last_check_time = now
    return False


class NetworkWatcherThread(QThread):
    """
    Continuous background QThread that periodically monitors network connectivity.
    Emits signals when connection state changes between Online and Offline.
    """
    connection_changed = Signal(bool)      # Emits True when online, False when offline
    connection_lost = Signal()             # Emits when transitioning from Online -> Offline
    connection_restored = Signal()         # Emits when transitioning from Offline -> Online

    def __init__(self, check_interval_sec: float = 2.5, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.check_interval_sec = max(1.5, check_interval_sec)
        self._running = True
        self._is_online: bool = is_internet_available(timeout_sec=1.0, force_refresh=True)

    @property
    def is_online(self) -> bool:
        return self._is_online

    def stop(self) -> None:
        """Signal the thread to cleanly exit its polling loop."""
        self._running = False

    def run(self) -> None:
        while self._running:
            # Sleep in small slices so stop() returns promptly
            steps = int(self.check_interval_sec * 10)
            for _ in range(steps):
                if not self._running:
                    return
                self.msleep(100)

            if not self._running:
                return

            current_status = is_internet_available(timeout_sec=1.2, force_refresh=True)

            if current_status != self._is_online:
                self._is_online = current_status
                self.connection_changed.emit(current_status)
                if not current_status:
                    self.connection_lost.emit()
                else:
                    self.connection_restored.emit()
