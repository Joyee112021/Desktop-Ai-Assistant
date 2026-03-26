from PySide6.QtGui import QFont


def get_font(size=11, weight=QFont.Weight.Normal, bold=False):
    font = QFont()
    font.setFamilies(
        [
            "Segoe UI Variable Display",
            "Segoe UI Variable Text",
            "Segoe UI",
            "Noto Sans",
            "Arial",
        ]
    )
    font.setPointSize(size)
    font.setWeight(QFont.Weight.Bold if bold else weight)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font
