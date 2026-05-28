# Example definition files

These files use the current revised grammar:

- `SWITCH(0)` or `SWITCH(1)`
- `CLOCK(4)`
- `AND(2)`, `NAND(2)`, `OR(2)`, `NOR(2)`
- `XOR`
- `DTYPE`

## Parser and text-interface smoke tests

From the repository root, run:

```bash
python3 logsim/logsim.py -c examples/example1_mixed_combinational.txt
```

At the prompt, try:

```text
h
r 10
s A 1
c 5
m G_NOR
z G_NOR
q
```

Then try the DTYPE example:

```bash
python3 logsim/logsim.py -c examples/example2_clocked_dtype.txt
```

At the prompt, try:

```text
r 10
s DATA_SW 0
c 5
m FF1.Q
m FF1.QBAR
z FF1.QBAR
q
```

## Automated checks

Run:

```bash
pytest -q logsim
```
