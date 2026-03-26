from pathlib import Path

from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from config.localization import hardware_label, interface_language_label, language_label, model_copy, profile_label, tr
from config.settings import (
    APP_NAME,
    HARDWARE_MODES,
    INTERFACE_LANGUAGES,
    MODEL_DIR,
    PERFORMANCE_PROFILES,
    RESPONSE_LANGUAGES,
    SETUP_DIALOG_HEIGHT,
    SETUP_DIALOG_WIDTH,
)
from config.user_settings import (
    ModelOption,
    UserSettings,
    backend_model_issue,
    build_runtime_config,
    llama_cpp_version,
    normalize_settings,
)
from gui.components import AuroraBackground, GlassButton
from gui.fonts import get_font
from gui.styles import COLORS, SCROLLBAR_STYLE, glass_panel_style, rgba
from utils.model_download import download_to_path, format_size_gb
from utils.system_info import collect_system_info


DIALOG_MARGIN = 20
DIALOG_SPACING = 14
CARD_PADDING = 16
SETUP_CONTENT_MIN_WIDTH = 760
DETAIL_CONTENT_MIN_WIDTH = 560
MODEL_LIBRARY_CONTENT_MIN_WIDTH = 760


def build_dialog_scroll_area() -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setStyleSheet("background: transparent;")
    scroll.horizontalScrollBar().setStyleSheet(SCROLLBAR_STYLE)
    scroll.verticalScrollBar().setStyleSheet(SCROLLBAR_STYLE)
    return scroll


def build_dialog_card(radius: int = 18, tone: str = "panel_alt", alpha: int = 118) -> QFrame:
    card = QFrame()
    card.setStyleSheet(f"QFrame {{{glass_panel_style(radius=radius, alpha=alpha, tone=tone, border_alpha=0)}}}")
    return card


def build_field_block(label_text: str, widget: QWidget, hint_text: str | None = None) -> QFrame:
    block = build_dialog_card(radius=16, tone="surface_soft", alpha=106)
    layout = QVBoxLayout(block)
    layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
    layout.setSpacing(8)

    label = QLabel(label_text)
    label.setFont(get_font(9, bold=True))
    label.setStyleSheet(f"color: {COLORS['text_main']};")
    layout.addWidget(label)

    if hint_text:
        hint = QLabel(hint_text)
        hint.setWordWrap(True)
        hint.setFont(get_font(9))
        hint.setStyleSheet(f"color: {COLORS['text_muted']};")
        layout.addWidget(hint)

    layout.addWidget(widget)
    return block


class ModelDownloadWorker(QThread):
    signal_progress = Signal(int, str)
    signal_done = Signal(str)
    signal_error = Signal(str)

    def __init__(self, model_option: ModelOption):
        super().__init__()
        self.model_option = model_option

    def run(self):
        try:
            targets = list(self.model_option.download_targets())
            if self.model_option.is_ready():
                existing_path = self.model_option.existing_primary_path() or self.model_option.install_path()
                self.signal_done.emit(str(existing_path))
                return

            total_targets = len(targets)
            for index, filename in enumerate(targets):
                target_path = Path(MODEL_DIR) / filename
                if target_path.exists():
                    percent = int(((index + 1) / total_targets) * 100)
                    self.signal_progress.emit(percent, f"Verified existing file: {filename}")
                    continue

                def on_progress(done: int, total: int, idx=index, current_file=filename):
                    ratio = (done / total) if total > 0 else 0.0
                    percent = int(((idx + ratio) / total_targets) * 100)
                    self.signal_progress.emit(percent, f"Downloading {current_file}")

                download_to_path(
                    self.model_option.download_url(filename),
                    target_path,
                    progress_callback=on_progress,
                )
                percent = int(((index + 1) / total_targets) * 100)
                self.signal_progress.emit(percent, f"Finished {filename}")

            self.signal_done.emit(str(self.model_option.install_path()))
        except Exception as exc:
            self.signal_error.emit(str(exc))


class ModelChoiceCard(QFrame):
    clicked = Signal(str)

    def __init__(self, model_option: ModelOption, language_code: str = "en", parent=None):
        super().__init__(parent)
        self.model_option = model_option
        self.language_code = language_code
        self.setObjectName("ModelCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("selected", False)
        self.setStyleSheet(
            f"""
            QFrame#ModelCard {{
                {glass_panel_style(radius=18, alpha=112, tone='panel_alt', border_alpha=18)}
            }}
            QFrame#ModelCard[selected="true"] {{
                background-color: {rgba(COLORS['surface'], 176)};
                border: 1px solid {rgba(COLORS['accent'], 126)};
                border-radius: 18px;
            }}
            QLabel#MetaText {{
                color: {COLORS['text_muted']};
            }}
            QLabel#BadgeLabel {{
                color: {COLORS['accent']};
                background-color: {rgba(COLORS['accent'], 18)};
                border-radius: 10px;
                padding: 4px 8px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        self.radio = QRadioButton()
        self.radio.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        top_row.addWidget(self.radio, 0, Qt.AlignmentFlag.AlignTop)

        title_column = QVBoxLayout()
        title_row = QHBoxLayout()
        title_label = QLabel(model_option.name)
        title_label.setFont(get_font(11, bold=True))
        title_label.setStyleSheet(f"color: {COLORS['text_main']};")
        title_row.addWidget(title_label)

        badge_label = QLabel(model_copy(model_option.id, "badge", model_option.badge, self.language_code))
        badge_label.setObjectName("BadgeLabel")
        badge_label.setFont(get_font(8, bold=True))
        title_row.addWidget(badge_label)
        title_row.addStretch(1)
        title_column.addLayout(title_row)

        summary_label = QLabel(model_copy(model_option.id, "summary", model_option.summary, self.language_code))
        summary_label.setWordWrap(True)
        summary_label.setFont(get_font(9))
        summary_label.setObjectName("MetaText")
        title_column.addWidget(summary_label)

        meta_label = QLabel(
            f"{model_option.parameter_size} | {model_option.quantization} | {format_size_gb(model_option.approx_size_gb)}"
        )
        meta_label.setFont(get_font(9))
        meta_label.setObjectName("MetaText")
        title_column.addWidget(meta_label)
        top_row.addLayout(title_column, 1)
        layout.addLayout(top_row)

        fit_label = QLabel(model_copy(model_option.id, "recommended_for", model_option.recommended_for, self.language_code))
        fit_label.setWordWrap(True)
        fit_label.setFont(get_font(9))
        fit_label.setStyleSheet(f"color: {rgba(COLORS['white'], 170)};")
        layout.addWidget(fit_label)

        self.install_label = QLabel()
        self.install_label.setWordWrap(True)
        self.install_label.setFont(get_font(9))
        layout.addWidget(self.install_label)
        self.refresh_install_state()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.model_option.id)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self.radio.setChecked(selected)
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def refresh_install_state(self):
        existing_path = self.model_option.existing_primary_path()
        missing = self.model_option.missing_files()
        if existing_path is not None and not missing:
            self.install_label.setText(existing_path.name)
            self.install_label.setStyleSheet(f"color: {COLORS['success']};")
        else:
            self.install_label.setText(", ".join(missing))
            self.install_label.setStyleSheet(f"color: {COLORS['warning']};")


class SectionCard(QFrame):
    clicked = Signal()

    def __init__(self, title: str, description: str, button_text: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{{glass_panel_style(radius=18, alpha=118, tone='panel_alt', border_alpha=0)}}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        self.title_label = QLabel(title)
        self.title_label.setFont(get_font(12, bold=True))
        self.title_label.setStyleSheet(f"color: {COLORS['text_main']};")
        layout.addWidget(self.title_label)

        self.description_label = QLabel(description)
        self.description_label.setWordWrap(True)
        self.description_label.setFont(get_font(9))
        self.description_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        layout.addWidget(self.description_label)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setFont(get_font(9))
        self.summary_label.setStyleSheet(f"color: {rgba(COLORS['white'], 180)};")
        layout.addWidget(self.summary_label)

        row = QHBoxLayout()
        row.addStretch(1)
        self.button = GlassButton(button_text, variant="ghost", compact=True)
        self.button.clicked.connect(self.clicked.emit)
        row.addWidget(self.button)
        layout.addLayout(row)


class GeneralSettingsDialog(QDialog):
    def __init__(self, settings: UserSettings, system_info, parent=None):
        super().__init__(parent)
        self.settings = UserSettings.from_dict(settings.to_dict())
        self.system_info = system_info
        self.setModal(True)
        self.resize(620, 560)
        self.setMinimumSize(460, 420)
        self.setWindowTitle(tr("setup_general_title", self.settings.interface_language))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        scroll = build_dialog_scroll_area()
        root_layout.addWidget(scroll)

        content = QWidget()
        content.setMinimumWidth(DETAIL_CONTENT_MIN_WIDTH)
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(DIALOG_MARGIN, DIALOG_MARGIN, DIALOG_MARGIN, DIALOG_MARGIN)
        layout.setSpacing(DIALOG_SPACING)

        intro_card = build_dialog_card(radius=18, tone="surface", alpha=126)
        intro_layout = QVBoxLayout(intro_card)
        intro_layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        intro_layout.setSpacing(8)

        title = QLabel(tr("setup_general_title", self.settings.interface_language))
        title.setFont(get_font(13, bold=True))
        title.setStyleSheet(f"color: {COLORS['text_main']};")
        intro_layout.addWidget(title)

        subtitle = QLabel(tr("setup_general_subtitle", self.settings.interface_language))
        subtitle.setWordWrap(True)
        subtitle.setFont(get_font(9))
        subtitle.setStyleSheet(f"color: {COLORS['text_muted']};")
        intro_layout.addWidget(subtitle)

        summary = QLabel(
            f"{self.system_info.cpu_name} | RAM {self.system_info.total_memory_gb} GB | "
            f"GPU: {', '.join(gpu.name for gpu in self.system_info.gpus) if self.system_info.gpus else tr('system_no_gpu', self.settings.interface_language)}"
        )
        summary.setWordWrap(True)
        summary.setFont(get_font(9))
        summary.setStyleSheet(f"color: {rgba(COLORS['white'], 170)};")
        intro_layout.addWidget(summary)
        layout.addWidget(intro_card)

        self.profile_combo = self._combo()
        for profile_id, profile in PERFORMANCE_PROFILES.items():
            self.profile_combo.addItem(profile_label(profile_id, self.settings.interface_language), profile_id)

        self.hardware_combo = self._combo()
        for mode_id, mode in HARDWARE_MODES.items():
            suffix = ""
            if mode_id != "cpu" and not any(gpu.vendor == mode_id for gpu in self.system_info.gpus):
                suffix = f" ({tr('setup_not_detected', self.settings.interface_language)})"
            self.hardware_combo.addItem(f"{hardware_label(mode_id, self.settings.interface_language)}{suffix}", mode_id)

        self.interface_language_combo = self._combo()
        for code, label in INTERFACE_LANGUAGES.items():
            self.interface_language_combo.addItem(interface_language_label(code), code)

        self.response_language_combo = self._combo()
        for code, label in RESPONSE_LANGUAGES.items():
            self.response_language_combo.addItem(language_label(code), code)

        self.hotkey_input = QLineEdit()
        self.hotkey_input.setMinimumHeight(42)
        self.hotkey_input.setFont(get_font(10))
        self.hotkey_input.setText(self.settings.hotkey)

        self.profile_combo.setCurrentIndex(max(0, self.profile_combo.findData(self.settings.profile_id)))
        self.hardware_combo.setCurrentIndex(max(0, self.hardware_combo.findData(self.settings.hardware_mode)))
        self.interface_language_combo.setCurrentIndex(
            max(0, self.interface_language_combo.findData(self.settings.interface_language))
        )
        self.response_language_combo.setCurrentIndex(
            max(0, self.response_language_combo.findData(self.settings.response_language))
        )

        layout.addWidget(build_field_block(tr("field_preset", self.settings.interface_language), self.profile_combo))
        layout.addWidget(build_field_block(tr("field_hardware", self.settings.interface_language), self.hardware_combo))
        layout.addWidget(
            build_field_block(
                tr("field_interface_language", self.settings.interface_language),
                self.interface_language_combo,
            )
        )
        layout.addWidget(
            build_field_block(
                tr("field_reply_language", self.settings.interface_language),
                self.response_language_combo,
            )
        )
        layout.addWidget(build_field_block(tr("field_hotkey", self.settings.interface_language), self.hotkey_input))

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch(1)
        cancel = GlassButton(tr("setup_cancel", self.settings.interface_language), variant="ghost", compact=True)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        save = GlassButton(tr("setup_save", self.settings.interface_language), variant="accent", compact=True)
        save.clicked.connect(self.accept)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def _combo(self):
        combo = QComboBox()
        combo.setMinimumHeight(40)
        combo.setMinimumWidth(320)
        combo.setFont(get_font(10))
        return combo

    def updated_settings(self) -> UserSettings:
        self.settings.profile_id = self.profile_combo.currentData()
        self.settings.hardware_mode = self.hardware_combo.currentData()
        self.settings.interface_language = self.interface_language_combo.currentData()
        self.settings.response_language = self.response_language_combo.currentData()
        self.settings.hotkey = self.hotkey_input.text().strip() or self.settings.hotkey
        return self.settings


class TuningDialog(QDialog):
    def __init__(self, settings: UserSettings, parent=None):
        super().__init__(parent)
        self.settings = UserSettings.from_dict(settings.to_dict())
        self.setModal(True)
        self.resize(620, 700)
        self.setMinimumSize(460, 460)
        self.setWindowTitle(tr("setup_tuning_title", self.settings.interface_language))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        scroll = build_dialog_scroll_area()
        root_layout.addWidget(scroll)

        content = QWidget()
        content.setMinimumWidth(DETAIL_CONTENT_MIN_WIDTH)
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(DIALOG_MARGIN, DIALOG_MARGIN, DIALOG_MARGIN, DIALOG_MARGIN)
        layout.setSpacing(DIALOG_SPACING)

        intro_card = build_dialog_card(radius=18, tone="surface", alpha=126)
        intro_layout = QVBoxLayout(intro_card)
        intro_layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        intro_layout.setSpacing(8)

        title = QLabel(tr("setup_tuning_title", self.settings.interface_language))
        title.setFont(get_font(13, bold=True))
        title.setStyleSheet(f"color: {COLORS['text_main']};")
        intro_layout.addWidget(title)

        subtitle = QLabel(tr("setup_tuning_subtitle", self.settings.interface_language))
        subtitle.setWordWrap(True)
        subtitle.setFont(get_font(9))
        subtitle.setStyleSheet(f"color: {COLORS['text_muted']};")
        intro_layout.addWidget(subtitle)

        hint = QLabel(tr("setup_profile_custom_hint", self.settings.interface_language))
        hint.setWordWrap(True)
        hint.setFont(get_font(9))
        hint.setStyleSheet(f"color: {rgba(COLORS['white'], 170)};")
        intro_layout.addWidget(hint)
        layout.addWidget(intro_card)

        self.threads_spin = self._spin(2, 48)
        self.ctx_spin = self._spin(1024, 16384, 512)
        self.batch_spin = self._spin(128, 4096, 128)
        self.max_tokens_spin = self._spin(64, 4096, 64)
        self.history_spin = self._spin(4, 24)
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.1, 1.5)
        self.temperature_spin.setSingleStep(0.05)
        self.temperature_spin.setDecimals(2)
        self.temperature_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.temperature_spin.setMinimumHeight(40)
        self.temperature_spin.setMinimumWidth(320)
        self.temperature_spin.setFont(get_font(11, bold=True))

        fallback = PERFORMANCE_PROFILES.get(self.settings.profile_id, PERFORMANCE_PROFILES["normal"])
        self.threads_spin.setValue(self.settings.n_threads or int(fallback["n_threads"]))
        self.ctx_spin.setValue(self.settings.n_ctx or int(fallback["n_ctx"]))
        self.batch_spin.setValue(self.settings.n_batch or int(fallback["n_batch"]))
        self.max_tokens_spin.setValue(self.settings.max_tokens or int(fallback["max_tokens"]))
        self.history_spin.setValue(self.settings.history_messages)
        self.temperature_spin.setValue(self.settings.temperature)

        layout.addWidget(build_field_block(tr("field_threads", self.settings.interface_language), self.threads_spin))
        layout.addWidget(build_field_block(tr("field_context", self.settings.interface_language), self.ctx_spin))
        layout.addWidget(build_field_block(tr("field_batch", self.settings.interface_language), self.batch_spin))
        layout.addWidget(
            build_field_block(tr("field_max_tokens", self.settings.interface_language), self.max_tokens_spin)
        )
        layout.addWidget(build_field_block(tr("field_history", self.settings.interface_language), self.history_spin))
        layout.addWidget(
            build_field_block(tr("field_temperature", self.settings.interface_language), self.temperature_spin)
        )

        toggles_card = build_dialog_card(radius=16, tone="surface_soft", alpha=106)
        toggles_layout = QVBoxLayout(toggles_card)
        toggles_layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        toggles_layout.setSpacing(10)

        self.use_mmap_checkbox = QCheckBox(tr("field_memory_map", self.settings.interface_language))
        self.use_mmap_checkbox.setChecked(self.settings.use_mmap)
        toggles_layout.addWidget(self.use_mmap_checkbox)

        self.warmup_checkbox = QCheckBox(tr("field_warmup", self.settings.interface_language))
        self.warmup_checkbox.setChecked(self.settings.warmup_on_launch)
        toggles_layout.addWidget(self.warmup_checkbox)
        layout.addWidget(toggles_card)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch(1)
        cancel = GlassButton(tr("setup_cancel", self.settings.interface_language), variant="ghost", compact=True)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        save = GlassButton(tr("setup_save", self.settings.interface_language), variant="accent", compact=True)
        save.clicked.connect(self.accept)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def _spin(self, minimum: int, maximum: int, step: int = 1):
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        spin.setMinimumHeight(40)
        spin.setMinimumWidth(320)
        spin.setFont(get_font(11, bold=True))
        return spin

    def updated_settings(self) -> UserSettings:
        self.settings.profile_id = "custom"
        self.settings.n_threads = self.threads_spin.value()
        self.settings.n_ctx = self.ctx_spin.value()
        self.settings.n_batch = self.batch_spin.value()
        self.settings.max_tokens = self.max_tokens_spin.value()
        self.settings.history_messages = self.history_spin.value()
        self.settings.temperature = self.temperature_spin.value()
        self.settings.use_mmap = self.use_mmap_checkbox.isChecked()
        self.settings.warmup_on_launch = self.warmup_checkbox.isChecked()
        return self.settings


class ModelLibraryDialog(QDialog):
    def __init__(self, catalog: list[ModelOption], settings: UserSettings, system_info, parent=None):
        super().__init__(parent)
        self.catalog = catalog
        self.settings = UserSettings.from_dict(settings.to_dict())
        self.system_info = system_info
        self._download_worker = None

        self.setModal(True)
        self.resize(860, 820)
        self.setMinimumSize(560, 520)
        self.setWindowTitle(tr("setup_model_title", self.settings.interface_language))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        scroll = build_dialog_scroll_area()
        root_layout.addWidget(scroll)

        content = QWidget()
        content.setMinimumWidth(MODEL_LIBRARY_CONTENT_MIN_WIDTH)
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(DIALOG_MARGIN, DIALOG_MARGIN, DIALOG_MARGIN, DIALOG_MARGIN)
        layout.setSpacing(DIALOG_SPACING)

        intro_card = build_dialog_card(radius=18, tone="surface", alpha=126)
        intro_layout = QVBoxLayout(intro_card)
        intro_layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        intro_layout.setSpacing(8)

        title = QLabel(tr("setup_model_title", self.settings.interface_language))
        title.setFont(get_font(13, bold=True))
        title.setStyleSheet(f"color: {COLORS['text_main']};")
        intro_layout.addWidget(title)

        subtitle = QLabel(tr("setup_model_subtitle", self.settings.interface_language))
        subtitle.setWordWrap(True)
        subtitle.setFont(get_font(9))
        subtitle.setStyleSheet(f"color: {COLORS['text_muted']};")
        intro_layout.addWidget(subtitle)
        layout.addWidget(intro_card)

        self.model_scroll = QScrollArea()
        self.model_scroll.setWidgetResizable(True)
        self.model_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.model_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.model_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.model_scroll.horizontalScrollBar().setStyleSheet(SCROLLBAR_STYLE)
        self.model_scroll.verticalScrollBar().setStyleSheet(SCROLLBAR_STYLE)
        self.model_list_container = QWidget()
        self.model_list_container.setMinimumWidth(MODEL_LIBRARY_CONTENT_MIN_WIDTH - (DIALOG_MARGIN * 2) - 16)
        self.model_list_layout = QVBoxLayout(self.model_list_container)
        self.model_list_layout.setContentsMargins(0, 0, 0, 0)
        self.model_list_layout.setSpacing(10)
        self.model_list_layout.addStretch(1)
        self.model_scroll.setWidget(self.model_list_container)
        layout.addWidget(self.model_scroll, 1)

        self.selected_model_hint = QLabel()
        self.selected_model_hint.setWordWrap(True)
        self.selected_model_hint.setFont(get_font(9))
        layout.addWidget(self.selected_model_hint)

        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setFont(get_font(9))
        layout.addWidget(self.warning_label)

        self.download_progress = QProgressBar()
        self.download_progress.setVisible(False)
        layout.addWidget(self.download_progress)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setFont(get_font(9))
        layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        self.open_models_button = GlassButton(
            tr("button_open_models", self.settings.interface_language), variant="ghost", compact=True
        )
        self.open_models_button.clicked.connect(self._open_models_folder)
        buttons.addWidget(self.open_models_button)

        self.download_button = GlassButton(
            tr("button_download_model", self.settings.interface_language), variant="ghost", compact=True
        )
        self.download_button.clicked.connect(self._download_selected_model)
        buttons.addWidget(self.download_button)
        buttons.addStretch(1)

        cancel = GlassButton(tr("setup_cancel", self.settings.interface_language), variant="ghost", compact=True)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)

        save = GlassButton(tr("setup_save", self.settings.interface_language), variant="accent", compact=True)
        save.clicked.connect(self.accept)
        buttons.addWidget(save)
        layout.addLayout(buttons)

        self._populate_models()
        self._select_model(self.settings.selected_model_id)

    def _populate_models(self):
        self.model_button_group = QButtonGroup(self)
        self.model_button_group.setExclusive(True)
        self.model_cards = {}
        while self.model_list_layout.count() > 1:
            item = self.model_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for index, option in enumerate(self.catalog):
            card = ModelChoiceCard(option, self.settings.interface_language)
            card.clicked.connect(self._select_model)
            self.model_list_layout.insertWidget(index, card)
            self.model_button_group.addButton(card.radio)
            self.model_cards[option.id] = card

    def _selected_model(self) -> ModelOption | None:
        for option in self.catalog:
            if option.id == self.settings.selected_model_id:
                return option
        return None

    def _localized_backend_issue(self, model: ModelOption | None) -> str | None:
        if model is None:
            return None
        issue = backend_model_issue(model)
        if issue is None:
            return None
        if model.id == "mistral-nemo-12b-q4km":
            if self.settings.interface_language == "zh-TW":
                return "目前專案內安裝的 llama-cpp-python 後端暫時無法載入 Mistral Nemo 12B。"
            if self.settings.interface_language == "zh-CN":
                return "当前项目内安装的 llama-cpp-python 后端暂时无法加载 Mistral Nemo 12B。"
        return issue

    def _select_model(self, model_id: str):
        self.settings.selected_model_id = model_id
        for option_id, card in self.model_cards.items():
            card.set_selected(option_id == model_id)
            card.refresh_install_state()

        model = self._selected_model()
        if model is None:
            return
        capabilities = ", ".join(cap.title() for cap in model.capabilities)
        self.selected_model_hint.setText(
            tr(
                "model_selected_hint",
                self.settings.interface_language,
                name=model.name,
                size=format_size_gb(model.approx_size_gb),
                ram=model.minimum_ram_gb,
                capabilities=capabilities,
            )
        )
        issue = self._localized_backend_issue(model)
        if issue:
            self.warning_label.setText(issue)
            self.warning_label.setStyleSheet(f"color: {COLORS['danger']};")
        elif self.settings.hardware_mode in {"cpu", "intel"} and self.system_info.total_memory_gb < model.minimum_ram_gb:
            self.warning_label.setText(
                tr(
                    "setup_ram_warning",
                    self.settings.interface_language,
                    name=model.name,
                    ram=model.minimum_ram_gb,
                    hardware=hardware_label(self.settings.hardware_mode, self.settings.interface_language),
                )
            )
            self.warning_label.setStyleSheet(f"color: {COLORS['warning']};")
        else:
            self.warning_label.setText("")
        self._update_save_state()

    def _update_save_state(self):
        model = self._selected_model()
        can_save = bool(model and model.is_ready() and self._localized_backend_issue(model) is None)
        self.download_button.setEnabled(model is not None and self._download_worker is None)
        self.status_label.setStyleSheet(
            f"color: {COLORS['success'] if can_save else COLORS['warning']};"
        )
        if model is None:
            self.status_label.setText(tr("setup_no_model", self.settings.interface_language))
        elif can_save:
            self.status_label.setText(tr("setup_ready", self.settings.interface_language))
        else:
            self.status_label.setText(tr("setup_need_model", self.settings.interface_language))

    def _download_selected_model(self):
        model = self._selected_model()
        if model is None:
            return
        if self._download_worker is not None and self._download_worker.isRunning():
            return
        if model.is_ready():
            self.status_label.setText(tr("setup_download_existing", self.settings.interface_language, name=model.name))
            return

        self.download_progress.setVisible(True)
        self.download_progress.setRange(0, 100)
        self.download_progress.setValue(0)
        self.status_label.setText(
            tr("setup_download_status", self.settings.interface_language, name=model.name, folder=Path(MODEL_DIR).name)
        )
        self._download_worker = ModelDownloadWorker(model)
        self._download_worker.signal_progress.connect(self._on_download_progress)
        self._download_worker.signal_done.connect(self._on_download_done)
        self._download_worker.signal_error.connect(self._on_download_error)
        self._download_worker.start()

    def _on_download_progress(self, percent: int, status_text: str):
        self.download_progress.setVisible(True)
        self.download_progress.setValue(percent)
        self.download_progress.setFormat(f"{percent}%")
        if status_text.startswith("Verified existing file: "):
            name = status_text.removeprefix("Verified existing file: ")
            status_text = tr("download_progress_verified", self.settings.interface_language, name=name)
        elif status_text.startswith("Downloading "):
            name = status_text.removeprefix("Downloading ")
            status_text = tr("download_progress_downloading", self.settings.interface_language, name=name)
        elif status_text.startswith("Finished "):
            name = status_text.removeprefix("Finished ")
            status_text = tr("download_progress_finished", self.settings.interface_language, name=name)
        self.status_label.setText(status_text)

    def _on_download_done(self, saved_path: str):
        self.download_progress.setVisible(False)
        self._download_worker = None
        for card in self.model_cards.values():
            card.refresh_install_state()
        self.status_label.setText(
            tr("setup_download_done", self.settings.interface_language, name=Path(saved_path).name)
        )
        self._update_save_state()

    def _on_download_error(self, message: str):
        self.download_progress.setVisible(False)
        self._download_worker = None
        self.status_label.setText(tr("setup_download_fail", self.settings.interface_language, message=message))
        self.status_label.setStyleSheet(f"color: {COLORS['danger']};")
        self._update_save_state()

    def _open_models_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(MODEL_DIR))))

    def updated_settings(self) -> UserSettings:
        return self.settings


class SetupDialog(QDialog):
    def __init__(self, catalog: list[ModelOption], settings: UserSettings, first_run=False, parent=None):
        super().__init__(parent)
        self.catalog = catalog
        self.first_run = first_run
        self.settings = normalize_settings(UserSettings.from_dict(settings.to_dict()), catalog)
        self.system_info = collect_system_info()
        self.saved_settings = None

        self.setWindowTitle(APP_NAME)
        self.setModal(True)
        self.resize(860, 920)
        self.setMinimumSize(560, 560)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.background = AuroraBackground(self)
        self.main_container = QFrame(self)
        self.main_container.setObjectName("SetupMainContainer")
        self.main_container.setStyleSheet(
            f"QFrame#SetupMainContainer {{{glass_panel_style(radius=28, alpha=120, tone='panel', border_alpha=0)}}}"
        )

        self._build_ui()
        self._apply_translations()
        self._refresh_summary()

    def _t(self, key: str, **kwargs) -> str:
        return tr(key, self.settings.interface_language, **kwargs)

    def _build_ui(self):
        outer_layout = QVBoxLayout(self.main_container)
        outer_layout.setContentsMargins(16, 16, 16, 16)
        outer_layout.setSpacing(0)

        scroll = build_dialog_scroll_area()
        outer_layout.addWidget(scroll)

        content = QWidget()
        content.setMinimumWidth(SETUP_CONTENT_MIN_WIDTH)
        scroll.setWidget(content)

        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(22, 22, 22, 22)
        content_layout.setSpacing(16)

        hero = QFrame()
        hero.setStyleSheet(f"QFrame {{{glass_panel_style(radius=20, alpha=136, tone='surface', border_alpha=0)}}}")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 18, 18, 18)
        hero_layout.setSpacing(8)

        self.title_label = QLabel()
        self.title_label.setFont(get_font(18, bold=True))
        self.title_label.setStyleSheet(f"color: {COLORS['text_main']};")
        hero_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel()
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setFont(get_font(10))
        self.subtitle_label.setStyleSheet(f"color: {COLORS['text_soft']};")
        hero_layout.addWidget(self.subtitle_label)

        self.edition_label = QLabel(self._t("setup_edition_line", version=llama_cpp_version()))
        self.edition_label.setFont(get_font(9))
        self.edition_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        hero_layout.addWidget(self.edition_label)

        self.system_summary_label = QLabel()
        self.system_summary_label.setWordWrap(True)
        self.system_summary_label.setFont(get_font(9))
        self.system_summary_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        hero_layout.addWidget(self.system_summary_label)
        content_layout.addWidget(hero)

        self.general_card = SectionCard("", "", "")
        self.general_card.clicked.connect(self.open_general_dialog)
        content_layout.addWidget(self.general_card)

        self.tuning_card = SectionCard("", "", "")
        self.tuning_card.clicked.connect(self.open_tuning_dialog)
        content_layout.addWidget(self.tuning_card)

        self.model_card = SectionCard("", "", "")
        self.model_card.clicked.connect(self.open_model_dialog)
        content_layout.addWidget(self.model_card)

        preview_card = QFrame()
        preview_card.setStyleSheet(
            f"QFrame {{{glass_panel_style(radius=18, alpha=116, tone='surface_soft', border_alpha=0)}}}"
        )
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(18, 18, 18, 18)
        preview_layout.setSpacing(10)

        self.preview_title = QLabel()
        self.preview_title.setFont(get_font(12, bold=True))
        self.preview_title.setStyleSheet(f"color: {COLORS['text_main']};")
        preview_layout.addWidget(self.preview_title)

        self.runtime_preview_label = QLabel()
        self.runtime_preview_label.setWordWrap(True)
        self.runtime_preview_label.setFont(get_font(9))
        self.runtime_preview_label.setStyleSheet(f"color: {rgba(COLORS['white'], 180)};")
        preview_layout.addWidget(self.runtime_preview_label)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setFont(get_font(9))
        preview_layout.addWidget(self.status_label)
        content_layout.addWidget(preview_card)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch(1)

        self.cancel_button = GlassButton("", variant="ghost", compact=True)
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)

        self.save_button = GlassButton("", variant="accent")
        self.save_button.clicked.connect(self._save_and_accept)
        buttons.addWidget(self.save_button)
        content_layout.addLayout(buttons)

    def _apply_translations(self):
        self.setWindowTitle(self._t("setup_title"))
        self.title_label.setText(self._t("setup_title"))
        self.subtitle_label.setText(self._t("setup_subtitle"))

        self.general_card.title_label.setText(self._t("setup_general"))
        self.general_card.description_label.setText(self._t("setup_general_desc"))
        self.general_card.button.setText(self._t("setup_open"))
        self.general_card.button._apply_style()

        self.tuning_card.title_label.setText(self._t("setup_tuning"))
        self.tuning_card.description_label.setText(self._t("setup_tuning_desc"))
        self.tuning_card.button.setText(self._t("setup_open"))
        self.tuning_card.button._apply_style()

        self.model_card.title_label.setText(self._t("setup_models"))
        self.model_card.description_label.setText(self._t("setup_models_desc"))
        self.model_card.button.setText(self._t("setup_open"))
        self.model_card.button._apply_style()

        self.preview_title.setText(self._t("setup_preview"))
        self.cancel_button.setText(self._t("setup_cancel"))
        self.cancel_button._apply_style()
        self.save_button.setText(self._t("setup_save"))
        self.save_button._apply_style()

    def _selected_model(self) -> ModelOption | None:
        for option in self.catalog:
            if option.id == self.settings.selected_model_id:
                return option
        return None

    def _localized_backend_issue(self, model: ModelOption | None) -> str | None:
        if model is None:
            return None
        issue = backend_model_issue(model)
        if issue is None:
            return None
        if model.id == "mistral-nemo-12b-q4km":
            if self.settings.interface_language == "zh-TW":
                return "目前專案內安裝的 llama-cpp-python 後端暫時無法載入 Mistral Nemo 12B。"
            if self.settings.interface_language == "zh-CN":
                return "当前项目内安装的 llama-cpp-python 后端暂时无法加载 Mistral Nemo 12B。"
        return issue

    def _refresh_summary(self):
        self.system_summary_label.setText(
            f"{self._t('setup_system')}: {self.system_info.cpu_name} | RAM {self.system_info.total_memory_gb} GB | "
            f"GPU: {self._gpu_summary()} | UI {interface_language_label(self.settings.interface_language)} | "
            f"AI {language_label(self.settings.response_language)}"
        )

        self.general_card.summary_label.setText(
            self._t(
                "setup_summary_general",
                profile=profile_label(self.settings.profile_id, self.settings.interface_language),
                hardware=hardware_label(self.settings.hardware_mode, self.settings.interface_language),
                ui_language=interface_language_label(self.settings.interface_language),
                reply_language=language_label(self.settings.response_language),
                hotkey=self.settings.hotkey,
            )
        )
        self.tuning_card.summary_label.setText(
            self._t(
                "setup_summary_tuning",
                threads=self.settings.n_threads or PERFORMANCE_PROFILES[self.settings.profile_id]["n_threads"],
                context=self.settings.n_ctx or PERFORMANCE_PROFILES[self.settings.profile_id]["n_ctx"],
                batch=self.settings.n_batch or PERFORMANCE_PROFILES[self.settings.profile_id]["n_batch"],
                tokens=self.settings.max_tokens or PERFORMANCE_PROFILES[self.settings.profile_id]["max_tokens"],
            )
        )

        model = self._selected_model()
        if model is None:
            self.model_card.summary_label.setText(self._t("setup_no_model"))
        else:
            self.model_card.summary_label.setText(
                self._t("setup_summary_model", name=model.name, size=format_size_gb(model.approx_size_gb))
            )

        runtime = build_runtime_config(self.settings, self.catalog, self.system_info)
        self.runtime_preview_label.setText(
            self._t(
                "setup_runtime_preview",
                profile=profile_label(self.settings.profile_id, self.settings.interface_language),
                hardware=hardware_label(self.settings.hardware_mode, self.settings.interface_language),
                language=language_label(runtime.response_language),
                threads=runtime.n_threads,
                context=runtime.n_ctx,
                batch=runtime.n_batch,
                tokens=runtime.max_tokens,
            )
        )

        self._update_save_state()

    def _update_save_state(self):
        model = self._selected_model()
        can_save = bool(model and model.is_ready() and self._localized_backend_issue(model) is None)
        if model is not None and self.settings.hardware_mode in {"cpu", "intel"}:
            can_save = can_save and self.system_info.total_memory_gb >= model.minimum_ram_gb
        self.save_button.setEnabled(can_save)

        if model is None:
            self.status_label.setText(self._t("setup_no_model"))
            self.status_label.setStyleSheet(f"color: {COLORS['warning']};")
            return
        if not model.is_ready():
            self.status_label.setText(self._t("setup_need_model"))
            self.status_label.setStyleSheet(f"color: {COLORS['warning']};")
            return
        issue = self._localized_backend_issue(model)
        if issue:
            self.status_label.setText(issue)
            self.status_label.setStyleSheet(f"color: {COLORS['danger']};")
            return
        if self.settings.hardware_mode in {"cpu", "intel"} and self.system_info.total_memory_gb < model.minimum_ram_gb:
            self.status_label.setText(
                self._t(
                    "setup_ram_warning",
                    name=model.name,
                    ram=model.minimum_ram_gb,
                    hardware=hardware_label(self.settings.hardware_mode, self.settings.interface_language),
                )
            )
            self.status_label.setStyleSheet(f"color: {COLORS['warning']};")
            return
        self.status_label.setText(self._t("setup_ready"))
        self.status_label.setStyleSheet(f"color: {COLORS['success']};")

    def open_general_dialog(self):
        dialog = GeneralSettingsDialog(self.settings, self.system_info, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.settings = normalize_settings(dialog.updated_settings(), self.catalog)
        self._apply_translations()
        self._refresh_summary()

    def open_tuning_dialog(self):
        dialog = TuningDialog(self.settings, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.updated_settings()
        updated.interface_language = self.settings.interface_language
        updated.response_language = self.settings.response_language
        updated.hardware_mode = self.settings.hardware_mode
        updated.selected_model_id = self.settings.selected_model_id
        updated.hotkey = self.settings.hotkey
        self.settings = normalize_settings(updated, self.catalog)
        self._refresh_summary()

    def open_model_dialog(self):
        dialog = ModelLibraryDialog(self.catalog, self.settings, self.system_info, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.updated_settings()
        updated.interface_language = self.settings.interface_language
        updated.response_language = self.settings.response_language
        updated.hardware_mode = self.settings.hardware_mode
        updated.profile_id = self.settings.profile_id
        updated.hotkey = self.settings.hotkey
        updated.n_threads = self.settings.n_threads
        updated.n_ctx = self.settings.n_ctx
        updated.n_batch = self.settings.n_batch
        updated.max_tokens = self.settings.max_tokens
        updated.history_messages = self.settings.history_messages
        updated.temperature = self.settings.temperature
        updated.use_mmap = self.settings.use_mmap
        updated.warmup_on_launch = self.settings.warmup_on_launch
        self.settings = normalize_settings(updated, self.catalog)
        self._refresh_summary()

    def _save_and_accept(self):
        self.saved_settings = normalize_settings(self.settings, self.catalog)
        if not self.save_button.isEnabled():
            self._update_save_state()
            return
        self.accept()

    def result_settings(self) -> UserSettings:
        return self.saved_settings or self.settings

    def _gpu_summary(self) -> str:
        if not self.system_info.gpus:
            return self._t("system_no_gpu")
        return ", ".join(gpu.name for gpu in self.system_info.gpus)

    def resizeEvent(self, event):
        self.background.setGeometry(self.rect())
        self.main_container.setGeometry(10, 10, self.width() - 20, self.height() - 20)
        super().resizeEvent(event)
