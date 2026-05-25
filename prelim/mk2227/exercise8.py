"""Tests for the MyNames class."""

from mynames import MyNames


def test_lookup_adds_new_name():
    """Test that lookup adds a new name and returns ID 0."""
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
    """Test that duplicate names are not added twice."""
    names = MyNames()

    first_id = names.lookup("Alice")
    second_id = names.lookup("Alice")

    assert first_id == second_id
    assert len(names.names) == 1


def test_get_string_invalid_id():
    """Test that invalid IDs return None."""
    names = MyNames()

    names.lookup("Alice")

    assert names.get_string(-1) is None
    assert names.get_string(1) is None
    assert names.get_string("not_an_integer") is None


def test_lookup_is_case_sensitive():
    """Test that names with different cases are different."""
    names = MyNames()

    assert names.lookup("alice") == 0
    assert names.lookup("Alice") == 1