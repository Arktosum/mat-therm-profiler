pyinstaller --onefile --collect-all pyvisa_py --hidden-import pyusb lcr_meter.py


pyinstaller --onefile --collect-all pyvisa_py eurotherm.py


pyinstaller  --onefile --collect-all pyvisa_py --hidden-import pyusb --hidden-import serial matthermprofiler.py