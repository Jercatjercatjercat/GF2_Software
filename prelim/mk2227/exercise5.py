def get_next_number(file_object):
    """Return the next number and the next non-digit character."""
    character = get_next_character(file_object)

    while character != "" and not character.isdigit():
        character = get_next_character(file_object)

    if character == "":
        return [None, ""]

    number_string = ""

    while character != "" and character.isdigit():
        number_string += character
        character = get_next_character(file_object)

    return [int(number_string), character]

file_object.seek(0)

number, character = get_next_number(file_object)

while number is not None:
    print(number)
    if character == "":
        break
    number, character = get_next_number(file_object)