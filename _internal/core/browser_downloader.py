"""
srkBrowser - One-Time Cloud Portable Chromium Downloader & Setup Engine
Python 3.13 / PySide6 Desktop Application
Developer: Srk Shofiqul (srbrowser.com)
"""

import os
import sys
import time
import zipfile
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QPushButton, QMessageBox, QApplication, QFrame
)
from PySide6.QtGui import QFont, QIcon


CHROMIUM_DOWNLOAD_URL = "https://srbrowser.com/static/downloads/chromium.zip"


class ChromiumDownloadWorker(QThread):
    progress_changed = Signal(int, float, float, float)  # percent, downloaded_mb, total_mb, speed_mbps
    status_changed = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, target_dir: Path, download_url: str = CHROMIUM_DOWNLOAD_URL):
        super().__init__()
        self.target_dir = target_dir
        self.download_url = download_url
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        temp_zip = self.target_dir / "chromium_temp.zip"
        try:
            self.target_dir.mkdir(parents=True, exist_ok=True)
            self.status_changed.emit("Connecting to srkBrowser Cloud CDN...")

            # 1. Start HTTP Request
            req = urllib.request.Request(
                self.download_url,
                headers={"User-Agent": "srkBrowser-Client/2.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.info().get('Content-Length', 0))
                total_mb = total_size / (1024 * 1024) if total_size > 0 else 180.0

                downloaded = 0
                block_size = 1024 * 64  # 64 KB chunks
                start_time = time.time()
                last_update = 0

                with open(temp_zip, 'wb') as out_file:
                    while True:
                        if self.is_cancelled:
                            out_file.close()
                            if temp_zip.exists():
                                temp_zip.unlink()
                            self.finished_signal.emit(False, "Download cancelled by user.")
                            return

                        buffer = response.read(block_size)
                        if not buffer:
                            break

                        downloaded += len(buffer)
                        out_file.write(buffer)

                        now = time.time()
                        if now - last_update > 0.1:
                            last_update = now
                            downloaded_mb = downloaded / (1024 * 1024)
                            percent = int((downloaded / total_size) * 100) if total_size > 0 else 50
                            elapsed = max(0.1, now - start_time)
                            speed_mbps = (downloaded_mb * 8) / elapsed
                            self.progress_changed.emit(percent, downloaded_mb, total_mb, speed_mbps)

            if self.is_cancelled:
                return

            # 2. Extract Archive
            self.status_changed.emit("Extracting & Initializing Portable Chromium Engine...")
            self.progress_changed.emit(100, total_mb, total_mb, 0.0)

            with zipfile.ZipFile(temp_zip, 'r') as zf:
                zf.extractall(self.target_dir)

            # Cleanup temp zip
            try:
                temp_zip.unlink()
            except Exception:
                pass

            # Verify extraction
            extracted_chrome = self.target_dir / "chromium" / "chrome.exe"
            if not extracted_chrome.exists():
                extracted_chrome = self.target_dir / "chrome.exe"

            if extracted_chrome.exists():
                self.status_changed.emit("✅ Chromium Engine Ready!")
                self.finished_signal.emit(True, str(extracted_chrome.resolve()))
            else:
                self.finished_signal.emit(False, "Could not find chrome.exe in extracted archive.")

        except Exception as e:
            if temp_zip.exists():
                try:
                    temp_zip.unlink()
                except Exception:
                    pass
            self.finished_signal.emit(False, f"Download failed: {str(e)}")


class ChromiumDownloaderDialog(QDialog):
    """
    Ultra-Luxury Dark Obsidian 1-time setup dialog for downloading portable Chromium.
    """
    def __init__(self, target_dir: Optional[Path] = None, parent=None):
        super().__init__(parent)
        if target_dir is None:
            local_appdata = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
            self.target_dir = local_appdata / "BrowserProfileManager"
        else:
            self.target_dir = target_dir

        self.worker: Optional[ChromiumDownloadWorker] = None
        self.is_success = False
        self.chrome_exe_path: Optional[str] = None

        self.setWindowTitle("🌐 srkBrowser — Initializing Browser Engine")
        self.setFixedSize(560, 280)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f111a;
                color: #f1f5f9;
                border: 1px solid #202438;
                border-radius: 14px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel {
                color: #f1f5f9;
            }
            QProgressBar {
                background-color: #10121e;
                border: 1px solid #232742;
                border-radius: 6px;
                text-align: center;
                color: #f1f5f9;
                font-weight: bold;
                font-size: 11px;
                height: 22px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #06b6d4);
                border-radius: 5px;
            }
            QPushButton {
                background-color: #151829;
                color: #94a3b8;
                border: 1px solid #232742;
                padding: 8px 20px;
                border-radius: 8px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1c2035;
                color: #ffffff;
            }
        """)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        # Header Frame
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1c2d, stop:1 #121422);
                border: 1px solid #202438;
                border-radius: 10px;
                padding: 4px 8px;
            }
        """)
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(10, 8, 10, 8)
        hdr_layout.setSpacing(10)

        icon_lbl = QLabel("🌐")
        icon_lbl.setStyleSheet("font-size: 22px; background: transparent; border: none;")
        hdr_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        title_lbl = QLabel("Initializing Portable Chromium Core")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 800; color: #f1f5f9; background: transparent; border: none;")
        subtitle_lbl = QLabel("Cloud setup for isolated browser automation sessions")
        subtitle_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent; border: none;")
        title_vbox.addWidget(title_lbl)
        title_vbox.addWidget(subtitle_lbl)
        hdr_layout.addLayout(title_vbox, stretch=1)

        cdn_badge = QLabel("Cloud CDN")
        cdn_badge.setStyleSheet("background: rgba(129, 140, 248, 0.15); color: #818cf8; border: 1px solid rgba(129, 140, 248, 0.3); border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 800;")
        hdr_layout.addWidget(cdn_badge)


        layout.addWidget(hdr_frame)

        # Status Label
        self.status_lbl = QLabel("Preparing download...")
        self.status_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #818cf8;")
        layout.addWidget(self.status_lbl)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Metrics Label (MBs & Speed)
        self.metrics_lbl = QLabel("0.0 MB / ~180 MB (0.0 Mbps)")
        self.metrics_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; font-family: 'Consolas', monospace;")
        layout.addWidget(self.metrics_lbl)

        layout.addStretch()

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.on_cancel)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def start_download(self):
        self.worker = ChromiumDownloadWorker(self.target_dir)
        self.worker.progress_changed.connect(self.on_progress)
        self.worker.status_changed.connect(self.on_status)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, percent: int, downloaded_mb: float, total_mb: float, speed_mbps: float):
        self.progress_bar.setValue(percent)
        self.metrics_lbl.setText(f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB  •  {speed_mbps:.1f} Mbps")

    def on_status(self, msg: str):
        self.status_lbl.setText(msg)

    def on_finished(self, success: bool, result_msg: str):
        if success:
            self.is_success = True
            self.chrome_exe_path = result_msg
            self.status_lbl.setText("🎉 Chromium Engine Ready! Starting srkBrowser...")
            self.status_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #4ade80;")
            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Download Error",
                f"Could not download Portable Chromium Engine:\n{result_msg}\n\nPlease check your internet connection and try again."
            )
            self.reject()

    def on_cancel(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(2000)
        self.reject()


def ensure_portable_chromium_available(parent=None) -> Optional[str]:
    """
    Checks if Portable Chromium exists on disk.
    If missing, opens ChromiumDownloaderDialog to download it once from cloud server.
    Returns executable path if available, or None.
    """
    from utils import get_system_browsers
    browsers = get_system_browsers()
    if browsers:
        for label, exe_path in browsers.items():
            if os.path.exists(exe_path):
                return exe_path

    # Not found on disk -> Open One-Time Downloader Dialog
    dialog = ChromiumDownloaderDialog(parent=parent)
    dialog.start_download()
    res = dialog.exec()

    if res == QDialog.Accepted and dialog.is_success and dialog.chrome_exe_path:
        return dialog.chrome_exe_path

    return None
