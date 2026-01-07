import pyvisa
import numpy as np
import time

class LCRMeter:
    def __init__(self):
        rm = pyvisa.ResourceManager('pyvisa-py')  # Pure Python backend
        resources = rm.list_resources()
        self.instr = None
        for res in resources:
            if '3536' in res.upper() or 'LCR' in res.upper():
                self.instr = rm.open_resource(res)
                break
        if not self.instr:
            raise ConnectionError("Hioki IM3536 not found. Check USB.")
        self.instr.write('*RST')  # Reset
        self.instr.write(':CALC:PAR ZS')  # ZS mode
        self.instr.write(':CALC:FORM ABS')  # Absolute
    
    def set_frequency(self, freq):
        self.instr.write(f':FREQ {freq}')
        time.sleep(0.1)  # Settle
    
    def measure(self):
        data = self.instr.query(':CALC:DATA? Z,THETA,RS,RP,CS,CP,LS,LP,D,Q')
        vals = data.strip().split(',')
        return {
            'Z': vals[0], 'theta': float(vals[1]), 'Rs': vals[2], 'Rp': vals[3],
            'Cs': vals[4], 'Cp': vals[5], 'Ls': vals[6], 'Lp': vals[7],
            'tan_d': float(vals[8]), 'Q': float(vals[9])
        }
    
    def close(self):
        if self.instr:
            self.instr.close()
