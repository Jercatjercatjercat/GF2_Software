# Error stress tests

These definition files are deliberately invalid. Use them to demonstrate improved parser error handling in both the terminal and the GUI pop-up.

Run terminal-only checks with:

```bash
python3 logsim.py -c examples/error_stress_tests/01_missing_device_name.txt
```

Run GUI checks with:

```bash
python3 logsim.py examples/error_stress_tests/01_missing_device_name.txt
```

## Files

- `01_missing_device_name.txt`: tests `expected device name before ':'` and caret placement.
- `02_numeric_device_name.txt`: tests device names starting with a digit.
- `03_undefined_devices.txt`: tests undefined source, undefined destination, and undefined monitor device names.
- `04_unconnected_inputs.txt`: tests named unconnected inputs, e.g. `WIDE_GATE.I2` and `WIDE_GATE.I4`.
- `05_duplicate_input_connection.txt`: tests duplicate connection to the same input.
- `06_invalid_ports_and_signal_direction.txt`: tests invalid input port, input used as source, and output used as destination.
- `07_missing_monitor_comma.txt`: tests local syntax recovery in a monitor list.
- `08_bad_dtype_output.txt`: tests ambiguous DTYPE output requiring `.Q` or `.QBAR`.
