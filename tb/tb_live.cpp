// -----------------------------------------------------------------------------
// tb_live.cpp — Banc Verilator « temps réel » pour sobel_top (test caméra)
//
// Le modèle RTL reste vivant pendant toute la session et traite un flux
// d'images envoyé par scripts/live.py via des tubes (stdin/stdout) :
//
//   stdin  (par image) : 1 octet  seuil
//                        W*H octets pixels (niveaux de gris, raster)
//   stdout (par image) : uint32   cycles d'horloge simulés pour l'image
//                        uint32   nombre de pixels émis (out_valid)
//                        uint32   1 si frame_done a été vu, sinon 0
//                        W*H octets magnitude |Gx|+|Gy| (bords à 0)
//                        W*H octets contours binaires (0 / 255)
//
// Pas de reset entre deux images : les compteurs col/row reviennent à 0
// après W*H pixels et win_valid masque les deux premières lignes, ce qui
// vérifie aussi que le pipeline enchaîne correctement les trames.
//
// Dimensions fixées à la compilation (doivent égaler -GWIDTH / -GHEIGHT) :
//   -CFLAGS "-DIMG_W=160 -DIMG_H=120"
// Usage : Vsobel_live [gap_percent=0] [seed=1]
// -----------------------------------------------------------------------------
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <vector>

#include "Vsobel_top.h"
#include "verilated.h"

#ifndef IMG_W
#define IMG_W 160
#endif
#ifndef IMG_H
#define IMG_H 120
#endif

static const int W = IMG_W;
static const int H = IMG_H;

static bool read_exact(void* buf, size_t n) {
    return fread(buf, 1, n, stdin) == n;
}

int main(int argc, char** argv) {
    const int gap_pct   = argc > 1 ? atoi(argv[1]) : 0;
    const unsigned seed = argc > 2 ? (unsigned)atoi(argv[2]) : 1u;
    srand(seed);

    auto ctx = std::make_unique<VerilatedContext>();
    auto dut = std::make_unique<Vsobel_top>(ctx.get());

    auto tick = [&]() {
        dut->clk = 0; dut->eval();
        dut->clk = 1; dut->eval();
    };

    std::vector<uint8_t> in((size_t)W * H), mag((size_t)W * H), edge((size_t)W * H);
    uint32_t cycles = 0, n_out = 0, done = 0;

    auto sample = [&]() {
        if (dut->out_valid) {
            int x = dut->out_x, y = dut->out_y;
            if (x < W && y < H) {
                mag[(size_t)y * W + x]  = dut->out_pixel;
                edge[(size_t)y * W + x] = dut->out_edge ? 255 : 0;
            }
            n_out++;
            if (dut->frame_done) done = 1;
        }
    };

    // Reset unique au démarrage
    dut->rst = 1; dut->in_valid = 0; dut->in_pixel = 0; dut->threshold = 100;
    for (int i = 0; i < 4; i++) tick();
    dut->rst = 0;

    fprintf(stderr, "[tb_live] prêt : %dx%d, trous %d%%\n", W, H, gap_pct);

    uint8_t thr;
    while (read_exact(&thr, 1) && read_exact(in.data(), in.size())) {
        std::fill(mag.begin(), mag.end(), 0);
        std::fill(edge.begin(), edge.end(), 0);
        cycles = n_out = done = 0;
        dut->threshold = thr;

        size_t idx = 0;
        while (idx < in.size()) {
            bool send = gap_pct > 0 ? (rand() % 100) >= gap_pct : true;
            dut->in_valid = send;
            dut->in_pixel = send ? in[idx] : 0;
            tick(); cycles++;
            if (send) idx++;
            sample();
        }
        // Vidange du pipeline (3 cycles de latence) jusqu'à frame_done
        dut->in_valid = 0;
        for (int i = 0; i < 16 && !done; i++) { tick(); cycles++; sample(); }

        fwrite(&cycles, 4, 1, stdout);
        fwrite(&n_out, 4, 1, stdout);
        fwrite(&done, 4, 1, stdout);
        fwrite(mag.data(), 1, mag.size(), stdout);
        fwrite(edge.data(), 1, edge.size(), stdout);
        fflush(stdout);
    }
    dut->final();
    return 0;
}
