"""
HADIL Native Desktop Startup Splash Screen

Provides native visual feedback while the local HADIL backend initializes in packaged desktop EXE mode.
- Lightweight (built-in Tkinter)
- Fast startup (<20ms)
- Automatically hidden upon backend readiness
- Displays error message on backend failure
- Bypassed entirely in CLI mode or cloud environments
"""

import sys
import os
import time
import threading
from typing import Optional

_GLOBAL_SPLASH: Optional["HadilNativeSplash"] = None

def get_global_splash() -> Optional["HadilNativeSplash"]:
    return _GLOBAL_SPLASH

class HadilNativeSplash:
    def __init__(self):
        global _GLOBAL_SPLASH
        _GLOBAL_SPLASH = self

        self.root = None
        self.status_label = None
        self.canvas = None
        self.btn_frame = None
        self.close_btn = None
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.has_error = False
        self.error_text = ""
        self._should_close = False
        self._pulse_pos = 0

    def _build_ui(self):
        import tkinter as tk

        self.root = tk.Tk()
        self.root.title("HADIL Startup")
        self.root.overrideredirect(True)  # Frameless native splash
        self.root.attributes("-topmost", True)

        width = 380
        height = 210

        # Center on primary monitor
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        # Dark theme background (#0F1626)
        self.root.configure(bg="#0F1626")

        # Outer border frame with emerald accent border (#10B981)
        border_frame = tk.Frame(self.root, bg="#10B981", bd=1)
        border_frame.pack(fill="both", expand=True)

        inner_frame = tk.Frame(border_frame, bg="#0F1626")
        inner_frame.pack(fill="both", expand=True, padx=1, pady=1)

        # Header Container (Logo + Title)
        header = tk.Frame(inner_frame, bg="#0F1626")
        header.pack(pady=(24, 8))

        # Emerald Diamond Emblem Canvas
        icon_canvas = tk.Canvas(header, width=38, height=38, bg="#0F1626", highlightthickness=0)
        icon_canvas.pack(side="left", padx=(0, 14))
        # Draw emerald diamond icon
        icon_canvas.create_polygon(19, 4, 34, 19, 19, 34, 4, 19, fill="#10B981", outline="#34D399", width=1)
        icon_canvas.create_polygon(19, 10, 28, 19, 19, 28, 10, 19, fill="#0F1626")
        icon_canvas.create_polygon(19, 14, 24, 19, 19, 24, 14, 19, fill="#10B981")

        # Title Stack
        title_box = tk.Frame(header, bg="#0F1626")
        title_box.pack(side="left")

        title_lbl = tk.Label(
            title_box, 
            text="HADIL", 
            font=("Segoe UI", 20, "bold"), 
            fg="#FFFFFF", 
            bg="#0F1626"
        )
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(
            title_box, 
            text="Database Intelligence", 
            font=("Segoe UI", 9), 
            fg="#94A3B8", 
            bg="#0F1626"
        )
        sub_lbl.pack(anchor="w")

        # Status Label
        self.status_label = tk.Label(
            inner_frame, 
            text="Starting HADIL...", 
            font=("Segoe UI", 10), 
            fg="#34D399", 
            bg="#0F1626"
        )
        self.status_label.pack(pady=(12, 10))

        # Indeterminate Emerald Loading Indicator Canvas
        self.canvas = tk.Canvas(inner_frame, width=290, height=4, bg="#1E293B", highlightthickness=0)
        self.canvas.pack(pady=(0, 14))

        # Failure Dismiss Button (hidden during normal loading)
        self.btn_frame = tk.Frame(inner_frame, bg="#0F1626")
        self.close_btn = tk.Button(
            self.btn_frame,
            text="Dismiss",
            font=("Segoe UI", 9, "bold"),
            fg="#FFFFFF",
            bg="#EF4444",
            activebackground="#DC2626",
            activeforeground="#FFFFFF",
            bd=0,
            padx=16,
            pady=4,
            cursor="hand2",
            command=self.close
        )
        self.close_btn.pack()

    def _loop(self):
        try:
            self._build_ui()
            self.is_running = True
            
            pulse_w = 75
            canvas_w = 290
            
            while not self._should_close and self.root:
                if not self.has_error:
                    # Animate smooth emerald pulse loading bar
                    self._pulse_pos = (self._pulse_pos + 6) % (canvas_w + pulse_w)
                    x1 = self._pulse_pos - pulse_w
                    x2 = self._pulse_pos
                    self.canvas.delete("all")
                    # Draw background rail
                    self.canvas.create_rectangle(0, 0, canvas_w, 4, fill="#1E293B", width=0)
                    # Draw animated emerald pulse segment
                    px1 = max(0, x1)
                    px2 = min(canvas_w, x2)
                    if px2 > px1:
                        self.canvas.create_rectangle(px1, 0, px2, 4, fill="#10B981", width=0)
                
                self.root.update_idletasks()
                self.root.update()
                time.sleep(0.02)
        except Exception:
            pass
        finally:
            self.is_running = False
            if self.root:
                try:
                    self.root.destroy()
                except Exception:
                    pass
                self.root = None

    def start(self):
        """Launches the native splash window in a background thread."""
        if self.is_running or self.thread is not None:
            return
        self._should_close = False
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        # Brief pause to allow Tkinter to create and render window
        time.sleep(0.12)

    def set_status(self, text: str):
        """Updates the status text label."""
        self.error_text = text
        if self.root and self.status_label:
            try:
                self.root.after(0, lambda: self.status_label.config(text=text))
            except Exception:
                pass

    def show_failure(self, error_msg: str):
        """Replaces loading state with a clear startup failure message."""
        self.has_error = True
        self.error_text = error_msg
        if self.root:
            try:
                def _update_err():
                    if self.status_label:
                        self.status_label.config(text=error_msg, fg="#F87171")
                    if self.canvas:
                        self.canvas.delete("all")
                        self.canvas.create_rectangle(0, 0, 290, 4, fill="#EF4444", width=0)
                    if self.btn_frame:
                        self.btn_frame.pack(pady=(0, 10))
                self.root.after(0, _update_err)
            except Exception:
                pass

    def close(self):
        """Destroys and closes the splash window immediately."""
        self._should_close = True
        if self.root:
            try:
                self.root.after(0, self.root.destroy)
            except Exception:
                pass
