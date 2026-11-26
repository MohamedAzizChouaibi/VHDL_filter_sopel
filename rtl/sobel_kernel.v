// -----------------------------------------------------------------------------
// sobel_kernel.v — Masques de convolution Sobel 3x3 + calcul du gradient
//
// Fenêtre (ligne, colonne) :      Masques :
//   p00 p01 p02                      Gx = [-1 0 +1]     Gy = [-1 -2 -1]
//   p10 p11 p12                           [-2 0 +2]          [ 0  0  0]
//   p20 p21 p22                           [-1 0 +1]          [+1 +2 +1]
//
// Pipeline à 2 étages :
//   Étage 1 : Gx, Gy (signés, 11 bits : plage [-1020, +1020])
//             les multiplications par 2 sont de simples décalages.
//   Étage 2 : |G| ≈ |Gx| + |Gy| (norme L1), saturation à 255,
//             seuillage binaire optionnel (edge = |G| >= threshold).
// Latence : 2 cycles. Débit : 1 pixel / cycle.
// -----------------------------------------------------------------------------
module sobel_kernel #(
    parameter integer DW = 8
) (
    input  wire          clk,
    input  wire          rst,
    input  wire          in_valid,
    input  wire [DW-1:0] p00, p01, p02,
    input  wire [DW-1:0] p10,      p12,   // p11 n'intervient pas dans Sobel
    input  wire [DW-1:0] p20, p21, p22,
    input  wire [DW-1:0] threshold,
    output reg           out_valid,
    output reg  [DW-1:0] magnitude,   // |Gx|+|Gy| saturé
    output reg           edge_bit,    // magnitude >= threshold
    output reg  signed [DW+2:0] gx_out, // pour débogage / GTKWave
    output reg  signed [DW+2:0] gy_out
);
    localparam integer GW = DW + 3;   // 8 bits -> 11 bits signés

    // Extension non signée -> signée sur GW bits
    function automatic signed [GW-1:0] ext(input [DW-1:0] v);
        ext = $signed({3'b000, v});
    endfunction

    // ---------------- Étage 1 : convolution ----------------
    wire signed [GW-1:0] gx_c =
          (ext(p02) + (ext(p12) <<< 1) + ext(p22))
        - (ext(p00) + (ext(p10) <<< 1) + ext(p20));
    wire signed [GW-1:0] gy_c =
          (ext(p20) + (ext(p21) <<< 1) + ext(p22))
        - (ext(p00) + (ext(p01) <<< 1) + ext(p02));

    reg signed [GW-1:0] gx_s1, gy_s1;
    reg                 v_s1;

    always @(posedge clk) begin
        if (rst) begin
            v_s1  <= 1'b0;
            gx_s1 <= {GW{1'b0}};
            gy_s1 <= {GW{1'b0}};
        end else begin
            v_s1  <= in_valid;
            gx_s1 <= gx_c;
            gy_s1 <= gy_c;
        end
    end

    // ---------------- Étage 2 : magnitude ----------------
    wire [GW-1:0] abs_gx = gx_s1[GW-1] ? -gx_s1 : gx_s1;
    wire [GW-1:0] abs_gy = gy_s1[GW-1] ? -gy_s1 : gy_s1;
    wire [GW:0]   sum    = {1'b0, abs_gx} + {1'b0, abs_gy};   // max 2040
    wire [DW-1:0] sat    = (sum > {{(GW-DW+1){1'b0}}, {DW{1'b1}}})
                         ? {DW{1'b1}} : sum[DW-1:0];

    always @(posedge clk) begin
        if (rst) begin
            out_valid <= 1'b0;
            magnitude <= {DW{1'b0}};
            edge_bit  <= 1'b0;
            gx_out    <= {GW{1'b0}};
            gy_out    <= {GW{1'b0}};
        end else begin
            out_valid <= v_s1;
            magnitude <= sat;
            edge_bit  <= (sat >= threshold);
            gx_out    <= gx_s1;
            gy_out    <= gy_s1;
        end
    end
endmodule
