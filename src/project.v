/*
 * Copyright (c) 2025 Govind
 * SPDX-License-Identifier: Apache-2.0
 *
 * project.v — tt_um_LFSR top-level wrapper
 *
 * Configurable Galois LFSR for Tiny Tapeout SKY130 (1×1 tile)
 *
 * ┌──────────────────────────────────── Pin Map ─────────────────────────────────────┐
 * │  ui_in[1:0]   → mode       RUN=00 | LOAD_SEED=01 | LOAD_TAP=10 | HOLD=11         │
 * │  ui_in[3:2]   → width_sel  4-bit=00 | 8-bit=01 | 12-bit=10 | 16-bit=11           │
 * │                            *** Sampled ONLY on first cycle after rst_n HIGH ***  │
 * │  ui_in[5:4]   → poly_idx   Polynomial index 0–3 (used with LOAD_TAP mode)        │
 * │  ui_in[7:6]   → data_in upper nibble (used with LOAD_SEED for nibble bits [3:2]) │
 * │  ui_in[7:4]   → data_in[3:0]  Full 4-bit nibble for LOAD_SEED                    │
 * │                                                                                  │
 * │  uo_out[7:0]  → lfsr_reg[7:0]   Lower byte of LFSR (live, every cycle)           │
 * │  uio_out[7:0] → lfsr_reg[15:8]  Upper byte of LFSR (live, every cycle)           │
 * │  uio_oe[7:0]  → 8'hFF           All bidir pins configured as OUTPUTS             │
 * │                                                                                  │
 * │  Combined: {uio_out, uo_out} = full 16-bit LFSR state                            │
 * └──────────────────────────────────────────────────────────────────────────────────┘
 *
 * Files:
 *   src/project.v   — This file (top-level wrapper)
 *   src/lfsr_ctrl.v — Mode FSM, registers, polynomial table, seed/tap loading
 *   src/lfsr_core.v — Galois LFSR combinational next-state logic
 */

`default_nettype none
`timescale 1ns / 1ps

module tt_um_LFSR (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path  (unused — all bidir as outputs)
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (1 = output, 0 = input)
    input  wire       ena,      // Always 1 when powered; safely ignored
    input  wire       clk,      // Clock
    input  wire       rst_n     // Reset, active-low
);

    wire [1:0] mode      = ui_in[1:0];
    wire [1:0] width_sel = ui_in[3:2];
    wire [1:0] poly_idx  = ui_in[5:4];   // Subset of data_in; dual-purpose pin pair
    wire [3:0] data_in   = ui_in[7:4];

    wire [15:0] lfsr_state;   

    lfsr_ctrl u_ctrl (
        .clk       (clk),
        .rst_n     (rst_n),
        .mode      (mode),
        .width_sel (width_sel),
        .poly_idx  (poly_idx),
        .data_in   (data_in),
        .lfsr_reg  (lfsr_state)
    );

    assign uo_out  = lfsr_state[7:0];    
    assign uio_out = lfsr_state[15:8];   
    assign uio_oe  = 8'hFF;              

    // Suppress unused-input warnings (TT convention)
    wire _unused = &{ena, uio_in, 1'b0};

endmodule
