# =============================================================================
# constants.py — Shared constants for MatTherm Profiler
# =============================================================================

# --- LCR Parameter Labels & Display ---
LCR_LABELS = [
    "Z", "Y", "Phase_Z",
    "Cs", "Cp", "D",
    "Ls", "Lp", "Rs", "Rp"
]
LCR_UNITS = ["Ω", "S", "°", "F", "F", "", "H", "H", "Ω", "Ω"]

# LCR display colors — adjusted for light theme (deeper, readable on white)
DISPLAY_COLORS = [
    "#0077B6", "#028A0F", "#E07B00", "#C2185B", "#C2185B",
    "#7B5EA7", "#6A0572", "#6A0572", "#B22222", "#B22222"
]

# --- Experiment Modes ---
MODE_TEMP_ONLY = "temp_only"
MODE_FULL_SWEEP = "full_sweep"

# --- Light Scientific Color Palette ---
FONT = "Segoe UI"       # Windows-native clean sans; fallback below
FONT_FALLBACK = "Helvetica Neue"

C_BG = "#F5F3EF"        # warm off-white — main window background
C_PANEL = "#FFFFFF"        # pure white — card/panel background
C_PANEL_ALT = "#EEF0F4"        # slightly cool — section header bg
C_BORDER = "#D1D5DB"        # soft grey border
C_BORDER_DARK = "#9CA3AF"        # darker border for emphasis

C_ACCENT = "#1D6FA4"        # strong scientific blue — primary action
C_ACCENT_LIGHT = "#EBF4FB"        # light blue tint — hover / active bg
C_ACCENT2 = "#C0392B"        # instrument red — PV readout
C_GREEN = "#1A7A3C"        # deep green — good status
C_GREEN_LIGHT = "#EAF5EE"        # light green tint
C_AMBER = "#B45309"        # amber — warnings / working SP
C_AMBER_LIGHT = "#FEF3C7"

C_TEXT = "#111827"        # near-black — primary text
C_TEXT_MID = "#374151"        # mid grey — secondary text
C_TEXT_DIM = "#6B7280"        # dim grey — labels, hints
C_TEXT_DISABLED = "#9CA3AF"

# Mode button active backgrounds
C_MODE_A_BG = "#EBF4FB"        # Temp Only active
C_MODE_A_FG = "#1D6FA4"
C_MODE_B_BG = "#F0EBF8"        # Full Sweep active
C_MODE_B_FG = "#6B21A8"

C_STOP_BG = "#FEF2F2"
C_STOP_FG = "#C0392B"
