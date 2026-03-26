from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation


def create_property_animation(
    target,
    prop,
    start,
    end,
    duration=320,
    curve=QEasingCurve.Type.OutCubic,
):
    animation = QPropertyAnimation(target, prop)
    animation.setDuration(duration)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setEasingCurve(curve)
    return animation


def create_parallel_animation(*animations, parent=None):
    group = QParallelAnimationGroup(parent)
    for animation in animations:
        group.addAnimation(animation)
    return group
