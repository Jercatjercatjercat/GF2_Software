"""Exercise 2: open a file supplied as a command-line argument."""

import sys


def open_file(path):
    """Open the file at path for reading and return the file object."""
    try:
        return open(path, "r", encoding="utf-8")
    except OSError as error:
        print(f"Error: could not open file '{path}': {error}")
        sys.exit(1)


def main():
    """Extract the file path from the command line and open the file."""
    if len(sys.argv) != 2:
        print("Usage: python exercise2.py <file_path>")
        sys.exit(1)

    path = sys.argv[1]
    print(path)

    file_object = open_file(path)
    file_object.close()


if __name__ == "__main__":
    main()