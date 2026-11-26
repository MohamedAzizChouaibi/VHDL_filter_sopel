// -----------------------------------------------------------------------------
// tb_sobel.cpp — Testbench Verilator pour sobel_top
//
//  * lit une image PGM (P5) 64x64 en niveaux de gris
//  * envoie les pixels en raster vers le DUT (avec trous aléatoires sur
//    in_valid pour tester la robustesse du pipeline)
//  * récupère les pixels de sortie (out_x, out_y) et écrit deux PGM :
//    magnitude et contours binaires
//  * compare au modèle de référence C++ (bit-exact) -> PASS/FAIL
//  * génère une trace VCD pour GTKWave
//
// Usage : Vsobel_top <in.pgm> <out_mag.pgm> <out_edge.pgm> <trace.vcd>
//                    [threshold=100] [gap_percent=20] [seed=1]
// -----------------------------------------------------------------------------
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <memory>
#include <string>
#include <vector>

#include "Vsobel_top.h"
#include "verilated.h"
#include "verilated_vcd_c.h"

static const int W = 64;
static const int H = 64;

static bool read_pgm(const char* path, std::vector<uint8_t>& img, int& w, int& h) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return false;
    std::string magic; int maxv;
    f >> magic;
    auto skip = [&]() { // espaces + commentaires
        while (true) {
            int c = f.peek();
            if (c == '#') { std::string l; std::getline(f, l); }
            else if (isspace(c)) f.get();
            else break;
        }
    };
    skip(); f >> w; skip(); f >> h; skip(); f >> maxv; f.get();
    if (magic != "P5" || maxv != 255) return false;
    img.resize((size_t)w * h);
    f.read(reinterpret_cast<char*>(img.data()), img.size());
    return (bool)f;
}

static void write_pgm(const char* path, const std::vector<uint8_t>& img, int w, int h) {
    FILE* f = fopen(path, "wb");
    if (!f) { perror(path); exit(1); }
    fprintf(f, "P5\n%d %d\n255\n", w, h);
    fwrite(img.data(), 1, img.size(), f);
    fclose(f);
}

// Modèle de référence (même arithmétique que le RTL)
static void golden(const std::vector<uint8_t>& in, std::vector<uint8_t>& out) {
    out.assign((size_t)W * H, 0);
    for (int y = 1; y < H - 1; y++)
        for (int x = 1; x < W - 1; x++) {
            auto p = [&](int dy, int dx) { return (int)in[(y + dy) * W + (x + dx)]; };
            int gx = (p(-1, 1) + 2 * p(0, 1) + p(1, 1)) - (p(-1, -1) + 2 * p(0, -1) + p(1, -1));
            int gy = (p(1, -1) + 2 * p(1, 0) + p(1, 1)) - (p(-1, -1) + 2 * p(-1, 0) + p(-1, 1));
            int m = abs(gx) + abs(gy);
            out[y * W + x] = (uint8_t)(m > 255 ? 255 : m);
        }
}

int main(int argc, char** argv) {
    if (argc < 5) {
        fprintf(stderr, "usage: %s in.pgm out_mag.pgm out_edge.pgm trace.vcd "
                        "[threshold] [gap%%] [seed]\n", argv[0]);
        return 2;
    }
    const int threshold = argc > 5 ? atoi(argv[5]) : 100;
    const int gap_pct   = argc > 6 ? atoi(argv[6]) : 20;
    const unsigned seed = argc > 7 ? (unsigned)atoi(argv[7]) : 1u;
    srand(seed);

    std::vector<uint8_t> in;
    int w = 0, h = 0;
    if (!read_pgm(argv[1], in, w, h) || w != W || h != H) {
        fprintf(stderr, "Erreur : %s doit être un PGM P5 %dx%d\n", argv[1], W, H);
        return 2;
    }

    auto ctx = std::make_unique<VerilatedContext>();
    ctx->traceEverOn(true);
    auto dut = std::make_unique<Vsobel_top>(ctx.get());
    auto tfp = std::make_unique<VerilatedVcdC>();
    dut->trace(tfp.get(), 99);
    tfp->open(argv[4]);

    uint64_t t = 0;
    auto tick = [&]() {
        dut->clk = 0; dut->eval(); tfp->dump(t++);
        dut->clk = 1; dut->eval(); tfp->dump(t++);
    };

    std::vector<uint8_t> mag((size_t)W * H, 0), edge((size_t)W * H, 0);
    std::vector<int> hits((size_t)W * H, 0);
    int n_out = 0;
    bool done = false;
    uint64_t cycles = 0, first_in = 0, first_out = 0;

    auto sample = [&]() {     // échantillonne les sorties après le front montant
        if (dut->out_valid) {
            int x = dut->out_x, y = dut->out_y;
            mag[y * W + x]  = dut->out_pixel;
            edge[y * W + x] = dut->out_edge ? 255 : 0;
            hits[y * W + x]++;
            if (n_out == 0) first_out = cycles;
            n_out++;
            if (dut->frame_done) done = true;
        }
    };

    // Reset
    dut->rst = 1; dut->in_valid = 0; dut->in_pixel = 0; dut->threshold = threshold;
    for (int i = 0; i < 4; i++) tick();
    dut->rst = 0;

    // Envoi du flux de pixels
    size_t idx = 0;
    while (idx < in.size()) {
        bool send = (rand() % 100) >= gap_pct;
        dut->in_valid = send;
        dut->in_pixel = send ? in[idx] : 0;
        if (send && idx == 0) first_in = cycles;
        tick(); cycles++;
        if (send) idx++;
        sample();
    }
    dut->in_valid = 0;
    for (int i = 0; i < 10 && !done; i++) { tick(); cycles++; sample(); }
    for (int i = 0; i < 4; i++) { tick(); cycles++; }
    tfp->close();
    dut->final();

    write_pgm(argv[2], mag, W, H);
    write_pgm(argv[3], edge, W, H);

    // Vérification
    std::vector<uint8_t> ref;
    golden(in, ref);
    int mism = 0, dup = 0, miss = 0;
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++) {
            bool interior = x > 0 && x < W - 1 && y > 0 && y < H - 1;
            int k = y * W + x;
            if (interior && hits[k] == 0) miss++;
            if (hits[k] > 1) dup++;
            if (mag[k] != ref[k]) {
                if (mism < 5) fprintf(stderr, "  diff (%d,%d): hdl=%d ref=%d\n", x, y, mag[k], ref[k]);
                mism++;
            }
        }

    const int expected = (W - 2) * (H - 2);
    printf("=== Sobel HDL testbench ===\n");
    printf("image             : %s (%dx%d)\n", argv[1], W, H);
    printf("seuil / trous     : %d / %d%%\n", threshold, gap_pct);
    printf("cycles simulés    : %llu\n", (unsigned long long)cycles);
    printf("latence 1er pixel : %llu cycles\n", (unsigned long long)(first_out - first_in));
    printf("pixels émis       : %d (attendu %d)\n", n_out, expected);
    printf("manquants/doublons: %d / %d\n", miss, dup);
    printf("écarts vs modèle  : %d\n", mism);
    bool ok = (n_out == expected) && miss == 0 && dup == 0 && mism == 0 && done;
    printf("RESULTAT          : %s\n", ok ? "PASS" : "FAIL");
    return ok ? 0 : 1;
}
