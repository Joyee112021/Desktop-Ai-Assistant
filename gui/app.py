from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, QThread, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QPainterPath, QRegion, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ai.tool_router import ToolRouter
from ai.model_loader import ModelLoader
from ai.prompt_template import ChatMemory
from config.localization import hardware_label, language_label, profile_label, tr
from config.settings import (
    APP_HEIGHT,
    APP_NAME,
    APP_WIDTH,
    APP_WINDOW_RADIUS,
)
from config.user_settings import ModelOption, UserSettings, build_runtime_config, normalize_settings, save_user_settings
from gui.animations import create_parallel_animation, create_property_animation
from gui.components import AuroraBackground, AnimatedMessageRow, GlassButton, MessageBubble, PillLabel
from gui.effects import apply_soft_shadow
from gui.fonts import get_font
from gui.setup_dialog import SetupDialog
from gui.styles import APP_STYLE, COLORS, SCROLLBAR_STYLE, glass_panel_style, rgba
from utils.attachment_tools import (
    capture_desktop_screenshot,
    image_file_to_data_url,
    is_document_file,
    read_text_file_context,
)
from utils.document_memory import DocumentMemoryStore
from utils.hotkey import HotkeyManager
from utils.logging_utils import get_logger
from utils.performance import AIWorker, ModelWarmupWorker
from utils.web_search import format_search_results, search_duckduckgo

class WebSearchWorker(QThread):
    signal_done = Signal(str, str)
    signal_error = Signal(str)

    def __init__(self, query: str):
        super().__init__()
        self.query = query

    def run(self):
        try:
            results = search_duckduckgo(self.query, max_results=5)
            if not results:
                self.signal_error.emit("No search results were returned.")
                return
            self.signal_done.emit(self.query, format_search_results(self.query, results))
        except Exception as exc:
            self.signal_error.emit(str(exc))


class DesktopAssistantApp(QWidget):
    def __init__(self, settings: UserSettings, catalog: list[ModelOption]):
        super().__init__()

        self.catalog = catalog
        self.settings = normalize_settings(settings, catalog)
        self.runtime_config = build_runtime_config(self.settings, catalog)
        self.logger = get_logger(__name__)
        self.memory_store = DocumentMemoryStore()
        self.tool_router = ToolRouter(self.memory_store)

        self.panel_padding = 10
        self.is_visible = True
        self.model_ready = False
        self.is_busy = False
        self.is_warming_up = False
        self.pending_generation = False
        self.request_had_error = False
        self.request_was_stopped = False
        self.response_started = False
        self.current_ai_bubble = None
        self.current_response = ""
        self._window_animation = None
        self._status_snapshot = ("", "warning")
        self._did_show_ready_message = False

        self.pending_file_context = ""
        self.pending_file_label = ""
        self.pending_image_paths: list[Path] = []
        self.pending_search_context = ""
        self.pending_search_query = ""
        self.pending_tool_context = ""
        self.pending_tool_labels: list[str] = []
        self.pending_auto_send_text = None
        self.search_worker = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(APP_WIDTH, APP_HEIGHT)
        self.setStyleSheet(APP_STYLE)

        self.memory = ChatMemory(
            system_prompt=self.runtime_config.system_prompt,
            max_history_messages=self.runtime_config.history_messages,
        )

        self.background = AuroraBackground(self)
        self.main_container = QFrame(self)
        self.main_container.setObjectName("MainContainer")
        self.main_container.setStyleSheet(
            f"""
            QFrame#MainContainer {{
                {glass_panel_style(radius=24, alpha=112, tone='panel', border_alpha=0)}
            }}
            """
        )

        self._setup_ui()
        self._setup_shortcuts()
        self._position_window()
        self._create_workers()
        self._start_hotkey()
        self._refresh_header()
        self._apply_translations()
        self._update_attachment_preview()
        self._update_controls()
        self._show_boot_messages()

        QTimer.singleShot(140, self._play_intro_animation)
        if self.runtime_config.warmup_on_launch:
            QTimer.singleShot(220, self.start_model_warmup)
        else:
            self._set_status(self._t("app_status_ready"), "accent")

    def _t(self, key: str, **kwargs) -> str:
        return tr(key, self.settings.interface_language, **kwargs)

    def _create_workers(self):
        self.ai_worker = AIWorker(self.memory, self.runtime_config)
        self.ai_worker.signal_start.connect(self.on_ai_start)
        self.ai_worker.signal_token.connect(self.on_ai_token)
        self.ai_worker.signal_done.connect(self.on_ai_done)
        self.ai_worker.signal_error.connect(self.on_ai_error)
        self.ai_worker.signal_stopped.connect(self.on_ai_stopped)

        self.warmup_worker = ModelWarmupWorker(self.runtime_config)
        self.warmup_worker.signal_ready.connect(self.on_model_ready)
        self.warmup_worker.signal_error.connect(self.on_model_error)

    def _start_hotkey(self):
        self.hotkey_mgr = HotkeyManager(self.runtime_config.hotkey)
        self.hotkey_mgr.toggle_signal.connect(self.toggle_window)
        self.hotkey_mgr.error_signal.connect(self.on_hotkey_error)
        self.hotkey_enabled = self.hotkey_mgr.start()

    def _restart_hotkey(self):
        try:
            self.hotkey_mgr.stop()
        except Exception:
            pass
        self._start_hotkey()
        self._update_footer_hint()

    def _create_horizontal_strip(self, spacing=8, viewport_margins=(0, 0, 0, 0), min_height=40):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("background: transparent;")
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        scroll.setMinimumHeight(min_height)
        scroll.setMaximumHeight(min_height + 14)
        scroll.horizontalScrollBar().setStyleSheet(SCROLLBAR_STYLE)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        row = QHBoxLayout(container)
        row.setContentsMargins(*viewport_margins)
        row.setSpacing(spacing)
        row.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        scroll.setWidget(container)
        return scroll, container, row

    def _setup_ui(self):
        layout = QVBoxLayout(self.main_container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.hero_card = QFrame()
        self.hero_card.setObjectName("HeroCard")
        self.hero_card.setStyleSheet(
            f"QFrame#HeroCard {{{glass_panel_style(radius=18, alpha=132, tone='surface', border_alpha=0)}}}"
        )
        apply_soft_shadow(self.hero_card, radius=30, dy=12, alpha=50)
        hero_layout = QVBoxLayout(self.hero_card)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        hero_layout.setSpacing(10)

        top_row = QHBoxLayout()
        title_column = QVBoxLayout()
        title_column.setSpacing(4)

        self.title_label = QLabel()
        self.title_label.setFont(get_font(18, bold=True))
        self.title_label.setStyleSheet(f"color: {COLORS['text_main']};")
        title_column.addWidget(self.title_label)

        self.subtitle_label = QLabel()
        self.subtitle_label.setFont(get_font(10))
        self.subtitle_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        title_column.addWidget(self.subtitle_label)

        top_row.addLayout(title_column)
        top_row.addStretch(1)

        self.status_pill = PillLabel()
        top_row.addWidget(self.status_pill)
        hero_layout.addLayout(top_row)

        badge_top_scroll, self.badge_top_container, badge_row_top = self._create_horizontal_strip(
            spacing=6, min_height=40
        )
        badge_bottom_scroll, self.badge_bottom_container, badge_row_bottom = self._create_horizontal_strip(
            spacing=6, min_height=40
        )

        self.model_pill = PillLabel()
        self.profile_pill = PillLabel()
        self.hardware_pill = PillLabel()
        self.reply_language_pill = PillLabel()
        self.context_pill = PillLabel()

        badge_row_top.addWidget(self.model_pill)
        badge_row_top.addWidget(self.profile_pill)
        badge_row_top.addWidget(self.hardware_pill)
        badge_row_top.addStretch(1)
        hero_layout.addWidget(badge_top_scroll)

        badge_row_bottom.addWidget(self.reply_language_pill)
        badge_row_bottom.addWidget(self.context_pill)
        badge_row_bottom.addStretch(1)
        hero_layout.addWidget(badge_bottom_scroll)

        actions_scroll, self.actions_container, action_row = self._create_horizontal_strip(spacing=6, min_height=42)

        self.settings_button = GlassButton("", variant="ghost", compact=True)
        self.settings_button.clicked.connect(self.open_settings_dialog)
        action_row.addWidget(self.settings_button)

        self.copy_button = GlassButton("", variant="ghost", compact=True)
        self.copy_button.clicked.connect(self.copy_last_response)
        action_row.addWidget(self.copy_button)

        self.export_button = GlassButton("", variant="ghost", compact=True)
        self.export_button.clicked.connect(self.export_chat)
        action_row.addWidget(self.export_button)

        self.clear_button = GlassButton("", variant="ghost", compact=True)
        self.clear_button.clicked.connect(self.clear_chat)
        action_row.addWidget(self.clear_button)

        self.stop_button = GlassButton("", variant="warning", compact=True)
        self.stop_button.clicked.connect(self.stop_generation)
        action_row.addWidget(self.stop_button)

        action_row.addStretch(1)
        hero_layout.addWidget(actions_scroll)
        layout.addWidget(self.hero_card)

        self.chat_card = QFrame()
        self.chat_card.setObjectName("ChatCard")
        self.chat_card.setStyleSheet(
            f"QFrame#ChatCard {{{glass_panel_style(radius=16, alpha=108, tone='panel_alt', border_alpha=0)}}}"
        )
        apply_soft_shadow(self.chat_card, radius=34, dy=14, alpha=42)
        chat_card_layout = QVBoxLayout(self.chat_card)
        chat_card_layout.setContentsMargins(10, 10, 10, 10)
        chat_card_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent;")
        self.scroll_area.verticalScrollBar().setStyleSheet(SCROLLBAR_STYLE)

        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("background: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(6, 8, 6, 8)
        self.chat_layout.setSpacing(10)
        self.chat_layout.addStretch(1)

        self.scroll_area.setWidget(self.chat_container)
        chat_card_layout.addWidget(self.scroll_area)
        layout.addWidget(self.chat_card, 1)

        self.composer_card = QFrame()
        self.composer_card.setObjectName("ComposerCard")
        self.composer_card.setStyleSheet(
            f"QFrame#ComposerCard {{{glass_panel_style(radius=14, alpha=138, tone='surface_soft', border_alpha=0)}}}"
        )
        apply_soft_shadow(self.composer_card, radius=28, dy=12, alpha=46)
        composer_layout = QVBoxLayout(self.composer_card)
        composer_layout.setContentsMargins(12, 10, 12, 10)
        composer_layout.setSpacing(8)

        extras_scroll, self.extras_container, extras_row = self._create_horizontal_strip(spacing=6, min_height=42)

        self.attach_file_button = GlassButton("", variant="ghost", compact=True)
        self.attach_file_button.clicked.connect(self.attach_file)
        extras_row.addWidget(self.attach_file_button)

        self.attach_image_button = GlassButton("", variant="ghost", compact=True)
        self.attach_image_button.clicked.connect(self.attach_image)
        extras_row.addWidget(self.attach_image_button)

        self.attach_desktop_button = GlassButton("", variant="ghost", compact=True)
        self.attach_desktop_button.clicked.connect(self.attach_desktop_view)
        extras_row.addWidget(self.attach_desktop_button)

        self.search_button = GlassButton("", variant="ghost", compact=True)
        self.search_button.clicked.connect(self.start_web_search)
        extras_row.addWidget(self.search_button)

        self.clear_extras_button = GlassButton("", variant="ghost", compact=True)
        self.clear_extras_button.clicked.connect(self.clear_pending_extras)
        extras_row.addWidget(self.clear_extras_button)

        extras_row.addStretch(1)
        composer_layout.addWidget(extras_scroll)

        self.attachment_label = QLabel()
        self.attachment_label.setWordWrap(True)
        self.attachment_label.setFont(get_font(9))
        self.attachment_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        composer_layout.addWidget(self.attachment_label)

        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        self.input_box = QLineEdit()
        self.input_box.setFont(get_font(11))
        self.input_box.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {rgba(COLORS['white'], 10)};
                border: 1px solid {rgba(COLORS['white'], 22)};
                border-radius: 14px;
                padding: 12px 14px;
                color: {COLORS['text_main']};
            }}
            QLineEdit:focus {{
                border: 1px solid {rgba(COLORS['accent'], 120)};
                background-color: {rgba(COLORS['white'], 14)};
            }}
            """
        )
        self.input_box.returnPressed.connect(self.send_message)
        input_row.addWidget(self.input_box, 1)

        self.btn_send = GlassButton("Send", variant="accent")
        self.btn_send.clicked.connect(self.send_message)
        input_row.addWidget(self.btn_send)
        composer_layout.addLayout(input_row)

        self.footer_label = QLabel()
        self.footer_label.setFont(get_font(9))
        self.footer_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        composer_layout.addWidget(self.footer_label)
        layout.addWidget(self.composer_card)

    def _apply_translations(self):
        self.setWindowTitle(self._t("app_name"))
        self.title_label.setText(self._t("app_name"))
        self.subtitle_label.setText(self._t("app_subtitle"))

        self.settings_button.setText(self._t("app_settings"))
        self.copy_button.setText(self._t("app_copy"))
        self.export_button.setText(self._t("app_export"))
        self.clear_button.setText(self._t("app_clear"))
        self.stop_button.setText(self._t("app_stop"))
        self.attach_file_button.setText(self._t("app_file"))
        self.attach_image_button.setText(self._t("app_image"))
        self.attach_desktop_button.setText(self._t("app_desktop"))
        self.search_button.setText(self._t("app_search"))
        self.clear_extras_button.setText(self._t("app_clear_extras"))
        self.btn_send.setText(self._t("app_send"))

        for button in (
            self.settings_button,
            self.copy_button,
            self.export_button,
            self.clear_button,
            self.stop_button,
            self.attach_file_button,
            self.attach_image_button,
            self.attach_desktop_button,
            self.search_button,
            self.clear_extras_button,
            self.btn_send,
        ):
            button._apply_style()

        self._refresh_header()
        self._update_footer_hint()
        self._update_attachment_preview()
        self._update_controls()

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Escape"), self, activated=self.hide_window)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.clear_chat)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=self.copy_last_response)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.export_chat)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.open_settings_dialog)

    def _position_window(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return

        area = screen.availableGeometry()
        x = area.right() - self.width() - 36
        y = area.top() + max(28, (area.height() - self.height()) // 2)
        self.move(x, y)

    def _play_intro_animation(self):
        self.setWindowOpacity(0.0)
        start_pos = QPoint(self.panel_padding, self.panel_padding + 18)
        end_pos = QPoint(self.panel_padding, self.panel_padding)
        self.main_container.move(start_pos)

        slide = create_property_animation(self.main_container, b"pos", start_pos, end_pos, duration=340)
        fade = create_property_animation(self, b"windowOpacity", 0.0, 1.0, duration=260)
        self._window_animation = create_parallel_animation(fade, slide, parent=self)
        self._window_animation.start()

    def _animate_visibility(self, showing):
        try:
            if self._window_animation is not None:
                self._window_animation.stop()
        except Exception:
            pass

        start_offset = 18 if showing else 0
        end_offset = 0 if showing else 18
        start_opacity = 0.0 if showing else 1.0
        end_opacity = 1.0 if showing else 0.0

        if showing:
            self.show()
            self.setWindowOpacity(start_opacity)
            self.main_container.move(self.panel_padding, self.panel_padding + start_offset)

        fade = create_property_animation(self, b"windowOpacity", start_opacity, end_opacity, duration=220)
        slide = create_property_animation(
            self.main_container,
            b"pos",
            QPoint(self.panel_padding, self.panel_padding + start_offset),
            QPoint(self.panel_padding, self.panel_padding + end_offset),
            duration=240,
        )
        self._window_animation = create_parallel_animation(fade, slide, parent=self)
        if not showing:
            self._window_animation.finished.connect(self.hide)
        else:
            self._window_animation.finished.connect(self._focus_input_when_ready)
        self._window_animation.start()

    def _focus_input_when_ready(self):
        if not self.is_busy and not self.is_warming_up:
            self.input_box.setFocus()

    def _refresh_header(self):
        model = self.runtime_config.model
        self.model_pill.set_theme(
            f"{model.family} {model.parameter_size}",
            COLORS["accent"],
            rgba(COLORS["accent"], 24),
            rgba(COLORS["accent"], 54),
        )
        self.profile_pill.set_theme(
            profile_label(self.settings.profile_id, self.settings.interface_language),
            COLORS["mint"],
            rgba(COLORS["mint"], 24),
            rgba(COLORS["mint"], 50),
        )
        self.hardware_pill.set_theme(
            hardware_label(self.settings.hardware_mode, self.settings.interface_language),
            COLORS["text_main"],
            rgba(COLORS["white"], 14),
            rgba(COLORS["white"], 24),
        )
        self.reply_language_pill.set_theme(
            language_label(self.runtime_config.response_language),
            COLORS["mint"],
            rgba(COLORS["mint"], 14),
            rgba(COLORS["mint"], 38),
        )
        self.context_pill.set_theme(
            f"CTX {max(1, self.runtime_config.n_ctx // 1024)}K",
            COLORS["text_soft"],
            rgba(COLORS["white"], 14),
            rgba(COLORS["white"], 24),
        )

    def _show_boot_messages(self):
        self.add_message(
            "system",
            self._t(
                "app_boot_model",
                name=self.runtime_config.model.name,
                quantization=self.runtime_config.model.quantization,
                size=f"{self.runtime_config.model.approx_size_gb:.1f}",
            ),
        )
        self.add_message(
            "system",
            self._t(
                "app_boot_runtime",
                profile=profile_label(self.settings.profile_id, self.settings.interface_language),
                hardware=hardware_label(self.settings.hardware_mode, self.settings.interface_language),
                language=language_label(self.runtime_config.response_language),
                threads=self.runtime_config.n_threads,
                context=self.runtime_config.n_ctx,
            ),
        )
        if self.runtime_config.model.supports("vision"):
            self.add_message("system", self._t("app_boot_vision"))
        if self.runtime_config.backend_warning:
            self.add_message("system", self.runtime_config.backend_warning)

    def _set_status(self, text, tone):
        palette = {
            "success": (COLORS["success"], rgba(COLORS["success"], 24), rgba(COLORS["success"], 68)),
            "warning": (COLORS["warning"], rgba(COLORS["warning"], 24), rgba(COLORS["warning"], 68)),
            "danger": (COLORS["danger"], rgba(COLORS["danger"], 24), rgba(COLORS["danger"], 68)),
            "accent": (COLORS["accent"], rgba(COLORS["accent"], 24), rgba(COLORS["accent"], 68)),
        }
        foreground, background, border = palette[tone]
        self.status_pill.set_theme(text, foreground, background, border)
        self._status_snapshot = (text, tone)

    def _flash_status(self, text, tone, timeout_ms=1500):
        previous = self._status_snapshot
        self._set_status(text, tone)
        QTimer.singleShot(timeout_ms, lambda: self._set_status(*previous))

    def _update_footer_hint(self):
        hotkey_text = self.runtime_config.hotkey if getattr(self, "hotkey_enabled", True) else self._t(
            "app_hotkey_unavailable"
        )
        self.footer_label.setText(self._t("app_footer", hotkey=hotkey_text))

    def _update_controls(self):
        ready_for_input = not self.is_busy and not self.is_warming_up
        self.input_box.setEnabled(ready_for_input)
        self.btn_send.setEnabled(ready_for_input)
        self.stop_button.setEnabled(self.is_busy)
        self.clear_button.setEnabled(not self.is_busy and not self.is_warming_up and self.search_worker is None)
        self.settings_button.setEnabled(not self.is_busy and not self.is_warming_up and self.search_worker is None)
        self.export_button.setEnabled(bool(self.memory.get_context()[1:]) and not self.is_busy)
        self.copy_button.setEnabled(bool(self._last_response_text()))
        self.attach_file_button.setEnabled(ready_for_input)
        self.attach_image_button.setEnabled(ready_for_input)
        self.attach_desktop_button.setEnabled(ready_for_input)
        self.search_button.setEnabled(ready_for_input and self.search_worker is None)
        self.clear_extras_button.setEnabled(
            ready_for_input and bool(self.pending_file_context or self.pending_image_paths or self.pending_search_context)
        )
        self.background.set_busy(self.is_busy or self.is_warming_up)

        if self.is_warming_up:
            self.input_box.setPlaceholderText(self._t("app_placeholder_loading"))
        elif self.is_busy:
            self.input_box.setPlaceholderText(self._t("app_placeholder_generating"))
        elif not self.model_ready:
            self.input_box.setPlaceholderText(self._t("app_placeholder_lazy"))
        else:
            self.input_box.setPlaceholderText(self._t("app_placeholder_ready"))

    def _scroll_to_bottom(self):
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _insert_message_row(self, row):
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, row)
        row.start_entry_animation()
        QTimer.singleShot(0, self._scroll_to_bottom)
        QTimer.singleShot(160, self._scroll_to_bottom)

    def add_message(self, role, text="", loading=False):
        bubble = MessageBubble(role, self.settings.interface_language)
        bubble.content_changed.connect(self._scroll_to_bottom)
        if loading:
            bubble.set_loading(True)
        elif text:
            bubble.set_text(text)
        row = AnimatedMessageRow(role, bubble)
        self._insert_message_row(row)
        return bubble

    def _clear_message_widgets(self):
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _vision_supported(self):
        return self.runtime_config.model.supports("vision")

    def _update_attachment_preview(self):
        parts = []
        if self.pending_file_label:
            parts.append(self._t("app_attachment_file", name=self.pending_file_label))
        if self.pending_image_paths:
            count = len(self.pending_image_paths)
            parts.append(self._t("app_attachment_image", count=count))
        if self.pending_search_query:
            parts.append(self._t("app_attachment_search", query=self.pending_search_query))
        for label in self.pending_tool_labels:
            if label == "memory":
                parts.append(self._t("app_attachment_memory"))
            elif label == "python":
                parts.append(self._t("app_attachment_python"))

        if parts:
            self.attachment_label.setText(self._t("app_attached", items=" | ".join(parts)))
        else:
            self.attachment_label.setText(self._t("app_attach_hint"))

    def _attachment_display_lines(self):
        lines = []
        if self.pending_file_label:
            lines.append(self._t("app_uploaded", name=self.pending_file_label))
        for path in self.pending_image_paths:
            lines.append(self._t("app_uploaded", name=path.name))
        if self.pending_search_query:
            lines.append(self._t("app_search_context", query=self.pending_search_query))
        return lines

    def _format_user_bubble_text(self, text: str):
        lines = self._attachment_display_lines()
        if not lines:
            return text
        return "\n".join(lines) + "\n\n" + text

    def _should_auto_search(self, text: str):
        if self.pending_search_context:
            return False
        return self.tool_router.should_search(text)

    def clear_pending_extras(self):
        self.pending_file_context = ""
        self.pending_file_label = ""
        self.pending_image_paths = []
        self.pending_search_context = ""
        self.pending_search_query = ""
        self.pending_tool_context = ""
        self.pending_tool_labels = []
        self._update_attachment_preview()
        self._update_controls()

    def attach_file(self):
        path_str, _ = QFileDialog.getOpenFileName(self, self._t("app_file"))
        if not path_str:
            return

        path = Path(path_str)
        if is_document_file(path):
            self.pending_file_context = read_text_file_context(path)
        else:
            file_size_mb = path.stat().st_size / (1024 * 1024)
            self.pending_file_context = (
                f"Attached file metadata:\nName: {path.name}\nPath: {path}\nSize: {file_size_mb:.1f} MB\n"
                "The current assistant can read the file name and metadata, but not the full binary contents."
            )
        self.pending_file_label = path.name
        try:
            if self.memory_store.supports(path):
                self.memory_store.index_path(path)
                self.add_message("system", self._t("app_memory_indexed", name=path.name))
        except Exception as exc:
            self.logger.exception("Failed to index %s into local memory.", path)
            self.add_message("system", self._t("app_memory_index_error", message=exc))
        self._update_attachment_preview()
        self._update_controls()
        self.add_message("system", self._t("app_file_attached", name=path.name))
        self._focus_input_when_ready()

    def attach_image(self):
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            self._t("app_image"),
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not path_str:
            return

        if not self._vision_supported():
            self.add_message("system", self._t("app_need_vision_image"))
            return

        self.pending_image_paths = [Path(path_str)]
        self._update_attachment_preview()
        self._update_controls()
        self.add_message("system", self._t("app_image_attached", name=Path(path_str).name))
        self._focus_input_when_ready()

    def attach_desktop_view(self):
        if not self._vision_supported():
            self.add_message("system", self._t("app_need_vision_desktop"))
            return

        try:
            screenshot_path = capture_desktop_screenshot()
        except Exception as exc:
            self.add_message("system", self._t("app_desktop_capture_failed", message=exc))
            return

        self.pending_image_paths = [screenshot_path]
        self._update_attachment_preview()
        self._update_controls()
        self.add_message("system", self._t("app_desktop_attached"))
        self._focus_input_when_ready()

    def start_web_search(self, query: str | None = None, auto_send_text: str | None = None):
        if self.search_worker is not None:
            return

        query = query or self.input_box.text().strip()
        if not query:
            query, accepted = QInputDialog.getText(self, self._t("app_search"), self._t("app_search"))
            if not accepted or not query.strip():
                return

        self.pending_auto_send_text = auto_send_text
        self.search_worker = WebSearchWorker(query.strip())
        self.search_worker.signal_done.connect(self.on_web_search_done)
        self.search_worker.signal_error.connect(self.on_web_search_error)
        self._set_status(self._t("app_status_searching"), "warning")
        self._update_controls()
        self.search_worker.start()

    def on_web_search_done(self, query: str, formatted_results: str):
        self.pending_search_query = query
        self.pending_search_context = formatted_results
        self.search_worker = None
        self._update_attachment_preview()
        auto_text = self.pending_auto_send_text
        self.pending_auto_send_text = None
        self._set_status(self._t("app_status_search_attached"), "accent")
        self.add_message("system", self._t("app_search_attached_message", query=query))
        self._update_controls()
        if auto_text:
            self._send_prepared_message(auto_text)
            return
        self._focus_input_when_ready()

    def on_web_search_error(self, message: str):
        self.search_worker = None
        auto_text = self.pending_auto_send_text
        self.pending_auto_send_text = None
        if message == "No search results were returned.":
            message = self._t("app_search_no_results")
        self.add_message("system", self._t("app_search_error", message=message))
        self._set_status(self._t("app_status_search_error"), "danger")
        self._update_controls()
        if auto_text:
            self._send_prepared_message(auto_text)
            return
        self._focus_input_when_ready()

    def _build_user_content(self, text: str):
        text_blocks = [text]
        if self.pending_search_context:
            text_blocks.append(self.pending_search_context)
        if self.pending_file_context:
            text_blocks.append(self.pending_file_context)
        if self.pending_tool_context:
            text_blocks.append(self.pending_tool_context)

        combined_text = "\n\n".join(block for block in text_blocks if block).strip()
        if self.pending_image_paths:
            content = [{"type": "text", "text": combined_text or "Please analyze the attached image."}]
            for path in self.pending_image_paths:
                content.append({"type": "image_url", "image_url": {"url": image_file_to_data_url(path)}})
            return content
        return combined_text

    def _default_attachment_prompt(self):
        if self.pending_image_paths and any("desktop_capture_" in path.name for path in self.pending_image_paths):
            return "Please describe what is visible on the desktop and suggest what the user can do next."
        if self.pending_image_paths:
            return "Please analyze the attached image."
        if self.pending_file_context:
            return "Please analyze the attached file."
        if self.pending_search_context:
            return "Please summarize the attached web search results."
        return ""

    def _send_prepared_message(self, text: str):
        self.add_message("user", self._format_user_bubble_text(text))
        self.memory.add_user_message(self._build_user_content(text))
        self.clear_pending_extras()

        self.request_had_error = False
        self.request_was_stopped = False
        self.response_started = False
        self.current_ai_bubble = None
        self.current_response = ""

        if not self.model_ready:
            self.pending_generation = True
            self._set_status(self._t("app_status_loading"), "warning")
            self.start_model_warmup()
            return

        self._start_generation()

    def start_model_warmup(self):
        if self.warmup_worker.isRunning() or self.model_ready:
            return

        self.is_warming_up = True
        self._set_status(self._t("app_status_loading"), "warning")
        self._update_controls()
        self.warmup_worker.start()

    def on_model_ready(self, seconds):
        self.model_ready = True
        self.is_warming_up = False
        self.ai_worker.model_ready = True
        self._set_status(self._t("app_status_ready"), "success")

        if not self._did_show_ready_message:
            self.add_message("system", self._t("app_warmup_finished", seconds=seconds))
            self.add_message("assistant", self._t("app_ready_message"))
            self._did_show_ready_message = True
        elif self.pending_generation:
            self.add_message("system", self._t("app_model_loaded_sending", seconds=seconds))
        else:
            self.add_message("system", self._t("app_warmup_finished", seconds=seconds))

        self._update_controls()
        self._focus_input_when_ready()

        if self.pending_generation:
            self.pending_generation = False
            QTimer.singleShot(40, self._start_generation)

    def on_model_error(self, error):
        self.model_ready = False
        self.is_warming_up = False
        self.pending_generation = False
        self._set_status(self._t("app_status_model_error"), "danger")
        self.add_message("system", self._t("app_model_error", message=error))
        self._update_controls()

    def open_settings_dialog(self):
        if self.is_busy or self.is_warming_up or self.search_worker is not None:
            self.add_message("system", self._t("app_wait_settings"))
            return

        dialog = SetupDialog(self.catalog, self.settings, first_run=False, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_settings = dialog.result_settings()
        if new_settings.to_dict() == self.settings.to_dict():
            return

        self.apply_new_settings(new_settings)

    def apply_new_settings(self, new_settings: UserSettings):
        self.settings = normalize_settings(new_settings, self.catalog)
        save_user_settings(self.settings)
        self.runtime_config = build_runtime_config(self.settings, self.catalog)

        try:
            self.hotkey_mgr.stop()
        except Exception:
            pass

        ModelLoader().reset()
        self.model_ready = False
        self.is_warming_up = False
        self.pending_generation = False
        self.request_had_error = False
        self.request_was_stopped = False
        self.response_started = False
        self.current_ai_bubble = None
        self.current_response = ""
        self._did_show_ready_message = False

        self.memory = ChatMemory(
            system_prompt=self.runtime_config.system_prompt,
            max_history_messages=self.runtime_config.history_messages,
        )
        self._create_workers()
        self._restart_hotkey()
        self._refresh_header()
        self._apply_translations()
        self.clear_pending_extras()
        self._clear_message_widgets()
        self._show_boot_messages()
        self.add_message("system", self._t("app_settings_updated"))

        if self.runtime_config.warmup_on_launch:
            self.start_model_warmup()
        else:
            self._set_status(self._t("app_status_ready"), "accent")
            self._update_controls()

    def clear_chat(self):
        if self.is_busy or self.is_warming_up:
            return

        self._clear_message_widgets()
        self.clear_pending_extras()
        self.memory.clear()
        self.current_ai_bubble = None
        self.current_response = ""
        self.request_had_error = False
        self.request_was_stopped = False
        self.response_started = False
        self.add_message("system", self._t("app_chat_cleared"))
        self._update_controls()

    def _last_response_text(self):
        if self.current_response.strip():
            return self.current_response.strip()
        return self.memory.last_assistant_message() or ""

    def copy_last_response(self):
        text = self._last_response_text()
        if not text:
            return

        QApplication.clipboard().setText(text)
        self._flash_status(self._t("app_status_copied"), "accent")

    def export_chat(self):
        if self.is_busy:
            return

        export_dir = Path("exports")
        export_dir.mkdir(parents=True, exist_ok=True)
        export_path = export_dir / f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        lines = [
            f"# {self._t('app_name')} - {self._t('app_export')}",
            "",
            f"- Model: {self.runtime_config.model.name}",
            f"- {self._t('field_hardware')}: {hardware_label(self.settings.hardware_mode, self.settings.interface_language)}",
            f"- {self._t('field_reply_language')}: {language_label(self.runtime_config.response_language)}",
            "",
        ]

        for message in self.memory.get_context():
            raw_role = str(message.get("role", "user")).lower()
            if raw_role == "system":
                continue
            if raw_role == "assistant":
                role = self._t("caption_ai")
            elif raw_role == "user":
                role = self._t("caption_you")
            else:
                role = raw_role.title()
            content = message.get("content", "")
            if isinstance(content, list):
                rendered = []
                for item in content:
                    if item.get("type") == "text":
                        rendered.append(str(item.get("text", "")).strip())
                    elif item.get("type") == "image_url":
                        rendered.append(f"[{self._t('export_image_attached')}]")
                content = "\n".join(part for part in rendered if part)
            lines.append(f"## {role}")
            lines.append("")
            lines.append(str(content).strip())
            lines.append("")

        export_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        self.add_message("system", self._t("app_export_done", path=export_path))
        self._flash_status(self._t("app_status_exported"), "accent")
        self._update_controls()

    def stop_generation(self):
        if not self.is_busy:
            return

        self.request_was_stopped = True
        self.ai_worker.request_stop()
        self.stop_button.setEnabled(False)
        self._set_status(self._t("app_status_stopping"), "warning")

    def send_message(self):
        text = self.input_box.text().strip()
        if self.is_busy or self.is_warming_up:
            return

        if not text:
            text = self._default_attachment_prompt()
        if not text:
            return

        if self.pending_image_paths and not self._vision_supported():
            self.add_message("system", self._t("app_need_vision_pending"))
            return

        self.input_box.clear()
        tool_preparation = self.tool_router.prepare(text, allow_search=not bool(self.pending_search_context))
        self.pending_tool_context = tool_preparation.prompt_context
        self.pending_tool_labels = [label for label in tool_preparation.labels if label in {"memory", "python"}]
        self._update_attachment_preview()

        if tool_preparation.search_query and self._should_auto_search(text):
            self.start_web_search(query=tool_preparation.search_query, auto_send_text=text)
            return

        self._send_prepared_message(text)

    def _start_generation(self):
        self.is_busy = True
        self._set_status(self._t("app_status_thinking"), "warning")
        self._update_controls()
        self.ai_worker.start()

    def on_ai_start(self):
        self.current_ai_bubble = self.add_message("assistant", loading=True)
        self.current_response = ""
        self.response_started = False

    def on_ai_token(self, token):
        if self.current_ai_bubble is None:
            self.current_ai_bubble = self.add_message("assistant", loading=True)

        self.current_response += token
        self.current_ai_bubble.enqueue_text(token)
        if not self.response_started:
            self._set_status(self._t("app_status_streaming"), "accent")
            self.response_started = True

    def on_ai_stopped(self):
        self.request_was_stopped = True

    def on_ai_done(self):
        self.is_busy = False

        if self.current_ai_bubble is not None:
            self.current_ai_bubble.mark_stream_complete()

        if self.current_response.strip():
            self.memory.add_assistant_message(self.current_response)
        elif self.current_ai_bubble is not None and not self.request_had_error and not self.request_was_stopped:
            fallback = self._t("app_reply_empty")
            self.current_ai_bubble.set_text(fallback)
            self.memory.add_assistant_message(fallback)

        if self.request_was_stopped:
            if self.current_ai_bubble is not None and not self.current_response.strip():
                self.current_ai_bubble.set_text(self._t("app_generation_stopped_inline"))
            self.add_message("system", self._t("app_generation_stopped"))
            self._set_status(self._t("app_status_stopped"), "warning")
        elif self.request_had_error:
            self._set_status(self._t("app_status_reply_error"), "danger")
        else:
            self._set_status(self._t("app_status_ready"), "success")

        self._update_controls()
        self._focus_input_when_ready()

    def on_ai_error(self, err):
        self.request_had_error = True
        self._set_status(self._t("app_status_reply_error"), "danger")

        if self.current_ai_bubble is not None and not self.current_response:
            self.current_ai_bubble.set_text(self._t("app_reply_failed"))

        self.add_message("system", self._t("app_generation_error", message=err))

    def on_hotkey_error(self, message):
        self.hotkey_enabled = False
        self._update_footer_hint()
        self.add_message("system", message)

    def toggle_window(self):
        self.is_visible = not self.is_visible
        self._animate_visibility(self.is_visible)

    def hide_window(self):
        if self.is_visible:
            self.is_visible = False
            self._animate_visibility(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 94:
            self.drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if hasattr(self, "drag_pos"):
            delta = event.globalPosition().toPoint() - self.drag_pos
            self.move(self.pos() + delta)
            self.drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        if hasattr(self, "drag_pos"):
            del self.drag_pos
        super().mouseReleaseEvent(event)

    def _apply_window_mask(self):
        path = QPainterPath()
        path.addRoundedRect(
            0,
            0,
            float(self.width()),
            float(self.height()),
            float(APP_WINDOW_RADIUS),
            float(APP_WINDOW_RADIUS),
        )
        polygon = path.toFillPolygon().toPolygon()
        self.setMask(QRegion(polygon))

    def resizeEvent(self, event):
        self.background.setGeometry(self.rect())
        self.main_container.setGeometry(
            self.panel_padding,
            self.panel_padding,
            self.width() - (self.panel_padding * 2),
            self.height() - (self.panel_padding * 2),
        )
        self._apply_window_mask()
        super().resizeEvent(event)

    def closeEvent(self, event):
        try:
            self.hotkey_mgr.stop()
        except Exception:
            pass
        if self.search_worker is not None and self.search_worker.isRunning():
            self.search_worker.quit()
            self.search_worker.wait(500)
        if self.ai_worker.isRunning():
            self.ai_worker.request_stop()
            self.ai_worker.wait(500)
        super().closeEvent(event)
