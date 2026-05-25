"""Name table for the preliminary Python exercises."""


class MyNames:
    """Store names and map them to integer IDs."""

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
        """Return the name string for name_id, or None if invalid."""
        if isinstance(name_id, int) and 0 <= name_id < len(self.names):
            return self.names[name_id]

        return None
    
    file_object.seek(0)

names = MyNames()
bad_names = [
    names.lookup("Ghastly"),
    names.lookup("Terrible"),
    names.lookup("Horrid"),
]

name, character = get_next_name(file_object)

while name is not None:
    name_id = names.lookup(name)

    if name_id not in bad_names:
        print(names.get_string(name_id))

    if character == "":
        break

    name, character = get_next_name(file_object)