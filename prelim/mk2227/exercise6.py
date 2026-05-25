def get_next_name(file_object):
    """Return the next name and the next non-alphanumeric character."""
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

file_object.seek(0)

name, character = get_next_name(file_object)

while name is not None:
    print(name)
    if character == "":
        break
    name, character = get_next_name(file_object)

    