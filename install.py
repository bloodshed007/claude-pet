#!/usr/bin/env python3
"""Install Agent Pet as a Windows desktop application."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_FILES = (
    "agent-pet.pyw", "agent_pet_state.py", "agent_pet_render.py",
    "agent_pet_layered.py", "agent_pet_notify.py", "agent_pet_hub.py",
)
SHORTCUT_NAME = "Agent Pet.lnk"
NO_WINDOW = 0x08000000
HERE = Path(__file__).resolve().parent


def app_dir(home=None):
    return Path(home or Path.home()) / ".agent-pet"


def startup_dir(appdata=None):
    root = Path(appdata or os.environ["APPDATA"])
    return root / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def powershell_exe():
    root = os.environ.get("SystemRoot")
    if root:
        candidate = Path(root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if candidate.is_file():
            return str(candidate)
    return "powershell.exe"


def find_pythonw():
    candidate = Path(sys.executable).with_name("pythonw.exe")
    if candidate.is_file():
        return candidate
    for name in ("pythonw.exe", "pythonw", "pyw"):
        found = shutil.which(name)
        if found:
            return Path(found)
    print("WARNING: pythonw was not found; a console window may flash.")
    return Path(sys.executable)


def validate_dependencies():
    try:
        import tkinter  # noqa: F401
    except Exception as error:
        raise RuntimeError("tkinter is required; use the standard Windows Python installer") from error
    try:
        import PIL  # noqa: F401
    except Exception as error:
        raise RuntimeError("Pillow is required; run: py -m pip install Pillow") from error


def install_files(source, destination):
    source, destination = Path(source), Path(destination)
    missing = [name for name in APP_FILES if not (source / name).is_file()]
    if missing:
        raise FileNotFoundError("missing runtime files: " + ", ".join(missing))
    destination.mkdir(parents=True, exist_ok=True)
    for name in APP_FILES:
        shutil.copy2(source / name, destination / name)


def shortcut_create_command(shortcut, pythonw, entrypoint):
    shortcut, pythonw, entrypoint = map(Path, (shortcut, pythonw, entrypoint))
    script = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(%s);"
        "$s.TargetPath=%s;$s.Arguments=%s;$s.WorkingDirectory=%s;$s.Save()"
    ) % (
        ps_quote(shortcut), ps_quote(pythonw),
        ps_quote('"%s"' % entrypoint), ps_quote(entrypoint.parent),
    )
    return [powershell_exe(), "-NoProfile", "-NonInteractive", "-Command", script]


def main():
    if os.name != "nt":
        print("ERROR: Agent Pet desktop installation requires Windows.")
        return 1
    try:
        validate_dependencies()
        destination = app_dir()
        install_files(HERE, destination)
        pythonw = find_pythonw()
        entrypoint = destination / "agent-pet.pyw"
        shortcut = startup_dir() / SHORTCUT_NAME
        shortcut.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(shortcut_create_command(shortcut, pythonw, entrypoint), check=True,
                       creationflags=NO_WINDOW)
        subprocess.Popen([str(pythonw), str(entrypoint)], close_fds=True,
                         creationflags=NO_WINDOW)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print("ERROR:", error)
        return 1
    print("installed Agent Pet into", destination)
    print("created Startup shortcut", shortcut)
    return 0


if __name__ == "__main__":
    sys.exit(main())
