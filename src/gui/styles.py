# =============================================================================
# gui/styles.py — Light scientific ttk theme + widget factory helpers
# =============================================================================
import tkinter as tk
from tkinter import ttk
from src.constants import (
    FONT,
    C_BG, C_PANEL, C_PANEL_ALT, C_BORDER, C_BORDER_DARK,
    C_ACCENT, C_ACCENT_LIGHT, C_TEXT, C_TEXT_MID, C_TEXT_DIM, C_TEXT_DISABLED,
    C_GREEN, C_AMBER, C_MODE_A_BG, C_MODE_A_FG, C_MODE_B_BG, C_MODE_B_FG,
    C_STOP_BG, C_STOP_FG
)

# Resolved font — Segoe UI ships with Windows, fine on all lab machines
F_BODY = (FONT, 9)
F_SMALL = (FONT, 8)
F_LABEL = (FONT, 9)
F_BOLD = (FONT, 9,  "bold")
F_TITLE = (FONT, 11, "bold")
F_MONO = ("Consolas", 9)
F_MONO_L = ("Consolas", 11, "bold")
F_MONO_XL = ("Consolas", 20, "bold")


def make_light_style():
    """Configure ttk styles for the light scientific theme."""
    style = ttk.Style()
    style.theme_use('clam')

    # Base
    style.configure(".",
                    background=C_BG,
                    foreground=C_TEXT,
                    font=F_BODY,
                    bordercolor=C_BORDER,
                    relief="flat",
                    focuscolor=C_ACCENT,
                    )
    style.configure("TFrame",    background=C_BG)
    style.configure("TLabel",    background=C_BG, foreground=C_TEXT)

    # Entry
    style.configure("TEntry",
                    fieldbackground=C_PANEL,
                    foreground=C_TEXT,
                    insertcolor=C_ACCENT,
                    bordercolor=C_BORDER,
                    lightcolor=C_BORDER,
                    darkcolor=C_BORDER,
                    padding=4,
                    )
    style.map("TEntry", bordercolor=[("focus", C_ACCENT)])

    # Combobox
    style.configure("TCombobox",
                    fieldbackground=C_PANEL,
                    foreground=C_TEXT,
                    selectbackground=C_ACCENT_LIGHT,
                    selectforeground=C_TEXT,
                    bordercolor=C_BORDER,
                    arrowcolor=C_TEXT_DIM,
                    padding=4,
                    )
    style.map("TCombobox",
              fieldbackground=[("readonly", C_PANEL)],
              bordercolor=[("focus", C_ACCENT)],
              )

    # Scrollbar
    style.configure("TScrollbar",
                    background=C_BORDER,
                    troughcolor=C_PANEL_ALT,
                    bordercolor=C_BORDER,
                    arrowcolor=C_TEXT_DIM,
                    relief="flat",
                    )
    style.map("TScrollbar", background=[("active", C_BORDER_DARK)])

    # Separator
    style.configure("TSeparator", background=C_BORDER)

    # ── Named button styles ────────────────────────────────────────────────

    # Mode: Temp Only (active)
    style.configure("ModeA.TButton",
                    background=C_MODE_A_BG,
                    foreground=C_MODE_A_FG,
                    font=(FONT, 9, "bold"),
                    relief="flat", padding=(10, 6),
                    bordercolor=C_ACCENT,
                    )
    style.map("ModeA.TButton",
              background=[("active", C_ACCENT_LIGHT)],
              )

    # Mode: Full Sweep (active)
    style.configure("ModeB.TButton",
                    background=C_MODE_B_BG,
                    foreground=C_MODE_B_FG,
                    font=(FONT, 9, "bold"),
                    relief="flat", padding=(10, 6),
                    bordercolor=C_MODE_B_FG,
                    )
    style.map("ModeB.TButton",
              background=[("active", "#E9D8FA")],
              )

    # Mode: inactive
    style.configure("ModeInactive.TButton",
                    background=C_PANEL_ALT,
                    foreground=C_TEXT_DIM,
                    font=(FONT, 9),
                    relief="flat", padding=(10, 6),
                    )
    style.map("ModeInactive.TButton",
              background=[("active", C_BORDER)],
              foreground=[("active", C_TEXT_MID)],
              )

    # Start experiment
    style.configure("Start.TButton",
                    background=C_ACCENT,
                    foreground="#FFFFFF",
                    font=(FONT, 10, "bold"),
                    relief="flat", padding=(10, 8),
                    )
    style.map("Start.TButton",
              background=[("active", "#155F8A"),
                          ("disabled", C_TEXT_DISABLED)],
              foreground=[("disabled", "#FFFFFF")],
              )

    # Small action buttons (refresh, browse, etc.)
    style.configure("Action.TButton",
                    background=C_PANEL_ALT,
                    foreground=C_TEXT_MID,
                    font=F_SMALL,
                    relief="flat", padding=(6, 4),
                    )
    style.map("Action.TButton",
              background=[("active", C_BORDER)],
              )

    # Accordion section header button
    style.configure("Section.TButton",
                    background=C_PANEL_ALT,
                    foreground=C_TEXT_MID,
                    font=(FONT, 8, "bold"),
                    relief="flat", padding=(8, 5),
                    anchor="w",
                    )
    style.map("Section.TButton",
              background=[("active", C_BORDER)],
              foreground=[("active", C_TEXT)],
              )


# =============================================================================
# Widget factory helpers  (shared across panels)
# =============================================================================

def make_entry_row(parent, label: str, default: str,
                   bg=None, on_key_release=None) -> tk.Entry:
    """Label + styled Entry. Returns Entry widget."""
    bg = bg or C_PANEL
    frm = tk.Frame(parent, bg=bg)
    frm.pack(fill="x", pady=2)
    tk.Label(frm, text=label, font=F_LABEL,
             bg=bg, fg=C_TEXT_MID,
             width=17, anchor="w").pack(side="left")
    ent = tk.Entry(frm, font=F_MONO, width=11,
                   bg=C_PANEL, fg=C_TEXT,
                   insertbackground=C_ACCENT,
                   relief="solid", bd=1,
                   highlightthickness=1,
                   highlightcolor=C_ACCENT,
                   highlightbackground=C_BORDER)
    ent.insert(0, default)
    ent.pack(side="right")
    if on_key_release:
        ent.bind("<KeyRelease>", on_key_release)
    return ent


def make_dropdown_row(parent, label: str, bg=None) -> ttk.Combobox:
    """Label + Combobox row. Returns Combobox widget."""
    bg = bg or C_PANEL
    frm = tk.Frame(parent, bg=bg)
    frm.pack(fill="x", pady=2)
    tk.Label(frm, text=label, font=F_LABEL,
             bg=bg, fg=C_TEXT_MID,
             width=17, anchor="w").pack(side="left")
    cmb = ttk.Combobox(frm, width=14)
    cmb.pack(side="right")
    return cmb


def make_action_button(parent, text: str, command,
                       side="left") -> ttk.Button:
    btn = ttk.Button(parent, text=text,
                     style="Action.TButton", command=command)
    btn.pack(side=side, fill="x", expand=True, padx=2)
    return btn


def make_divider(parent, bg=None):
    """Thin horizontal rule."""
    bg = bg or C_BG
    tk.Frame(parent, bg=C_BORDER, height=1).pack(fill="x", padx=0, pady=4)
