/*
 * Copyright (c) 2025 Govind
 * SPDX-License-Identifier: Apache-2.0
 *
 * lfsr_ctrl.v — Configurable LFSR Controller
 *
 * Manages all sequential state for the configurable LFSR block:
 *   - Reset-time width capture (4/8/12/16-bit via width_sel)
 *   - Mode FSM: RUN / LOAD_SEED / LOAD_TAP / HOLD
 *   - Nibble-serial seed staging register (4 cycles × 4-bit = 16-bit seed)
 *   - Primitive polynomial lookup table (4 verified polys per width)
 *   - Instantiates lfsr_core for the combinational next-state function
 *
 * Key timing behaviour:
 *   - width_sel is sampled on the FIRST clock cycle after rst_n deasserts
 *   - LOAD_SEED: 4 consecutive nibble cycles load the 16-bit seed_reg
 *   - LOAD_SEED → RUN transition: seed_reg (masked to width) loads into lfsr_reg
 *   - LOAD_TAP:  1 cycle; poly_idx selects the primitive polynomial for current width
 *   - HOLD:      LFSR register frozen; output unchanged
 */

`default_nettype none

module lfsr_ctrl (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [1:0] mode,       
    input  wire [1:0] width_sel,  
    input  wire [1:0] poly_idx,   
    input  wire [3:0] data_in,    
    output reg  [15:0] lfsr_reg   
);

    localparam MODE_RUN       = 2'b00;
    localparam MODE_LOAD_SEED = 2'b01;
    localparam MODE_LOAD_TAP  = 2'b10;
    localparam MODE_HOLD      = 2'b11;

    reg [1:0]  width_reg;    
    reg [15:0] tap_reg;      
    reg [15:0] seed_reg;     
    reg [1:0]  load_cnt;     
    reg        reset_done;   
    reg [1:0]  mode_prev;    

    wire [15:0] width_mask;
    assign width_mask = (width_reg == 2'b00) ? 16'h000F :   // 4-bit
                        (width_reg == 2'b01) ? 16'h00FF :   // 8-bit
                        (width_reg == 2'b10) ? 16'h0FFF :   // 12-bit
                                               16'hFFFF ;   // 16-bit

    wire [15:0] lfsr_next;
    lfsr_core u_core (
        .lfsr_reg   (lfsr_reg),
        .tap_reg    (tap_reg),
        .width_mask (width_mask),
        .lfsr_next  (lfsr_next)
    );

    wire entering_load_seed = (mode == MODE_LOAD_SEED) && (mode_prev != MODE_LOAD_SEED);
    wire entering_load_tap  = (mode == MODE_LOAD_TAP)  && (mode_prev != MODE_LOAD_TAP);
    wire apply_seed         = (mode == MODE_RUN)        && (mode_prev == MODE_LOAD_SEED);

    // =========================================================================
    // Primitive Polynomial Lookup Table
    //
    // Right-shift Galois convention:
    //   tap_reg[N-1] = 1 always          (feedback to MSB, implicit x^N)
    //   tap_reg[k]   = 1 for x^(k+1)    (each intermediate polynomial term)
    //
    // Verified primitive polynomials (maximal-length, period = 2^N - 1):
    //   4-bit : x^4+x+1   (0x0009)  |  x^4+x^3+1 (0x000C)
    //   8-bit : x^8+x^6+x^5+x^4+1 (0x00B8)  |  x^8+x^4+x^3+x^2+1 (0x008E)
    //   12-bit: x^12+x^11+x^10+x^4+1 (0x0E08)  [Xilinx XAPP052 {12,11,10,4}]
    //   16-bit: x^16+x^15+x^13+x^4+1 (0xD008)  [Xilinx XAPP052 {16,15,13,4}]
    //
    // Note: Degree 4 has only 2 primitive polynomials; indices 2-3 repeat.
    //       Degree 12 and 16 use one verified polynomial each; all indices repeat.
    //       Use LOAD_TAP with a custom raw tap (via a future extension) for others.
    // =========================================================================
    function [15:0] get_poly;
        input [1:0] w;  // width_reg value
        input [1:0] p;  // poly_idx value
        begin
            case ({w, p})
                // --- 4-bit ---
                4'b00_00: get_poly = 16'h0009; // x^4+x+1
                4'b00_01: get_poly = 16'h000C; // x^4+x^3+1
                4'b00_10: get_poly = 16'h0009; // x^4+x+1   (repeat — only 2 prims)
                4'b00_11: get_poly = 16'h000C; // x^4+x^3+1 (repeat)
                
                // --- 8-bit ---
                4'b01_00: get_poly = 16'h00B8; // x^8+x^6+x^5+x^4+1  (default)
                4'b01_01: get_poly = 16'h008E; // x^8+x^4+x^3+x^2+1
                4'b01_10: get_poly = 16'h00B8; // repeat
                4'b01_11: get_poly = 16'h008E; // repeat
                
                // --- 12-bit ---
                4'b10_00: get_poly = 16'h0E08; // x^12+x^11+x^10+x^4+1
                4'b10_01: get_poly = 16'h0E08; // repeat
                4'b10_10: get_poly = 16'h0E08; // repeat
                4'b10_11: get_poly = 16'h0E08; // repeat
                
                // --- 16-bit ---
                4'b11_00: get_poly = 16'hD008; // x^16+x^15+x^13+x^4+1
                4'b11_01: get_poly = 16'hD008; // repeat
                4'b11_10: get_poly = 16'hD008; // repeat
                default:  get_poly = 16'hD008; // repeat
            endcase
        end
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            reset_done <= 1'b0;
            width_reg  <= 2'b01;       
            tap_reg    <= 16'h00B8;    
            lfsr_reg   <= 16'h0001;    
            seed_reg   <= 16'h0001;    
            load_cnt   <= 2'b00;
            mode_prev  <= MODE_RUN;    

        end else if (!reset_done) begin
            reset_done <= 1'b1;
            width_reg  <= width_sel;                       
            tap_reg    <= get_poly(width_sel, 2'b00);      
            lfsr_reg   <= 16'h0001;                        
            seed_reg   <= 16'h0001;
            load_cnt   <= 2'b00;
            mode_prev  <= MODE_RUN;   

        end else begin
            mode_prev <= mode;
            if (entering_load_seed) begin
                seed_reg[3:0] <= data_in;   
                load_cnt      <= 2'b01;      
            end else if (mode == MODE_LOAD_SEED) begin
                load_cnt <= load_cnt + 1'b1;
                case (load_cnt)
                    2'b01:   seed_reg[7:4]   <= data_in;
                    2'b10:   seed_reg[11:8]  <= data_in;
                    2'b11:   seed_reg[15:12] <= data_in;
                    default: seed_reg[3:0]   <= data_in; 
                endcase
            end

            if (mode == MODE_LOAD_TAP) begin
                tap_reg <= get_poly(width_reg, poly_idx);
            end

            if (apply_seed) begin
                lfsr_reg <= ((seed_reg & width_mask) == 16'h0000)
                             ? 16'h0001
                             : (seed_reg & width_mask);

            end else if (mode == MODE_RUN) begin
                lfsr_reg <= lfsr_next;
            end
        end
    end

endmodule
