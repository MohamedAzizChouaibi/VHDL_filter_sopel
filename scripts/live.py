#!/usr/bin/env python3
"""
Test en direct du filtre Sobel HDL avec la caméra (ou une vidéo / image).

Chaque image de la caméra est recadrée, redimensionnée à W x H, convertie en
niveaux de gris puis envoyée pixel par pixel au RTL simulé par Verilator
(tb/tb_live.cpp, exécutable obj_live/Vsobel_live). La sortie matérielle est
comparée en temps réel à cv2.Sobel (|Gx|+|Gy|) sur les pixels intérieurs.

Fenêtre :
    Caméra | Entrée HDL (WxH) | Sobel HDL
    Contours HDL | Sobel OpenCV | |HDL - OpenCV| (x50)

Touches :
    q / Échap  quitter            espace  pause
    + / -      seuil +-10         s       capture -> images/live_*.png
    (le seuil se règle aussi avec le curseur)

Exemples :
    make live
    python3 scripts/live.py --sim obj_live/Vsobel_live --width 160 --height 120
    python3 scripts/live.py --source video.mp4
    python3 scripts/live.py --no-display --frames 100   # test sans écran
"""
import argparse
import struct
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from sobel import sobel_opencv

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "images"
TILE = 320          # largeur d'une vignette à l'écran
WIN = "Sobel HDL - test live (Verilator)"


class HdlSim:
    """Processus Verilator persistant : une image en entrée, une image en sortie."""

    def __init__(self, exe: str, w: int, h: int, gap: int, seed: int):
        self.w, self.h = w, h
        self.p = subprocess.Popen([exe, str(gap), str(seed)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def _read(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self.p.stdout.read(n - len(buf))
            if not chunk:
                sys.exit("[live] le simulateur s'est arrêté (dimensions différentes ?)")
            buf += chunk
        return bytes(buf)

    def process(self, gray: np.ndarray, threshold: int):
        self.p.stdin.write(bytes([threshold]) + np.ascontiguousarray(gray, np.uint8).tobytes())
        self.p.stdin.flush()
        cycles, n_out, done = struct.unpack("<III", self._read(12))
        n = self.w * self.h
        data = np.frombuffer(self._read(2 * n), np.uint8)
        mag = data[:n].reshape(self.h, self.w)
        edge = data[n:].reshape(self.h, self.w)
        return mag, edge, cycles, n_out, bool(done)

    def close(self):
        if self.p.poll() is None:
            self.p.stdin.close()
            self.p.wait(timeout=5)


def open_source(src: str):
    """Index de caméra (« 0 »), fichier vidéo ou image fixe."""
    if src.isdigit():
        cap = cv2.VideoCapture(int(src))
        if not cap.isOpened():
            sys.exit(f"[live] impossible d'ouvrir la caméra {src}")
        return lambda: cap.read(), cap.release
    img = cv2.imread(src)
    if img is not None:                       # image fixe répétée
        return lambda: (True, img.copy()), lambda: None
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        sys.exit(f"[live] impossible d'ouvrir {src}")

    def read_loop():                          # vidéo lue en boucle
        ok, f = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, f = cap.read()
        return ok, f
    return read_loop, cap.release


def crop_to_aspect(frame: np.ndarray, w: int, h: int) -> np.ndarray:
    """Recadrage central au rapport w:h (pas de déformation)."""
    fh, fw = frame.shape[:2]
    target = w / h
    if fw / fh > target:
        nw = int(round(fh * target))
        x0 = (fw - nw) // 2
        return frame[:, x0:x0 + nw]
    nh = int(round(fw / target))
    y0 = (fh - nh) // 2
    return frame[y0:y0 + nh, :]


def tile(img: np.ndarray, title: str, w: int, h: int) -> np.ndarray:
    th = int(round(TILE * h / w))
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    interp = cv2.INTER_NEAREST if img.shape[1] < TILE else cv2.INTER_AREA
    t = cv2.resize(img, (TILE, th), interpolation=interp)
    cv2.rectangle(t, (0, 0), (TILE, 20), (0, 0, 0), -1)
    cv2.putText(t, title, (6, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    return t


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim", default=str(ROOT / "obj_live" / "Vsobel_live"), help="exécutable Verilator live")
    ap.add_argument("--source", default="0", help="index caméra, fichier vidéo ou image (défaut 0)")
    ap.add_argument("--width", type=int, default=160, help="doit égaler -GWIDTH du build")
    ap.add_argument("--height", type=int, default=120, help="doit égaler -GHEIGHT du build")
    ap.add_argument("--threshold", type=int, default=100)
    ap.add_argument("--gap", type=int, default=0, help="%% de cycles sans pixel (in_valid=0)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--frames", type=int, default=0, help="arrêt après N images (0 = infini)")
    ap.add_argument("--no-display", action="store_true", help="sans fenêtre (test automatique)")
    ap.add_argument("--snapshot", help="enregistre la dernière vue affichée dans ce fichier à la sortie")
    args = ap.parse_args()

    W, H = args.width, args.height
    if not Path(args.sim).exists():
        sys.exit(f"[live] {args.sim} introuvable : lancez d'abord « make live-build »")

    read_frame, release = open_source(args.source)
    sim = HdlSim(args.sim, W, H, args.gap, args.seed)
    thr = max(0, min(255, args.threshold))
    expected = (W - 2) * (H - 2)

    if not args.no_display:
        cv2.namedWindow(WIN, cv2.WINDOW_AUTOSIZE)
        cv2.createTrackbar("seuil", WIN, thr, 255, lambda v: None)

    frames = bad_frames = 0
    t_sim_total = 0.0
    fps = 0.0
    t_prev = time.perf_counter()
    paused = False
    last = None
    view = None

    try:
        while True:
            if not paused or last is None:
                ok, frame = read_frame()
                if not ok or frame is None:
                    print("[live] fin du flux")
                    break
                frame = crop_to_aspect(frame, W, H)
                gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (W, H),
                                  interpolation=cv2.INTER_AREA)
                if not args.no_display:
                    thr = cv2.getTrackbarPos("seuil", WIN)

                t0 = time.perf_counter()
                mag, edge, cycles, n_out, done = sim.process(gray, thr)
                t_sim = time.perf_counter() - t0
                t_sim_total += t_sim

                # Référence OpenCV et vérification bit à bit (intérieur)
                cv_l1, _ = sobel_opencv(gray)
                cv_edge = np.where(cv_l1 >= thr, 255, 0).astype(np.uint8)   # = out_edge du RTL
                diff = cv2.absdiff(mag[1:-1, 1:-1], cv_l1[1:-1, 1:-1])
                mism = int(np.count_nonzero(diff))
                mism_e = int(np.count_nonzero(edge[1:-1, 1:-1] != cv_edge[1:-1, 1:-1]))
                ok_frame = mism == 0 and mism_e == 0 and n_out == expected and done
                frames += 1
                if not ok_frame:
                    bad_frames += 1
                    print(f"[live] image {frames} : écarts mag={mism} contours={mism_e} "
                          f"pixels={n_out}/{expected} frame_done={done}")

                now = time.perf_counter()
                fps = 0.9 * fps + 0.1 / max(now - t_prev, 1e-6) if frames > 1 else 1 / max(now - t_prev, 1e-6)
                t_prev = now
                last = (frame, gray, mag, edge, cv_l1, diff, cycles, t_sim, mism, ok_frame)

            frame, gray, mag, edge, cv_l1, diff, cycles, t_sim, mism, ok_frame = last

            if not args.no_display:
                diff_full = np.zeros((H, W), np.uint8)
                diff_full[1:-1, 1:-1] = np.clip(diff.astype(np.int32) * 50, 0, 255)
                row1 = np.hstack([tile(frame, "Camera", W, H),
                                  tile(gray, f"Entree HDL {W}x{H}", W, H),
                                  tile(mag, "Sobel HDL |Gx|+|Gy|", W, H)])
                row2 = np.hstack([tile(edge, f"Contours HDL (seuil {thr})", W, H),
                                  tile(cv_l1, "Sobel OpenCV |Gx|+|Gy|", W, H),
                                  tile(diff_full, "|HDL - OpenCV| x50", W, H)])
                status = np.zeros((34, row1.shape[1], 3), np.uint8)
                verdict = "PASS (bit-exact)" if ok_frame else f"FAIL ({mism} px)"
                color = (80, 220, 80) if ok_frame else (60, 60, 255)
                sim_mhz = cycles / max(t_sim, 1e-9) / 1e6
                txt = (f"{fps:5.1f} img/s | {cycles} cycles/img ({W * H / cycles:.2f} px/cycle) | "
                       f"sim {sim_mhz:.1f} MHz | images {frames}, echecs {bad_frames} | ")
                cv2.putText(status, txt, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (230, 230, 230), 1, cv2.LINE_AA)
                (tw, _), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.putText(status, verdict, (8 + tw, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
                if paused:
                    cv2.putText(status, "PAUSE", (row1.shape[1] - 70, 22), cv2.FONT_HERSHEY_SIMPLEX,
                                0.5, (0, 200, 255), 1, cv2.LINE_AA)
                view = np.vstack([row1, row2, status])
                cv2.imshow(WIN, view)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27) or cv2.getWindowProperty(WIN, cv2.WND_PROP_VISIBLE) < 1:
                    break
                if key == ord(" "):
                    paused = not paused
                elif key in (ord("+"), ord("=")):
                    cv2.setTrackbarPos("seuil", WIN, min(255, thr + 10))
                elif key == ord("-"):
                    cv2.setTrackbarPos("seuil", WIN, max(0, thr - 10))
                elif key == ord("s"):
                    stamp = time.strftime("%Y%m%d_%H%M%S")
                    IMG.mkdir(exist_ok=True)
                    cv2.imwrite(str(IMG / f"live_{stamp}.png"), view)
                    print(f"[live] capture -> images/live_{stamp}.png")

            if args.frames and frames >= args.frames:
                break
    except KeyboardInterrupt:
        pass
    finally:
        if args.snapshot and view is not None:
            cv2.imwrite(args.snapshot, view)
            print(f"[live] vue enregistrée -> {args.snapshot}")
        sim.close()
        release()
        if not args.no_display:
            cv2.destroyAllWindows()

    if frames:
        print(f"[live] {frames} images {W}x{H}, {bad_frames} en échec, "
              f"simulation moyenne {1000 * t_sim_total / frames:.1f} ms/image")
        print(f"[live] RESULTAT : {'PASS' if bad_frames == 0 else 'FAIL'}")
    return 0 if frames and bad_frames == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
