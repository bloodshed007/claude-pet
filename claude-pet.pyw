"""
claude-pet.pyw  --  a tiny always-on-top desktop companion for Claude Code.

It aggregates the state of every active Claude Code session (each writes
%USERPROFILE%\\.claude\\pet-sessions\\<session_id>.txt via hooks) and shows one
little floating bot whose face / colour / status reflect the whole fleet:

    idle       ( o_o )   calm blue    -- nothing running
    working    ( >_> )   active blue  -- at least one session busy  (x2, x3 ...)
    done       ( ^_^ )   green        -- a session just finished (fades to idle)
    needs-you  ( O_O )   amber        -- a session needs input (wins over working)

Priority when sessions disagree: needs-you > working > done > idle, so a blocked
session is never hidden by a busy one.

Launch (no console window):
    pythonw claude-pet.pyw

Single instance only (socket lock on 127.0.0.1:49731). Drag it anywhere.
Right-click for a menu. To restart after an update, kill the process owning
port 49731, then relaunch.
"""

import os
import sys
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
CHROMA = "#ff00ff"          # this colour is made fully transparent (Windows)
POLL_MS = 350

STATES = {
    "idle":      {"face": "( o_o )", "label": "idle",       "body": "#1b3a5c", "accent": "#8fb8de"},
    "working":   {"face": "( >_> )", "label": "working",    "body": "#134d78", "accent": "#79d0ff"},
    "done":      {"face": "( ^_^ )", "label": "done!",      "body": "#1c5a37", "accent": "#8fe6a6"},
    "needs-you": {"face": "( O_O )", "label": "needs you!", "body": "#7a4610", "accent": "#ffce7a"},
}

W, H = 156, 116


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
root.geometry(f"{W}x{H}+{sw - W - 24}+{sh - H - 64}")

canvas = tk.Canvas(root, width=W, height=H, bg=CHROMA, highlightthickness=0, bd=0)
canvas.pack()


def round_rect(x1, y1, x2, y2, r, **kw):
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


# ------------------------------------------------------------------ drawing --
_frame = 0


def render():
    global _frame
    _frame += 1

    state, count = aggregate()
    st = STATES[state]

    if state == "working":
        label = ("working x%d" % count) if count > 1 else ("working" + "." * (_frame % 4))
    elif state == "needs-you":
        label = ("needs you x%d" % count) if count > 1 else st["label"]
    else:
        label = st["label"]

    canvas.delete("all")
    round_rect(8, 10, W - 6, H - 6, 22, fill="#0b1622", outline="")            # shadow
    round_rect(6, 6, W - 8, H - 10, 22, fill=st["body"], outline=st["accent"], width=2)
    canvas.create_line(W / 2, 10, W / 2, 2, fill=st["accent"], width=2)         # antenna
    canvas.create_oval(W / 2 - 3, -2, W / 2 + 3, 4, fill=st["accent"], outline="")
    canvas.create_text(W / 2, 50, text=st["face"], fill="white",
                       font=("Consolas", 22, "bold"))
    canvas.create_text(W / 2, 88, text=label, fill=st["accent"],
                       font=("Segoe UI", 11, "bold"))

    root.after(POLL_MS, render)


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
