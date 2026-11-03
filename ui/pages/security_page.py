"""
FaceLock Security Screen
Matches macOS Sonoma design specification exactly:
- Header: "Security" + "Choose how strict FaceLock is. Balanced works for most people."
- Left Column:
  - "Protection level" (Relaxed, Balanced, Strict) with dynamic explanation.
  - "Recognition" card: Match threshold slider, Strikes before lock stepper, Check interval slider.
- Right Column:
  - "Behavior" card:
    - Lock if stranger is next to me (MacToggle)
    - Lock when nobody is here (MacToggle)
    - Blink check with Beta badge (MacToggle)
  - "Lock method" card:
    - Segmented control (Windows lock, Privacy overlay) with explanatory caption.
  - Info banner: "FaceLock adds a layer on top of your Windows lock screen. It does not replace Windows Hello or your password."
"""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)

from core.config import AppConfig
from ui.theme import ThemeTokens
from ui.strings import Strings
from ui.components.card import MacCard, SettingsRow
from ui.components.toggle import MacToggle
from ui.components.segmented import SegmentedControl
from ui.components.stepper import Stepper
from ui.components.slider import LabeledSlider
from ui.components.badge import Badge


class SecurityPage(QWidget):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._syncing_presets = False
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 28)
        main_layout.setSpacing(16)

        # 1. Page Header
        h_title = QLabel(Strings.SECURITY_TITLE, self)
        h_title.setFont(ThemeTokens.get_font(size_pt=22, weight=600))
        h_title.setStyleSheet("color: #1D1D1F;")
        main_layout.addWidget(h_title)

        h_sub = QLabel(Strings.SECURITY_SUBTITLE, self)
        h_sub.setFont(ThemeTokens.get_font(size_pt=13))
        h_sub.setStyleSheet("color: #5C5C63;")
        main_layout.addWidget(h_sub)

        # 2. Two-Column Layout
        cols_layout = QHBoxLayout()
        cols_layout.setSpacing(24)

        # ====================================================================
        # LEFT COLUMN: Protection Level & Recognition Parameters
        # ====================================================================
        left_col = QVBoxLayout()
        left_col.setSpacing(14)

        # Protection Level
        prot_lbl = QLabel(Strings.PROTECTION_LEVEL_TITLE, self)
        prot_lbl.setFont(ThemeTokens.get_font(size_pt=12, weight=600))
        prot_lbl.setStyleSheet("color: #5C5C63;")
        left_col.addWidget(prot_lbl)

        card_preset = MacCard(is_hero=False, is_dark=False, parent=self)
        cp_layout = QVBoxLayout(card_preset)
        cp_layout.setContentsMargins(16, 14, 16, 14)
        cp_layout.setSpacing(10)

        # Determine initial preset from config
        initial_preset_idx = 1  # Balanced default
        if self.config.match_threshold <= 0.36 and self.config.strikes_to_lock >= 3:
            initial_preset_idx = 0
        elif self.config.match_threshold >= 0.44 and self.config.strikes_to_lock == 1:
            initial_preset_idx = 2

        self.preset_seg = SegmentedControl(["Relaxed", "Balanced", "Strict"], default_index=initial_preset_idx, is_dark=False, parent=card_preset)
        self.preset_seg.currentChanged.connect(self._on_preset_changed)
        cp_layout.addWidget(self.preset_seg)

        self.preset_desc = QLabel(Strings.PRESET_BALANCED_DESC, card_preset)
        self.preset_desc.setFont(ThemeTokens.get_font(size_pt=11))
        self.preset_desc.setStyleSheet("color: #5C5C63; line-height: 15px;")
        self.preset_desc.setWordWrap(True)
        cp_layout.addWidget(self.preset_desc)
        left_col.addWidget(card_preset)

        # Recognition Group
        rec_lbl = QLabel(Strings.RECOGNITION_GROUP, self)
        rec_lbl.setFont(ThemeTokens.get_font(size_pt=12, weight=600))
        rec_lbl.setStyleSheet("color: #5C5C63;")
        left_col.addWidget(rec_lbl)

        card_rec = MacCard(is_hero=False, is_dark=False, parent=self)
        cr_layout = QVBoxLayout(card_rec)
        cr_layout.setContentsMargins(0, 0, 0, 0)
        cr_layout.setSpacing(0)

        # Row 1: Match threshold slider
        self.slider_thresh = LabeledSlider(
            value=self.config.match_threshold,
            min_value=0.25,
            max_value=0.70,
            step=0.01,
            formatter=lambda v: f"{v:.2f}",
            is_dark=False,
            parent=card_rec
        )
        self.slider_thresh.valueChanged.connect(self._on_threshold_changed)
        cr_layout.addWidget(SettingsRow(
            Strings.MATCH_THRESHOLD,
            Strings.MATCH_THRESHOLD_DESC,
            self.slider_thresh,
            has_divider=True,
            is_dark=False,
            parent=card_rec
        ))

        # Row 2: Strikes before lock stepper
        self.stepper_strikes = Stepper(
            value=self.config.strikes_to_lock,
            min_value=1,
            max_value=10,
            is_dark=False,
            parent=card_rec
        )
        self.stepper_strikes.valueChanged.connect(self._on_strikes_changed)
        cr_layout.addWidget(SettingsRow(
            Strings.STRIKES_BEFORE_LOCK,
            Strings.STRIKES_BEFORE_LOCK_DESC,
            self.stepper_strikes,
            has_divider=True,
            is_dark=False,
            parent=card_rec
        ))

        # Row 3: Check interval slider
        self.slider_interval = LabeledSlider(
            value=float(self.config.check_interval_sec),
            min_value=1.0,
            max_value=10.0,
            step=1.0,
            formatter=lambda v: f"{int(v)} s",
            is_dark=False,
            parent=card_rec
        )
        self.slider_interval.valueChanged.connect(self._on_interval_changed)
        cr_layout.addWidget(SettingsRow(
            Strings.CHECK_INTERVAL,
            Strings.CHECK_INTERVAL_DESC,
            self.slider_interval,
            has_divider=False,
            is_dark=False,
            parent=card_rec
        ))

        left_col.addWidget(card_rec)
        left_col.addStretch()
        cols_layout.addLayout(left_col, stretch=1)

        # ====================================================================
        # RIGHT COLUMN: Behavior, Lock Method & Info Banner
        # ====================================================================
        right_col = QVBoxLayout()
        right_col.setSpacing(14)

        # Behavior Group
        beh_lbl = QLabel(Strings.BEHAVIOR_GROUP, self)
        beh_lbl.setFont(ThemeTokens.get_font(size_pt=12, weight=600))
        beh_lbl.setStyleSheet("color: #5C5C63;")
        right_col.addWidget(beh_lbl)

        card_beh = MacCard(is_hero=False, is_dark=False, parent=self)
        cb_layout = QVBoxLayout(card_beh)
        cb_layout.setContentsMargins(0, 0, 0, 0)
        cb_layout.setSpacing(0)

        # Row 1: Lock if stranger is next to me
        self.toggle_shoulder = MacToggle(checked=self.config.lock_on_stranger_with_owner, active_color="#1B7F45", accessible_name=Strings.STRANGER_WITH_OWNER, parent=card_beh)
        self.toggle_shoulder.toggled.connect(lambda v: self.config.update(lock_on_stranger_with_owner=v))
        cb_layout.addWidget(SettingsRow(
            Strings.STRANGER_WITH_OWNER,
            Strings.STRANGER_WITH_OWNER_DESC,
            self.toggle_shoulder,
            has_divider=True,
            is_dark=False,
            parent=card_beh
        ))

        # Row 2: Lock when nobody is here
        self.toggle_absence = MacToggle(checked=(self.config.lock_on_no_face_sec > 0), active_color="#1B7F45", accessible_name=Strings.ABSENCE_LOCK, parent=card_beh)
        self.toggle_absence.toggled.connect(self._on_absence_toggled)
        cb_layout.addWidget(SettingsRow(
            Strings.ABSENCE_LOCK,
            Strings.ABSENCE_LOCK_DESC,
            self.toggle_absence,
            has_divider=True,
            is_dark=False,
            parent=card_beh
        ))

        # Row 3: Blink check with Beta badge
        blink_row_widget = QWidget(card_beh)
        br_layout = QHBoxLayout(blink_row_widget)
        br_layout.setContentsMargins(16, 6, 16, 6)
        br_layout.setSpacing(12)

        b_text_col = QVBoxLayout()
        b_text_col.setSpacing(2)
        b_title_row = QHBoxLayout()
        b_title_row.setSpacing(8)

        b_title = QLabel(Strings.BLINK_CHECK, blink_row_widget)
        b_title.setFont(ThemeTokens.get_font(size_pt=13, weight=500))
        b_title.setStyleSheet("color: #1D1D1F;")
        b_title_row.addWidget(b_title)

        beta_badge = Badge(Strings.BADGE_BETA, variant="beta", is_dark=False, parent=blink_row_widget)
        b_title_row.addWidget(beta_badge)
        b_title_row.addStretch()
        b_text_col.addLayout(b_title_row)

        b_sub = QLabel(Strings.BLINK_CHECK_DESC, blink_row_widget)
        b_sub.setFont(ThemeTokens.get_font(size_pt=11))
        b_sub.setStyleSheet("color: #5C5C63;")
        b_text_col.addWidget(b_sub)

        br_layout.addLayout(b_text_col)
        br_layout.addStretch()

        self.toggle_blink = MacToggle(checked=False, active_color="#1B7F45", accessible_name="Blink check", parent=blink_row_widget)
        br_layout.addWidget(self.toggle_blink)
        cb_layout.addWidget(blink_row_widget)

        right_col.addWidget(card_beh)

        # Lock Method Group
        lock_lbl = QLabel(Strings.LOCK_METHOD_TITLE, self)
        lock_lbl.setFont(ThemeTokens.get_font(size_pt=12, weight=600))
        lock_lbl.setStyleSheet("color: #5C5C63;")
        right_col.addWidget(lock_lbl)

        card_lock = MacCard(is_hero=False, is_dark=False, parent=self)
        cl_layout = QVBoxLayout(card_lock)
        cl_layout.setContentsMargins(16, 14, 16, 14)
        cl_layout.setSpacing(10)

        initial_method_idx = 0 if self.config.lock_mode == "native" else 1
        self.lock_method_seg = SegmentedControl(["Windows lock", "Privacy overlay"], default_index=initial_method_idx, is_dark=False, parent=card_lock)
        self.lock_method_seg.currentChanged.connect(self._on_lock_method_changed)
        cl_layout.addWidget(self.lock_method_seg)

        lock_desc = QLabel(Strings.LOCK_METHOD_DESC, card_lock)
        lock_desc.setFont(ThemeTokens.get_font(size_pt=11))
        lock_desc.setStyleSheet("color: #5C5C63; line-height: 15px;")
        lock_desc.setWordWrap(True)
        cl_layout.addWidget(lock_desc)
        right_col.addWidget(card_lock)

        # Info Banner
        info_banner = QFrame(self)
        info_banner.setStyleSheet("""
            QFrame {
                background-color: #E6F0FC;
                border-radius: 10px;
            }
        """)
        ib_layout = QHBoxLayout(info_banner)
        ib_layout.setContentsMargins(14, 12, 14, 12)
        ib_layout.setSpacing(10)

        # Vector ℹ️ icon
        info_icon = QWidget(info_banner)
        info_icon.setFixedSize(18, 18)
        def draw_info_circle(e):
            p = QPainter(info_icon)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QPen(QColor("#0066D6"), 1.6))
            p.drawEllipse(1, 1, 16, 16)
            p.setFont(ThemeTokens.get_font(size_pt=10, weight=700))
            p.setPen(QColor("#0066D6"))
            p.drawText(QRectF(0, 0, 18, 18), Qt.AlignCenter, "i")
            p.end()
        info_icon.paintEvent = draw_info_circle
        ib_layout.addWidget(info_icon, 0, Qt.AlignTop)

        info_text = QLabel(Strings.INFO_BANNER_TEXT, info_banner)
        info_text.setFont(ThemeTokens.get_font(size_pt=11))
        info_text.setStyleSheet("color: #0B3F8A; line-height: 15px;")
        info_text.setWordWrap(True)
        ib_layout.addWidget(info_text)

        right_col.addWidget(info_banner)
        right_col.addStretch()
        cols_layout.addLayout(right_col, stretch=1)

        main_layout.addLayout(cols_layout)

    def _on_preset_changed(self, idx: int):
        self._syncing_presets = True
        if idx == 0:  # Relaxed
            self.config.update(match_threshold=0.35, strikes_to_lock=3, check_interval_sec=4.0)
            self.slider_thresh.setValue(0.35)
            self.stepper_strikes.setValue(3)
            self.slider_interval.setValue(4.0)
            self.preset_desc.setText(Strings.PRESET_RELAXED_DESC)
        elif idx == 1:  # Balanced
            self.config.update(match_threshold=0.40, strikes_to_lock=2, check_interval_sec=3.0)
            self.slider_thresh.setValue(0.40)
            self.stepper_strikes.setValue(2)
            self.slider_interval.setValue(3.0)
            self.preset_desc.setText(Strings.PRESET_BALANCED_DESC)
        elif idx == 2:  # Strict
            self.config.update(match_threshold=0.45, strikes_to_lock=1, check_interval_sec=2.0)
            self.slider_thresh.setValue(0.45)
            self.stepper_strikes.setValue(1)
            self.slider_interval.setValue(2.0)
            self.preset_desc.setText(Strings.PRESET_STRICT_DESC)
        self._syncing_presets = False

    def _on_threshold_changed(self, val: float):
        if not self._syncing_presets:
            self.config.update(match_threshold=round(val, 2))
            self._check_custom_preset()

    def _on_strikes_changed(self, val: int):
        if not self._syncing_presets:
            self.config.update(strikes_to_lock=val)
            self._check_custom_preset()

    def _on_interval_changed(self, val: float):
        if not self._syncing_presets:
            self.config.update(check_interval_sec=val)
            self._check_custom_preset()

    def _check_custom_preset(self):
        # Check if values match any exact preset; if not, show custom description
        t = self.config.match_threshold
        s = self.config.strikes_to_lock
        i = self.config.check_interval_sec

        if t == 0.35 and s == 3 and i == 4.0:
            self.preset_seg.setCurrentIndex(0)
            self.preset_desc.setText(Strings.PRESET_RELAXED_DESC)
        elif t == 0.40 and s == 2 and i == 3.0:
            self.preset_seg.setCurrentIndex(1)
            self.preset_desc.setText(Strings.PRESET_BALANCED_DESC)
        elif t == 0.45 and s == 1 and i == 2.0:
            self.preset_seg.setCurrentIndex(2)
            self.preset_desc.setText(Strings.PRESET_STRICT_DESC)
        else:
            self.preset_desc.setText(Strings.PRESET_CUSTOM_DESC)

    def _on_absence_toggled(self, checked: bool):
        self.config.update(lock_on_no_face_sec=120 if checked else 0)

    def _on_lock_method_changed(self, idx: int):
        mode = "native" if idx == 0 else "overlay"
        self.config.update(lock_mode=mode)
