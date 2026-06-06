"""Parse the definition file and build the logic network.

Used in the Logic Simulator project to analyse the syntactic and semantic
correctness of the symbols received from the scanner and then build the
logic network.

Classes
-------
Parser - parses the definition file and builds the logic network.
"""


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
    """

    def __init__(self, names, devices, network, monitors, scanner):
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

    def parse_network(self):
        """Parse the circuit definition file."""
        self.advance()

        self.parse_devices_section()
        self.parse_connections_section()
        self.parse_monitors_section()

        self.expect_keyword(self.scanner.END_ID, "expected END")
        self.expect_symbol(self.scanner.SEMICOLON, "expected ';' after END")
        self.expect_symbol(self.scanner.EOF, "expected end of file after END")

        if not self.network.check_network():
            self.report_semantic_error(
                "one or more device inputs are unconnected"
            )

        return self.error_count == 0

    def parse_devices_section(self):
        """Parse the DEVICES section."""
        self.expect_keyword(self.scanner.DEVICES_ID, "expected DEVICES")
        self.expect_symbol(self.scanner.LEFT_BRACE,
                           "expected '{' after DEVICES")

        device_count = 0
        while self.symbol.type not in [self.scanner.RIGHT_BRACE,
                                       self.scanner.EOF]:
            if self.symbol.type == self.scanner.NAME:
                self.parse_device_decl()
                device_count += 1
            elif self.symbol.type == self.scanner.NUMBER:
                self.report_syntax_error(
                    "device name must start with a letter"
                )
                self.recover_device_declaration()
            elif self.symbol.type == self.scanner.INVALID:
                self.report_invalid_symbol()
                self.recover_device_declaration()
            else:
                self.report_syntax_error("expected device declaration")
                self.recover_device_declaration()

        if device_count == 0:
            self.report_syntax_error(
                "expected at least one device declaration"
            )

        self.expect_symbol(self.scanner.RIGHT_BRACE,
                           "expected '}' after devices")

    def parse_device_decl(self):
        """Parse one device declaration and create the device."""
        device_id = self.parse_name("expected device name")
        self.expect_symbol(self.scanner.COLON,
                           "expected ':' after device name")
        device_kind, device_property = self.parse_device_spec()
        self.expect_symbol(self.scanner.SEMICOLON,
                           "expected ';' after device")

        if device_id is None or device_kind is None:
            return

        error = self.devices.make_device(
            device_id, device_kind, device_property
        )
        self.handle_device_error(error, device_id)

    def parse_device_spec(self):
        """Parse a device specification and return kind and property."""
        if self.is_keyword(self.scanner.SWITCH_ID):
            self.advance()
            self.expect_symbol(self.scanner.LEFT_PAREN,
                               "expected '(' after SWITCH")
            initial_state = self.parse_bit()
            self.expect_symbol(self.scanner.RIGHT_PAREN,
                               "expected ')' after SWITCH value")
            return self.devices.SWITCH, initial_state

        if self.is_keyword(self.scanner.CLOCK_ID):
            self.advance()
            self.expect_symbol(self.scanner.LEFT_PAREN,
                               "expected '(' after CLOCK")
            half_period = self.parse_positive_integer()
            self.expect_symbol(self.scanner.RIGHT_PAREN,
                               "expected ')' after CLOCK period")
            return self.devices.CLOCK, half_period

        if self.is_gate_kind():
            device_kind = self.symbol.id
            self.advance()
            self.expect_symbol(self.scanner.LEFT_PAREN,
                               "expected '(' after gate type")
            input_count = self.parse_positive_integer()
            self.expect_symbol(self.scanner.RIGHT_PAREN,
                               "expected ')' after gate input count")
            return device_kind, input_count

        if self.is_keyword(self.scanner.DTYPE_ID):
            self.advance()
            return self.devices.D_TYPE, None

        if self.is_keyword(self.scanner.XOR_ID):
            self.advance()
            return self.devices.XOR, None

        self.report_syntax_error("expected device type")
        return None, None

    def parse_bit(self):
        """Parse a bit value, either 0 or 1."""
        if (self.symbol.type == self.scanner.NUMBER and
                self.symbol.id in [0, 1]):
            value = self.symbol.id
            self.advance()
            return value

        self.report_syntax_error("expected bit value 0 or 1")
        self.advance_if_needed()
        return None

    def parse_positive_integer(self):
        """Parse a positive integer."""
        if self.symbol.type == self.scanner.NUMBER and self.symbol.id > 0:
            value = self.symbol.id
            self.advance()
            return value

        self.report_syntax_error("expected positive integer")
        self.advance_if_needed()
        return None

    def parse_connections_section(self):
        """Parse the CONNECT section."""
        self.expect_keyword(self.scanner.CONNECT_ID, "expected CONNECT")
        self.expect_symbol(self.scanner.LEFT_BRACE,
                           "expected '{' after CONNECT")

        while self.symbol.type == self.scanner.NAME:
            self.parse_connection_decl()

        self.expect_symbol(self.scanner.RIGHT_BRACE,
                           "expected '}' after connections")

    def parse_connection_decl(self):
        """Parse one connection declaration and make the connection."""
        output_device_id, output_port_id = self.parse_output_signal()
        self.expect_symbol(self.scanner.ARROW, "expected '->' in connection")
        input_device_id, input_port_id = self.parse_input_signal()
        self.expect_symbol(self.scanner.SEMICOLON,
                           "expected ';' after connection")

        if None in [output_device_id, input_device_id, input_port_id]:
            return

        if self.is_ambiguous_dtype_output(output_device_id, output_port_id):
            device_name = self.names.get_name_string(output_device_id)
            self.report_semantic_error(
                "DTYPE output must be specified as "
                + device_name + ".Q or " + device_name + ".QBAR"
            )
            return

        error = self.network.make_connection(
            output_device_id, output_port_id, input_device_id, input_port_id
        )
        self.handle_connection_error(
            error, output_device_id, output_port_id,
            input_device_id, input_port_id
        )

    def parse_input_signal(self):
        """Parse an input signal and return device and input IDs."""
        device_id = self.parse_name("expected input device name")
        self.expect_symbol(self.scanner.DOT, "expected '.' in input signal")
        input_id = self.parse_input_port()
        return device_id, input_id

    def parse_input_port(self):
        """Parse an input port keyword and return its ID."""
        return self.parse_keyword_from(
            self.input_port_ids, "expected input port"
        )

    def parse_output_signal(self):
        """Parse an output signal and return device and output IDs."""
        device_id = self.parse_name("expected output device name")
        output_id = None

        if self.symbol.type == self.scanner.DOT:
            self.advance()
            output_id = self.parse_output_port()

        return device_id, output_id

    def parse_output_port(self):
        """Parse a DTYPE output port keyword and return its ID."""
        return self.parse_keyword_from(
            self.dtype_output_ids, "expected output port Q or QBAR"
        )

    def parse_monitors_section(self):
        """Parse the MONITOR section and create monitors."""
        self.expect_keyword(self.scanner.MONITOR_ID, "expected MONITOR")
        self.expect_symbol(self.scanner.LEFT_BRACE,
                           "expected '{' after MONITOR")

        if self.symbol.type == self.scanner.NAME:
            self.parse_monitor_signal()

            while self.symbol.type not in [self.scanner.RIGHT_BRACE,
                                           self.scanner.EOF]:
                if self.symbol.type == self.scanner.COMMA:
                    self.advance()
                    if self.symbol.type == self.scanner.RIGHT_BRACE:
                        self.report_syntax_error(
                            "expected monitor signal after ','"
                        )
                    else:
                        self.parse_monitor_signal()
                elif self.symbol.type == self.scanner.NAME:
                    self.report_syntax_error(
                        "expected ',' or '}' after monitor signal"
                    )
                    self.parse_monitor_signal()
                elif self.symbol.type == self.scanner.INVALID:
                    self.report_invalid_symbol()
                    self.recover_to([self.scanner.COMMA,
                                     self.scanner.RIGHT_BRACE])
                else:
                    self.report_syntax_error(
                        "expected ',' or '}' after monitor signal"
                    )
                    self.recover_to([self.scanner.COMMA,
                                     self.scanner.RIGHT_BRACE])

        self.expect_symbol(self.scanner.RIGHT_BRACE,
                           "expected '}' after monitors")
        self.expect_symbol(self.scanner.SEMICOLON,
                           "expected ';' after MONITOR section")

    def parse_monitor_signal(self):
        """Parse one monitor signal and create the monitor."""
        device_id, output_id = self.parse_output_signal()
        if device_id is None:
            return

        if self.is_ambiguous_dtype_output(device_id, output_id):
            device_name = self.names.get_name_string(device_id)
            self.report_semantic_error(
                "DTYPE output must be specified as "
                + device_name + ".Q or " + device_name + ".QBAR"
            )
            return

        error = self.monitors.make_monitor(device_id, output_id)
        self.handle_monitor_error(error, device_id, output_id)

    def parse_name(self, error_message):
        """Parse a user-defined name and return its ID."""
        if self.symbol.type == self.scanner.NAME:
            name_id = self.symbol.id
            self.advance()
            return name_id

        if self.symbol.type == self.scanner.INVALID:
            self.report_invalid_symbol()
            self.advance_if_needed()
            return None

        self.report_syntax_error(error_message)
        self.advance_if_needed()
        return None

    def parse_keyword_from(self, accepted_ids, error_message):
        """Parse one keyword from accepted_ids and return its ID."""
        if (self.symbol.type == self.scanner.KEYWORD and
                self.symbol.id in accepted_ids):
            keyword_id = self.symbol.id
            self.advance()
            return keyword_id

        if self.symbol.type == self.scanner.INVALID:
            self.report_invalid_symbol()
            self.advance_if_needed()
            return None

        self.report_syntax_error(error_message)
        self.advance_if_needed()
        return None

    def advance(self):
        """Advance to the next symbol from the scanner."""
        self.symbol = self.scanner.get_symbol()

    def advance_if_needed(self):
        """Advance unless already at end of file."""
        if self.symbol.type != self.scanner.EOF:
            self.advance()

    def report_syntax_error(self, message):
        """Report a syntax error."""
        self.error_count += 1
        print(self.format_error("Syntax", message))

    def report_semantic_error(self, message):
        """Report a semantic error."""
        self.error_count += 1
        print(self.format_error("Semantic", message))

    def report_invalid_symbol(self):
        """Report an invalid scanner symbol."""
        self.report_syntax_error("invalid symbol: " + str(self.symbol.id))

    def format_error(self, error_type, message):
        """Return a formatted error message with source location."""
        return (
            f"{error_type} error at line {self.symbol.line_number}, "
            f"column {self.symbol.position}: {message}"
        )

    def expect_symbol(self, symbol_type, error_message):
        """Check that the current symbol has the expected type."""
        if self.symbol.type == symbol_type:
            self.advance()
            return True

        if self.symbol.type == self.scanner.INVALID:
            self.report_invalid_symbol()
            self.advance_if_needed()
            return False

        self.report_syntax_error(error_message)
        self.advance_if_needed()
        return False

    def expect_keyword(self, keyword_id, error_message):
        """Check that the current symbol is the expected keyword."""
        if self.is_keyword(keyword_id):
            self.advance()
            return True

        if self.symbol.type == self.scanner.INVALID:
            self.report_invalid_symbol()
            self.advance_if_needed()
            return False

        self.report_syntax_error(error_message)
        self.advance_if_needed()
        return False

    def is_keyword(self, keyword_id):
        """Return True if the current symbol is the specified keyword."""
        return (self.symbol.type == self.scanner.KEYWORD and
                self.symbol.id == keyword_id)

    def is_gate_kind(self):
        """Return True if the current symbol is a logic gate keyword."""
        return (self.symbol.type == self.scanner.KEYWORD and
                self.symbol.id in self.gate_type_ids)

    def is_ambiguous_dtype_output(self, device_id, output_id):
        """Return True if a DTYPE output has been used without Q or QBAR."""
        device = self.devices.get_device(device_id)
        return (device is not None and
                device.device_kind == self.devices.D_TYPE and
                output_id is None)

    def handle_device_error(self, error, device_id):
        """Report semantic errors returned by Devices.make_device."""
        if error == self.devices.NO_ERROR:
            return

        device_name = self.names.get_name_string(device_id)
        if error == self.devices.DEVICE_PRESENT:
            self.report_semantic_error(
                "device name " + device_name + " is already defined"
            )
        elif error == self.devices.INVALID_QUALIFIER:
            self.report_semantic_error(
                "invalid property for device " + device_name
            )
        elif error == self.devices.NO_QUALIFIER:
            self.report_semantic_error(
                "missing required property for device " + device_name
            )
        elif error == self.devices.QUALIFIER_PRESENT:
            self.report_semantic_error(
                "unexpected property for device " + device_name
            )
        elif error == self.devices.BAD_DEVICE:
            self.report_semantic_error(
                "invalid device type for " + device_name
            )

    def handle_connection_error(self, error, output_device_id, output_port_id,
                                input_device_id, input_port_id):
        """Report semantic errors returned by Network.make_connection."""
        if error == self.network.NO_ERROR:
            return

        output_name = self.signal_name(output_device_id, output_port_id)
        input_name = self.signal_name(input_device_id, input_port_id)

        if error == self.network.DEVICE_ABSENT:
            self.report_semantic_error(
                "connection refers to an undefined device"
            )
        elif error == self.network.INPUT_TO_INPUT:
            self.report_semantic_error(
                output_name + " is an input and cannot be a connection source"
            )
        elif error == self.network.OUTPUT_TO_OUTPUT:
            self.report_semantic_error(
                input_name + " is an output and cannot be a connection "
                "destination"
            )
        elif error == self.network.INPUT_CONNECTED:
            self.report_semantic_error(
                "input " + input_name + " is connected more than once"
            )
        elif error == self.network.PORT_ABSENT:
            self.report_semantic_error(
                "invalid port in connection " + output_name + " -> "
                + input_name
            )

    def handle_monitor_error(self, error, device_id, output_id):
        """Report semantic errors returned by Monitors.make_monitor."""
        if error == self.monitors.NO_ERROR:
            return

        signal_name = self.signal_name(device_id, output_id)
        if error == self.network.DEVICE_ABSENT:
            self.report_semantic_error(
                "monitor refers to undefined device "
                + self.names.get_name_string(device_id)
            )
        elif error == self.monitors.NOT_OUTPUT:
            self.report_semantic_error(
                signal_name + " cannot be monitored because it is not an "
                "output"
            )
        elif error == self.monitors.MONITOR_PRESENT:
            self.report_semantic_error(
                "monitor point " + signal_name + " is listed more than once"
            )

    def signal_name(self, device_id, port_id):
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

    def recover_to(self, stopping_types):
        """Skip symbols until one of the stopping symbol types is found."""
        while (self.symbol.type not in stopping_types and
               self.symbol.type != self.scanner.EOF):
            self.advance()

    def recover_device_declaration(self):
        """Skip a malformed device declaration and consume its semicolon."""
        self.recover_to([self.scanner.SEMICOLON, self.scanner.RIGHT_BRACE])
        if self.symbol.type == self.scanner.SEMICOLON:
            self.advance()
