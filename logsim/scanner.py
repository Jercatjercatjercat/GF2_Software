"""Read the circuit definition file and translate the characters into symbols.

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
    """Read circuit definition file and translate the characters into symbols.

    Once supplied with the path to a valid definition file, the scanner
    translates the sequence of characters in the definition file into symbols
    that the parser can use. It also skips over comments and irrelevant
    formatting characters, such as spaces and line breaks.

    Parameters
    ----------
    path: path to the circuit definition file.
    names: instance of the names.Names() class.

    Public methods
    -------------
    get_symbol(self): Translates the next sequence of characters into a symbol
                      and returns the symbol.
    """

    def __init__(self, path, names):
        """Open specified file and initialise reserved words and IDs."""

    def get_symbol(self):
        """Translate the next sequence of characters into a symbol."""
