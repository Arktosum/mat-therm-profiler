# =============================================================================
# gui/dashboard.py — Right-side dashboard: readouts, live plot, LCR panel, log
# =============================================================================
import tkinter as tk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from src.constants import (
    C_BG, C_PANEL, C_PANEL_ALT, C_BORDER, C_BORDER_DARK,
    C_ACCENT, C_ACCENT2, C_GREEN, C_AMBER,
    C_TEXT, C_TEXT_MID, C_TEXT_DIM,
    LCR_LABELS, LCR_UNITS, DISPLAY_COLORS, FONT,
)
from src.gui.styles import F_BODY, F_SMALL, F_LABEL, F_BOLD, F_MONO, F_MONO_L, F_MONO_XL


class Dashboard:
    """
    Right-side dashboard panel.
    Exposes update_readouts(), update_plot(), update_lcr(), set_status(), log().
    """

    def __init__(self, parent: tk.Frame):
        self.parent = parent
        self._build_readout_bar()
        self._build_status_label()
        self._build_content_area()
        self._build_log_console()

    # -------------------------------------------------------------------------
    # Construction
    # -------------------------------------------------------------------------

    def _build_readout_bar(self):
        bar = tk.Frame(self.parent, bg=C_PANEL,
                       highlightthickness=1, highlightbackground=C_BORDER)
        bar.pack(fill="x", pady=(0, 8))

        def _readout(parent, title, color, attr, side="left"):
            frm = tk.Frame(parent, bg=C_PANEL)
            frm.pack(side=side, fill="both", expand=True, padx=2, pady=6)
            tk.Label(frm, text=title, font=(FONT, 7, "bold"),
                     bg=C_PANEL, fg=C_TEXT_DIM).pack(anchor="nw", padx=12, pady=(6, 0))
            lbl = tk.Label(frm, text="--.-- °C", font=F_MONO_XL,
                           bg=C_PANEL, fg=color)
            lbl.pack(anchor="nw", padx=12)

            # Thin colored underline
            tk.Frame(frm, bg=color, height=2).pack(
                fill="x", padx=12, pady=(2, 6))
            setattr(self, attr, lbl)

        _readout(bar, "ACTUAL TEMP  (PV)", C_ACCENT2, "lbl_pv")

        # Vertical divider
        tk.Frame(bar, bg=C_BORDER, width=1).pack(side="left", fill="y", pady=6)

        _readout(bar, "TARGET TEMP  (SP)", C_ACCENT, "lbl_sp")

        tk.Frame(bar, bg=C_BORDER, width=1).pack(side="left", fill="y", pady=6)

        _readout(bar, "WORKING SP", C_AMBER, "lbl_wsp")

        # ETA — right side
        tk.Frame(bar, bg=C_BORDER, width=1).pack(
            side="right", fill="y", pady=6)
        eta_frm = tk.Frame(bar, bg=C_PANEL)
        eta_frm.pack(side="right", fill="both", padx=2, pady=6)
        tk.Label(eta_frm, text="EST. REMAINING", font=(FONT, 7, "bold"),
                 bg=C_PANEL, fg=C_TEXT_DIM).pack(anchor="ne", padx=12, pady=(6, 0))
        self.lbl_eta = tk.Label(eta_frm, text="00h 00m 00s",
                                font=("Consolas", 18, "bold"),
                                bg=C_PANEL, fg=C_TEXT_MID)
        self.lbl_eta.pack(anchor="ne", padx=12)
        tk.Frame(eta_frm, bg=C_TEXT_DIM, height=2).pack(
            fill="x", padx=12, pady=(2, 6))

    def _build_status_label(self):
        self.lbl_status = tk.Label(self.parent,
                                   text="● Ready",
                                   font=(FONT, 9, "bold"),
                                   bg=C_BG, fg=C_GREEN)
        self.lbl_status.pack(anchor="w", pady=(0, 4))

    def _build_content_area(self):
        self.content_frame = tk.Frame(self.parent, bg=C_BG)
        self.content_frame.pack(fill="both", expand=True)

        # Temperature plot — always visible
        self.plot_frame = tk.Frame(self.content_frame, bg=C_BG)
        self.plot_frame.pack(side="left", fill="both", expand=True)
        self._build_temp_plot(self.plot_frame)

        # LCR panel — toggled by mode
        self.lcr_panel = tk.Frame(self.content_frame, bg=C_PANEL,
                                  width=230,
                                  highlightthickness=1,
                                  highlightbackground=C_BORDER)
        self._build_lcr_panel(self.lcr_panel)

    def _build_temp_plot(self, parent):
        self.fig = Figure(figsize=(5, 3.5), dpi=100, facecolor=C_PANEL)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor("#FAFAFA")

        self.ax.set_title("Live Temperature Profile",
                          color=C_TEXT_MID, fontname=FONT, fontsize=9)
        self.ax.set_xlabel("Time (s)",
                           color=C_TEXT_DIM, fontname=FONT, fontsize=8)
        self.ax.set_ylabel("Temperature (°C)",
                           color=C_TEXT_DIM, fontname=FONT, fontsize=8)
        self.ax.tick_params(colors=C_TEXT_DIM, labelsize=7)
        for spine in self.ax.spines.values():
            spine.set_edgecolor(C_BORDER)
        self.ax.grid(True, color=C_BORDER, linestyle="-", alpha=0.8)

        self.line_pv,  = self.ax.plot([], [], color=C_ACCENT2,  linewidth=2,
                                      label="Actual (PV)")
        self.line_sp,  = self.ax.plot([], [], color=C_ACCENT,   linewidth=1.5,
                                      linestyle="--", alpha=0.7, label="Setpoint (SP)")
        self.line_wsp, = self.ax.plot([], [], color=C_AMBER,    linewidth=1.5,
                                      linestyle=":",  label="Working SP")
        self.line_ghost, = self.ax.plot([], [], color=C_TEXT_DIM, linewidth=1,
                                        linestyle="--", alpha=0.4,
                                        label="Ideal Ramp",
                                        visible=False)  # drawn at experiment start

        self.ax.legend(fontsize=7, facecolor=C_PANEL,
                       edgecolor=C_BORDER, labelcolor=C_TEXT_MID,
                       loc="upper left")
        self.fig.tight_layout(pad=1.5)

        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def _build_lcr_panel(self, parent):
        # Header
        hdr = tk.Frame(parent, bg=C_PANEL_ALT,
                       highlightthickness=0)
        hdr.pack(fill="x")
        tk.Label(hdr, text="LCR  LIVE  DATA",
                 font=(FONT, 9, "bold"),
                 bg=C_PANEL_ALT, fg=C_ACCENT).pack(side="left", padx=12, pady=8)

        self.lbl_lcr_freq = tk.Label(hdr,
                                     text="— Hz", font=("Consolas", 9, "bold"),
                                     bg=C_PANEL_ALT, fg=C_TEXT_MID)
        self.lbl_lcr_freq.pack(side="right", padx=12)

        tk.Frame(parent, bg=C_BORDER, height=1).pack(fill="x")

        # Parameter grid
        self.lcr_vars = []
        grid = tk.Frame(parent, bg=C_PANEL)
        grid.pack(fill="both", expand=True, padx=10, pady=6)

        for i, (label, color, unit) in enumerate(zip(LCR_LABELS, DISPLAY_COLORS, LCR_UNITS)):
            row = tk.Frame(grid, bg=C_PANEL)
            row.pack(fill="x", pady=2)

            # Colored left tag
            tk.Frame(row, bg=color, width=3).pack(
                side="left", fill="y", padx=(0, 6))

            tk.Label(row, text=f"{label:<6}",
                     font=(FONT, 8, "bold"),
                     bg=C_PANEL, fg=C_TEXT_MID,
                     width=6, anchor="w").pack(side="left")

            val_lbl = tk.Label(row, text="0.000e+00",
                               font=("Consolas", 9, "bold"),
                               bg=C_PANEL, fg=color)
            val_lbl.pack(side="left")

            tk.Label(row, text=f" {unit}",
                     font=(FONT, 7),
                     bg=C_PANEL, fg=C_TEXT_DIM).pack(side="left")

            self.lcr_vars.append(val_lbl)

    def _build_log_console(self):
        log_outer = tk.Frame(self.parent, bg=C_PANEL,
                             highlightthickness=1,
                             highlightbackground=C_BORDER)
        log_outer.pack(fill="x", pady=(8, 0))

        hdr = tk.Frame(log_outer, bg=C_PANEL_ALT)
        hdr.pack(fill="x")
        tk.Label(hdr, text="System Log",
                 font=(FONT, 8, "bold"),
                 bg=C_PANEL_ALT, fg=C_TEXT_DIM).pack(anchor="w", padx=10, pady=4)

        tk.Frame(log_outer, bg=C_BORDER, height=1).pack(fill="x")

        self.log_text = tk.Text(log_outer,
                                height=6, state="disabled",
                                font=("Consolas", 8),
                                bg="#FAFAFA", fg=C_TEXT_MID,
                                insertbackground=C_ACCENT,
                                relief="flat", bd=0,
                                padx=10, pady=6,
                                wrap="word")
        self.log_text.pack(fill="x")

    # -------------------------------------------------------------------------
    # LCR panel visibility
    # -------------------------------------------------------------------------

    def show_lcr_panel(self):
        self.lcr_panel.pack(side="right", fill="y", padx=(8, 0))

    def hide_lcr_panel(self):
        self.lcr_panel.pack_forget()

    def show_wsp_line(self):
        self.line_wsp.set_visible(True)
        self.ax.legend(fontsize=7, facecolor=C_PANEL,
                       edgecolor=C_BORDER, labelcolor=C_TEXT_MID, loc="upper left")
        self.canvas.draw_idle()

    def hide_wsp_line(self):
        self.line_wsp.set_visible(False)
        self.ax.legend(fontsize=7, facecolor=C_PANEL,
                       edgecolor=C_BORDER, labelcolor=C_TEXT_MID, loc="upper left")
        self.canvas.draw_idle()

    # -------------------------------------------------------------------------
    # Update methods
    # -------------------------------------------------------------------------

    def draw_ghost_ramp(self, start_pv: float, end_temp: float,
                        rate_per_min: float, t_offset: float = 0.0):
        """
        Draw the ideal ramp line.
        t_offset: elapsed seconds at the moment the ramp was anchored (from first plot callback).
        """
        if rate_per_min <= 0 or end_temp <= start_pv:
            return
        duration_sec = ((end_temp - start_pv) / rate_per_min) * 60
        t_end = t_offset + duration_sec
        self.line_ghost.set_data([t_offset, t_end], [start_pv, end_temp])
        self.line_ghost.set_visible(True)
        self.ax.legend(fontsize=7, facecolor=C_PANEL,
                       edgecolor=C_BORDER, labelcolor=C_TEXT_MID, loc="upper left")
        self.ax.relim()
        self.ax.autoscale_view(True, True, True)
        self.canvas.draw_idle()

    def clear_plot(self):
        """Reset all plot lines (call before each experiment start)."""
        for line in (self.line_pv, self.line_sp, self.line_wsp, self.line_ghost):
            line.set_data([], [])
        self.line_ghost.set_visible(False)
        self.ax.relim()
        self.canvas.draw_idle()

    def update_readouts(self, pv: float, sp: float, wsp: float,
                        rem_sec: int, status_text: str):
        self.lbl_pv.config(text=f"{pv:.1f} °C")
        self.lbl_sp.config(text=f"{sp:.1f} °C")
        self.lbl_wsp.config(text=f"{wsp:.1f} °C")
        hrs, rem = divmod(int(rem_sec), 3600)
        mins, secs = divmod(rem, 60)
        self.lbl_eta.config(text=f"{hrs:02d}h {mins:02d}m {secs:02d}s")
        self.lbl_status.config(text=f"● {status_text}", fg=C_AMBER)

    def update_plot(self, time_data, pv_data, sp_data, wsp_data):
        self.line_pv.set_data(time_data,  pv_data)
        self.line_sp.set_data(time_data,  sp_data)
        self.line_wsp.set_data(time_data, wsp_data)
        self.ax.relim()
        self.ax.autoscale_view(True, True, True)
        self.canvas.draw_idle()

    def update_lcr(self, freq: float, lcr_data: list):
        self.lbl_lcr_freq.config(text=f"{freq:.2f} Hz")
        for i, val in enumerate(lcr_data):
            if i < len(self.lcr_vars):
                self.lcr_vars[i].config(text=f"{val:.3e}")

    def set_status(self, text: str, color: str):
        self.lbl_status.config(text=f"● {text}", fg=color)

    def log(self, ts: str, msg: str):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"[{ts}]  {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
