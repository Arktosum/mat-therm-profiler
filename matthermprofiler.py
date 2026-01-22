import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pyvisa
import minimalmodbus
import serial
import serial.tools.list_ports
import time
import csv
import threading
import datetime
import numpy as np
import math

# =============================================================================
# CONSTANTS
# =============================================================================
LCR_LABELS = ["Z_Ohm", "Y_Siemens", "Phase_Deg", "Cs_Farad", "Cp_Farad", "D_Loss", "Ls_Henry", "Lp_Henry"]

# =============================================================================
# MODULE 1: INSTRUMENT DRIVERS
# =============================================================================

class LCRDriver:
    def __init__(self, resource_str):
        try:
            rm = pyvisa.ResourceManager()
        except OSError:
            rm = pyvisa.ResourceManager('@py')
            
        self.inst = rm.open_resource(resource_str)
        self.inst.timeout = 3000
        self.inst.write(":MEASure:VALid 0")         
        self.inst.write(":TRIGger INTernal")        
        self.inst.write(":MEASure:ITEM 255,0,0")    
    
    def set_frequency(self, freq):
        self.inst.write(f":FREQuency {freq}")

    def get_parsed_reading(self):
        try:
            raw = self.inst.query(":MEASure?").strip()
            # Parse CSV response into floats
            parts = raw.split(',')
            data = []
            for p in parts:
                try:
                    data.append(float(p))
                except ValueError:
                    data.append(0.0)
            return data
        except Exception:
            return [0.0] * len(LCR_LABELS)

    def close(self):
        if self.inst: self.inst.close()


class EurothermDriver:
    def __init__(self, port, address=1):
        self.inst = minimalmodbus.Instrument(port, address)
        self.inst.serial.baudrate = 9600
        self.inst.serial.timeout = 1.0
        self.inst.clear_buffers_before_each_transaction = True
    
    def get_pv(self):
        return self.inst.read_register(1, number_of_decimals=2)
    
    def set_sp(self, value):
        self.inst.write_register(2, value, number_of_decimals=2)

    def set_ramp_rate(self, rate_per_min):
        """
        Sets the SP Rate Limit (Register 35 on Eurotherm 3200 series).
        Unit is typically Degrees/Minute.
        """
        try:
            # If rate is 0 or very high, we might want to disable it, 
            # but usually setting a high value (e.g. 999) acts as 'immediate'.
            # Here we just pass the user value.
            self.inst.write_register(35, rate_per_min, number_of_decimals=1)
        except IOError:
            print("Warning: Could not set Ramp Rate (Reg 35). Controller might be locked or mapped differently.")

# =============================================================================
# MODULE 2: EXPERIMENT WORKER
# =============================================================================

class ExperimentWorker(threading.Thread):
    def __init__(self, config, callback_log, callback_progress, callback_finished):
        super().__init__()
        self.config = config
        self.log = callback_log
        self.update_progress = callback_progress
        self.on_finished = callback_finished
        self.running = True
        self.daemon = True

    def run(self):
        lcr = None
        oven = None
        
        try:
            # 1. Connect
            self.log("Connecting instruments...")
            lcr = LCRDriver(self.config['lcr_addr'])
            oven = EurothermDriver(self.config['oven_port'], self.config['oven_id'])
            
            # 2. Configure Ramp Rate
            rate = self.config['ramp_rate']
            self.log(f"Setting Ramp Rate to {rate} °C/min")
            oven.set_ramp_rate(rate)

            # 3. Plan Experiment
            temps = np.arange(self.config['start_temp'], 
                              self.config['end_temp'] + 0.1, 
                              self.config['temp_step'])
            
            log_min = np.log10(self.config['min_freq'])
            log_max = np.log10(self.config['max_freq'])
            num_decades = log_max - log_min
            total_freq_points = int(num_decades * self.config['steps_per_decade']) + 1
            freqs = np.logspace(log_min, log_max, num=total_freq_points)
            
            total_readings = len(temps) * len(freqs)
            
            # 4. Create CSV
            filename = self.config['filename']
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                header = ["Timestamp", "Setpoint_DegC", "Actual_DegC", "Frequency_Hz"] + LCR_LABELS
                writer.writerow(header)

            current_idx = 0
            
            # --- MAIN LOOP ---
            for sp in temps:
                if not self.running: break
                
                # A. Set Temperature
                self.log(f"Ramping to {sp:.2f} °C...")
                oven.set_sp(sp)
                
                # B. Wait for Stability (Wait for Ramp + Settling)
                while self.running:
                    pv = oven.get_pv()
                    error = abs(pv - sp)
                    
                    # Update status slightly differently during Ramp vs Stable
                    if error > self.config['tolerance']:
                        status_msg = f"Ramping: {pv:.2f}C -> {sp}C (Err: {error:.2f})"
                    else:
                        status_msg = f"Stabilizing: {pv:.2f}C (Target {sp}C)"
                        # Exit loop if stable
                        break
                    
                    self.update_progress(current_idx, total_readings, status_msg)
                    time.sleep(1.0)
                
                # C. Dwell
                dwell_sec = int(self.config['dwell_min'] * 60)
                for i in range(dwell_sec):
                    if not self.running: break
                    if i % 5 == 0:
                        self.update_progress(current_idx, total_readings, f"Dwelling @ {sp}C: {dwell_sec-i}s left")
                    time.sleep(1)

                # D. Sweep
                self.log(f"Sweeping {len(freqs)} frequencies @ {sp} °C")
                for freq in freqs:
                    if not self.running: break
                    
                    lcr.set_frequency(freq)
                    time.sleep(0.2) 
                    
                    pv_now = oven.get_pv()
                    lcr_data = lcr.get_parsed_reading()
                    
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    row = [timestamp, sp, pv_now, f"{freq:.2f}"] + lcr_data
                    
                    with open(filename, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(row)
                    
                    current_idx += 1
                    z_val = lcr_data[0] if len(lcr_data) > 0 else 0
                    self.update_progress(current_idx, total_readings, f"Meas: {freq:.1f}Hz | Z={z_val:.2e}")

            self.log("Experiment Complete!")
            
        except Exception as e:
            self.log(f"ERROR: {e}")
            messagebox.showerror("Experiment Error", str(e))
        finally:
            if lcr: lcr.close()
            self.on_finished()

    def stop(self):
        self.running = False

# =============================================================================
# MODULE 3: MAIN GUI
# =============================================================================
class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AutoLCR - Characterization Suite")
        self.root.geometry("950x750") # Taller for new input
        
        self.worker = None

        # --- LAYOUT ---
        left_panel = ttk.Frame(root, padding=10)
        left_panel.pack(side="left", fill="y")
        
        right_panel = ttk.Frame(root, padding=10)
        right_panel.pack(side="right", fill="both", expand=True)

        # 1. Connection Config
        self.create_conn_group(left_panel)
        
        # 2. Temperature Config
        self.create_temp_group(left_panel)
        
        # 3. LCR Config
        self.create_lcr_group(left_panel)
        
        # 4. File Config
        self.create_file_group(left_panel)
        
        # 5. Controls
        btn_frame = ttk.Frame(left_panel, padding=10)
        btn_frame.pack(fill="x", pady=10)
        
        self.btn_start = ttk.Button(btn_frame, text="START EXPERIMENT", command=self.start_experiment)
        self.btn_start.pack(side="left", fill="x", expand=True, padx=5)
        
        self.btn_stop = ttk.Button(btn_frame, text="STOP", command=self.stop_experiment, state="disabled")
        self.btn_stop.pack(side="right", fill="x", expand=True, padx=5)

        # 6. Status Display
        ttk.Label(right_panel, text="Live Progress:").pack(anchor="w")
        self.lbl_main_status = ttk.Label(right_panel, text="Ready", font=("Arial", 12, "bold"), foreground="blue")
        self.lbl_main_status.pack(anchor="w", pady=5)
        
        self.progress = ttk.Progressbar(right_panel, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", pady=5)
        
        ttk.Label(right_panel, text="Experiment Log:").pack(anchor="w", pady=(10,0))
        self.log_text = tk.Text(right_panel, height=20, state="disabled", font=("Consolas", 9), bg="#f4f4f4")
        self.log_text.pack(fill="both", expand=True)

        self.refresh_resources()
        self.recalc_stats()

    def create_conn_group(self, parent):
        grp = ttk.LabelFrame(parent, text="1. Instruments & Connection", padding=10)
        grp.pack(fill="x", pady=5)
        
        ttk.Label(grp, text="LCR Addr:").grid(row=0, column=0, sticky="w")
        self.cmb_lcr = ttk.Combobox(grp, width=18)
        self.cmb_lcr.grid(row=0, column=1, padx=2)
        ttk.Button(grp, text="↻", width=3, command=self.refresh_resources).grid(row=0, column=2)
        
        ttk.Label(grp, text="Oven Port:").grid(row=1, column=0, sticky="w")
        self.cmb_oven = ttk.Combobox(grp, width=18)
        self.cmb_oven.grid(row=1, column=1, padx=2)
        ttk.Button(grp, text="↻", width=3, command=self.refresh_resources).grid(row=1, column=2)
        
        ttk.Label(grp, text="Oven ID:").grid(row=2, column=0, sticky="w")
        self.ent_oven_id = ttk.Entry(grp, width=5)
        self.ent_oven_id.insert(0, "1")
        self.ent_oven_id.grid(row=2, column=1, sticky="w", padx=2)
        
        btn_frame = ttk.Frame(grp)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=(10,5), sticky="ew")
        
        self.btn_test_conn = ttk.Button(btn_frame, text="Test Connections", command=self.test_connections)
        self.btn_test_conn.pack(side="left", fill="x", expand=True)
        
        self.lbl_conn_status = ttk.Label(btn_frame, text="Not Tested", foreground="gray")
        self.lbl_conn_status.pack(side="left", padx=5)

    def create_temp_group(self, parent):
        grp = ttk.LabelFrame(parent, text="2. Temperature Profile", padding=10)
        grp.pack(fill="x", pady=5)
        
        self.add_entry(grp, "Start Temp (°C):", "30", 0)
        self.add_entry(grp, "End Temp (°C):", "100", 1)
        self.add_entry(grp, "Step Size (°C):", "10", 2)
        self.add_entry(grp, "Tolerance (°C):", "1.0", 3)
        self.add_entry(grp, "Dwell Time (min):", "2", 4)
        # Added Ramp Rate Input
        self.add_entry(grp, "Ramp (deg/min):", "6.0", 5)

    def create_lcr_group(self, parent):
        grp = ttk.LabelFrame(parent, text="3. Frequency Sweep", padding=10)
        grp.pack(fill="x", pady=5)
        
        self.ent_min = self.add_entry(grp, "Min Freq (Hz):", "100", 0, bind_recalc=True)
        self.ent_max = self.add_entry(grp, "Max Freq (Hz):", "100000", 1, bind_recalc=True)
        self.ent_steps = self.add_entry(grp, "Steps/Decade:", "5", 2, bind_recalc=True)
        
        self.lbl_stats = ttk.Label(grp, text="Points: --", foreground="#0078D7", font=("Arial", 9, "italic"))
        self.lbl_stats.grid(row=3, column=0, columnspan=2, pady=5)

    def create_file_group(self, parent):
        grp = ttk.LabelFrame(parent, text="4. Data Output", padding=10)
        grp.pack(fill="x", pady=5)
        
        self.ent_filename = ttk.Entry(grp, width=30)
        self.ent_filename.insert(0, "data.csv")
        self.ent_filename.pack(side="left", fill="x", expand=True)
        ttk.Button(grp, text="Browse", command=self.browse_file).pack(side="right")

    def add_entry(self, parent, label, default, row, bind_recalc=False):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ent = ttk.Entry(parent, width=10)
        ent.insert(0, default)
        ent.grid(row=row, column=1, sticky="e", pady=2, padx=5)
        
        # Clean attribute naming
        raw_name = label.split()[0].lower()
        if "ramp" in raw_name: attr_name = "ent_ramp_rate"
        elif "steps" in raw_name: attr_name = "ent_steps"
        else: attr_name = f"ent_{raw_name}"
        
        setattr(self, attr_name, ent)
        
        if bind_recalc:
            ent.bind("<KeyRelease>", self.recalc_stats)
            
        return ent

    def refresh_resources(self):
        try:
            rm = pyvisa.ResourceManager()
            self.cmb_lcr['values'] = rm.list_resources()
            if self.cmb_lcr['values']: self.cmb_lcr.current(0)
        except: pass
        
        try:
            ports = [p.device for p in serial.tools.list_ports.comports()]
            self.cmb_oven['values'] = ports
            if ports: self.cmb_oven.current(0)
        except: pass

    def test_connections(self):
        self.lbl_conn_status.config(text="Testing...", foreground="orange")
        self.root.update()
        lcr_ok = False
        oven_ok = False
        
        try:
            rm = pyvisa.ResourceManager()
            inst = rm.open_resource(self.cmb_lcr.get())
            inst.timeout = 1000
            inst.query("*IDN?")
            inst.close()
            lcr_ok = True
        except: pass
        
        try:
            inst = minimalmodbus.Instrument(self.cmb_oven.get(), int(self.ent_oven_id.get()))
            inst.serial.baudrate = 9600
            inst.serial.timeout = 0.5
            inst.read_register(1, number_of_decimals=2)
            oven_ok = True
        except: pass
        
        if lcr_ok and oven_ok:
            self.lbl_conn_status.config(text="BOTH OK", foreground="green")
            self.log_msg("Connection Test: PASS")
        else:
            status = []
            if not lcr_ok: status.append("LCR Fail")
            if not oven_ok: status.append("Oven Fail")
            self.lbl_conn_status.config(text=", ".join(status), foreground="red")
            self.log_msg(f"Connection Test: FAIL ({', '.join(status)})")

    def recalc_stats(self, event=None):
        try:
            min_f = float(self.ent_min.get())
            max_f = float(self.ent_max.get())
            steps = float(self.ent_steps.get())
            if min_f <= 0 or max_f <= min_f or steps <= 0: raise ValueError
            decades = math.log10(max_f / min_f)
            total = int(decades * steps) + 1
            self.lbl_stats.config(text=f"Decades: {decades:.2f} | Total Points: {total}")
        except:
            self.lbl_stats.config(text="Invalid Input")

    def browse_file(self):
        f = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if f:
            self.ent_filename.delete(0, tk.END)
            self.ent_filename.insert(0, f)

    def start_experiment(self):
        try:
            config = {
                'lcr_addr': self.cmb_lcr.get(),
                'oven_port': self.cmb_oven.get(),
                'oven_id': int(self.ent_oven_id.get()),
                'start_temp': float(self.ent_start.get()),
                'end_temp': float(self.ent_end.get()),
                'temp_step': float(self.ent_step.get()),
                'tolerance': float(self.ent_tolerance.get()),
                'dwell_min': float(self.ent_dwell.get()),
                'ramp_rate': float(self.ent_ramp_rate.get()), # New Config
                'min_freq': float(self.ent_min.get()),
                'max_freq': float(self.ent_max.get()),
                'steps_per_decade': int(self.ent_steps.get()),
                'filename': self.ent_filename.get()
            }
        except ValueError:
            messagebox.showerror("Input Error", "Please check all numeric fields.")
            return

        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.progress['value'] = 0
        self.log_msg("Starting experiment...")
        
        self.worker = ExperimentWorker(config, self.log_msg, self.update_prog, self.on_finish)
        self.worker.start()

    def stop_experiment(self):
        if self.worker:
            self.worker.stop()
            self.log_msg("Stopping requested...")

    def on_finish(self):
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.lbl_main_status.config(text="Finished")

    def update_prog(self, current, total, status_text):
        pct = (current / total) * 100
        self.progress['value'] = pct
        self.lbl_main_status.config(text=status_text)

    def log_msg(self, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()