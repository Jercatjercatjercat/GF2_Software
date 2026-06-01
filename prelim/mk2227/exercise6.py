"""Exercise 6: find and print all names in a file."""

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


def get_next_name(file_object):
    """Return the next name and the following non-alphanumeric character."""
    character = get_next_character(file_object)

    while character != "" and not character.isalpha():
        character = get_next_character(file_object)

    if character == "":
        return [None, ""]

    name = ""

    while character != "" and character.isalnum():
        name += character
        character = get_next_character(file_object)

    return [name, character]


def main():
    """Print all names found in the file."""
    if len(sys.argv) != 2:
        print("Usage: python exercise6.py <file_path>")
        sys.exit(1)

    path = sys.argv[1]
    file_object = open_file(path)

    file_object.seek(0)
    name, next_character = get_next_name(file_object)

    while name is not None:
        print(name)

        if next_character == "":
            break

        name, next_character = get_next_name(file_object)

    file_object.close()


if __name__ == "__main__":
    main()