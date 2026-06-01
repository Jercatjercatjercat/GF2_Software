"""Exercise 4: read and print only non-whitespace characters."""

import sys


def open_file(path):
    """Open the file at path for reading and return the file object."""
    try:
        return open(path, "r", encoding="utf-8")
    except OSError as error:
        print(f"Error: could not open file '{path}': {error}")
        sys.exit(1)


def get_next_character(file_object):
    """Return the next character from the file."""
    return file_object.read(1)


def get_next_non_whitespace_character(file_object):
    """Return the next non-whitespace character from the file."""
    character = get_next_character(file_object)

    while character != "" and character.isspace():
        character = get_next_character(file_object)

    return character


def main():
    """Print the file contents without whitespace."""
    if len(sys.argv) != 2:
        print("Usage: python exercise4.py <file_path>")
        sys.exit(1)

    path = sys.argv[1]
    file_object = open_file(path)

    file_object.seek(0)
    character = get_next_non_whitespace_character(file_object)

    while character != "":
        print(character, end="")
        character = get_next_non_whitespace_character(file_object)

    file_object.close()


if __name__ == "__main__":
    main()