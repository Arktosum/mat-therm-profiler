# MatThermProfiler



**Automated Materials Thermal Characterization Platform** - Frequency-domain electrical parameter profiling (impedance, capacitance, inductance, dissipation) vs controlled temperature sweeps with live visualization and CSV/XLSX export.

## 🎯 Features

- **Multi-parameter sweeps**: Z, ∠θ, Rs/Rp, Cs/Cp, Ls/Lp, tanδ, Q
- **Thermal synchronization**: Ramp/soak profiles with stability detection
- **Live Bode plots**: |Z| & ∠θ vs log-frequency per temperature
- **Tkinter GUI**: Configurable sweeps, real-time monitoring
- **Thread-safe acquisition**: Non-blocking UI updates
- **Pandas logging**: Timestamped CSV/XLSX with full metadata

## 🛠️ Quick Start

```bash
# Clone & install
git clone https://github.com/Arktosum/mat-therm-profiler
cd mat-therm-profiler
pip install -r requirements.txt

# Hardware: LCR Meter (USB), PID Controller (RS485/USB-adapter)
python main.py
```

## 📋 Hardware Setup

```
LCR Meter ── USB ── PC
PID Controller ── RS485 ── USB-RS485 ── PC (COM3)
```

**PID Config**: Modbus RTU, Slave ID=1, 9600 baud

## 🎛️ GUI Controls

| Parameter | Default | Description |
|-----------|---------|-------------|
| Freq Min | 4 mHz | Sweep start (logspace) |
| Freq Max | 8 MHz | Sweep end |
| Steps/decade | 10 | Resolution |
| Target Temps | 25,50,100°C | Ramp sequence |
| Ramp Rate | 5°C/min | PID setpoint rate |
| Stability Tol | 0.5°C | Hold before sweep |
| Poll Interval | 2s | Acquisition rate |

**Workflow**: Connect → Config → Start → Live Plot → Stop → Export

## 🏗️ Architecture

```
MatThermProfiler/
├── README.md              # This file
├── main.py                # Tkinter GUI entrypoint
├── instruments/
│   ├── __init__.py
│   ├── lcr_meter.py       # PyVISA SCPI driver
│   └── eurotherm.py       # minimalmodbus RTU
├── acquisition/
│   ├── __init__.py
│   ├── sweeper.py         # Freq/temp logic
│   └── logger.py          # Pandas DataFrame
├── ui/
│   ├── __init__.py
│   └── main_window.py     # Embedded plots
└── requirements.txt
```

## 📊 Sample Data Output

```csv
timestamp,temp,freq,Z,theta,Rs,Rp,Cs,Cp,Ls,Lp,tan_d,Q
1699123456.1,25.2,1e3,"1.23k+45j",12.5,1.2k,10M,47nF,50nF,1.2uH,1.5uH,0.15,6.67
1699123458.3,25.1,10e3,"987+23j",8.2,950,5M,48nF,51nF,1.1uH,1.4uH,0.12,8.33
```

## 🔧 Installation

```bash
pip install pyvisa-py pyvisa minimalmodbus pandas numpy matplotlib pyserial
```

## 🚀 Usage

1. **Connect hardware** (USB LCR, RS485 PID)
2. `python main.py`
3. **Configure sweep** (freq range, target temps, ramp rate)
4. **Connect instruments** → **Start Sweep** 
5. **Monitor live Bode plots** → **Stop** → **Export CSV/XLSX**

## 🔬 Research Applications

- **Dielectrics**: εr, tanδ vs temperature/frequency
- **HPHT materials**: Diamond anvil cell characterization
- **Polymers/Composites**: Glass transition monitoring
- **Ferroelectrics**: Phase transitions
- **Semiconductors**: Temperature-dependent impedance

## 🧪 Development Roadmap

- [x] Modular instrument drivers
- [x] Tkinter GUI + live plots
- [x] Thread-safe acquisition
- [ ] YAML configuration files
- [ ] Multi-sample correction (open/short/load)
- [ ] Advanced plotting (Nyquist, Cole-Cole)
- [ ] REST API for lab integration

## 📚 References

- LCR measurement theory and SCPI protocols
- PID thermal ramp/soak control (Modbus RTU)
- Built for IIT Madras materials characterization research

## 🤝 Contributing

1. Fork → Branch (`feat/your-feature`)
2. `pip install -r requirements.txt`
3. `black .` (code formatting)
4. Test → PR

**License**: MIT

***

⭐ **Star if useful for your materials lab!** 🚀
**Issues**: [New Issue](https://github.com/Arktosum/mat-therm-profiler/issues)
