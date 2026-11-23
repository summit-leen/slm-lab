# -*- coding: utf-8 -*-
"""Minimal, reliable SLM driver for Windows (wxWidgets in the main thread).

Why not slmpy directly
----------------------
slmpy runs its wx window inside a worker thread. Windows wxWidgets requires all
GUI calls on the main thread, so slmpy prints
``wxThread::IsMain() failed ... only the main thread can process Windows messages``
on every repaint, and ``isImageLock=True`` can block forever. This module keeps
wx on the main thread and marshals images with ``wx.CallAfter``: quiet, and fast
enough for 60 Hz pattern streams at VGA/XGA sizes.

Library use
-----------
    from slm_driver import SLM
    slm = SLM(monitor=1)          # 0-based display index, 1 = second screen
    W, H = slm.getSize()
    slm.update(frame)             # uint8 (H,W) or (H,W,3); thread-safe
    slm.run()                     # blocks on the wx main loop
    slm.close()                   # any thread: closes the window and the loop

The window is borderless and full-screen on the chosen display, so each array
pixel maps to one panel pixel as long as that display runs at its native
resolution with 100 % scaling.
"""
import ctypes
import threading
import time

import numpy as np


def ensure_dpi_aware():
    """Per-monitor DPI awareness: otherwise wx reports scaled (DIP) sizes."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


ensure_dpi_aware()

import wx  # noqa: E402  (must come after the DPI call)

try:
    wx.Log.EnableLogging(False)
except Exception:
    pass


class _SLMFrame(wx.Frame):
    def __init__(self, geometry):
        super().__init__(None, style=wx.FRAME_NO_TASKBAR | wx.BORDER_NONE)
        self.SetPosition(geometry.GetPosition())
        self.SetClientSize(geometry.GetSize())
        self._w = geometry.GetWidth()
        self._h = geometry.GetHeight()
        # one persistent bitmap; frames are copied into it in place
        self._bmp = wx.Bitmap(self._w, self._h, 24)
        self.paint_count = 0
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self._on_erase)
        self.SetBackgroundColour(wx.BLACK)
        try:
            self.SetCursor(wx.Cursor(wx.CURSOR_BLANK))
        except Exception:
            pass
        self.Show()
        self.ShowFullScreen(True, wx.FULLSCREEN_ALL)
        self.SetFocus()

    def _on_erase(self, evt):
        pass  # no flicker

    def _on_paint(self, evt):
        dc = wx.PaintDC(self)
        dc.DrawBitmap(self._bmp, 0, 0)
        self.paint_count += 1

    def apply(self, w, h, buf):
        self._bmp.CopyFromBuffer(buf, wx.BitmapBufferFormat_RGB, w * 3)
        self.Refresh(False)
        self.Update()  # repaint now instead of waiting for the idle-time WM_PAINT


class SLM:
    """A borderless full-screen window on one display, driven from any thread."""

    def __init__(self, monitor=1, verbose=True, refresh_hz=60):
        self.app = wx.App(False)
        count = wx.Display.GetCount()
        if count == 0:
            raise RuntimeError('no display available')
        if not 0 <= monitor < count:
            raise ValueError(f'display {monitor} not present (found {count} displays)')
        self.monitor = monitor
        self.geometry = wx.Display(monitor).GetGeometry()
        self.W = self.geometry.GetWidth()
        self.H = self.geometry.GetHeight()
        self.frame = _SLMFrame(self.geometry)
        self._closed = False
        self._dpi = wx.Display(monitor).GetScaleFactor()
        # Latest-frame-wins pump: a pacing thread hands at most one frame per
        # refresh period to the GUI thread, so the paint queue cannot starve
        # while a producer streams frames faster than the display.
        self._pending = None
        self._lock = threading.Lock()
        self._period = 1.0 / max(1.0, refresh_hz)
        self._pump = threading.Thread(target=self._pump_loop, daemon=True)
        self._pump.start()
        if verbose:
            print(f'SLM window: display {monitor} {self.W}x{self.H} '
                  f'at ({self.geometry.GetX()},{self.geometry.GetY()}) '
                  f'scale={self._dpi} refresh={refresh_hz} Hz')

    # ---- public API -------------------------------------------------
    def getSize(self):
        return self.W, self.H

    @property
    def paint_count(self):
        return self.frame.paint_count

    def update(self, array):
        """Display ``array`` (uint8, HxW grayscale or HxWx3 BGR/RGB)."""
        if self._closed:
            raise RuntimeError('SLM already closed')
        arr = np.ascontiguousarray(array)
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        if arr.ndim == 2:
            arr = np.repeat(arr[:, :, None], 3, axis=2)
        if arr.ndim != 3 or arr.shape[2] != 3:
            raise ValueError(f'expected (H,W) or (H,W,3), got {array.shape}')
        h, w = arr.shape[:2]
        if (w, h) != (self.W, self.H):
            raise ValueError(f'array is {w}x{h}, SLM window is {self.W}x{self.H}')
        buf = arr.tobytes()
        with self._lock:
            self._pending = (w, h, buf)

    def _pump_loop(self):
        period = self._period
        next_t = time.perf_counter()
        while not self._closed:
            with self._lock:
                item = self._pending
                self._pending = None
            if item is not None:
                wx.CallAfter(self.frame.apply, *item)
            next_t += period
            dt = next_t - time.perf_counter()
            if dt > 0:
                time.sleep(dt)
            else:
                next_t = time.perf_counter()

    def update_blocking(self, array, timeout=1.0):
        """Display ``array`` and wait until the window actually repainted it."""
        before = self.frame.paint_count
        self.update(array)
        deadline = time.time() + timeout
        while self.frame.paint_count == before and time.time() < deadline:
            time.sleep(0.001)
        return self.frame.paint_count != before

    def run(self, hold=None):
        """Block on the wx loop; ``hold`` seconds (if given) auto-closes it."""
        if hold:
            wx.CallLater(int(hold * 1000), self.close)
        self.app.MainLoop()

    def close(self):
        if self._closed:
            return
        self._closed = True

        def _shutdown():
            try:
                self.frame.Destroy()
            finally:
                self.app.ExitMainLoop()

        wx.CallAfter(_shutdown)
