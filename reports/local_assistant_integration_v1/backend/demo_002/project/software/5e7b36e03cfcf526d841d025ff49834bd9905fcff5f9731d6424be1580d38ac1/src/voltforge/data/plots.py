"""Measured-data figures; preserve gaps and original sample order."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .inspection import contiguous_segments

COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7"]


def segmented(ax, t, y, label, color, gap_s=1.5):
    for j, index in enumerate(contiguous_segments(t, gap_s)):
        ax.plot(np.asarray(t)[index]/3600., np.asarray(y)[index], lw=.85,
                label=label if j == 0 else None, color=color)


def module_plots(frame, run_id, cells, destination):
    destination.mkdir(parents=True, exist_ok=True)
    for scope in ["full", "discharge"]:
        f = frame if scope == "full" else frame.loc[frame.step_index == 5]
        fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True, layout="constrained")
        fig.suptitle(f"{run_id} | {scope}\nMeasured records; positive current = discharge", fontsize=14)
        t = f.time_s.to_numpy()
        segmented(axes[0], t, f.module_voltage_V, "Raw module voltage", "#333333")
        segmented(axes[1], t, f.module_current_A, "Raw module current", "#333333")
        for i, (cell, color) in enumerate(zip(cells, COLORS), start=1):
            label = f"Position {i}: {cell}"
            segmented(axes[2], t, f[f"branch_{i}_A"], label, color)
            segmented(axes[3], t, f[f"surface_{i}_C"], label, color)
        segmented(axes[3], t, f.ambient_C, "Measured ambient", "#777777")
        for ax, unit in zip(axes, ["Module voltage [V]", "Module current [A]", "Author-calibrated branch [A]", "Raw surface / ambient [degC]"]):
            ax.set_ylabel(unit)
            ax.grid(alpha=.2)
            for seg in contiguous_segments(t, 1.5)[1:]:
                i = int(seg[0])
                if t[i]-t[i-1] > 1.5:
                    ax.axvspan(t[i-1]/3600., t[i]/3600., color="red", alpha=.2)
        axes[2].legend(loc="best", ncol=4, fontsize=8)
        axes[3].legend(loc="best", ncol=5, fontsize=8)
        axes[-1].set_xlabel("Elapsed test time [h]; line breaks/red bands mark gaps > 1.5 s")
        fig.savefig(destination / f"{run_id}_{scope}.png", dpi=150)
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(12, 3.8), layout="constrained")
    segmented(ax, frame.time_s, frame.kcl_residual_A, "Sum of branches minus module", "#A33E32")
    ax.axhline(0, color="black", lw=.7)
    ax.set(title=f"{run_id}: current conservation audit (no correction applied)",
           xlabel="Elapsed test time [h]", ylabel="Discharge-current residual [A]")
    ax.grid(alpha=.2)
    fig.savefig(destination / f"{run_id}_kcl.png", dpi=150)
    plt.close(fig)
