import minimalmodbus
import time

class Eurotherm:
    MODBUS_ID = 1
    BAUDRATE = 9600
    
    # Common registers (adapt from full map)
    REG_PV = 0x0001      # Process Value
    REG_SP1 = 0x0000      # Setpoint 1
    REG_SPRAT = 0x4000    # Ramp Rate (example)
    
    def __init__(self, port):
        self.instr = minimalmodbus.Instrument(port, self.MODBUS_ID)
        self.instr.serial.baudrate = self.BAUDRATE
        self.instr.serial.timeout = 1
        self.instr.mode = minimalmodbus.MODE_RTU
    
    def set_ramp_rate(self, rate):
        self.instr.write_register(self.REG_SPRAT, rate)
    
    def set_setpoint(self, sp):
        self.instr.write_register(self.REG_SP1, sp)
    
    def read_pv(self):
        return self.instr.read_register(self.REG_PV)
    
    def wait_stable(self, target, tol, timeout=300, poll=2):
        start = time.time()
        while time.time() - start < timeout:
            pv = self.read_pv()
            if abs(pv - target) < tol:
                return pv
            time.sleep(poll)
        raise TimeoutError(f"Temp not stable at {target}±{tol}")
