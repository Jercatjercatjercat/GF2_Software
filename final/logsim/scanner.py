"""Read the circuit definition file and translate it into symbols.

Used in the Logic Simulator project to read the characters in the definition
file and translate them into symbols that are usable by the parser.

Classes
-------
Scanner - reads definition file and translates characters into symbols.
Symbol - encapsulates a symbol and stores its properties.
"""


class Symbol:
    """Encapsulate a symbol and store its properties.

    A symbol is one token produced by the scanner, such as a keyword,
    name, number, punctuation mark, or end-of-file marker.

    Parameters
    ----------
    symbol_type: symbol type, such as KEYWORD, NAME, NUMBER or punctuation.
    symbol_id: symbol value, such as a name ID, number value or keyword ID.
    line_number: line on which the symbol starts.
    position: character position on the line where the symbol starts.

    Public methods
    --------------
    No public methods.
    """

    def __init__(self, symbol_type=None, symbol_id=None, line_number=None,
                 position=None):
        """Initialise symbol properties."""
        self.type = symbol_type
        self.id = symbol_id
        self.line_number = line_number
        self.position = position


class Scanner:
    """Read circuit definition file and translate characters into symbols.

    The implemented grammar is:

    network =
        devices_section , connections_section , monitors_section ,
        "END" , ";" ;

    devices_section =
        "DEVICES" , "{" , device_decl , { device_decl } , "}" ;

    device_decl =
        device_name , ":" , device_spec , ";" ;

    device_spec =
          "SWITCH" , "(" , bit , ")"
        | "CLOCK" , "(" , positive_integer , ")"
        | "RC" , "(" , positive_integer , ")"
        | "SIGGEN" , "(" , bit , { "," , bit } , ")"
        | gate_kind , "(" , positive_integer , ")"
        | "DTYPE"
        | "XOR" ;

    gate_kind =
        "AND" | "NAND" | "OR" | "NOR" ;

    connections_section =
        "CONNECT" , "{" , { connection_decl } , "}" ;

    connection_decl =
        output_signal , "->" , input_signal , ";" ;

    monitors_section =
        "MONITOR" , "{" , [ output_signal , { "," , output_signal } ] ,
        "}" , ";" ;

    input_signal =
        device_name , "." , input_port ;

    output_signal =
        device_name | device_name , "." , dtype_output_port ;

    input_port =
        gate_input_port | dtype_input_port ;

    gate_input_port =
        "I1" | "I2" | ... | "I16" ;

    dtype_input_port =
        "DATA" | "CLK" | "SET" | "CLEAR" ;

    dtype_output_port =
        "Q" | "QBAR" ;

    device_name =
        letter , { letter | digit | "_" } ;

    positive_integer =
        non_zero_digit , { digit } ;

    bit =
        "0" | "1" ;

    The scanner recognises names, reserved keywords, numbers, punctuation,
    open comments beginning with '#', and closed comments delimited by
    '/*' and '*/'. Comments and whitespace are discarded before the parser
    sees the symbol stream.

    Parameters
    ----------
    path: path to the circuit definition file.
    names: instance of the names.Names() class.

    Public methods
    -------------
    get_symbol(self): Translates the next sequence of characters into a symbol
                      and returns the symbol.

    print_current_line(self): Prints the current input line with a marker
                              showing the current position.
    """

    def __init__(self, path, names):
        """Open specified file and initialise reserved words and IDs."""
        self.names = names
        self.symbol_type_list = [
            self.COMMA, self.SEMICOLON, self.EQUALS, self.COLON,
            self.DOT, self.LEFT_BRACE, self.RIGHT_BRACE, self.LEFT_PAREN,
            self.RIGHT_PAREN, self.ARROW, self.KEYWORD, self.NUMBER,
            self.NAME, self.EOF, self.INVALID
        ] = range(15)

        gate_inputs = ["I" + str(index) for index in range(1, 17)]
        self.keywords_list = [
            "DEVICES", "CONNECT", "MONITOR", "END", "SWITCH", "CLOCK",
            "RC", "SIGGEN", "DTYPE", "XOR", "AND", "NAND", "OR", "NOR",
            "DATA", "CLK", "SET", "CLEAR", "Q", "QBAR"
        ] + gate_inputs

        [
            self.DEVICES_ID, self.CONNECT_ID, self.MONITOR_ID, self.END_ID,
            self.SWITCH_ID, self.CLOCK_ID, self.RC_ID, self.SIGGEN_ID,
            self.DTYPE_ID, self.XOR_ID, self.AND_ID, self.NAND_ID,
            self.OR_ID, self.NOR_ID, self.DATA_ID, self.CLK_ID,
            self.SET_ID, self.CLEAR_ID, self.Q_ID, self.QBAR_ID,
            *self.gate_input_ids
        ] = self.names.lookup(self.keywords_list)

        self.punctuation = {
            ",": self.COMMA,
            ";": self.SEMICOLON,
            "=": self.EQUALS,
            ":": self.COLON,
            ".": self.DOT,
            "{": self.LEFT_BRACE,
            "}": self.RIGHT_BRACE,
            "(": self.LEFT_PAREN,
            ")": self.RIGHT_PAREN,
        }

        self.definition_file = open(path, encoding="utf-8")
        self.source_lines = self.definition_file.readlines()
        self.definition_file.seek(0)
        self.line_number = 1
        self.position = 0
        self.current_line = ""
        self.current_character = ""
        self.pending_symbol = None
        self.advance()

    def advance(self):
        """Read the next character and update line and position counters."""
        character = self.definition_file.read(1)
        self.current_character = character

        if character == "":
            return

        if self.position == 0:
            self.current_line = ""

        self.current_line += character

        if character == "\n":
            self.line_number += 1
            self.position = 0
        else:
            self.position += 1

    def peek(self):
        """Return the next character without consuming it."""
        file_position = self.definition_file.tell()
        character = self.definition_file.read(1)
        self.definition_file.seek(file_position)
        return character

    def skip_spaces_and_comments(self):
        """Skip whitespace and comments from the current position."""
        skipping = True
        while skipping:
            skipping = False

            while self.current_character.isspace():
                self.advance()
                skipping = True

            if self.current_character == "#":
                self.skip_open_comment()
                skipping = True

            elif self.current_character == "/" and self.peek() == "*":
                start_line = self.line_number
                start_position = self.position
                self.advance()
                if self.skip_closed_comment():
                    skipping = True
                else:
                    self.pending_symbol = Symbol(
                        self.INVALID,
                        "unterminated block comment",
                        start_line,
                        start_position,
                    )
                    return

    def skip_open_comment(self):
        """Skip from '#' to the end of the current line or file."""
        while self.current_character not in ["", "\n"]:
            self.advance()

    def skip_closed_comment(self):
        """Skip from '/*' to the following '*/'.

        Return True if the closing delimiter is found, or False if the file
        ends before the comment is closed.
        """
        self.advance()
        previous_character = ""
        while self.current_character != "":
            if previous_character == "*" and self.current_character == "/":
                self.advance()
                return True
            previous_character = self.current_character
            self.advance()
        return False

    def get_name(self):
        """Return a name string, leaving current character after the name."""
        name = ""
        while (self.current_character.isalnum()
               or self.current_character == "_"):
            name += self.current_character
            self.advance()
        return name

    def get_number(self):
        """Return an integer, leaving current character after the number."""
        number = ""
        while self.current_character.isdigit():
            number += self.current_character
            self.advance()
        return int(number)

    def get_symbol(self):
        """Translate the next sequence of characters into a symbol."""
        self.skip_spaces_and_comments()
        if self.pending_symbol is not None:
            symbol = self.pending_symbol
            self.pending_symbol = None
            return symbol

        line_number = self.line_number
        position = self.position

        if self.current_character == "":
            return Symbol(self.EOF, None, line_number, position)

        if self.current_character.isalpha():
            name_string = self.get_name()
            [name_id] = self.names.lookup([name_string])
            if name_string in self.keywords_list:
                return Symbol(self.KEYWORD, name_id, line_number, position)
            return Symbol(self.NAME, name_id, line_number, position)

        if self.current_character.isdigit():
            number = self.get_number()
            return Symbol(self.NUMBER, number, line_number, position)

        if self.current_character == "-":
            self.advance()
            if self.current_character == ">":
                self.advance()
                return Symbol(self.ARROW, None, line_number, position)
            return Symbol(self.INVALID, "-", line_number, position)

        if self.current_character in self.punctuation:
            symbol_type = self.punctuation[self.current_character]
            self.advance()
            return Symbol(symbol_type, None, line_number, position)

        invalid_character = self.current_character
        self.advance()
        return Symbol(self.INVALID, invalid_character, line_number, position)

    def print_current_line(self):
        """Print the current input line and mark the current position."""
        line = self.current_line.rstrip("\n")
        print(line)
        print(" " * max(self.position - 1, 0) + "^")

    def print_line_with_pointer(self, line_number, position):
        """Print a source line and mark the given position with a caret."""
        if line_number is None or position is None:
            return
        if line_number < 1 or line_number > len(self.source_lines):
            return

        line = self.source_lines[line_number - 1].rstrip("\n")
        print(line)
        print(" " * max(position - 1, 0) + "^")
