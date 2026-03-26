COLORS = {
    "bg_start": "#061018",
    "bg_end": "#0b1f2b",
    "panel": "#122434",
    "panel_alt": "#0e1d2b",
    "surface": "#162a3d",
    "surface_soft": "#1b3348",
    "text_main": "#f5f7fb",
    "text_soft": "#c9d7e5",
    "text_muted": "#8ea4ba",
    "accent": "#64d8ff",
    "accent_alt": "#7b8dff",
    "mint": "#69e6cf",
    "success": "#71dea9",
    "warning": "#ffc06b",
    "danger": "#ff9b9b",
    "white": "#ffffff",
    "user_bubble_start": "#3a93ff",
    "user_bubble_end": "#63d6ff",
}


def rgba(hex_color: str, alpha: int) -> str:
    color = hex_color.lstrip("#")
    if len(color) != 6:
        return hex_color

    red = int(color[0:2], 16)
    green = int(color[2:4], 16)
    blue = int(color[4:6], 16)
    return f"rgba({red}, {green}, {blue}, {alpha})"


def glass_panel_style(radius=26, alpha=156, tone="panel", border_alpha=48) -> str:
    return (
        f"background-color: {rgba(COLORS[tone], alpha)};"
        f"border: 1px solid {rgba(COLORS['white'], border_alpha)};"
        f"border-radius: {radius}px;"
    )


APP_STYLE = f"""
QWidget {{
    color: {COLORS['text_main']};
    font-family: "Segoe UI Variable", "Segoe UI", "Noto Sans TC", "Microsoft JhengHei";
}}
QLabel {{
    background: transparent;
    border: none;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QLineEdit {{
    selection-background-color: {rgba(COLORS['accent'], 120)};
    selection-color: {COLORS['text_main']};
}}
QToolTip {{
    color: {COLORS['text_main']};
    background-color: {rgba(COLORS['panel'], 230)};
    border: 1px solid {rgba(COLORS['white'], 40)};
    padding: 6px 8px;
}}
"""


SCROLLBAR_STYLE = f"""
QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 8px;
    margin: 4px 0px;
}}
QScrollBar::handle:vertical {{
    background: {rgba(COLORS['white'], 72)};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {rgba(COLORS['white'], 110)};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    border: none;
    background: transparent;
    height: 8px;
    margin: 0px 4px;
}}
QScrollBar::handle:horizontal {{
    background: {rgba(COLORS['white'], 72)};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {rgba(COLORS['white'], 110)};
}}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0px;
}}
"""
