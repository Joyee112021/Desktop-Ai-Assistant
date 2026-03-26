import math

from PySide6.QtCore import Property, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QRadialGradient
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from config.localization import tr
from gui.animations import create_parallel_animation, create_property_animation
from gui.effects import apply_soft_shadow
from gui.fonts import get_font
from gui.styles import COLORS, glass_panel_style, rgba


class PillLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setFont(get_font(9, weight=QFont.Weight.DemiBold))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(34)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setContentsMargins(0, 0, 0, 0)

    def set_theme(self, text, foreground, background, border=None):
        self.setText(text)
        border_color = border or background
        self.setStyleSheet(
            f"""
            color: {foreground};
            background-color: {background};
            border: 1px solid {border_color};
            border-radius: 12px;
            padding: 5px 12px;
            """
        )
        metrics = QFontMetrics(self.font())
        self.setFixedWidth(max(92, metrics.horizontalAdvance(text) + 42))


class GlassButton(QPushButton):
    VARIANTS = {
        "accent": {
            "bg": (
                "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
                f"stop:0 {COLORS['user_bubble_start']}, stop:1 {COLORS['user_bubble_end']})"
            ),
            "fg": COLORS["white"],
            "hover": COLORS["accent"],
            "border": rgba(COLORS["white"], 28),
        },
        "ghost": {
            "bg": rgba(COLORS["white"], 20),
            "fg": COLORS["text_main"],
            "hover": rgba(COLORS["white"], 32),
            "border": rgba(COLORS["white"], 28),
        },
        "warning": {
            "bg": rgba(COLORS["warning"], 30),
            "fg": COLORS["warning"],
            "hover": rgba(COLORS["warning"], 42),
            "border": rgba(COLORS["warning"], 58),
        },
    }

    def __init__(self, text, variant="ghost", compact=False, parent=None):
        super().__init__(text, parent)
        self.variant = variant
        self.compact = compact
        self.setFont(get_font(10, bold=True))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(36 if compact else 44)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        apply_soft_shadow(self, radius=22, dy=10, alpha=40)
        self._apply_style()

    def _apply_style(self):
        palette = self.VARIANTS[self.variant]
        radius = 9 if self.compact else 12
        padding_x = 10 if self.compact else 18
        padding_y = 4 if self.compact else 8

        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {palette['bg']};
                color: {palette['fg']};
                border-radius: {radius}px;
                border: 1px solid {palette['border']};
                padding: {padding_y}px {padding_x}px;
            }}
            QPushButton:hover {{
                background: {palette['hover']};
            }}
            QPushButton:pressed {{
                background: {palette['hover']};
            }}
            QPushButton:disabled {{
                background: {rgba(COLORS['white'], 14)};
                color: {rgba(COLORS['white'], 120)};
                border: 1px solid {rgba(COLORS['white'], 18)};
            }}
            """
        )
        metrics = QFontMetrics(self.font())
        min_width = 78 if self.compact else 104
        self.setFixedWidth(max(min_width, metrics.horizontalAdvance(self.text()) + (padding_x * 2) + 18))


class ThinkingIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        self._active = True
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(90)
        self.setFixedSize(34, 16)

    def sizeHint(self):
        return QSize(34, 16)

    def set_active(self, active):
        self._active = active
        if active and not self._timer.isActive():
            self._timer.start(90)
        elif not active and self._timer.isActive():
            self._timer.stop()
        self.update()

    def _tick(self):
        self._phase = (self._phase + 0.55) % (math.pi * 2.0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for index in range(3):
            distance = self._phase + (index * 0.8)
            weight = (math.sin(distance) + 1.0) / 2.0 if self._active else 0.35
            radius = 2.8 + (weight * 1.8)
            alpha = int(110 + (weight * 120))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(100, 216, 255, alpha))
            painter.drawEllipse(5 + (index * 11), 8 - radius, radius * 2.0, radius * 2.0)


class AuroraBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        self._busy = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(55)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_busy(self, busy):
        self._busy = busy
        self._timer.setInterval(105 if busy else 55)

    def _tick(self):
        self._phase += 0.014 if self._busy else 0.02
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        base_gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        base_gradient.setColorAt(0.0, QColor(COLORS["bg_start"]))
        base_gradient.setColorAt(1.0, QColor(COLORS["bg_end"]))
        painter.fillRect(rect, base_gradient)

        blobs = [
            (0.18, 0.16, 250, QColor(100, 216, 255, 110), 0.9),
            (0.78, 0.26, 220, QColor(123, 141, 255, 95), 1.3),
            (0.52, 0.82, 280, QColor(105, 230, 207, 86), 1.1),
        ]

        for x_ratio, y_ratio, radius, color, speed in blobs:
            center_x = rect.width() * x_ratio + math.sin(self._phase * speed) * 18
            center_y = rect.height() * y_ratio + math.cos(self._phase * speed) * 16
            radial = QRadialGradient(center_x, center_y, radius)
            radial.setColorAt(0.0, color)
            radial.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(radial)
            painter.drawEllipse(int(center_x - radius), int(center_y - radius), radius * 2, radius * 2)

        sheen = QLinearGradient(0, 0, rect.width(), rect.height() * 0.55)
        sheen.setColorAt(0.0, QColor(255, 255, 255, 34))
        sheen.setColorAt(0.35, QColor(255, 255, 255, 0))
        sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(rect, sheen)


class MessageBubble(QFrame):
    content_changed = Signal()

    def __init__(self, role, language_code="en", parent=None):
        super().__init__(parent)
        self.role = role.lower()
        self.language_code = language_code
        self._visible_text = ""
        self._pending_text = ""
        self.setObjectName("MessageBubble")

        self.setMaximumWidth(410)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        self.caption_label = QLabel(self._caption_text())
        self.caption_label.setFont(get_font(9, weight=QFont.Weight.DemiBold))
        layout.addWidget(self.caption_label)

        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.text_label.setFont(get_font(11))
        layout.addWidget(self.text_label)

        self.loading_row = QWidget()
        loading_layout = QHBoxLayout(self.loading_row)
        loading_layout.setContentsMargins(0, 0, 0, 0)
        loading_layout.setSpacing(8)
        self.loading_indicator = ThinkingIndicator()
        self.loading_label = QLabel(tr("thinking", self.language_code))
        self.loading_label.setFont(get_font(10, weight=QFont.Weight.Medium))
        loading_layout.addWidget(self.loading_indicator)
        loading_layout.addWidget(self.loading_label)
        loading_layout.addStretch(1)
        layout.addWidget(self.loading_row)

        self.typing_timer = QTimer(self)
        self.typing_timer.timeout.connect(self._flush_pending_text)
        self.typing_timer.setInterval(10)

        self._apply_style()
        self.set_loading(False)

    def _caption_text(self):
        if self.role == "user":
            return tr("caption_you", self.language_code)
        if self.role in {"assistant", "ai"}:
            return tr("caption_ai", self.language_code)
        return tr("caption_system", self.language_code)

    def _apply_style(self):
        if self.role == "user":
            self.caption_label.setStyleSheet(f"color: {rgba(COLORS['white'], 190)};")
            self.text_label.setStyleSheet(f"color: {COLORS['white']}; background: transparent;")
            self.loading_label.setStyleSheet(f"color: {rgba(COLORS['white'], 220)};")
            self.setStyleSheet(
                """
                QFrame#MessageBubble {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:1,
                        stop:0 #3a93ff,
                        stop:1 #63d6ff
                    );
                    border-radius: 14px;
                    border: none;
                }
                """
            )
        elif self.role in {"assistant", "ai"}:
            self.caption_label.setStyleSheet(f"color: {COLORS['accent']};")
            self.text_label.setStyleSheet(f"color: {COLORS['text_main']}; background: transparent;")
            self.loading_label.setStyleSheet(f"color: {COLORS['text_soft']};")
            self.setStyleSheet(
                f"""
                QFrame#MessageBubble {{
                    {glass_panel_style(radius=12, alpha=132, tone='panel_alt', border_alpha=0)}
                }}
                """
            )
        else:
            self.caption_label.setStyleSheet(f"color: {COLORS['text_muted']};")
            self.text_label.setStyleSheet(f"color: {COLORS['text_soft']}; background: transparent;")
            self.loading_label.setStyleSheet(f"color: {COLORS['text_soft']};")
            self.setStyleSheet(
                f"""
                QFrame#MessageBubble {{
                    background-color: {rgba(COLORS['white'], 6)};
                    border-radius: 10px;
                    border: none;
                }}
                """
            )

    def displayed_text(self):
        return self._visible_text + self._pending_text

    def set_loading(self, loading):
        self.loading_row.setVisible(loading)
        self.loading_indicator.set_active(loading)
        self.text_label.setVisible(not loading or bool(self._visible_text))
        self.content_changed.emit()

    def set_text(self, text):
        self.typing_timer.stop()
        self._pending_text = ""
        self._visible_text = text
        self.text_label.setText(text)
        self.text_label.setVisible(True)
        self.loading_row.setVisible(False)
        self.content_changed.emit()

    def enqueue_text(self, text):
        if not text:
            return

        self._pending_text += text
        self.set_loading(False)
        if not self.typing_timer.isActive():
            self.typing_timer.start()

    def mark_stream_complete(self):
        if self.typing_timer.isActive():
            self.typing_timer.setInterval(5)
        elif self._pending_text:
            self.typing_timer.setInterval(5)
            self.typing_timer.start()

    def _flush_pending_text(self):
        if not self._pending_text:
            self.typing_timer.stop()
            return

        pending_length = len(self._pending_text)
        if pending_length > 180:
            step = 18
        elif pending_length > 96:
            step = 12
        elif pending_length > 40:
            step = 7
        elif pending_length > 14:
            step = 3
        else:
            step = 1

        chunk = self._pending_text[:step]
        self._pending_text = self._pending_text[step:]
        self._visible_text += chunk
        self.text_label.setText(self._visible_text)
        self.text_label.setVisible(True)
        self.content_changed.emit()


class AnimatedMessageRow(QWidget):
    def __init__(self, role, bubble, parent=None):
        super().__init__(parent)
        self.role = role.lower()
        self.bubble = bubble
        self._slide_offset = 28

        self.setStyleSheet("background: transparent;")
        self.row_layout = QHBoxLayout(self)
        self.row_layout.setContentsMargins(0, 0, 0, 0)

        if self.role == "user":
            self.row_layout.addStretch(1)
            self.row_layout.addWidget(self.bubble, 0, Qt.AlignmentFlag.AlignRight)
        elif self.role in {"assistant", "ai"}:
            self.row_layout.addWidget(self.bubble, 0, Qt.AlignmentFlag.AlignLeft)
            self.row_layout.addStretch(1)
        else:
            self.row_layout.addStretch(1)
            self.row_layout.addWidget(self.bubble, 0, Qt.AlignmentFlag.AlignCenter)
            self.row_layout.addStretch(1)

        self._sync_margins()
        self._animation = None

    def _sync_margins(self):
        if self.role == "user":
            self.row_layout.setContentsMargins(0, 0, self._slide_offset, 0)
        elif self.role in {"assistant", "ai"}:
            self.row_layout.setContentsMargins(self._slide_offset, 0, 0, 0)
        else:
            top_margin = max(0, self._slide_offset // 3)
            self.row_layout.setContentsMargins(0, top_margin, 0, 0)

    def get_slide_offset(self):
        return self._slide_offset

    def set_slide_offset(self, value):
        self._slide_offset = value
        self._sync_margins()

    slideOffset = Property(int, get_slide_offset, set_slide_offset)

    def start_entry_animation(self):
        slide = create_property_animation(self, b"slideOffset", self._slide_offset, 0, duration=340)
        self._animation = create_parallel_animation(slide, parent=self)
        self._animation.start()
