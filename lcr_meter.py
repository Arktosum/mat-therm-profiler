import tkinter as tk
from tkinter import ttk, messagebox
import pyvisa


class LCRMeterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("IM3536 LCR Meter Controller")
        # Increased height to fit the debug section
        self.root.geometry("450x550")

        self.inst = None

        # Robust ResourceManager init
        try:
            self.rm = pyvisa.ResourceManager()
        except OSError:
            self.rm = pyvisa.ResourceManager('@py')

        # ============================================
        # SECTION 1: CONNECTION
        # ============================================
        conn_frame = ttk.LabelFrame(root, text="Connection", padding=10)
        conn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(conn_frame, text="Select Device:").grid(
            row=0, column=0, sticky="w")

        self.addr_combo = ttk.Combobox(conn_frame, width=35)
        self.addr_combo.grid(row=1, column=0, pady=5, padx=5)

        self.btn_refresh = ttk.Button(
            conn_frame, text="Refresh", command=self.refresh_devices)
        self.btn_refresh.grid(row=1, column=1, padx=2)

        self.btn_connect = ttk.Button(
            conn_frame, text="Connect", command=self.connect_instrument)
        self.btn_connect.grid(row=1, column=2, padx=5)

        self.lbl_status = ttk.Label(
            conn_frame, text="Status: Disconnected", foreground="red")
        self.lbl_status.grid(row=2, column=0, columnspan=3, sticky="w")

        # ============================================
        # SECTION 2: MEASUREMENT CONTROL
        # ============================================
        ctrl_frame = ttk.LabelFrame(
            root, text="Measurement Control", padding=10)
        ctrl_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(ctrl_frame, text="Frequency (Hz):").grid(
            row=0, column=0, sticky="w")
        self.freq_entry = ttk.Entry(ctrl_frame, width=15)
        self.freq_entry.insert(0, "1000")
        self.freq_entry.grid(row=0, column=1, pady=5, sticky="w")

        self.btn_measure = ttk.Button(
            ctrl_frame, text="Set Freq & Measure", command=self.measure_reading, state="disabled")
        self.btn_measure.grid(row=1, column=0, columnspan=2, pady=10)

        ttk.Label(ctrl_frame, text="Main Output:").grid(
            row=2, column=0, sticky="nw")
        self.result_text = tk.Text(
            ctrl_frame, height=4, width=40, state="disabled", bg="#f0f0f0")
        self.result_text.grid(row=3, column=0, columnspan=2, pady=5)

        # ============================================
        # SECTION 3: DEBUG / COMMAND SENDER (NEW)
        # ============================================
        debug_frame = ttk.LabelFrame(
            root, text="Debug / Command Sender", padding=10)
        debug_frame.pack(fill="both", expand=True, padx=10, pady=5)

        ttk.Label(debug_frame, text="SCPI Command:").grid(
            row=0, column=0, sticky="w")

        # Entry for typing manual commands (e.g., "*IDN?" or ":CORR:OPEN:EXEC")
        self.cmd_entry = ttk.Entry(debug_frame, width=30)
        self.cmd_entry.grid(row=0, column=1, padx=5, sticky="w")
        # Press Enter to send
        self.cmd_entry.bind('<Return>', lambda event: self.send_manual_cmd())

        self.btn_send = ttk.Button(
            debug_frame, text="Send", command=self.send_manual_cmd, state="disabled")
        self.btn_send.grid(row=0, column=2, padx=5)

        ttk.Label(debug_frame, text="Debug Response:").grid(
            row=1, column=0, sticky="nw", pady=(10, 0))
        self.debug_text = tk.Text(
            debug_frame, height=5, width=40, state="disabled", bg="#e6e6e6", font=("Consolas", 9))
        self.debug_text.grid(row=2, column=0, columnspan=3,
                             pady=5, sticky="nsew")

        # Auto-scan on startup
        self.refresh_devices()

    def refresh_devices(self):
        try:
            devices = self.rm.list_resources()
            self.addr_combo['values'] = devices
            if devices:
                self.addr_combo.current(0)
            else:
                self.addr_combo.set("No devices found")
        except Exception as e:
            self.addr_combo.set("Error scanning")
            print(f"Scan error: {e}")

    def connect_instrument(self):
        try:
            self.inst = self.rm.open_resource(self.addr_combo.get())
            self.inst.timeout = 5000
            idn = self.inst.query("*IDN?")
            self.lbl_status.config(
                text=f"Connected: {idn.strip()}", foreground="green")

            # Enable buttons
            self.btn_measure.config(state="normal")
            self.btn_send.config(state="normal")
            self.btn_connect.config(state="disabled")
            self.addr_combo.config(state="disabled")

        except Exception as e:
            messagebox.showerror("Connection Error",
                                 f"Could not connect:\n{e}")

    def measure_reading(self):
        if self.inst is None:
            return
        try:
            # 1. Set Frequency
            freq_val = self.freq_entry.get()
            self.inst.write(f":FREQuency {freq_val}")

            # 2. Configure Measurements (Turn on commonly used parameters)
            self.inst.write(":MEASure:ITEM 255,0,0")

            # 3. Trigger and Read
            reading = self.inst.query(":MEASure?")

            # 4. Display
            self.result_text.config(state="normal")
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, reading)
            self.result_text.config(state="disabled")

        except Exception as e:
            messagebox.showerror("Measurement Error", f"Failed:\n{e}")

    def send_manual_cmd(self):
        """Sends the command typed in the debug box"""
        if self.inst is None:
            messagebox.showwarning("Warning", "Connect to instrument first.")
            return

        cmd = self.cmd_entry.get().strip()
        if not cmd:
            return

        try:
            # Logic: If it has a '?', we wait for a response (Query).
            # If not, we just send it (Write).
            if "?" in cmd:
                response = self.inst.query(cmd)
                display_str = f">> {cmd}\n{response.strip()}"
            else:
                self.inst.write(cmd)
                display_str = f">> {cmd}\n(Command Sent)"

            # Update Debug Window
            self.debug_text.config(state="normal")
            self.debug_text.delete(1.0, tk.END)
            self.debug_text.insert(tk.END, display_str)
            self.debug_text.config(state="disabled")

        except Exception as e:
            self.debug_text.config(state="normal")
            self.debug_text.delete(1.0, tk.END)
            self.debug_text.insert(tk.END, f"Error: {e}")
            self.debug_text.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    app = LCRMeterGUI(root)
    root.mainloop()
