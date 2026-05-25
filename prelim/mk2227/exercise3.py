def get_next_character(file_object):
    """Return the next character from the file."""
    return file_object.read(1)

character = get_next_character(file_object)

while character != "":
    print(character, end="")
    character = get_next_character(file_object)