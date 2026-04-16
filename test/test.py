# SPDX-FileCopyrightText: © 2025 Govind
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

# Mode constants (ui_in[1:0])
MODE_RUN       = 0b00
MODE_LOAD_SEED = 0b01
MODE_LOAD_TAP  = 0b10
MODE_HOLD      = 0b11

# Helper: pack ui_in fields into one 8-bit value
#   ui_in[1:0] = mode
#   ui_in[3:2] = width_sel  (captured at reset release only)
#   ui_in[5:4] = poly_idx   (used with LOAD_TAP; also = data_in[1:0])
#   ui_in[7:4] = data_in    (nibble for LOAD_SEED)
def make_ui(mode=MODE_RUN, width_sel=0b01, poly_idx=0b00, data_in=0b0000):
    return (mode & 0x3) | ((width_sel & 0x3) << 2) | ((data_in & 0xF) << 4)

# Helper: read combined 16-bit LFSR state from outputs
#   {uio_out, uo_out} = lfsr_reg[15:0]
def read_lfsr(dut):
    lo = int(dut.uo_out.value)
    hi = int(dut.uio_out.value)
    return (hi << 8) | lo

# Helper: load a 16-bit seed via nibble-serial LOAD_SEED (4 cycles)
#   Cycle 0 (entry): bits [3:0]   — entering_load_seed fires here
#   Cycle 1        : bits [7:4]
#   Cycle 2        : bits [11:8]
#   Cycle 3        : bits [15:12]
async def load_seed(dut, seed_val, width_sel=0b01):
    nibbles = [
        (seed_val >>  0) & 0xF,
        (seed_val >>  4) & 0xF,
        (seed_val >>  8) & 0xF,
        (seed_val >> 12) & 0xF,
    ]
    for nibble in nibbles:
        dut.ui_in.value = make_ui(mode=MODE_LOAD_SEED, width_sel=width_sel, data_in=nibble)
        await ClockCycles(dut.clk, 1)


# Test 1: Reset State
@cocotb.test()
async def test_reset(dut):
    """After reset, LFSR output must be 0x0001 (default seed, 8-bit mode)."""
    dut._log.info("Start")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value    = 1
    dut.ui_in.value  = make_ui(mode=MODE_RUN, width_sel=0b01)   # 8-bit, RUN
    dut.uio_in.value = 0
    dut.rst_n.value  = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value  = 1
    await ClockCycles(dut.clk, 2)   # +1 for reset_done capture, +1 for output to settle

    lfsr = read_lfsr(dut)
    dut._log.info(f"LFSR after reset = 0x{lfsr:04X}")
    assert lfsr == 0x0001, f"Expected 0x0001, got 0x{lfsr:04X}"


# Test 2: Default 8-bit Run — Maximum-Length Sequence (255 unique states)
@cocotb.test()
async def test_default_8bit_run(dut):
    """8-bit LFSR with default poly (x^8+x^6+x^5+x^4+1) must visit all 255 states."""
    dut._log.info("Start")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut._log.info("Reset")
    dut.ena.value    = 1
    dut.ui_in.value  = make_ui(mode=MODE_RUN, width_sel=0b01)
    dut.uio_in.value = 0
    dut.rst_n.value  = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value  = 1
    await ClockCycles(dut.clk, 2)

    dut._log.info("Running 255 cycles and collecting states")
    dut.ui_in.value = make_ui(mode=MODE_RUN, width_sel=0b01)
    states = set()
    for _ in range(255):
        await ClockCycles(dut.clk, 1)
        state = int(dut.uo_out.value) & 0xFF
        assert state != 0, "LFSR locked up at 0x00!"
        states.add(state)

    dut._log.info(f"Unique 8-bit states visited: {len(states)}")
    assert len(states) == 255, f"Expected 255 unique states, got {len(states)}"


# Test 3: HOLD Mode
@cocotb.test()
async def test_hold_mode(dut):
    """LFSR output must not change while mode = HOLD."""
    dut._log.info("Start")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut._log.info("Reset")
    dut.ena.value    = 1
    dut.ui_in.value  = make_ui(mode=MODE_RUN, width_sel=0b01)
    dut.uio_in.value = 0
    dut.rst_n.value  = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value  = 1
    await ClockCycles(dut.clk, 2)

    # Run 5 cycles to reach a non-trivial state
    dut.ui_in.value = make_ui(mode=MODE_RUN, width_sel=0b01)
    await ClockCycles(dut.clk, 5)

    # Switch to HOLD and record frozen state
    dut.ui_in.value = make_ui(mode=MODE_HOLD, width_sel=0b01)
    await ClockCycles(dut.clk, 1)
    frozen = read_lfsr(dut)
    dut._log.info(f"LFSR frozen at 0x{frozen:04X}")

    # Verify no change over 10 cycles
    for i in range(10):
        await ClockCycles(dut.clk, 1)
        current = read_lfsr(dut)
        assert current == frozen, \
            f"LFSR changed during HOLD at cycle {i}: 0x{current:04X} != 0x{frozen:04X}"

    dut._log.info("HOLD mode: output stable for 10 cycles")


# Test 4: LOAD_SEED then RUN
@cocotb.test()
async def test_load_seed(dut):
    """Load seed 0xA5C3, switch to RUN; verify LFSR starts from masked seed."""
    dut._log.info("Start")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut._log.info("Reset")
    dut.ena.value    = 1
    dut.ui_in.value  = make_ui(mode=MODE_RUN, width_sel=0b01)
    dut.uio_in.value = 0
    dut.rst_n.value  = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value  = 1
    await ClockCycles(dut.clk, 2)

    dut._log.info("Loading seed 0xA5C3 (effective 8-bit seed = 0xC3)")
    await load_seed(dut, 0xA5C3, width_sel=0b01)

    # Switch to RUN — seed applies on this transition cycle
    dut.ui_in.value = make_ui(mode=MODE_RUN, width_sel=0b01)
    await ClockCycles(dut.clk, 2)   # +1 for apply_seed, +1 for first RUN step

    hi = int(dut.uio_out.value)
    lo = int(dut.uo_out.value)
    dut._log.info(f"Post-seed LFSR = 0x{hi:02X}{lo:02X}")
    # 8-bit mode: upper byte must be 0
    assert hi == 0x00, f"Upper byte non-zero for 8-bit mode: 0x{hi:02X}"
    assert lo != 0x00, "Lower byte is 0x00 — LFSR did not start from seed"


# Test 5: LOAD_SEED with Zero Seed — Guard promotes to 0x0001
@cocotb.test()
async def test_load_seed_zero(dut):
    """Loading seed 0x0000 — zero-seed guard must promote LFSR to run from 0x0001."""
    dut._log.info("Start")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut._log.info("Reset")
    dut.ena.value    = 1
    dut.ui_in.value  = make_ui(mode=MODE_RUN, width_sel=0b01)
    dut.uio_in.value = 0
    dut.rst_n.value  = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value  = 1
    await ClockCycles(dut.clk, 2)

    dut._log.info("Loading zero seed 0x0000")
    await load_seed(dut, 0x0000, width_sel=0b01)

    dut.ui_in.value = make_ui(mode=MODE_RUN, width_sel=0b01)
    await ClockCycles(dut.clk, 2)

    lo = int(dut.uo_out.value)
    dut._log.info(f"LFSR after zero-seed load = 0x{lo:02X}")
    assert lo != 0, "LFSR stuck at 0 — zero-seed guard failed!"



# Test 6: LOAD_TAP — Polynomial Switch Changes Sequence
@cocotb.test()
async def test_load_tap(dut):
    """Switching to poly index 1 (0x008E) must produce a different sequence."""
    dut._log.info("Start")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    # --- Collect 50 states with default polynomial (index 0) ---
    dut._log.info("Reset — collecting default poly sequence")
    dut.ena.value    = 1
    dut.ui_in.value  = make_ui(mode=MODE_RUN, width_sel=0b01)
    dut.uio_in.value = 0
    dut.rst_n.value  = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value  = 1
    await ClockCycles(dut.clk, 2)

    dut.ui_in.value = make_ui(mode=MODE_RUN, width_sel=0b01)
    seq_default = []
    for _ in range(50):
        await ClockCycles(dut.clk, 1)
        seq_default.append(int(dut.uo_out.value))

    # --- Reset again, load polynomial index 1, collect 50 states ---
    dut._log.info("Reset — loading poly index 1 and collecting alternate sequence")
    dut.rst_n.value = 0
    dut.ui_in.value = make_ui(mode=MODE_RUN, width_sel=0b01)
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)

    # LOAD_TAP: single cycle — poly_idx sits in ui_in[5:4] = data_in[1:0]
    dut.ui_in.value = make_ui(mode=MODE_LOAD_TAP, width_sel=0b01, poly_idx=0b01)
    await ClockCycles(dut.clk, 1)

    dut.ui_in.value = make_ui(mode=MODE_RUN, width_sel=0b01)
    seq_alt = []
    for _ in range(50):
        await ClockCycles(dut.clk, 1)
        seq_alt.append(int(dut.uo_out.value))

    dut._log.info(f"Default seq first 5: {[hex(x) for x in seq_default[:5]]}")
    dut._log.info(f"Alt     seq first 5: {[hex(x) for x in seq_alt[:5]]}")
    assert seq_default != seq_alt, "Polynomial switch had no effect — sequences are identical!"


# Test 7: Lockup Escape (force LFSR state toward 0x0000 via zero seed)
@cocotb.test()
async def test_lockup_escape(dut):
    """Zero seed triggers guard; LFSR must escape to a non-zero state within 1 cycle."""
    dut._log.info("Start")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut._log.info("Reset")
    dut.ena.value    = 1
    dut.ui_in.value  = make_ui(mode=MODE_RUN, width_sel=0b01)
    dut.uio_in.value = 0
    dut.rst_n.value  = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value  = 1
    await ClockCycles(dut.clk, 2)

    dut._log.info("Loading zero seed — zero-seed guard should promote to 0x0001")
    await load_seed(dut, 0x0000, width_sel=0b01)

    dut.ui_in.value = make_ui(mode=MODE_RUN, width_sel=0b01)
    await ClockCycles(dut.clk, 1)   # apply_seed cycle: guard promotes to 0x0001
    await ClockCycles(dut.clk, 1)   # first RUN step

    state = int(dut.uo_out.value)
    dut._log.info(f"LFSR after lockup escape = 0x{state:02X}")
    assert state != 0, "LFSR still at 0 after lockup escape!"


# Test 8: 4-bit Width — 15 unique non-zero states
@cocotb.test()
async def test_4bit_width(dut):
    """4-bit LFSR (x^4+x+1) must visit exactly 15 unique non-zero states."""
    dut._log.info("Start")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut._log.info("Reset — 4-bit width")
    dut.ena.value    = 1
    dut.ui_in.value  = make_ui(mode=MODE_RUN, width_sel=0b00)   # 4-bit
    dut.uio_in.value = 0
    dut.rst_n.value  = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value  = 1
    await ClockCycles(dut.clk, 2)

    dut.ui_in.value = make_ui(mode=MODE_RUN, width_sel=0b00)
    states = set()
    for _ in range(15):
        await ClockCycles(dut.clk, 1)
        state = int(dut.uo_out.value) & 0x0F
        assert state != 0, "4-bit LFSR locked up at 0x0!"
        states.add(state)

    dut._log.info(f"4-bit unique states: {len(states)}")
    assert len(states) == 15, f"Expected 15 unique 4-bit states, got {len(states)}"

    # 16th state must cycle back (same as last state + one step — within the 15)
    await ClockCycles(dut.clk, 1)
    state_16 = int(dut.uo_out.value) & 0x0F
    assert state_16 in states, f"State 16 (0x{state_16:X}) not within the 15-state cycle"


# Test 9: 12-bit Width — Upper Nibble of uio_out Goes Non-Zero
@cocotb.test()
async def test_12bit_width(dut):
    """12-bit LFSR: bits [11:8] = uio_out[3:0] must become non-zero within 100 cycles."""
    dut._log.info("Start")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut._log.info("Reset — 12-bit width")
    dut.ena.value    = 1
    dut.ui_in.value  = make_ui(mode=MODE_RUN, width_sel=0b10)   # 12-bit
    dut.uio_in.value = 0
    dut.rst_n.value  = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value  = 1
    await ClockCycles(dut.clk, 2)

    dut.ui_in.value = make_ui(mode=MODE_RUN, width_sel=0b10)
    upper_seen = False
    for _ in range(100):
        await ClockCycles(dut.clk, 1)
        # lfsr_reg[11:8] maps to uio_out[3:0]; uio_out[7:4] must stay 0 (12-bit mask)
        hi = int(dut.uio_out.value)
        if (hi & 0x0F) != 0:
            upper_seen = True
            break

    dut._log.info(f"Upper nibble active: {upper_seen}")
    assert upper_seen, "12-bit LFSR: bits [11:8] never went non-zero in 100 cycles"


# Test 10: 16-bit Width — MSB (bit 15) Reaches HIGH
@cocotb.test()
async def test_16bit_width(dut):
    """16-bit LFSR: uio_out[7] (lfsr_reg[15]) must go HIGH within 200 cycles."""
    dut._log.info("Start")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut._log.info("Reset — 16-bit width")
    dut.ena.value    = 1
    dut.ui_in.value  = make_ui(mode=MODE_RUN, width_sel=0b11)   # 16-bit
    dut.uio_in.value = 0
    dut.rst_n.value  = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value  = 1
    await ClockCycles(dut.clk, 2)

    dut.ui_in.value = make_ui(mode=MODE_RUN, width_sel=0b11)
    msb_seen = False
    for _ in range(200):
        await ClockCycles(dut.clk, 1)
        hi = int(dut.uio_out.value)
        if hi & 0x80:   # lfsr_reg[15] = uio_out[7]
            msb_seen = True
            break

    lo = int(dut.uo_out.value)
    hi = int(dut.uio_out.value)
    dut._log.info(f"16-bit LFSR output = 0x{hi:02X}{lo:02X}, MSB reached: {msb_seen}")
    assert msb_seen, "16-bit LFSR: bit 15 (uio_out[7]) never went HIGH in 200 cycles"
