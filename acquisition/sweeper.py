import numpy as np
import time
from typing import List, Dict

class SweepController:
    def __init__(self, lcr, euro, fmin, fmax, steps, temps, ramp, tol, poll):
        self.lcr = lcr
        self.euro = euro
        self.freqs = self._gen_freqs(fmin, fmax, steps)
        self.temps = temps
        self.ramp = ramp
        self.tol = tol
        self.poll = poll
    
    def _gen_freqs(self, fmin, fmax, steps):
        decades = np.log10(fmax / fmin)
        return np.logspace(np.log10(fmin), np.log10(fmax), int(decades * steps) + 1)
    
    def run(self, logger):
        prev_temp = self.euro.read_pv()
        for target_temp in self.temps:
            self.euro.set_setpoint(target_temp)
            self.euro.set_ramp_rate(self.ramp)
            current_temp = self.euro.wait_stable(target_temp, self.tol)
            print(f"Stable at {current_temp}°C")
            
            for freq in self.freqs:
                self.lcr.set_frequency(freq)
                data = self.lcr.measure()
                data.update({'freq': freq, 'temp': current_temp, 'timestamp': time.time()})
                logger.log(data)
                time.sleep(self.poll)
