"""Parse the definition file and build the logic network.

Used in the Logic Simulator project to analyse the syntactic and semantic
correctness of the symbols received from the scanner and then build the
logic network.

Classes
-------
Parser - parses the definition file and builds the logic network.
"""

from typing import Sequence


class Parser:
    """Parse the definition file and build the logic network.

    The parser implements the grammar specified in LogicDescriptionLanguage.
    It consumes symbols from Scanner, checks syntax, reports semantic errors,
    and calls Devices, Network, and Monitors to construct the simulator state.

    Parameters
    ----------
    names: instance of the names.Names() class.
    devices: instance of the devices.Devices() class.
    network: instance of the network.Network() class.
    monitors: instance of the monitors.Monitors() class.
    scanner: instance of the scanner.Scanner() class.

    Public methods
    --------------
    parse_network(self): Parses the circuit definition file.

    Notes
    -----
    Helper methods are private because parsing is driven only through
    parse_network(). They are kept small to mirror the grammar rules and to
    keep syntax checks separate from semantic checks.
    """

    def __init__(self, names: object, devices: object, network: object,
                 monitors: object, scanner: object) -> None:
        """Initialise parser state."""
        self.names = names
        self.devices = devices
        self.network = network
        self.monitors = monitors
        self.scanner = scanner

        self.symbol = None
        self.error_count = 0

        self.gate_type_ids = [
            self.scanner.AND_ID, self.scanner.NAND_ID,
            self.scanner.OR_ID, self.scanner.NOR_ID
        ]
        self.dtype_input_ids = [
            self.scanner.DATA_ID, self.scanner.CLK_ID,
            self.scanner.SET_ID, self.scanner.CLEAR_ID
        ]
        self.dtype_output_ids = [
            self.scanner.Q_ID, self.scanner.QBAR_ID
        ]
        self.input_port_ids = (
            self.scanner.gate_input_ids + self.dtype_input_ids
        )

    def parse_network(self) -> bool:
        """Parse the circuit definition file."""
        self._advance()

        # The top-level order follows the LDL grammar exactly.
        self._parse_devices_section()
        self._parse_connections_section()
        self._parse_monitors_section()

        self._expect_keyword(self.scanner.END_ID, "expected END")
        self._expect_symbol(self.scanner.SEMICOLON, "expected ';' after END")
        self._expect_symbol(self.scanner.EOF, "expected end of file after END")

        self._report_unconnected_inputs()

        return self.error_count == 0

    def _parse_devices_section(self) -> None:
        """Parse the DEVICES section."""
        self._expect_keyword(self.scanner.DEVICES_ID, "expected DEVICES")
        self._expect_symbol(self.scanner.LEFT_BRACE,
                            "expected '{' after DEVICES")

        device_count = 0
        while self.symbol.type not in [self.scanner.RIGHT_BRACE,
                                       self.scanner.EOF]:
            # Recover one declaration at a time so that later sections can
            # still be parsed and useful errors can still be reported.
            if self.symbol.type == self.scanner.NAME:
                self._parse_device_decl()
                device_count += 1
            elif self.symbol.type == self.scanner.NUMBER:
                self._report_syntax_error(
                    "device name must start with a letter"
                )
                self._recover_device_declaration()
            elif self.symbol.type == self.scanner.INVALID:
                self._report_invalid_symbol()
                self._recover_device_declaration()
            else:
                self._report_syntax_error("expected device declaration")
                self._recover_device_declaration()

        if device_count == 0:
            self._report_syntax_error(
                "expected at least one device declaration"
            )

        self._expect_symbol(self.scanner.RIGHT_BRACE,
                            "expected '}' after devices")

    def _parse_device_decl(self) -> None:
        """Parse one device declaration and create the device."""
        device_id = self._parse_name("expected device name")
        self._expect_symbol(self.scanner.COLON,
                            "expected ':' after device name")
        device_kind, device_property = self._parse_device_spec()
        self._expect_symbol(self.scanner.SEMICOLON,
                            "expected ';' after device")

        if device_id is None or device_kind is None:
            return

        # Once the declaration syntax is valid, Devices performs semantic
        # checks such as duplicate names and invalid properties.
        error = self.devices.make_device(
            device_id, device_kind, device_property
        )
        self._handle_device_error(error, device_id)

    def _parse_device_spec(self) -> tuple[int | None, object]:
        """Parse a device specification and return kind and property."""
        if self._is_keyword(self.scanner.SWITCH_ID):
            self._advance()
            self._expect_symbol(self.scanner.LEFT_PAREN,
                                "expected '(' after SWITCH")
            initial_state = self._parse_bit()
            self._expect_symbol(self.scanner.RIGHT_PAREN,
                                "expected ')' after SWITCH value")
            return self.devices.SWITCH, initial_state

        if self._is_keyword(self.scanner.CLOCK_ID):
            self._advance()
            self._expect_symbol(self.scanner.LEFT_PAREN,
                                "expected '(' after CLOCK")
            half_period = self._parse_positive_integer()
            self._expect_symbol(self.scanner.RIGHT_PAREN,
                                "expected ')' after CLOCK period")
            return self.devices.CLOCK, half_period

        if self._is_keyword(self.scanner.RC_ID):
            self._advance()
            self._expect_symbol(self.scanner.LEFT_PAREN,
                                "expected '(' after RC")
            delay = self._parse_positive_integer()
            self._expect_symbol(self.scanner.RIGHT_PAREN,
                                "expected ')' after RC delay")
            return self.devices.RC, delay

        if self._is_keyword(self.scanner.SIGGEN_ID):
            self._advance()
            self._expect_symbol(self.scanner.LEFT_PAREN,
                                "expected '(' after SIGGEN")
            pattern = self._parse_siggen_pattern()
            self._expect_symbol(self.scanner.RIGHT_PAREN,
                                "expected ')' after SIGGEN waveform")
            return self.devices.SIGGEN, pattern

        if self._is_gate_kind():
            device_kind = self.symbol.id
            self._advance()
            self._expect_symbol(self.scanner.LEFT_PAREN,
                                "expected '(' after gate type")
            input_count = self._parse_positive_integer()
            self._expect_symbol(self.scanner.RIGHT_PAREN,
                                "expected ')' after gate input count")
            return device_kind, input_count

        if self._is_keyword(self.scanner.DTYPE_ID):
            self._advance()
            return self.devices.D_TYPE, None

        if self._is_keyword(self.scanner.XOR_ID):
            self._advance()
            return self.devices.XOR, None

        self._report_syntax_error("expected device type")
        return None, None

    def _parse_siggen_pattern(self) -> list[int]:
        """Parse a SIGGEN waveform as a comma-separated list of bits."""
        pattern = []
        bit = self._parse_bit()
        if bit is not None:
            pattern.append(bit)

        while self.symbol.type == self.scanner.COMMA:
            self._advance()
            bit = self._parse_bit()
            if bit is not None:
                pattern.append(bit)

        return pattern

    def _parse_bit(self) -> int | None:
        """Parse a bit value, either 0 or 1."""
        if (self.symbol.type == self.scanner.NUMBER and
                self.symbol.id in [0, 1]):
            value = self.symbol.id
            self._advance()
            return value

        self._report_syntax_error("expected bit value 0 or 1")
        self._advance_if_needed()
        return None

    def _parse_positive_integer(self) -> int | None:
        """Parse a positive integer."""
        if self.symbol.type == self.scanner.NUMBER and self.symbol.id > 0:
            value = self.symbol.id
            self._advance()
            return value

        self._report_syntax_error("expected positive integer")
        self._advance_if_needed()
        return None

    def _parse_connections_section(self) -> None:
        """Parse the CONNECT section."""
        self._expect_keyword(self.scanner.CONNECT_ID, "expected CONNECT")
        self._expect_symbol(self.scanner.LEFT_BRACE,
                            "expected '{' after CONNECT")

        while self.symbol.type == self.scanner.NAME:
            self._parse_connection_decl()

        self._expect_symbol(self.scanner.RIGHT_BRACE,
                            "expected '}' after connections")

    def _parse_connection_decl(self) -> None:
        """Parse one connection declaration and make the connection."""
        output_device_id, output_port_id = self._parse_output_signal()
        self._expect_symbol(self.scanner.ARROW, "expected '->' in connection")
        input_device_id, input_port_id = self._parse_input_signal()
        self._expect_symbol(self.scanner.SEMICOLON,
                           "expected ';' after connection")

        if None in [output_device_id, input_device_id, input_port_id]:
            return

        # A bare DTYPE name is syntactically an output signal, but semantically
        # ambiguous because DTYPE has both Q and QBAR outputs.
        if self._is_ambiguous_dtype_output(output_device_id, output_port_id):
            device_name = self.names.get_name_string(output_device_id)
            self._report_semantic_error(
                "DTYPE output must be specified as "
                + device_name + ".Q or " + device_name + ".QBAR"
            )
            return

        error = self.network.make_connection(
            output_device_id, output_port_id, input_device_id, input_port_id
        )
        self._handle_connection_error(
            error, output_device_id, output_port_id,
            input_device_id, input_port_id
        )

    def _parse_input_signal(self) -> tuple[int | None, int | None]:
        """Parse an input signal and return device and input IDs."""
        device_id = self._parse_name("expected input device name")
        self._expect_symbol(self.scanner.DOT, "expected '.' in input signal")
        input_id = self._parse_input_port()
        return device_id, input_id

    def _parse_input_port(self) -> int | None:
        """Parse an input port keyword and return its ID."""
        return self._parse_keyword_from(
            self.input_port_ids, "expected input port"
        )

    def _parse_output_signal(self) -> tuple[int | None, int | None]:
        """Parse an output signal and return device and output IDs."""
        device_id = self._parse_name("expected output device name")
        output_id = None

        if self.symbol.type == self.scanner.DOT:
            self._advance()
            output_id = self._parse_output_port()

        return device_id, output_id

    def _parse_output_port(self) -> int | None:
        """Parse a DTYPE output port keyword and return its ID."""
        return self._parse_keyword_from(
            self.dtype_output_ids, "expected output port Q or QBAR"
        )

    def _parse_monitors_section(self) -> None:
        """Parse the MONITOR section and create monitors."""
        self._expect_keyword(self.scanner.MONITOR_ID, "expected MONITOR")
        self._expect_symbol(self.scanner.LEFT_BRACE,
                            "expected '{' after MONITOR")

        if self.symbol.type == self.scanner.NAME:
            self._parse_monitor_signal()

            while self.symbol.type not in [self.scanner.RIGHT_BRACE,
                                           self.scanner.EOF]:
                # Monitor lists are comma-separated. If a comma is missing,
                # parse the next signal after reporting the local error.
                if self.symbol.type == self.scanner.COMMA:
                    self._advance()
                    if self.symbol.type == self.scanner.RIGHT_BRACE:
                        self._report_syntax_error(
                            "expected monitor signal after ','"
                        )
                    else:
                        self._parse_monitor_signal()
                elif self.symbol.type == self.scanner.NAME:
                    self._report_syntax_error(
                        "expected ',' or '}' after monitor signal"
                    )
                    self._parse_monitor_signal()
                elif self.symbol.type == self.scanner.INVALID:
                    self._report_invalid_symbol()
                    self._recover_to([self.scanner.COMMA,
                                      self.scanner.RIGHT_BRACE])
                else:
                    self._report_syntax_error(
                        "expected ',' or '}' after monitor signal"
                    )
                    self._recover_to([self.scanner.COMMA,
                                      self.scanner.RIGHT_BRACE])

        self._expect_symbol(self.scanner.RIGHT_BRACE,
                            "expected '}' after monitors")
        self._expect_symbol(self.scanner.SEMICOLON,
                            "expected ';' after MONITOR section")

    def _parse_monitor_signal(self) -> None:
        """Parse one monitor signal and create the monitor."""
        device_id, output_id = self._parse_output_signal()
        if device_id is None:
            return

        if self._is_ambiguous_dtype_output(device_id, output_id):
            device_name = self.names.get_name_string(device_id)
            self._report_semantic_error(
                "DTYPE output must be specified as "
                + device_name + ".Q or " + device_name + ".QBAR"
            )
            return

        error = self.monitors.make_monitor(device_id, output_id)
        self._handle_monitor_error(error, device_id, output_id)

    def _parse_name(self, error_message: str) -> int | None:
        """Parse a user-defined name and return its ID."""
        if self.symbol.type == self.scanner.NAME:
            name_id = self.symbol.id
            self._advance()
            return name_id

        if self.symbol.type == self.scanner.INVALID:
            self._report_invalid_symbol()
            self._advance_if_needed()
            return None

        self._report_syntax_error(error_message)
        self._advance_if_needed()
        return None

    def _parse_keyword_from(self, accepted_ids: Sequence[int],
                            error_message: str) -> int | None:
        """Parse one keyword from accepted_ids and return its ID."""
        if (self.symbol.type == self.scanner.KEYWORD and
                self.symbol.id in accepted_ids):
            keyword_id = self.symbol.id
            self._advance()
            return keyword_id

        if self.symbol.type == self.scanner.INVALID:
            self._report_invalid_symbol()
            self._advance_if_needed()
            return None

        self._report_syntax_error(error_message)
        self._advance_if_needed()
        return None

    def _advance(self) -> None:
        """Advance to the next symbol from the scanner."""
        self.symbol = self.scanner.get_symbol()

    def _advance_if_needed(self) -> None:
        """Advance unless already at end of file."""
        if self.symbol.type != self.scanner.EOF:
            self._advance()

    def _report_syntax_error(self, message: str) -> None:
        """Report a syntax error."""
        self.error_count += 1
        print(self._format_error("Syntax", message))
        self._print_error_pointer()

    def _report_semantic_error(self, message: str) -> None:
        """Report a semantic error."""
        self.error_count += 1
        print(self._format_error("Semantic", message))
        self._print_error_pointer()

    def _report_invalid_symbol(self) -> None:
        """Report an invalid scanner symbol."""
        self._report_syntax_error("invalid symbol: " + str(self.symbol.id))

    def _format_error(self, error_type: str, message: str) -> str:
        """Return a formatted error message with source location."""
        return (
            f"{error_type} error at line {self.symbol.line_number}, "
            f"column {self.symbol.position}: {message}"
        )

    def _print_error_pointer(self) -> None:
        """Print the source line containing the current symbol with a caret."""
        self.scanner.print_line_with_pointer(
            self.symbol.line_number, self.symbol.position
        )

    def _expect_symbol(self, symbol_type: int, error_message: str) -> bool:
        """Check that the current symbol has the expected type."""
        if self.symbol.type == symbol_type:
            self._advance()
            return True

        if self.symbol.type == self.scanner.INVALID:
            self._report_invalid_symbol()
            self._advance_if_needed()
            return False

        self._report_syntax_error(error_message)
        self._advance_if_needed()
        return False

    def _expect_keyword(self, keyword_id: int, error_message: str) -> bool:
        """Check that the current symbol is the expected keyword."""
        if self._is_keyword(keyword_id):
            self._advance()
            return True

        if self.symbol.type == self.scanner.INVALID:
            self._report_invalid_symbol()
            self._advance_if_needed()
            return False

        self._report_syntax_error(error_message)
        self._advance_if_needed()
        return False

    def _is_keyword(self, keyword_id: int) -> bool:
        """Return True if the current symbol is the specified keyword."""
        return (self.symbol.type == self.scanner.KEYWORD and
                self.symbol.id == keyword_id)

    def _is_gate_kind(self) -> bool:
        """Return True if the current symbol is a logic gate keyword."""
        return (self.symbol.type == self.scanner.KEYWORD and
                self.symbol.id in self.gate_type_ids)

    def _is_ambiguous_dtype_output(self, device_id: int,
                                   output_id: int | None) -> bool:
        """Return True if a DTYPE output has been used without Q or QBAR."""
        device = self.devices.get_device(device_id)
        return (device is not None and
                device.device_kind == self.devices.D_TYPE and
                output_id is None)

    def _handle_device_error(self, error: int, device_id: int) -> None:
        """Report semantic errors returned by Devices.make_device."""
        if error == self.devices.NO_ERROR:
            return

        device_name = self.names.get_name_string(device_id)
        if error == self.devices.DEVICE_PRESENT:
            self._report_semantic_error(
                "device name " + device_name + " is already defined"
            )
        elif error == self.devices.INVALID_QUALIFIER:
            self._report_semantic_error(
                "invalid property for device " + device_name
            )
        elif error == self.devices.NO_QUALIFIER:
            self._report_semantic_error(
                "missing required property for device " + device_name
            )
        elif error == self.devices.QUALIFIER_PRESENT:
            self._report_semantic_error(
                "unexpected property for device " + device_name
            )
        elif error == self.devices.BAD_DEVICE:
            self._report_semantic_error(
                "invalid device type for " + device_name
            )

    def _handle_connection_error(self, error: int, output_device_id: int,
                                 output_port_id: int | None,
                                 input_device_id: int,
                                 input_port_id: int) -> None:
        """Report semantic errors returned by Network.make_connection."""
        if error == self.network.NO_ERROR:
            return

        output_name = self._signal_name(output_device_id, output_port_id)
        input_name = self._signal_name(input_device_id, input_port_id)

        if error == self.network.DEVICE_ABSENT:
            self._report_semantic_error(
                "connection refers to undefined device "
                + self._undefined_connection_devices(
                    output_device_id, input_device_id
                )
            )
        elif error == self.network.INPUT_TO_INPUT:
            self._report_semantic_error(
                output_name + " is an input and cannot be a connection source"
            )
        elif error == self.network.OUTPUT_TO_OUTPUT:
            self._report_semantic_error(
                input_name + " is an output and cannot be a connection "
                "destination"
            )
        elif error == self.network.INPUT_CONNECTED:
            self._report_semantic_error(
                "input " + input_name + " is connected more than once"
            )
        elif error == self.network.PORT_ABSENT:
            self._report_semantic_error(
                "invalid port in connection " + output_name + " -> "
                + input_name
            )

    def _handle_monitor_error(self, error: int, device_id: int,
                              output_id: int | None) -> None:
        """Report semantic errors returned by Monitors.make_monitor."""
        if error == self.monitors.NO_ERROR:
            return

        monitor_name = self._signal_name(device_id, output_id)
        if error == self.network.DEVICE_ABSENT:
            self._report_semantic_error(
                "monitor refers to undefined device "
                + self.names.get_name_string(device_id)
            )
        elif error == self.monitors.NOT_OUTPUT:
            self._report_semantic_error(
                monitor_name + " cannot be monitored because it is not an "
                "output"
            )
        elif error == self.monitors.MONITOR_PRESENT:
            self._report_semantic_error(
                "monitor point " + monitor_name + " is listed more than once"
            )

    def _signal_name(self, device_id: int, port_id: int | None) -> str:
        """Return a readable signal name from IDs."""
        device_name = self.names.get_name_string(device_id)
        if device_name is None:
            device_name = "<unknown>"
        if port_id is None:
            return device_name

        port_name = self.names.get_name_string(port_id)
        if port_name is None:
            port_name = "<unknown>"
        return device_name + "." + port_name

    def _undefined_connection_devices(self, output_device_id: int,
                                      input_device_id: int) -> str:
        """Return the undefined device names used in a connection."""
        undefined_devices = []
        for device_id in [output_device_id, input_device_id]:
            if self.devices.get_device(device_id) is None:
                undefined_devices.append(self.names.get_name_string(device_id))
        return ", ".join(undefined_devices)

    def _report_unconnected_inputs(self) -> None:
        """Report each unconnected input by name."""
        for device_id, input_id in self.network.get_unconnected_inputs():
            self._report_semantic_error(
                "input " + self._signal_name(device_id, input_id)
                + " is not connected"
            )

    def _recover_to(self, stopping_types: Sequence[int]) -> None:
        """Skip symbols until one of the stopping symbol types is found."""
        while (self.symbol.type not in stopping_types and
               self.symbol.type != self.scanner.EOF):
            self._advance()

    def _recover_device_declaration(self) -> None:
        """Skip a malformed device declaration and consume its semicolon."""
        self._recover_to([self.scanner.SEMICOLON, self.scanner.RIGHT_BRACE])
        if self.symbol.type == self.scanner.SEMICOLON:
            self._advance()
