"""Control logic shared by the graphical user interface.

This module keeps simulator actions separate from wxPython widgets.  The GUI
can call these methods directly, and pytest can exercise the same behaviour
without needing to open a window.
"""

from __future__ import annotations


class GuiController:
    """Wrap simulator operations needed by the graphical interface.

    Every method returns plain data (usually a ``(success, message)``
    tuple or a list of display strings) so the GUI stays a thin layer
    over the simulator and the behaviour is testable without wx.

    Parameters
    ----------
    names: instance of the names.Names class.
    devices: instance of the devices.Devices class.
    network: instance of the network.Network class.
    monitors: instance of the monitors.Monitors class.

    Public methods
    --------------
    run_from_start(self, cycles): Cold-starts and runs the network.

    continue_simulation(self, cycles): Runs further simulation cycles.

    step_simulation(self): Runs exactly one simulation cycle.

    set_switch(self, switch_name, switch_state): Sets a switch level.

    add_monitor(self, signal_name): Starts monitoring a signal.

    remove_monitor(self, signal_name): Stops monitoring a signal.

    list_switches(self): Returns the names of all switches.

    list_monitored_signals(self): Returns monitored signal names.

    list_unmonitored_signals(self): Returns unmonitored signal names.

    list_device_readings(self): Returns display rows of output levels.

    get_existing_signal_ids(self, signal_name): Resolves a signal name.
    """

    def __init__(self, names, devices, network, monitors):
        """Store simulator objects and initialise run state."""
        self.names = names
        self.devices = devices
        self.network = network
        self.monitors = monitors
        self.cycles_completed = 0

    def run_from_start(self, cycles: int) -> tuple[bool, str]:
        """Cold-start the network and run for the requested cycles."""
        cycles = self._validate_cycles(cycles)
        if cycles is None:
            return False, "Number of cycles must be zero or greater."

        self.cycles_completed = 0
        self.monitors.reset_monitors()
        self.devices.cold_startup()

        success, message, cycles_run = self._run_network(cycles)
        self.cycles_completed += cycles_run
        if success:
            return True, "Running for " + str(cycles) + " cycles."
        return False, message

    def continue_simulation(self, cycles: int) -> tuple[bool, str]:
        """Continue a network that has already been run."""
        cycles = self._validate_cycles(cycles)
        if cycles is None:
            return False, "Number of cycles must be zero or greater."
        if self.cycles_completed == 0:
            return False, "Nothing to continue. Run first."

        success, message, cycles_run = self._run_network(cycles)
        self.cycles_completed += cycles_run
        if success:
            return (
                True,
                "Continuing for "
                + str(cycles)
                + " cycles. Total: "
                + str(self.cycles_completed)
                + "."
            )
        return False, message

    def step_simulation(self) -> tuple[bool, str]:
        """Run exactly one cycle, cold-starting if necessary."""
        if self.cycles_completed == 0:
            return self.run_from_start(1)

        success, message, cycles_run = self._run_network(1)
        self.cycles_completed += cycles_run
        if success:
            return (
                True,
                "Advanced one cycle. Total: "
                + str(self.cycles_completed)
                + "."
            )
        return False, message

    def _run_network(self, cycles):
        """Run the network for a number of cycles.

        Return a tuple containing success, message, and the number of cycles
        completed before any error.
        """
        cycles_run = 0
        for _ in range(cycles):
            if not self.network.execute_network():
                return False, "Error! Network oscillating.", cycles_run
            self.monitors.record_signals()
            cycles_run += 1
        return True, "", cycles_run

    def set_switch(self, switch_name: str,
                   switch_state: int | str) -> tuple[bool, str]:
        """Set the named switch to 0 or 1."""
        switch_id = self.names.query(switch_name)
        if switch_id is None:
            return False, "Unknown switch: " + switch_name

        try:
            switch_state = int(switch_state)
        except (TypeError, ValueError):
            return False, "Switch value must be 0 or 1."

        if switch_state not in [self.devices.LOW, self.devices.HIGH]:
            return False, "Switch value must be 0 or 1."

        if self.devices.set_switch(switch_id, switch_state):
            return (
                True,
                "Set switch " + switch_name + " to " + str(switch_state)
                + "."
            )

        return False, switch_name + " is not a switch."

    def add_monitor(self, signal_name: str) -> tuple[bool, str]:
        """Add a monitor point for the selected output signal."""
        signal_ids = self.get_existing_signal_ids(signal_name)
        if signal_ids is None:
            return False, "Unknown signal: " + signal_name

        device_id, output_id = signal_ids
        error = self.monitors.make_monitor(
            device_id, output_id, self.cycles_completed
        )

        if error == self.monitors.NO_ERROR:
            return True, "Added monitor " + signal_name + "."
        if error == self.monitors.MONITOR_PRESENT:
            return False, "Monitor already present: " + signal_name
        if error == self.monitors.NOT_OUTPUT:
            return False, signal_name + " is not an output signal."
        if error == self.network.DEVICE_ABSENT:
            return False, "Unknown device in signal: " + signal_name
        return False, "Could not add monitor " + signal_name + "."

    def remove_monitor(self, signal_name: str) -> tuple[bool, str]:
        """Remove a monitor point for the selected output signal."""
        signal_ids = self.get_existing_signal_ids(signal_name)
        if signal_ids is None:
            return False, "Unknown signal: " + signal_name

        device_id, output_id = signal_ids
        if self.monitors.remove_monitor(device_id, output_id):
            return True, "Removed monitor " + signal_name + "."
        return False, "Monitor is not present: " + signal_name

    def list_switches(self) -> list[str]:
        """Return switch device names in definition order."""
        switch_names = []
        for device_id in self.devices.find_devices(self.devices.SWITCH):
            switch_names.append(self.names.get_name_string(device_id))
        return switch_names

    def list_monitored_signals(self) -> list[str]:
        """Return signal names that are currently monitored."""
        monitored, _ = self.monitors.get_signal_names()
        return monitored

    def list_unmonitored_signals(self) -> list[str]:
        """Return output signal names that are not currently monitored."""
        _, unmonitored = self.monitors.get_signal_names()
        return unmonitored

    def list_device_readings(self) -> list[str]:
        """Return readable current output values for all devices."""
        readings = []
        for device in self.devices.devices_list:
            device_name = self.names.get_name_string(device.device_id)
            if device.device_kind == self.devices.SWITCH:
                readings.append(
                    device_name + " = "
                    + self._signal_to_text(device.switch_state)
                )
                continue

            for output_id in self._sorted_output_ids(device.outputs):
                signal_name = self.devices.get_signal_name(
                    device.device_id, output_id
                )
                readings.append(
                    signal_name + " = "
                    + self._signal_to_text(device.outputs[output_id])
                )
        return readings

    def _sorted_output_ids(self, outputs):
        """Return output port IDs in a stable display order."""
        return sorted(outputs, key=self._output_sort_name)

    def _output_sort_name(self, output_id):
        """Return the display name used to sort an output port."""
        if output_id is None:
            return ""
        return str(self.names.get_name_string(output_id))

    def _signal_to_text(self, signal):
        """Return a short display string for a simulator signal value."""
        if signal == self.devices.LOW:
            return "0"
        if signal == self.devices.HIGH:
            return "1"
        if signal == self.devices.RISING:
            return "R"
        if signal == self.devices.FALLING:
            return "F"
        if signal == self.devices.BLANK:
            return "-"
        return "?"

    def get_existing_signal_ids(self,
                                signal_name: str) -> tuple | None:
        """Return IDs for an existing signal name, without adding names."""
        if not isinstance(signal_name, str) or signal_name == "":
            return None

        signal_parts = signal_name.split(".")
        if len(signal_parts) not in [1, 2]:
            return None
        if "" in signal_parts:
            return None

        device_id = self.names.query(signal_parts[0])
        if device_id is None:
            return None

        output_id = None
        if len(signal_parts) == 2:
            output_id = self.names.query(signal_parts[1])
            if output_id is None:
                return None

        return device_id, output_id

    def _validate_cycles(self, cycles):
        """Return a non-negative cycle count, or None if invalid."""
        try:
            cycles = int(cycles)
        except (TypeError, ValueError):
            return None

        if cycles < 0:
            return None
        return cycles
