#!/usr/bin/env python3
"""
Mini-projet 3 — Pipeline Sobel HDL : script Python (NumPy + OpenCV)

Sous-commandes :
  prepare   génère (ou charge) l'image d'entrée 64x64 -> images/input.{pgm,png}
  compare   compare la sortie HDL à OpenCV et au modèle NumPy -> métriques + figures
  all       prepare + simulation Verilator + compare

Exemples :
  python3 scripts/sobel.py all --sim obj_dir/Vsobel_top
  python3 scripts/sobel.py all --sim obj_dir/Vsobel_top --image photo.jpg
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "images"
RES = ROOT / "results"
N = 64


# --------------------------------------------------------------------------- #
# Image d'entrée
# --------------------------------------------------------------------------- #
def synthetic_image(seed: int = 0) -> np.ndarray:
    """Scène de test 64x64 : formes géométriques, dégradé, texte, bruit léger."""
    rng = np.random.default_rng(seed)
    img = np.tile(np.linspace(30, 90, N, dtype=np.float32), (N, 1))  # dégradé horizontal
    img = img.astype(np.uint8)
    cv2.rectangle(img, (6, 6), (26, 24), 200, -1)
    cv2.circle(img, (45, 16), 10, 240, -1)
    cv2.circle(img, (45, 16), 4, 60, -1)
    tri = np.array([[8, 56], [28, 34], [34, 58]], np.int32)
    cv2.fillPoly(img, [tri], 170)
    cv2.line(img, (38, 36), (60, 58), 255, 2)
    cv2.putText(img, "HDL", (36, 50), cv2.FONT_HERSHEY_PLAIN, 0.8, 10, 1)
    noise = rng.normal(0, 3, img.shape)
    return np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def load_image(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        sys.exit(f"Impossible de lire l'image {path}")
    return cv2.resize(img, (N, N), interpolation=cv2.INTER_AREA)


def write_pgm(path: Path, img: np.ndarray) -> None:
    h, w = img.shape
    with open(path, "wb") as f:
        f.write(f"P5\n{w} {h}\n255\n".encode())
        f.write(np.ascontiguousarray(img, dtype=np.uint8).tobytes())


def read_pgm(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        sys.exit(f"Impossible de lire {path}")
    return img


def cmd_prepare(args) -> np.ndarray:
    IMG.mkdir(exist_ok=True)
    img = load_image(args.image) if args.image else synthetic_image()
    write_pgm(IMG / "input.pgm", img)
    cv2.imwrite(str(IMG / "input.png"), img)
    print(f"[prepare] image d'entrée {img.shape} -> {IMG / 'input.pgm'}")
    return img


# --------------------------------------------------------------------------- #
# Références logicielles
# --------------------------------------------------------------------------- #
KX = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], np.int32)
KY = KX.T.copy()


def sobel_numpy(img: np.ndarray) -> np.ndarray:
    """Convolution 3x3 explicite (NumPy), même arithmétique que le RTL."""
    p = img.astype(np.int32)
    gx = np.zeros_like(p)
    gy = np.zeros_like(p)
    for dy in range(3):
        for dx in range(3):
            win = p[dy:N - 2 + dy, dx:N - 2 + dx]
            gx[1:-1, 1:-1] += KX[dy, dx] * win
            gy[1:-1, 1:-1] += KY[dy, dx] * win
    out = np.clip(np.abs(gx) + np.abs(gy), 0, 255).astype(np.uint8)
    out[0, :] = out[-1, :] = out[:, 0] = out[:, -1] = 0
    return out


def sobel_opencv(img: np.ndarray):
    """Référence OpenCV : cv2.Sobel 3x3 puis |Gx|+|Gy| (L1) et sqrt(Gx²+Gy²) (L2)."""
    gx = cv2.Sobel(img, cv2.CV_16S, 1, 0, ksize=3, borderType=cv2.BORDER_REPLICATE)
    gy = cv2.Sobel(img, cv2.CV_16S, 0, 1, ksize=3, borderType=cv2.BORDER_REPLICATE)
    l1 = cv2.add(cv2.convertScaleAbs(gx), cv2.convertScaleAbs(gy))
    l2 = cv2.convertScaleAbs(cv2.magnitude(gx.astype(np.float32), gy.astype(np.float32)))
    return l1, l2


def interior(a: np.ndarray) -> np.ndarray:
    return a[1:-1, 1:-1]


def metrics(a: np.ndarray, b: np.ndarray) -> dict:
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    d = np.abs(a - b)
    mse = float(np.mean((a - b) ** 2))
    psnr = float("inf") if mse == 0 else 10 * np.log10(255 ** 2 / mse)
    return {
        "identical_pixels": int(np.sum(d == 0)),
        "total_pixels": int(d.size),
        "match_percent": round(100.0 * float(np.mean(d == 0)), 3),
        "max_abs_diff": int(d.max()),
        "mean_abs_diff": round(float(d.mean()), 4),
        "mse": round(mse, 4),
        "psnr_db": "inf" if psnr == float("inf") else round(float(psnr), 2),
    }


# --------------------------------------------------------------------------- #
# Comparaison + figures
# --------------------------------------------------------------------------- #
def cmd_compare(args) -> bool:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    RES.mkdir(exist_ok=True)
    img = read_pgm(IMG / "input.pgm")
    hdl = read_pgm(IMG / "output_hdl.pgm")
    hdl_edges = read_pgm(IMG / "output_hdl_edges.pgm")
    ref_np = sobel_numpy(img)
    cv_l1, cv_l2 = sobel_opencv(img)
    _, cv_edges = cv2.threshold(cv_l1, args.threshold - 1, 255, cv2.THRESH_BINARY)

    diff = cv2.absdiff(interior(hdl), interior(cv_l1))
    cv2.imwrite(str(IMG / "output_hdl.png"), hdl)
    cv2.imwrite(str(IMG / "output_hdl_edges.png"), hdl_edges)
    cv2.imwrite(str(IMG / "output_opencv.png"), cv_l1)
    cv2.imwrite(str(IMG / "output_opencv_l2.png"), cv_l2)
    cv2.imwrite(str(IMG / "diff_hdl_opencv.png"), cv2.copyMakeBorder(diff, 1, 1, 1, 1, cv2.BORDER_CONSTANT))

    m = {
        "hdl_vs_numpy_full": metrics(hdl, ref_np),
        "hdl_vs_opencv_L1_interior": metrics(interior(hdl), interior(cv_l1)),
        "hdl_vs_opencv_L1_full_image": metrics(hdl, cv_l1),
        "hdl_vs_opencv_L2_interior": metrics(interior(hdl), interior(cv_l2)),
        "edges_hdl_vs_opencv_interior": metrics(interior(hdl_edges), interior(cv_edges)),
        "threshold": args.threshold,
    }
    (RES / "metrics.json").write_text(json.dumps(m, indent=2))

    # Figure avant / après
    fig, ax = plt.subplots(2, 3, figsize=(12, 8.4))
    panels = [
        (img, "Entrée 64×64"),
        (hdl, "Sobel HDL (Verilator) |Gx|+|Gy|"),
        (cv_l1, "Sobel OpenCV |Gx|+|Gy|"),
        (hdl_edges, f"Contours HDL (seuil {args.threshold})"),
        (cv_l2, "OpenCV √(Gx²+Gy²) (L2)"),
        (cv2.absdiff(hdl, cv_l1), "|HDL − OpenCV| (bords inclus)"),
    ]
    for a, (im, title) in zip(ax.flat, panels):
        a.imshow(im, cmap="gray", vmin=0, vmax=255 if "|HDL" not in title else max(1, int(im.max())),
                 interpolation="nearest")
        a.set_title(title, fontsize=10)
        a.axis("off")
    r = m["hdl_vs_opencv_L1_interior"]
    fig.suptitle(f"Filtre Sobel HDL vs OpenCV — intérieur 62×62 : {r['match_percent']} % identiques, "
                 f"écart max {r['max_abs_diff']}", fontsize=12)
    fig.tight_layout(h_pad=2.5)
    fig.savefig(IMG / "comparison.png", dpi=110)
    plt.close(fig)

    for k, v in m.items():
        print(f"[compare] {k}: {v}")
    ok = m["hdl_vs_numpy_full"]["max_abs_diff"] == 0 and r["max_abs_diff"] == 0
    print(f"[compare] HDL == OpenCV (intérieur) : {'OUI' if ok else 'NON'}")
    return ok


def cmd_all(args) -> int:
    cmd_prepare(args)
    RES.mkdir(exist_ok=True)
    sim = [args.sim, str(IMG / "input.pgm"), str(IMG / "output_hdl.pgm"),
           str(IMG / "output_hdl_edges.pgm"), str(RES / "sobel.vcd"),
           str(args.threshold), str(args.gap), str(args.seed)]
    print("[sim] " + " ".join(sim))
    p = subprocess.run(sim, capture_output=True, text=True)
    sys.stdout.write(p.stdout)
    sys.stderr.write(p.stderr)
    (RES / "sim_log.txt").write_text(p.stdout + p.stderr)
    if p.returncode != 0:
        print("[sim] ÉCHEC du testbench")
        return 1
    return 0 if cmd_compare(args) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["prepare", "compare", "all"])
    ap.add_argument("--image", help="image source (sinon scène synthétique)")
    ap.add_argument("--sim", default=str(ROOT / "obj_dir" / "Vsobel_top"), help="exécutable Verilator")
    ap.add_argument("--threshold", type=int, default=100)
    ap.add_argument("--gap", type=int, default=20, help="%% de cycles sans pixel (in_valid=0)")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    if args.command == "prepare":
        cmd_prepare(args)
        return 0
    if args.command == "compare":
        return 0 if cmd_compare(args) else 1
    return cmd_all(args)


if __name__ == "__main__":
    sys.exit(main())
