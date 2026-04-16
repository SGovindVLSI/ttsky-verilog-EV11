![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# Configurable Galois LFSR

A 16-bit Configurable Galois LFSR (Linear Feedback Shift Register) designed for submission via [Tiny Tapeout](https://tinytapeout.com) (SKY130 ASIC).

![LFSR Test Pass](https://img.shields.io/badge/Cocotb_Tests-10%2F10_Passing-brightgreen?logo=python)

## 📌 Features

- **Galois Architecture**: Shorter combinational critical path compared to Fibonacci LFSRs, designed for reliable high-speed ASIC execution (target: 50 MHz).
- **Configurable Widths**: Selectable as 4-bit, 8-bit, 12-bit, or 16-bit width at reset time via input pins.
- **Maximal-Length Guarantees**: On-board verification table containing pre-computed primitive polynomials to guarantee maximal-length pseudo-random sequence generation regardless of configured width.
- **Custom Seed Staging**: Capability to load a custom 16-bit seed state via a 4-cycle nibble-serial transmission protocol.
- **Robustness**: Implementations for automatic lockup-escape (from the all-zero dead state) and active-width bit masking out-of-the-box.
- **Full Output Bus**: Employs both `uo_out` (lower byte) and `uio_out` (upper byte) to expose the full 16-bit internal state every clock cycle.

## 📖 Usage & Documentation

For a deep dive into the operating modes (RUN, LOAD_SEED, LOAD_TAP, HOLD), pin mappings, seed procedures, and the specific polynomial table in hardware, please refer to the primary project documentation:
- [Read the full LFSR Documentation](docs/info.md)

## 🚀 Running the Tests Locally

The hardware is bundled with a comprehensive 10-test `cocotb` test suite that verifies everything from zero-seed guard functionality to polynomial swapping and mode holds. 

Requires `cocotb` and a simulator like `iverilog` installed.
```bash
cd test/
make
```

## What is Tiny Tapeout?
Tiny Tapeout is an educational project that aims to make it easier and cheaper than ever to get your digital and analog designs manufactured on a real chip.

To learn more and get started, visit https://tinytapeout.com.
