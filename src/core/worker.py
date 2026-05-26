# =============================================================================
# core/worker.py — ExperimentWorker background thread
# =============================================================================
import threading
import time
import csv
import datetime
import os

import numpy as np
from tkinter import messagebox

from src.constants import LCR_LABELS, LCR_UNITS, MODE_TEMP_ONLY, MODE_FULL_SWEEP
from src.drivers.lcr_driver import LCRDriver
from src.drivers.eurotherm_driver import EurothermDriver
from src.core.plotting import save_bode_plots


class ExperimentWorker(threading.Thread):
    def __init__(
        self, config: dict, mode: str, callback_log, callback_progress,
        callback_live_plot, callback_lcr_display, callback_finished
    ):
        super().__init__()
        self.config = config
        self.mode = mode
        self.log = callback_log
        self.update_progress = callback_progress
        self.update_live_plot = callback_live_plot
        self.update_lcr_display = callback_lcr_display
        self.on_finished = callback_finished
        self.running = True
        self.daemon = True
        self.emergency_cooldown = False

        self.csv_file = self.config['filename']
        self.base_dir = os.path.dirname(self.csv_file) or "."
        self.base_name = os.path.splitext(os.path.basename(self.csv_file))[0]
        self.log_file = os.path.join(
            self.base_dir, f"{self.base_name}_log.txt")

    def _write_log(self, msg: str):
        self.log(msg)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] {msg}\n")

    def _log_row(self, sp: float, pv: float, wsp: float):
        ts_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([ts_str, sp, pv, wsp])
            
    def _run_temp_only(self, oven: EurothermDriver, start_time: float):
        start_temp = self.config['start_temp']
        end_temp = self.config['end_temp']
        rate = self.config['ramp_rate']
        tolerance = self.config['tolerance']

        # --- NEW: Check direction ---
        is_heating = (end_temp >= start_temp)

        self._write_log(f"Ramping from {start_temp}°C to {end_temp}°C at {rate}°C/min")
        oven.set_sp(end_temp)

        while self.running:
            pv = oven.get_pv()
            wsp = oven.get_wsp()
            elapsed = time.time() - start_time

            self.update_live_plot(elapsed, pv, end_temp, wsp)
            self._log_row(end_temp, pv, wsp)

            # --- FIXED: Use absolute value so cooling ETA works ---
            remaining_deg = abs(end_temp - pv)
            time_rem = (remaining_deg / rate) * 60 if rate > 0 else 0
            self.update_progress(
                f"Ramping... {pv:.1f}°C → {end_temp:.1f}°C", time_rem, pv, end_temp)

            # --- FIXED: Directional stability check ---
            stable = False
            if is_heating and pv >= (end_temp - tolerance):
                stable = True
            elif not is_heating and pv <= (end_temp + tolerance):
                stable = True

            if stable:
                self._write_log(f"Target {end_temp}°C reached (Actual: {pv:.1f}°C). Holding.")
                break

            time.sleep(1.0)
            
    def _wait_for_stability(self, oven: EurothermDriver, sp: float, is_heating: bool, total_temps: int, t_idx: int, total_freqs: int, start_time: float):
        rate = self.config['ramp_rate']
        while self.running:
            pv, wsp = oven.get_pv(), oven.get_wsp()
            self.update_live_plot(time.time() - start_time, pv, sp, wsp)

            stable = ((is_heating and pv >= sp - self.config['tolerance']) or (
                not is_heating and pv <= sp + self.config['tolerance']))
            if stable:
                self._write_log(f"Target {sp}°C reached. Starting dwell.")
                return

            time_rem = ((abs(pv - sp) / rate) * 60 if rate > 0 else 0) + \
                (total_temps - t_idx) * \
                (self.config['dwell_min'] * 60 + total_freqs * 0.3)
            self.update_progress(
                f"Ramping... (W.SP: {wsp:.1f}°C)", time_rem, pv, sp)
            time.sleep(1.0)

    def _dwell(self, oven: EurothermDriver, sp: float, total_temps: int, t_idx: int, total_freqs: int, start_time: float):
        dwell_sec = int(self.config['dwell_min'] * 60)
        for i in range(dwell_sec):
            if not self.running:
                break
            pv, wsp = oven.get_pv(), oven.get_wsp()
            self.update_live_plot(time.time() - start_time, pv, sp, wsp)
            time_rem = (dwell_sec - i) + (total_temps - t_idx -
                                          1) * (dwell_sec + total_freqs * 0.3)
            self.update_progress(f"Dwelling @ {sp:.1f}°C...", time_rem, pv, sp)
            time.sleep(1)

    def _sweep_frequencies(self, lcr: LCRDriver, oven: EurothermDriver, sp: float, freqs, total_temps: int, t_idx: int, dwell_sec: int, start_time: float):
        self._write_log(f"Sweeping {len(freqs)} frequencies @ {sp}°C")
        step_z, step_y, step_phase = [], [], []
        total_freqs = len(freqs)

        for freq in freqs:
            if not self.running:
                break
            lcr.set_frequency(freq)
            time.sleep(0.2)

            pv_now, wsp_now = oven.get_pv(), oven.get_wsp()
            self.update_live_plot(
                time.time() - start_time, pv_now, sp, wsp_now)

            lcr_data = lcr.get_parsed_reading()
            step_z.append(lcr_data[0])
            step_y.append(lcr_data[1])
            step_phase.append(lcr_data[2])
            self.update_lcr_display(freq, lcr_data)

            ts_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(
                    [ts_str, sp, pv_now, f"{freq:.2f}"] + lcr_data)

            time_rem = (total_freqs - len(step_z)) * 0.3 + \
                (total_temps - t_idx - 1) * (dwell_sec + total_freqs * 0.3)
            self.update_progress(f"Meas: {freq:.1f} Hz", time_rem, pv_now, sp)

        if self.running and step_z:
            self._write_log(f"Saving Bode plots for {sp}°C...")
            save_bode_plots(sp, freqs, step_z, step_phase,
                            step_y, self.base_dir, self.base_name)

    # -------------------------------------------------------------------------
    # Main thread entry
    # -------------------------------------------------------------------------

    def run(self):
        lcr = None
        oven = None
        start_time = time.time()

        try:
            is_manual = self.config.get('manual_mode', False)
            mode_str = "MANUAL SWEEP" if is_manual else self.mode.upper()
            self._write_log(f"=== EXPERIMENT STARTED [{mode_str}] ===")

            oven = EurothermDriver(
                self.config['oven_port'], self.config['oven_id'])

            # =================================================================
            # MODE 1: MANUAL SINGLE SWEEP
            # =================================================================
            if is_manual:
                lcr = LCRDriver(self.config['lcr_addr'])
                lcr.set_voltage(self.config['ac_voltage'])
                lcr.apply_advanced_settings(self.config, self._write_log) 
                self._write_log(f"LCR voltage set to {self.config['ac_voltage']} V")

                curr_sp = oven.get_sp()
                curr_pv = oven.get_pv()
                self._write_log(
                    f"Running Manual Sweep at Current Temp: {curr_pv:.2f} °C")

                log_min, log_max = np.log10(
                    self.config['min_freq']), np.log10(self.config['max_freq'])
                freqs = np.logspace(log_min, log_max, num=int(
                    (log_max - log_min) * self.config['steps_per_decade']) + 1)

                file_exists = os.path.isfile(self.csv_file)
                with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        lcr_headers = [f"{lbl} ({unt})" if unt else lbl for lbl, unt in zip(
                            LCR_LABELS, LCR_UNITS)]
                        writer.writerow(
                            ["Timestamp", "Setpoint_DegC", "Actual_DegC", "Frequency_Hz"] + lcr_headers)

                self._sweep_frequencies(
                    lcr, oven, curr_sp, freqs, 1, 0, 0, start_time)
                self._write_log("=== MANUAL SWEEP FINISHED ===")

            # =================================================================
            # MODE 2: AUTOMATED SEQUENCES (TEMP ONLY & FULL SWEEP)
            # =================================================================
            else:
                oven.set_ramp_rate(self.config['ramp_rate'])
                raw_readback = oven.get_ramp_rate()
                self._write_log(
                    f"Ramp rate: sent {int(self.config['ramp_rate'])} to register 35, raw readback = {raw_readback}")

                # ── TEMP ONLY ──
                if self.mode == MODE_TEMP_ONLY:
                    with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                        csv.writer(f).writerow(
                            ["Timestamp", "Setpoint_DegC", "Actual_DegC", "Working_SP_DegC"])

                    self._run_temp_only(oven, start_time)
                    self._write_log("=== RAMP COMPLETE — HOLDING ===")

                # ── FULL SWEEP ──
                elif self.mode == MODE_FULL_SWEEP:
                    lcr = LCRDriver(self.config['lcr_addr'])
                    lcr.set_voltage(self.config['ac_voltage'])
                    lcr.apply_advanced_settings(self.config, self._write_log)
                    self._write_log(f"LCR voltage set to {self.config['ac_voltage']} V")

                    log_min, log_max = np.log10(
                        self.config['min_freq']), np.log10(self.config['max_freq'])
                    freqs = np.logspace(log_min, log_max, num=int(
                        (log_max - log_min) * self.config['steps_per_decade']) + 1)
                    temps = np.arange(
                        self.config['start_temp'], self.config['end_temp'] + 0.1, self.config['temp_step'])

                    total_temps, total_freqs, dwell_sec = len(temps), len(
                        freqs), int(self.config['dwell_min'] * 60)

                    with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                        lcr_headers = [f"{lbl} ({unt})" if unt else lbl for lbl, unt in zip(
                            LCR_LABELS, LCR_UNITS)]
                        csv.writer(f).writerow(
                            ["Timestamp", "Setpoint_DegC", "Actual_DegC", "Frequency_Hz"] + lcr_headers)

                    prev_sp = oven.get_pv()

                    for t_idx, sp in enumerate(temps):
                        if not self.running:
                            break
                        self._write_log(f"Ramping to {sp:.1f}°C...")
                        oven.set_sp(sp)
                        is_heating = (sp >= prev_sp)

                        self._wait_for_stability(
                            oven, sp, is_heating, total_temps, t_idx, total_freqs, start_time)
                        self._dwell(oven, sp, total_temps, t_idx,
                                    total_freqs, start_time)

                        if self.running:
                            self._sweep_frequencies(
                                lcr, oven, sp, freqs, total_temps, t_idx, dwell_sec, start_time)

                        prev_sp = sp

                    self._write_log("=== EXPERIMENT FINISHED ===")
                    if self.running:
                        self._write_log("Auto-Cooldown: Setting Oven to 25°C")
                        oven.set_sp(25.0)

        except Exception as e:
            self._write_log(f"CRITICAL ERROR: {e}")
            messagebox.showerror("Experiment Error", str(e))

        finally:
            if self.emergency_cooldown and oven:
                self._write_log("E-STOP: Forcing Oven to 25°C")
                oven.set_sp(25.0)
            if lcr:
                lcr.close()
            self.on_finished()

    def stop(self, cooldown: bool = True):
        self.running = False
        self.emergency_cooldown = cooldown
