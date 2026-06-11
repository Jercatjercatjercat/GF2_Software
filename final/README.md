# GF2 Logic Simulator Final Submission

This folder is self-contained. Run commands from this `final/` directory.

## Requirements

Install the packages listed in `requirements.txt` if they are not already available:

```bash
python3 -m pip install -r requirements.txt
```

On some macOS setups, `python3` may point to a system Python without `wxPython`. If that happens, use the Python from the environment where `wxPython` is installed, for example `python` in the conda base environment.

## Run the simulator

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

Run in Spanish for one launch:

```bash
LANG=es_ES.utf8 python3 logsim.py examples/example1_mixed_combinational.txt
```

If `python3` cannot import `wx`, use:

```bash
python logsim.py examples/example1_mixed_combinational.txt
```

## Suggested demonstrations

- `examples/example1_mixed_combinational.txt`: basic gates.
- `examples/example2_clocked_dtype.txt`: clocked DTYPE.
- `examples/example4_full_adder.txt`: full-adder SUM/COUT behaviour.
- `examples/example6_rc_siggen_dtype.txt`: RC and SIGGEN maintenance devices plus 3D traces.

## Run tests

```bash
python3 -m pytest -q
```

or, if your working environment uses `python` rather than `python3`:

```bash
python -m pytest -q
```

## Contents

- `logsim/`: source code and pytest tests.
- `examples/`: valid definition files and error stress tests.
- `LogicDescriptionLanguage`: final LDL specification.
- `requirements.txt`: required Python packages.
- `pytest.ini`: pytest configuration.

The individual report and contribution evidence are submitted separately outside this runnable code folder.
