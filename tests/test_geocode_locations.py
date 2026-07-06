import csv
from unittest.mock import Mock

import pytest

from geocode_locations import (
    collect_unique_addresses,
    geocode_addresses,
    load_existing_locations,
    write_locations,
)
from google_geocoding_client import (
    GeocodingError,
    GoogleGeocodingClient,
)


def test_collect_unique_addresses_preserves_order_and_removes_duplicates(
    tmp_path,
):
    people_path = tmp_path / "people.csv"
    places_path = tmp_path / "places.csv"
    people_path.write_text(
        "name,home_address\n"
        "Driver,Shared address\n"
        "Passenger,Passenger address\n",
        encoding="utf-8",
    )
    places_path.write_text(
        "name,address\n"
        "Shared place,Shared address\n"
        "Destination,Destination address\n",
        encoding="utf-8",
    )

    addresses = collect_unique_addresses(people_path, places_path)

    assert addresses == [
        "Shared address",
        "Passenger address",
        "Destination address",
    ]


def test_google_geocoding_client_returns_normalized_first_result(
    monkeypatch,
):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "status": "OK",
        "results": [
            {
                "formatted_address": "Beta KL, Kuala Lumpur, Malaysia",
                "place_id": "test-place-id",
                "partial_match": True,
                "geometry": {
                    "location": {
                        "lat": 3.153,
                        "lng": 101.711,
                    },
                    "location_type": "ROOFTOP",
                },
            }
        ],
    }
    get = Mock(return_value=response)
    monkeypatch.setattr("google_geocoding_client.requests.get", get)

    result = GoogleGeocodingClient("test-key").geocode("Beta KL")

    assert result == {
        "address": "Beta KL",
        "formatted_address": "Beta KL, Kuala Lumpur, Malaysia",
        "latitude": 3.153,
        "longitude": 101.711,
        "place_id": "test-place-id",
        "location_type": "ROOFTOP",
        "partial_match": True,
    }
    assert get.call_args.kwargs["params"]["region"] == "my"


def test_google_geocoding_client_raises_for_unsuccessful_status(
    monkeypatch,
):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "status": "REQUEST_DENIED",
        "error_message": "Geocoding API is not enabled.",
    }
    monkeypatch.setattr(
        "google_geocoding_client.requests.get",
        Mock(return_value=response),
    )

    with pytest.raises(
        GeocodingError,
        match="Geocoding API is not enabled",
    ):
        GoogleGeocodingClient("test-key").geocode("Beta KL")


def test_geocode_addresses_reuses_complete_existing_locations():
    existing_location = {
        "address": "Cached address",
        "latitude": "3.1",
        "longitude": "101.7",
        "place_id": "cached-place-id",
    }
    client = Mock()

    locations = geocode_addresses(
        addresses=["Cached address"],
        client=client,
        existing={"Cached address": existing_location},
        delay_seconds=0,
    )

    assert locations == [existing_location]
    client.geocode.assert_not_called()


def test_geocode_addresses_fetches_missing_locations():
    fetched_location = {
        "address": "New address",
        "latitude": 3.2,
        "longitude": 101.8,
        "place_id": "new-place-id",
    }
    client = Mock()
    client.geocode.return_value = fetched_location

    locations = geocode_addresses(
        addresses=["New address"],
        client=client,
        existing={},
        delay_seconds=0,
    )

    assert locations == [fetched_location]
    client.geocode.assert_called_once_with(
        "New address",
        region_code="my",
    )


def test_write_and_load_locations_round_trip(tmp_path):
    output_path = tmp_path / "locations.csv"
    location = {
        "address": "Beta KL",
        "formatted_address": "Beta KL, Kuala Lumpur, Malaysia",
        "latitude": 3.153,
        "longitude": 101.711,
        "place_id": "test-place-id",
        "location_type": "ROOFTOP",
        "partial_match": False,
    }

    write_locations(output_path, [location])
    loaded = load_existing_locations(output_path)

    assert loaded["Beta KL"]["latitude"] == "3.153"
    assert loaded["Beta KL"]["longitude"] == "101.711"
    assert loaded["Beta KL"]["place_id"] == "test-place-id"

    with output_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["partial_match"] == "False"
