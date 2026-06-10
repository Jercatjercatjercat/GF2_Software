"""Test GUI controller behaviour without opening a wxPython window."""

import pytest

from final.logsim.devices import Devices
from final.logsim.gui_controller import GuiController
from final.logsim.monitors import Monitors
from final.logsim.names import Names
from final.logsim.network import Network


@pytest.fixture
def controller():
    """Return a GUI controller with a small connected network."""
    names = Names()
    devices = Devices(names)
    network = Network(names, devices)
    monitors = Monitors(names, devices, network)

    [sw1_id, sw2_id, gate_id, i1_id, i2_id] = names.lookup(
        ["SW1", "SW2", "G1", "I1", "I2"]
    )
    devices.make_device(sw1_id, devices.SWITCH, 0)
    devices.make_device(sw2_id, devices.SWITCH, 1)
    devices.make_device(gate_id, devices.AND, 2)
    network.make_connection(sw1_id, None, gate_id, i1_id)
    network.make_connection(sw2_id, None, gate_id, i2_id)
    monitors.make_monitor(gate_id, None)

    return GuiController(names, devices, network, monitors)


def test_run_from_start_records_requested_cycles(controller):
    """Test if a cold run records monitor traces."""
    success, message = controller.run_from_start(3)

    assert success
    assert message == "Running for 3 cycles."
    assert controller.cycles_completed == 3
    assert len(controller.monitors.monitors_dictionary[(
        controller.names.query("G1"), None
    )]) == 3


def test_continue_requires_previous_run(controller):
    """Test if continue reports an error before the first run."""
    success, message = controller.continue_simulation(2)

    assert not success
    assert message == "Nothing to continue. Run first."


def test_continue_appends_trace_after_run(controller):
    """Test if continuing adds cycles without clearing traces."""
    controller.run_from_start(2)
    success, message = controller.continue_simulation(3)

    assert success
    assert message == "Continuing for 3 cycles. Total: 5."
    assert controller.cycles_completed == 5
    assert len(controller.monitors.monitors_dictionary[(
        controller.names.query("G1"), None
    )]) == 5


def test_step_simulation_cold_starts_then_advances(controller):
    """Test if stepping works before and after an initial run."""
    success, message = controller.step_simulation()

    assert success
    assert message == "Running for 1 cycles."
    assert controller.cycles_completed == 1

    success, message = controller.step_simulation()

    assert success
    assert message == "Advanced one cycle. Total: 2."
    assert controller.cycles_completed == 2


def test_set_switch_changes_switch_state(controller):
    """Test if a switch value can be changed by name."""
    success, message = controller.set_switch("SW1", 1)

    assert success
    assert message == "Set switch SW1 to 1."
    assert controller.devices.get_device(
        controller.names.query("SW1")
    ).switch_state == controller.devices.HIGH


def test_set_switch_rejects_non_switch(controller):
    """Test if non-switch devices cannot be changed as switches."""
    success, message = controller.set_switch("G1", 1)

    assert not success
    assert message == "G1 is not a switch."


def test_add_monitor_mid_run_pads_blank_cycles(controller):
    """Test if monitors added after running preserve time alignment."""
    controller.run_from_start(4)

    success, message = controller.add_monitor("SW1")

    assert success
    assert message == "Added monitor SW1."
    assert controller.monitors.monitors_dictionary[(
        controller.names.query("SW1"), None
    )] == [controller.devices.BLANK] * 4


def test_add_monitor_rejects_duplicate(controller):
    """Test if a duplicate monitor is rejected."""
    success, message = controller.add_monitor("G1")

    assert not success
    assert message == "Monitor already present: G1"


def test_remove_monitor_removes_selected_signal(controller):
    """Test if monitor removal updates the monitor dictionary."""
    success, message = controller.remove_monitor("G1")

    assert success
    assert message == "Removed monitor G1."
    assert (controller.names.query("G1"), None) not in (
        controller.monitors.monitors_dictionary
    )


def test_readded_monitor_preserves_hidden_trace(controller):
    """Test if a removed monitor keeps recording while hidden."""
    g1_id = controller.names.query("G1")

    controller.run_from_start(2)
    success, message = controller.remove_monitor("G1")
    assert success
    assert message == "Removed monitor G1."

    controller.set_switch("SW1", 1)
    controller.continue_simulation(2)
    success, message = controller.add_monitor("G1")

    assert success
    assert message == "Added monitor G1."
    assert controller.monitors.monitors_dictionary[(g1_id, None)] == [
        controller.devices.LOW, controller.devices.LOW,
        controller.devices.HIGH, controller.devices.HIGH
    ]


def test_monitor_lists_split_current_and_available(controller):
    """Test if monitored and unmonitored output lists are correct."""
    assert controller.list_monitored_signals() == ["G1"]
    assert controller.list_unmonitored_signals() == ["SW1", "SW2"]


def test_unknown_signal_lookup_does_not_mutate_names(controller):
    """Test if invalid GUI input does not add names to the name table."""
    before = list(controller.names.names)

    success, message = controller.add_monitor("NO_SUCH_SIGNAL")

    assert not success
    assert message == "Unknown signal: NO_SUCH_SIGNAL"
    assert controller.names.names == before


def test_list_device_readings_shows_switches_and_gate_outputs(controller):
    """Test if GUI readings list current switch and gate values."""
    controller.run_from_start(1)

    readings = controller.list_device_readings()

    assert "SW1 = 0" in readings
    assert "SW2 = 1" in readings
    assert "G1 = 0" in readings


def test_list_device_readings_updates_after_switch_change(controller):
    """Test if readings reflect changed switch state and gate output."""
    controller.set_switch("SW1", 1)
    controller.run_from_start(1)

    readings = controller.list_device_readings()

    assert "SW1 = 1" in readings
    assert "G1 = 1" in readings
