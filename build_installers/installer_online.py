"""
srkBrowser - Official Online Web Installer & Fast Cloud Setup
Python 3 Desktop Installer
Developer: Srk Shofiqul (srkbrowser.com)
"""

import os
import sys
import time
import shutil
import zipfile
import threading
import subprocess
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

CORE_DOWNLOAD_URL = "https://github.com/Srkshofiqul/srk-browser-updates/releases/download/v2.1.0/srkBrowser_Core.zip"
CORE_FALLBACK_URL = "https://srbrowser.com/static/downloads/srkBrowser_Core.zip"

CHROMIUM_DOWNLOAD_URL = "https://github.com/Srkshofiqul/srk-browser-updates/releases/download/v2.1.0/chromium.zip"
CHROMIUM_FALLBACK_URL = "https://srbrowser.com/static/downloads/chromium.zip"

DEFAULT_INSTALL_DIR = r"C:\srkBrowser"

def create_windows_shortcut(target_exe: Path, shortcut_path: Path, icon_path: Path = None, description: str = "srkBrowser"):
    try:
        ps_cmd = f"""
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{target_exe}"
$Shortcut.WorkingDirectory = "{target_exe.parent}"
if ("{icon_path}" -ne "" -and (Test-Path "{icon_path}")) {{
    $Shortcut.IconLocation = "{icon_path}"
}}
$Shortcut.Description = "{description}"
$Shortcut.Save()
"""
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            check=False
        )
    except Exception as e:
        print(f"Error creating shortcut: {e}")

class ModernWebInstallerUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("srkBrowser — Web Installer & Fast Setup")
        self.geometry("620x460")
        self.resizable(False, False)
        self.configure(bg="#0d1117")

        # Center on screen
        self.eval('tk::PlaceWindow . center')

        self.is_installing = False
        self.is_cancelled = False

        self.setup_styles()
        self.build_ui()

    def setup_styles(self):
        style = ttk.Style(self)
        style.theme_use('clam')

        # Progressbar styling
        style.configure(
            "Cyan.Horizontal.TProgressbar",
            troughcolor="#161b22",
            background="#00b4d8",
            lightcolor="#00b4d8",
            darkcolor="#0077b6",
            bordercolor="#30363d",
            thickness=14
        )

        style.configure(
            "TCheckbutton",
            background="#0d1117",
            foreground="#c9d1d9",
            font=("Segoe UI", 10)
        )
        style.map("TCheckbutton",
            background=[('active', '#0d1117')],
            foreground=[('active', '#58a6ff')]
        )

    def build_ui(self):
        # 1. Header Banner
        header_frame = tk.Frame(self, bg="#161b22", padx=24, pady=16)
        header_frame.pack(fill="x")

        title_lbl = tk.Label(
            header_frame,
            text="🚀 srkBrowser v2.1.0 — Online Setup",
            font=("Segoe UI", 16, "bold"),
            bg="#161b22",
            fg="#58a6ff"
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = tk.Label(
            header_frame,
            text="Official Cloud Web Installer • High-Speed Global CDN Integration",
            font=("Segoe UI", 10),
            bg="#161b22",
            fg="#8b949e"
        )
        subtitle_lbl.pack(anchor="w", pady=(4, 0))

        # 2. Main Content Card
        content_frame = tk.Frame(self, bg="#0d1117", padx=24, pady=18)
        content_frame.pack(fill="both", expand=True)

        # Installation Directory Selector
        dir_lbl = tk.Label(
            content_frame,
            text="📁 Installation Directory / ইনস্টলেশন ফোল্ডার:",
            font=("Segoe UI", 10, "bold"),
            bg="#0d1117",
            fg="#c9d1d9"
        )
        dir_lbl.pack(anchor="w")

        dir_box = tk.Frame(content_frame, bg="#0d1117")
        dir_box.pack(fill="x", pady=(6, 14))

        self.dir_var = tk.StringVar(value=DEFAULT_INSTALL_DIR)
        self.dir_entry = tk.Entry(
            dir_box,
            textvariable=self.dir_var,
            font=("Consolas", 10),
            bg="#161b22",
            fg="#f0f6fc",
            insertbackground="#58a6ff",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#30363d",
            highlightcolor="#58a6ff"
        )
        self.dir_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))

        browse_btn = tk.Button(
            dir_box,
            text="Browse...",
            font=("Segoe UI", 9, "bold"),
            bg="#21262d",
            fg="#c9d1d9",
            activebackground="#30363d",
            activeforeground="#f0f6fc",
            relief="flat",
            padx=12,
            pady=3,
            cursor="hand2",
            command=self.browse_directory
        )
        browse_btn.pack(side="right")

        # Options Checkboxes
        self.shortcut_var = tk.BooleanVar(value=True)
        chk_shortcut = ttk.Checkbutton(
            content_frame,
            text="Create Desktop Shortcut (ডেস্কটপে শর্টকাট তৈরি করুন)",
            variable=self.shortcut_var,
            style="TCheckbutton"
        )
        chk_shortcut.pack(anchor="w", pady=(0, 4))

        self.launch_var = tk.BooleanVar(value=True)
        chk_launch = ttk.Checkbutton(
            content_frame,
            text="Launch srkBrowser upon completion (ইনস্টল শেষে চালু করুন)",
            variable=self.launch_var,
            style="TCheckbutton"
        )
        chk_launch.pack(anchor="w", pady=(0, 16))

        # Progress Section
        self.status_lbl = tk.Label(
            content_frame,
            text="Ready to install. Click 'Install Now' to begin cloud setup.",
            font=("Segoe UI", 10),
            bg="#0d1117",
            fg="#8b949e",
            anchor="w"
        )
        self.status_lbl.pack(fill="x", pady=(0, 4))

        self.progress_bar = ttk.Progressbar(
            content_frame,
            style="Cyan.Horizontal.TProgressbar",
            mode="determinate"
        )
        self.progress_bar.pack(fill="x", pady=(0, 4))

        self.info_lbl = tk.Label(
            content_frame,
            text="Status: Idle",
            font=("Consolas", 9),
            bg="#0d1117",
            fg="#6e7681",
            anchor="w"
        )
        self.info_lbl.pack(fill="x")

        # 3. Bottom Action Buttons
        btn_frame = tk.Frame(self, bg="#161b22", padx=24, pady=14)
        btn_frame.pack(fill="x", side="bottom")

        self.cancel_btn = tk.Button(
            btn_frame,
            text="Exit / বাতিল",
            font=("Segoe UI", 10),
            bg="#21262d",
            fg="#8b949e",
            activebackground="#30363d",
            activeforeground="#c9d1d9",
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
            command=self.on_cancel
        )
        self.cancel_btn.pack(side="left")

        self.install_btn = tk.Button(
            btn_frame,
            text="⚡ Install Now / ইনস্টল শুরু করুন",
            font=("Segoe UI", 10, "bold"),
            bg="#238636",
            fg="#ffffff",
            activebackground="#2ea043",
            activeforeground="#ffffff",
            relief="flat",
            padx=22,
            pady=6,
            cursor="hand2",
            command=self.start_installation
        )
        self.install_btn.pack(side="right")

    def browse_directory(self):
        chosen = filedialog.askdirectory(initialdir=self.dir_var.get())
        if chosen:
            self.dir_var.set(chosen)

    def on_cancel(self):
        if self.is_installing:
            if messagebox.askyesno("Confirm Exit", "Installation is in progress. Are you sure you want to cancel?"):
                self.is_cancelled = True
                self.destroy()
        else:
            self.destroy()

    def update_progress(self, percent: int, status_text: str, info_text: str):
        self.progress_bar['value'] = percent
        self.status_lbl.config(text=status_text)
        self.info_lbl.config(text=info_text)

    def start_installation(self):
        if self.is_installing:
            return
        target_path = Path(self.dir_var.get().strip())
        if not target_path:
            messagebox.showerror("Error", "Please specify a valid installation directory.")
            return

        self.is_installing = True
        self.install_btn.config(state="disabled", bg="#30363d")
        self.dir_entry.config(state="disabled")

        t = threading.Thread(target=self.run_install_thread, args=(target_path,), daemon=True)
        t.start()

    def download_file(self, urls: list, dest_file: Path, label: str):
        temp_file = dest_file.with_suffix('.part')
        for url in urls:
            if self.is_cancelled:
                return False
            try:
                self.update_progress(0, f"Connecting: {label}...", f"URL: {url}")
                req = urllib.request.Request(url, headers={"User-Agent": "srkBrowser-WebSetup/2.1"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    total_size = int(resp.info().get('Content-Length', 0))
                    total_mb = total_size / (1024 * 1024) if total_size > 0 else 0

                    downloaded = 0
                    block_size = 1024 * 64
                    start_time = time.time()
                    last_ui_update = 0

                    with open(temp_file, 'wb') as f:
                        while True:
                            if self.is_cancelled:
                                return False
                            chunk = resp.read(block_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)

                            now = time.time()
                            if now - last_ui_update > 0.08:
                                last_ui_update = now
                                dl_mb = downloaded / (1024 * 1024)
                                pct = int((downloaded / total_size) * 100) if total_size > 0 else 50
                                speed = (dl_mb * 8) / max(0.1, now - start_time)
                                self.after(0, self.update_progress, pct, f"Downloading: {label} ({pct}%)", f"{dl_mb:.1f} MB / {total_mb:.1f} MB ({speed:.1f} Mbps)")

                if temp_file.exists():
                    if dest_file.exists():
                        dest_file.unlink()
                    temp_file.rename(dest_file)
                return True
            except Exception as e:
                print(f"Download attempt failed for {url}: {e}")
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass
                continue
        return False

    def extract_zip(self, zip_path: Path, target_dir: Path, strip_prefix: str, label: str):
        with zipfile.ZipFile(zip_path, 'r') as z:
            members = [m for m in z.infolist() if not m.is_dir()]
            total = len(members)
            for idx, m in enumerate(members):
                if self.is_cancelled:
                    return False
                name = m.filename.replace('\\', '/')
                if strip_prefix and name.startswith(strip_prefix):
                    name = name[len(strip_prefix):].lstrip('/')
                if not name:
                    continue
                out_path = target_dir / name
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with z.open(m) as sf, open(out_path, 'wb') as df:
                    shutil.copyfileobj(sf, df)

                if idx % 15 == 0:
                    pct = int((idx / total) * 100)
                    self.after(0, self.update_progress, pct, f"Extracting {label}... ({pct}%)", f"Extracted {idx}/{total} files")
        return True

    def run_install_thread(self, target_dir: Path):
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            temp_cache = target_dir / "_setup_cache"
            temp_cache.mkdir(parents=True, exist_ok=True)

            core_zip = temp_cache / "srkBrowser_Core.zip"
            chromium_zip = temp_cache / "chromium.zip"

            # 1. Download Core
            self.after(0, self.update_progress, 5, "Connecting to Cloud CDN for Core Package...", "")
            success = self.download_file([CORE_DOWNLOAD_URL, CORE_FALLBACK_URL], core_zip, "Core Application (114 MB)")
            if not success:
                raise Exception("Failed to download Core Application package. Please check internet connection.")

            # 2. Extract Core
            self.after(0, self.update_progress, 0, "Extracting Core Files...", "")
            self.extract_zip(core_zip, target_dir, strip_prefix="srkBrowser_Portable/", label="Core Files")

            # 3. Download Chromium Engine
            self.after(0, self.update_progress, 0, "Connecting for Chromium Engine...", "")
            success_chrome = self.download_file([CHROMIUM_DOWNLOAD_URL, CHROMIUM_FALLBACK_URL], chromium_zip, "Chromium Browser Engine (182 MB)")
            if not success_chrome:
                raise Exception("Failed to download Chromium Engine package.")

            # 4. Extract Chromium Engine
            self.after(0, self.update_progress, 0, "Extracting Chromium Browser Engine...", "")
            self.extract_zip(chromium_zip, target_dir, strip_prefix="", label="Chromium Engine")

            # 5. Cleanup Cache
            try:
                shutil.rmtree(temp_cache, ignore_errors=True)
            except Exception:
                pass

            # 6. Create Shortcuts
            target_exe = target_dir / "Start_srBrowser.exe"
            if not target_exe.exists():
                target_exe = target_dir / "srBrowser.exe"

            icon_path = target_dir / "data" / "assets" / "app_icon.ico"
            if not icon_path.exists():
                icon_path = target_dir / "_internal" / "assets" / "app_icon.ico"

            if self.shortcut_var.get() and target_exe.exists():
                self.after(0, self.update_progress, 95, "Creating Desktop Shortcut...", "")
                desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
                shortcut_file = desktop / "srkBrowser.lnk"
                create_windows_shortcut(target_exe, shortcut_file, icon_path)

            self.after(0, self.update_progress, 100, "🎉 Installation Complete! Launching...", "Setup Succeeded.")
            time.sleep(1.2)

            if self.launch_var.get() and target_exe.exists():
                subprocess.Popen([str(target_exe)], cwd=str(target_dir))

            self.after(0, self.finish_success)

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Setup Error", f"Installation could not be completed:\n\n{str(e)}"))
            self.after(0, lambda: self.install_btn.config(state="normal", bg="#238636"))
            self.after(0, lambda: self.dir_entry.config(state="normal"))
            self.is_installing = False

    def finish_success(self):
        messagebox.showinfo("Success", "srkBrowser v2.1.0 has been installed successfully!")
        self.destroy()

if __name__ == "__main__":
    app = ModernWebInstallerUI()
    app.mainloop()
