#!/usr/bin/env python3
"""Remove Agent Pet app files and its owned Startup shortcut."""

import os
import subprocess
from pathlib import Path

from install import APP_FILES, SHORTCUT_NAME, app_dir, powershell_exe, ps_quote, startup_dir


def remove_app_files(destination):
    destination = Path(destination)
    for name in APP_FILES:
        path = destination / name
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    try:
        destination.rmdir()
    except OSError:
        pass


def shortcut_details(shortcut):
    script = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(%s);"
        "[Console]::WriteLine($s.TargetPath);[Console]::WriteLine($s.Arguments)"
    ) % ps_quote(shortcut)
    result = subprocess.run(
        [powershell_exe(), "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, check=True,
    )
    lines = result.stdout.splitlines()
    return (lines + ["", ""])[:2]


def shortcut_is_owned(actual_target, actual_arguments, expected_entrypoint):
    launcher = os.path.basename(actual_target).lower()
    if launcher not in ("pythonw.exe", "pythonw", "pyw.exe", "pyw", "python.exe", "python"):
        return False
    argument = actual_arguments.strip()
    if len(argument) >= 2 and argument[0] == argument[-1] == '"':
        argument = argument[1:-1]
    return os.path.normcase(os.path.abspath(argument)) == os.path.normcase(os.path.abspath(expected_entrypoint))


def main():
    destination = app_dir()
    entrypoint = destination / "agent-pet.pyw"
    shortcut = startup_dir() / SHORTCUT_NAME
    if shortcut.exists():
        try:
            target, arguments = shortcut_details(shortcut)
            if shortcut_is_owned(target, arguments, entrypoint):
                shortcut.unlink()
            else:
                print("kept non-Agent-Pet shortcut:", shortcut)
        except (OSError, subprocess.SubprocessError) as error:
            print("could not inspect shortcut (%s); kept it" % error)
    remove_app_files(destination)
    print("Agent Pet app files removed; AgentHub state and settings were kept.")


if __name__ == "__main__":
    main()
