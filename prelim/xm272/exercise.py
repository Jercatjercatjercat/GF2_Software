#!/usr/bin/env python3
"""Preliminary exercises for Part IIA Project GF2......."""
import sys

from mynames import MyNames


def open_file(path):
    """Open and return the file specified by path."""
    try:
        return open(path, encoding="utf-8")
    except OSError as exc:
        print(f"Error: could not open {path!r} for reading: {exc}")
        sys.exit(1)


def get_next_character(input_file):
    """Read and return the next character in input_file."""
    return input_file.read(1)


def get_next_non_whitespace_character(input_file):
    """Seek and return the next non-whitespace character in input_file."""
    character = get_next_character(input_file)
    while character != "" and character.isspace():
        character = get_next_character(input_file)
    return character


def get_next_number(input_file):
    """Seek the next number in input_file.

    Return the number (or None) and the next non-numeric character.
    """
    character = get_next_character(input_file)
    while character != "" and not character.isdigit():
        character = get_next_character(input_file)

    if character == "":
        return [None, ""]

    number_string = ""
    while character != "" and character.isdigit():
        number_string += character
        character = get_next_character(input_file)

    return [int(number_string), character]


def get_next_name(input_file):
    """Seek the next name string in input_file.

    Return the name string (or None) and the next non-alphanumeric character.
    """
    character = get_next_character(input_file)
    while character != "" and not character.isalpha():
        character = get_next_character(input_file)

    if character == "":
        return [None, ""]

    name_string = ""
    while character != "" and character.isalnum():
        name_string += character
        character = get_next_character(input_file)

    return [name_string, character]


def main():
    """Preliminary exercises for Part IIA Project GF2."""
    # Check command line arguments
    arguments = sys.argv[1:]
    if len(arguments) != 1:
        print("Error! One command line argument is required.")
        sys.exit()

    else:
        path = arguments[0]
        print("\nNow opening file...")
        print(path)
        input_file = open_file(path)

        print("\nNow reading file...")
        # Print out all the characters in the file, until the end of file
        character = get_next_character(input_file)
        while character != "":
            print(character, end="")
            character = get_next_character(input_file)

        print("\nNow skipping spaces...")
        # Print out all the characters in the file, without spaces
        input_file.seek(0)
        character = get_next_non_whitespace_character(input_file)
        while character != "":
            print(character, end="")
            character = get_next_non_whitespace_character(input_file)

        print("\nNow reading numbers...")
        # Print out all the numbers in the file
        input_file.seek(0)
        number, character = get_next_number(input_file)
        while number is not None:
            print(number)
            number, character = get_next_number(input_file)

        print("\nNow reading names...")
        # Print out all the names in the file
        input_file.seek(0)
        name_string, character = get_next_name(input_file)
        while name_string is not None:
            print(name_string)
            name_string, character = get_next_name(input_file)

        print("\nNow censoring bad names...")
        # Print out only the good names in the file
        name = MyNames()
        bad_name_ids = [name.lookup("Terrible"), name.lookup("Horrid"),
                        name.lookup("Ghastly"), name.lookup("Awful")]
        input_file.seek(0)
        name_string, character = get_next_name(input_file)
        while name_string is not None:
            name_id = name.lookup(name_string)
            if name_id not in bad_name_ids:
                print(name.get_string(name_id))
            name_string, character = get_next_name(input_file)


if __name__ == "__main__":
    main()
