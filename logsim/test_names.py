"""Test the names module."""
import pytest
from names import Names


@pytest.fixture
def new_names():
    """Return a new instance of the Names class."""
    return Names()


def test_lookup_adds_and_returns_ids(new_names):
    """Test if lookup correctly adds names and returns their unique IDs."""
    ids = new_names.lookup(["G1", "Sw1", "Clock1"])
    assert ids == [0, 1, 2]

    # Looking up existing names should return the same IDs
    ids2 = new_names.lookup(["Sw1", "G1"])
    assert ids2 == [1, 0]

    # Looking up a mix of new and existing names
    ids3 = new_names.lookup(["G1", "NewDevice", "Sw1"])
    assert ids3 == [0, 3, 1]


def test_query_returns_correct_id_or_none(new_names):
    """Test if query returns correct name IDs or None if not present."""
    # Table is empty initially
    assert new_names.query("G1") is None

    # Add G1 and check again
    new_names.lookup(["G1"])
    assert new_names.query("G1") == 0
    assert new_names.query("Sw1") is None


def test_get_name_string_returns_correct_string_or_none(new_names):
    """Test if get_name_string retrieves the correct name or returns None."""
    new_names.lookup(["G1", "Sw1"])
    assert new_names.get_name_string(0) == "G1"
    assert new_names.get_name_string(1) == "Sw1"

    # Out of bounds IDs should return None
    assert new_names.get_name_string(2) is None
    assert new_names.get_name_string(-1) is None


def test_unique_error_codes(new_names):
    """Test unique_error_codes returns unique error codes on demand."""
    codes1 = new_names.unique_error_codes(3)
    assert list(codes1) == [0, 1, 2]

    codes2 = new_names.unique_error_codes(2)
    assert list(codes2) == [3, 4]


def test_lookup_input_validation(new_names):
    """Test if lookup raises TypeErrors for invalid inputs."""
    # Must be a list
    with pytest.raises(TypeError):
        new_names.lookup("G1")

    with pytest.raises(TypeError):
        new_names.lookup(123)

    # Elements in list must be strings
    with pytest.raises(TypeError):
        new_names.lookup(["G1", 123])


def test_query_input_validation(new_names):
    """Test if query raises TypeErrors for invalid inputs."""
    with pytest.raises(TypeError):
        new_names.query(123)

    with pytest.raises(TypeError):
        new_names.query(["G1"])


def test_get_name_string_input_validation(new_names):
    """Test if get_name_string raises TypeErrors for invalid inputs."""
    with pytest.raises(TypeError):
        new_names.get_name_string("0")

    with pytest.raises(TypeError):
        new_names.get_name_string(1.5)


def test_unique_error_codes_validation(new_names):
    """Test if unique_error_codes raises TypeErrors for invalid inputs."""
    with pytest.raises(TypeError):
        new_names.unique_error_codes("3")


def test_names_isolation():
    """Test that two separate Names instances are isolated from each other."""
    names1 = Names()
    names2 = Names()

    names1.lookup(["G1"])
    assert names1.query("G1") == 0
    assert names2.query("G1") is None
