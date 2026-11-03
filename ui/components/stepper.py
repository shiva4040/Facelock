"""
FaceLock macOS Sonoma Stepper Control
Two 26px round push buttons ('-' and '+') with a centered tabular number.
Emits valueChanged(int).
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from ui.theme import ThemeTokens


class Stepper(QWidget):
    valueChanged = Signal(int)

    def __init__(
        self,
        value: int = 2,
        min_value: int = 1,
        max_value: int = 10,
        is_dark: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self._value = value
        self.min_value = min_value
        self.max_value = max_value
        self.is_dark = is_dark
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Minus button
        self.btn_minus = QPushButton("-", self)
        self.btn_minus.setFixedSize(26, 26)
        self.btn_minus.setCursor(Qt.PointingHandCursor)
        self.btn_minus.setAccessibleName("Decrease value")
        self.btn_minus.clicked.connect(self._decrement)
        layout.addWidget(self.btn_minus)

        # Value label
        self.label = QLabel(str(self._value), self)
        self.label.setFixedWidth(24)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFont(ThemeTokens.get_font(size_pt=13, weight=600, tabular=True))
        layout.addWidget(self.label)

        # Plus button
        self.btn_plus = QPushButton("+", self)
        self.btn_plus.setFixedSize(26, 26)
        self.btn_plus.setCursor(Qt.PointingHandCursor)
        self.btn_plus.setAccessibleName("Increase value")
        self.btn_plus.clicked.connect(self._increment)
        layout.addWidget(self.btn_plus)

        self._apply_style()

    def value(self) -> int:
        return self._value

    def setValue(self, val: int):
        clamped = max(self.min_value, min(self.max_value, val))
        if clamped != self._value:
            self._value = clamped
            self.label.setText(str(self._value))
            self.valueChanged.emit(self._value)

    def _decrement(self):
        if self._value > self.min_value:
            self.setValue(self._value - 1)

    def _increment(self):
        if self._value < self.max_value:
            self.setValue(self._value + 1)

    def setDarkTheme(self, is_dark: bool):
        self.is_dark = is_dark
        self._apply_style()

    def _apply_style(self):
        border = "#48484A" if self.is_dark else "#CFCFD6"
        bg = "#2C2C2E" if self.is_dark else "#FFFFFF"
        bg_hover = "#3A3A3C" if self.is_dark else "#F5F5F7"
        text = "#F5F5F7" if self.is_dark else "#1D1D1F"
        focus_ring = "#0A84FF" if self.is_dark else "#0066D6"

        btn_qss = f"""
            QPushButton {{
                background-color: {bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 13px;
                font-size: 15px;
                font-weight: 500;
                line-height: 24px;
                padding-bottom: 2px;
                outline: none;
            }}
            QPushButton:hover {{
                background-color: {bg_hover};
            }}
            QPushButton:focus {{
                border: 2px solid {focus_ring};
            }}
            QPushButton:disabled {{
                color: #8E8E93;
                border-color: #38383A;
            }}
        """
        self.btn_minus.setStyleSheet(btn_qss)
        self.btn_plus.setStyleSheet(btn_qss)
        self.label.setStyleSheet(f"color: {text};")

