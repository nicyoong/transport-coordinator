import pytest

from private_locations import (
    load_private_locations,
    require_private_locations,
)


def test_load_private_locations_returns_id_to_address_mapping(tmp_path):
    path = tmp_path / "private_locations.csv"
    path.write_text(
        "location_id,address\n"
        'home:alice,"1 Private Road, Kuala Lumpur"\n',
        encoding="utf-8",
    )

    assert load_private_locations(path) == {
        "home:alice": "1 Private Road, Kuala Lumpur",
    }


def test_load_private_locations_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "private_locations.csv"
    path.write_text(
        "location_id,address\n"
        "home:alice,First address\n"
        "home:alice,Second address\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="repeats location_id"):
        load_private_locations(path)


def test_require_private_locations_returns_only_requested_records():
    private_locations = {
        "home:alice": "Private home",
        "place:lunch": "Private restaurant",
        "unused": "Unused address",
    }

    assert require_private_locations(
        ["home:alice", "place:lunch", "home:alice"],
        private_locations,
    ) == {
        "home:alice": "Private home",
        "place:lunch": "Private restaurant",
    }


def test_require_private_locations_reports_ids_without_addresses():
    with pytest.raises(ValueError) as error:
        require_private_locations(["home:missing"], {})

    assert "home:missing" in str(error.value)
