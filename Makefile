# Mini-projet 3 — Pipeline Sobel HDL
#   make           : compile + simule + compare (flux complet)
#   make sim       : compile + simule uniquement (image déjà générée)
#   make lint      : vérification Verilator -Wall
#   make wave      : ouvre la trace dans GTKWave
#   make live      : test en direct avec la caméra (LIVE_W x LIVE_H, CAM=0)
#   make live-check: test caméra sans écran sur LIVE_FRAMES images -> PASS/FAIL
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

# Test live (caméra)
LIVE_OBJ    := obj_live
LIVE_BIN    := $(LIVE_OBJ)/Vsobel_live
LIVE_W      ?= 160
LIVE_H      ?= 120
CAM         ?= 0
LIVE_FRAMES ?= 60
LIVE_ARGS   := --sim $(LIVE_BIN) --width $(LIVE_W) --height $(LIVE_H) \
               --source $(CAM) --threshold $(THRESH)

.PHONY: all build sim lint wave run clean live live-build live-check

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

# Build live : RTL paramétré à LIVE_W x LIVE_H, sans trace VCD.
# Le fichier .dims force la recompilation si les dimensions changent.
$(LIVE_OBJ)/.dims-$(LIVE_W)x$(LIVE_H):
	rm -rf $(LIVE_OBJ) && mkdir -p $(LIVE_OBJ) && touch $@

$(LIVE_BIN): $(RTL) tb/tb_live.cpp $(LIVE_OBJ)/.dims-$(LIVE_W)x$(LIVE_H)
	$(VERILATOR) -Wall --cc --exe --build -O3 \
	    --top-module sobel_top -GWIDTH=$(LIVE_W) -GHEIGHT=$(LIVE_H) \
	    -CFLAGS "-O2 -DIMG_W=$(LIVE_W) -DIMG_H=$(LIVE_H)" \
	    -Mdir $(LIVE_OBJ) $(RTL) tb/tb_live.cpp -o Vsobel_live

live-build: $(LIVE_BIN)

live: $(LIVE_BIN)
	$(PYTHON) scripts/live.py $(LIVE_ARGS)

live-check: $(LIVE_BIN)
	$(PYTHON) scripts/live.py $(LIVE_ARGS) --no-display --frames $(LIVE_FRAMES)

clean:
	rm -rf $(OBJ) $(LIVE_OBJ) images/*.pgm images/*.png results/*.vcd results/*.txt results/*.json
