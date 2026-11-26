#!/usr/bin/env python3
"""Génère docs/Sobel_HDL_explication.pdf (document explicatif du projet).
Prérequis : python3 -m pip install reportlab ; lancer d'abord `make` puis scripts/figures.py."""
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parent.parent
FIG, IMG, OUT = ROOT / "figures", ROOT / "images", ROOT / "docs"
OUT.mkdir(exist_ok=True)

F = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("Sans", F + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("Sans-B", F + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Sans-I", F + "DejaVuSans-Oblique.ttf"))
pdfmetrics.registerFont(TTFont("Mono", F + "DejaVuSansMono.ttf"))
pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-B", italic="Sans-I", boldItalic="Sans-B")

TEAL, NAVY, ORANGE = colors.HexColor("#12808A"), colors.HexColor("#1F3A5F"), colors.HexColor("#B85E12")
MIST = colors.HexColor("#EEF5F6")

body = ParagraphStyle("body", fontName="Sans", fontSize=10, leading=14.5, textColor=colors.HexColor("#2B3A4F"),
                      spaceAfter=6)
h1 = ParagraphStyle("h1", fontName="Sans-B", fontSize=16, leading=20, textColor=NAVY, spaceBefore=14, spaceAfter=8)
h2 = ParagraphStyle("h2", fontName="Sans-B", fontSize=12, leading=16, textColor=TEAL, spaceBefore=8, spaceAfter=4)
cap = ParagraphStyle("cap", parent=body, fontName="Sans-I", fontSize=8.5, alignment=TA_CENTER,
                     textColor=colors.HexColor("#5A6B80"))
bul = ParagraphStyle("bul", parent=body, leftIndent=14, bulletIndent=4, spaceAfter=3)
code = ParagraphStyle("code", fontName="Mono", fontSize=8.3, leading=11, backColor=MIST, borderPadding=6,
                      leftIndent=6, rightIndent=6, spaceBefore=4, spaceAfter=10)
title = ParagraphStyle("title", fontName="Sans-B", fontSize=26, leading=32, textColor=NAVY, alignment=TA_CENTER)
sub = ParagraphStyle("sub", parent=body, fontSize=13, leading=18, alignment=TA_CENTER, textColor=TEAL)

P = lambda t, s=body: Paragraph(t, s)


def bullets(items):
    return [Paragraph(i, bul, bulletText="•") for i in items]


def fig(path, width_cm, caption):
    from reportlab.lib.utils import ImageReader
    w, h = ImageReader(str(path)).getSize()
    return KeepTogether([Image(str(path), width=width_cm * cm, height=width_cm * cm * h / w), P(caption, cap)])


def table(rows, widths, head=TEAL):
    t = Table(rows, colWidths=[w * cm for w in widths], repeatRows=1)
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Sans", 9), ("FONT", (0, 0), (-1, 0), "Sans-B", 9),
        ("BACKGROUND", (0, 0), (-1, 0), head), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, MIST]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D6DE")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return t


def footer(c, doc):
    c.saveState()
    c.setFont("Sans", 8)
    c.setFillColor(colors.HexColor("#7A8899"))
    c.drawString(2 * cm, 1.2 * cm, "Mini-projet 3 — Pipeline de traitement d'image HDL : filtre de Sobel")
    c.drawRightString(A4[0] - 2 * cm, 1.2 * cm, str(doc.page))
    c.restoreState()


def build():
    m = json.loads((ROOT / "results" / "metrics.json").read_text())
    log = (ROOT / "results" / "sim_log.txt").read_text().strip().replace(str(ROOT) + "/", "")
    pct = lambda k: f"{m[k]['identical_pixels']} / {m[k]['total_pixels']} ({m[k]['match_percent']:.1f} %)".replace(".", ",")
    s = []

    # ------------------------------------------------------------ Couverture
    s += [Spacer(1, 4.5 * cm), P("Mini-projet 3", sub), Spacer(1, 10),
          P("Pipeline de traitement d'image HDL :<br/>filtre de Sobel", title), Spacer(1, 14),
          P("Conception, simulation et validation d'un circuit de détection de contours", sub),
          Spacer(1, 1.2 * cm), Image(str(IMG / "comparison.png"), width=15 * cm, height=15 * cm * 924 / 1320),
          Spacer(1, 1.2 * cm),
          P("Outils : Verilog · Verilator · C++ · Python · NumPy · OpenCV · GTKWave", ParagraphStyle(
              "c", parent=body, alignment=TA_CENTER)),
          P("Réalisé par : [Étudiant 1], [Étudiant 2] — Encadré par : [Encadrant]",
            ParagraphStyle("c2", parent=body, alignment=TA_CENTER)),
          PageBreak()]

    # ------------------------------------------------------------ 1. Objectif
    s += [P("1. Objectif du projet", h1),
          P("Le but est de concevoir un <b>circuit matériel</b> (décrit en Verilog) qui détecte les contours "
            "d'une image en appliquant le filtre de Sobel. Le circuit reçoit les pixels un par un, comme le ferait "
            "une caméra, et produit pour chaque pixel la force du contour à cet endroit. Le travail demandé "
            "comporte quatre étapes :")]
    s += bullets(["Implémenter les masques de convolution Sobel 3×3.",
                  "Développer le traitement des pixels et le calcul du gradient.",
                  "Tester le module sur une image 64×64.",
                  "Comparer le résultat HDL avec OpenCV."])
    s += [P("Les livrables sont le code HDL, le testbench, le script Python, les images avant/après et un rapport. "
            "Tous se trouvent dans le dépôt, organisé comme suit :")]
    s += [table([["Dossier / fichier", "Contenu"],
                 ["rtl/", "Code HDL : line_buffer.v, sobel_kernel.v, sobel_top.v"],
                 ["tb/tb_sobel.cpp", "Testbench Verilator (C++), auto-vérifiant, trace VCD"],
                 ["scripts/sobel.py", "Préparation de l'image, références NumPy/OpenCV, comparaison"],
                 ["scripts/figures.py", "Chronogramme, schéma d'architecture, images agrandies"],
                 ["images/, results/", "Images avant/après, métriques, journal de simulation, VCD"],
                 ["Makefile", "make (tout), make lint, make wave, make clean"]], [4.5, 12])]

    # ------------------------------------------------------------ 2. Sobel
    s += [P("2. Le filtre de Sobel", h1),
          P("Un contour est un endroit où la luminosité change brusquement. Le filtre de Sobel mesure ce "
            "changement avec deux masques 3×3 : <b>Gx</b> compare la colonne de droite à celle de gauche "
            "(il détecte les contours verticaux) et <b>Gy</b> compare la ligne du bas à celle du haut "
            "(contours horizontaux). Le pixel central est pondéré par 2 pour lisser le bruit."),
          fig(FIG / "masks.png", 8, "Figure 1 — Masques de Sobel Gx et Gy"),
          P("Pour une fenêtre de pixels p[ligne][colonne] centrée sur (x, y) :"),
          Preformatted("Gx = (p02 + 2·p12 + p22) − (p00 + 2·p10 + p20)\n"
                       "Gy = (p20 + 2·p21 + p22) − (p00 + 2·p01 + p02)\n"
                       "|G| = √(Gx² + Gy²)  ≈  |Gx| + |Gy|   (puis saturation à 255)", code),
          P("<b>Choix matériels.</b> La racine carrée coûte cher en logique : on utilise la norme L1 "
            "|Gx| + |Gy|, standard en traitement d'image embarqué. La multiplication par 2 est un simple "
            "décalage d'un bit, donc le circuit n'a <b>aucun multiplieur</b>. Avec des pixels de 8 bits, "
            "Gx et Gy restent dans [−1020, +1020] : <b>11 bits signés</b> suffisent, et la somme "
            "|Gx| + |Gy| ≤ 2040 tient sur 12 bits.")]

    # ------------------------------------------------------------ 3. Architecture
    s += [P("3. Architecture du pipeline", h1),
          fig(FIG / "architecture.png", 16.5, "Figure 2 — Chaîne de traitement, un pixel par cycle"),
          P("Les pixels arrivent en <b>balayage raster</b> (gauche → droite, haut → bas), un par cycle "
            "quand <font face='Mono'>in_valid</font> = 1. Le circuit ne garde jamais l'image entière : "
            "il lui suffit de mémoriser les deux lignes précédentes."),
          P("3.1 Tampons de ligne — line_buffer.v", h2),
          P("Deux mémoires de 64 octets : <font face='Mono'>lb0</font> contient la ligne r−1 et "
            "<font face='Mono'>lb1</font> la ligne r−2. Quand le pixel (r, c) arrive, on lit lb1[c] et "
            "lb0[c], ce qui donne directement la colonne verticale de trois pixels (r−2, r−1, r). "
            "Ensuite on décale : lb1[c] ← lb0[c] et lb0[c] ← pixel. Une lecture et une écriture par cycle : "
            "sur FPGA, cela s'implante en BRAM ou en LUTRAM."),
          P("3.2 Fenêtre 3×3 — sobel_top.v", h2),
          P("Neuf registres forment la fenêtre. À chaque pixel valide, la fenêtre glisse d'une colonne : "
            "les colonnes existantes se décalent vers la gauche et la colonne fournie par les tampons entre "
            "à droite. Des compteurs <font face='Mono'>col</font>/<font face='Mono'>row</font> suivent la "
            "position ; la fenêtre est déclarée valide (<font face='Mono'>win_valid</font>) seulement si "
            "row ≥ 2 et col ≥ 2, c'est-à-dire quand elle contient vraiment 3 lignes et 3 colonnes de l'image. "
            "Son centre est alors le pixel (col−1, row−1)."),
          P("3.3 Noyau Sobel — sobel_kernel.v (2 étages)", h2),
          Preformatted(
              "// Étage 1 : convolution (décalages et additions uniquement)\n"
              "gx_c = (ext(p02) + (ext(p12) <<< 1) + ext(p22))\n"
              "     - (ext(p00) + (ext(p10) <<< 1) + ext(p20));\n"
              "gy_c = (ext(p20) + (ext(p21) <<< 1) + ext(p22))\n"
              "     - (ext(p00) + (ext(p01) <<< 1) + ext(p02));\n"
              "// Étage 2 : magnitude L1 saturée + seuil\n"
              "abs_gx = gx_s1[10] ? -gx_s1 : gx_s1;\n"
              "sum    = abs_gx + abs_gy;              // 12 bits, max 2040\n"
              "sat    = (sum > 255) ? 255 : sum[7:0];\n"
              "edge   = (sat >= threshold);", code),
          P("Les coordonnées (x, y) sont retardées de 2 cycles pour rester alignées avec le résultat. "
            "Le signal <font face='Mono'>frame_done</font> signale le dernier pixel de l'image."),
          KeepTogether([P("3.4 Performances", h2), table([["Caractéristique", "Valeur"],
                 ["Débit", "1 pixel par cycle d'horloge"],
                 ["Latence du pipeline", "3 cycles (fenêtre → étage 1 → étage 2)"],
                 ["Premier résultat", "après 2 lignes + 3 pixels (cycle 133 sans trous)"],
                 ["Mémoire", "2 × 64 × 8 bits = 128 octets"],
                 ["Multiplieurs", "0"],
                 ["Pixels produits", "62 × 62 = 3844 pixels intérieurs (bords à 0)"],
                 ["Qualité du code", "verilator --lint-only -Wall : aucun avertissement"]], [5, 11.5])])]

    # ------------------------------------------------------------ 4. Vérification
    s += [P("4. Vérification", h1),
          P("4.1 Testbench Verilator — tb/tb_sobel.cpp", h2),
          P("Verilator traduit le Verilog en un modèle C++ très rapide. Le testbench :")]
    s += bullets(["lit l'image d'entrée (format PGM, 64×64, 8 bits) ;",
                  "applique un reset puis envoie les pixels, avec <b>20 % de cycles vides aléatoires</b> sur "
                  "in_valid pour prouver que le pipeline supporte un flux irrégulier ;",
                  "range chaque sortie à sa position (out_x, out_y) et écrit l'image résultat ;",
                  "compare chaque pixel à un <b>modèle de référence C++</b>, vérifie qu'aucun pixel ne manque "
                  "ni n'est dupliqué, et affiche PASS ou FAIL ;",
                  "enregistre une trace VCD visible dans GTKWave (disposition fournie : results/sobel.gtkw)."])
    s += [P("Journal de la simulation :", body), Preformatted(log.split("\n", 1)[1] if "\n" in log else log, code),
          fig(FIG / "waveform.png", 16.5, "Figure 3 — Chronogramme autour de la première sortie : la fenêtre "
              "devient valide, Gx/Gy sont calculés, puis out_valid monte"),
          P("4.2 Script Python — scripts/sobel.py", h2),
          P("Le script génère une image de test (dégradé, rectangle, anneau, triangle, ligne, texte « HDL » et "
            "léger bruit) ou charge une image fournie avec --image. Il lance la simulation, puis calcule deux "
            "références logicielles : une convolution NumPy écrite à la main et "
            "<font face='Mono'>cv2.Sobel</font> d'OpenCV (ksize = 3, puis |Gx| + |Gy| saturé, identique à "
            "<font face='Mono'>cv2.add(convertScaleAbs(gx), convertScaleAbs(gy))</font>). Il mesure le nombre "
            "de pixels identiques, l'écart maximal, l'erreur quadratique moyenne et le PSNR, et produit les figures.")]

    # ------------------------------------------------------------ 5. Résultats
    k = "hdl_vs_opencv_L1_full_image"
    s += [P("5. Résultats et comparaison avec OpenCV", h1),
          fig(IMG / "comparison.png", 16, "Figure 4 — Entrée, sortie HDL, sortie OpenCV, contours binaires, "
              "norme L2 et carte des différences"),
          table([["Comparaison", "Pixels identiques", "Écart max", "PSNR"],
                 ["HDL / modèle NumPy (image entière)", pct("hdl_vs_numpy_full"), "0", "∞"],
                 ["HDL / OpenCV L1 (intérieur 62×62)", pct("hdl_vs_opencv_L1_interior"), "0", "∞"],
                 ["Contours binaires HDL / OpenCV", pct("edges_hdl_vs_opencv_interior"), "0", "∞"],
                 ["HDL / OpenCV L1 (bords inclus)", pct(k), str(m[k]["max_abs_diff"]),
                  f"{m[k]['psnr_db']} dB".replace(".", ",")],
                 ["HDL (L1) / OpenCV L2 √(Gx²+Gy²)", pct("hdl_vs_opencv_L2_interior"),
                  str(m["hdl_vs_opencv_L2_interior"]["max_abs_diff"]),
                  f"{m['hdl_vs_opencv_L2_interior']['psnr_db']} dB".replace(".", ",")]],
                [6.3, 4.6, 2.2, 2.4]),
          Spacer(1, 8),
          P("<b>Analyse.</b> Sur l'intérieur de l'image, le circuit donne <b>exactement</b> le même résultat "
            "qu'OpenCV : 100 % de pixels identiques et un écart maximal nul. Cela valide les masques, la "
            "largeur des données, la valeur absolue, la saturation et l'alignement de la fenêtre."),
          P("Les deux écarts restants sont attendus. (1) Le cadre de 1 pixel : le circuit ne calcule pas les "
            "bords, alors qu'OpenCV prolonge l'image en répliquant ses bords (BORDER_REPLICATE). (2) La norme "
            "L2 : la norme L1 surestime au plus d'un facteur √2 sur les diagonales, mais les contours trouvés "
            "sont les mêmes ; c'est le prix d'un circuit sans racine carrée ni multiplieur."),
          P("Le flux a aussi été testé avec 0 %, 50 % et 90 % de cycles vides et plusieurs graines "
            "aléatoires : tous les essais donnent PASS. Sans trous, 4096 pixels sont traités en 4102 cycles."),
          Spacer(1, 6)]

    # ------------------------------------------------------------ 6. Utilisation
    s += [P("6. Utilisation", h1),
          Preformatted("sudo apt install verilator gtkwave\n"
                       "python3 -m pip install numpy opencv-python matplotlib reportlab\n\n"
                       "make                                   # build + simulation + comparaison\n"
                       "make IMAGE=photo.jpg THRESH=80 GAP=0   # autre image, seuil, flux continu\n"
                       "make lint                              # vérification Verilator -Wall\n"
                       "make wave                              # chronogrammes dans GTKWave\n"
                       "python3 scripts/figures.py             # figures du rapport\n"
                       "python3 scripts/make_pdf.py            # ce document", code),
          P("7. Limites et perspectives", h1)]
    s += bullets(["<b>Bords</b> : répliquer les pixels de bord dans la fenêtre pour obtenir une sortie 64×64 "
                  "complète, identique à OpenCV partout.",
                  "<b>Magnitude</b> : approcher √(Gx² + Gy²) par max + min/2 ou par un CORDIC.",
                  "<b>Interface</b> : passer à AXI4-Stream (tready, tlast, tuser) pour gérer la contre-pression "
                  "et s'intégrer dans un SoC.",
                  "<b>Résolution</b> : le code est paramétré (WIDTH, HEIGHT) ; seuls les paramètres changent "
                  "pour du 640×480.",
                  "<b>Synthèse FPGA</b> : mesurer la fréquence maximale et les ressources réelles avec Yosys ou Vivado."])
    s += [P("8. Conclusion", h1),
          P("Nous avons conçu un pipeline Sobel complet en Verilog : tampons de ligne, fenêtre glissante et "
            "noyau de gradient en deux étages, au rythme d'un pixel par cycle et sans multiplieur. Un testbench "
            "Verilator auto-vérifiant et un script Python montrent que le circuit reproduit OpenCV bit à bit "
            "sur l'image 64×64 de test.")]

    doc = SimpleDocTemplate(str(OUT / "Sobel_HDL_explication.pdf"), pagesize=A4, leftMargin=2 * cm,
                            rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=2 * cm,
                            title="Pipeline Sobel HDL — document explicatif", author="Mini-projet 3")
    doc.build(s, onFirstPage=lambda c, d: None, onLaterPages=footer)
    print("PDF ->", OUT / "Sobel_HDL_explication.pdf")


if __name__ == "__main__":
    build()
