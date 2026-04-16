# =============================================================================
# gui/app.py — MainApp: orchestrates panels, handles callbacks, owns state
# =============================================================================
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import datetime
import json
import math
import os

import pyvisa
import serial.tools.list_ports

from src.constants import (
    C_BG, C_PANEL, C_PANEL_ALT, C_BORDER,
    C_ACCENT, C_ACCENT2, C_GREEN, C_AMBER,
    C_TEXT, C_TEXT_MID, C_TEXT_DIM,
    FONT, MODE_TEMP_ONLY, MODE_FULL_SWEEP
)
from src.gui.styles import make_light_style
from src.gui.panels import LeftPanel
from src.gui.dashboard import Dashboard
from src.core.worker import ExperimentWorker
from src.drivers.lcr_driver import LCRDriver
from src.drivers.eurotherm_driver import EurothermDriver
import sys

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class MainApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("MatTherm Profiler  //  v2.0")
        self.root.geometry("1450x900")
        self.root.configure(bg=C_BG)
        self.root.resizable(True, True)
        try:
            # --- FIXED: Now resolves correctly inside the .exe ---
            self.root.iconbitmap(resource_path(os.path.join("assets", "wee.ico")))
        except Exception:
            pass

        make_light_style()

        self.mode = MODE_TEMP_ONLY
        self.worker = None
        self.status_oven = None
        self.status_lcr = None

        self.time_data, self.pv_data, self.sp_data, self.wsp_data = [], [], [], []

        self._build_chrome()
        self.refresh_resources()
        self.recalc_stats()
        self.set_mode(MODE_TEMP_ONLY)

    def _build_chrome(self):
        top_bar = tk.Frame(self.root, bg=C_PANEL, highlightthickness=1,
                           highlightbackground=C_BORDER, height=48)
        top_bar.pack(fill="x", side="top")
        top_bar.pack_propagate(False)

        tk.Label(top_bar, text="MatTherm Profiler", font=(FONT, 13, "bold"),
                 bg=C_PANEL, fg=C_TEXT).pack(side="left", padx=16, pady=10)

        mode_frame = tk.Frame(top_bar, bg=C_PANEL)
        mode_frame.pack(side="right", padx=16)
        tk.Label(mode_frame, text="Mode:", font=(FONT, 8), bg=C_PANEL,
                 fg=C_TEXT_DIM).pack(side="left", padx=(0, 6))

        self.btn_mode_temp = ttk.Button(
            mode_frame, text="🌡  Temp Only", style="ModeA.TButton", command=lambda: self.set_mode(MODE_TEMP_ONLY))
        self.btn_mode_temp.pack(side="left", padx=2)

        self.btn_mode_full = ttk.Button(
            mode_frame, text="⚡  Full Sweep", style="ModeInactive.TButton", command=lambda: self.set_mode(MODE_FULL_SWEEP))
        self.btn_mode_full.pack(side="left", padx=2)

        body = tk.Frame(self.root, bg=C_BG)
        body.pack(fill="both", expand=True)

        left_container = tk.Frame(body, bg=C_BG, width=310)
        left_container.pack(side="left", fill="y", padx=(8, 4), pady=8)
        left_container.pack_propagate(False)
        self.panel = LeftPanel(left_container, self)

        right_container = tk.Frame(body, bg=C_BG)
        right_container.pack(side="right", fill="both",
                             expand=True, padx=(4, 8), pady=8)
        self.dash = Dashboard(right_container)

    def set_mode(self, mode: str):
        self.mode = mode
        if mode == MODE_TEMP_ONLY:
            self.btn_mode_temp.configure(style="ModeA.TButton")
            self.btn_mode_full.configure(style="ModeInactive.TButton")
            self.panel.hide_lcr_section()
            self.panel.hide_step_dwell()
            self.dash.hide_lcr_panel()
            self.panel.set_lcr_status_unused()
        elif mode == MODE_FULL_SWEEP:
            self.btn_mode_full.configure(style="ModeB.TButton")
            self.btn_mode_temp.configure(style="ModeInactive.TButton")
            self.panel.show_lcr_section()
            self.panel.show_step_dwell()
            self.dash.show_lcr_panel()
            self.panel.restore_lcr_status(self.status_lcr)
        self.recalc_stats()

    def refresh_resources(self):
        try:
            rm = pyvisa.ResourceManager()
            resources = rm.list_resources()
            self.panel.cmb_lcr['values'] = resources
            if resources:
                self.panel.cmb_lcr.current(0)
        except Exception:
            pass
        try:
            ports = [p.device for p in serial.tools.list_ports.comports()]
            self.panel.cmb_oven['values'] = ports
            if ports:
                self.panel.cmb_oven.current(0)
        except Exception:
            pass

    def test_connections(self):
        def _test():
            try:
                drv = EurothermDriver(self.panel.cmb_oven.get(), int(
                    self.panel.ent_oven_id.get()))
                pv = drv.get_pv()
                self.status_oven = True
                self.root.after(0, lambda: self.panel.set_device_status(
                    "oven", True, f"{pv:.1f}°C"))
                self.log_msg(f"Oven OK — PV: {pv:.2f}°C")
            except Exception as e:
                self.status_oven = False
                self.root.after(
                    0, lambda: self.panel.set_device_status("oven", False))
                self.log_msg(f"Oven FAILED: {e}")

            if self.mode == MODE_FULL_SWEEP:
                try:
                    drv = LCRDriver(self.panel.cmb_lcr.get())
                    data = drv.get_parsed_reading()
                    drv.close()
                    self.status_lcr = True
                    self.root.after(0, lambda: self.panel.set_device_status(
                        "lcr", True, f"Z={data[0]:.2e}Ω"))
                    self.log_msg(f"LCR OK — Z: {data[0]:.3e} Ω")
                except Exception as e:
                    self.status_lcr = False
                    self.root.after(
                        0, lambda: self.panel.set_device_status("lcr", False))
                    self.log_msg(f"LCR FAILED: {e}")

        threading.Thread(target=_test, daemon=True).start()
        self.log_msg("Testing connections...")

    def recalc_stats(self, event=None):
        if self.mode == MODE_TEMP_ONLY:
            self.panel.lbl_stats.config(text="")
            return
        try:
            mn, mx, st = float(self.panel.ent_min.get()), float(
                self.panel.ent_max.get()), float(self.panel.ent_steps.get())
            total = int(math.log10(mx / mn) * st) + 1
            self.panel.lbl_stats.config(text=f"Total points/step: {total}")
        except Exception:
            pass

    def save_profile(self):
        data = {
            "mode":    self.mode, "start":   self.panel.ent_start.get(), "end":     self.panel.ent_end.get(),
            "step":    self.panel.ent_step.get(), "tol":     self.panel.ent_tolerance.get(), "dwell":   self.panel.ent_dwell.get(),
            "ramp":    self.panel.ent_ramp_rate.get(), "f_min":   self.panel.ent_min.get(), "f_max":   self.panel.ent_max.get(),
            "f_steps": self.panel.ent_steps.get(), "ac_v":    self.panel.ent_voltage.get(),
        }
        f = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("Profile", "*.json")])
        if f:
            with open(f, 'w') as jf:
                json.dump(data, jf, indent=2)
            self.log_msg(f"Profile saved: {os.path.basename(f)}")

    def load_profile(self):
        f = filedialog.askopenfilename(filetypes=[("Profile", "*.json")])
        if not f:
            return
        with open(f, 'r') as jf:
            data = json.load(jf)
        field_map = {
            "start": self.panel.ent_start, "end": self.panel.ent_end, "step": self.panel.ent_step,
            "tol": self.panel.ent_tolerance, "dwell": self.panel.ent_dwell, "ramp": self.panel.ent_ramp_rate,
            "f_min": self.panel.ent_min, "f_max": self.panel.ent_max, "f_steps": self.panel.ent_steps, "ac_v": self.panel.ent_voltage,
        }
        for key, ent in field_map.items():
            if key in data:
                ent.delete(0, tk.END)
                ent.insert(0, data[key])
        if "mode" in data:
            self.set_mode(data["mode"])
        self.recalc_stats()
        self.log_msg(f"Profile loaded: {os.path.basename(f)}")

    # --- NEW: Manual Sweep Routing ---
    def start_manual_sweep(self):
        self._start_worker(manual_mode=True)

    def start_experiment(self):
        self._start_worker(manual_mode=False)

    def _start_worker(self, manual_mode: bool):
        config = {
            'lcr_addr':         self.panel.cmb_lcr.get(),
            'oven_port':        self.panel.cmb_oven.get(),
            'oven_id':          int(self.panel.ent_oven_id.get()),
            'start_temp':       float(self.panel.ent_start.get()),
            'end_temp':         float(self.panel.ent_end.get()),
            'temp_step':        float(self.panel.ent_step.get()),
            'tolerance':        float(self.panel.ent_tolerance.get()),
            'dwell_min':        float(self.panel.ent_dwell.get()),
            'ramp_rate':        float(self.panel.ent_ramp_rate.get()),
            'min_freq':         float(self.panel.ent_min.get()) if self.mode == MODE_FULL_SWEEP else 100,
            'max_freq':         float(self.panel.ent_max.get()) if self.mode == MODE_FULL_SWEEP else 100000,
            'steps_per_decade': int(self.panel.ent_steps.get()) if self.mode == MODE_FULL_SWEEP else 5,
            'ac_voltage':       float(self.panel.ent_voltage.get()) if self.mode == MODE_FULL_SWEEP else 1.0,
            'filename':         self.panel.ent_filename.get(),
            'manual_mode':      manual_mode
        }

        self.panel.btn_start.config(state="disabled")
        if hasattr(self.panel, 'btn_manual'):
            self.panel.btn_manual.config(state="disabled")
        self.panel.btn_stop.config(state="normal")

        self.time_data, self.pv_data, self.sp_data, self.wsp_data = [], [], [], []
        self._ghost_drawn = False
        self._ghost_config = (config['end_temp'], round(
            config['ramp_rate'])) if self.mode == MODE_TEMP_ONLY else None

        self.dash.clear_plot()

        self.worker = ExperimentWorker(
            config=config,
            mode=self.mode,
            callback_log=self.log_msg,
            callback_progress=self._cb_progress,
            callback_live_plot=self._cb_live_plot,
            callback_lcr_display=self._cb_lcr_display,
            callback_finished=self._cb_finished,
        )
        self.worker.start()

        mode_str = "Manual Sweep" if manual_mode else (
            'Temp Only' if self.mode == MODE_TEMP_ONLY else 'Full Sweep')
        self.log_msg(f"Experiment started — Mode: {mode_str}")

    def stop_experiment(self):
        if self.worker:
            self.worker.stop(cooldown=True)
        self.log_msg("E-STOP issued — cooldown to 25°C")

    def _cb_progress(self, status_text: str, rem_sec: float, pv: float, sp: float):
        wsp = self.wsp_data[-1] if self.wsp_data else 0.0
        self.root.after(0, lambda: self.dash.update_readouts(
            pv, sp, wsp, rem_sec, status_text))

    def _cb_live_plot(self, elapsed: float, pv: float, sp: float, wsp: float):
        self.time_data.append(elapsed)
        self.pv_data.append(pv)
        self.sp_data.append(sp)
        self.wsp_data.append(wsp)

        if not self._ghost_drawn and self._ghost_config is not None:
            end_temp, rate = self._ghost_config
            self.root.after(0, lambda: self.dash.draw_ghost_ramp(
                pv, end_temp, rate, t_offset=elapsed))
            self._ghost_drawn = True

        self.root.after(0, lambda: self.dash.update_plot(
            self.time_data, self.pv_data, self.sp_data, self.wsp_data))

    def _cb_lcr_display(self, freq: float, lcr_data: list):
        if self.mode == MODE_FULL_SWEEP:
            self.root.after(0, lambda: self.dash.update_lcr(freq, lcr_data))

    def _cb_finished(self):
        self.root.after(0, self._on_finish)

    def _on_finish(self):
        self.panel.btn_start.config(state="normal")
        if hasattr(self.panel, 'btn_manual'):
            self.panel.btn_manual.config(state="normal")
        self.panel.btn_stop.config(state="disabled")
        self.dash.set_status("Finished", C_ACCENT)

    def log_msg(self, msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.root.after(0, lambda: self.dash.log(ts, msg))
