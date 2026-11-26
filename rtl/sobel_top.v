// -----------------------------------------------------------------------------
// sobel_top.v — Pipeline de détection de contours Sobel (flux raster)
//
// Entrée : flux de pixels en balayage raster (gauche->droite, haut->bas),
//          1 pixel par cycle quand in_valid = 1 (des trous sont permis).
// Sortie : magnitude du gradient pour chaque pixel intérieur (x,y),
//          1 <= x <= W-2, 1 <= y <= H-2, avec ses coordonnées.
//          Les pixels de bord ne sont pas émis (mis à 0 par le testbench).
//
//  pixel ──► line_buffer ──► fenêtre 3x3 (registres à décalage)
//                                 │
//                                 ▼
//                        sobel_kernel (Gx, Gy, |G|)  ──► sortie
//
// Latence : 3 cycles entre le pixel (y+1, x+1) et la sortie du pixel (y, x).
// -----------------------------------------------------------------------------
module sobel_top #(
    parameter integer WIDTH  = 64,
    parameter integer HEIGHT = 64,
    parameter integer DW     = 8,
    parameter integer AW     = 6     // log2(WIDTH), et log2(HEIGHT)
) (
    input  wire          clk,
    input  wire          rst,
    input  wire          in_valid,
    input  wire [DW-1:0] in_pixel,
    input  wire [DW-1:0] threshold,
    output wire          out_valid,
    output wire [DW-1:0] out_pixel,   // magnitude
    output wire          out_edge,    // contour binaire
    output reg  [AW-1:0] out_x,
    output reg  [AW-1:0] out_y,
    output wire signed [DW+2:0] out_gx,
    output wire signed [DW+2:0] out_gy,
    output wire          frame_done   // impulsion : dernier pixel émis
);
    // ---------------- Compteurs de position du pixel d'entrée ----------------
    reg [AW-1:0] col, row;
    always @(posedge clk) begin
        if (rst) begin
            col <= {AW{1'b0}};
            row <= {AW{1'b0}};
        end else if (in_valid) begin
            if (col == AW'(WIDTH - 1)) begin
                col <= {AW{1'b0}};
                row <= (row == AW'(HEIGHT - 1)) ? {AW{1'b0}} : row + 1'b1;
            end else begin
                col <= col + 1'b1;
            end
        end
    end

    // ---------------- Tampons de lignes ----------------
    wire [DW-1:0] t0, t1, t2;
    line_buffer #(.WIDTH(WIDTH), .DW(DW), .AW(AW)) u_lb (
        .clk(clk), .en(in_valid), .col(col), .pix_in(in_pixel),
        .tap_row0(t0), .tap_row1(t1), .tap_row2(t2)
    );

    // ---------------- Fenêtre 3x3 (registres à décalage) ----------------
    // w[r][c] : r = 0 (haut) .. 2 (bas), c = 0 (gauche) .. 2 (droite)
    reg [DW-1:0] w00, w01, w02, w10, w11, w12, w20, w21, w22;
    reg          win_valid;
    reg [AW-1:0] win_x, win_y;   // coordonnées du centre de la fenêtre

    always @(posedge clk) begin
        if (rst) begin
            {w00, w01, w02, w10, w11, w12, w20, w21, w22} <= {9*DW{1'b0}};
            win_valid <= 1'b0;
            win_x     <= {AW{1'b0}};
            win_y     <= {AW{1'b0}};
        end else begin
            win_valid <= 1'b0;
            if (in_valid) begin
                w00 <= w01; w01 <= w02; w02 <= t0;
                w10 <= w11; w11 <= w12; w12 <= t1;
                w20 <= w21; w21 <= w22; w22 <= t2;
                // la fenêtre est complète dès que 3 lignes et 3 colonnes ont été vues
                win_valid <= (row >= AW'(2)) && (col >= AW'(2));
                win_x     <= col - 1'b1;
                win_y     <= row - 1'b1;
            end
        end
    end

    // ---------------- Noyau Sobel (2 étages) ----------------
    sobel_kernel #(.DW(DW)) u_kernel (
        .clk(clk), .rst(rst), .in_valid(win_valid),
        .p00(w00), .p01(w01), .p02(w02),
        .p10(w10),            .p12(w12),
        .p20(w20), .p21(w21), .p22(w22),
        .threshold(threshold),
        .out_valid(out_valid), .magnitude(out_pixel), .edge_bit(out_edge),
        .gx_out(out_gx), .gy_out(out_gy)
    );

    // Coordonnées retardées pour rester alignées avec le noyau (2 cycles)
    reg [AW-1:0] x_s1, y_s1;
    always @(posedge clk) begin
        x_s1  <= win_x;  y_s1  <= win_y;
        out_x <= x_s1;   out_y <= y_s1;
    end

    assign frame_done = out_valid && (out_x == AW'(WIDTH - 2))
                                  && (out_y == AW'(HEIGHT - 2));

    // w11 (centre) n'est pas utilisé par Sobel : conservé pour lisibilité
    wire _unused = &{1'b0, w11};
endmodule
