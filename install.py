#!/usr/bin/env python3
"""Install claude-pet: copy files into ~/.claude and wire Claude Code hooks.

Usage:  py install.py
Idempotent: re-running updates the files and re-stamps the hooks in place.
"""

import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
DEST = os.path.join(HOME, ".claude")
FILES = ["claude-pet.pyw", "claude_pet_state.py", "claude-notify.ps1"]
MARKERS = ("claude-notify.ps1", "claude-pet.pyw")


def find_pythonw():
    """Prefer pythonw.exe next to this interpreter, then PATH; fall back to python."""
    cand = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if os.path.isfile(cand):
        return cand
    for name in ("pythonw", "pythonw.exe", "pyw"):
        found = shutil.which(name)
        if found:
            return found
    print("  WARNING: pythonw not found; using python (a console window may flash).")
    return sys.executable


def build_hooks(notify, pet, pyw):
    def ps(args):
        return 'powershell -NoProfile -WindowStyle Hidden -File "%s" %s' % (notify, args)

    def cmd(c):
        return {"type": "command", "async": True, "command": c}

    return {
        "SessionStart":     [{"hooks": [cmd(ps("-State idle")), cmd('"%s" "%s"' % (pyw, pet))]}],
        "SessionEnd":       [{"hooks": [cmd(ps("-Action end"))]}],
        "UserPromptSubmit": [{"hooks": [cmd(ps("-State working"))]}],
        "Stop":             [{"hooks": [cmd(ps('-Title "Claude Code" -Message "Done - back to you" '
                                              '-Sound Asterisk -State done -Toast'))]}],
        "Notification":     [{"hooks": [cmd(ps('-Title "Claude Code needs you" -Message "Waiting for your input" '
                                              '-Sound Exclamation -State needs-you -Toast'))]}],
    }


def main():
    try:
        import tkinter  # noqa: F401
    except Exception:
        print("ERROR: this Python has no tkinter. Install the standard python.org build and retry.")
        sys.exit(1)

    os.makedirs(DEST, exist_ok=True)

    print("Installing claude-pet into", DEST)
    for f in FILES:
        src, dst = os.path.join(HERE, f), os.path.join(DEST, f)
        if os.path.abspath(src) != os.path.abspath(dst):
            shutil.copyfile(src, dst)
        print("  copied", f)

    pyw = find_pythonw()
    notify = os.path.join(DEST, "claude-notify.ps1")
    pet = os.path.join(DEST, "claude-pet.pyw")
    hooks = build_hooks(notify, pet, pyw)

    settings_path = os.path.join(DEST, "settings.json")
    settings = {}
    if os.path.isfile(settings_path):
        try:
            with open(settings_path, encoding="utf-8-sig") as f:
                settings = json.load(f) or {}
        except Exception as e:
            print("ERROR: could not parse existing settings.json (%s)." % e)
            print("Fix or move it, then re-run. Nothing was changed.")
            sys.exit(1)

    settings.setdefault("hooks", {})
    for event, entries in hooks.items():
        existing = settings["hooks"].get(event, [])
        cleaned = []
        for entry in existing:
            cmds = " ".join(h.get("command", "") for h in entry.get("hooks", []) if isinstance(h, dict))
            if any(m in cmds for m in MARKERS):
                continue  # drop a previous claude-pet install so re-running is clean
            cleaned.append(entry)
        settings["hooks"][event] = cleaned + entries

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    print("  wired hooks into settings.json")
    print("  pythonw:", pyw)

    try:
        subprocess.Popen([pyw, pet], close_fds=True)
        print("  launched pet")
    except Exception as e:
        print("  (could not auto-launch pet: %s)" % e)

    print("\nDone. Open /hooks in Claude Code once (or restart it) to activate the hooks.")


if __name__ == "__main__":
    main()
