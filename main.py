import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Import instrument modules
try:
    from instruments.lcr_meter import LCRMeter
    from instruments.eurotherm import Eurotherm
    from acquisition.sweeper import SweepController
    from acquisition.logger import DataLogger
except ImportError as e:
    print(f"Warning: Could not import modules: {e}")
    print("Running in demo mode")

class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MatThermProfiler v1.0")
        self.root.geometry("1400x900")
        
        self.lcr = None
        self.euro = None
        self.sweeper = None
        self.logger = None
        self.acquiring = False
        self.thread = None
        
        self.setup_ui()
        
        # Setup matplotlib figure
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(12, 8))
        self.canvas = FigureCanvasTkAgg(self.fig, self.plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        plt.tight_layout()
    
    def setup_ui(self):
        # Config frame
        config_frame = ttk.LabelFrame(self.root, text="Configuration")
        config_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Row 0
        ttk.Label(config_frame, text="COM Port:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.com_var = tk.StringVar(value="COM3")
        ttk.Entry(config_frame, textvariable=self.com_var, width=10).grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        
        ttk.Label(config_frame, text="Freq Min (Hz):").grid(row=0, column=2, sticky="w", padx=5, pady=2)
        self.fmin_var = tk.DoubleVar(value=1000)
        ttk.Entry(config_frame, textvariable=self.fmin_var, width=12).grid(row=0, column=3, sticky="ew", padx=5, pady=2)
        
        ttk.Label(config_frame, text="Freq Max (Hz):").grid(row=0, column=4, sticky="w", padx=5, pady=2)
        self.fmax_var = tk.DoubleVar(value=1e6)
        ttk.Entry(config_frame, textvariable=self.fmax_var, width=12).grid(row=0, column=5, sticky="ew", padx=5, pady=2)
        
        # Row 1
        ttk.Label(config_frame, text="Steps/decade:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.steps_var = tk.IntVar(value=10)
        ttk.Entry(config_frame, textvariable=self.steps_var, width=10).grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        
        ttk.Label(config_frame, text="Target Temps (°C):").grid(row=1, column=2, sticky="w", padx=5, pady=2)
        self.temps_var = tk.StringVar(value="25,50,100")
        ttk.Entry(config_frame, textvariable=self.temps_var, width=12).grid(row=1, column=3, sticky="ew", padx=5, pady=2)
        
        ttk.Label(config_frame, text="Ramp Rate (°C/min):").grid(row=1, column=4, sticky="w", padx=5, pady=2)
        self.ramp_var = tk.DoubleVar(value=5.0)
        ttk.Entry(config_frame, textvariable=self.ramp_var, width=12).grid(row=1, column=5, sticky="ew", padx=5, pady=2)
        
        # Row 2
        ttk.Label(config_frame, text="Stability Tol (°C):").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.tol_var = tk.DoubleVar(value=0.5)
        ttk.Entry(config_frame, textvariable=self.tol_var, width=10).grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        
        ttk.Label(config_frame, text="Poll Interval (s):").grid(row=2, column=2, sticky="w", padx=5, pady=2)
        self.poll_var = tk.DoubleVar(value=2.0)
        ttk.Entry(config_frame, textvariable=self.poll_var, width=12).grid(row=2, column=3, sticky="ew", padx=5, pady=2)
        
        # Buttons frame (Row 3)
        btn_frame = ttk.Frame(config_frame)
        btn_frame.grid(row=3, column=0, columnspan=6, pady=10)
        
        ttk.Button(btn_frame, text="Connect", command=self.connect).pack(side=tk.LEFT, padx=5)
        self.start_btn = ttk.Button(btn_frame, text="Start Sweep", command=self.start_acq, state="disabled")
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.stop_acq, state="disabled")
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Export CSV", command=self.export_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Export XLSX", command=self.export_xlsx).pack(side=tk.LEFT, padx=5)
        
        # Status (Row 4)
        self.status_var = tk.StringVar(value="Disconnected")
        status_label = ttk.Label(config_frame, textvariable=self.status_var, font=("Arial", 10, "bold"))
        status_label.grid(row=4, column=0, columnspan=6, pady=5)
        
        # Column weights for responsive layout
        config_frame.columnconfigure(1, weight=1)
        config_frame.columnconfigure(3, weight=1)
        config_frame.columnconfigure(5, weight=1)
        
        # Plot frame
        self.plot_frame = ttk.Frame(self.root)
        self.plot_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    
    def connect(self):
        try:
            self.status_var.set("Connecting...")
            self.root.update()
            
            # Connect LCR Meter
            self.lcr = LCRMeter()
            
            # Connect Eurotherm
            self.euro = Eurotherm(self.com_var.get())
            
            self.status_var.set("Connected ✓")
            self.start_btn.config(state="normal")
            messagebox.showinfo("Success", "Instruments connected successfully!")
        except Exception as e:
            self.status_var.set("Connection Failed")
            messagebox.showerror("Connection Error", f"Failed to connect:\n{str(e)}")
    
    def start_acq(self):
        if not self.lcr or not self.euro:
            messagebox.showerror("Error", "Connect instruments first!")
            return
        
        try:
            # Parse temperatures
            temps = [float(t.strip()) for t in self.temps_var.get().split(",")]
            
            self.acquiring = True
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.status_var.set("Acquiring data...")
            
            # Create sweep controller
            self.sweeper = SweepController(
                self.lcr, self.euro,
                fmin=self.fmin_var.get(), 
                fmax=self.fmax_var.get(),
                steps=self.steps_var.get(),
                temps=temps, 
                ramp=self.ramp_var.get(),
                tol=self.tol_var.get(), 
                poll=self.poll_var.get()
            )
            
            # Create logger
            self.logger = DataLogger()
            
            # Start acquisition thread
            self.thread = threading.Thread(target=self.acq_loop, daemon=True)
            self.thread.start()
            
        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid input values:\n{str(e)}")
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
    
    def stop_acq(self):
        self.acquiring = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_var.set("Stopped")
    
    def acq_loop(self):
        try:
            self.sweeper.run(self.logger, lambda: self.acquiring)
            self.root.after(0, lambda: self.status_var.set("Acquisition Complete ✓"))
            self.root.after(0, self.update_plot)
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"Error: {str(e)}"))
            self.root.after(0, lambda: messagebox.showerror("Acquisition Error", str(e)))
        finally:
            self.root.after(0, lambda: self.start_btn.config(state="normal"))
            self.root.after(0, lambda: self.stop_btn.config(state="disabled"))
    
    def update_plot(self):
        if self.logger.df is None or len(self.logger.df) == 0:
            return
        
        try:
            df = self.logger.df
            
            # Clear axes
            self.ax1.clear()
            self.ax2.clear()
            
            # Plot by temperature
            temps_unique = sorted(df['temp'].unique())
            
            for temp in temps_unique:
                df_temp = df[df['temp'] == temp]
                
                # Convert Z to complex if string format
                Z_vals = []
                for z in df_temp['Z']:
                    try:
                        Z_vals.append(float(z))
                    except:
                        Z_vals.append(np.abs(complex(z)))
                
                # Magnitude plot
                self.ax1.loglog(df_temp['freq'], Z_vals, 'o-', label=f'{temp:.1f}°C', markersize=4)
                
                # Phase plot
                self.ax2.semilogx(df_temp['freq'], df_temp['theta'], 'o-', label=f'{temp:.1f}°C', markersize=4)
            
            # Format plots
            self.ax1.set_xlabel('Frequency (Hz)', fontsize=10)
            self.ax1.set_ylabel('|Z| (Ω)', fontsize=10)
            self.ax1.set_title('Impedance Magnitude vs Frequency', fontsize=12, fontweight='bold')
            self.ax1.legend(loc='best', fontsize=8)
            self.ax1.grid(True, which='both', alpha=0.3)
            
            self.ax2.set_xlabel('Frequency (Hz)', fontsize=10)
            self.ax2.set_ylabel('Phase (°)', fontsize=10)
            self.ax2.set_title('Phase Angle vs Frequency', fontsize=12, fontweight='bold')
            self.ax2.legend(loc='best', fontsize=8)
            self.ax2.grid(True, which='both', alpha=0.3)
            
            plt.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            print(f"Plot error: {e}")
    
    def export_csv(self):
        if self.logger is None or self.logger.df is None or len(self.logger.df) == 0:
            messagebox.showwarning("No Data", "No data to export!")
            return
        
        try:
            file = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if file:
                self.logger.df.to_csv(file, index=False)
                messagebox.showinfo("Exported", f"Data saved to:\n{file}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export:\n{str(e)}")
    
    def export_xlsx(self):
        if self.logger is None or self.logger.df is None or len(self.logger.df) == 0:
            messagebox.showwarning("No Data", "No data to export!")
            return
        
        try:
            file = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
            )
            if file:
                self.logger.df.to_excel(file, index=False)
                messagebox.showinfo("Exported", f"Data saved to:\n{file}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export:\n{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()
