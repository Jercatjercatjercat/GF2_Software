"""Exercise 3: read and print a file one character at a time."""

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


def main():
    """Print the contents of the file one character at a time."""
    if len(sys.argv) != 2:
        print("Usage: python exercise3.py <file_path>")
        sys.exit(1)

    path = sys.argv[1]
    file_object = open_file(path)

    character = get_next_character(file_object)

    while character != "":
        print(character, end="")
        character = get_next_character(file_object)

    file_object.close()


if __name__ == "__main__":
    main()