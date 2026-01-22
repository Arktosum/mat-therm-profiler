import tkinter as tk
from tkinter import ttk, messagebox
import minimalmodbus
import serial
import serial.tools.list_ports

class EurothermGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Eurotherm 3216 - Live Monitor")
        self.root.geometry("500x500")
        
        self.inst = None
        self.monitoring = False  # Flag to control the loop
        
        # --- Connection Section ---
        conn_frame = ttk.LabelFrame(root, text="Connection", padding=10)
        conn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(conn_frame, text="COM Port:").grid(row=0, column=0, sticky="w")
        self.port_combo = ttk.Combobox(conn_frame, width=25)
        self.port_combo.grid(row=0, column=1, padx=5, sticky="w")
        
        self.btn_refresh = ttk.Button(conn_frame, text="Ref", width=5, command=self.refresh_ports)
        self.btn_refresh.grid(row=0, column=2, padx=2)

        ttk.Label(conn_frame, text="ID:").grid(row=1, column=0, sticky="w", pady=5)
        self.addr_entry = ttk.Entry(conn_frame, width=5)
        self.addr_entry.insert(0, "1") 
        self.addr_entry.grid(row=1, column=1, sticky="w", padx=5)

        self.btn_connect = ttk.Button(conn_frame, text="Connect & Start", command=self.connect_and_start)
        self.btn_connect.grid(row=1, column=1, columnspan=2, sticky="e", padx=5)

        self.lbl_status = ttk.Label(conn_frame, text="Status: Disconnected", foreground="red")
        self.lbl_status.grid(row=2, column=0, columnspan=3, sticky="w", pady=(5,0))

        # --- Dashboard (Live Readings) ---
        dash_frame = ttk.LabelFrame(root, text="Live Readings", padding=10)
        dash_frame.pack(fill="x", padx=10, pady=5)

        # Process Variable (Actual Temp)
        pv_frame = ttk.Frame(dash_frame, borderwidth=2, relief="groove")
        pv_frame.pack(side="left", fill="both", expand=True, padx=5)
        ttk.Label(pv_frame, text="Current Temp (PV)", font=("Arial", 10)).pack(anchor="n", pady=5)
        self.lbl_pv = ttk.Label(pv_frame, text="--.-- °C", font=("Consolas", 22, "bold"), foreground="#d9534f")
        self.lbl_pv.pack(anchor="center", pady=10)

        # Setpoint (Target Temp)
        sp_frame = ttk.Frame(dash_frame, borderwidth=2, relief="groove")
        sp_frame.pack(side="left", fill="both", expand=True, padx=5)
        ttk.Label(sp_frame, text="Target (SP)", font=("Arial", 10)).pack(anchor="n", pady=5)
        self.lbl_sp = ttk.Label(sp_frame, text="--.-- °C", font=("Consolas", 22, "bold"), foreground="#0275d8")
        self.lbl_sp.pack(anchor="center", pady=10)

        # --- Control Section ---
        ctrl_frame = ttk.LabelFrame(root, text="Control", padding=10)
        ctrl_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(ctrl_frame, text="Set New Target:").pack(side="left")
        self.sp_entry = ttk.Entry(ctrl_frame, width=10)
        self.sp_entry.pack(side="left", padx=5)
        
        self.btn_write = ttk.Button(ctrl_frame, text="Update", command=self.write_setpoint, state="disabled")
        self.btn_write.pack(side="left", padx=5)

        self.btn_stop = ttk.Button(ctrl_frame, text="Stop Monitoring", command=self.stop_monitoring, state="disabled")
        self.btn_stop.pack(side="right", padx=5)

        # --- Log ---
        log_frame = ttk.LabelFrame(root, text="Log", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.log_text = tk.Text(log_frame, height=6, state="disabled", font=("Consolas", 8))
        self.log_text.pack(fill="both", expand=True)

        self.refresh_ports()

    def log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        self.port_combo['values'] = [f"{p.device}" for p in ports]
        if ports: self.port_combo.current(0)

    def connect_and_start(self):
        try:
            port = self.port_combo.get().split(" ")[0]
            addr = int(self.addr_entry.get())

            # Setup Instrument
            self.inst = minimalmodbus.Instrument(port, addr)
            self.inst.serial.baudrate = 9600
            self.inst.serial.timeout  = 0.2  # Very fast timeout for live loop
            self.inst.clear_buffers_before_each_transaction = True

            # Verify connection with one read
            self.inst.read_register(1, number_of_decimals=2)
            
            self.lbl_status.config(text=f"Connected: {port} (ID {addr})", foreground="green")
            self.btn_connect.config(state="disabled")
            self.btn_write.config(state="normal")
            self.btn_stop.config(state="normal")
            
            # START THE LOOP
            self.monitoring = True
            self.log("Connected. Starting live monitoring...")
            self.monitor_loop()

        except Exception as e:
            messagebox.showerror("Error", f"Connection Failed:\n{e}")
            self.log(f"Conn Error: {e}")

    def monitor_loop(self):
        """This function calls itself every 500ms to keep readings live"""
        if not self.monitoring or not self.inst:
            return

        try:
            # FIXED: Changed number_of_decimals to 2
            pv = self.inst.read_register(1, number_of_decimals=2)
            sp = self.inst.read_register(2, number_of_decimals=2)

            self.lbl_pv.config(text=f"{pv:.2f} °C")
            self.lbl_sp.config(text=f"{sp:.2f} °C")
            
            # Schedule the next read in 500ms
            self.root.after(500, self.monitor_loop)

        except Exception as e:
            # If a read fails, log it but don't crash the app
            self.lbl_status.config(text="Status: Read Error (Retrying...)", foreground="orange")
            print(f"Read error: {e}")
            # Retry slightly slower (1000ms)
            self.root.after(1000, self.monitor_loop)

    def write_setpoint(self):
        if not self.inst: return
        try:
            val = float(self.sp_entry.get())
            # Pause monitoring briefly to write safely
            self.monitoring = False
            
            # FIXED: Write with 2 decimals
            self.inst.write_register(2, val, number_of_decimals=2)
            self.log(f"Set Target -> {val}")
            
            # Resume monitoring
            self.monitoring = True
            self.monitor_loop()
            
        except Exception as e:
            self.monitoring = True # Ensure we restart even if write fails
            self.monitor_loop()
            messagebox.showerror("Write Error", str(e))

    def stop_monitoring(self):
        self.monitoring = False
        self.btn_connect.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.lbl_status.config(text="Status: Paused", foreground="blue")
        self.log("Monitoring paused.")

if __name__ == "__main__":
    root = tk.Tk()
    app = EurothermGUI(root)
    root.mainloop()