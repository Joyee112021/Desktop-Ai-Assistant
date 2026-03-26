def apply_soft_shadow(widget, radius=36, dx=0, dy=16, alpha=82):
    # QWidget graphics effects are unstable on some Windows/PySide6 setups,
    # especially with translucent frameless windows and frequent repaints.
    # Keep this helper as a no-op so callers can preserve the visual structure
    # without triggering QPainter recursion warnings at runtime.
    return None
