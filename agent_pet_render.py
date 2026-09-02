"""Pillow rendering for the Agent Pet robot and session panel."""

import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from agent_pet_state import format_age

UI = 1.0                    # device pixels per logical pixel (display scaling)
SC = 2.0                    # shape canvas scale: UI x supersampling
ROBOT_W, ROBOT_COL = 162, 186
ROBOT_BLOCK_H = 218         # robot column height, cloud included
CLOUD_H, CLOUD_Y = 42, 2
PANEL_W_MIN, PANEL_W_MAX = 200, 260
ROW_H, ROW_H_HINT, HEAD_H, MORE_H = 22, 34, 20, 18
PAD, GAP, MARGIN = 10, 10, 14
MAX_ROWS = 8

SCREEN = (10, 15, 22, 255)
CLOUD_FILL = (247, 250, 253, 250)
CLOUD_EDGE = (206, 216, 230, 255)
CLOUD_TEXT = (30, 41, 56, 255)
PANEL_BG = (246, 248, 251, 240)
PANEL_EDGE = (211, 219, 231, 255)
PANEL_GLOSS = (255, 255, 255, 170)
SEP = (229, 234, 242, 255)
TXT = (43, 52, 64, 255)
TXT_MUTED = (129, 140, 156, 255)
TXT_AGE = (154, 163, 177, 255)
TXT_HEAD = (160, 169, 183, 255)
NEEDS_BG = (255, 246, 230, 255)
NEEDS_BAR = (241, 170, 60, 255)
HINT_TXT = (156, 118, 54, 255)

DOT = {"needs-you": (240, 160, 42, 255), "working": (47, 157, 224, 255),
       "done": (53, 180, 106, 255), "idle": (188, 196, 207, 255)}
GLYPH = {"claude": (198, 116, 70, 255), "codex": (91, 141, 239, 255),
         "pi": (122, 91, 214, 255)}

STATES = {
    "idle":      {"label": "idle",       "body": (27, 58, 92),  "accent": (143, 184, 222), "expr": "calm",  "amp": 3, "spd": 0.11, "shake": 0},
    "working":   {"label": "working",    "body": (18, 63, 99),  "accent": (95, 208, 255),  "expr": "scan",  "amp": 2, "spd": 0.22, "shake": 0},
    "done":      {"label": "done!",      "body": (28, 90, 55),  "accent": (127, 230, 160), "expr": "happy", "amp": 4, "spd": 0.16, "shake": 0},
    "needs-you": {"label": "needs you!", "body": (122, 70, 16), "accent": (255, 206, 107), "expr": "wide",  "amp": 2, "spd": 0.20, "shake": 3},
}

_FONTDIR = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Fonts")
_FONTS = {"ui": "segoeui.ttf", "ui-sb": "seguisb.ttf", "ui-b": "segoeuib.ttf",
          "mono": "consola.ttf", "mono-b": "consolab.ttf"}
_font_cache = {}
_shadow_cache = {}


def set_scale(scale):
    """Render at `scale` device pixels per logical pixel and drop stale caches."""
    global UI, SC
    UI = max(1.0, float(scale))
    SC = UI * (2.0 if UI < 1.5 else 1.25)
    _font_cache.clear()
    _shadow_cache.clear()
    _static_cache.clear()


class Pen:
    """Text/marker drawing in logical coordinates on a device-scaled image."""

    def __init__(self, img):
        self.d = ImageDraw.Draw(img)

    def text(self, xy, s, **kw):
        self.d.text((xy[0] * UI, xy[1] * UI), s, **kw)

    def ellipse(self, box, **kw):
        self.d.ellipse([v * UI for v in box], **kw)

    def textlength(self, s, font=None):
        return self.d.textlength(s, font=font) / UI


def font(kind, size):
    size = max(6, int(round(size * UI)))
    key = (kind, size)
    if key not in _font_cache:
        try:
            _font_cache[key] = ImageFont.truetype(os.path.join(_FONTDIR, _FONTS[kind]), size)
        except Exception:
            try:
                _font_cache[key] = ImageFont.load_default(size)
            except TypeError:
                _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


def text_w(draw, s, f):
    return int(draw.textlength(s, font=f))


def _fit(draw, s, f, maxw):
    if text_w(draw, s, f) <= maxw:
        return s
    while s and text_w(draw, s + "\u2026", f) > maxw:
        s = s[:-1]
    return (s + "\u2026") if s else ""


def _down(img, size):
    """Downscale a shape canvas; LANCZOS only pays off for a real supersample."""
    ratio = img.width / max(1, size[0])
    return img.resize(size, Image.LANCZOS if ratio >= 1.8 else Image.BILINEAR)


def _over(dst, src, x, y):
    """alpha_composite that clips instead of raising when src overhangs dst."""
    x, y = int(x), int(y)
    x0, y0 = max(0, -x), max(0, -y)
    x1, y1 = min(src.width, dst.width - x), min(src.height, dst.height - y)
    if x1 <= x0 or y1 <= y0:
        return
    if (x0, y0, x1, y1) != (0, 0, src.width, src.height):
        src = src.crop((x0, y0, x1, y1))
    dst.alpha_composite(src, (x + x0, y + y0))


def _shadow(key, size, builder, blur, alpha):
    """Cached blurred silhouette; builder(draw) paints white on an L mask."""
    if key in _shadow_cache:
        return _shadow_cache[key]
    pad = int(blur * 3)
    m = Image.new("L", (size[0] + pad * 2, size[1] + pad * 2), 0)
    builder(ImageDraw.Draw(m), pad)
    m = m.filter(ImageFilter.GaussianBlur(blur))
    m = m.point(lambda v: int(v * alpha))
    img = Image.new("RGBA", m.size, (18, 28, 44, 0))
    img.putalpha(m)
    if len(_shadow_cache) > 48:
        _shadow_cache.clear()
    _shadow_cache[key] = (img, pad)
    return _shadow_cache[key]


# ------------------------------------------------------------------- cloud --
_CLOUD_PUFFS = ((0.135, 0.56, 0.30), (0.34, 0.32, 0.31),
                (0.63, 0.30, 0.33), (0.865, 0.56, 0.30), (0.50, 0.70, 0.30))


def _cloud_ellipses(w, h, grow=0.0):
    """One flat body plus overlapping puffs; unioned in a single mask."""
    g = grow
    out = [(w * 0.10 - g, h * 0.28 - g, w * 0.90 + g, h * 0.88 + g)]
    for fx, fy, fr in _CLOUD_PUFFS:
        cx, cy, r = w * fx, h * fy, h * fr + g
        out.append((cx - r, cy - r, cx + r, cy + r))
    return out


def _draw_cloud(d, canvas, x, y, w, h, s):
    """One mask, one fill: overlapping ellipses with no internal seams."""
    for grow, col in ((1.0, CLOUD_EDGE), (0.0, CLOUD_FILL)):
        m = Image.new("L", (int(w * s) + 8, int(h * s) + 8), 0)
        md = ImageDraw.Draw(m)
        for e in _cloud_ellipses(w, h, grow):
            md.ellipse([e[0] * s + 4, e[1] * s + 4, e[2] * s + 4, e[3] * s + 4], fill=255)
        layer = Image.new("RGBA", m.size, col[:3] + (255,))
        layer.putalpha(m)
        _over(canvas, layer, int(x * s) - 4, int(y * s) - 4)
    for tx, ty, r in ((w * 0.50, h + 2.5, 4.4), (w * 0.53, h + 9.0, 2.6)):
        for grow, col in ((1.0, CLOUD_EDGE), (0.0, CLOUD_FILL)):
            d.ellipse([(x + tx - r - grow) * s, (y + ty - r - grow) * s,
                       (x + tx + r + grow) * s, (y + ty + r + grow) * s], fill=col[:3] + (255,))


# ------------------------------------------------------------------- robot --
def _rr(d, box, r, s, **kw):
    if "width" in kw:
        kw["width"] = max(1, int(round(kw["width"])))
    d.rounded_rectangle([box[0] * s, box[1] * s, box[2] * s, box[3] * s], radius=int(r * s), **kw)


def _eyes(d, expr, blink, look, accent, ox, oy, s):
    ey = oy + 115
    for ex in (ox + 62, ox + 100):
        if blink:
            d.line([(ex - 8) * s, ey * s, (ex + 8) * s, ey * s], fill=accent, width=int(4 * s))
        elif expr == "happy":
            d.arc([(ex - 10) * s, (ey - 7) * s, (ex + 10) * s, (ey + 12) * s],
                  200, 340, fill=accent, width=int(4 * s))
        elif expr == "wide":
            d.ellipse([(ex - 9) * s, (ey - 11) * s, (ex + 9) * s, (ey + 11) * s],
                      fill=(255, 255, 255, 255), outline=accent, width=int(2 * s))
            d.ellipse([(ex - 3 + look) * s, (ey - 4) * s, (ex + 5 + look) * s, (ey + 6) * s], fill=SCREEN)
        elif expr == "scan":
            d.ellipse([(ex - 8) * s, (ey - 9) * s, (ex + 8) * s, (ey + 9) * s],
                      fill=SCREEN, outline=accent, width=int(2 * s))
            d.ellipse([(ex - 3 + look) * s, (ey - 4) * s, (ex + 4 + look) * s, (ey + 4) * s], fill=accent)
        else:
            d.ellipse([(ex - 6) * s, (ey - 9) * s, (ex + 6) * s, (ey + 9) * s], fill=accent)


def _draw_robot(d, ox, oy, st, f, s):
    accent = st["accent"] + (255,)
    body = st["body"] + (255,)
    dy = -st["amp"] * math.sin(f * st["spd"])
    dx = st["shake"] * math.sin(f * 0.9) if st["shake"] else 0
    blink = st["expr"] == "calm" and (f % 95) < 3
    look = int(round(3 * math.sin(f * 0.18)))
    glow = 4 + 1.6 * (0.5 + 0.5 * math.sin(f * 0.22))

    shw = 26 - abs(dy) * 0.9
    for i, a in ((0, 26), (1, 30), (2, 34)):
        d.ellipse([(ox + 81 - shw + i) * s, (oy + 200 + i * 0.8) * s,
                   (ox + 81 + shw - i) * s, (oy + 208 - i * 0.8) * s], fill=(12, 20, 32, a))

    bx, by = ox + dx, oy + dy
    _rr(d, (bx + 52, by + 160, bx + 72, by + 175), 7, s, fill=body, outline=accent, width=int(2 * s))
    _rr(d, (bx + 90, by + 160, bx + 110, by + 175), 7, s, fill=body, outline=accent, width=int(2 * s))
    d.line([(bx + 81) * s, (by + 78) * s, (bx + 81) * s, (by + 60) * s], fill=accent, width=int(3 * s))
    d.ellipse([(bx + 81 - glow) * s, (by + 60 - glow) * s,
               (bx + 81 + glow) * s, (by + 60 + glow) * s], fill=accent)
    d.ellipse([(bx + 26) * s, (by + 114) * s, (bx + 40) * s, (by + 128) * s],
              fill=body, outline=accent, width=int(2 * s))
    d.ellipse([(bx + 122) * s, (by + 114) * s, (bx + 136) * s, (by + 128) * s],
              fill=body, outline=accent, width=int(2 * s))
    _rr(d, (bx + 32, by + 78, bx + 130, by + 166), 24, s, fill=body, outline=accent, width=int(3 * s))
    _rr(d, (bx + 44, by + 92, bx + 118, by + 149), 16, s, fill=SCREEN)
    d.line([(bx + 52) * s, (by + 100) * s, (bx + 74) * s, (by + 100) * s],
           fill=(36, 50, 68, 255), width=int(2 * s))
    _eyes(d, st["expr"], blink, look, accent, bx, by, s)
    return bx, by, accent


# ------------------------------------------------------------------ layout --
def _row_h(s):
    return ROW_H_HINT if (s.state == "needs-you" and s.hint) else ROW_H


def layout(sess, measure):
    """Window + panel geometry for this session list."""
    rows = sess[:MAX_ROWS]
    extra = len(sess) - len(rows)
    if not rows:
        return {"w": ROBOT_COL, "h": ROBOT_BLOCK_H, "rows": [], "extra": 0,
                "panel": None, "rx": (ROBOT_COL - ROBOT_W) // 2, "ry": 0}
    fn, fa = font("ui", 12), font("ui", 10)
    need = PANEL_W_MIN
    for s in rows:
        need = max(need, PAD + 20 + measure(s.display, fn) + 12 + 8 + 6
                   + measure(format_age(s.age_ms) or "0s", fa) + PAD)
        if s.state == "needs-you" and s.hint:
            need = max(need, PAD + 20 + measure(s.hint, fa) + PAD + 6)
    pw = max(PANEL_W_MIN, min(PANEL_W_MAX, need))
    ph = 8 + HEAD_H + 7 + sum(_row_h(s) for s in rows) + 8 + (MORE_H if extra else 0)
    w = MARGIN + pw + GAP + ROBOT_COL
    h = max(ROBOT_BLOCK_H, ph + 26)
    ry = h - ROBOT_BLOCK_H
    return {"w": w, "h": h, "rows": rows, "extra": extra,
            "panel": (MARGIN, ry + ROBOT_BLOCK_H - 16 - ph, pw, ph),
            "rx": w - ROBOT_COL + (ROBOT_COL - ROBOT_W) // 2, "ry": ry}


def _panel_shapes(d, lay, sess_rows):
    px, py, pw, ph = lay["panel"]
    s = SC
    _rr(d, (px, py, px + pw, py + ph), 12, s, fill=PANEL_BG, outline=PANEL_EDGE, width=s)
    _rr(d, (px + 1, py + 1, px + pw - 1, py + ph - 1), 11, s, outline=PANEL_GLOSS, width=s)
    y = py + 8 + HEAD_H
    d.line([(px + PAD) * s, y * s, (px + pw - PAD) * s, y * s], fill=SEP, width=max(1, int(s)))
    y += 7
    out = []
    for it in sess_rows:
        rh = _row_h(it)
        if it.state == "needs-you":
            _rr(d, (px + 5, y, px + pw - 5, y + rh - 2), 7, s, fill=NEEDS_BG)
            _rr(d, (px + 5, y + 2, px + 8.4, y + rh - 4), 1.7, s, fill=NEEDS_BAR)
        cy = y + 11
        d.ellipse([(px + pw - PAD - 34) * s, (cy - 3.5) * s,
                   (px + pw - PAD - 27) * s, (cy + 3.5) * s], fill=DOT[it.state])
        out.append((px + 4, y, px + pw - 4, y + rh - 2))
        y += rh
    return out


def _panel_text(d, lay, sess_rows, extra, rects):
    px, py, pw, ph = lay["panel"]
    fh, fn, fnb = font("ui", 9), font("ui", 12), font("ui-sb", 12)
    fa, fg, fhint = font("ui", 10), font("mono-b", 11), font("ui", 10)
    d.text((px + PAD, py + 8), "SESSIONS", font=fh, fill=TXT_HEAD)
    cnt = str(len(sess_rows) + extra)
    d.text((px + pw - PAD - text_w(d, cnt, fh), py + 8), cnt, font=fh, fill=TXT_HEAD)
    for it, r in zip(sess_rows, rects):
        dim = it.state == "idle" or not it.clickable
        y = r[1]
        d.text((px + PAD + 2, y + 4), it.glyph, font=fg,
               fill=GLYPH[it.agent] if not dim else TXT_MUTED)
        age = format_age(it.age_ms)
        aw = text_w(d, age, fa)
        d.text((px + pw - PAD - aw, y + 5), age, font=fa, fill=TXT_AGE)
        navail = pw - PAD * 2 - 20 - 26 - aw
        nf = fnb if it.state == "needs-you" else fn
        d.text((px + PAD + 20, y + 3), _fit(d, it.display, nf, navail), font=nf,
               fill=TXT_MUTED if dim else TXT)
        if it.state == "needs-you" and it.hint:
            d.text((px + PAD + 20, y + 19),
                   _fit(d, it.hint, fhint, pw - PAD * 2 - 26), font=fhint, fill=HINT_TXT)
    if extra:
        d.text((px + PAD + 20, py + ph - 8 - MORE_H + 3), "+%d more" % extra,
               font=fa, fill=TXT_MUTED)


# ------------------------------------------------------------------ render --
_static_cache = {}


def _cloud_geom(base_draw, cloud_text, rx):
    cf, csize = font("ui-b", 13), 13
    while csize > 9 and text_w(base_draw, cloud_text, cf) > 118:
        csize -= 1
        cf = font("ui-b", csize)
    tw = text_w(base_draw, cloud_text, cf)
    cw = max(108.0, min(172.0, tw + 48.0))
    return cf, tw, cw, rx + 81 - cw / 2.0


def _build_static(state, cloud_text, lay, base_draw):
    """Everything that does not animate: shadows, panel, cloud, all text."""
    w, h, rx = lay["w"], lay["h"], lay["rx"]
    cf, tw, cw, cx = _cloud_geom(base_draw, cloud_text, rx)
    img = Image.new("RGBA", (int(w * UI), int(h * UI)), (0, 0, 0, 0))
    if lay["panel"]:
        px, py, pw, ph = lay["panel"]
        dw, dh = int(pw * UI), int(ph * UI)
        sh, pad = _shadow(("panel", dw, dh), (dw, dh),
                          lambda dd, p: dd.rounded_rectangle([p, p, p + dw, p + dh],
                                                             int(12 * UI), fill=255),
                          6 * UI, 0.30)
        _over(img, sh, px * UI - pad, (py + 3) * UI - pad)
    sh, pad = _shadow(("cloud", int(cw * UI)), (int(cw * UI), int((CLOUD_H + 18) * UI)),
                      lambda dd, p: [dd.ellipse([e[0] * UI + p, e[1] * UI + p,
                                                 e[2] * UI + p, e[3] * UI + p], fill=255)
                                     for e in _cloud_ellipses(cw, CLOUD_H)],
                      5 * UI, 0.26)
    _over(img, sh, cx * UI - pad, (CLOUD_Y + 3) * UI - pad)

    shapes = Image.new("RGBA", (int(w * SC), int(h * SC)), (0, 0, 0, 0))
    d = ImageDraw.Draw(shapes)
    rects = _panel_shapes(d, lay, lay["rows"]) if lay["panel"] else []
    _draw_cloud(d, shapes, cx, CLOUD_Y, cw, CLOUD_H, SC)
    img.alpha_composite(_down(shapes, img.size))

    td = Pen(img)
    dot_r, gap = 4.0, 6.0
    tx = cx + cw / 2.0 - (dot_r * 2 + gap + tw) / 2.0
    tcy = CLOUD_Y + CLOUD_H * 0.58
    td.ellipse([tx, tcy - dot_r, tx + dot_r * 2, tcy + dot_r], fill=DOT[state])
    td.text((tx + dot_r * 2 + gap, tcy), cloud_text, font=cf, fill=CLOUD_TEXT, anchor="lm")
    if lay["panel"]:
        _panel_text(td, lay, lay["rows"], lay["extra"], rects)
    return img, rects


def _static(state, cloud_text, lay, base_draw):
    key = (lay["w"], lay["h"], state, cloud_text, lay["extra"],
           tuple((s.key, s.state, s.display, s.hint, s.clickable, format_age(s.age_ms))
                 for s in lay["rows"]))
    hit = _static_cache.get(key)
    if hit is None:
        _static_cache.clear()
        hit = _build_static(state, cloud_text, lay, base_draw)
        _static_cache[key] = hit
    return hit


def render(state, cloud_text, sess, frame):
    """Return (RGBA frame, row hit-rects, drag rect). Rects are 1x window px."""
    st = STATES.get(state, STATES["idle"])
    base_draw = Pen(Image.new("RGBA", (1, 1)))
    lay = layout(sess, lambda t, f: text_w(base_draw, t, f))
    w, h, ry = lay["w"], lay["h"], lay["ry"]

    static, rects = _static(state, cloud_text, lay, base_draw)
    img = static.copy()

    col = Image.new("RGBA", (int(ROBOT_COL * SC), int(ROBOT_BLOCK_H * SC)), (0, 0, 0, 0))
    ox = (ROBOT_COL - ROBOT_W) // 2
    bx, by, accent = _draw_robot(ImageDraw.Draw(col), ox, 0, st, frame, SC)
    img.alpha_composite(_down(col, (int(ROBOT_COL * UI), int(ROBOT_BLOCK_H * UI))),
                        (img.width - int(ROBOT_COL * UI), int(ry * UI)))
    Pen(img).text((w - ROBOT_COL + bx + 81, ry + by + 137), ">_",
                  font=font("mono-b", 12), fill=accent, anchor="mm")

    drag = tuple(v * UI for v in (w - ROBOT_COL, 0, w, h))
    rects = [tuple(v * UI for v in r) for r in rects]
    return img, list(zip(rects, lay["rows"])), drag
