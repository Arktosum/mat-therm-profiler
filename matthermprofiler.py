#!/usr/bin/env python3
# =============================================================================
# matthermprofiler.py — Entry point
# Run from project root:  python matthermprofiler.py
# =============================================================================
import tkinter as tk
from src.gui.app import MainApp

if __name__ == "__main__":
    root = tk.Tk()
    app  = MainApp(root)
    root.mainloop()