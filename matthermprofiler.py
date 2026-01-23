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
import json
import os

# --- MATPLOTLIB IMPORTS FOR GUI AND FILE SAVING ---
import matplotlib
matplotlib.use('TkAgg') # Use Tk backend for live GUI
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# =============================================================================
# CONSTANTS & MAPPING
# =============================================================================
LCR_LABELS = [
    "Z", "Y", "Phase_Z", 
    "Cs", "Cp", "D", 
    "Ls", "Lp", "Rs", "Rp"
]

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
        self.inst.write(":MEASure:ITEM 255,3,0")    
    
    def set_frequency(self, freq):
        self.inst.write(f":FREQuency {freq}")

    def get_parsed_reading(self):
        try:
            raw = self.inst.query(":MEASure?").strip()
            parts = raw.split(',')
            data = [float(p) if '*' not in p else 0.0 for p in parts]
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
        try:
            self.inst.write_register(35, rate_per_min, number_of_decimals=1)
        except IOError:
            print("Warning: Reg 35 (Ramp Rate) not writable on this firmware.")

# =============================================================================
# MODULE 2: GRAPHING & FILE UTILITIES
# =============================================================================

def save_bode_plots(temp, freqs, z_data, phase_z, y_data, save_path, base_name):
    """Generates and saves the Z and Y Bode plots automatically."""
    try:
        # Calculate Phase Y (Opposite of Phase Z)
        phase_y = [-p for p in phase_z]
        
        # 1. Z-Plot
        fig_z, ax1_z = plt.subplots(figsize=(8, 5))
        ax1_z.set_title(f"Impedance Response @ {temp}°C")
        ax1_z.set_xlabel("Frequency (Hz)")
        ax1_z.set_xscale("log")
        
        color_z = 'tab:blue'
        ax1_z.set_ylabel("|Z| (Ω)", color=color_z)
        ax1_z.plot(freqs, z_data, color=color_z, marker='.')
        ax1_z.set_yscale("log")
        ax1_z.tick_params(axis='y', labelcolor=color_z)

        ax2_z = ax1_z.twinx()
        color_p = 'tab:orange'
        ax2_z.set_ylabel("Phase (deg)", color=color_p)
        ax2_z.plot(freqs, phase_z, color=color_p, linestyle='--')
        ax2_z.tick_params(axis='y', labelcolor=color_p)
        
        fig_z.tight_layout()
        fig_z.savefig(os.path.join(save_path, f"{base_name}_{temp}C_Z_Plot.png"), dpi=150)
        plt.close(fig_z)

        # 2. Y-Plot
        fig_y, ax1_y = plt.subplots(figsize=(8, 5))
        ax1_y.set_title(f"Admittance Response @ {temp}°C")
        ax1_y.set_xlabel("Frequency (Hz)")
        ax1_y.set_xscale("log")
        
        color_y = 'tab:green'
        ax1_y.set_ylabel("|Y| (S)", color=color_y)
        ax1_y.plot(freqs, y_data, color=color_y, marker='.')
        ax1_y.set_yscale("log")
        ax1_y.tick_params(axis='y', labelcolor=color_y)

        ax2_y = ax1_y.twinx()
        ax2_y.set_ylabel("Phase Y (deg)", color=color_p)
        ax2_y.plot(freqs, phase_y, color=color_p, linestyle='--')
        ax2_y.tick_params(axis='y', labelcolor=color_p)
        
        fig_y.tight_layout()
        fig_y.savefig(os.path.join(save_path, f"{base_name}_{temp}C_Y_Plot.png"), dpi=150)
        plt.close(fig_y)
        
    except Exception as e:
        print(f"Plotting Error: {e}")

# =============================================================================
# MODULE 3: EXPERIMENT WORKER
# =============================================================================

class ExperimentWorker(threading.Thread):
    def __init__(self, config, callback_log, callback_progress, callback_live_plot, callback_finished):
        super().__init__()
        self.config = config
        self.log = callback_log
        self.update_progress = callback_progress
        self.update_live_plot = callback_live_plot
        self.on_finished = callback_finished
        self.running = True
        self.daemon = True
        self.emergency_cooldown = False

        # File paths
        self.csv_file = self.config['filename']
        self.base_dir = os.path.dirname(self.csv_file)
        self.base_name = os.path.splitext(os.path.basename(self.csv_file))[0]
        self.log_file = os.path.join(self.base_dir, f"{self.base_name}_log.txt")

    def write_log(self, msg):
        self.log(msg)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_file, 'a') as f:
            f.write(f"[{ts}] {msg}\n")

    def run(self):
        lcr = None
        oven = None
        start_time = time.time()
        
        try:
            self.write_log("=== EXPERIMENT STARTED ===")
            lcr = LCRDriver(self.config['lcr_addr'])
            oven = EurothermDriver(self.config['oven_port'], self.config['oven_id'])
            
            rate = self.config['ramp_rate']
            oven.set_ramp_rate(rate)
            self.write_log(f"Ramp Rate set to {rate} °C/min")

            temps = np.arange(self.config['start_temp'], self.config['end_temp'] + 0.1, self.config['temp_step'])
            log_min = np.log10(self.config['min_freq'])
            log_max = np.log10(self.config['max_freq'])
            freqs = np.logspace(log_min, log_max, num=int((log_max - log_min) * self.config['steps_per_decade']) + 1)
            
            total_temps = len(temps)
            total_freqs = len(freqs)
            
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Setpoint_DegC", "Actual_DegC", "Frequency_Hz"] + LCR_LABELS)

            # --- MAIN LOOP ---
            for t_idx, sp in enumerate(temps):
                if not self.running: break
                
                self.write_log(f"Ramping to {sp:.2f} °C...")
                oven.set_sp(sp)
                
                # B. Wait for Stability
                while self.running:
                    pv = oven.get_pv()
                    error = abs(pv - sp)
                    elapsed = time.time() - start_time
                    self.update_live_plot(elapsed, pv, sp)
                    
                    if error > self.config['tolerance']:
                        # Estimation Logic
                        rem_temp_steps = total_temps - t_idx
                        time_rem = (error / rate)*60 if rate > 0 else 0 
                        time_rem += rem_temp_steps * (self.config['dwell_min']*60 + total_freqs*0.3)
                        self.update_progress(f"Ramping to {sp}C...", time_rem, pv, sp)
                    else:
                        break
                    time.sleep(1.0)
                
                # C. Dwell
                dwell_sec = int(self.config['dwell_min'] * 60)
                for i in range(dwell_sec):
                    if not self.running: break
                    elapsed = time.time() - start_time
                    pv = oven.get_pv()
                    self.update_live_plot(elapsed, pv, sp)
                    
                    time_rem = (dwell_sec - i) + (total_temps - t_idx - 1) * (dwell_sec + total_freqs*0.3)
                    self.update_progress(f"Dwelling @ {sp}C...", time_rem, pv, sp)
                    time.sleep(1)

                # D. Sweep & Collect Data for Plots
                self.write_log(f"Sweeping {len(freqs)} frequencies @ {sp} °C")
                step_z, step_y, step_phase = [], [], []

                for freq in freqs:
                    if not self.running: break
                    
                    lcr.set_frequency(freq)
                    time.sleep(0.2) 
                    
                    pv_now = oven.get_pv()
                    elapsed = time.time() - start_time
                    self.update_live_plot(elapsed, pv_now, sp)

                    lcr_data = lcr.get_parsed_reading()
                    
                    # Store data for end-of-step plotting
                    step_z.append(lcr_data[0]) # Z
                    step_y.append(lcr_data[1]) # Y
                    step_phase.append(lcr_data[2]) # Phase Z
                    
                    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with open(self.csv_file, 'a', newline='') as f:
                        csv.writer(f).writerow([ts, sp, pv_now, f"{freq:.2f}"] + lcr_data)
                    
                    time_rem = (total_freqs - len(step_z)) * 0.3 + (total_temps - t_idx - 1) * (dwell_sec + total_freqs*0.3)
                    self.update_progress(f"Meas: {freq:.1f}Hz", time_rem, pv_now, sp)

                # E. Generate Plots at end of step
                if self.running and step_z:
                    self.write_log(f"Generating Bode plots for {sp} °C...")
                    save_bode_plots(sp, freqs, step_z, step_phase, step_y, self.base_dir, self.base_name)

            self.write_log("=== EXPERIMENT FINISHED ===")
            
        except Exception as e:
            self.write_log(f"CRITICAL ERROR: {e}")
            messagebox.showerror("Error", str(e))
        finally:
            if self.emergency_cooldown and oven:
                self.write_log("SAFE COOLDOWN: Forcing Oven to 25°C")
                oven.set_sp(25.0)
            if lcr: lcr.close()
            self.on_finished()

    def stop(self, cooldown=True):
        self.running = False
        self.emergency_cooldown = cooldown

# =============================================================================
# MODULE 4: MAIN GUI PRO
# =============================================================================

class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AutoLCR Pro - Thermal & Frequency Suite")
        self.root.geometry("1250x800")
        
        self.worker = None

        # Data for Live Plot
        self.time_data = []
        self.pv_data = []
        self.sp_data = []

        # --- LAYOUT SETUP ---
        left_panel = ttk.Frame(root, padding=10, width=350)
        left_panel.pack(side="left", fill="y")
        
        right_panel = ttk.Frame(root, padding=10)
        right_panel.pack(side="right", fill="both", expand=True)

        # Left Panel Components
        self.create_conn_group(left_panel)
        self.create_temp_group(left_panel)
        self.create_lcr_group(left_panel)
        self.create_file_group(left_panel)
        self.create_control_group(left_panel) # Save/Load/Start/Stop

        # Right Panel Components
        self.create_dashboard(right_panel)

        self.refresh_resources()
        self.recalc_stats()

    def create_conn_group(self, parent):
        grp = ttk.LabelFrame(parent, text="1. Instruments", padding=10)
        grp.pack(fill="x", pady=5)
        self.cmb_lcr = self.add_dropdown(grp, "LCR Addr:", 0)
        self.cmb_oven = self.add_dropdown(grp, "Oven Port:", 1)
        self.ent_oven_id = self.add_entry(grp, "Oven ID:", "1", 2)

    def create_temp_group(self, parent):
        grp = ttk.LabelFrame(parent, text="2. Temperature Profile", padding=10)
        grp.pack(fill="x", pady=5)
        self.ent_start = self.add_entry(grp, "Start Temp (°C):", "30", 0)
        self.ent_end = self.add_entry(grp, "End Temp (°C):", "100", 1)
        self.ent_step = self.add_entry(grp, "Step Size (°C):", "10", 2)
        self.ent_tolerance = self.add_entry(grp, "Tolerance (°C):", "1.0", 3)
        self.ent_dwell = self.add_entry(grp, "Dwell (min):", "2", 4)
        self.ent_ramp_rate = self.add_entry(grp, "Ramp (°C/min):", "6.0", 5)

    def create_lcr_group(self, parent):
        grp = ttk.LabelFrame(parent, text="3. Frequency Sweep", padding=10)
        grp.pack(fill="x", pady=5)
        self.ent_min = self.add_entry(grp, "Min Freq (Hz):", "100", 0, bind_recalc=True)
        self.ent_max = self.add_entry(grp, "Max Freq (Hz):", "100000", 1, bind_recalc=True)
        self.ent_steps = self.add_entry(grp, "Steps/Decade:", "5", 2, bind_recalc=True)
        self.lbl_stats = ttk.Label(grp, text="Points: --", foreground="#0078D7")
        self.lbl_stats.grid(row=3, column=0, columnspan=2, pady=5)

    def create_file_group(self, parent):
        grp = ttk.LabelFrame(parent, text="4. Data Output", padding=10)
        grp.pack(fill="x", pady=5)
        self.ent_filename = ttk.Entry(grp, width=25)
        self.ent_filename.insert(0, os.path.join(os.getcwd(), "data.csv"))
        self.ent_filename.pack(side="left", fill="x", expand=True)
        ttk.Button(grp, text="...", width=3, command=self.browse_file).pack(side="right")

    def create_control_group(self, parent):
        # Profile Frame
        prof_frame = ttk.Frame(parent)
        prof_frame.pack(fill="x", pady=(10, 5))
        ttk.Button(prof_frame, text="💾 Save Profile", command=self.save_profile).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(prof_frame, text="📂 Load Profile", command=self.load_profile).pack(side="right", expand=True, fill="x", padx=2)

        # Experiment Controls
        ctrl_frame = ttk.Frame(parent)
        ctrl_frame.pack(fill="x", pady=5)
        self.btn_start = ttk.Button(ctrl_frame, text="▶ START", command=self.start_experiment)
        self.btn_start.pack(side="left", fill="x", expand=True, padx=2)
        
        self.btn_stop = tk.Button(ctrl_frame, text="⏹ EMERGENCY STOP (Cooldown)", bg="#d9534f", fg="white", font=("Arial", 9, "bold"), command=self.stop_experiment, state="disabled")
        self.btn_stop.pack(side="right", fill="x", expand=True, padx=2)

    def create_dashboard(self, parent):
        top_dash = ttk.Frame(parent)
        top_dash.pack(fill="x", pady=5)

        # Big Temp Displays
        pv_frame = ttk.Frame(top_dash)
        pv_frame.pack(side="left", expand=True)
        ttk.Label(pv_frame, text="Actual (PV)").pack()
        self.lbl_live_pv = ttk.Label(pv_frame, text="--.-- °C", font=("Consolas", 24, "bold"), foreground="#d9534f")
        self.lbl_live_pv.pack()

        sp_frame = ttk.Frame(top_dash)
        sp_frame.pack(side="left", expand=True)
        ttk.Label(sp_frame, text="Target (SP)").pack()
        self.lbl_live_sp = ttk.Label(sp_frame, text="--.-- °C", font=("Consolas", 24, "bold"), foreground="#0275d8")
        self.lbl_live_sp.pack()

        # Countdown Timer
        time_frame = ttk.Frame(top_dash)
        time_frame.pack(side="right", expand=True)
        ttk.Label(time_frame, text="Est. Time Remaining").pack()
        self.lbl_eta = ttk.Label(time_frame, text="00h 00m 00s", font=("Consolas", 18, "bold"), foreground="#5cb85c")
        self.lbl_eta.pack()

        self.lbl_main_status = ttk.Label(parent, text="Ready", font=("Arial", 11, "bold"))
        self.lbl_main_status.pack(anchor="w", pady=(10,0))

        # LIVE PLOT CANVAS
        plot_frame = ttk.Frame(parent)
        plot_frame.pack(fill="both", expand=True, pady=10)
        
        self.fig = Figure(figsize=(5, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Live Temperature Profile")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Temperature (°C)")
        self.line_pv, = self.ax.plot([], [], 'r-', label="Actual (PV)")
        self.line_sp, = self.ax.plot([], [], 'b--', label="Target (SP)")
        self.ax.legend()
        self.ax.grid(True)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # LOG AREA
        self.log_text = tk.Text(parent, height=8, state="disabled", font=("Consolas", 8), bg="#f4f4f4")
        self.log_text.pack(fill="x")

    # --- HELPER WIDGETS ---
    def add_entry(self, parent, label, default, row, bind_recalc=False):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ent = ttk.Entry(parent, width=12)
        ent.insert(0, default)
        ent.grid(row=row, column=1, sticky="e", pady=2, padx=5)
        if bind_recalc: ent.bind("<KeyRelease>", self.recalc_stats)
        return ent

    def add_dropdown(self, parent, label, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        cmb = ttk.Combobox(parent, width=15)
        cmb.grid(row=row, column=1, pady=2, padx=5)
        return cmb

    # --- LOGIC ---
    def refresh_resources(self):
        try:
            self.cmb_lcr['values'] = pyvisa.ResourceManager().list_resources()
            if self.cmb_lcr['values']: self.cmb_lcr.current(0)
            self.cmb_oven['values'] = [p.device for p in serial.tools.list_ports.comports()]
            if self.cmb_oven['values']: self.cmb_oven.current(0)
        except: pass

    def recalc_stats(self, event=None):
        try:
            mn, mx, st = float(self.ent_min.get()), float(self.ent_max.get()), float(self.ent_steps.get())
            total = int(math.log10(mx / mn) * st) + 1
            self.lbl_stats.config(text=f"Total Freq Points per step: {total}")
        except: pass

    def browse_file(self):
        f = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if f:
            self.ent_filename.delete(0, tk.END)
            self.ent_filename.insert(0, f)

    # --- PROFILE MANAGEMENT ---
    def save_profile(self):
        data = {
            "start": self.ent_start.get(), "end": self.ent_end.get(), "step": self.ent_step.get(),
            "tol": self.ent_tolerance.get(), "dwell": self.ent_dwell.get(), "ramp": self.ent_ramp_rate.get(),
            "f_min": self.ent_min.get(), "f_max": self.ent_max.get(), "f_steps": self.ent_steps.get()
        }
        f = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Profile", "*.json")])
        if f:
            with open(f, 'w') as jf: json.dump(data, jf)
            self.log_msg("Profile saved.")

    def load_profile(self):
        f = filedialog.askopenfilename(filetypes=[("Profile", "*.json")])
        if f:
            with open(f, 'r') as jf: data = json.load(jf)
            for k, entry in zip(data.keys(), [self.ent_start, self.ent_end, self.ent_step, self.ent_tolerance, self.ent_dwell, self.ent_ramp_rate, self.ent_min, self.ent_max, self.ent_steps]):
                entry.delete(0, tk.END)
                entry.insert(0, data[k])
            self.recalc_stats()
            self.log_msg("Profile loaded.")

    # --- EXPERIMENT CONTROL ---
    def start_experiment(self):
        config = {
            'lcr_addr': self.cmb_lcr.get(), 'oven_port': self.cmb_oven.get(), 'oven_id': int(self.ent_oven_id.get()),
            'start_temp': float(self.ent_start.get()), 'end_temp': float(self.ent_end.get()), 'temp_step': float(self.ent_step.get()),
            'tolerance': float(self.ent_tolerance.get()), 'dwell_min': float(self.ent_dwell.get()), 'ramp_rate': float(self.ent_ramp_rate.get()),
            'min_freq': float(self.ent_min.get()), 'max_freq': float(self.ent_max.get()), 'steps_per_decade': int(self.ent_steps.get()),
            'filename': self.ent_filename.get()
        }
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        
        # Reset Plot Data
        self.time_data, self.pv_data, self.sp_data = [], [], []

        self.worker = ExperimentWorker(config, self.log_msg, self.update_prog, self.push_plot_data, self.on_finish)
        self.worker.start()

    def stop_experiment(self):
        # E-STOP
        if self.worker:
            self.worker.stop(cooldown=True) # Forces oven to 25C
            self.log_msg("EMERGENCY STOP TRIGGERED. Cooling down...")

    def on_finish(self):
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.lbl_main_status.config(text="Finished")

    def update_prog(self, status_text, rem_sec, pv, sp):
        self.lbl_main_status.config(text=status_text)
        self.lbl_live_pv.config(text=f"{pv:.2f} °C")
        self.lbl_live_sp.config(text=f"{sp:.2f} °C")
        
        # Format ETA
        hrs, rem = divmod(int(rem_sec), 3600)
        mins, secs = divmod(rem, 60)
        self.lbl_eta.config(text=f"{hrs:02d}h {mins:02d}m {secs:02d}s")

    def push_plot_data(self, elapsed_sec, pv, sp):
        """Called by thread, updates arrays and triggers plot redraw"""
        self.time_data.append(elapsed_sec)
        self.pv_data.append(pv)
        self.sp_data.append(sp)
        
        # Update lines
        self.line_pv.set_data(self.time_data, self.pv_data)
        self.line_sp.set_data(self.time_data, self.sp_data)
        
        # Rescale axes
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

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