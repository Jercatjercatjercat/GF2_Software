"""Test the userint module."""
import pytest

from final.logsim.devices import Devices
from final.logsim.monitors import Monitors
from final.logsim.names import Names
from final.logsim.network import Network
from final.logsim.userint import UserInterface


@pytest.fixture
def user_interface():
    """Return a user interface with a small connected network."""
    names = Names()
    devices = Devices(names)
    network = Network(names, devices)
    monitors = Monitors(names, devices, network)

    [sw1_id, data_sw_id, g1_id, i1_id] = names.lookup(
        ["SW1", "DATA_SW", "G1", "I1"]
    )
    devices.make_device(sw1_id, devices.SWITCH, 0)
    devices.make_device(data_sw_id, devices.SWITCH, 1)
    devices.make_device(g1_id, devices.AND, 1)
    network.make_connection(sw1_id, None, g1_id, i1_id)

    userint = UserInterface(names, devices, network, monitors)
    return userint, names, devices, network, monitors


def set_line(userint, line):
    """Set the current command line on a UserInterface."""
    userint.line = line
    userint.cursor = 0
    userint.character = ""


def test_read_string_accepts_underscores(user_interface):
    """Test if command names may contain underscores."""
    userint, names, devices, network, monitors = user_interface
    set_line(userint, "  DATA_SW")

    assert userint.read_string() == "DATA_SW"


def test_read_signal_name_accepts_dotted_output(user_interface):
    """Test if dotted signal names are parsed into device and port IDs."""
    userint, names, devices, network, monitors = user_interface
    [d1_id, q_id] = names.lookup(["D1", "Q"])
    set_line(userint, "D1.Q")

    assert userint.read_signal_name() == [d1_id, q_id]


def test_switch_command_sets_switch(user_interface, capsys):
    """Test if the switch command changes a switch state."""
    userint, names, devices, network, monitors = user_interface
    [sw1_id] = names.lookup(["SW1"])
    set_line(userint, "SW1 1")

    userint.switch_command()

    assert devices.get_device(sw1_id).switch_state == devices.HIGH
    assert "Successfully set switch." in capsys.readouterr().out


def test_monitor_command_adds_monitor(user_interface, capsys):
    """Test if the monitor command adds an output monitor."""
    userint, names, devices, network, monitors = user_interface
    [g1_id] = names.lookup(["G1"])
    set_line(userint, "G1")

    userint.monitor_command()

    assert (g1_id, None) in monitors.monitors_dictionary
    assert "Successfully made monitor." in capsys.readouterr().out


def test_monitor_command_adds_dotted_monitor(user_interface, capsys):
    """Test if the monitor command can add a DTYPE output monitor."""
    userint, names, devices, network, monitors = user_interface
    [d1_id, q_id] = names.lookup(["D1", "Q"])
    devices.make_device(d1_id, devices.D_TYPE)
    set_line(userint, "D1.Q")

    userint.monitor_command()

    assert (d1_id, q_id) in monitors.monitors_dictionary
    assert "Successfully made monitor." in capsys.readouterr().out


def test_zap_command_removes_monitor(user_interface, capsys):
    """Test if the zap command removes an output monitor."""
    userint, names, devices, network, monitors = user_interface
    [g1_id] = names.lookup(["G1"])
    monitors.make_monitor(g1_id, None)
    set_line(userint, "G1")

    userint.zap_command()

    assert (g1_id, None) not in monitors.monitors_dictionary
    assert "Successfully zapped monitor" in capsys.readouterr().out


def test_run_command_runs_from_cold_start(user_interface, capsys):
    """Test if run command executes the network for N cycles."""
    userint, names, devices, network, monitors = user_interface
    [g1_id] = names.lookup(["G1"])
    monitors.make_monitor(g1_id, None)
    set_line(userint, "2")

    userint.run_command()

    assert userint.cycles_completed == 2
    assert len(monitors.monitors_dictionary[(g1_id, None)]) == 2
    assert "Running for 2 cycles" in capsys.readouterr().out


def test_continue_command_requires_previous_run(user_interface, capsys):
    """Test if continue reports an error before any run."""
    userint, names, devices, network, monitors = user_interface
    set_line(userint, "2")

    userint.continue_command()

    assert "Nothing to continue" in capsys.readouterr().out


def test_continue_command_continues_after_run(user_interface, capsys):
    """Test if continue advances after a previous run."""
    userint, names, devices, network, monitors = user_interface
    [g1_id] = names.lookup(["G1"])
    monitors.make_monitor(g1_id, None)
    set_line(userint, "1")
    userint.run_command()
    set_line(userint, "2")

    userint.continue_command()

    assert userint.cycles_completed == 3
    assert len(monitors.monitors_dictionary[(g1_id, None)]) == 3
    assert "Continuing for 2 cycles" in capsys.readouterr().out
