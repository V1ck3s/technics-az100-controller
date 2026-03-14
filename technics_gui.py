# /// script
# requires-python = ">=3.11"
# dependencies = ["customtkinter>=5.2"]
# ///
"""
Technics EAH-AZ100 - GUI (customtkinter)

Exposes all features from technics.py in a modern GUI.
Launch: uv run technics_gui.py
"""

import json
import threading
import tkinter as tk
from typing import Any, Callable

import customtkinter as ctk

import technics as tc

# ---------------------------------------------------------------------------
#  GUI Constants
# ---------------------------------------------------------------------------

ACCENT = "#1f6aa5"
ACCENT_HOVER = "#144870"
BG_DARK = "#1a1a2e"
BG_SIDEBAR = "#16213e"
BG_HEADER = "#0f3460"
GREEN = "#27ae60"
ORANGE = "#f39c12"
RED = "#e74c3c"
GRAY = "#7f8c8d"
TEXT = "#ecf0f1"
TEXT_DIM = "#95a5a6"

PAGES = [
    ("Battery", "battery"),
    ("ANC", "anc"),
    ("Audio", "audio"),
    ("Connectivity", "connectivity"),
    ("Settings", "settings"),
    ("Voice", "voice"),
    ("Info", "info"),
    ("Tools", "tools"),
]

EQ_LABELS = {
    "off": "None", "bass": "Bass+", "clear-voice": "Clear Voice",
    "custom": "Custom 1", "bass2": "Bass+ 2", "clear-voice2": "Clear Voice 2",
    "super-bass": "Super Bass", "custom2": "Custom 2", "custom3": "Custom 3",
}

CODEC_LABELS = {
    "sbc": "SBC", "aac": "AAC", "aptx": "aptX",
    "aptx-ll": "aptX LL", "aptx-hd": "aptX HD", "ldac": "LDAC",
}

LANGUAGE_LABELS = {
    "ja": "Japanese", "en": "English", "de": "German", "fr": "French",
    "fr-ca": "French (CA)", "es": "Spanish", "it": "Italian",
    "pl": "Polish", "ru": "Russian", "uk": "Ukrainian",
    "zh": "Chinese", "yue": "Cantonese",
}

# ---------------------------------------------------------------------------
#  BTWorker - Bluetooth operations in thread
# ---------------------------------------------------------------------------

class BTWorker:
    """Handles Bluetooth operations in a daemon thread."""

    def __init__(self):
        self.sock = None
        self._lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return self.sock is not None

    def connect(self, address: str, channel: int,
                callback: Callable[[bool, Exception | None], None]):
        def _task():
            try:
                self.sock = tc.bt_connect(address, channel)
                callback(True, None)
            except Exception as e:
                self.sock = None
                callback(False, e)
        t = threading.Thread(target=_task, daemon=True)
        t.start()

    def disconnect(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def run(self, func: Callable, *args,
            callback: Callable[[Any, Exception | None], None] | None = None):
        def _task():
            with self._lock:
                try:
                    result = func(self.sock, *args)
                    if callback:
                        callback(result, None)
                except Exception as e:
                    if callback:
                        callback(None, e)
        t = threading.Thread(target=_task, daemon=True)
        t.start()


# ---------------------------------------------------------------------------
#  Reusable widgets
# ---------------------------------------------------------------------------

class Section(ctk.CTkFrame):
    """Section frame with title."""

    def __init__(self, parent, title: str, **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        ctk.CTkLabel(
            self, text=title, font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=8, pady=(12, 4))
        self._content = ctk.CTkFrame(self, fg_color=("gray86", "gray17"), corner_radius=8)
        self._content.pack(fill="x", padx=8, pady=(0, 4))

    @property
    def content(self) -> ctk.CTkFrame:
        return self._content


class ToggleRow(ctk.CTkFrame):
    """Row with label + switch."""

    def __init__(self, parent, label: str, command=None, **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=label, text_color=TEXT).grid(
            row=0, column=0, sticky="w", padx=8, pady=4)
        self.switch = ctk.CTkSwitch(self, text="", command=command, width=40)
        self.switch.grid(row=0, column=1, padx=8, pady=4)

    def get(self) -> bool:
        return self.switch.get() == 1

    def set(self, value: bool):
        if value:
            self.switch.select()
        else:
            self.switch.deselect()


# ---------------------------------------------------------------------------
#  Pages
# ---------------------------------------------------------------------------

class BasePage(ctk.CTkScrollableFrame):
    """Base page with access to the app and BT worker."""

    # Pages whose data is fully covered by the batch (no refresh needed)
    BATCH_COMPLETE = False

    def __init__(self, parent, app: "App"):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._loading = False
        self._populated = False

    @property
    def bt(self) -> BTWorker:
        return self.app.bt

    def refresh(self):
        """Reload data from the earbuds."""
        pass

    def populate_from_batch(self, data: dict):
        """Populate the page from batch data."""
        self._populated = True

    def _cb(self, callback):
        """Wrap a callback to execute it in the UI thread."""
        def wrapper(*args):
            self.app.after(0, lambda: callback(*args))
        return wrapper

    def _status(self, msg: str):
        self.app.set_status(msg)

    def _set_enabled(self, enabled: bool):
        """Enable/disable page controls."""
        state = "normal" if enabled else "disabled"
        for widget in self._iter_controls():
            try:
                widget.configure(state=state)
            except Exception:
                pass

    def _iter_controls(self):
        """Iterator over interactive widgets."""
        return []


# --- Battery Page ---

class BatteryPage(BasePage):

    def __init__(self, parent, app):
        super().__init__(parent, app)

        sec = Section(self, "Battery Levels")
        sec.pack(fill="x")
        c = sec.content

        self._bars = {}
        for label_text, key in [("Agent (L)", "agent"), ("Partner (R)", "partner"),
                                ("Case", "cradle")]:
            row = ctk.CTkFrame(c, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=4)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(row, text=label_text, width=80, text_color=TEXT).grid(
                row=0, column=0, sticky="w")
            bar = ctk.CTkProgressBar(row, height=18, corner_radius=4)
            bar.set(0)
            bar.grid(row=0, column=1, sticky="ew", padx=8)
            lbl = ctk.CTkLabel(row, text="--", width=50, text_color=TEXT_DIM)
            lbl.grid(row=0, column=2)
            self._bars[key] = (bar, lbl)

        btn = ctk.CTkButton(self, text="Refresh", command=self.refresh, width=120)
        btn.pack(pady=12)
        self._refresh_btn = btn

    def refresh(self):
        if not self.bt.connected:
            return
        self._status("Reading battery...")
        self.bt.run(tc.cmd_battery_get, callback=self._cb(self._on_battery))

    def populate_from_batch(self, data: dict):
        super().populate_from_batch(data)
        if "cradle_battery" in data:
            level = data["cradle_battery"].get("level", 0)
            self._update_bar("cradle", level)

    def _on_battery(self, result, error):
        if error:
            self._status(f"Battery error: {error}")
            return
        for key in ("agent", "partner", "cradle"):
            if key in result:
                self._update_bar(key, result[key])
        self._status("Battery updated")

    def _update_bar(self, key: str, level: int):
        if key not in self._bars:
            return
        bar, lbl = self._bars[key]
        pct = max(0, min(100, level)) / 100
        bar.set(pct)
        lbl.configure(text=f"{level}%")
        if level > 50:
            bar.configure(progress_color=GREEN)
        elif level > 20:
            bar.configure(progress_color=ORANGE)
        else:
            bar.configure(progress_color=RED)

    def _iter_controls(self):
        return [self._refresh_btn]


# --- ANC Page ---

class ANCPage(BasePage):

    def __init__(self, parent, app):
        super().__init__(parent, app)

        # ANC Mode
        sec = Section(self, "ANC Mode")
        sec.pack(fill="x")
        c = sec.content
        self._anc_mode = ctk.CTkSegmentedButton(
            c, values=["Off", "NC", "Ambient"],
            command=self._on_anc_mode)
        self._anc_mode.pack(fill="x", padx=8, pady=8)

        # NC Level
        sec2 = Section(self, "NC Level")
        sec2.pack(fill="x")
        c2 = sec2.content
        row = ctk.CTkFrame(c2, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=8)
        row.grid_columnconfigure(0, weight=1)
        self._nc_slider = ctk.CTkSlider(
            row, from_=20, to=40, number_of_steps=20,
            command=self._on_nc_slider)
        self._nc_slider.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._nc_label = ctk.CTkLabel(row, text="--", width=60, text_color=TEXT)
        self._nc_label.grid(row=0, column=1)

        # Adaptive ANC
        sec3 = Section(self, "Adaptive ANC")
        sec3.pack(fill="x")
        self._adaptive = ToggleRow(sec3.content, "Adaptive ANC", command=self._on_adaptive)
        self._adaptive.pack(fill="x")

        # Ambient Mode
        sec4 = Section(self, "Ambient Mode")
        sec4.pack(fill="x")
        c4 = sec4.content
        self._ambient_mode = ctk.CTkSegmentedButton(
            c4, values=["Transparent", "Attention"],
            command=self._on_ambient_mode)
        self._ambient_mode.pack(fill="x", padx=8, pady=4)
        self._ambient_music = ctk.CTkSegmentedButton(
            c4, values=["Play", "Stop"],
            command=self._on_ambient_music)
        self._ambient_music.pack(fill="x", padx=8, pady=(0, 8))

        # Physical button
        sec5 = Section(self, "Physical Button (cycles)")
        sec5.pack(fill="x")
        c5 = sec5.content
        self._toggle_off = ctk.CTkCheckBox(c5, text="Off", command=self._on_toggle)
        self._toggle_off.pack(anchor="w", padx=8, pady=2)
        self._toggle_nc = ctk.CTkCheckBox(c5, text="NC", command=self._on_toggle)
        self._toggle_nc.pack(anchor="w", padx=8, pady=2)
        self._toggle_amb = ctk.CTkCheckBox(c5, text="Ambient", command=self._on_toggle)
        self._toggle_amb.pack(anchor="w", padx=8, pady=(2, 8))

    def refresh(self):
        if not self.bt.connected:
            return
        self._loading = True
        self._status("Reading ANC...")
        self.bt.run(tc.cmd_anc_get, callback=self._cb(self._on_anc_data))
        self.bt.run(tc.cmd_anc_level_get, callback=self._cb(self._on_level_data))
        # Adaptive ANC (cmd 103) does not respond to GET on EAH-AZ100
        self.bt.run(tc.cmd_ambient_mode_get, callback=self._cb(self._on_ambient_data))
        self.bt.run(tc.cmd_outside_toggle_get, callback=self._cb(self._on_toggle_data))

    def populate_from_batch(self, data: dict):
        super().populate_from_batch(data)
        self._loading = True
        try:
            if "anc" in data:
                anc = data["anc"]
                mode_map = {"Off": "Off", "Noise Canceling": "NC", "Ambient": "Ambient"}
                mode_label = mode_map.get(anc.get("mode", "Off"), "Off")
                self._anc_mode.set(mode_label)
            if "anc_level" in data:
                level = data["anc_level"].get("level", 30)
                if 20 <= level <= 40:
                    self._nc_slider.set(level)
                db = tc.NC_ADJUST_DB.get(level)
                self._nc_label.configure(
                    text=f"{db:+.1f} dB" if db is not None else "default")
            if "adaptive_anc" in data:
                self._adaptive.set(data["adaptive_anc"].get("mode") == "on")
            if "ambient_mode" in data:
                amb = data["ambient_mode"]
                amb_map = {"transparent": "Transparent", "attention": "Attention"}
                self._ambient_mode.set(amb_map.get(amb.get("ambient", "transparent"), "Transparent"))
                mus_map = {"play": "Play", "stop": "Stop"}
                self._ambient_music.set(mus_map.get(amb.get("music", "play"), "Play"))
            if "outside_toggle" in data:
                active = data["outside_toggle"].get("active", [])
                self._toggle_off.select() if "off" in active else self._toggle_off.deselect()
                self._toggle_nc.select() if "nc" in active else self._toggle_nc.deselect()
                self._toggle_amb.select() if "ambient" in active else self._toggle_amb.deselect()
        finally:
            self._loading = False

    def _on_anc_data(self, result, error):
        if error:
            self._status(f"ANC error: {error}")
            self._loading = False
            return
        mode_map = {0: "Off", 1: "NC", 2: "Ambient"}
        self._anc_mode.set(mode_map.get(result.get("mode", 0), "Off"))
        self._loading = False
        self._status("ANC updated")

    def _on_level_data(self, result, error):
        if error:
            return
        level = result.get("level", 30)
        if 20 <= level <= 40:
            self._nc_slider.set(level)
        self._nc_label.configure(text=result.get("label", "--"))

    def _on_adaptive_data(self, result, error):
        if error:
            return
        self._adaptive.set(result.get("label") == "on")

    def _on_ambient_data(self, result, error):
        if error:
            return
        amb_map = {"transparent": "Transparent", "attention": "Attention"}
        self._ambient_mode.set(amb_map.get(result.get("ambient_mode", "transparent"), "Transparent"))
        mus_map = {"play": "Play", "stop": "Stop"}
        self._ambient_music.set(mus_map.get(result.get("music_mode", "play"), "Play"))

    def _on_toggle_data(self, result, error):
        if error:
            return
        active = result.get("active", [])
        self._toggle_off.select() if "off" in active else self._toggle_off.deselect()
        self._toggle_nc.select() if "nc" in active else self._toggle_nc.deselect()
        self._toggle_amb.select() if "ambient" in active else self._toggle_amb.deselect()

    def _on_anc_mode(self, value):
        if self._loading or not self.bt.connected:
            return
        mode_map = {"Off": "off", "NC": "nc", "Ambient": "ambient"}
        mode = mode_map.get(value)
        if mode:
            self._status(f"ANC -> {value}...")
            self.bt.run(tc.cmd_anc_set, mode,
                        callback=self._cb(lambda r, e: self._status(
                            f"ANC: {value}" if not e else f"Error: {e}")))

    def _on_nc_slider(self, value):
        if self._loading or not self.bt.connected:
            return
        level = int(value)
        db = tc.NC_ADJUST_DB.get(level)
        self._nc_label.configure(text=f"{db:+.1f} dB" if db is not None else "default")

    def _on_nc_slider_release(self, _event=None):
        if self._loading or not self.bt.connected:
            return
        level = int(self._nc_slider.get())
        self._status(f"NC Level -> {level}...")
        self.bt.run(tc.cmd_anc_level_set, level,
                    callback=self._cb(lambda r, e: self._status(
                        f"NC Level: {r.get('label', '')}" if not e else f"Error: {e}")))

    def _on_adaptive(self):
        if self._loading or not self.bt.connected:
            return
        mode = "on" if self._adaptive.get() else "off"
        self._status(f"Adaptive -> {mode}...")
        self.bt.run(tc.generic_set, tc.GENERIC_CMDS["adaptive-anc"], mode,
                    callback=self._cb(lambda r, e: self._status(
                        f"Adaptive: {mode}" if not e else f"Error: {e}")))

    def _on_ambient_mode(self, value):
        if self._loading or not self.bt.connected:
            return
        mode_map = {"Transparent": "transparent", "Attention": "attention"}
        mode = mode_map.get(value)
        if mode:
            self._status(f"Ambient -> {value}...")
            self.bt.run(tc.cmd_ambient_mode_set, mode,
                        callback=self._cb(lambda r, e: self._status(
                            f"Ambient: {value}" if not e else f"Error: {e}")))

    def _on_ambient_music(self, value):
        if self._loading or not self.bt.connected:
            return
        mus_map = {"Play": "play", "Stop": "stop"}
        music = mus_map.get(value)
        if music:
            current = {"Transparent": "transparent", "Attention": "attention"}.get(
                self._ambient_mode.get(), "transparent")
            self._status(f"Ambient music -> {value}...")
            self.bt.run(tc.cmd_ambient_mode_set, current, music,
                        callback=self._cb(lambda r, e: self._status(
                            f"Music: {value}" if not e else f"Error: {e}")))

    def _on_toggle(self):
        if self._loading or not self.bt.connected:
            return
        modes = []
        if self._toggle_off.get():
            modes.append("off")
        if self._toggle_nc.get():
            modes.append("nc")
        if self._toggle_amb.get():
            modes.append("ambient")
        if not modes:
            modes.append("off")
        self._status(f"Toggle -> {', '.join(modes)}...")
        self.bt.run(tc.cmd_outside_toggle_set, modes,
                    callback=self._cb(lambda r, e: self._status(
                        f"Toggle: {', '.join(modes)}" if not e else f"Error: {e}")))

    def _iter_controls(self):
        return [self._anc_mode, self._nc_slider, self._adaptive.switch,
                self._ambient_mode, self._ambient_music,
                self._toggle_off, self._toggle_nc, self._toggle_amb]


# --- Audio Page ---

class AudioPage(BasePage):

    def __init__(self, parent, app):
        super().__init__(parent, app)

        # Equalizer
        sec = Section(self, "Equalizer")
        sec.pack(fill="x")
        c = sec.content
        eq_values = list(EQ_LABELS.values())
        self._eq_var = ctk.StringVar(value="--")
        self._eq_menu = ctk.CTkOptionMenu(
            c, values=eq_values, variable=self._eq_var,
            command=self._on_eq)
        self._eq_menu.pack(fill="x", padx=8, pady=8)

        # Spatial Audio + Head Tracking
        sec2 = Section(self, "Spatial Audio")
        sec2.pack(fill="x")
        self._spatial = ToggleRow(sec2.content, "Spatial Audio", command=self._on_spatial)
        self._spatial.pack(fill="x")
        self._head_tracking = ToggleRow(sec2.content, "Head Tracking", command=self._on_head_tracking)
        self._head_tracking.pack(fill="x")

        # A2DP Codec
        sec3 = Section(self, "Preferred A2DP Codec")
        sec3.pack(fill="x")
        c3 = sec3.content
        codec_values = list(CODEC_LABELS.values())
        self._codec_var = ctk.StringVar(value=codec_values[0])
        self._codec_menu = ctk.CTkOptionMenu(
            c3, values=codec_values, variable=self._codec_var,
            command=self._on_codec)
        self._codec_menu.pack(fill="x", padx=8, pady=8)

        # Buffer
        sec4 = Section(self, "Audio Buffer")
        sec4.pack(fill="x")
        self._buffer = ctk.CTkSegmentedButton(
            sec4.content, values=["Auto", "Music", "Video"],
            command=self._on_buffer)
        self._buffer.pack(fill="x", padx=8, pady=8)

        # Current codec
        sec5 = Section(self, "Current Codec")
        sec5.pack(fill="x")
        c5 = sec5.content
        self._codec_info = {}
        for label_text, key in [("Codec", "codec"), ("Frequency", "sample_freq"),
                                ("Channels", "channel_mode"), ("Bitrate", "bitrate")]:
            row = ctk.CTkFrame(c5, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text=label_text, text_color=TEXT_DIM).grid(
                row=0, column=0, sticky="w")
            lbl = ctk.CTkLabel(row, text="--", text_color=TEXT)
            lbl.grid(row=0, column=1, sticky="e")
            self._codec_info[key] = lbl

    def refresh(self):
        if not self.bt.connected:
            return
        self._loading = True
        self._status("Reading audio...")
        self.bt.run(tc.cmd_eq_get, callback=self._cb(self._on_eq_data))
        self.bt.run(tc.cmd_spatial_get, callback=self._cb(self._on_spatial_data))
        self.bt.run(tc.generic_get, tc.GENERIC_CMDS["a2dp"],
                    callback=self._cb(self._on_a2dp_data))
        self.bt.run(tc.generic_get, tc.GENERIC_CMDS["buffer"],
                    callback=self._cb(self._on_buffer_data))
        self.bt.run(tc.cmd_codec_get, callback=self._cb(self._on_codec_info))

    def populate_from_batch(self, data: dict):
        super().populate_from_batch(data)
        self._loading = True
        try:
            if "spatial" in data:
                self._spatial.set(data["spatial"].get("mode") == "on")
                self._head_tracking.set(data["spatial"].get("head_tracking") == "on")
            if "buffer" in data:
                buf_map = {"auto": "Auto", "music": "Music", "video": "Video"}
                self._buffer.set(buf_map.get(data["buffer"].get("mode", "auto"), "Auto"))
        finally:
            self._loading = False
        # EQ is not in batch, GET via Airoha PEQ
        if self.bt.connected:
            self.bt.run(tc.cmd_eq_get, callback=self._cb(self._on_eq_data))

    def _on_eq_data(self, result, error):
        if error:
            return
        mode = result.get("sound_mode", "off")
        label = EQ_LABELS.get(mode, mode)
        self._eq_var.set(label)

    def _on_spatial_data(self, result, error):
        if error:
            self._loading = False
            return
        self._spatial.set(result.get("mode") == "on")
        self._head_tracking.set(result.get("head_tracking") == "on")
        self._loading = False
        self._status("Audio updated")

    def _on_a2dp_data(self, result, error):
        if error:
            return
        label = CODEC_LABELS.get(result.get("label", "sbc"), result.get("label", "sbc"))
        self._codec_var.set(label)

    def _on_buffer_data(self, result, error):
        if error:
            return
        buf_map = {"auto": "Auto", "music": "Music", "video": "Video"}
        self._buffer.set(buf_map.get(result.get("label", "auto"), "Auto"))

    def _on_codec_info(self, result, error):
        if error:
            return
        for key, lbl in self._codec_info.items():
            val = result.get(key, "--")
            if key == "bitrate" and isinstance(val, int):
                val = f"{val} kbps" if val > 0 else "N/A"
            lbl.configure(text=str(val))

    def _on_eq(self, value):
        if self._loading or not self.bt.connected:
            return
        rev = {v: k for k, v in EQ_LABELS.items()}
        mode = rev.get(value)
        if mode:
            self._status(f"EQ -> {value}...")
            self.bt.run(tc.cmd_eq_set, mode,
                        callback=self._cb(lambda r, e: self._status(
                            f"EQ: {value}" if not e else f"Error: {e}")))

    def _on_spatial(self):
        if self._loading or not self.bt.connected:
            return
        mode = "on" if self._spatial.get() else "off"
        self._status(f"Spatial -> {mode}...")
        self.bt.run(tc.cmd_spatial_set, mode,
                    callback=self._cb(lambda r, e: self._status(
                        f"Spatial: {mode}" if not e else f"Error: {e}")))

    def _on_head_tracking(self):
        if self._loading or not self.bt.connected:
            return
        ht = "on" if self._head_tracking.get() else "off"
        spatial = "on" if self._spatial.get() else "off"
        self._status(f"Head Tracking -> {ht}...")
        self.bt.run(tc.cmd_spatial_set, spatial, ht,
                    callback=self._cb(lambda r, e: self._status(
                        f"Head Tracking: {ht}" if not e else f"Error: {e}")))

    def _on_codec(self, value):
        if self._loading or not self.bt.connected:
            return
        rev = {v: k for k, v in CODEC_LABELS.items()}
        codec = rev.get(value)
        if codec:
            self._status(f"Codec -> {value}...")
            self.bt.run(tc.generic_set, tc.GENERIC_CMDS["a2dp"], codec,
                        callback=self._cb(lambda r, e: self._status(
                            f"Codec: {value}" if not e else f"Error: {e}")))

    def _on_buffer(self, value):
        if self._loading or not self.bt.connected:
            return
        buf_map = {"Auto": "auto", "Music": "music", "Video": "video"}
        mode = buf_map.get(value)
        if mode:
            self._status(f"Buffer -> {value}...")
            self.bt.run(tc.generic_set, tc.GENERIC_CMDS["buffer"], mode,
                        callback=self._cb(lambda r, e: self._status(
                            f"Buffer: {value}" if not e else f"Error: {e}")))

    def _iter_controls(self):
        return [self._eq_menu, self._spatial.switch, self._head_tracking.switch,
                self._codec_menu, self._buffer]


# --- Connectivity Page ---

class ConnectivityPage(BasePage):
    BATCH_COMPLETE = True

    def __init__(self, parent, app):
        super().__init__(parent, app)

        # Multipoint
        sec = Section(self, "Multipoint")
        sec.pack(fill="x")
        self._multipoint = ctk.CTkSegmentedButton(
            sec.content, values=["Off", "On", "Triple"],
            command=self._on_multipoint)
        self._multipoint.pack(fill="x", padx=8, pady=8)

        # LE Audio
        sec2 = Section(self, "LE Audio")
        sec2.pack(fill="x")
        self._le_audio = ToggleRow(sec2.content, "LE Audio", command=self._on_le_audio)
        self._le_audio.pack(fill="x")

        # Switch playback
        sec3 = Section(self, "Playback Switch")
        sec3.pack(fill="x")
        self._switch_playing = ToggleRow(sec3.content, "Auto switch", command=self._on_switch_playing)
        self._switch_playing.pack(fill="x")

        # Connected devices
        sec4 = Section(self, "Connected Devices")
        sec4.pack(fill="x")
        c4 = sec4.content
        self._devices_text = ctk.CTkTextbox(c4, height=100, state="disabled")
        self._devices_text.pack(fill="x", padx=8, pady=4)
        btn = ctk.CTkButton(c4, text="Refresh", command=self._refresh_devices, width=100)
        btn.pack(pady=(0, 8))
        self._refresh_btn = btn

    def refresh(self):
        if not self.bt.connected:
            return
        self._loading = True
        self._status("Reading connectivity...")
        self.bt.run(tc.generic_get, tc.GENERIC_CMDS["multipoint"],
                    callback=self._cb(self._on_multipoint_data))
        self.bt.run(tc.generic_get, tc.GENERIC_CMDS["le-audio"],
                    callback=self._cb(self._on_le_data))
        self.bt.run(tc.generic_get, tc.GENERIC_CMDS["switch-playing"],
                    callback=self._cb(self._on_switch_data))
        self._refresh_devices()

    def populate_from_batch(self, data: dict):
        super().populate_from_batch(data)
        self._loading = True
        try:
            if "multipoint" in data:
                mp_map = {"off": "Off", "on": "On", "triple": "Triple"}
                self._multipoint.set(mp_map.get(data["multipoint"].get("mode", "off"), "Off"))
            if "le_audio" in data:
                self._le_audio.set(data["le_audio"].get("mode") == "on")
            if "switch_playing" in data:
                self._switch_playing.set(data["switch_playing"].get("mode") == "on")
        finally:
            self._loading = False

    def _on_multipoint_data(self, result, error):
        if error:
            self._loading = False
            return
        mp_map = {"off": "Off", "on": "On", "triple": "Triple"}
        self._multipoint.set(mp_map.get(result.get("label", "off"), "Off"))
        self._loading = False
        self._status("Connectivity updated")

    def _on_le_data(self, result, error):
        if error:
            return
        self._le_audio.set(result.get("label") == "on")

    def _on_switch_data(self, result, error):
        if error:
            return
        self._switch_playing.set(result.get("label") == "on")

    def _refresh_devices(self):
        if not self.bt.connected:
            return
        self.bt.run(tc.cmd_connected_devices_get, callback=self._cb(self._on_devices))

    def _on_devices(self, result, error):
        self._devices_text.configure(state="normal")
        self._devices_text.delete("0.0", "end")
        if error:
            self._devices_text.insert("0.0", f"Error: {error}")
        else:
            devices = result.get("devices", [])
            if devices:
                self._devices_text.insert("0.0", "\n".join(devices))
            else:
                self._devices_text.insert("0.0", "No devices")
        self._devices_text.configure(state="disabled")

    def _on_multipoint(self, value):
        if self._loading or not self.bt.connected:
            return
        mp_map = {"Off": "off", "On": "on", "Triple": "triple"}
        mode = mp_map.get(value)
        if mode:
            self._status(f"Multipoint -> {value}...")
            self.bt.run(tc.generic_set, tc.GENERIC_CMDS["multipoint"], mode,
                        callback=self._cb(lambda r, e: self._status(
                            f"Multipoint: {value}" if not e else f"Error: {e}")))

    def _on_le_audio(self):
        if self._loading or not self.bt.connected:
            return
        mode = "on" if self._le_audio.get() else "off"
        self._status(f"LE Audio -> {mode}...")
        self.bt.run(tc.generic_set, tc.GENERIC_CMDS["le-audio"], mode,
                    callback=self._cb(lambda r, e: self._status(
                        f"LE Audio: {mode}" if not e else f"Error: {e}")))

    def _on_switch_playing(self):
        if self._loading or not self.bt.connected:
            return
        mode = "on" if self._switch_playing.get() else "off"
        self._status(f"Switch -> {mode}...")
        self.bt.run(tc.generic_set, tc.GENERIC_CMDS["switch-playing"], mode,
                    callback=self._cb(lambda r, e: self._status(
                        f"Switch: {mode}" if not e else f"Error: {e}")))

    def _iter_controls(self):
        return [self._multipoint, self._le_audio.switch,
                self._switch_playing.switch, self._refresh_btn]


# --- Settings Page ---

class SettingsPage(BasePage):

    def __init__(self, parent, app):
        super().__init__(parent, app)

        # LED
        sec = Section(self, "LED")
        sec.pack(fill="x")
        self._led = ToggleRow(sec.content, "Indicator LED", command=self._on_led)
        self._led.pack(fill="x")

        # Wearing detection
        sec2 = Section(self, "Wearing Detection")
        sec2.pack(fill="x")
        c2 = sec2.content
        self._wearing = ToggleRow(c2, "Detection", command=self._on_wearing)
        self._wearing.pack(fill="x")
        self._wearing_music = ToggleRow(c2, "  Pause music", command=self._on_wearing_sub)
        self._wearing_music.pack(fill="x")
        self._wearing_touch = ToggleRow(c2, "  Touch control", command=self._on_wearing_sub)
        self._wearing_touch.pack(fill="x")
        self._wearing_replay = ToggleRow(c2, "  Playback resume", command=self._on_wearing_sub)
        self._wearing_replay.pack(fill="x")

        # Auto power off
        sec3 = Section(self, "Auto Power Off")
        sec3.pack(fill="x")
        c3 = sec3.content
        row = ctk.CTkFrame(c3, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=8)
        row.grid_columnconfigure(0, weight=1)
        self._auto_off = ToggleRow(row, "Auto off", command=self._on_auto_off)
        self._auto_off.grid(row=0, column=0, sticky="ew")
        self._auto_off_min = ctk.CTkOptionMenu(
            row, values=["5", "10", "30", "60"], width=80,
            command=self._on_auto_off_min)
        self._auto_off_min.grid(row=0, column=1, padx=8)
        ctk.CTkLabel(row, text="min", text_color=TEXT_DIM).grid(row=0, column=2)

        # Safe volume
        sec4 = Section(self, "Safe Volume")
        sec4.pack(fill="x")
        c4 = sec4.content
        row4 = ctk.CTkFrame(c4, fg_color="transparent")
        row4.pack(fill="x", padx=8, pady=8)
        row4.grid_columnconfigure(0, weight=1)
        self._safe_vol_slider = ctk.CTkSlider(
            row4, from_=0, to=100, number_of_steps=100,
            command=self._on_safe_vol_slide)
        self._safe_vol_slider.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._safe_vol_label = ctk.CTkLabel(row4, text="--", width=40, text_color=TEXT)
        self._safe_vol_label.grid(row=0, column=1)

        # Language
        sec5 = Section(self, "Announcement Language")
        sec5.pack(fill="x")
        lang_values = list(LANGUAGE_LABELS.values())
        self._lang_var = ctk.StringVar(value="--")
        self._lang_menu = ctk.CTkOptionMenu(
            sec5.content, values=lang_values, variable=self._lang_var,
            command=self._on_language)
        self._lang_menu.pack(fill="x", padx=8, pady=8)

        # Ringtone during call
        sec6 = Section(self, "Call")
        sec6.pack(fill="x")
        self._ringtone = ToggleRow(sec6.content, "Ringtone during call", command=self._on_ringtone)
        self._ringtone.pack(fill="x")

    def refresh(self):
        if not self.bt.connected:
            return
        self._loading = True
        self._status("Reading settings...")
        # LED (cmd 19) and Safe Volume (cmd 92) do not respond to GET on EAH-AZ100
        self.bt.run(tc.cmd_wearing_get, callback=self._cb(self._on_wearing_data))
        self.bt.run(tc.cmd_auto_power_off_get, callback=self._cb(self._on_auto_off_data))
        self.bt.run(tc.cmd_lang_get, callback=self._cb(self._on_lang_data))
        self.bt.run(tc.generic_get, tc.GENERIC_CMDS["ringtone-talking"],
                    callback=self._cb(self._on_ringtone_data))

    def populate_from_batch(self, data: dict):
        super().populate_from_batch(data)
        self._loading = True
        try:
            if "led" in data:
                self._led.set(data["led"].get("mode") == "on")
            if "wearing" in data:
                w = data["wearing"]
                self._wearing.set(w.get("detection") == "on")
                self._wearing_music.set(w.get("music") == "on")
                self._wearing_touch.set(w.get("touch") == "on")
                self._wearing_replay.set(w.get("replay") == "on")
            if "auto_power_off" in data:
                apo = data["auto_power_off"]
                self._auto_off.set(apo.get("mode") == "on")
                mins = apo.get("minutes", 30)
                self._auto_off_min.set(str(mins))
            if "safe_volume" in data:
                val = data["safe_volume"].get("value", 0)
                self._safe_vol_slider.set(val)
                self._safe_vol_label.configure(text=str(val))
            # Language is not in batch, GET via cmd 37
            if "ringtone_talking" in data:
                self._ringtone.set(data["ringtone_talking"].get("mode") == "on")
        finally:
            self._loading = False
        # Language is not in batch, GET via cmd 37
        if self.bt.connected:
            self.bt.run(tc.cmd_lang_get, callback=self._cb(self._on_lang_data))

    def _on_wearing_data(self, result, error):
        if error:
            self._loading = False
            return
        self._wearing.set(result.get("wearing_detection") == "on")
        self._wearing_music.set(result.get("music") == "on")
        self._wearing_touch.set(result.get("touch") == "on")
        self._wearing_replay.set(result.get("replay") == "on")
        self._loading = False
        self._status("Settings updated")

    def _on_auto_off_data(self, result, error):
        if error:
            return
        self._auto_off.set(result.get("mode") == "on")
        self._auto_off_min.set(str(result.get("minutes", 30)))

    def _on_lang_data(self, result, error):
        if error:
            return
        lang = result.get("label", "en")
        label = LANGUAGE_LABELS.get(lang, lang)
        self._lang_var.set(label)

    def _on_ringtone_data(self, result, error):
        if error:
            return
        self._ringtone.set(result.get("label") == "on")

    def _on_led(self):
        if self._loading or not self.bt.connected:
            return
        mode = "on" if self._led.get() else "off"
        self.bt.run(tc.generic_set, tc.GENERIC_CMDS["led"], mode,
                    callback=self._cb(lambda r, e: self._status(
                        f"LED: {mode}" if not e else f"Error: {e}")))

    def _on_wearing(self):
        if self._loading or not self.bt.connected:
            return
        mode = "on" if self._wearing.get() else "off"
        self.bt.run(tc.cmd_wearing_set, mode,
                    callback=self._cb(lambda r, e: self._status(
                        f"Detection: {mode}" if not e else f"Error: {e}")))

    def _on_wearing_sub(self):
        if self._loading or not self.bt.connected:
            return
        self.bt.run(
            tc.cmd_wearing_set, None,
            "on" if self._wearing_music.get() else "off",
            "on" if self._wearing_touch.get() else "off",
            "on" if self._wearing_replay.get() else "off",
            callback=self._cb(lambda r, e: self._status(
                "Detection updated" if not e else f"Error: {e}")))

    def _on_auto_off(self):
        if self._loading or not self.bt.connected:
            return
        mode = "on" if self._auto_off.get() else "off"
        mins = int(self._auto_off_min.get())
        self.bt.run(tc.cmd_auto_power_off_set, mode, mins,
                    callback=self._cb(lambda r, e: self._status(
                        f"Auto off: {mode}" if not e else f"Error: {e}")))

    def _on_auto_off_min(self, value):
        if self._loading or not self.bt.connected:
            return
        if self._auto_off.get():
            self.bt.run(tc.cmd_auto_power_off_set, "on", int(value),
                        callback=self._cb(lambda r, e: self._status(
                            f"Auto off: {value} min" if not e else f"Error: {e}")))

    def _on_safe_vol_slide(self, value):
        if self._loading:
            return
        self._safe_vol_label.configure(text=str(int(value)))

    def _on_safe_vol_release(self, _event=None):
        if self._loading or not self.bt.connected:
            return
        val = int(self._safe_vol_slider.get())
        self.bt.run(tc.generic_set, tc.GENERIC_CMDS["safe-volume"], val,
                    callback=self._cb(lambda r, e: self._status(
                        f"Safe volume: {val}" if not e else f"Error: {e}")))

    def _on_language(self, value):
        if self._loading or not self.bt.connected:
            return
        rev = {v: k for k, v in LANGUAGE_LABELS.items()}
        lang = rev.get(value)
        if lang:
            self._status(f"Language -> {value}...")
            self.bt.run(tc.cmd_lang_set, lang,
                        callback=self._cb(lambda r, e: self._status(
                            f"Language: {value}" if not e else f"Error: {e}")))

    def _on_ringtone(self):
        if self._loading or not self.bt.connected:
            return
        mode = "on" if self._ringtone.get() else "off"
        self.bt.run(tc.generic_set, tc.GENERIC_CMDS["ringtone-talking"], mode,
                    callback=self._cb(lambda r, e: self._status(
                        f"Ringtone: {mode}" if not e else f"Error: {e}")))

    def _iter_controls(self):
        return [self._led.switch, self._wearing.switch,
                self._wearing_music.switch, self._wearing_touch.switch,
                self._wearing_replay.switch, self._auto_off.switch,
                self._auto_off_min, self._safe_vol_slider,
                self._lang_menu, self._ringtone.switch]


# --- Voice Page ---

class VoicePage(BasePage):

    def __init__(self, parent, app):
        super().__init__(parent, app)

        # Voice assistant
        sec = Section(self, "Voice Assistant")
        sec.pack(fill="x")
        self._assistant = ctk.CTkSegmentedButton(
            sec.content, values=["Google", "Alexa", "Off"],
            command=self._on_assistant)
        self._assistant.pack(fill="x", padx=8, pady=8)

        # Call noise reduction
        sec2 = Section(self, "Noise Reduction (Call)")
        sec2.pack(fill="x")
        self._noise_red = ctk.CTkSegmentedButton(
            sec2.content, values=["Normal", "High"],
            command=self._on_noise_red)
        self._noise_red.pack(fill="x", padx=8, pady=8)

        # ANC change announcement
        sec3 = Section(self, "ANC Change Announcement")
        sec3.pack(fill="x")
        self._vp_outside = ctk.CTkSegmentedButton(
            sec3.content, values=["Tone", "Voice"],
            command=self._on_vp_outside)
        self._vp_outside.pack(fill="x", padx=8, pady=8)

        # Connection announcement
        sec4 = Section(self, "Connection Announcement")
        sec4.pack(fill="x")
        vp_values = [f"{i}: {tc.VP_CONNECTED_MODES[i]}" for i in range(8)]
        self._vp_connected_var = ctk.StringVar(value=vp_values[0])
        self._vp_connected = ctk.CTkOptionMenu(
            sec4.content, values=vp_values, variable=self._vp_connected_var,
            command=self._on_vp_connected)
        self._vp_connected.pack(fill="x", padx=8, pady=8)

        # Announcement volume
        sec5 = Section(self, "Announcement Volume")
        sec5.pack(fill="x")
        c5 = sec5.content
        row = ctk.CTkFrame(c5, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=8)
        row.grid_columnconfigure(0, weight=1)
        self._vp_vol_slider = ctk.CTkSlider(
            row, from_=0, to=15, number_of_steps=15,
            command=self._on_vp_vol_slide)
        self._vp_vol_slider.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._vp_vol_label = ctk.CTkLabel(row, text="--", width=30, text_color=TEXT)
        self._vp_vol_label.grid(row=0, column=1)

        # Just My Voice
        sec6 = Section(self, "Just My Voice")
        sec6.pack(fill="x")
        c6 = sec6.content
        row6 = ctk.CTkFrame(c6, fg_color="transparent")
        row6.pack(fill="x", padx=8, pady=8)
        row6.grid_columnconfigure(0, weight=1)
        self._jmv = ToggleRow(row6, "Just My Voice", command=self._on_jmv)
        self._jmv.grid(row=0, column=0, sticky="ew")
        self._jmv_start_btn = ctk.CTkButton(
            row6, text="Start", width=80, command=self._on_jmv_start)
        self._jmv_start_btn.grid(row=0, column=1, padx=8)

    def refresh(self):
        if not self.bt.connected:
            return
        self._loading = True
        self._status("Reading voice...")
        self.bt.run(tc.generic_get, tc.GENERIC_CMDS["assistant"],
                    callback=self._cb(self._on_assistant_data))
        self.bt.run(tc.generic_get, tc.GENERIC_CMDS["noise-reduction"],
                    callback=self._cb(self._on_noise_data))
        self.bt.run(tc.generic_get, tc.GENERIC_CMDS["jmv"],
                    callback=self._cb(self._on_jmv_data))

    def populate_from_batch(self, data: dict):
        super().populate_from_batch(data)
        self._loading = True
        try:
            if "assistant" in data:
                a_map = {"google": "Google", "alexa": "Alexa", "off": "Off", "unset": "Off"}
                self._assistant.set(a_map.get(data["assistant"].get("mode", "off"), "Off"))
            if "noise_reduction" in data:
                nr_map = {"normal": "Normal", "high": "High"}
                self._noise_red.set(nr_map.get(
                    data["noise_reduction"].get("mode", "normal"), "Normal"))
            if "jmv" in data:
                self._jmv.set(data["jmv"].get("mode") == "on")
        finally:
            self._loading = False

    def _on_assistant_data(self, result, error):
        if error:
            self._loading = False
            return
        a_map = {"google": "Google", "alexa": "Alexa", "off": "Off", "unset": "Off"}
        self._assistant.set(a_map.get(result.get("label", "off"), "Off"))
        self._loading = False
        self._status("Voice updated")

    def _on_noise_data(self, result, error):
        if error:
            return
        nr_map = {"normal": "Normal", "high": "High"}
        self._noise_red.set(nr_map.get(result.get("label", "normal"), "Normal"))

    def _on_jmv_data(self, result, error):
        if error:
            return
        self._jmv.set(result.get("label") == "on")

    def _on_assistant(self, value):
        if self._loading or not self.bt.connected:
            return
        a_map = {"Google": "google", "Alexa": "alexa", "Off": "off"}
        mode = a_map.get(value)
        if mode:
            self._status(f"Assistant -> {value}...")
            self.bt.run(tc.generic_set, tc.GENERIC_CMDS["assistant"], mode,
                        callback=self._cb(lambda r, e: self._status(
                            f"Assistant: {value}" if not e else f"Error: {e}")))

    def _on_noise_red(self, value):
        if self._loading or not self.bt.connected:
            return
        nr_map = {"Normal": "normal", "High": "high"}
        mode = nr_map.get(value)
        if mode:
            self._status(f"Noise reduction -> {value}...")
            self.bt.run(tc.generic_set, tc.GENERIC_CMDS["noise-reduction"], mode,
                        callback=self._cb(lambda r, e: self._status(
                            f"Noise reduction: {value}" if not e else f"Error: {e}")))

    def _on_vp_outside(self, value):
        if self._loading or not self.bt.connected:
            return
        vp_map = {"Tone": "tone", "Voice": "voice"}
        mode = vp_map.get(value)
        if mode:
            self._status(f"ANC announcement -> {value}...")
            self.bt.run(tc.cmd_vp_outside_set, mode,
                        callback=self._cb(lambda r, e: self._status(
                            f"ANC announcement: {value}" if not e else f"Error: {e}")))

    def _on_vp_connected(self, value):
        if self._loading or not self.bt.connected:
            return
        idx = int(value.split(":")[0])
        self._status(f"Connection announcement -> {idx}...")
        self.bt.run(tc.cmd_vp_connected_set, idx,
                    callback=self._cb(lambda r, e: self._status(
                        f"Connection announcement: {idx}" if not e else f"Error: {e}")))

    def _on_vp_vol_slide(self, value):
        if self._loading:
            return
        self._vp_vol_label.configure(text=str(int(value)))

    def _on_vp_vol_release(self, _event=None):
        if self._loading or not self.bt.connected:
            return
        vol = int(self._vp_vol_slider.get())
        self.bt.run(tc.cmd_vp_volume_set, vol,
                    callback=self._cb(lambda r, e: self._status(
                        f"Announcement volume: {vol}" if not e else f"Error: {e}")))

    def _on_jmv(self):
        if self._loading or not self.bt.connected:
            return
        mode = "on" if self._jmv.get() else "off"
        self.bt.run(tc.generic_set, tc.GENERIC_CMDS["jmv"], mode,
                    callback=self._cb(lambda r, e: self._status(
                        f"JMV: {mode}" if not e else f"Error: {e}")))

    def _on_jmv_start(self):
        if not self.bt.connected:
            return
        self._status("JMV calibration...")
        self.bt.run(tc.cmd_jmv_start,
                    callback=self._cb(lambda r, e: self._status(
                        "JMV calibration OK" if not e else f"Error: {e}")))

    def _iter_controls(self):
        return [self._assistant, self._noise_red, self._vp_outside,
                self._vp_connected, self._vp_vol_slider,
                self._jmv.switch, self._jmv_start_btn]


# --- Info Page ---

class InfoPage(BasePage):

    def __init__(self, parent, app):
        super().__init__(parent, app)

        # Firmware
        sec = Section(self, "Firmware")
        sec.pack(fill="x")
        c = sec.content
        self._fw_labels = {}
        for label_text, key in [("SDK Version", "sdk_version"), ("SoC", "soc_name"),
                                ("SDK Name", "sdk_name"), ("Build", "build_date")]:
            row = ctk.CTkFrame(c, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text=label_text, text_color=TEXT_DIM).grid(
                row=0, column=0, sticky="w")
            lbl = ctk.CTkLabel(row, text="--", text_color=TEXT)
            lbl.grid(row=0, column=1, sticky="e")
            self._fw_labels[key] = lbl

        # Device
        sec2 = Section(self, "Device")
        sec2.pack(fill="x")
        c2 = sec2.content
        row2 = ctk.CTkFrame(c2, fg_color="transparent")
        row2.pack(fill="x", padx=8, pady=4)
        row2.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(row2, text="Color", text_color=TEXT_DIM).grid(
            row=0, column=0, sticky="w")
        self._color_label = ctk.CTkLabel(row2, text="--", text_color=TEXT)
        self._color_label.grid(row=0, column=1, sticky="e")

        # Full status
        sec3 = Section(self, "Full Status (JSON)")
        sec3.pack(fill="x")
        self._status_text = ctk.CTkTextbox(sec3.content, height=300, state="disabled")
        self._status_text.pack(fill="both", padx=8, pady=8, expand=True)

        btn = ctk.CTkButton(self, text="Refresh", command=self.refresh, width=120)
        btn.pack(pady=12)
        self._refresh_btn = btn

    def refresh(self):
        if not self.bt.connected:
            return
        self._status("Reading info...")
        self.bt.run(tc.cmd_firmware_info_get, callback=self._cb(self._on_firmware))
        self.bt.run(tc.cmd_color_get, callback=self._cb(self._on_color))
        self.bt.run(tc.cmd_status_batch, callback=self._cb(self._on_status))

    def _on_firmware(self, result, error):
        if error:
            self._status(f"Firmware error: {error}")
            return
        for key, lbl in self._fw_labels.items():
            lbl.configure(text=result.get(key, "--"))
        self._status("Info updated")

    def _on_color(self, result, error):
        if error:
            return
        self._color_label.configure(text=result.get("color", "--"))

    def _on_status(self, result, error):
        self._status_text.configure(state="normal")
        self._status_text.delete("0.0", "end")
        if error:
            self._status_text.insert("0.0", f"Error: {error}")
        else:
            self._status_text.insert("0.0", json.dumps(result, indent=2, ensure_ascii=False))
        self._status_text.configure(state="disabled")

    def _iter_controls(self):
        return [self._refresh_btn]


# --- Tools Page ---

class ToolsPage(BasePage):

    def __init__(self, parent, app):
        super().__init__(parent, app)

        # Find earbuds
        sec = Section(self, "Find Earbuds")
        sec.pack(fill="x")
        c = sec.content
        self._blink_cb = ctk.CTkCheckBox(c, text="Blink")
        self._blink_cb.pack(anchor="w", padx=8, pady=2)
        self._ring_cb = ctk.CTkCheckBox(c, text="Ring")
        self._ring_cb.pack(anchor="w", padx=8, pady=2)
        self._find_target = ctk.CTkSegmentedButton(
            c, values=["Agent", "Partner", "Both"])
        self._find_target.set("Both")
        self._find_target.pack(fill="x", padx=8, pady=4)
        self._find_btn = ctk.CTkButton(
            c, text="Find", command=self._on_find)
        self._find_btn.pack(fill="x", padx=8, pady=(4, 8))

        # Power off
        sec2 = Section(self, "Power")
        sec2.pack(fill="x")
        self._power_btn = ctk.CTkButton(
            sec2.content, text="Power off earbuds",
            fg_color=RED, hover_color="#c0392b",
            command=self._on_power_off)
        self._power_btn.pack(fill="x", padx=8, pady=8)

    def _on_find(self):
        if not self.bt.connected:
            return
        blink = bool(self._blink_cb.get())
        ring = bool(self._ring_cb.get())
        target_map = {"Agent": "agent", "Partner": "partner", "Both": "both"}
        target = target_map.get(self._find_target.get(), "both")
        self._status("Locating...")
        self.bt.run(tc.cmd_find_me, blink, ring, target,
                    callback=self._cb(lambda r, e: self._status(
                        "Location sent" if not e else f"Error: {e}")))

    def _on_power_off(self):
        if not self.bt.connected:
            return
        dialog = ctk.CTkInputDialog(
            text="Type 'yes' to confirm power off",
            title="Confirm Power Off")
        result = dialog.get_input()
        if result and result.strip().lower() == "yes":
            self._status("Powering off...")
            self.bt.run(tc.cmd_power_off,
                        callback=self._cb(lambda r, e: self._status(
                            "Earbuds powered off" if not e else f"Error: {e}")))

    def _iter_controls(self):
        return [self._blink_cb, self._ring_cb, self._find_target,
                self._find_btn, self._power_btn]


# ---------------------------------------------------------------------------
#  Main application
# ---------------------------------------------------------------------------

class App(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Technics EAH-AZ100")
        self.geometry("900x650")
        self.minsize(700, 500)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.bt = BTWorker()
        self._current_page = None
        self._batch_data = {}

        self._build_layout()
        self._show_page("battery")

    def _build_layout(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # --- Header ---
        header = ctk.CTkFrame(self, height=48, fg_color=BG_HEADER, corner_radius=0)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header, text="TECHNICS EAH-AZ100",
            font=ctk.CTkFont(size=16, weight="bold"), text_color=TEXT,
        ).grid(row=0, column=0, padx=12, pady=8)

        right_frame = ctk.CTkFrame(header, fg_color="transparent")
        right_frame.grid(row=0, column=2, padx=12, pady=8)

        self._status_dot = ctk.CTkLabel(
            right_frame, text="\u25cf", text_color=RED,
            font=ctk.CTkFont(size=14))
        self._status_dot.pack(side="left", padx=(0, 4))
        self._conn_label = ctk.CTkLabel(
            right_frame, text="Disconnected", text_color=TEXT_DIM)
        self._conn_label.pack(side="left", padx=(0, 8))
        self._conn_btn = ctk.CTkButton(
            right_frame, text="Connect", width=100,
            command=self._toggle_connection)
        self._conn_btn.pack(side="left")

        # --- Sidebar ---
        sidebar = ctk.CTkFrame(self, width=120, fg_color=BG_SIDEBAR, corner_radius=0)
        sidebar.grid(row=1, column=0, sticky="ns")
        sidebar.grid_propagate(False)

        self._nav_btns = {}
        for i, (label, key) in enumerate(PAGES):
            btn = ctk.CTkButton(
                sidebar, text=label, fg_color="transparent",
                text_color=TEXT_DIM, hover_color=ACCENT_HOVER,
                anchor="w", height=36,
                command=lambda k=key: self._show_page(k))
            btn.pack(fill="x", padx=4, pady=1)
            self._nav_btns[key] = btn

        # --- Content ---
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)

        self._pages: dict[str, BasePage] = {
            "battery": BatteryPage(self._content, self),
            "anc": ANCPage(self._content, self),
            "audio": AudioPage(self._content, self),
            "connectivity": ConnectivityPage(self._content, self),
            "settings": SettingsPage(self._content, self),
            "voice": VoicePage(self._content, self),
            "info": InfoPage(self._content, self),
            "tools": ToolsPage(self._content, self),
        }

        for page in self._pages.values():
            page.grid(row=0, column=0, sticky="nsew")
            page.grid_remove()

        # --- Status bar ---
        self._status_bar = ctk.CTkLabel(
            self, text="Ready", height=24, anchor="w",
            text_color=TEXT_DIM, font=ctk.CTkFont(size=11))
        self._status_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8)

        # Bind slider releases
        anc_page = self._pages["anc"]
        anc_page._nc_slider.bind("<ButtonRelease-1>", anc_page._on_nc_slider_release)
        settings_page = self._pages["settings"]
        settings_page._safe_vol_slider.bind("<ButtonRelease-1>", settings_page._on_safe_vol_release)
        voice_page = self._pages["voice"]
        voice_page._vp_vol_slider.bind("<ButtonRelease-1>", voice_page._on_vp_vol_release)

    def _show_page(self, key: str):
        for k, btn in self._nav_btns.items():
            if k == key:
                btn.configure(fg_color=ACCENT, text_color=TEXT)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_DIM)

        if self._current_page:
            self._pages[self._current_page].grid_remove()

        self._current_page = key
        page = self._pages[key]
        page.grid()

        if self.bt.connected:
            if self._batch_data and not page._populated:
                page.populate_from_batch(self._batch_data)
            if not (page.BATCH_COMPLETE and page._populated):
                page.refresh()

    def _toggle_connection(self):
        if self.bt.connected:
            self.bt.disconnect()
            self._on_disconnected()
        else:
            self._conn_btn.configure(state="disabled", text="Searching...")
            self.set_status("Searching for Technics earbuds...")

            def _discover_and_connect():
                address = tc.discover_device()
                if not address:
                    self.after(0, lambda: self._on_connect_result(
                        False, Exception("No Technics earbuds found")))
                    return
                self.after(0, lambda: self.set_status(f"Connecting to {address}..."))
                self.after(0, lambda: self._conn_btn.configure(text="Connecting..."))
                self.bt.connect(
                    address, tc.RFCOMM_CHANNEL,
                    callback=lambda ok, err: self.after(0, lambda: self._on_connect_result(ok, err)))

            import threading
            threading.Thread(target=_discover_and_connect, daemon=True).start()

    def _on_connect_result(self, ok: bool, error):
        self._conn_btn.configure(state="normal")
        if ok:
            self._status_dot.configure(text_color=GREEN)
            self._conn_label.configure(text="Connected", text_color=GREEN)
            self._conn_btn.configure(text="Disconnect")
            self.set_status("Connected - loading data...")
            self.bt.run(tc.cmd_status_batch,
                        callback=lambda r, e: self.after(0, lambda: self._on_batch(r, e)))
        else:
            self._status_dot.configure(text_color=RED)
            self._conn_label.configure(text="Disconnected", text_color=TEXT_DIM)
            self._conn_btn.configure(text="Connect")
            self.set_status(f"Connection failed: {error}")

    def _on_batch(self, result, error):
        if error:
            self.set_status(f"Batch error: {error}")
            if self._current_page:
                self._pages[self._current_page].refresh()
            return
        self._batch_data = result
        for page in self._pages.values():
            page.populate_from_batch(result)
        # Only refresh the active page if it has data outside the batch
        if self._current_page:
            page = self._pages[self._current_page]
            if not page.BATCH_COMPLETE:
                page.refresh()
        self.set_status("Data loaded")

    def _on_disconnected(self):
        self._status_dot.configure(text_color=RED)
        self._conn_label.configure(text="Disconnected", text_color=TEXT_DIM)
        self._conn_btn.configure(text="Connect")
        self._batch_data = {}
        self.set_status("Disconnected")

    def set_status(self, msg: str):
        self._status_bar.configure(text=msg)

    def destroy(self):
        self.bt.disconnect()
        super().destroy()


# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------

def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
