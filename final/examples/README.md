# Example definition files

Run these commands from the `final/` directory.

These files use the current revised grammar:

- `SWITCH(0)` or `SWITCH(1)`
- `CLOCK(4)`
- `RC(3)`
- `SIGGEN(0, 1, 1, 0)`
- `AND(2)`, `NAND(2)`, `OR(2)`, `NOR(2)`
- `XOR`
- `DTYPE`

## Choosing the interface

Text interface:

```bash
python3 logsim.py -c examples/example1_mixed_combinational.txt
```

Normal graphical interface:

```bash
python3 logsim.py examples/example1_mixed_combinational.txt
```

3D trace graphical interface:

```bash
python3 logsim.py --3d examples/example6_rc_siggen_dtype.txt
```

In the 3D GUI, run or continue the simulation first so traces exist, then use `View > 3D art style` in the side panel to choose `Modern` or `Template`. Drag the oscilloscope with the mouse to rotate it, hold Shift while dragging to pan, and use the mouse wheel over the oscilloscope to zoom.

If `python3` cannot import `wx`, use the Python executable from the environment where `wxPython` is installed:

```bash
python logsim.py examples/example1_mixed_combinational.txt
```

## Example 1: mixed combinational logic

```bash
python3 logsim.py -c examples/example1_mixed_combinational.txt
python3 logsim.py examples/example1_mixed_combinational.txt
```

At the text prompt, try:

```text
h
r 10
s A 1
c 5
m G_NOR
z G_NOR
q
```

## Example 2: clocked DTYPE

```bash
python3 logsim.py -c examples/example2_clocked_dtype.txt
python3 logsim.py examples/example2_clocked_dtype.txt
```

At the text prompt, try:

```text
r 10
s DATA_SW 0
c 5
m FF1.Q
m FF1.QBAR
z FF1.QBAR
q
```

## Example 3: flip-flop switch

```bash
python3 logsim.py -c examples/example3_flip_flop_switch.txt
python3 logsim.py examples/example3_flip_flop_switch.txt
```

At the text prompt, try:

```text
r 10
c 5
m FF_SWITCH.Q
m FF_SWITCH.QBAR
z FF_SWITCH.QBAR
q
```

## Example 4: one-bit full adder

```bash
python3 logsim.py -c examples/example4_full_adder.txt
python3 logsim.py examples/example4_full_adder.txt
```

At the text prompt, try:

```text
r 1
s A 1
c 1
s B 1
c 1
s CIN 1
c 1
q
```

Expected full-adder behaviour:

```text
A B CIN | SUM COUT
0 0 0   | 0   0
1 0 0   | 1   0
1 1 0   | 0   1
1 1 1   | 1   1
```

## Example 5: GUI stress test with multi-input gates

```bash
python3 logsim.py examples/example5_gui_stress_multi_input.txt
```

This file uses multi-input gates, clocks, a DTYPE, long device names, many connections, and many monitors. In the GUI, resize the window and add/remove monitors such as `MEMORY_CELL_LONG_NAME.Q`, `FINAL_OR_OUTPUT`, and `WIDE_AND_SIX_INPUTS`.

## Example 6: RC reset with SIGGEN clock

```bash
python3 logsim.py -c examples/example6_rc_siggen_dtype.txt
python3 logsim.py examples/example6_rc_siggen_dtype.txt
python3 logsim.py --3d examples/example6_rc_siggen_dtype.txt
```

This file uses `RC(2)` to briefly clear a DTYPE on power-up, and `SIGGEN(0, 1, 0, 1)` to provide a repeating clock-like waveform.

At the text prompt, try:

```text
r 8
c 8
m FF1.Q
m FF1.QBAR
q
```

## Automated checks

```bash
python3 -m pytest -q
```
