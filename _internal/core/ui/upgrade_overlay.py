"""
Browser Profile Manager - In-Page Upgrade Slide-Over Overlay
Python 3.13 / PySide6 Desktop Application
"""

import json
from typing import Dict, Any, List, Optional
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QRect, QPoint, QSize, QThread
from PySide6.QtGui import QColor, QFont, QCursor, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QGraphicsOpacityEffect, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy, QApplication
)


class PlansSyncWorker(QThread):
    """Background thread worker to sync live pricing and plans from server API."""
    plans_synced = Signal(list)

    def run(self) -> None:
        try:
            import requests
            from pathlib import Path
            import json
            r = requests.get("https://srbrowser.com/api/v1/plans", headers={"User-Agent": "srkBrowser/2.0"}, timeout=6)
            if r.status_code == 200:
                data = r.json()
                plans_list = data.get("plans", [])
                if plans_list and isinstance(plans_list, list):
                    cache_p = Path(__file__).parent.parent.parent / "data" / "plans_cache.json"
                    try:
                        cache_p.parent.mkdir(parents=True, exist_ok=True)
                        with open(cache_p, "w", encoding="utf-8") as f:
                            json.dump(plans_list, f, indent=2)
                    except Exception:
                        pass
                    self.plans_synced.emit(plans_list)
        except Exception as e:
            print(f"[LIVE PLANS SYNC ERROR]: {e}")


class DrawerCloseButton(QPushButton):
    """Crystal-sharp custom close cross button with anti-aliased vector rendering."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Close (Esc)")
        self._hovered = False

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background and border
        if self._hovered:
            bg_color = QColor("#ef4444")
            border_color = QColor("#dc2626")
            cross_color = QColor("#ffffff")
        else:
            bg_color = QColor("#1e2438")
            border_color = QColor("#334155")
            cross_color = QColor("#f1f5f9")

        # Rounded rectangle
        painter.setBrush(bg_color)
        painter.setPen(border_color)
        painter.drawRoundedRect(1, 1, self.width() - 2, self.height() - 2, 8, 8)

        # Sharp Cross lines
        pen = QPen(cross_color, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)

        pad = 11
        w = self.width()
        h = self.height()
        painter.drawLine(pad, pad, w - pad, h - pad)
        painter.drawLine(w - pad, pad, pad, h - pad)


class UpgradeSlideOverlay(QWidget):
    """In-page Slide-Over Upgrade Drawer that animates over the current view."""

    closed = Signal()

    def __init__(self, parent: Optional[QWidget] = None, cloud_token: str = "") -> None:
        super().__init__(parent)
        self.cloud_token = cloud_token
        self.selected_plan_id = "pro"
        self.selected_duration_key = "1m"
        self.plans_data = self._fetch_live_plans()

        # Set overlay background
        self.setAttribute(Qt.WA_NoSystemBackground, False)
        self.setStyleSheet("background-color: transparent;")

        # Main Layout: Centered or Slide from right
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Left dim backdrop area (clicking dismisses)
        self.backdrop_left = QWidget()
        self.backdrop_left.setStyleSheet("background-color: rgba(5, 8, 12, 0.65);")
        self.backdrop_left.setCursor(Qt.PointingHandCursor)
        self.backdrop_left.mousePressEvent = lambda e: self.hide_drawer()

        # Right Drawer Frame
        self.drawer_frame = QFrame()
        self.drawer_frame.setObjectName("UpgradeDrawerFrame")
        self.drawer_frame.setStyleSheet("""
            QFrame#UpgradeDrawerFrame {
                background-color: #0d111a;
                border-left: 1.5px solid rgba(137, 180, 250, 0.3);
                border-top: 1.5px solid rgba(137, 180, 250, 0.3);
                border-bottom: 1.5px solid rgba(137, 180, 250, 0.3);
                border-top-left-radius: 20px;
                border-bottom-left-radius: 20px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)
        self.drawer_frame.setFixedWidth(870)

        d_layout = QVBoxLayout(self.drawer_frame)
        d_layout.setContentsMargins(24, 20, 24, 20)
        d_layout.setSpacing(14)

        # ----------------------------------------------------
        # 1. TOP HEADER: Title + Current Plan + Close Button
        # ----------------------------------------------------
        hdr_hbox = QHBoxLayout()
        
        hdr_left = QHBoxLayout()
        hdr_left.setSpacing(10)
        
        lbl_title = QLabel("💎 Upgrade Plan")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: 900; color: #ffffff; letter-spacing: 0.3px;")
        
        lbl_divider = QLabel("|")
        lbl_divider.setStyleSheet("color: #45475a; font-size: 16px; font-weight: bold;")
        
        self.lbl_curr_plan = QLabel("Current plan : <span style='color:#a6e3a1; font-weight:800;'>Free Account (100 Profiles)</span>")
        self.lbl_curr_plan.setStyleSheet("font-size: 13px; color: #a6adc8;")
        
        hdr_left.addWidget(lbl_title)
        hdr_left.addWidget(lbl_divider)
        hdr_left.addWidget(self.lbl_curr_plan)
        hdr_left.addStretch()
        
        btn_close = DrawerCloseButton()
        btn_close.clicked.connect(self.hide_drawer)
        
        hdr_hbox.addLayout(hdr_left)
        hdr_hbox.addWidget(btn_close)
        d_layout.addLayout(hdr_hbox)

        # Divider line
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color: #26283b; background-color: #26283b; max-height: 1px;")
        d_layout.addWidget(div)

        # ----------------------------------------------------
        # 2. MAIN 2-COLUMN CONTENT: (Left: Steps 1-3 | Right: Order Summary)
        # ----------------------------------------------------
        body_hbox = QHBoxLayout()
        body_hbox.setSpacing(22)

        # Scroll Area for Left Content
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        left_scroll.setStyleSheet("background: transparent; border: none;")

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(16)

        # --- STEP 1: Choose a plan ---
        step1_box = QVBoxLayout()
        step1_box.setSpacing(8)

        lbl_step1 = QLabel("● Choose a plan <span style='color:#ef4444; font-size:11px; font-weight:600;'>(Proxy & Captcha not included)</span>")
        lbl_step1.setStyleSheet("color: #ffffff; font-weight: 800; font-size: 13.5px;")
        step1_box.addWidget(lbl_step1)

        self.plan_buttons_hbox = QHBoxLayout()
        self.plan_buttons_hbox.setSpacing(12)
        self.plan_btn_group = {}

        # 3 Plan Definitions
        self.plan_configs = {
            "pro": {
                "title": "⭐  Professional",
                "name": "Professional",
                "quota": 500,
                "badge": "⭐ 500 Profiles",
                "durations": {
                    "1m": {"label": "1 Month", "price": "$3", "price_val": 3.0, "period": "/ Month", "rate": "About $0.33/Day", "discount": "", "url_plan": "pro_1m", "days": "30 Days"},
                    "3m": {"label": "3 Month", "price": "$8.10", "price_val": 8.1, "period": "/ 3 Months", "rate": "About $0.30/Day", "discount": "10% off", "url_plan": "pro_3m", "days": "90 Days"},
                    "6m": {"label": "6 Month", "price": "$14.40", "price_val": 14.4, "period": "/ 6 Months", "rate": "About $0.26/Day", "discount": "20% off", "url_plan": "pro_6m", "days": "180 Days"}
                }
            },
            "business": {
                "title": "🚀  Business",
                "name": "Business",
                "quota": 1000,
                "badge": "🚀 1,000 Profiles",
                "durations": {
                    "1m": {"label": "1 Month", "price": "$5", "price_val": 5.0, "period": "/ Month", "rate": "About $0.66/Day", "discount": "", "url_plan": "business_1m", "days": "30 Days"},
                    "3m": {"label": "3 Month", "price": "$13.50", "price_val": 13.5, "period": "/ 3 Months", "rate": "About $0.60/Day", "discount": "10% off", "url_plan": "business_3m", "days": "90 Days"},
                    "6m": {"label": "6 Month", "price": "$24", "price_val": 24.0, "period": "/ 6 Months", "rate": "About $0.53/Day", "discount": "20% off", "url_plan": "business_6m", "days": "180 Days"}
                }
            },
            "enterprise": {
                "title": "👑  Enterprise",
                "name": "Enterprise",
                "quota": 5000,
                "badge": "👑 5,000 Profiles + All Bots",
                "durations": {
                    "1m": {"label": "1 Month", "price": "$25", "price_val": 25.0, "period": "/ Month", "rate": "About $1.63/Day", "discount": "", "url_plan": "enterprise_1m", "days": "30 Days"},
                    "2m": {"label": "2 Month", "price": "$46", "price_val": 46.0, "period": "/ 2 Months", "rate": "About $1.50/Day", "discount": "8% off", "url_plan": "enterprise_2m", "days": "60 Days"},
                    "3m": {"label": "3 Month", "price": "$66", "price_val": 66.0, "period": "/ 3 Months", "rate": "About $1.44/Day", "discount": "12% off", "url_plan": "enterprise_3m", "days": "90 Days"}
                }
            }
        }

        # Load any existing cached server plans into plan_configs
        try:
            from pathlib import Path
            cache_p = Path(__file__).parent.parent.parent / "data" / "plans_cache.json"
            if cache_p.exists():
                import json
                with open(cache_p, "r", encoding="utf-8") as f:
                    cached_list = json.load(f)
                if isinstance(cached_list, list):
                    for p in cached_list:
                        pid = p.get("id")
                        if pid in self.plan_configs and p.get("durations"):
                            for dkey, dval in p["durations"].items():
                                pval = float(dval.get("price_usd", 0.0))
                                pstr = dval.get("price", f"${pval:.2f}")
                                if dkey in self.plan_configs[pid]["durations"]:
                                    self.plan_configs[pid]["durations"][dkey]["price"] = pstr
                                    self.plan_configs[pid]["durations"][dkey]["price_val"] = pval
                                    if "badge" in dval:
                                        self.plan_configs[pid]["durations"][dkey]["discount"] = dval["badge"]
        except Exception:
            pass

        for pid, pcfg in self.plan_configs.items():
            btn_p = QPushButton(pcfg["title"])
            btn_p.setCursor(Qt.PointingHandCursor)
            btn_p.setFixedHeight(42)
            btn_p.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.plan_btn_group[pid] = btn_p

            def make_plan_click(target_id=pid):
                return lambda: self._on_plan_selected(target_id)

            btn_p.clicked.connect(make_plan_click(pid))
            self.plan_buttons_hbox.addWidget(btn_p)

        step1_box.addLayout(self.plan_buttons_hbox)
        left_layout.addLayout(step1_box)

        # --- STEP 2: Select plan duration ---
        self.step2_widget = QWidget()
        self.step2_layout = QVBoxLayout(self.step2_widget)
        self.step2_layout.setContentsMargins(0, 0, 0, 0)
        self.step2_layout.setSpacing(8)

        self.lbl_step2 = QLabel("● Select plan duration")
        self.lbl_step2.setStyleSheet("color: #ffffff; font-weight: 800; font-size: 13.5px;")
        self.step2_layout.addWidget(self.lbl_step2)

        self.duration_cards_hbox = QHBoxLayout()
        self.duration_cards_hbox.setSpacing(10)
        self.step2_layout.addLayout(self.duration_cards_hbox)
        self.dur_card_widgets = {}

        left_layout.addWidget(self.step2_widget)

        # --- STEP 3: Plan content / Comparison table ---
        step3_box = QVBoxLayout()
        step3_box.setSpacing(8)

        lbl_step3 = QLabel("● Plan content & feature comparison")
        lbl_step3.setStyleSheet("color: #ffffff; font-weight: 800; font-size: 13.5px;")
        step3_box.addWidget(lbl_step3)

        self.comp_table = QTableWidget()
        self.comp_table.setColumnCount(3)
        self.comp_table.setHorizontalHeaderLabels(["Plan Feature", "Free Account", "Selected Plan"])
        self.comp_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.comp_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.comp_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.comp_table.verticalHeader().setVisible(False)
        self.comp_table.verticalHeader().setDefaultSectionSize(36)
        self.comp_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.comp_table.setSelectionMode(QTableWidget.NoSelection)
        self.comp_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.comp_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.comp_table.setFixedHeight(265)
        self.comp_table.setStyleSheet("""
            QTableWidget {
                background-color: #101424;
                border: 1.5px solid #23283e;
                border-radius: 12px;
                gridline-color: #1b2034;
                font-size: 12px;
                color: #cdd6f4;
            }
            QHeaderView::section {
                background-color: #171c32;
                color: #89b4fa;
                font-weight: 800;
                border: none;
                border-bottom: 1.5px solid #262c46;
                padding: 8px 10px;
                font-size: 11.5px;
            }
        """)

        self._populate_comparison_table()
        step3_box.addWidget(self.comp_table)
        left_layout.addLayout(step3_box)
        left_layout.addStretch(1)

        left_scroll.setWidget(left_widget)
        body_hbox.addWidget(left_scroll, stretch=64)

        # ----------------------------------------------------
        # RIGHT SIDEBAR: Order Details & Checkout Summary
        # ----------------------------------------------------
        self.order_card = QFrame()
        self.order_card.setObjectName("OrderCard")
        self.order_card.setStyleSheet("""
            QFrame#OrderCard {
                background-color: #101424;
                border: 1.5px solid rgba(137, 180, 250, 0.25);
                border-radius: 14px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        self.order_card.setFixedWidth(275)

        ord_vbox = QVBoxLayout(self.order_card)
        ord_vbox.setContentsMargins(16, 16, 16, 16)
        ord_vbox.setSpacing(10)

        lbl_ord_title = QLabel("📦 Order Details")
        lbl_ord_title.setStyleSheet("font-size: 16px; font-weight: 900; color: #ffffff;")
        ord_vbox.addWidget(lbl_ord_title)

        ord_div = QFrame()
        ord_div.setFrameShape(QFrame.HLine)
        ord_div.setStyleSheet("color: #23283e; background-color: #23283e; max-height: 1px;")
        ord_vbox.addWidget(ord_div)

        # Details list
        self.lbl_ord_ver = QLabel("Plan version : <b style='color:#ffffff;'>Professional</b>")
        self.lbl_ord_ver.setStyleSheet("font-size: 12px; color: #a6adc8;")
        ord_vbox.addWidget(self.lbl_ord_ver)

        self.lbl_ord_dur = QLabel("Plan duration : <b style='color:#ffffff;'>1 Month</b>")
        self.lbl_ord_dur.setStyleSheet("font-size: 12px; color: #a6adc8;")
        ord_vbox.addWidget(self.lbl_ord_dur)

        self.lbl_ord_amount = QLabel("Amount : <span style='font-size:22px; font-weight:900; color:#a6e3a1;'>$3</span>")
        self.lbl_ord_amount.setStyleSheet("font-size: 13px; color: #a6adc8; margin-top: 2px;")
        ord_vbox.addWidget(self.lbl_ord_amount)

        self.lbl_ord_expiry = QLabel("Estimated duration : <b style='color:#f9e2af;'>30 Days</b>")
        self.lbl_ord_expiry.setStyleSheet("font-size: 11.5px; color: #a6adc8;")
        ord_vbox.addWidget(self.lbl_ord_expiry)

        self.lbl_ord_active_validity = QLabel("Active plan validity : <b style='color:#38bdf8;'>30 Days Remaining</b>")
        self.lbl_ord_active_validity.setStyleSheet("font-size: 11.5px; color: #a6adc8;")
        ord_vbox.addWidget(self.lbl_ord_active_validity)

        # Benefits Breakdown Card
        benefits_card = QFrame()
        benefits_card.setStyleSheet("""
            QFrame {
                background-color: #151a2e;
                border: 1px solid #282f48;
                border-radius: 10px;
                padding: 4px;
            }
        """)
        ben_vbox = QVBoxLayout(benefits_card)
        ben_vbox.setContentsMargins(8, 8, 8, 8)
        ben_vbox.setSpacing(6)

        lbl_ben_hdr = QLabel("🛡️ Plan Inclusions:")
        lbl_ben_hdr.setStyleSheet("font-size: 11px; font-weight: 800; color: #89b4fa;")
        ben_vbox.addWidget(lbl_ben_hdr)

        for icon, btext in [
            ("⚡", "Instant Cloud License Activation"),
            ("🔒", "256-Bit SSL Encrypted Checkout"),
            ("🔄", "Multi-Device Real-Time Sync"),
            ("👑", "Priority Storage & Dedicated Support")
        ]:
            b_lbl = QLabel(f"{icon} {btext}")
            b_lbl.setStyleSheet("font-size: 10.5px; color: #cdd6f4;")
            ben_vbox.addWidget(b_lbl)

        ord_vbox.addWidget(benefits_card)

        # Payment Notice
        lbl_notice = QLabel("Notice: After successful payment, your cloud quota activates automatically.")
        lbl_notice.setWordWrap(True)
        lbl_notice.setStyleSheet("font-size: 10px; color: #f38ba8; line-height: 1.3; padding: 6px; background: rgba(243,139,168,0.08); border-radius: 6px; border: 1px solid rgba(243,139,168,0.2);")
        ord_vbox.addWidget(lbl_notice)

        ord_vbox.addStretch(1)

        # Submit Upgrade Button
        self.btn_submit_upgrade = QPushButton("🚀 Submit Upgrade")
        self.btn_submit_upgrade.setCursor(Qt.PointingHandCursor)
        self.btn_submit_upgrade.setMinimumHeight(44)
        self.btn_submit_upgrade.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #89b4fa, stop:1 #b4befe);
                color: #11111b;
                border: none;
                border-radius: 10px;
                padding: 10px 6px;
                font-weight: 900;
                font-size: 12.5px;
            }
            QPushButton:hover {
                background: #cdd6f4;
            }
        """)
        self.btn_submit_upgrade.clicked.connect(self._on_submit_checkout)
        ord_vbox.addWidget(self.btn_submit_upgrade)

        # Redeem key link
        btn_redeem_link = QPushButton("🔑 Have a key? Redeem Here")
        btn_redeem_link.setCursor(Qt.PointingHandCursor)
        btn_redeem_link.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #f9e2af;
                font-size: 11.5px;
                font-weight: 700;
                border: none;
                text-decoration: underline;
                padding: 2px;
            }
            QPushButton:hover { color: #ffffff; }
        """)
        btn_redeem_link.clicked.connect(self._on_redeem_clicked)
        ord_vbox.addWidget(btn_redeem_link)

        body_hbox.addWidget(self.order_card, stretch=38)
        d_layout.addLayout(body_hbox)

        self.main_layout.addWidget(self.backdrop_left, stretch=1)
        self.main_layout.addWidget(self.drawer_frame)

        # Initial UI State
        self._on_plan_selected("pro")
        self._sync_live_plans()

    def _fetch_live_plans(self) -> List[Dict[str, Any]]:
        """Fetch dynamic membership plans with disk cache and default fallback."""
        from pathlib import Path
        cache_p = Path(__file__).parent.parent.parent / "data" / "plans_cache.json"
        if cache_p.exists():
            try:
                import json
                with open(cache_p, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if isinstance(cached, list) and len(cached) > 0:
                    return cached
            except Exception:
                pass

        default_plans = [
            {
                "id": "pro", "title": "Professional", "badge": "⭐", "price_label": "$3", "period_label": "/ Monthly",
                "durations": {
                    "1m": {"label": "1 Month", "price": "$3", "price_val": 3.0, "rate": "About $0.33/Day", "discount": "", "url_plan": "pro_1m", "days": "30 Days"},
                    "3m": {"label": "3 Month", "price": "$8.10", "price_val": 8.1, "rate": "About $0.30/Day", "discount": "10% off", "url_plan": "pro_3m", "days": "90 Days"},
                    "6m": {"label": "6 Month", "price": "$14.40", "price_val": 14.4, "rate": "About $0.26/Day", "discount": "20% off", "url_plan": "pro_6m", "days": "180 Days"}
                }
            },
            {
                "id": "business", "title": "Business", "badge": "🏢", "price_label": "$5", "period_label": "/ Monthly",
                "durations": {
                    "1m": {"label": "1 Month", "price": "$5", "price_val": 5.0, "rate": "About $0.66/Day", "discount": "", "url_plan": "business_1m", "days": "30 Days"},
                    "3m": {"label": "3 Month", "price": "$13.50", "price_val": 13.5, "rate": "About $0.60/Day", "discount": "10% off", "url_plan": "business_3m", "days": "90 Days"},
                    "6m": {"label": "6 Month", "price": "$24", "price_val": 24.0, "rate": "About $0.53/Day", "discount": "20% off", "url_plan": "business_6m", "days": "180 Days"}
                }
            },
            {
                "id": "enterprise", "title": "Enterprise", "badge": "👑", "price_label": "$25", "period_label": "/ Monthly",
                "durations": {
                    "1m": {"label": "1 Month", "price": "$25", "price_val": 25.0, "rate": "About $1.63/Day", "discount": "", "url_plan": "enterprise_1m", "days": "30 Days"},
                    "2m": {"label": "2 Month", "price": "$46", "price_val": 46.0, "rate": "About $1.50/Day", "discount": "8% off", "url_plan": "enterprise_2m", "days": "60 Days"},
                    "3m": {"label": "3 Month", "price": "$66", "price_val": 66.0, "rate": "About $1.44/Day", "discount": "12% off", "url_plan": "enterprise_3m", "days": "90 Days"}
                }
            }
        ]
        return default_plans

    def _render_duration_cards(self, plan_id: str) -> None:
        """Dynamically render duration cards based on selected plan."""
        # Clear existing cards
        while self.duration_cards_hbox.count() > 0:
            item = self.duration_cards_hbox.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.dur_card_widgets.clear()
        durations = self.plan_configs.get(plan_id, {}).get("durations", {})

        # If previous duration key doesn't exist for new plan, reset to 1m
        if self.selected_duration_key not in durations:
            self.selected_duration_key = "1m"

        for dkey, dinfo in durations.items():
            card = QFrame()
            card.setObjectName(f"DurCard_{dkey}")
            card.setCursor(Qt.PointingHandCursor)
            card.setFixedHeight(94)
            c_vbox = QVBoxLayout(card)
            c_vbox.setContentsMargins(12, 10, 12, 10)
            c_vbox.setSpacing(3)

            # Top label row (Label + Discount Tag)
            top_h = QHBoxLayout()
            top_h.setSpacing(6)
            top_h.setContentsMargins(0, 0, 0, 0)

            lbl_dl = QLabel(dinfo["label"])
            lbl_dl.setStyleSheet("font-size: 13px; font-weight: 800; color: #ffffff; border: none; background: transparent;")
            top_h.addWidget(lbl_dl)

            if dinfo.get("discount"):
                raw_disc = str(dinfo['discount']).strip().upper()
                clean_disc = raw_disc.replace("SAVE", "").replace("🔥", "").replace("-", "").strip()
                if not clean_disc.endswith("OFF"):
                    clean_disc = f"{clean_disc} OFF"
                lbl_tag = QLabel(clean_disc)
                lbl_tag.setStyleSheet("""
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ef4444, stop:1 #ea580c);
                    color: #ffffff;
                    font-size: 9px;
                    font-weight: 900;
                    border-radius: 4px;
                    padding: 1.5px 5px;
                    border: none;
                """)
                top_h.addWidget(lbl_tag)
            top_h.addStretch()
            c_vbox.addLayout(top_h)

            lbl_dp = QLabel(dinfo["price"])
            lbl_dp.setStyleSheet("font-size: 17px; font-weight: 900; color: #a6e3a1; border: none; background: transparent;")
            c_vbox.addWidget(lbl_dp)

            lbl_dr = QLabel(dinfo.get("rate", ""))
            lbl_dr.setStyleSheet("font-size: 11px; color: #94a3b8; border: none; background: transparent;")
            c_vbox.addWidget(lbl_dr)

            def make_dur_click(k=dkey):
                return lambda e: self._on_duration_selected(k)

            card.mousePressEvent = make_dur_click(dkey)
            self.dur_card_widgets[dkey] = card
            self.duration_cards_hbox.addWidget(card)

        self._on_duration_selected(self.selected_duration_key)

    def _populate_comparison_table(self) -> None:
        """Fill the comparison table rows matching user requirements."""
        if self.selected_plan_id == "enterprise":
            target_title = "Enterprise (5,000 Profiles)"
            rows = [
                ("Cloud Profiles Backup", "100", "5,000"),
                ("Profiles Created", "Unlimited", "Unlimited"),
                ("Profiles Open (Launch)", "Unlimited", "Unlimited"),
                ("API Access", "✕ No", "✓ Included"),
                ("All Bots, Tools & Scripts", "Basic Only", "👑 ALL Included"),
                ("Cloud Sync & Encryption", "Standard", "⚡ Instant Real-Time")
            ]
        elif self.selected_plan_id == "business":
            target_title = "Business (1,000 Profiles)"
            rows = [
                ("Cloud Profiles Backup", "100", "1,000"),
                ("Profiles Created", "Unlimited", "Unlimited"),
                ("Profiles Open (Launch)", "Unlimited", "Unlimited"),
                ("API Access", "✕ No", "✓ Included"),
                ("All Bots, Tools & Scripts", "Basic Only", "Core Tools"),
                ("Cloud Sync & Encryption", "Standard", "High Speed")
            ]
        else: # Professional
            target_title = "Professional (500 Profiles)"
            rows = [
                ("Cloud Profiles Backup", "100", "500"),
                ("Profiles Created", "Unlimited", "Unlimited"),
                ("Profiles Open (Launch)", "Unlimited", "Unlimited"),
                ("API Access", "✕ No", "✓ Included"),
                ("All Bots, Tools & Scripts", "Basic Only", "Basic Tools"),
                ("Cloud Sync & Encryption", "Standard", "High Speed")
            ]

        self.comp_table.setHorizontalHeaderLabels(["Plan Feature", "Free Account", target_title])
        self.comp_table.setRowCount(len(rows))
        for r_idx, (feat, free_val, target_val) in enumerate(rows):
            it_f = QTableWidgetItem(f"  {feat}")
            it_free = QTableWidgetItem(f" {free_val} ")
            it_free.setTextAlignment(Qt.AlignCenter)
            it_target = QTableWidgetItem(f" {target_val} ")
            it_target.setTextAlignment(Qt.AlignCenter)

            it_f.setForeground(QColor("#cdd6f4"))
            if free_val == "✕ No":
                it_free.setForeground(QColor("#f38ba8"))
            else:
                it_free.setForeground(QColor("#a6adc8"))

            if "👑" in target_val or "5,000" in target_val:
                it_target.setForeground(QColor("#cba6f7"))
            elif "1,000" in target_val or "500" in target_val or "✓" in target_val:
                it_target.setForeground(QColor("#89b4fa"))
            else:
                it_target.setForeground(QColor("#a6e3a1"))

            self.comp_table.setItem(r_idx, 0, it_f)
            self.comp_table.setItem(r_idx, 1, it_free)
            self.comp_table.setItem(r_idx, 2, it_target)

    def _on_plan_selected(self, plan_id: str) -> None:
        """Handle clicking plan button (Professional / Business / Enterprise)."""
        # Support alias mapping
        if plan_id in ("free", "pro", "vip_pro"):
            if plan_id == "free":
                plan_id = "pro"
            elif plan_id == "vip_pro":
                plan_id = "pro"
        elif plan_id == "vip_all_in_one":
            plan_id = "enterprise"

        self.selected_plan_id = plan_id

        # Update button styles
        for pid, btn in self.plan_btn_group.items():
            if pid == plan_id:
                if pid == "enterprise":
                    btn.setStyleSheet("""
                        QPushButton {
                            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #a855f7);
                            color: #ffffff;
                            border: 1.5px solid #c084fc;
                            border-radius: 8px;
                            font-weight: 900;
                            font-size: 13px;
                            padding: 6px 14px;
                        }
                    """)
                elif pid == "business":
                    btn.setStyleSheet("""
                        QPushButton {
                            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
                            color: #ffffff;
                            border: 1.5px solid #7dd3fc;
                            border-radius: 8px;
                            font-weight: 900;
                            font-size: 13px;
                            padding: 6px 14px;
                        }
                    """)
                else: # Professional
                    btn.setStyleSheet("""
                        QPushButton {
                            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                            color: #ffffff;
                            border: 1.5px solid #34d399;
                            border-radius: 8px;
                            font-weight: 900;
                            font-size: 13px;
                            padding: 6px 14px;
                        }
                    """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #161928;
                        color: #a6adc8;
                        border: 1px solid #2b2f48;
                        border-radius: 8px;
                        font-weight: 700;
                        font-size: 12.5px;
                        padding: 6px 14px;
                    }
                    QPushButton:hover {
                        background-color: #23273e;
                        color: #ffffff;
                    }
                """)

        # Render duration cards for the selected plan
        self._render_duration_cards(plan_id)
        self._populate_comparison_table()

    def _on_duration_selected(self, dur_key: str) -> None:
        """Handle duration card selection."""
        self.selected_duration_key = dur_key
        pcfg = self.plan_configs.get(self.selected_plan_id, {})
        durations = pcfg.get("durations", {})
        dinfo = durations.get(dur_key, list(durations.values())[0] if durations else {})

        # Update card styles
        for k, card in self.dur_card_widgets.items():
            if k == dur_key:
                card.setStyleSheet("""
                    QFrame {
                        background-color: #19253d;
                        border: 2px solid #38bdf8;
                        border-radius: 10px;
                    }
                """)
            else:
                card.setStyleSheet("""
                    QFrame {
                        background-color: #141829;
                        border: 1px solid #282d46;
                        border-radius: 10px;
                    }
                    QFrame:hover {
                        border-color: #454d73;
                        background-color: #1a2036;
                    }
                """)

        # Update Order Summary
        plan_title = pcfg.get("name", pcfg.get("title", "Professional"))
        quota = pcfg.get("quota", 500)
        self.lbl_ord_ver.setText(f"Plan version : <b style='color:#38bdf8;'>{plan_title} ({quota:,} Profiles)</b>")
        self.lbl_ord_dur.setText(f"Plan duration : <b style='color:#ffffff;'>{dinfo.get('label', '1 Month')}</b>")
        self.lbl_ord_amount.setText(f"Amount : <span style='font-size:22px; font-weight:900; color:#a6e3a1;'>{dinfo.get('price', '$10.00')}</span>")
        days = dinfo.get("days", "30 Days")
        self.lbl_ord_expiry.setText(f"Estimated duration : <b style='color:#f9e2af;'>{days}</b>")

        # Detect if current selection is a renewal or upgrade
        parent_w = self.parent()
        curr_plan_key = "free"
        if parent_w and hasattr(parent_w, "auth_mgr") and parent_w.auth_mgr:
            u = parent_w.auth_mgr.get_current_user() or {}
            curr_plan_key = str(u.get("plan_type", "free")).lower()
            if u.get("max_profiles", 100) == 500:
                curr_plan_key = "pro"
            elif u.get("max_profiles", 100) == 1000:
                curr_plan_key = "business"
            elif u.get("max_profiles", 100) >= 5000:
                curr_plan_key = "enterprise"

        is_renew = (
            (self.selected_plan_id == "pro" and curr_plan_key in ("pro", "professional", "vip")) or
            (self.selected_plan_id == "business" and curr_plan_key == "business") or
            (self.selected_plan_id == "enterprise" and curr_plan_key in ("enterprise", "ultimate"))
        )

        if self.selected_plan_id == "enterprise":
            action_text = f"🔄 Renew Enterprise ({dinfo.get('label', '1 Month')})" if is_renew else f"👑 Get Enterprise Plan ({dinfo.get('label', '1 Month')})"
            self.btn_submit_upgrade.setText(action_text)
            self.btn_submit_upgrade.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #a855f7);
                    color: #ffffff;
                    border: none;
                    border-radius: 10px;
                    padding: 11px 4px;
                    font-weight: 900;
                    font-size: 12.5px;
                }
                QPushButton:hover { background: #9333ea; }
            """)
        elif self.selected_plan_id == "business":
            action_text = f"🔄 Renew Business ({dinfo.get('label', '1 Month')})" if is_renew else f"🚀 Upgrade to Business ({dinfo.get('label', '1 Month')})"
            self.btn_submit_upgrade.setText(action_text)
            self.btn_submit_upgrade.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
                    color: #ffffff;
                    border: none;
                    border-radius: 10px;
                    padding: 11px 4px;
                    font-weight: 900;
                    font-size: 12.5px;
                }
                QPushButton:hover { background: #0ea5e9; }
            """)
        else: # Professional
            action_text = f"🔄 Renew Professional ({dinfo.get('label', '1 Month')})" if is_renew else f"🚀 Upgrade to Professional ({dinfo.get('label', '1 Month')})"
            self.btn_submit_upgrade.setText(action_text)
            self.btn_submit_upgrade.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                    color: #ffffff;
                    border: none;
                    border-radius: 10px;
                    padding: 11px 4px;
                    font-weight: 900;
                    font-size: 12.5px;
                }
                QPushButton:hover { background: #10b981; }
            """)

    def _on_submit_checkout(self) -> None:
        """Open web store checkout URL."""
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        pcfg = self.plan_configs.get(self.selected_plan_id, {})
        dinfo = pcfg.get("durations", {}).get(self.selected_duration_key, {})
        plan_param = dinfo.get("url_plan", f"{self.selected_plan_id}_{self.selected_duration_key}")
        token_param = f"&token={self.cloud_token}" if self.cloud_token else ""
        url = f"https://srbrowser.com/store?plan={plan_param}{token_param}"
        QDesktopServices.openUrl(QUrl(url))
        self.hide_drawer()

    def _on_redeem_clicked(self) -> None:
        """Trigger license key redeem."""
        self.hide_drawer()
        parent_w = self.parent()
        if parent_w and hasattr(parent_w, "_on_dash_redeem_clicked"):
            parent_w._on_dash_redeem_clicked()

    def _sync_live_plans(self) -> None:
        """Sync live plans and multi-durations dynamically from server API in a background QThread."""
        self._sync_worker = PlansSyncWorker(parent=self)
        self._sync_worker.plans_synced.connect(self._apply_synced_plans)
        self._sync_worker.start()

    def _apply_synced_plans(self, plans_list: list) -> None:
        try:
            for p in plans_list:
                pid = p.get("id")
                if pid in self.plan_configs:
                    if p.get("durations"):
                        for dkey, dval in p["durations"].items():
                            price_val = float(dval.get("price_usd", 0.0))
                            price_str = dval.get("price", f"${price_val:.2f}")
                            label_str = dval.get("label", f"{dkey} Month")
                            badge_str = dval.get("badge", "")

                            rate_str = dval.get("rate", "")
                            if not rate_str:
                                if "1" in dkey:
                                    rate_str = f"About ${price_val / 30:.2f}/Day"
                                elif "2" in dkey:
                                    rate_str = f"About ${price_val / 60:.2f}/Day"
                                elif "3" in dkey:
                                    rate_str = f"About ${price_val / 90:.2f}/Day"
                                elif "6" in dkey:
                                    rate_str = f"About ${price_val / 180:.2f}/Day"

                            if dkey in self.plan_configs[pid]["durations"]:
                                self.plan_configs[pid]["durations"][dkey]["price"] = price_str
                                self.plan_configs[pid]["durations"][dkey]["price_val"] = price_val
                                self.plan_configs[pid]["durations"][dkey]["rate"] = rate_str
                                self.plan_configs[pid]["durations"][dkey]["discount"] = badge_str
                            else:
                                self.plan_configs[pid]["durations"][dkey] = {
                                    "label": label_str,
                                    "price": price_str,
                                    "price_val": price_val,
                                    "rate": rate_str,
                                    "discount": badge_str,
                                    "url_plan": f"{pid}_{dkey}",
                                    "days": "30 Days"
                                }
            self._render_duration_cards(self.selected_plan_id)
            self._on_duration_selected(self.selected_duration_key)
            self._populate_comparison_table()
        except Exception as err:
            print(f"[APPLY SYNC ERROR]: {err}")

    def show_drawer(self) -> None:
        """Customer Standalone Edition: No upgrade overlay drawer."""
        self.hide()
        return
            
        # Refresh current user status label
        parent_w = self.parent()
        if parent_w and hasattr(parent_w, "auth_mgr") and parent_w.auth_mgr:
            u = parent_w.auth_mgr.get_current_user() or {}
            if u and u.get("is_logged_in"):
                ptype = str(u.get("plan_type", "Free Account")).title()
                quota = u.get("max_profiles", u.get("cloud_quota", 100)) or 100
                days_left = u.get("days_remaining", 0)
                if not days_left and ptype.lower() in ("pro", "business", "enterprise", "vip", "professional"):
                    days_left = 30
                
                if quota == 500 or ptype.lower() in ("pro", "vip", "professional"):
                    ptype_str = "⭐ Professional (500 Profiles)"
                elif quota == 1000 or ptype.lower() == "business":
                    ptype_str = "🚀 Business (1,000 Profiles)"
                elif quota >= 5000 or ptype.lower() in ("enterprise", "ultimate"):
                    ptype_str = "👑 Enterprise (5,000 Profiles)"
                else:
                    ptype_str = f"Free Account ({quota} Profiles)"

                if days_left and days_left > 0:
                    validity_badge = f" • <span style='color:#38bdf8; font-weight:800;'>⏳ {days_left} Days Remaining</span>"
                    if hasattr(self, "lbl_ord_active_validity"):
                        self.lbl_ord_active_validity.setText(f"Active plan validity : <b style='color:#38bdf8;'>{days_left} Days Remaining</b>")
                else:
                    validity_badge = " • <span style='color:#a6adc8;'>✨ Lifetime Free Access</span>"
                    if hasattr(self, "lbl_ord_active_validity"):
                        self.lbl_ord_active_validity.setText("Active plan validity : <b style='color:#a6e3a1;'>Lifetime Free</b>")

                self.lbl_curr_plan.setText(f"Current plan : <span style='color:#a6e3a1; font-weight:800;'>{ptype_str}</span>{validity_badge}")
            else:
                self.lbl_curr_plan.setText("Current plan : <span style='color:#a6e3a1; font-weight:800;'>Free Account (100 Profiles)</span>")
                if hasattr(self, "lbl_ord_active_validity"):
                    self.lbl_ord_active_validity.setText("Active plan validity : <b style='color:#a6e3a1;'>Lifetime Free</b>")

        # Sync live plans dynamically from server in background
        self._sync_live_plans()

    def hide_drawer(self) -> None:
        """Hide the drawer."""
        self.setVisible(False)
        self.closed.emit()

    def resizeEvent(self, event) -> None:
        """Ensure overlay matches parent size on window resize."""
        super().resizeEvent(event)
        if self.parent():
            pw = self.parent().width()
            ph = self.parent().height()
            self.setGeometry(0, 0, pw, ph)
            target_w = min(870, int(pw * 0.85))
            self.drawer_frame.setFixedWidth(target_w)
