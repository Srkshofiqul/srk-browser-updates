"""
srkBrowser - Official Offline Full Setup & Standalone Installer
100% Offline Portable Edition (0 KB Download Required)
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
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

DEFAULT_INSTALL_DIR = r"C:\srkBrowser"

def get_bundle_zip_path() -> Path:
    # 1. PyInstaller MEIPASS bundled path
    if hasattr(sys, '_MEIPASS'):
        p = Path(sys._MEIPASS) / "srkBrowser_v2.1.0_Portable.zip"
        if p.exists():
            return p

    # 2. Local desktop or current dir fallback
    candidates = [
        Path(r"C:\Users\Muhammad_Shofiqul\Desktop\srkBrowser_v2.1.0_Portable.zip"),
        Path(__file__).parent / "srkBrowser_v2.1.0_Portable.zip",
        Path.cwd() / "srkBrowser_v2.1.0_Portable.zip"
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]

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

class ModernOfflineInstallerUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("srkBrowser — Offline Full Setup (Standalone Edition)")
        self.geometry("620x460")
        self.resizable(False, False)
        self.configure(bg="#0d1117")

        self.eval('tk::PlaceWindow . center')

        self.is_installing = False
        self.is_cancelled = False

        self.setup_styles()
        self.build_ui()

    def setup_styles(self):
        style = ttk.Style(self)
        style.theme_use('clam')

        style.configure(
            "Green.Horizontal.TProgressbar",
            troughcolor="#161b22",
            background="#2ea043",
            lightcolor="#3fb950",
            darkcolor="#238636",
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
            text="🚀 srkBrowser v2.1.0 — Offline Full Setup",
            font=("Segoe UI", 16, "bold"),
            bg="#161b22",
            fg="#3fb950"
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = tk.Label(
            header_frame,
            text="100% Standalone Offline Package • Complete Chromium & Runtime Bundled (No Internet Needed)",
            font=("Segoe UI", 9),
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
            text="📁 Destination Directory / ইনস্টলেশন ফোল্ডার:",
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
            highlightcolor="#3fb950"
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
            text="Ready to install offline. Click 'Install Now' to begin.",
            font=("Segoe UI", 10),
            bg="#0d1117",
            fg="#8b949e",
            anchor="w"
        )
        self.status_lbl.pack(fill="x", pady=(0, 4))

        self.progress_bar = ttk.Progressbar(
            content_frame,
            style="Green.Horizontal.TProgressbar",
            mode="determinate"
        )
        self.progress_bar.pack(fill="x", pady=(0, 4))

        self.info_lbl = tk.Label(
            content_frame,
            text="Package Status: Ready (Offline 301 MB Archive Embedded)",
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
            text="⚡ Install Now / অফলাইনে ইনস্টল করুন",
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

    def run_install_thread(self, target_dir: Path):
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            bundle_zip = get_bundle_zip_path()

            if not bundle_zip.exists():
                raise Exception(f"Embedded offline payload not found at: {bundle_zip}")

            self.after(0, self.update_progress, 0, "Extracting bundled offline package...", f"Source: {bundle_zip.name}")

            with zipfile.ZipFile(bundle_zip, 'r') as zf:
                members = [m for m in zf.infolist() if not m.is_dir()]
                total = len(members)

                for idx, m in enumerate(members):
                    if self.is_cancelled:
                        return

                    name = m.filename.replace('\\', '/')
                    # Strip 'srkBrowser_Portable/' prefix if present
                    if name.startswith("srkBrowser_Portable/"):
                        name = name[len("srkBrowser_Portable/"):].lstrip('/')
                    if not name:
                        continue

                    out_path = target_dir / name
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(m) as sf, open(out_path, 'wb') as df:
                        shutil.copyfileobj(sf, df)

                    if idx % 20 == 0 or idx == total - 1:
                        pct = int(((idx + 1) / total) * 100)
                        self.after(0, self.update_progress, pct, f"Installing offline files... ({pct}%)", f"Extracted {idx+1}/{total} files")

            # Create Shortcuts
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

            self.after(0, self.update_progress, 100, "🎉 Offline Installation Complete!", "Setup Succeeded 100% Offline.")
            time.sleep(1.2)

            if self.launch_var.get() and target_exe.exists():
                subprocess.Popen([str(target_exe)], cwd=str(target_dir))

            self.after(0, self.finish_success)

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Setup Error", f"Offline Installation Error:\n\n{str(e)}"))
            self.after(0, lambda: self.install_btn.config(state="normal", bg="#238636"))
            self.after(0, lambda: self.dir_entry.config(state="normal"))
            self.is_installing = False

    def finish_success(self):
        messagebox.showinfo("Success", "srkBrowser v2.1.0 has been successfully installed offline!")
        self.destroy()

if __name__ == "__main__":
    app = ModernOfflineInstallerUI()
    app.mainloop()
