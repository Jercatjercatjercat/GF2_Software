"""Test the parse module."""
from pathlib import Path

import pytest

from devices import Devices
from monitors import Monitors
from names import Names
from network import Network
from parse import Parser
from scanner import Scanner


@pytest.fixture
def parser_parts():
    """Return fresh parser dependencies."""
    names = Names()
    devices = Devices(names)
    network = Network(names, devices)
    monitors = Monitors(names, devices, network)
    return names, devices, network, monitors


def make_parser(tmp_path, text):
    """Create a parser for text in a temporary definition file."""
    path = tmp_path / "definition.txt"
    path.write_text(text, encoding="utf-8")
    names = Names()
    devices = Devices(names)
    network = Network(names, devices)
    monitors = Monitors(names, devices, network)
    scanner = Scanner(path, names)
    parser = Parser(names, devices, network, monitors, scanner)
    return parser, names, devices, network, monitors


def make_parser_from_path(path):
    """Create a parser for an existing definition file."""
    names = Names()
    devices = Devices(names)
    network = Network(names, devices)
    monitors = Monitors(names, devices, network)
    scanner = Scanner(path, names)
    parser = Parser(names, devices, network, monitors, scanner)
    return parser, names, devices, network, monitors


@pytest.mark.parametrize("example_path", [
    Path("examples/example1_mixed_combinational.txt"),
    Path("examples/example2_clocked_dtype.txt"),
    Path("examples/example3_flip_flop_switch.txt"),
])
def test_parse_example_files(example_path):
    """Test if the checked-in example definition files parse successfully."""
    parser, names, devices, network, monitors = make_parser_from_path(
        example_path
    )

    assert parser.parse_network()


def test_example3_flip_flop_switch_behaviour():
    """Test if example3 is wired as a toggling DTYPE switch."""
    parser, names, devices, network, monitors = make_parser_from_path(
        Path("examples/example3_flip_flop_switch.txt")
    )

    assert parser.parse_network()

    [ff_id, q_id, qbar_id, data_id] = names.lookup(
        ["FF_SWITCH", "Q", "QBAR", "DATA"]
    )

    assert devices.get_device(ff_id).device_kind == devices.D_TYPE
    assert network.get_connected_output(ff_id, data_id) == (ff_id, qbar_id)
    assert (ff_id, q_id) in monitors.monitors_dictionary
    assert (ff_id, qbar_id) in monitors.monitors_dictionary

    for _ in range(20):
        assert network.execute_network()
        monitors.record_signals()

    q_trace = monitors.monitors_dictionary[(ff_id, q_id)]
    qbar_trace = monitors.monitors_dictionary[(ff_id, qbar_id)]
    settled_pairs = [
        (q, qbar) for q, qbar in zip(q_trace, qbar_trace)
        if q in [devices.LOW, devices.HIGH]
        and qbar in [devices.LOW, devices.HIGH]
    ]

    assert settled_pairs
    assert all(qbar == network.invert_signal(q) for q, qbar in settled_pairs)


def test_parse_valid_cross_coupled_nand_network(tmp_path):
    """Test if parser builds a valid combinational network."""
    parser, names, devices, network, monitors = make_parser(
        tmp_path,
        """DEVICES {
            SW1 : SWITCH(0);
            SW2 : SWITCH(1);
            G1 : NAND(2);
            G2 : NAND(2);
        }
        CONNECT {
            SW1 -> G1.I1;
            SW2 -> G2.I2;
            G1 -> G2.I1;
            G2 -> G1.I2;
        }
        MONITOR { G1, G2 };
        END;
        """,
    )

    assert parser.parse_network()
    [sw1_id, sw2_id, g1_id, g2_id, i1_id, i2_id] = names.lookup(
        ["SW1", "SW2", "G1", "G2", "I1", "I2"]
    )
    assert devices.get_device(sw1_id).device_kind == devices.SWITCH
    assert devices.get_device(g1_id).device_kind == devices.NAND
    assert network.get_connected_output(g1_id, i1_id) == (sw1_id, None)
    assert network.get_connected_output(g1_id, i2_id) == (g2_id, None)
    assert (g1_id, None) in monitors.monitors_dictionary
    assert (g2_id, None) in monitors.monitors_dictionary


def test_parse_valid_dtype_network(tmp_path):
    """Test if parser builds a network containing a DTYPE."""
    parser, names, devices, network, monitors = make_parser(
        tmp_path,
        """DEVICES {
            CLK1 : CLOCK(4);
            DATA_SW : SWITCH(1);
            SET_SW : SWITCH(0);
            CLEAR_SW : SWITCH(0);
            D1 : DTYPE;
            G1 : AND(2);
        }
        CONNECT {
            DATA_SW -> D1.DATA;
            CLK1 -> D1.CLK;
            SET_SW -> D1.SET;
            CLEAR_SW -> D1.CLEAR;
            D1.Q -> G1.I1;
            D1.QBAR -> G1.I2;
        }
        MONITOR { CLK1, D1.Q, D1.QBAR, G1 };
        END;
        """,
    )

    assert parser.parse_network()
    [d1_id, q_id, qbar_id] = names.lookup(["D1", "Q", "QBAR"])
    assert devices.get_device(d1_id).device_kind == devices.D_TYPE
    assert (d1_id, q_id) in monitors.monitors_dictionary
    assert (d1_id, qbar_id) in monitors.monitors_dictionary


def test_parse_rejects_empty_devices_section(tmp_path):
    """Test if parser rejects a DEVICES section with no devices."""
    parser, names, devices, network, monitors = make_parser(
        tmp_path,
        """DEVICES {
        }
        CONNECT {
        }
        MONITOR {
        };
        END;
        """,
    )

    assert not parser.parse_network()


def test_parse_rejects_duplicate_device(tmp_path):
    """Test if parser reports duplicate device declarations."""
    parser, names, devices, network, monitors = make_parser(
        tmp_path,
        """DEVICES {
            SW1 : SWITCH(0);
            SW1 : SWITCH(1);
        }
        CONNECT {
        }
        MONITOR {
        };
        END;
        """,
    )

    assert not parser.parse_network()


def test_parse_rejects_keyword_as_port_name_mismatch(tmp_path):
    """Test if parser rejects invalid input ports by syntax."""
    parser, names, devices, network, monitors = make_parser(
        tmp_path,
        """DEVICES {
            SW1 : SWITCH(0);
            G1 : NAND(1);
        }
        CONNECT {
            SW1 -> G1.Q;
        }
        MONITOR { G1 };
        END;
        """,
    )

    assert not parser.parse_network()


def test_parse_rejects_unconnected_input(tmp_path):
    """Test if parser rejects networks with unconnected inputs."""
    parser, names, devices, network, monitors = make_parser(
        tmp_path,
        """DEVICES {
            SW1 : SWITCH(0);
            G1 : NAND(2);
        }
        CONNECT {
            SW1 -> G1.I1;
        }
        MONITOR { G1 };
        END;
        """,
    )

    assert not parser.parse_network()


def test_parse_rejects_duplicate_monitor(tmp_path):
    """Test if parser rejects duplicate monitor declarations."""
    parser, names, devices, network, monitors = make_parser(
        tmp_path,
        """DEVICES {
            SW1 : SWITCH(0);
        }
        CONNECT {
        }
        MONITOR { SW1, SW1 };
        END;
        """,
    )

    assert not parser.parse_network()


def test_parse_rejects_ambiguous_dtype_output(tmp_path):
    """Test if parser rejects bare DTYPE output references."""
    parser, names, devices, network, monitors = make_parser(
        tmp_path,
        """DEVICES {
            D1 : DTYPE;
            G1 : AND(1);
            CLK1 : CLOCK(1);
            S1 : SWITCH(0);
        }
        CONNECT {
            CLK1 -> D1.CLK;
            S1 -> D1.DATA;
            S1 -> D1.SET;
            S1 -> D1.CLEAR;
            D1 -> G1.I1;
        }
        MONITOR { G1 };
        END;
        """,
    )

    assert not parser.parse_network()


def test_parse_rejects_gate_input_count_outside_range(tmp_path):
    """Test if parser rejects gates with too many inputs."""
    parser, names, devices, network, monitors = make_parser(
        tmp_path,
        """DEVICES {
            SW1 : SWITCH(0);
            G1 : AND(17);
        }
        CONNECT {
            SW1 -> G1.I1;
        }
        MONITOR { G1 };
        END;
        """,
    )

    assert not parser.parse_network()


def test_parse_rejects_undefined_device_in_connection(tmp_path):
    """Test if parser rejects connections using undeclared devices."""
    parser, names, devices, network, monitors = make_parser(
        tmp_path,
        """DEVICES {
            SW1 : SWITCH(0);
            G1 : AND(1);
        }
        CONNECT {
            SW2 -> G1.I1;
        }
        MONITOR { G1 };
        END;
        """,
    )

    assert not parser.parse_network()


def test_parse_rejects_undefined_device_in_monitor(tmp_path):
    """Test if parser rejects monitors using undeclared devices."""
    parser, names, devices, network, monitors = make_parser(
        tmp_path,
        """DEVICES {
            SW1 : SWITCH(0);
        }
        CONNECT {
        }
        MONITOR { SW2 };
        END;
        """,
    )

    assert not parser.parse_network()


def test_parse_rejects_input_port_incompatible_with_device(tmp_path):
    """Test if parser rejects ports beyond a gate's declared input count."""
    parser, names, devices, network, monitors = make_parser(
        tmp_path,
        """DEVICES {
            SW1 : SWITCH(0);
            SW2 : SWITCH(1);
            G1 : AND(2);
        }
        CONNECT {
            SW1 -> G1.I1;
            SW2 -> G1.I3;
        }
        MONITOR { G1 };
        END;
        """,
    )

    assert not parser.parse_network()


def test_parse_rejects_output_port_incompatible_with_device(tmp_path):
    """Test if parser rejects dotted outputs on non-DTYPE devices."""
    parser, names, devices, network, monitors = make_parser(
        tmp_path,
        """DEVICES {
            SW1 : SWITCH(0);
            G1 : AND(1);
            G2 : AND(1);
        }
        CONNECT {
            SW1 -> G1.I1;
            G1.Q -> G2.I1;
        }
        MONITOR { G2 };
        END;
        """,
    )

    assert not parser.parse_network()


def test_parse_rejects_connection_from_non_output_signal(tmp_path):
    """Test if parser rejects input signals as connection sources."""
    parser, names, devices, network, monitors = make_parser(
        tmp_path,
        """DEVICES {
            SW1 : SWITCH(0);
            SW2 : SWITCH(1);
            G1 : AND(2);
            G2 : AND(1);
        }
        CONNECT {
            SW1 -> G1.I1;
            SW2 -> G1.I2;
            G1.I1 -> G2.I1;
        }
        MONITOR { G2 };
        END;
        """,
    )

    assert not parser.parse_network()


def test_parse_rejects_connection_to_non_input_signal(tmp_path):
    """Test if parser rejects output signals as connection destinations."""
    parser, names, devices, network, monitors = make_parser(
        tmp_path,
        """DEVICES {
            SW1 : SWITCH(0);
            SW2 : SWITCH(1);
            G1 : AND(1);
        }
        CONNECT {
            SW1 -> G1.I1;
            SW2 -> G1;
        }
        MONITOR { G1 };
        END;
        """,
    )

    assert not parser.parse_network()


def test_parse_rejects_input_connected_more_than_once(tmp_path):
    """Test if parser rejects duplicate connections to the same input."""
    parser, names, devices, network, monitors = make_parser(
        tmp_path,
        """DEVICES {
            SW1 : SWITCH(0);
            SW2 : SWITCH(1);
            G1 : AND(1);
        }
        CONNECT {
            SW1 -> G1.I1;
            SW2 -> G1.I1;
        }
        MONITOR { G1 };
        END;
        """,
    )

    assert not parser.parse_network()


def test_parse_rejects_monitor_placed_on_non_output_signal(tmp_path):
    """Test if parser rejects monitor points that are input signals."""
    parser, names, devices, network, monitors = make_parser(
        tmp_path,
        """DEVICES {
            SW1 : SWITCH(0);
            G1 : AND(1);
        }
        CONNECT {
            SW1 -> G1.I1;
        }
        MONITOR { G1.I1 };
        END;
        """,
    )

    assert not parser.parse_network()
