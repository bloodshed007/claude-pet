"""Always-on-top Windows companion for AgentHub sessions.

Environment:
  PI_PET_HOME           alternate home for an isolated test instance
  PI_PET_LOG            enable traceback logging
  AGENT_PET_WSL_DISTRO  optional WSL distribution for click-to-focus
  AGENT_PET_HUB_COMMAND optional AgentHub command or WSL path
"""

import ctypes
import os
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent_pet_state import Tracker, aggregate, latest_activity_ms, sessions
from agent_pet_notify import NO_WINDOW, Settings
import agent_pet_render as R
from agent_pet_hub import build_focus_command

HOME = os.environ.get("PI_PET_HOME") or os.path.expanduser("~")
LOCK_PORT = 49733 if os.environ.get("PI_PET_HOME") else 49732
LOG_ON = bool(os.environ.get("PI_PET_LOG")) or "--log" in sys.argv
LOG_PATH = os.path.join(HOME, ".pi-pet", "pet.log")

ANIM_MS = 45                # ~22 fps while visible
IDLE_POLL_MS = 600          # slower poll while hidden
STATE_EVERY = 7             # re-read session state every Nth frame
HIDE_AFTER_MS = 120_000     # auto-hide after this long with no new activity
CHROMA = "#ff00ff"          # fallback transparency key
FRONT_TITLES = ("Visual Studio Code", "Windows Terminal")
MAX_NAMES = 3


def log(where, exc=True):
    if not LOG_ON:
        return
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), where))
            if exc:
                f.write(traceback.format_exc())
    except OSError:
        pass


_LOCK = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    _LOCK.bind(("127.0.0.1", LOCK_PORT))
    _LOCK.listen(1)
except OSError:
    raise SystemExit(0)                      # another pet already owns the port


# ------------------------------------------------------------------ labels --
def names_text(names):
    names = [n for n in names if n]
    if not names:
        return ""
    if len(names) > MAX_NAMES:
        return ", ".join(names[:2]) + " +%d" % (len(names) - 2)
    return ", ".join(names)


def cloud_label(state, count, names, frame):
    who = names_text(names)
    if state == "needs-you":
        if not who:
            return "needs you!"
        return ("%s need you" % who) if count > 1 else ("%s needs you" % who)
    if state == "working":
        if not who:
            return "working" + "." * ((frame // 6) % 4)
        return "%s working" % who
    if state == "done":
        return ("%s done!" % who) if who else "done!"
    return ("%d idle" % count) if count else "idle"


def _dpi_scale():
    """Opt out of DPI virtualisation so frames are drawn at device resolution."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            return 1.0
    try:
        return max(1.0, ctypes.windll.user32.GetDpiForSystem() / 96.0)
    except Exception:
        return 1.0


# ------------------------------------------------------------------- window --
UI_SCALE = _dpi_scale()
R.set_scale(UI_SCALE)
root = tk.Tk()
root.title("Agent Pet")
root.overrideredirect(True)
root.attributes("-topmost", True)

SW, SH = root.winfo_screenwidth(), root.winfo_screenheight()
_set = Settings(HOME)
ANCHOR = [_set.get("x") if _set.get("x") is not None else SW - int(24 * UI_SCALE),
          _set.get("y") if _set.get("y") is not None else SH - int(56 * UI_SCALE)]
ANCHOR[0] = min(max(ANCHOR[0], 80), SW)
ANCHOR[1] = min(max(ANCHOR[1], 80), SH)

layered = None
canvas = None
try:
    from agent_pet_layered import LayeredWindow, focus_window, toplevel_hwnd
except Exception:
    log("agent_pet_layered import")

    def focus_window(_suffixes):
        return ""
else:
    try:
        root.update_idletasks()
        layered = LayeredWindow(toplevel_hwnd(root))
    except Exception:
        log("layered setup failed, using chroma fallback")
        layered = None

if layered is None:
    try:
        root.attributes("-transparentcolor", CHROMA)
    except tk.TclError:
        pass
    root.configure(bg=CHROMA)
    canvas = tk.Canvas(root, bg=CHROMA, highlightthickness=0, bd=0)
    canvas.pack(fill="both", expand=True)
    from PIL import ImageTk


# ------------------------------------------------------------------- state --
_frame = 0
_state, _count, _names = "idle", 0, []
_sess = []
_latest = 0
_hidden = False
_geom = None
_rects = []
_drag_rect = (0, 0, 0, 0)
_photo = None
_frame_ms = 0.0
_tracker = Tracker()


def _apply_geometry(w, h):
    global _geom
    x, y = int(ANCHOR[0] - w), int(ANCHOR[1] - h)
    g = (w, h, x, y)
    if g != _geom:
        root.geometry("%dx%d+%d+%d" % g)
        root.update_idletasks()
        _geom = g


def _blit(img):
    global _photo
    if layered is not None:
        layered.update(img)
        return
    from PIL import Image
    bg = Image.new("RGB", img.size, CHROMA)
    bg.paste(img, (0, 0), img)
    _photo = ImageTk.PhotoImage(bg)
    canvas.delete("all")
    canvas.create_image(0, 0, image=_photo, anchor="nw")


def _reveal():
    global _hidden
    root.deiconify()
    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        pass
    _hidden = False


def poll_state():
    global _state, _count, _names, _sess, _latest
    _sess = sessions(HOME)
    _state, _count, _names = aggregate(HOME, sess=_sess)
    _latest = latest_activity_ms(HOME, sess=_sess)
    for ev in _tracker.update(_sess):
        who = ev.session.display or "agent"
        if ev.kind == "needs-you":
            _set.alert("needs-you", "Agent Pet", "%s: %s" % (who, ev.session.hint or "needs your input"))
        else:
            _set.alert("done", "Agent Pet", "%s done" % who)


def render():
    global _frame, _hidden, _rects, _drag_rect, _frame_ms
    try:
        _frame += 1
        if _frame % STATE_EVERY == 1:
            poll_state()

        now_ms = int(time.time() * 1000)
        show = (_set.get("always_show") or _state in ("working", "needs-you")
                or (_latest != 0 and (now_ms - _latest) < HIDE_AFTER_MS))
        if show and _hidden:
            _reveal()
        elif not show and not _hidden:
            root.withdraw()
            _hidden = True
        if _hidden:
            root.after(IDLE_POLL_MS, render)
            return

        t0 = time.perf_counter()
        img, _rects, _drag_rect = R.render(
            _state, cloud_label(_state, _count, _names, _frame),
            _sess if _set.get("show_sessions") else [], _frame)
        _apply_geometry(img.width, img.height)
        _blit(img)
        _frame_ms = (time.perf_counter() - t0) * 1000.0
    except Exception:
        log("render")
    root.after(max(ANIM_MS, int(_frame_ms * 2.5)), render)


# ------------------------------------------------------------ interactions --
_press = {"x": 0, "y": 0, "row": None, "moved": False, "armed": False}
_cursor = [""]


def hit_row(x, y):
    for rect, sess in _rects:
        if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
            return sess
    return None


def jump(sess):
    if sess is None or not sess.window:
        return
    threading.Thread(target=_jump_worker, args=(sess.window,), daemon=True).start()


def _jump_worker(window):
    try:
        subprocess.run(
            build_focus_command(window), timeout=15, creationflags=NO_WINDOW,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        log("hub focus %s" % window)
    try:
        focus_window(FRONT_TITLES)
    except Exception:
        log("focus_window")


def _in_drag_zone(x, y):
    r = _drag_rect
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


def on_press(e):
    _press.update(x=e.x_root, y=e.y_root, row=hit_row(e.x, e.y), moved=False,
                  armed=_in_drag_zone(e.x, e.y))


def on_motion(e):
    if _press["row"] is not None or not _press["armed"]:
        return
    dx, dy = e.x_root - _press["x"], e.y_root - _press["y"]
    if not _press["moved"] and abs(dx) + abs(dy) < 3:
        return
    _press["moved"] = True
    ANCHOR[0] += dx
    ANCHOR[1] += dy
    _press.update(x=e.x_root, y=e.y_root)
    if _geom:
        _apply_geometry(_geom[0], _geom[1])


def on_release(e):
    was_robot, _press["armed"] = _press["armed"], False
    if _press["moved"]:
        _set.set("x", int(ANCHOR[0]))
        _set.set("y", int(ANCHOR[1]))
        return
    if _press["row"] is not None:
        jump(_press["row"])
    elif was_robot and _state == "needs-you":
        jump(next((s for s in _sess if s.state == "needs-you" and s.window), None))


def on_hover(e):
    s = hit_row(e.x, e.y)
    want = "hand2" if (s is not None and s.clickable) else ""
    if want != _cursor[0]:
        _cursor[0] = want
        root.config(cursor=want)


for widget in (root,):
    widget.bind("<Button-1>", on_press)
    widget.bind("<B1-Motion>", on_motion)
    widget.bind("<ButtonRelease-1>", on_release)
    widget.bind("<Motion>", on_hover)

_vars = {}
menu = tk.Menu(root, tearoff=0)
for key, label in (("mute_done", "Mute done chime"),
                   ("mute_needs_you", "Mute needs-you toast"),
                   ("mute_all", "Mute all sounds"),
                   ("always_show", "Always show"),
                   ("show_sessions", "Show sessions")):
    _vars[key] = tk.BooleanVar(value=bool(_set.get(key)))
    menu.add_checkbutton(
        label=label, variable=_vars[key],
        command=(lambda k=key: _set.set(k, bool(_vars[k].get()))))
menu.add_separator()
menu.add_command(label="Hide (until next launch)", command=root.withdraw)
menu.add_command(label="Quit pet", command=lambda: (_LOCK.close(), root.destroy()))
root.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))


root.report_callback_exception = lambda *a: log("tk-callback")
render()
root.mainloop()
