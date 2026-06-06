"""Test the scanner module."""
from pathlib import Path

import pytest

from names import Names
from scanner import Scanner, Symbol


@pytest.fixture
def names():
    """Return a fresh Names instance."""
    return Names()


def make_definition_file(tmp_path, text):
    """Create and return a temporary definition file path."""
    path = tmp_path / "definition.txt"
    path.write_text(text, encoding="utf-8")
    return path


def collect_symbols(scanner):
    """Return all symbols up to and including EOF."""
    symbols = []
    symbol = scanner.get_symbol()
    while symbol.type != scanner.EOF:
        symbols.append(symbol)
        symbol = scanner.get_symbol()
    symbols.append(symbol)
    return symbols


def test_symbol_initialisation():
    """Test if Symbol stores its given properties."""
    symbol = Symbol(symbol_type=1, symbol_id=2, line_number=3, position=4)

    assert symbol.type == 1
    assert symbol.id == 2
    assert symbol.line_number == 3
    assert symbol.position == 4


def test_scanner_recognises_definition_symbols(tmp_path, names):
    """Test if the scanner tokenises the revised EBNF language."""
    path = make_definition_file(
        tmp_path,
        """DEVICES {
        SW1 : SWITCH(0);
        G1 : NAND(2);
        }
        CONNECT { SW1 -> G1.I1; }
        MONITOR { G1 };
        END;
        """,
    )
    scanner = Scanner(path, names)
    symbols = collect_symbols(scanner)

    symbol_types = [symbol.type for symbol in symbols]
    assert symbol_types == [
        scanner.KEYWORD, scanner.LEFT_BRACE,
        scanner.NAME, scanner.COLON, scanner.KEYWORD,
        scanner.LEFT_PAREN, scanner.NUMBER, scanner.RIGHT_PAREN,
        scanner.SEMICOLON,
        scanner.NAME, scanner.COLON, scanner.KEYWORD,
        scanner.LEFT_PAREN, scanner.NUMBER, scanner.RIGHT_PAREN,
        scanner.SEMICOLON, scanner.RIGHT_BRACE,
        scanner.KEYWORD, scanner.LEFT_BRACE,
        scanner.NAME, scanner.ARROW, scanner.NAME, scanner.DOT,
        scanner.KEYWORD, scanner.SEMICOLON, scanner.RIGHT_BRACE,
        scanner.KEYWORD, scanner.LEFT_BRACE, scanner.NAME,
        scanner.RIGHT_BRACE, scanner.SEMICOLON,
        scanner.KEYWORD, scanner.SEMICOLON, scanner.EOF,
    ]
    assert symbols[6].id == 0
    assert symbols[13].id == 2
    assert names.get_name_string(symbols[23].id) == "I1"


def test_scanner_distinguishes_keywords_and_names(tmp_path, names):
    """Test if reserved words are keywords and other words are names."""
    path = make_definition_file(tmp_path, "DEVICES SW1 DATA_SW DATA I16")
    scanner = Scanner(path, names)
    symbols = collect_symbols(scanner)

    assert [symbol.type for symbol in symbols[:-1]] == [
        scanner.KEYWORD, scanner.NAME, scanner.NAME,
        scanner.KEYWORD, scanner.KEYWORD,
    ]
    assert names.get_name_string(symbols[1].id) == "SW1"
    assert names.get_name_string(symbols[2].id) == "DATA_SW"
    assert names.get_name_string(symbols[3].id) == "DATA"


def test_scanner_skips_open_and_closed_comments(tmp_path, names):
    """Test if scanner skips hash comments and closed block comments."""
    path = make_definition_file(
        tmp_path,
        """DEVICES { # open comment
        /* closed
           block comment */
        SW1 : SWITCH(1);
        }
        """,
    )
    scanner = Scanner(path, names)
    symbols = collect_symbols(scanner)

    assert [symbol.type for symbol in symbols] == [
        scanner.KEYWORD, scanner.LEFT_BRACE,
        scanner.NAME, scanner.COLON, scanner.KEYWORD,
        scanner.LEFT_PAREN, scanner.NUMBER, scanner.RIGHT_PAREN,
        scanner.SEMICOLON, scanner.RIGHT_BRACE, scanner.EOF,
    ]


def test_scanner_reports_unterminated_closed_comment(tmp_path, names):
    """Test if scanner reports an unclosed block comment at its start."""
    path = make_definition_file(
        tmp_path,
        """DEVICES {
/* not properly closed
   *./
SW1 : SWITCH(1);
}
        """,
    )
    scanner = Scanner(path, names)

    scanner.get_symbol()
    scanner.get_symbol()
    symbol = scanner.get_symbol()

    assert symbol.type == scanner.INVALID
    assert symbol.id == "unterminated block comment"
    assert symbol.line_number == 2
    assert symbol.position == 1


def test_scanner_returns_invalid_symbol_for_unknown_character(tmp_path, names):
    """Test if scanner returns INVALID for an unsupported character."""
    path = make_definition_file(tmp_path, "@")
    scanner = Scanner(path, names)
    symbol = scanner.get_symbol()

    assert symbol.type == scanner.INVALID
    assert symbol.id == "@"


def test_scanner_tracks_line_and_position(tmp_path, names):
    """Test if scanner stores line and column information on symbols."""
    path = make_definition_file(tmp_path, "DEVICES {\n    SW1")
    scanner = Scanner(path, names)

    first = scanner.get_symbol()
    scanner.get_symbol()
    third = scanner.get_symbol()

    assert first.line_number == 1
    assert first.position == 1
    assert third.line_number == 2
    assert third.position == 5


def test_print_current_line_marks_position(tmp_path, names, capsys):
    """Test if print_current_line marks the scanner position."""
    path = make_definition_file(tmp_path, "DEVICES {\n    SW1")
    scanner = Scanner(path, names)

    scanner.get_symbol()
    scanner.get_symbol()
    scanner.get_symbol()
    scanner.print_current_line()

    output = capsys.readouterr().out.splitlines()
    assert output[0] == "    SW1"
    assert output[1] == "      ^"


def test_print_line_with_pointer_marks_given_location(tmp_path, names, capsys):
    """Test if print_line_with_pointer marks an arbitrary source location."""
    path = make_definition_file(tmp_path, "DEVICES {\n    SW1")
    scanner = Scanner(path, names)

    scanner.print_line_with_pointer(2, 5)

    output = capsys.readouterr().out.splitlines()
    assert output[0] == "    SW1"
    assert output[1] == "    ^"


def test_scanner_file_not_found_raises_oserror(names):
    """Test if scanner reports file-opening errors through OSError."""
    with pytest.raises(OSError):
        Scanner(Path("missing_definition_file.txt"), names)
