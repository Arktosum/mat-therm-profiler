# =============================================================================
# drivers/lcr_driver.py — Hioki IM3536 LCR Meter (PyVISA)
# =============================================================================
import pyvisa
import time
from src.constants import LCR_LABELS


class LCRDriver:
    def __init__(self, resource_str):
        try:
            rm = pyvisa.ResourceManager()
        except OSError:
            rm = pyvisa.ResourceManager('@py')

        self.inst = rm.open_resource(resource_str)
        self.inst.timeout = 3000

        self.inst.read_termination = '\n'
        self.inst.write_termination = '\n'

        self.inst.write("*RST")         # Clear the machine

        # Turns OFF the annoying status byte
        self.inst.write(":MEASure:VALid 0")
        self.inst.write(":TRIGger INTernal")
        # Requests our exact 10 parameters
        self.inst.write(":MEASure:ITEM 31,31,0")

    def set_frequency(self, freq: float):
        self.inst.write(f":FREQuency {freq}")

    def set_voltage(self, voltage: float):
        self.inst.write(f":VOLTage {voltage}")

    def apply_advanced_settings(self, config: dict, logger):
        """Translates the UI Advanced Settings into Hioki SCPI commands."""

        def safe_write(cmd, desc):
            try:
                self.inst.write(cmd)
            except Exception as e:
                logger(f"LCR Warning: Failed to set {desc} -> {e}")

        # 1. Speed
        speed = config.get('adv_speed', 'MED')
        safe_write(f":SPEED {speed}", f"Speed to {speed}")

        # 2. Averaging
        avg = config.get('adv_avg', 'OFF').strip().upper()
        if avg == "OFF":
            safe_write(":AVERage:STATe OFF", "Avg OFF")
        else:
            safe_write(":AVERage:STATe ON", "Avg ON")
            safe_write(f":AVERage {avg}", f"Avg Count to {avg}")

        # 3. Delay
        try:
            delay = float(config.get('adv_delay', 0))
            safe_write(f":TRIGger:DELay {delay}", f"Delay to {delay}s")
        except ValueError:
            pass

        # 4. Range
        rng = config.get('adv_range', 'AUTO').strip()
        if rng == "AUTO":
            safe_write(":RANGe:AUTO ON", "Range AUTO")
        else:
            # Map UI strings to standard engineering notation for SCPI
            # e.g., "100mΩ" -> 0.1, "1kΩ" -> 1E3
            rmap = {"100mΩ": "0.1", "1Ω": "1", "10Ω": "10", "100Ω": "100",
                    "1kΩ": "1E3", "10kΩ": "10E3", "100kΩ": "100E3",
                    "1MΩ": "1E6", "10MΩ": "10E6", "100MΩ": "100E6"}
            val = rmap.get(rng, "1E3")
            safe_write(f":RANGe {val}", f"Range HOLD to {rng}")

        # 5. Low Z
        lowz = config.get('adv_lowz', 'OFF')
        safe_write(f":MEASure:LOWZ {lowz}", f"LowZ to {lowz}")

        # 6. DC Bias
        dcbias = config.get('adv_dcbias', 'OFF').strip().upper()
        if dcbias == "OFF":
            safe_write(":DCBias:STATe OFF", "DC Bias OFF")
        else:
            try:
                volts = float(dcbias)
                safe_write(":DCBias:STATe ON", "DC Bias ON")
                safe_write(f":DCBias:VOLTage {volts}", f"DC Bias to {volts}V")
            except ValueError:
                pass

        # 7. Cable Length (0m, 1m, 2m, 4m)
        cable = config.get('adv_cable', '0m').replace('m', '')
        safe_write(f":CORRection:CABLe {cable}", f"Cable to {cable}m")

        # 8. Compensations (Open, Short, Load)
        for comp in ["OPEN", "SHORt", "LOAD"]:
            val = config.get(f'adv_{comp.lower()}', 'OFF')
            
            # FIXED: Removed the ":STATe" part for Hioki compatibility
            safe_write(f":CORRection:{comp} {val}", f"{comp} Comp to {val}")

        # 9. Sync & Triggers
        sync = config.get('adv_sync', 'OFF')
        jsync = config.get('adv_jsync', 'OFF')
        safe_write(f":DCBias:SYNc {sync}", f"SYNC to {sync}")
        safe_write(f":TRIGger:SYNc {jsync}", f"J SYNC to {jsync}")

        # 10. Limits, Scale, and Judge
        limit = config.get('adv_limit', 'OFF')
        judge = config.get('adv_judge', 'OFF')
        scale = config.get('adv_scale', 'OFF')

        safe_write(f":CALCulate1:LIMit:STATe {limit}", f"Limit to {limit}")
        safe_write(f":CALCulate3:LIMit:STATe {judge}", f"Judge to {judge}")
        safe_write(f":CALCulate:SCALe:STATe {scale}", f"Scale to {scale}")

        # Give the machine a moment to process the massive dump of settings
        time.sleep(0.5)

    def get_parsed_reading(self) -> list:
        try:
            raw = self.inst.query(":MEASure?").strip()
            parts = raw.split(',')
            return [float(p) if '*' not in p else 0.0 for p in parts]
        except Exception:
            return [0.0] * len(LCR_LABELS)

    def close(self):
        if self.inst:
            self.inst.close()
