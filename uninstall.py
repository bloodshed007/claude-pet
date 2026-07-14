#!/usr/bin/env python3
"""Uninstall claude-pet: remove its hooks from settings.json and delete the copied files.

Usage:  py uninstall.py
Leaves the rest of your settings.json untouched. Right-click the pet -> Quit
(or it will be gone next restart).
"""

import json
import os

HOME = os.path.expanduser("~")
DEST = os.path.join(HOME, ".claude")
FILES = ["claude-pet.pyw", "claude_pet_state.py", "claude-notify.ps1"]
EVENTS = ("SessionStart", "SessionEnd", "UserPromptSubmit", "Stop", "Notification")
MARKERS = ("claude-notify.ps1", "claude-pet.pyw")


def main():
    settings_path = os.path.join(DEST, "settings.json")
    if os.path.isfile(settings_path):
        try:
            with open(settings_path, encoding="utf-8-sig") as f:
                settings = json.load(f) or {}
        except Exception as e:
            print("Could not parse settings.json (%s); leaving it alone." % e)
            settings = None

        if settings is not None:
            hooks = settings.get("hooks", {})
            for event in EVENTS:
                entries = hooks.get(event)
                if not entries:
                    continue
                kept = []
                for entry in entries:
                    cmds = " ".join(h.get("command", "") for h in entry.get("hooks", []) if isinstance(h, dict))
                    if any(m in cmds for m in MARKERS):
                        continue
                    kept.append(entry)
                if kept:
                    hooks[event] = kept
                else:
                    hooks.pop(event, None)
            if not hooks:
                settings.pop("hooks", None)
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
                f.write("\n")
            print("removed claude-pet hooks from settings.json")

    for f in FILES:
        p = os.path.join(DEST, f)
        try:
            os.remove(p)
            print("deleted", f)
        except FileNotFoundError:
            pass
        except OSError as e:
            print("could not delete %s (%s) - pet may be running; right-click it -> Quit first" % (f, e))

    print("\nDone. Right-click the pet -> Quit (or it'll be gone next restart).")
    print("(~/.claude/pet-sessions/ is left in place; it's harmless and empty when idle.)")


if __name__ == "__main__":
    main()
