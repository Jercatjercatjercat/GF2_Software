"""Exercise 8: pytest tests for the MyNames class."""

from exercise7 import MyNames


def test_lookup_adds_first_name():
    """Test that the first new name gets ID 0."""
    names = MyNames()

    assert names.lookup("Alice") == 0
    assert names.get_string(0) == "Alice"


def test_lookup_adds_multiple_names():
    """Test that different names get different IDs."""
    names = MyNames()

    assert names.lookup("Alice") == 0
    assert names.lookup("Bob") == 1
    assert names.lookup("Charlie") == 2

    assert names.get_string(0) == "Alice"
    assert names.get_string(1) == "Bob"
    assert names.get_string(2) == "Charlie"


def test_lookup_existing_name_returns_same_id():
    """Test that looking up the same name returns the same ID."""
    names = MyNames()

    first_id = names.lookup("Alice")
    second_id = names.lookup("Alice")

    assert first_id == second_id
    assert len(names.names) == 1


def test_get_string_invalid_negative_id():
    """Test that a negative ID returns None."""
    names = MyNames()

    names.lookup("Alice")

    assert names.get_string(-1) is None


def test_get_string_invalid_large_id():
    """Test that an out-of-range ID returns None."""
    names = MyNames()

    names.lookup("Alice")

    assert names.get_string(1) is None


def test_get_string_invalid_non_integer_id():
    """Test that a non-integer ID returns None."""
    names = MyNames()

    names.lookup("Alice")

    assert names.get_string("Alice") is None


def test_lookup_is_case_sensitive():
    """Test that names with different capitalisation are different."""
    names = MyNames()

    assert names.lookup("alice") == 0
    assert names.lookup("Alice") == 1