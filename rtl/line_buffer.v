// -----------------------------------------------------------------------------
// line_buffer.v — Double tampon de lignes (2 lignes) pour fenêtre 3x3
//
// À chaque pixel valide d'entrée (ligne r, colonne c) :
//   tap_row0 = pixel(r-2, c)   (ligne la plus ancienne)
//   tap_row1 = pixel(r-1, c)
//   tap_row2 = pixel(r  , c)   (pixel courant, transmis directement)
// Les deux mémoires sont décalées : lb1[c] <= lb0[c], lb0[c] <= pixel.
// Inférable en BRAM/LUTRAM sur FPGA (une lecture + une écriture par cycle).
// -----------------------------------------------------------------------------
module line_buffer #(
    parameter integer WIDTH = 64,   // pixels par ligne
    parameter integer DW    = 8,    // bits par pixel
    parameter integer AW    = $clog2(WIDTH)
) (
    input  wire          clk,
    input  wire          en,        // pixel d'entrée valide
    input  wire [AW-1:0] col,       // colonne du pixel courant
    input  wire [DW-1:0] pix_in,
    output wire [DW-1:0] tap_row0,  // ligne r-2
    output wire [DW-1:0] tap_row1,  // ligne r-1
    output wire [DW-1:0] tap_row2   // ligne r
);
    reg [DW-1:0] lb0 [0:WIDTH-1];   // contient la ligne r-1
    reg [DW-1:0] lb1 [0:WIDTH-1];   // contient la ligne r-2

    // Initialisation à zéro (simulation) pour éviter les X/valeurs aléatoires
    integer i;
    initial begin
        for (i = 0; i < WIDTH; i = i + 1) begin
            lb0[i] = {DW{1'b0}};
            lb1[i] = {DW{1'b0}};
        end
    end

    assign tap_row0 = lb1[col];
    assign tap_row1 = lb0[col];
    assign tap_row2 = pix_in;

    always @(posedge clk) begin
        if (en) begin
            lb1[col] <= lb0[col];
            lb0[col] <= pix_in;
        end
    end
endmodule
