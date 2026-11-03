"""
FaceLock macOS Sonoma Labeled Slider
Horizontal slider with accent #0066D6 groove and right-aligned tabular value label.
"""
from typing import Callable, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QSlider, QLabel
from ui.theme import ThemeTokens


class LabeledSlider(QWidget):
    valueChanged = Signal(float)

    def __init__(
        self,
        value: float = 0.40,
        min_value: float = 0.25,
        max_value: float = 0.70,
        step: float = 0.01,
        formatter: Optional[Callable[[float], str]] = None,
        is_dark: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self._min = min_value
        self._max = max_value
        self._step = step
        self._formatter = formatter or (lambda v: f"{v:.2f}")
        self.is_dark = is_dark
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # QSlider works in integers, map float range [min, max] to int [0, steps]
        self._steps = int(round((self._max - self._min) / self._step))
        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setRange(0, self._steps)
        self.slider.setFixedWidth(110)
        self.slider.setFocusPolicy(Qt.StrongFocus)
        self.slider.setCursor(Qt.PointingHandCursor)

        current_step = int(round((value - self._min) / self._step))
        self.slider.setValue(current_step)
        self.slider.valueChanged.connect(self._on_slider_moved)
        layout.addWidget(self.slider)

        # Tabular Value Label
        self.val_label = QLabel(self._formatter(value), self)
        self.val_label.setFixedWidth(38)
        self.val_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.val_label.setFont(ThemeTokens.get_font(size_pt=13, weight=500, tabular=True))
        layout.addWidget(self.val_label)

        self._apply_style()

    def _on_slider_moved(self, step_idx: int):
        val = self._min + step_idx * self._step
        self.val_label.setText(self._formatter(val))
        self.valueChanged.emit(val)

    def value(self) -> float:
        return self._min + self.slider.value() * self._step

    def setValue(self, val: float):
        clamped = max(self._min, min(self._max, val))
        step_idx = int(round((clamped - self._min) / self._step))
        if self.slider.value() != step_idx:
            self.slider.setValue(step_idx)
            self.val_label.setText(self._formatter(clamped))

    def setDarkTheme(self, is_dark: bool):
        self.is_dark = is_dark
        self._apply_style()

    def _apply_style(self):
        accent = "#0A84FF" if self.is_dark else "#0066D6"
        track_bg = "#48484A" if self.is_dark else "#E6E6EA"
        text_color = "#F5F5F7" if self.is_dark else "#1D1D1F"

        self.slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px;
                background: {track_bg};
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {accent};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: #FFFFFF;
                border: 1px solid rgba(0, 0, 0, 0.15);
                width: 18px;
                height: 18px;
                margin-top: -7px;
                margin-bottom: -7px;
                border-radius: 9px;
            }}
            QSlider::handle:horizontal:focus {{
                border: 2px solid {accent};
            }}
        """)
        self.val_label.setStyleSheet(f"color: {text_color};")

