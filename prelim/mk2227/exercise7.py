"""Exercise 7: use a simple name table to filter bad names."""

import sys


class MyNames:
    """Map name strings to unique integer IDs."""

    def __init__(self):
        """Initialise an empty name table."""
        self.names = []

    def lookup(self, name_string):
        """Return the ID for name_string, adding it if necessary."""
        if name_string in self.names:
            return self.names.index(name_string)

        self.names.append(name_string)
        return len(self.names) - 1

    def get_string(self, name_id):
        """Return the string for name_id, or None if the ID is invalid."""
        if isinstance(name_id, int) and 0 <= name_id < len(self.names):
            return self.names[name_id]

        return None


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
    """Print all names except the bad names."""
    if len(sys.argv) != 2:
        print("Usage: python exercise7.py <file_path>")
        sys.exit(1)

    path = sys.argv[1]
    file_object = open_file(path)

    names = MyNames()

    bad_name_ids = [
        names.lookup("Ghastly"),
        names.lookup("Terrible"),
        names.lookup("Horrid"),
    ]

    file_object.seek(0)
    name, next_character = get_next_name(file_object)

    while name is not None:
        name_id = names.lookup(name)

        if name_id not in bad_name_ids:
            print(names.get_string(name_id))

        if next_character == "":
            break

        name, next_character = get_next_name(file_object)

    file_object.close()


if __name__ == "__main__":
    main()