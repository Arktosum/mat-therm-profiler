# =============================================================================
# core/plotting.py — Bode plot generation & saving
# =============================================================================
import os
import matplotlib.pyplot as plt


def save_bode_plots(
    temp: float,
    freqs: list,
    z_data: list,
    phase_z: list,
    y_data: list,
    save_path: str,
    base_name: str
):
    """
    Generate and save impedance (Z) and admittance (Y) Bode plots as PNGs.

    Args:
        temp       : Temperature at which sweep was taken (°C)
        freqs      : List of frequency points (Hz)
        z_data     : |Z| values (Ω)
        phase_z    : Phase of Z (degrees)
        y_data     : |Y| values (S)
        save_path  : Directory to save PNGs
        base_name  : Base filename prefix
    """
    try:
        phase_y = [-p for p in phase_z]

        # --- Impedance Plot ---
        fig_z, ax1_z = plt.subplots(figsize=(8, 5))
        ax1_z.set_title(f"Impedance Response @ {temp}°C")
        ax1_z.set_xlabel("Frequency (Hz)")
        ax1_z.set_xscale("log")

        color_z = 'tab:blue'
        color_p = 'tab:orange'

        ax1_z.set_ylabel("|Z| (Ω)", color=color_z)
        ax1_z.plot(freqs, z_data, color=color_z, marker='.')
        ax1_z.set_yscale("log")
        ax1_z.grid(True, which="both", ls="-", alpha=0.2)

        ax2_z = ax1_z.twinx()
        ax2_z.set_ylabel("Phase (deg)", color=color_p)
        ax2_z.plot(freqs, phase_z, color=color_p, linestyle='--')

        fig_z.tight_layout()
        fig_z.savefig(
            os.path.join(save_path, f"{base_name}_{temp}C_Z_Plot.png"), dpi=150)
        plt.close(fig_z)

        # --- Admittance Plot ---
        fig_y, ax1_y = plt.subplots(figsize=(8, 5))
        ax1_y.set_title(f"Admittance Response @ {temp}°C")
        ax1_y.set_xlabel("Frequency (Hz)")
        ax1_y.set_xscale("log")

        color_y = 'tab:green'

        ax1_y.set_ylabel("|Y| (S)", color=color_y)
        ax1_y.plot(freqs, y_data, color=color_y, marker='.')
        ax1_y.set_yscale("log")
        ax1_y.grid(True, which="both", ls="-", alpha=0.2)

        ax2_y = ax1_y.twinx()
        ax2_y.set_ylabel("Phase Y (deg)", color=color_p)
        ax2_y.plot(freqs, phase_y, color=color_p, linestyle='--')

        fig_y.tight_layout()
        fig_y.savefig(
            os.path.join(save_path, f"{base_name}_{temp}C_Y_Plot.png"), dpi=150)
        plt.close(fig_y)

    except Exception as e:
        print(f"[plotting] Error saving Bode plots: {e}")