#!/usr/bin/env python3
"""Remove Agent Pet app files and its owned Startup shortcut."""

import os
import subprocess
from pathlib import Path

from install import APP_FILES, app_dir, powershell_exe, ps_quote, startup_dir


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


def shortcut_target(shortcut):
    script = "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(%s);$s.TargetPath" % ps_quote(shortcut)
    result = subprocess.run(
        [powershell_exe(), "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def shortcut_is_owned(actual_target, expected_target):
    return os.path.normcase(os.path.abspath(actual_target)) == os.path.normcase(os.path.abspath(expected_target))


def main():
    destination = app_dir()
    entrypoint = destination / "agent-pet.pyw"
    shortcut = startup_dir() / "Agent Pet.lnk"
    if shortcut.exists():
        try:
            if shortcut_is_owned(shortcut_target(shortcut), entrypoint):
                shortcut.unlink()
            else:
                print("kept non-Agent-Pet shortcut:", shortcut)
        except (OSError, subprocess.SubprocessError) as error:
            print("could not inspect shortcut (%s); kept it" % error)
    remove_app_files(destination)
    print("Agent Pet app files removed; AgentHub state and settings were kept.")


if __name__ == "__main__":
    main()
