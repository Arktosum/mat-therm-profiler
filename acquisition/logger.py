import pandas as pd
from collections import deque
from datetime import datetime

class DataLogger:
    def __init__(self, max_rows=10000):
        self.buffer = deque(maxlen=max_rows)
        self.df = None
    
    def log(self, data: dict):
        self.buffer.append(data)
        self.df = pd.DataFrame(list(self.buffer))
        print(f"Logged: {len(self.buffer)} rows")
