import os
import sys
from pathlib import Path

# Add project roots to path
current_dir = Path(__file__).resolve().parent
app_root = current_dir.parent.parent
core_dir = app_root / "01_Main_Software" / "core"
if str(core_dir) not in sys.path and core_dir.exists():
    sys.path.insert(0, str(core_dir))
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from fb_bulk_login_ui import MasterBotStudioDialog, FbBulkLoginBotDialog, launch_ui, main

__all__ = ["MasterBotStudioDialog", "FbBulkLoginBotDialog", "launch_ui", "main"]

if __name__ == "__main__":
    main()
