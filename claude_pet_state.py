"""Aggregate per-session pet state written by Claude Code hooks.

Each Claude Code session writes  ~/.claude/pet-sessions/<session_id>.txt  with
contents  "<state>|<unix_millis>". This module reads them all and reduces to a
single (state, count) the pet can display.

Kept tkinter-free so it can be unit-tested on its own.
"""

import os
import time

TTL_MS = 60 * 60 * 1000    # ignore session files older than this (hard-crash backstop)
DONE_FADE_MS = 6000        # a finished session relaxes back to idle after this long
_PRIORITY = ("needs-you", "working", "done")   # highest -> lowest; idle is the fallback


def _now_ms():
    return int(time.time() * 1000)


def aggregate(home=None, now_ms=None):
    """Return (state, count): the highest-priority state across live sessions and
    how many sessions are in it. Empty/unreadable -> ('idle', 0)."""
    home = home or os.path.expanduser("~")
    now = _now_ms() if now_ms is None else now_ms
    d = os.path.join(home, ".claude", "pet-sessions")

    counts = {"needs-you": 0, "working": 0, "done": 0, "idle": 0}
    try:
        names = os.listdir(d)
    except OSError:
        names = []

    for nm in names:
        if not nm.endswith(".txt"):
            continue
        try:
            with open(os.path.join(d, nm), "r", encoding="utf-8-sig", errors="ignore") as f:
                raw = f.read().strip()
        except OSError:
            continue

        parts = raw.split("|")
        st = (parts[0] if parts and parts[0] else "idle").lower()
        ts = 0
        if len(parts) > 1:
            try:
                ts = int(parts[1])
            except ValueError:
                ts = 0
        if st not in counts:
            st = "idle"

        if ts and (now - ts) > TTL_MS:      # crash backstop: drop very old files
            continue
        if st == "done" and ts and (now - ts) > DONE_FADE_MS:
            st = "idle"                      # celebration over -> back to calm
        counts[st] += 1

    for st in _PRIORITY:
        if counts[st] > 0:
            return st, counts[st]
    return "idle", counts["idle"]
