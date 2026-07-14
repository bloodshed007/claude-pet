"""
claude-pet.pyw  --  a tiny always-on-top desktop companion for Claude Code.

It aggregates the state of every active Claude Code session (each writes
%USERPROFILE%\\.claude\\pet-sessions\\<session_id>.txt via hooks) and shows one
little floating ROBOT, with a thought-CLOUD above its head showing the status:

    idle       calm eyes, gentle bob, occasional blink      (blue)
    working    eyes darting side to side, quicker bob        (cyan)   x2, x3...
    done       happy arc-eyes                                (green)  -> fades to idle
    needs-you  wide eyes + a little shake (wins over working) (amber)

Priority when sessions disagree: needs-you > working > done > idle.

Launch (no console window):  pythonw claude-pet.pyw
Single instance only (socket lock on 127.0.0.1:49731). Drag it anywhere.
Right-click for a menu. To restart after an update, kill the process owning
port 49731, then relaunch.
"""

import os
import sys
import math
import socket
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from claude_pet_state import aggregate

# ---------------------------------------------------------------- singleton --
_LOCK = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    _LOCK.bind(("127.0.0.1", 49731))
    _LOCK.listen(1)
except OSError:
    raise SystemExit(0)                      # another pet already owns the port

# ------------------------------------------------------------------- config --
CHROMA = "#ff00ff"          # made fully transparent (Windows) -> irregular shape
SCREEN = "#0a0f16"          # the bot's face "screen"
CLOUD_FILL = "#eef3f9"      # the thought cloud
CLOUD_TEXT = "#16222f"
ANIM_MS = 45                # ~22 fps animation
STATE_EVERY = 7             # re-read session state every Nth frame (~0.3s)
BASE_DY = 40                # push the robot down to make room for the cloud on top
W, H = 162, 214

STATES = {
    "idle":      {"label": "idle",       "body": "#1b3a5c", "accent": "#8fb8de", "expr": "calm",  "amp": 3, "spd": 0.11, "shake": 0},
    "working":   {"label": "working",    "body": "#123f63", "accent": "#5fd0ff", "expr": "scan",  "amp": 2, "spd": 0.22, "shake": 0},
    "done":      {"label": "done!",      "body": "#1c5a37", "accent": "#7fe6a0", "expr": "happy", "amp": 4, "spd": 0.16, "shake": 0},
    "needs-you": {"label": "needs you!", "body": "#7a4610", "accent": "#ffce6b", "expr": "wide",  "amp": 2, "spd": 0.20, "shake": 3},
}

# --------------------------------------------------------------- app window --
root = tk.Tk()
root.title("Claude pet")
root.overrideredirect(True)
root.attributes("-topmost", True)
try:
    root.attributes("-transparentcolor", CHROMA)
except tk.TclError:
    pass
root.configure(bg=CHROMA)

sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
root.geometry(f"{W}x{H}+{sw - W - 24}+{sh - H - 56}")

canvas = tk.Canvas(root, width=W, height=H, bg=CHROMA, highlightthickness=0, bd=0)
canvas.pack()


def rr(x1, y1, x2, y2, r, **kw):
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


def draw_cloud(label, accent):
    # puffy thought cloud near the top (fixed; doesn't bob with the bot)
    for (a, b, c, d) in [(34, 8, 128, 40), (24, 17, 60, 43),
                         (102, 17, 138, 43), (48, 2, 88, 30), (80, 4, 116, 32)]:
        canvas.create_oval(a, b, c, d, fill=CLOUD_FILL, outline="", tags="cloud")
    # two little thought bubbles trailing down toward the antenna
    canvas.create_oval(74, 44, 84, 54, fill=CLOUD_FILL, outline="", tags="cloud")
    canvas.create_oval(78, 55, 85, 62, fill=CLOUD_FILL, outline="", tags="cloud")
    canvas.create_text(81, 23, text=label, fill=CLOUD_TEXT, font=("Segoe UI", 10, "bold"), tags="cloud")


def draw_eyes(expr, blink, look, accent):
    lx, rx, ey = 62, 100, 75
    if blink:
        for ex in (lx, rx):
            canvas.create_line(ex - 8, ey, ex + 8, ey, fill=accent, width=4,
                               capstyle="round", tags="bot")
        return
    if expr == "happy":
        for ex in (lx, rx):
            canvas.create_arc(ex - 10, ey - 7, ex + 10, ey + 12, start=20, extent=140,
                              style="arc", outline=accent, width=4, tags="bot")
    elif expr == "wide":
        for ex in (lx, rx):
            canvas.create_oval(ex - 9, ey - 11, ex + 9, ey + 11, fill="white",
                               outline=accent, width=2, tags="bot")
            canvas.create_oval(ex - 3 + look, ey - 4, ex + 5 + look, ey + 6,
                               fill=SCREEN, outline="", tags="bot")
    elif expr == "scan":
        for ex in (lx, rx):
            canvas.create_oval(ex - 8, ey - 9, ex + 8, ey + 9, fill=SCREEN,
                               outline=accent, width=2, tags="bot")
            canvas.create_oval(ex - 3 + look, ey - 4, ex + 4 + look, ey + 4,
                               fill=accent, outline="", tags="bot")
    else:  # calm
        for ex in (lx, rx):
            canvas.create_oval(ex - 6, ey - 9, ex + 6, ey + 9, fill=accent,
                               outline="", tags="bot")


# ------------------------------------------------------------------ animation --
_frame = 0
_state = "idle"
_count = 0


def render():
    global _frame, _state, _count
    _frame += 1
    if _frame % STATE_EVERY == 1:
        _state, _count = aggregate()

    st = STATES[_state]
    f = _frame
    accent, body = st["accent"], st["body"]
    dy = -st["amp"] * math.sin(f * st["spd"])
    dx = st["shake"] * math.sin(f * 0.9) if st["shake"] else 0
    blink = st["expr"] == "calm" and (f % 95) < 3
    look = int(round(3 * math.sin(f * 0.18)))
    glow = 4 + 1.6 * (0.5 + 0.5 * math.sin(f * 0.22))

    if _state == "working":
        label = ("working x%d" % _count) if _count > 1 else ("working" + "." * ((f // 6) % 4))
    elif _state == "needs-you" and _count > 1:
        label = "needs you x%d" % _count
    else:
        label = st["label"]

    canvas.delete("all")

    # thought cloud on top (fixed)
    draw_cloud(label, accent)

    # floor shadow (fixed; shrinks as the bot floats up)
    shw = 26 - abs(dy) * 0.9
    canvas.create_oval(80 - shw, 160 + BASE_DY, 80 + shw, 168 + BASE_DY, fill="#0a0d12", outline="")

    # ---- robot (drawn at base coords, tag "bot", then shifted down by BASE_DY) ----
    rr(52, 120, 72, 135, 7, fill=body, outline=accent, width=2, tags="bot")
    rr(90, 120, 110, 135, 7, fill=body, outline=accent, width=2, tags="bot")
    canvas.create_line(81, 34, 81, 16, fill=accent, width=3, capstyle="round", tags="bot")
    canvas.create_oval(81 - glow, 16 - glow, 81 + glow, 16 + glow, fill=accent, outline="", tags="bot")
    canvas.create_oval(26, 74, 40, 88, fill=body, outline=accent, width=2, tags="bot")
    canvas.create_oval(122, 74, 136, 88, fill=body, outline=accent, width=2, tags="bot")
    rr(32, 34, 130, 122, 24, fill=body, outline=accent, width=3, tags="bot")
    rr(44, 48, 118, 105, 16, fill=SCREEN, outline="", tags="bot")
    canvas.create_line(52, 56, 74, 56, fill="#243244", width=2, capstyle="round", tags="bot")
    draw_eyes(st["expr"], blink, look, accent)
    canvas.create_text(81, 97, text=">_", fill=accent, font=("Consolas", 10, "bold"), tags="bot")

    canvas.move("bot", dx, dy + BASE_DY)

    root.after(ANIM_MS, render)


# ------------------------------------------------------------ interactions --
_drag = {"x": 0, "y": 0}


def start_drag(e):
    _drag["x"], _drag["y"] = e.x, e.y


def do_drag(e):
    root.geometry(f"+{root.winfo_x() + e.x - _drag['x']}+{root.winfo_y() + e.y - _drag['y']}")


canvas.bind("<Button-1>", start_drag)
canvas.bind("<B1-Motion>", do_drag)

menu = tk.Menu(root, tearoff=0)
menu.add_command(label="Hide (until next launch)", command=root.withdraw)
menu.add_separator()
menu.add_command(label="Quit pet", command=lambda: (_LOCK.close(), root.destroy()))
canvas.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

render()
root.mainloop()
