# VHDL_filter_sopel — Pipeline Sobel HDL (Mini-projet 3)

```
rtl/        line_buffer.v, sobel_kernel.v, sobel_top.v   (code HDL)
tb/         tb_sobel.cpp                                  (testbench Verilator auto-vérifiant)
scripts/    sobel.py                                      (NumPy/OpenCV : image, référence, comparaison)
images/     input.png, output_hdl*.png, output_opencv*.png, comparison.png
results/    sim_log.txt, metrics.json, sobel.vcd, sobel.gtkw
rapport.md  rapport
docs/       Sobel_HDL_explication.pdf (document explicatif)
figures/    chronogramme, architecture, masques (scripts/figures.py)
```

Prérequis : `sudo apt install verilator gtkwave` et `pip install numpy opencv-python matplotlib`.

```bash
make         # build + simulation + comparaison  -> RESULTAT : PASS
make wave    # GTKWave
python3 scripts/figures.py && python3 scripts/make_pdf.py   # figures + PDF (reportlab)
```
