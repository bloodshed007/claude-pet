"""Windows sounds/toasts and persisted Agent Pet settings."""

import json
import os
import subprocess

_PS = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                   "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
NO_WINDOW = 0x08000000 | 0x00000008          # CREATE_NO_WINDOW | DETACHED_PROCESS

DEFAULTS = {
    "mute_done": False,
    "mute_needs_you": False,
    "mute_all": False,
    "always_show": False,
    "show_sessions": True,
    "x": None,
    "y": None,
}


def _ps_quote(s):
    return "'" + str(s).replace("'", "''") + "'"


def notify(title, message, sound="Asterisk", toast=False):
    """Fire-and-forget PowerShell sound/toast. Never blocks the tk loop."""
    parts = []
    if sound and sound != "None":
        method = "Exclamation" if sound == "Exclamation" else "Asterisk"
        parts.append("try{[System.Media.SystemSounds]::%s.Play()}catch{}" % method)
    if toast:
        tip = "Warning" if sound == "Exclamation" else "Info"
        parts.append(
            "try{"
            "Add-Type -AssemblyName System.Windows.Forms;"
            "Add-Type -AssemblyName System.Drawing;"
            "$n=New-Object System.Windows.Forms.NotifyIcon;"
            "$n.Icon=[System.Drawing.SystemIcons]::Information;"
            "$n.Visible=$true;"
            "$n.ShowBalloonTip(6000,%s,%s,[System.Windows.Forms.ToolTipIcon]::%s);"
            "Start-Sleep -Milliseconds 900;"
            "$n.Dispose()"
            "}catch{}" % (_ps_quote(title), _ps_quote(message), tip)
        )
    if not parts:
        return
    try:
        subprocess.Popen(
            [_PS, "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
             "-Command", ";".join(parts)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, creationflags=NO_WINDOW,
        )
    except Exception:
        pass                                  # alerts are best-effort


class Settings:
    """Mute flags and last window position, persisted in ~/.pi-pet/pet.json."""

    def __init__(self, home=None):
        home = home or os.path.expanduser("~")
        self.path = os.path.join(home, ".pi-pet", "pet.json")
        self.data = dict(DEFAULTS)
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                for k in DEFAULTS:
                    if k in stored:
                        self.data[k] = stored[k]
        except (OSError, ValueError):
            pass
        return self.data

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=1)
        except OSError:
            pass

    def get(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def alert(self, kind, title, message):
        """Route an alert through the mute settings. kind: done | needs-you."""
        if self.get("mute_all"):
            return
        if kind == "done":
            if not self.get("mute_done"):
                notify(title, message, sound="Asterisk", toast=False)
        elif kind == "needs-you":
            if not self.get("mute_needs_you"):
                notify(title, message, sound="Exclamation", toast=True)
