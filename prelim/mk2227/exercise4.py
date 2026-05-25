def get_next_non_whitespace_character(file_object):
    """Return the next non-whitespace character from the file."""
    character = get_next_character(file_object)

    while character != "" and character.isspace():
        character = get_next_character(file_object)

    return character

file_object.seek(0)

character = get_next_non_whitespace_character(file_object)

while character != "":
    print(character, end="")
    character = get_next_non_whitespace_character(file_object)