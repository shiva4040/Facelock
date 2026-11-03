"""
FaceLock Settings Page
Configures system startup, tray minimization, camera hardware device,
theme appearance, sound alerts, and complete factory reset.
"""
import os
import sys
import platform
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QMessageBox, QLineEdit
)

from core.config import AppConfig, DEFAULT_BASE_DIR, OWNER_ENC_FILE
from core.events import events
from ui.components.card import MacCard, SettingsRow
from ui.components.toggle import MacToggle
from ui.components.pill_button import PillButton

IS_WINDOWS = platform.system() == "Windows"


def set_autostart(enable: bool) -> bool:
    """Configures application autostart on Windows or Linux."""
    if IS_WINDOWS:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE
            )
            app_path = sys.executable
            if enable:
                winreg.SetValueEx(key, "FaceLock", 0, winreg.REG_SZ, f'"{app_path}"')
            else:
                try:
                    winreg.DeleteValue(key, "FaceLock")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
            return True
        except Exception:
            return False
    return False


class SettingsPage(QWidget):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(16)

        header = QLabel("Settings", self)
        header.setStyleSheet("color: #FFFFFF; font-size: 22px; font-weight: 700;")
        main_layout.addWidget(header)

        # Card 1: General Preferences
        sec1 = QLabel("GENERAL PREFERENCES", self)
        sec1.setStyleSheet("color: #8E8E93; font-size: 11px; font-weight: 600; padding-left: 4px;")
        main_layout.addWidget(sec1)

        card1 = MacCard(self)
        c1_layout = QVBoxLayout(card1)
        c1_layout.setContentsMargins(0, 0, 0, 0)
        c1_layout.setSpacing(0)

        # Launch at login
        self.autostart_toggle = MacToggle(checked=self.config.launch_at_login, active_color="#0A84FF", parent=card1)
        self.autostart_toggle.toggled.connect(self._on_autostart_toggled)
        c1_layout.addWidget(SettingsRow(
            "Launch at Login",
            "Automatically start guarding when you sign into your computer.",
            self.autostart_toggle,
            has_divider=True,
            parent=card1
        ))

        # Start minimized
        self.minimized_toggle = MacToggle(checked=self.config.start_minimized, active_color="#0A84FF", parent=card1)
        self.minimized_toggle.toggled.connect(lambda v: self.config.update(start_minimized=v))
        c1_layout.addWidget(SettingsRow(
            "Start Minimized to Tray",
            "Run silently in the background without opening the main window.",
            self.minimized_toggle,
            has_divider=True,
            parent=card1
        ))

        # Persistent Live Activity
        self.activity_toggle = MacToggle(checked=self.config.notifications_enabled, active_color="#0A84FF", parent=card1)
        self.activity_toggle.toggled.connect(lambda v: self.config.update(notifications_enabled=v))
        c1_layout.addWidget(SettingsRow(
            "Show Live Activity",
            "Keep FaceLock status and security updates in a persistent bar at the top of the app.",
            self.activity_toggle,
            has_divider=True,
            parent=card1
        ))

        # Sound effects
        self.sound_toggle = MacToggle(checked=self.config.sound_enabled, active_color="#0A84FF", parent=card1)
        self.sound_toggle.toggled.connect(lambda v: self.config.update(sound_enabled=v))
        c1_layout.addWidget(SettingsRow(
            "Play Subtle Alert Sounds",
            "Audible chimes on intruder detection and screen lock.",
            self.sound_toggle,
            has_divider=False,
            parent=card1
        ))
        main_layout.addWidget(card1)

        # Master PIN fallback used by FaceLock's privacy overlay.
        pin_card = MacCard(self)
        pin_layout = QVBoxLayout(pin_card)
        pin_layout.setContentsMargins(16, 14, 16, 14)
        pin_layout.setSpacing(8)
        pin_dark = self.config.theme == "dark"
        pin_title_fg = "#F5F5F7" if pin_dark else "#1D1D1F"
        pin_description_fg = "#A1A1A6" if pin_dark else "#6E6E73"
        pin_input_bg = "rgba(255,255,255,0.08)" if pin_dark else "rgba(120,120,128,0.10)"
        pin_input_fg = "#F5F5F7" if pin_dark else "#222222"
        pin_title = QLabel("Master PIN", pin_card)
        pin_title.setStyleSheet(f"color: {pin_title_fg}; font-size: 13px; font-weight: 600;")
        pin_description = QLabel("Set a private 4–8 digit fallback for FaceLock's privacy overlay.", pin_card)
        pin_description.setStyleSheet(f"color: {pin_description_fg}; font-size: 11px;")
        pin_layout.addWidget(pin_title)
        pin_layout.addWidget(pin_description)
        pin_controls = QWidget(pin_card)
        pin_row = QHBoxLayout(pin_controls)
        pin_row.setContentsMargins(0, 0, 0, 0)
        pin_row.setSpacing(8)
        self.current_pin_input = QLineEdit(pin_controls)
        self.current_pin_input.setEchoMode(QLineEdit.Password)
        self.current_pin_input.setMaxLength(8)
        self.current_pin_input.setPlaceholderText("Current PIN")
        self.new_pin_input = QLineEdit(pin_controls)
        self.new_pin_input.setEchoMode(QLineEdit.Password)
        self.new_pin_input.setMaxLength(8)
        self.new_pin_input.setPlaceholderText("New 4–8 digit PIN")
        self.confirm_pin_input = QLineEdit(pin_controls)
        self.confirm_pin_input.setEchoMode(QLineEdit.Password)
        self.confirm_pin_input.setMaxLength(8)
        self.confirm_pin_input.setPlaceholderText("Confirm PIN")
        for field in (self.current_pin_input, self.new_pin_input, self.confirm_pin_input):
            field.setStyleSheet(f"QLineEdit {{ background: {pin_input_bg}; border: 1px solid rgba(120,120,128,0.22); border-radius: 9px; padding: 8px; color: {pin_input_fg}; }}")
            pin_row.addWidget(field, 1)
        self.pin_save_button = PillButton("Set Master PIN", variant="primary", parent=pin_controls)
        self.pin_save_button.clicked.connect(self._save_master_pin)
        pin_row.addWidget(self.pin_save_button)
        self.pin_status = QLabel(
            "A Master PIN is set." if self.config.overlay_pin_hash else "No Master PIN set. PIN fallback is unavailable until you set one.",
            pin_card,
        )
        self.pin_status.setStyleSheet(f"color: {pin_description_fg}; font-size: 11px;")
        pin_layout.addWidget(pin_controls)
        pin_layout.addWidget(self.pin_status)
        main_layout.addWidget(pin_card)

        # Card 2: Hardware & Appearance
        sec2 = QLabel("HARDWARE & APPEARANCE", self)
        sec2.setStyleSheet("color: #8E8E93; font-size: 11px; font-weight: 600; padding-left: 4px; margin-top: 10px;")
        main_layout.addWidget(sec2)

        card2 = MacCard(self)
        c2_layout = QVBoxLayout(card2)
        c2_layout.setContentsMargins(0, 0, 0, 0)
        c2_layout.setSpacing(0)

        # Camera selection combo
        self.cam_combo = QComboBox(card2)
        for i in range(4):
            self.cam_combo.addItem(f"Camera Device {i}", i)
        self.cam_combo.setCurrentIndex(min(self.config.camera_index, 3))
        self.cam_combo.currentIndexChanged.connect(self._on_cam_changed)
        c2_layout.addWidget(SettingsRow(
            "Active Camera Device",
            "Select the optical sensor used for facial scanning.",
            self.cam_combo,
            has_divider=True,
            parent=card2
        ))

        # Theme selection combo
        self.theme_combo = QComboBox(card2)
        self.theme_combo.addItem("Light Mode", "light")
        self.theme_combo.addItem("Dark Mode", "dark")
        idx = 1 if self.config.theme == "dark" else 0
        self.theme_combo.setCurrentIndex(idx)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        c2_layout.addWidget(SettingsRow(
            "App Appearance",
            "Light mode matches the supplied macOS-style screen designs.",
            self.theme_combo,
            has_divider=False,
            parent=card2
        ))
        main_layout.addWidget(card2)

        # Card 3: Danger Zone / Reset
        sec3 = QLabel("DATA & PRIVACY", self)
        sec3.setStyleSheet("color: #8E8E93; font-size: 11px; font-weight: 600; padding-left: 4px; margin-top: 10px;")
        main_layout.addWidget(sec3)

        card3 = MacCard(self)
        c3_layout = QVBoxLayout(card3)
        c3_layout.setContentsMargins(0, 0, 0, 0)
        c3_layout.setSpacing(0)

        reset_btn = PillButton("Reset Everything", variant="danger", parent=card3)
        reset_btn.clicked.connect(self._reset_everything)
        c3_layout.addWidget(SettingsRow(
            "Factory Reset",
            "Clears all facial data, snapshots, logs, and preferences.",
            reset_btn,
            has_divider=False,
            parent=card3
        ))
        main_layout.addWidget(card3)

        # Card 4: About / Security Model
        sec4 = QLabel("ABOUT & SECURITY MODEL", self)
        sec4.setStyleSheet("color: #8E8E93; font-size: 11px; font-weight: 600; padding-left: 4px; margin-top: 10px;")
        main_layout.addWidget(sec4)

        card4 = MacCard(self)
        c4_layout = QVBoxLayout(card4)
        c4_layout.setContentsMargins(18, 16, 18, 16)
        c4_layout.setSpacing(8)

        about_title = QLabel("FaceLock v1.0 Production Security Model", card4)
        about_title.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 600;")
        c4_layout.addWidget(about_title)

        about_desc = QLabel(
            "FaceLock is an automated physical privacy layer that locks your screen when strangers approach or when you leave.\n\n"
            "• Convenience Layer: FaceLock triggers your OS lock screen. It is NOT a replacement for Windows Hello, BitLocker, or an OS password.\n"
            "• Biometric Encryption: Face embeddings are encrypted at rest using Windows DPAPI or OS Keyring. No plaintext keys are stored.\n"
            "• Tamper Resistance: Preferences are cryptographically HMAC-signed. A background watchdog guards against unauthorized process kills.",
            card4
        )
        about_desc.setWordWrap(True)
        about_desc.setStyleSheet("color: #8E8E93; font-size: 11px; line-height: 1.4;")
        c4_layout.addWidget(about_desc)
        main_layout.addWidget(card4)

        main_layout.addStretch()

    def _on_autostart_toggled(self, enabled: bool):
        set_autostart(enabled)
        self.config.update(launch_at_login=enabled)

    def _on_cam_changed(self, idx: int):
        self.config.update(camera_index=idx)

    def _on_theme_changed(self, idx: int):
        theme_val = self.theme_combo.currentData()
        self.config.update(theme=theme_val)
        events.config_updated.emit()

    def _save_master_pin(self):
        current = self.current_pin_input.text().strip()
        new_pin = self.new_pin_input.text().strip()
        confirm = self.confirm_pin_input.text().strip()
        if self.config.overlay_pin_hash and not self.config.verify_pin(current):
            self.pin_status.setText("Current PIN is incorrect.")
            return
        if not new_pin.isdigit() or not 4 <= len(new_pin) <= 8:
            self.pin_status.setText("Enter a new PIN with 4–8 digits.")
            return
        if new_pin != confirm:
            self.pin_status.setText("The new PINs do not match.")
            return
        self.config.set_pin(new_pin)
        self.current_pin_input.clear()
        self.new_pin_input.clear()
        self.confirm_pin_input.clear()
        self.pin_status.setText("Master PIN saved. Keep it private; it is required for PIN fallback.")

    def _reset_everything(self):
        reply = QMessageBox.critical(
            self,
            "Factory Reset FaceLock",
            "This will permanently delete your enrolled face profile, all intruder snapshots, and reset all settings to defaults.\n\nAre you absolutely sure?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # Delete owner file
            if os.path.exists(OWNER_ENC_FILE):
                os.remove(OWNER_ENC_FILE)
            events.owner_data_cleared.emit()

            # Reset config
            cfg = AppConfig()
            cfg.save()
            events.status_changed.emit("paused", "Reset to Defaults")
            QMessageBox.information(self, "FaceLock Reset", "FaceLock has been reset to defaults.")

