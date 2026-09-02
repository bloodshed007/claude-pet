"""Read and reduce AgentHub's per-session state files.

Both the six-field v2 protocol and legacy three-field records are accepted.
This module has no tkinter or Windows dependencies.
"""

import os
import time
from dataclasses import dataclass, field

TTL_MS = 60 * 60 * 1000        # ignore session files older than this (crash backstop)
DONE_FADE_MS = 6000            # a finished session relaxes back to idle after this long
MIN_WORK_FOR_CHIME_MS = 20000  # shorter runs than this finish silently
MAX_HINT = 80

STATE_DIR_PARTS = (".pi-pet", "sessions")
KNOWN_STATES = ("idle", "working", "done", "needs-you")
_PRIORITY = ("needs-you", "working", "done")
_ORDER = {"needs-you": 0, "working": 1, "done": 2, "idle": 3}

AGENT_GLYPH = {"claude": "c\u00b7", "codex": "x\u00b7", "pi": "\u03c0\u00b7"}


def _now_ms():
    return int(time.time() * 1000)


def state_dir(home=None):
    home = home or os.path.expanduser("~")
    return os.path.join(home, *STATE_DIR_PARTS)


@dataclass
class Session:
    """One live session file, already reduced to what the UI needs."""
    key: str
    state: str          # effective state, after the done -> idle fade
    raw_state: str      # exactly what the writer put in the file
    ts: int
    name: str
    agent: str
    window: str
    hint: str
    display: str = ""
    age_ms: int = 0

    @property
    def glyph(self):
        return AGENT_GLYPH.get(self.agent, AGENT_GLYPH["pi"])

    @property
    def clickable(self):
        return bool(self.window)


@dataclass
class Event:
    """An edge worth alerting on."""
    kind: str           # "done" or "needs-you"
    session: Session
    worked_ms: int = 0


def _clean(s):
    return s.replace("\r", " ").replace("\n", " ").strip()


def parse_line(raw, key=""):
    """Parse one state file body into a field dict. Tolerates old/short lines."""
    parts = raw.split("|")
    state = (parts[0].strip().lower() if parts and parts[0].strip() else "idle")
    if state not in KNOWN_STATES:
        state = "idle"
    ts = 0
    if len(parts) > 1:
        try:
            ts = int(parts[1].strip())
        except ValueError:
            ts = 0

    def fld(i):
        return _clean(parts[i]) if len(parts) > i else ""

    name = fld(2) or "?"
    agent = fld(3).lower() or _agent_from_key(key)
    return {
        "state": state, "ts": ts, "name": name, "agent": agent,
        "window": fld(4), "hint": fld(5)[:MAX_HINT],
    }


def _agent_from_key(key):
    for a in ("claude", "codex"):
        if key.startswith(a + "-"):
            return a
    return "pi"


def _read_files(home, now):
    d = state_dir(home)
    try:
        names = os.listdir(d)
    except OSError:
        return
    for nm in names:
        if not nm.endswith(".txt"):
            continue
        try:
            with open(os.path.join(d, nm), "r", encoding="utf-8-sig", errors="ignore") as f:
                raw = f.read().strip()
        except OSError:
            continue
        key = nm[:-4]
        rec = parse_line(raw, key)
        if rec["ts"] and (now - rec["ts"]) > TTL_MS:
            continue
        yield key, rec


def _assign_display_names(items):
    """Duplicate names get a '#2', '#3' suffix; the oldest session keeps the
    plain name so the labels stay stable as states change."""
    seen = {}
    for s in sorted(items, key=lambda s: (s.ts, s.key)):
        n = seen.get(s.name, 0) + 1
        seen[s.name] = n
        s.display = s.name if n == 1 else "%s #%d" % (s.name, n)


def sessions(home=None, now_ms=None):
    """All live sessions, sorted needs-you > working > done > idle, newest first."""
    home = home or os.path.expanduser("~")
    now = _now_ms() if now_ms is None else now_ms
    out = []
    for key, rec in _read_files(home, now):
        eff = rec["state"]
        if eff == "done" and rec["ts"] and (now - rec["ts"]) > DONE_FADE_MS:
            eff = "idle"
        out.append(Session(
            key=key, state=eff, raw_state=rec["state"], ts=rec["ts"],
            name=rec["name"], agent=rec["agent"], window=rec["window"],
            hint=rec["hint"], age_ms=max(0, now - rec["ts"]) if rec["ts"] else 0,
        ))
    _assign_display_names(out)
    out.sort(key=lambda s: (_ORDER[s.state], -s.ts, s.key))
    return out


def aggregate(home=None, now_ms=None, sess=None):
    """(state, count, names) for the headline cloud: the highest-priority state
    across live sessions, how many are in it, and their display names."""
    sess = sessions(home, now_ms) if sess is None else sess
    buckets = {k: [] for k in KNOWN_STATES}
    for s in sess:
        buckets[s.state].append(s.display or s.name)
    for st in _PRIORITY:
        if buckets[st]:
            return st, len(buckets[st]), sorted(buckets[st])
    return "idle", len(buckets["idle"]), sorted(buckets["idle"])


def latest_activity_ms(home=None, now_ms=None, sess=None):
    """Newest state-write timestamp across live sessions, or 0."""
    sess = sessions(home, now_ms) if sess is None else sess
    return max([s.ts for s in sess if s.ts] or [0])


def format_age(ms):
    """Compact age label: '4s', '3m', '2h'."""
    if ms <= 0:
        return ""
    sec = ms // 1000
    if sec < 60:
        return "%ds" % sec
    if sec < 3600:
        return "%dm" % (sec // 60)
    return "%dh" % (sec // 3600)


@dataclass
class Tracker:
    """Per-session state-edge detector feeding the alerts.

    A 'done' event only fires when that session had been working for at least
    min_work_ms; 'needs-you' fires on every per-session edge into it.
    """
    min_work_ms: int = MIN_WORK_FOR_CHIME_MS
    _prev: dict = field(default_factory=dict)
    _work_start: dict = field(default_factory=dict)
    _primed: bool = False

    def update(self, sess):
        events = []
        seen = set()
        for s in sess:
            seen.add(s.key)
            prev = self._prev.get(s.key)
            self._prev[s.key] = s.raw_state
            if s.raw_state == "working":
                if prev != "working":
                    self._work_start[s.key] = s.ts
                continue
            if prev == s.raw_state:
                continue
            if prev is None and not self._primed:
                continue
            if s.raw_state == "needs-you":
                events.append(Event("needs-you", s))
            elif s.raw_state == "done" and prev is not None:
                start = self._work_start.pop(s.key, 0)
                worked = (s.ts - start) if (start and s.ts) else 0
                if worked >= self.min_work_ms:
                    events.append(Event("done", s, worked))
        for k in [k for k in self._prev if k not in seen]:
            self._prev.pop(k, None)
            self._work_start.pop(k, None)
        self._primed = True
        return events
