# Example definition files

These files use the current revised grammar:

- `SWITCH(0)` or `SWITCH(1)`
- `CLOCK(4)`
- `RC(3)`
- `SIGGEN(0, 1, 1, 0)`
- `AND(2)`, `NAND(2)`, `OR(2)`, `NOR(2)`
- `XOR`
- `DTYPE`

## Choosing the interface

Use `-c` for the text/command-line interface:

```bash
python3 logsim/logsim.py -c examples/example1_mixed_combinational.txt
```

Omit `-c` for the graphical interface:

```bash
python3 logsim/logsim.py examples/example1_mixed_combinational.txt
```

If `python3` cannot import `wx`, use the Python executable from the conda environment where `wxPython` is installed, for example:

```bash
python logsim/logsim.py examples/example1_mixed_combinational.txt
```

## Selecting the GUI language

The GUI language can be changed while the simulator is running:

```text
Settings > Language
```

Available languages are English, Spanish, Arabic, French, and German.

You can also choose the startup language for one launch by setting `LANG` before the command:

```bash
LANG=es_ES.utf8 python3 logsim/logsim.py examples/example1_mixed_combinational.txt
LANG=fr_FR.utf8 python3 logsim/logsim.py examples/example1_mixed_combinational.txt
LANG=de_DE.utf8 python3 logsim/logsim.py examples/example1_mixed_combinational.txt
LANG=ar_SA.utf8 python3 logsim/logsim.py examples/example1_mixed_combinational.txt
LANG=en_GB.utf8 python3 logsim/logsim.py examples/example1_mixed_combinational.txt
```

On PowerShell, set `LANG` first, then run the simulator:

```powershell
$env:LANG = "es_ES.utf8"
python logsim\logsim.py examples\example1_mixed_combinational.txt
Remove-Item Env:LANG
```

## Example 1: mixed combinational logic

Text interface:

```bash
python3 logsim/logsim.py -c examples/example1_mixed_combinational.txt
```

Graphical interface:

```bash
python3 logsim/logsim.py examples/example1_mixed_combinational.txt
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

Text interface:

```bash
python3 logsim/logsim.py -c examples/example2_clocked_dtype.txt
```

Graphical interface:

```bash
python3 logsim/logsim.py examples/example2_clocked_dtype.txt
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

Text interface:

```bash
python3 logsim/logsim.py -c examples/example3_flip_flop_switch.txt
```

Graphical interface:

```bash
python3 logsim/logsim.py examples/example3_flip_flop_switch.txt
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

Text interface:

```bash
python3 logsim/logsim.py -c examples/example4_full_adder.txt
```

Graphical interface:

```bash
python3 logsim/logsim.py examples/example4_full_adder.txt
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

Text interface:

```bash
python3 logsim/logsim.py -c examples/example5_gui_stress_multi_input.txt
```

Graphical interface:

```bash
python3 logsim/logsim.py examples/example5_gui_stress_multi_input.txt
```

This file is intended for GUI stress testing. It uses a six-input `AND`, several five-input gates, two clocks, a DTYPE, long device names, many connections, and many monitors.

At the text prompt, try:

```text
r 20
s SW_A 1
s SW_C 1
s SW_E 1
c 10
s RESET_MAIN 1
c 10
q
```

In the GUI, use the run/continue controls, resize the window, and add/remove monitors such as `MEMORY_CELL_LONG_NAME.Q`, `FINAL_OR_OUTPUT`, and `WIDE_AND_SIX_INPUTS`.

## Example 6: RC reset with SIGGEN clock

Text interface:

```bash
python3 logsim/logsim.py -c examples/example6_rc_siggen_dtype.txt
```

Graphical interface:

```bash
python3 logsim/logsim.py examples/example6_rc_siggen_dtype.txt
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

Run:

```bash
pytest -q logsim
```
