#!/usr/bin/env python3
"""Figures pour le rapport PDF et la présentation : chronogramme (depuis le VCD),
architecture, masques, et images agrandies (64x64 -> 512x512, plus proche voisin)."""
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "images"
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)
TEAL, GREEN, ORANGE, RED, NAVY = "#138A92", "#7FAE3E", "#E8892B", "#C62F3D", "#1F3A5F"


# ------------------------------------------------------------------ VCD ---- #
def parse_vcd(path, wanted):
    ids, scope, vals, t = {}, [], {}, 0
    with open(path) as f:
        for line in f:
            tok = line.split()
            if not tok:
                continue
            if tok[0] == "$scope":
                scope.append(tok[2])
            elif tok[0] == "$upscope":
                scope.pop()
            elif tok[0] == "$var":
                name = ".".join(scope[1:] + [tok[4]])
                if name in wanted:
                    ids.setdefault(tok[3], []).append(name)
                    vals[name] = []
            elif tok[0].startswith("#"):
                t = int(tok[0][1:])
            elif tok[0].startswith("b") and len(tok) == 2 and tok[1] in ids:
                v = int(tok[0][1:].replace("x", "0").replace("z", "0"), 2)
                for n in ids[tok[1]]:
                    vals[n].append((t, v))
            elif tok[0][0] in "01xz" and tok[0][1:] in ids:
                for n in ids[tok[0][1:]]:
                    vals[n].append((t, int(tok[0][0] == "1")))
    return vals


def value_at(changes, t):
    v = 0
    for tt, vv in changes:
        if tt > t:
            break
        v = vv
    return v


def waveform():
    sig = [("sobel_top.clk", "clk", 1, False), ("sobel_top.in_valid", "in_valid", 1, False),
           ("sobel_top.in_pixel", "in_pixel", 8, False), ("sobel_top.col", "col", 6, False),
           ("sobel_top.win_valid", "win_valid", 1, False),
           ("sobel_top.u_kernel.gx_s1", "Gx", 11, True), ("sobel_top.u_kernel.gy_s1", "Gy", 11, True),
           ("sobel_top.out_valid", "out_valid", 1, False), ("sobel_top.out_x", "out_x", 6, False),
           ("sobel_top.out_pixel", "out_pixel", 8, False)]
    vals = parse_vcd(ROOT / "results" / "sobel.vcd", {s[0] for s in sig})
    first_out = next(t for t, v in vals["sobel_top.out_valid"] if v == 1)
    t0, n = first_out - 2 * 9, 14                      # 14 cycles autour de la 1re sortie
    fig, ax = plt.subplots(figsize=(12, 5.2))
    for i, (key, label, w, signed) in enumerate(sig):
        y = len(sig) - 1 - i
        ax.text(-0.3, y + 0.35, label, ha="right", va="center", fontsize=10, family="monospace")
        if key.endswith("clk"):
            xs, ys = [], []
            for c in range(n):
                xs += [c, c, c + 0.5, c + 0.5]
                ys += [y, y + 0.7, y + 0.7, y]
            ax.plot(xs + [n], ys + [y], color=NAVY, lw=1.2)
            continue
        for c in range(n):
            v = value_at(vals[key], t0 + 2 * c + 1)
            if w == 1:
                ax.plot([c, c + 1], [y + 0.7 * v] * 2, color=TEAL if "out" in key else NAVY, lw=1.6)
                nv = value_at(vals[key], t0 + 2 * (c + 1) + 1)
                if c < n - 1 and nv != v:
                    ax.plot([c + 1, c + 1], [y, y + 0.7], color=NAVY, lw=1.6)
            else:
                if signed and v >= 1 << (w - 1):
                    v -= 1 << w
                ax.add_patch(FancyBboxPatch((c + 0.06, y), 0.88, 0.7, boxstyle="round,pad=0,rounding_size=0.12",
                                            fc="#E7F3F4" if "out" not in key else "#FDEBD8", ec=NAVY, lw=0.8))
                ax.text(c + 0.5, y + 0.35, str(v), ha="center", va="center", fontsize=8)
    c_out = (first_out - t0) // 2
    ax.axvline(c_out, color=RED, ls="--", lw=1)
    ax.text(c_out + 0.05, len(sig) - 0.15, "1re sortie (x=1, y=1)", color=RED, fontsize=9)
    ax.set_xlim(-2.4, n)
    ax.set_ylim(-0.4, len(sig))
    ax.axis("off")
    ax.set_title("Chronogramme Verilator (extrait de results/sobel.vcd)", fontsize=12)
    fig.tight_layout()
    fig.savefig(FIG / "waveform.png", dpi=160)
    plt.close(fig)


# -------------------------------------------------------- Architecture ---- #
def box(ax, x, y, w, h, text, color, fs=10):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=color, ec="none"))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color="white", fontsize=fs,
            fontweight="bold", linespacing=1.4)


def arrow(ax, x0, y0, x1, y1):
    ax.annotate("", (x1, y1), (x0, y0), arrowprops=dict(arrowstyle="-|>", color=NAVY, lw=1.6))


def architecture():
    fig, ax = plt.subplots(figsize=(12, 3.6))
    ax.text(-1.0, 1.95, "in_pixel[7:0]\nin_valid", fontsize=9, family="monospace", va="center")
    box(ax, 1.3, 1.3, 2.1, 1.3, "line_buffer\n2 × 64 × 8 bits", TEAL)
    box(ax, 4.2, 1.3, 2.1, 1.3, "Fenêtre 3×3\n9 registres", GREEN)
    box(ax, 7.1, 1.3, 2.1, 1.3, "Étage 1\nGx, Gy (11 b signés)", ORANGE)
    box(ax, 10.0, 1.3, 2.1, 1.3, "Étage 2\n|Gx|+|Gy|, saturation", RED)
    box(ax, 1.3, 0.0, 2.1, 0.75, "Compteurs col / row", NAVY, 9)
    arrow(ax, 0.95, 1.95, 1.3, 1.95)
    for x in (3.4, 6.3, 9.2):
        arrow(ax, x, 1.95, x + 0.8, 1.95)
    arrow(ax, 3.4, 0.37, 4.6, 1.3)
    arrow(ax, 12.1, 1.95, 12.6, 1.95)
    ax.text(12.65, 1.95, "out_pixel\nout_edge\nout_x, out_y", fontsize=9, family="monospace", va="center")
    ax.text(3.45, 2.25, "r-2, r-1, r", fontsize=8, color=NAVY)
    ax.text(7.0, 3.0, "sobel_kernel.v  (latence 2 cycles)", fontsize=9, color=NAVY, ha="left")
    ax.plot([7.05, 12.15], [2.85, 2.85], color=NAVY, lw=0.8)
    ax.set_xlim(-1.1, 14.2)
    ax.set_ylim(-0.2, 3.2)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(FIG / "architecture.png", dpi=160)
    plt.close(fig)


def masks():
    import numpy as np
    kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]])
    fig, axs = plt.subplots(1, 2, figsize=(6.4, 3))
    for a, k, name in zip(axs, (kx, kx.T), ("Gx (contours verticaux)", "Gy (contours horizontaux)")):
        a.imshow(k, cmap="coolwarm", vmin=-2.6, vmax=2.6)
        for i in range(3):
            for j in range(3):
                a.text(j, i, f"{k[i, j]:+d}" if k[i, j] else "0", ha="center", va="center", fontsize=15,
                       fontweight="bold")
        a.set_title(name, fontsize=11)
        a.set_xticks([])
        a.set_yticks([])
    fig.tight_layout()
    fig.savefig(FIG / "masks.png", dpi=160)
    plt.close(fig)


def upscale():
    for name in ("input", "output_hdl", "output_opencv", "output_hdl_edges", "output_opencv_l2"):
        im = cv2.imread(str(IMG / f"{name}.png"), cv2.IMREAD_GRAYSCALE)
        cv2.imwrite(str(FIG / f"{name}_512.png"), cv2.resize(im, (512, 512), interpolation=cv2.INTER_NEAREST))


if __name__ == "__main__":
    waveform()
    architecture()
    masks()
    upscale()
    print("figures ->", FIG)
