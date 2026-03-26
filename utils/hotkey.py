from PySide6.QtCore import QObject, Signal

try:
    import keyboard
except Exception:
    keyboard = None


class HotkeyManager(QObject):
    toggle_signal = Signal()
    error_signal = Signal(str)

    def __init__(self, hotkey):
        super().__init__()
        self.hotkey = hotkey
        self._hotkey_handle = None

    def start(self):
        if keyboard is None:
            self.error_signal.emit(
                "Global hotkeys are unavailable because the 'keyboard' package could not be loaded."
            )
            return False

        try:
            self._hotkey_handle = keyboard.add_hotkey(self.hotkey, self._on_trigger)
            return True
        except Exception as exc:
            self.error_signal.emit(f"Could not register the global hotkey '{self.hotkey}': {exc}")
            return False

    def stop(self):
        if keyboard is None or self._hotkey_handle is None:
            return

        try:
            keyboard.remove_hotkey(self._hotkey_handle)
        except Exception:
            pass
        finally:
            self._hotkey_handle = None

    def _on_trigger(self):
        self.toggle_signal.emit()
