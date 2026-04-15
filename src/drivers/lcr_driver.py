# =============================================================================
# drivers/lcr_driver.py — Hioki IM3536 LCR Meter (PyVISA)
# =============================================================================
import pyvisa
from src.constants import LCR_LABELS


class LCRDriver:
    def __init__(self, resource_str):
        try:
            rm = pyvisa.ResourceManager()
        except OSError:
            rm = pyvisa.ResourceManager('@py')
            
        self.inst = rm.open_resource(resource_str)
        self.inst.timeout = 3000
        
        # --- NEW: ADD THESE TWO LINES ---
        self.inst.read_termination = '\n'
        self.inst.write_termination = '\n'
        # --------------------------------
        self.inst.write("*RST")         # Clear the machine

        self.inst.write(":MEASure:VALid 0")         # Turns OFF the annoying status byte
        self.inst.write(":TRIGger INTernal")        
        self.inst.write(":MEASure:ITEM 31,31,0")    # Requests our exact 10 parameters

    def set_frequency(self, freq: float):
        self.inst.write(f":FREQuency {freq}")

    def set_voltage(self, voltage: float):
        self.inst.write(f":VOLTage {voltage}")

    def get_parsed_reading(self) -> list:
        try:
            raw   = self.inst.query(":MEASure?").strip()
            parts = raw.split(',')
            return [float(p) if '*' not in p else 0.0 for p in parts]
        except Exception:
            return [0.0] * len(LCR_LABELS)

    def close(self):
        if self.inst:
            self.inst.close()