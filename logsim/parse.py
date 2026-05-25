"""Parse the definition file and build the logic network.

Used in the Logic Simulator project to analyse the syntactic and semantic
correctness of the symbols received from the scanner and then builds the
logic network.

Classes
-------
Parser - parses the definition file and builds the logic network.
"""


class Parser:

    """Parse the definition file and build the logic network.

    The parser deals with error handling. It analyses the syntactic and
    semantic correctness of the symbols it receives from the scanner, and
    then builds the logic network. If there are errors in the definition file,
    the parser detects this and tries to recover from it, giving helpful
    error messages.

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
        """Initialise constants."""
        self.names = names
        self.devices = devices
        self.network = network
        self.monitors = monitors
        self.scanner = scanner

        self.symbol = None
        self.error_count = 0

    #Parse Functions
    def parse_network(self):
        """Parse the circuit definition file."""
        self.advance()

        self.parse_devices_section()
        self.parse_connections_section()
        self.parse_monitors_section()

        self.expect_keyword(self.scanner.END_ID, "expected END")
        self.expect_symbol(self.scanner.SEMICOLON, "expected ';' after END")
        self.expect_symbol(self.scanner.EOF, "expected end of file after END;")
        
        return self.error_count == 0

    def parse_devices_section(self):
        """Parse the DEVICES section."""
        self.expect_keyword(self.scanner.DEVICES_ID, "expected DEVICES")
        self.expect_symbol(self.scanner.LEFT_BRACE, "expected '{' after DEVICES")

        while self.symbol.type == self.scanner.NAME:
            self.parse_device_decl()

        self.expect_symbol(self.scanner.RIGHT_BRACE, "expected '}' after devices")
        # Assumes scanner has symbol types 'LEFT_BRACE, RIGHT_BRACE, NAME'

    def parse_device_decl(self):
        """Parse one device declaration."""
        self.expect_symbol(self.scanner.NAME, "expected device name")
        self.expect_symbol(self.scanner.COLON, "expected ':' after device name")
        self.parse_device_spec()
        self.expect_symbol(self.scanner.SEMICOLON, "expected ';' after device")
        # to be implemented: store device name and create device

    def parse_device_spec(self):
        """Parse a device specification."""
        if self.is_keyword(self.scanner.SWITCH_ID):
            self.advance()
            self.expect_symbol(self.scanner.LEFT_PAREN, "expected '(' after SWITCH")
            self.parse_bit()
            self.expect_symbol(self.scanner.RIGHT_PAREN, "expected ')' after SWITCH value")

        elif self.is_keyword(self.scanner.CLOCK_ID):
            self.advance()
            self.expect_symbol(self.scanner.LEFT_PAREN, "expected '(' after CLOCK")
            self.parse_positive_integer()
            self.expect_symbol(self.scanner.RIGHT_PAREN, "expected ')' after CLOCK period")

        elif self.is_gate_kind():
            self.advance()
            self.expect_symbol(self.scanner.LEFT_PAREN, "expected '(' after gate type")
            self.parse_positive_integer()
            self.expect_symbol(self.scanner.RIGHT_PAREN, "expected ')' after gate input count")

        elif self.is_keyword(self.scanner.DTYPE_ID):
            self.advance()

        elif self.is_keyword(self.scanner.XOR_ID):
            self.advance()

        else:
            self.report_error("expected device type")

    def parse_bit(self):
        """Parse a bit value, either 0 or 1."""
        if self.symbol.type == self.scanner.NUMBER and self.symbol.id in [0, 1]:
            self.advance()
        else:
            self.report_error("expected bit value 0 or 1")
    
    def parse_positive_integer(self):
        """Parse a positive integer."""
        if self.symbol.type == self.scanner.NUMBER and self.symbol.id > 0:
            self.advance()
        else:
            self.report_error("expected positive integer")

    def parse_connections_section(self):
        """Parse the CONNECT section."""
        self.expect_keyword(self.scanner.CONNECT_ID, "expected CONNECT")
        self.expect_symbol(self.scanner.LEFT_BRACE, "expected '{' after CONNECT")

        while self.symbol.type == self.scanner.NAME:
            self.parse_connection_decl()

        self.expect_symbol(self.scanner.RIGHT_BRACE, "expected '}' after connections")

    def parse_connection_decl(self):
        """Parse one connection declaration."""
        self.parse_output_signal()
        self.expect_symbol(self.scanner.ARROW, "expected '->' in connection")
        self.parse_input_signal()
        self.expect_symbol(self.scanner.SEMICOLON, "expected ';' after connection")
        # to be implemented: make connection

    def parse_input_signal(self):
        """Parse an input signal."""
        self.expect_symbol(self.scanner.NAME, "expected input device name")
        self.expect_symbol(self.scanner.DOT, "expected '.' in input signal")
        self.parse_input_port()

    def parse_input_port(self):
        """Parse an input port name."""
        self.expect_symbol(self.scanner.NAME, "expected input port name")
        # Assumes scanner treats 'DATA, CLK, SET, CLEAR' as NAME

    def parse_output_signal(self):
        """Parse an output signal."""
        self.expect_symbol(self.scanner.NAME, "expected output device name")

        if self.symbol.type == self.scanner.DOT:
            self.advance()
            self.parse_output_port()
    
    def parse_output_port(self):
        """Parse an output port name."""
        self.expect_symbol(self.scanner.NAME, "expected output port name")
        # Assumes scanner treats 'Q, QBAR' as NAME

    def parse_monitors_section(self):
        """Parse the MONITOR section."""
        self.expect_keyword(self.scanner.MONITOR_ID, "expected MONITOR")
        self.expect_symbol(self.scanner.LEFT_BRACE, "expected '{' after MONITOR")

        if self.symbol.type == self.scanner.NAME:
            self.parse_output_signal()

            while self.symbol.type == self.scanner.COMMA:
                self.advance()
                self.parse_output_signal()

        self.expect_symbol(self.scanner.RIGHT_BRACE, "expected '}' after monitors")
        self.expect_symbol(self.scanner.SEMICOLON, "expected ';' after MONITOR section")


    #Helper Functions
    def advance(self):
        """Advances to the next symbol from the scanner."""
        self.symbol = self.scanner.get_symbol()

    def report_error(self, message):
        """Report a syntax error."""
        self.error_count += 1
        print(f"Syntax error: {message}")

    def expect_symbol(self, symbol_type, error_message):
        """Checks that the current symbol has the expected type."""
        if self.symbol.type == symbol_type:
            self.advance()
            return True

        self.report_error(error_message)
        return False
    
    def expect_keyword(self, keyword_id, error_message):
        """Checks that the current symbol is the expected keyword."""
        if (self.symbol.type == self.scanner.KEYWORD and
                self.symbol.id == keyword_id):
            self.advance()
            return True

        self.report_error(error_message)
        return False
        # Assumes scanner classifies 'DEVICES, CONNECT, SWITCH, etc.' as keywords
    
    def is_keyword(self, keyword_id):
        """Return True if the current symbol is the specified keyword."""
        return (self.symbol.type == self.scanner.KEYWORD and
                self.symbol.id == keyword_id)
    
    def is_gate_kind(self):
        """Return True if the current symbol is a logic gate keyword."""
        return (
            self.is_keyword(self.scanner.AND_ID) or
            self.is_keyword(self.scanner.NAND_ID) or
            self.is_keyword(self.scanner.OR_ID) or
            self.is_keyword(self.scanner.NOR_ID)
        )
    
    def recover_to(self, stopping_types):
        """Skip symbols until one of the stopping symbol types is found."""
        while (self.symbol.type not in stopping_types and
            self.symbol.type != self.scanner.EOF):
            self.advance()