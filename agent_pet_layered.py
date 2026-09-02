"""Windows per-pixel-alpha blitting and terminal foreground helpers."""

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
ULW_ALPHA = 0x00000002
AC_SRC_OVER, AC_SRC_ALPHA = 0x00, 0x01
BI_RGB, DIB_RGB_COLORS = 0, 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


HGDIOBJ = wintypes.HGDIOBJ if hasattr(wintypes, "HGDIOBJ") else wintypes.HANDLE

user32.SetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
user32.GetWindowLongW.restype = ctypes.c_long
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetParent.restype = wintypes.HWND
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.UpdateLayeredWindow.argtypes = [
    wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT),
    ctypes.POINTER(wintypes.SIZE), wintypes.HDC, ctypes.POINTER(wintypes.POINT),
    wintypes.DWORD, ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
gdi32.SelectObject.restype = HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, HGDIOBJ]
gdi32.DeleteObject.argtypes = [HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]


def toplevel_hwnd(tk_root):
    """HWND of the real toplevel behind a tk window."""
    hwnd = int(tk_root.winfo_id())
    parent = user32.GetParent(hwnd)
    return parent if parent else hwnd


def bgra_premultiplied(image):
    """PIL RGBA -> premultiplied BGRA bytes, top-down."""
    prem = image.convert("RGBa")
    try:
        return prem.tobytes("raw", "BGRa")
    except Exception:
        buf = bytearray(prem.tobytes())
        buf[0::4], buf[2::4] = buf[2::4], buf[0::4]
        return bytes(buf)


class LayeredWindow:
    """Owns the DIB the frame is blitted through. One per pet window."""

    def __init__(self, hwnd, toolwindow=True):
        self.hwnd = hwnd
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE) | WS_EX_LAYERED
        if toolwindow:
            ex |= WS_EX_TOOLWINDOW
        if not user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex):
            if ctypes.get_last_error():
                raise ctypes.WinError(ctypes.get_last_error())
        self._screen = user32.GetDC(None)
        self._dc = None
        self._bmp = None
        self._old = None
        self._bits = None
        self._size = (0, 0)

    def _ensure(self, w, h):
        if self._size == (w, h) and self._dc:
            return
        self._free_dib()
        self._dc = gdi32.CreateCompatibleDC(self._screen)
        bmi = BITMAPINFO()
        hdr = bmi.bmiHeader
        hdr.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        hdr.biWidth, hdr.biHeight = w, -h
        hdr.biPlanes, hdr.biBitCount, hdr.biCompression = 1, 32, BI_RGB
        bits = ctypes.c_void_p()
        self._bmp = gdi32.CreateDIBSection(self._dc, ctypes.byref(bmi), DIB_RGB_COLORS,
                                           ctypes.byref(bits), None, 0)
        if not self._bmp:
            raise ctypes.WinError(ctypes.get_last_error())
        self._bits = bits
        self._old = gdi32.SelectObject(self._dc, self._bmp)
        self._size = (w, h)

    def update(self, image):
        """Blit one RGBA frame; window position is left to tk."""
        w, h = image.size
        self._ensure(w, h)
        buf = bgra_premultiplied(image)
        ctypes.memmove(self._bits, buf, len(buf))
        size = wintypes.SIZE(w, h)
        src = wintypes.POINT(0, 0)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        ok = user32.UpdateLayeredWindow(self.hwnd, self._screen, None,
                                        ctypes.byref(size), self._dc,
                                        ctypes.byref(src), 0, ctypes.byref(blend),
                                        ULW_ALPHA)
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())

    def _free_dib(self):
        if self._dc:
            if self._old:
                gdi32.SelectObject(self._dc, self._old)
            if self._bmp:
                gdi32.DeleteObject(self._bmp)
            gdi32.DeleteDC(self._dc)
        self._dc = self._bmp = self._old = None

    def close(self):
        self._free_dib()
        if self._screen:
            user32.ReleaseDC(None, self._screen)
            self._screen = None


_ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _window_titles():
    found = []

    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        found.append((hwnd, buf.value))
        return True

    user32.EnumWindows(_ENUMPROC(cb), 0)
    return found


def focus_window(suffixes):
    """Bring the first visible top-level window whose title ends with one of
    `suffixes` to the front. Best effort; returns the title or ''."""
    try:
        for hwnd, title in _window_titles():
            for suf in suffixes:
                if title.endswith(suf):
                    user32.ShowWindow(hwnd, 9)          # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
                    return title
    except Exception:
        pass
    return ""
