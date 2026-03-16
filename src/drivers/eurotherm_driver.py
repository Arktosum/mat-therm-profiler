# =============================================================================
# drivers/eurotherm_driver.py — Eurotherm 3216 via Modbus RTU (minimalmodbus)
# =============================================================================
import minimalmodbus


class EurothermDriver:
    """
    Register map (Eurotherm 3216):
      1  — Process Variable (actual temp)
      2  — Target Setpoint
      5  — Working Setpoint (ramp ghost SP)
      35 — Ramp Rate (°C/min)
    """

    def __init__(self, port: str, address: int = 1):
        self.inst = minimalmodbus.Instrument(port, address)
        self.inst.serial.baudrate = 9600
        self.inst.serial.timeout = 1.0
        self.inst.clear_buffers_before_each_transaction = True

    def get_pv(self) -> float:
        """Read actual temperature (Process Variable)."""
        return self.inst.read_register(1, number_of_decimals=1)

    def get_sp(self) -> float:
        """Read final target setpoint."""
        return self.inst.read_register(2, number_of_decimals=1)

    def get_wsp(self) -> float:
        """Read working setpoint (the ramping ghost SP)."""
        return self.inst.read_register(5, number_of_decimals=1)

    def set_sp(self, value: float):
        """Write a new target setpoint."""
        self.inst.write_register(2, value, number_of_decimals=1)

    def get_ramp_rate(self) -> float:
        """Read back ramp rate register 35 with 2 decimal places."""
        try:
            return self.inst.read_register(35, number_of_decimals=2)
        except IOError:
            return 0.0

    def set_ramp_rate(self, rate_per_min: float):
        """
        Write ramp rate in °C/min to register 35.
        Register 35 uses 2 decimal places internally — so 6.0 sends 600 on the wire,
        which the Eurotherm front panel correctly shows as 6.00 °C/min.
        """
        try:
            self.inst.write_register(35, rate_per_min, number_of_decimals=2)
        except IOError:
            pass
