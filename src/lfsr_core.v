/*
 * Copyright (c) 2025 Govind
 * SPDX-License-Identifier: Apache-2.0
 *
 * lfsr_core.v — Galois LFSR Combinational Next-State Logic
 *
 * Implements a right-shift Galois LFSR:
 *   fb           = lfsr_reg[0]             (feedback / serial output bit)
 *   lfsr_next    = {0, lfsr_reg[15:1]}     (right shift, MSB cleared)
 *                  XOR (fb ? tap_reg : 0)   (XOR tap mask when fb = 1)
 *                  AND width_mask           (zero out inactive upper bits)
 *
 * Tap mask convention:
 *   tap_reg[N-1] = 1 always        (routes feedback to MSB — tap for x^N term)
 *   tap_reg[k]   = 1 for x^(k+1)  (each middle polynomial term)
 *   e.g. 8-bit x^8+x^6+x^5+x^4+1 → tap_reg = 16'h00B8 (bits 7,5,4,3 set)
 *
 * Lockup protection:
 *   If all bits within width_mask are 0, the next state is forced to 16'h0001
 *   to prevent the LFSR from remaining stuck in the all-zero dead state.
 */

`default_nettype none

module lfsr_core (
    input  wire [15:0] lfsr_reg,   
    input  wire [15:0] tap_reg,    
    input  wire [15:0] width_mask, 
    output wire [15:0] lfsr_next   
);

    wire        fb;        
    wire [15:0] shifted;   
    wire [15:0] tapped;    
    wire        all_zero;  

    assign fb = lfsr_reg[0];
    assign shifted = {1'b0, lfsr_reg[15:1]};
    assign tapped = shifted ^ ({16{fb}} & tap_reg);
    assign all_zero = ((lfsr_reg & width_mask) == 16'h0000);
    assign lfsr_next = all_zero ? 16'h0001 : (tapped & width_mask);

endmodule
