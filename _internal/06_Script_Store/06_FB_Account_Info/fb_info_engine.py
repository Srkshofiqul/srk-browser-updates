# -*- coding: utf-8 -*-
"""
srkBrowser FB 1-Click Account Info & Credentials Engine
Provides modular launch for FBAccountInfoPopupDialog.
"""
from typing import Any, Dict, Optional
from PySide6.QtWidgets import QWidget


class FbAccountInfoEngine:
    """
    Engine that opens the sleek, modern FBAccountInfoPopupDialog for any profile.
    """

    @staticmethod
    def show_info_popup(profile_data: Dict[str, Any], parent: Optional[QWidget] = None):
        from core.ui.dialogs import FBAccountInfoPopupDialog
        dlg = FBAccountInfoPopupDialog(profile_data, parent=parent)
        return dlg.exec()


def launch_info_modal(profile_data: Dict[str, Any], parent: Optional[QWidget] = None):
    return FbAccountInfoEngine.show_info_popup(profile_data, parent)
