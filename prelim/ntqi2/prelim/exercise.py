#!/usr/bin/env python3
"""Preliminary exercises for Part IIA Project GF2."""
import sys

from mynames import MyNames


def open_file(path):
    """Open and return the file specified by path."""
    try:
        input_file = open(path, "r")
        return input_file

    except OSError:
        print(f"Error! Could not open file: {path}")
        sys.exit()


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
    # Skip characters until we find a digit or reach the end of the file
    while character != "" and not character.isdigit():
        character = get_next_character(input_file)
    # If we reached the end of the file without finding a number
    if character == "":
        return [None, ""]
    # Build up the full number string
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
    # Skip characters until we find a letter or reach the end of the file
    while character != "" and not character.isalpha():
        character = get_next_character(input_file)
    # If we reached the end of the file without finding a name
    if character == "":
        return [None, ""]
    # Build up the full name string
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

        print("\nNow opening file...")
        # Print the path provided and try to open the file for reading
        path = arguments[0]
        print(f"File path: {path}")
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
        print()

        print("\nNow reading numbers...")
        # Print out all the numbers in the file
        input_file.seek(0)
        [number, next_character] = get_next_number(input_file)
        while number is not None:
            print(number)
            [number, next_character] = get_next_number(input_file)

        print("\nNow reading names...")
        # Print out all the names in the file
        input_file.seek(0)
        [name, next_character] = get_next_name(input_file)
        while name is not None:
            print(name)
            [name, next_character] = get_next_name(input_file)

        print("\nNow censoring bad names...")
        # Print out only the good names in the file
        input_file.seek(0)
        names = MyNames()
        bad_name_ids = [
            names.lookup("Terrible"),
            names.lookup("Horrid"),
            names.lookup("Ghastly"),
            names.lookup("Awful"),
        ]
        [name, next_character] = get_next_name(input_file)
        while name is not None:
            name_id = names.lookup(name)
            if name_id not in bad_name_ids:
                print(names.get_string(name_id))
            [name, next_character] = get_next_name(input_file)

        input_file.close()


if __name__ == "__main__":
    main()
