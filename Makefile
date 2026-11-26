# Mini-projet 3 — Pipeline Sobel HDL
#   make           : compile + simule + compare (flux complet)
#   make sim       : compile + simule uniquement (image déjà générée)
#   make lint      : vérification Verilator -Wall
#   make wave      : ouvre la trace dans GTKWave
#   make clean

VERILATOR ?= verilator
PYTHON    ?= python3
RTL       := rtl/line_buffer.v rtl/sobel_kernel.v rtl/sobel_top.v
TB        := tb/tb_sobel.cpp
OBJ       := obj_dir
BIN       := $(OBJ)/Vsobel_top
THRESH    ?= 100
GAP       ?= 20
SEED      ?= 1
IMAGE     ?=

.PHONY: all build sim lint wave run clean

all: run

lint:
	$(VERILATOR) --lint-only -Wall --top-module sobel_top $(RTL)

$(BIN): $(RTL) $(TB)
	$(VERILATOR) -Wall --cc --exe --build --trace -O2 \
	    --top-module sobel_top -Mdir $(OBJ) $(RTL) $(TB) -o Vsobel_top

build: $(BIN)

images/input.pgm:
	$(PYTHON) scripts/sobel.py prepare $(if $(IMAGE),--image $(IMAGE))

sim: $(BIN) images/input.pgm
	$(BIN) images/input.pgm images/output_hdl.pgm images/output_hdl_edges.pgm \
	    results/sobel.vcd $(THRESH) $(GAP) $(SEED) | tee results/sim_log.txt

run: build
	$(PYTHON) scripts/sobel.py all --sim $(BIN) --threshold $(THRESH) \
	    --gap $(GAP) --seed $(SEED) $(if $(IMAGE),--image $(IMAGE))

wave:
	gtkwave results/sobel.vcd results/sobel.gtkw &

clean:
	rm -rf $(OBJ) images/*.pgm images/*.png results/*.vcd results/*.txt results/*.json
