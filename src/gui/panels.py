# =============================================================================
# gui/panels.py — Left configuration panel (scrollable + accordion sections)
# =============================================================================
import tkinter as tk
from tkinter import ttk, filedialog
import os

from src.constants import (
    C_BG, C_PANEL, C_PANEL_ALT, C_BORDER, C_BORDER_DARK,
    C_ACCENT, C_ACCENT_LIGHT, C_ACCENT2,
    C_GREEN, C_GREEN_LIGHT, C_AMBER,
    C_TEXT, C_TEXT_MID, C_TEXT_DIM, C_TEXT_DISABLED,
    C_STOP_BG, C_STOP_FG,
    MODE_TEMP_ONLY, MODE_FULL_SWEEP,
    FONT,
)
from src.gui.styles import (
    make_entry_row, make_dropdown_row, make_action_button, make_divider,
    F_BODY, F_SMALL, F_LABEL, F_BOLD, F_TITLE, F_MONO,
)


class AccordionSection:
    def __init__(self, parent, title: str, expanded: bool = True, bg=None):
        self.bg = bg or C_BG
        self.expanded = expanded

        self.wrapper = tk.Frame(parent, bg=self.bg)
        self.wrapper.pack(fill="x", pady=(6, 0))

        hdr = tk.Frame(self.wrapper, bg=C_PANEL_ALT,
                       highlightthickness=1, highlightbackground=C_BORDER)
        hdr.pack(fill="x")

        self._arrow = tk.Label(hdr, text="▾" if expanded else "▸", font=(
            FONT, 9), bg=C_PANEL_ALT, fg=C_TEXT_DIM, cursor="hand2")
        self._arrow.pack(side="left", padx=(8, 2), pady=4)

        self._title_lbl = tk.Label(hdr, text=title, font=(
            FONT, 8, "bold"), bg=C_PANEL_ALT, fg=C_TEXT_MID, cursor="hand2")
        self._title_lbl.pack(side="left", pady=4)

        for w in (hdr, self._arrow, self._title_lbl):
            w.bind("<Button-1>", self._toggle)

        self.content = tk.Frame(self.wrapper, bg=C_PANEL, highlightthickness=1,
                                highlightbackground=C_BORDER, padx=10, pady=8)
        if expanded:
            self.content.pack(fill="x")

    def _toggle(self, event=None):
        self.expanded = not self.expanded
        self._arrow.config(text="▾" if self.expanded else "▸")
        if self.expanded:
            self.content.pack(fill="x")
        else:
            self.content.pack_forget()

    def expand(self):
        if not self.expanded:
            self._toggle()

    def collapse(self):
        if self.expanded:
            self._toggle()


class LeftPanel:
    def __init__(self, parent: tk.Frame, app):
        self.app = app
        self.parent = parent

        self._build_scrollable_canvas()
        self._build_device_status()
        self._build_connections()
        self._build_temp_profile()
        self._build_lcr_section()
        self._build_lcr_advanced_section()  # <--- NEW ADVANCED SECTION
        self._build_output_file()
        self._build_profile_buttons()
        self._build_control_buttons()

    def _build_scrollable_canvas(self):
        self._ctrl_strip = tk.Frame(self.parent, bg=C_BG)
        self._ctrl_strip.pack(side="bottom", fill="x", padx=8, pady=(4, 8))

        scroll_wrapper = tk.Frame(self.parent, bg=C_BG)
        scroll_wrapper.pack(side="top", fill="both", expand=True)

        self._canvas = tk.Canvas(scroll_wrapper, bg=C_BG, bd=0,
                                 highlightthickness=0, yscrollcommand=lambda *a: self._sb.set(*a))
        self._sb = ttk.Scrollbar(
            scroll_wrapper, orient="vertical", command=self._canvas.yview)

        self._sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(self._canvas, bg=C_BG)
        self._window_id = self._canvas.create_window(
            (0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind_all("<Button-4>", self._on_mousewheel)
        self._canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _on_frame_configure(self, event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._window_id, width=event.width)

    def _on_mousewheel(self, event):
        if event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")
        else:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _build_device_status(self):
        sec = AccordionSection(self.inner, "DEVICE STATUS", expanded=True)
        c = sec.content

        oven_row = tk.Frame(c, bg=C_PANEL)
        oven_row.pack(fill="x", pady=3)
        self.dot_oven = tk.Label(oven_row, text="●", font=(
            FONT, 13), bg=C_PANEL, fg=C_TEXT_DIM)
        self.dot_oven.pack(side="left", padx=(0, 6))
        tk.Label(oven_row, text="Eurotherm (Oven)", font=F_LABEL,
                 bg=C_PANEL, fg=C_TEXT).pack(side="left")
        self.lbl_oven_status = tk.Label(
            oven_row, text="Not checked", font=F_SMALL, bg=C_PANEL, fg=C_TEXT_DIM)
        self.lbl_oven_status.pack(side="right")

        lcr_row = tk.Frame(c, bg=C_PANEL)
        lcr_row.pack(fill="x", pady=3)
        self.dot_lcr = tk.Label(lcr_row, text="●", font=(
            FONT, 13), bg=C_PANEL, fg=C_TEXT_DIM)
        self.dot_lcr.pack(side="left", padx=(0, 6))
        self.lbl_lcr_name = tk.Label(
            lcr_row, text="LCR Meter", font=F_LABEL, bg=C_PANEL, fg=C_TEXT)
        self.lbl_lcr_name.pack(side="left")
        self.lbl_lcr_status = tk.Label(
            lcr_row, text="Not checked", font=F_SMALL, bg=C_PANEL, fg=C_TEXT_DIM)
        self.lbl_lcr_status.pack(side="right")

        make_divider(c, bg=C_PANEL)

        btn_row = tk.Frame(c, bg=C_PANEL)
        btn_row.pack(fill="x")
        make_action_button(btn_row, "↺  Refresh Ports",
                           self.app.refresh_resources, side="left")
        make_action_button(btn_row, "⬡  Test Connections",
                           self.app.test_connections, side="right")

    def _build_connections(self):
        sec = AccordionSection(self.inner, "CONNECTIONS", expanded=False)
        c = sec.content
        self.cmb_lcr = make_dropdown_row(c, "LCR Address", bg=C_PANEL)
        self.cmb_oven = make_dropdown_row(c, "Oven Port", bg=C_PANEL)
        self.ent_oven_id = make_entry_row(c, "Oven Modbus ID", "1", bg=C_PANEL)

    def _build_temp_profile(self):
        sec = AccordionSection(
            self.inner, "TEMPERATURE PROFILE", expanded=True)
        c = sec.content
        self.ent_start = make_entry_row(c, "Start Temp (°C)", "30", bg=C_PANEL)
        self.ent_end = make_entry_row(c, "End Temp (°C)", "100", bg=C_PANEL)
        self.ent_tolerance = make_entry_row(
            c, "Tolerance (°C)", "1.0", bg=C_PANEL)
        self.ent_ramp_rate = make_entry_row(
            c, "Ramp (°C/min)", "6.0", bg=C_PANEL)

        self._step_frame = tk.Frame(c, bg=C_PANEL)
        self._step_frame.pack(fill="x")
        self.ent_step = make_entry_row(
            self._step_frame, "Step Size (°C)", "10", bg=C_PANEL)

        self._dwell_frame = tk.Frame(c, bg=C_PANEL)
        self._dwell_frame.pack(fill="x")
        self.ent_dwell = make_entry_row(
            self._dwell_frame, "Dwell (min)", "2", bg=C_PANEL)

    def _build_lcr_section(self):
        self._lcr_section = AccordionSection(
            self.inner, "FREQUENCY SWEEP", expanded=True)
        c = self._lcr_section.content

        self.ent_min = make_entry_row(
            c, "Min Freq (Hz)", "100", bg=C_PANEL, on_key_release=self.app.recalc_stats)
        self.ent_max = make_entry_row(
            c, "Max Freq (Hz)", "100000", bg=C_PANEL, on_key_release=self.app.recalc_stats)
        self.ent_steps = make_entry_row(
            c, "Steps/Decade", "5", bg=C_PANEL, on_key_release=self.app.recalc_stats)
        self.ent_voltage = make_entry_row(
            c, "AC Voltage (V)", "1.0", bg=C_PANEL)

        self.btn_manual = ttk.Button(
            c, text="▶ Run Single Sweep (Manual)", command=self.app.start_manual_sweep)
        self.btn_manual.pack(fill="x", pady=(8, 0), padx=2)

        self.lbl_stats = tk.Label(
            c, text="", font=F_SMALL, bg=C_PANEL, fg=C_ACCENT)
        self.lbl_stats.pack(anchor="e", pady=(4, 0))

    # --- NEW ADVANCED SETTINGS ACCORDION ---
    def _build_lcr_advanced_section(self):
        self._lcr_adv_section = AccordionSection(
            self.inner, "ADVANCED LCR SETTINGS", expanded=False)
        c = self._lcr_adv_section.content

        on_off = ["OFF", "ON"]
        ranges = ["AUTO", "100mΩ", "1Ω", "10Ω", "100Ω",
                  "1kΩ", "10kΩ", "100kΩ", "1MΩ", "10MΩ", "100MΩ"]

        # Measurement Setup
        self.cmb_speed = make_dropdown_row(c, "SPEED", bg=C_PANEL)
        self.cmb_speed['values'] = ["FAST", "MED", "SLOW", "SLOW2"]
        self.cmb_speed.current(1)

        self.ent_avg = make_entry_row(c, "AVG (OFF or num)", "OFF", bg=C_PANEL)
        self.ent_delay = make_entry_row(c, "DELAY (s)", "0.0000", bg=C_PANEL)

        self.cmb_range = make_dropdown_row(c, "RANGE", bg=C_PANEL)
        self.cmb_range['values'] = ranges
        self.cmb_range.current(0)

        self.cmb_lowz = make_dropdown_row(c, "LOW Z", bg=C_PANEL)
        self.cmb_lowz['values'] = on_off
        self.cmb_lowz.current(0)

        self.ent_dcbias = make_entry_row(
            c, "DCBIAS (OFF or V)", "OFF", bg=C_PANEL)

        make_divider(c, bg=C_PANEL)

        # Hardware & Compensation
        self.cmb_cable = make_dropdown_row(c, "CABLE", bg=C_PANEL)
        self.cmb_cable['values'] = ["0m", "1m", "2m", "4m"]
        self.cmb_cable.current(0)

        self.cmb_open = make_dropdown_row(c, "OPEN Comp", bg=C_PANEL)
        self.cmb_open['values'] = on_off
        self.cmb_open.current(0)

        self.cmb_short = make_dropdown_row(c, "SHORT Comp", bg=C_PANEL)
        self.cmb_short['values'] = on_off
        self.cmb_short.current(0)

        self.cmb_load = make_dropdown_row(c, "LOAD Comp", bg=C_PANEL)
        self.cmb_load['values'] = on_off
        self.cmb_load.current(0)

        make_divider(c, bg=C_PANEL)

        # Trigger & Sorting
        self.cmb_sync = make_dropdown_row(c, "SYNC", bg=C_PANEL)
        self.cmb_sync['values'] = on_off
        self.cmb_sync.current(0)

        self.cmb_jsync = make_dropdown_row(c, "J SYNC", bg=C_PANEL)
        self.cmb_jsync['values'] = on_off
        self.cmb_jsync.current(0)

        self.cmb_judge = make_dropdown_row(c, "JUDGE", bg=C_PANEL)
        self.cmb_judge['values'] = on_off
        self.cmb_judge.current(0)

        self.cmb_limit = make_dropdown_row(c, "LIMIT", bg=C_PANEL)
        self.cmb_limit['values'] = on_off
        self.cmb_limit.current(0)

        self.cmb_scale = make_dropdown_row(c, "SCALE", bg=C_PANEL)
        self.cmb_scale['values'] = on_off
        self.cmb_scale.current(0)

    def _build_output_file(self):
        sec = AccordionSection(self.inner, "OUTPUT FILE", expanded=True)
        c = sec.content

        file_row = tk.Frame(c, bg=C_PANEL)
        file_row.pack(fill="x")
        self.ent_filename = tk.Entry(file_row, font=(FONT, 8), width=20, bg=C_PANEL, fg=C_TEXT, insertbackground=C_ACCENT,
                                     relief="solid", bd=1, highlightthickness=1, highlightcolor=C_ACCENT, highlightbackground=C_BORDER)
        self.ent_filename.insert(0, os.path.join(os.getcwd(), "data.csv"))
        self.ent_filename.pack(side="left", fill="x", expand=True)
        ttk.Button(file_row, text="…", style="Action.TButton",
                   command=self._browse_file, width=3).pack(side="right", padx=(4, 0))

    def _build_profile_buttons(self):
        sec = AccordionSection(self.inner, "PROFILE", expanded=False)
        c = sec.content
        row = tk.Frame(c, bg=C_PANEL)
        row.pack(fill="x")
        make_action_button(row, "💾  Save Profile",
                           self.app.save_profile, side="left")
        make_action_button(row, "📂  Load Profile",
                           self.app.load_profile, side="right")

    def _build_control_buttons(self):
        c = self._ctrl_strip
        tk.Frame(c, bg=C_BORDER, height=1).pack(fill="x", pady=(0, 8))

        self.btn_start = ttk.Button(
            c, text="▶   START EXPERIMENT", style="Start.TButton", command=self.app.start_experiment)
        self.btn_start.pack(fill="x", pady=(0, 4))

        self.btn_stop = tk.Button(c, text="⏹   E-STOP", bg=C_STOP_BG, fg=C_STOP_FG, font=(FONT, 10, "bold"), relief="solid",
                                  bd=1, activebackground="#FECACA", activeforeground=C_STOP_FG, command=self.app.stop_experiment, state="disabled")
        self.btn_stop.pack(fill="x")

    def show_lcr_section(self):
        self._lcr_section.wrapper.pack(fill="x", pady=(6, 0))
        self._lcr_adv_section.wrapper.pack(fill="x", pady=(6, 0))
        self._on_frame_configure()

    def hide_lcr_section(self):
        self._lcr_section.wrapper.pack_forget()
        self._lcr_adv_section.wrapper.pack_forget()
        self._on_frame_configure()

    def show_step_dwell(self):
        self._step_frame.pack(fill="x")
        self._dwell_frame.pack(fill="x")
        self._on_frame_configure()

    def hide_step_dwell(self):
        self._step_frame.pack_forget()
        self._dwell_frame.pack_forget()
        self._on_frame_configure()

    def set_lcr_status_unused(self):
        self.dot_lcr.config(fg=C_TEXT_DIM)
        self.lbl_lcr_name.config(fg=C_TEXT_DISABLED)
        self.lbl_lcr_status.config(text="Not used", fg=C_TEXT_DIM)

    def restore_lcr_status(self, status):
        self.lbl_lcr_name.config(fg=C_TEXT)
        if status is None:
            color, text = C_TEXT_DIM, "Not checked"
        elif status:
            color, text = C_GREEN, "Connected"
        else:
            color, text = C_ACCENT2, "Failed"
        self.dot_lcr.config(fg=color)
        self.lbl_lcr_status.config(text=text, fg=color)

    def set_device_status(self, device: str, ok: bool, msg: str = ""):
        color = C_GREEN if ok else C_ACCENT2
        text = ("Connected" if ok else "Failed") + (f" — {msg}" if msg else "")
        if device == "oven":
            self.dot_oven.config(fg=color)
            self.lbl_oven_status.config(text=text, fg=color)
        elif device == "lcr":
            self.dot_lcr.config(fg=color)
            self.lbl_lcr_status.config(text=text, fg=color)

    def _browse_file(self):
        f = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if f:
            self.ent_filename.delete(0, tk.END)
            self.ent_filename.insert(0, f)
