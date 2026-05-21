"""Test the mynames module."""
import pytest

from mynames import MyNames


@pytest.fixture
def new_names():
    """Return a new names instance."""
    return MyNames()


@pytest.fixture
def name_string_list():
    """Return a list of example names."""
    return ["Alice", "Bob", "Eve"]


@pytest.fixture
def used_names(name_string_list):
    """Return a names instance, after three names have been added."""
    my_name = MyNames()
    for name in name_string_list:
        my_name.lookup(name)
    return my_name


def test_get_string_raises_exceptions(used_names):
    """Test if get_string raises expected exceptions."""
    with pytest.raises(TypeError):
        used_names.get_string(1.4)
    with pytest.raises(TypeError):
        used_names.get_string("hello")
    with pytest.raises(ValueError):
        used_names.get_string(-1)


@pytest.mark.parametrize("name_id, expected_string", [
    (0, "Alice"),
    (1, "Bob"),
    (2, "Eve"),
    (3, None)
])
def test_get_string(used_names, new_names, name_id, expected_string):
    """Test if get_string returns the expected string."""
    # Name is present
    assert used_names.get_string(name_id) == expected_string
    # Name is absent
    assert new_names.get_string(name_id) is None


def test_lookup_adds_new_name(new_names):
    """Test if lookup adds a new name and returns its ID."""
    name_id = new_names.lookup("Alice")

    assert name_id == 0
    assert new_names.get_string(name_id) == "Alice"


def test_lookup_returns_existing_name_id(new_names):
    """Test if lookup returns the same ID for an existing name."""
    first_id = new_names.lookup("Alice")
    second_id = new_names.lookup("Alice")

    assert second_id == first_id


def test_lookup_adds_names_in_order(new_names, name_string_list):
    """Test if lookup gives increasing IDs to new names."""
    for expected_id, name_string in enumerate(name_string_list):
        assert new_names.lookup(name_string) == expected_id


def test_lookup_can_store_distinct_names(new_names, name_string_list):
    """Test if lookup stores distinct names under distinct IDs."""
    name_ids = [new_names.lookup(name_string)
                for name_string in name_string_list]

    assert len(set(name_ids)) == len(name_string_list)
    for name_id, name_string in zip(name_ids, name_string_list):
        assert new_names.get_string(name_id) == name_string
