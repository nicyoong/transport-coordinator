import csv
from unittest.mock import Mock

import pytest
import requests

from geocode_locations import (
    geocode_addresses,
    load_existing_locations,
    write_locations,
)
from google_geocoding_client import (
    GeocodingError,
    GoogleGeocodingClient,
)

def test_google_geocoding_client_returns_address_free_audit(
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

    result = GoogleGeocodingClient("test-key").geocode(
        "place:beta",
        "Beta KL",
    )

    assert result == {
        "location_id": "place:beta",
        "location_type": "ROOFTOP",
        "partial_match": True,
    }
    assert get.call_args.kwargs["params"]["region"] == "my"
    assert get.call_args.kwargs["params"]["address"] == "Beta KL"


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

    with pytest.raises(GeocodingError) as error:
        GoogleGeocodingClient("test-key").geocode(
            "place:beta",
            "Private Beta Address",
        )

    assert "REQUEST_DENIED" in str(error.value)
    assert "place:beta" in str(error.value)
    assert "Private Beta Address" not in str(error.value)


def test_google_geocoding_client_hides_address_and_key_in_http_errors(
    monkeypatch,
):
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError(
        "Failed URL contains Private Address and secret-key"
    )
    monkeypatch.setattr(
        "google_geocoding_client.requests.get",
        Mock(return_value=response),
    )

    with pytest.raises(GeocodingError) as error:
        GoogleGeocodingClient("secret-key").geocode(
            "home:private",
            "Private Address",
        )

    message = str(error.value)
    assert "home:private" in message
    assert "Private Address" not in message
    assert "secret-key" not in message


def test_geocode_addresses_reuses_complete_existing_locations():
    existing_location = {
        "location_id": "home:cached",
        "location_type": "ROOFTOP",
        "partial_match": "False",
    }
    client = Mock()

    locations = geocode_addresses(
        private_locations={"home:cached": "Cached address"},
        client=client,
        existing={"home:cached": existing_location},
        delay_seconds=0,
    )

    assert locations == [existing_location]
    client.geocode.assert_not_called()


def test_geocode_addresses_fetches_missing_locations():
    fetched_location = {
        "location_id": "home:new",
        "location_type": "ROOFTOP",
        "partial_match": False,
    }
    client = Mock()
    client.geocode.return_value = fetched_location

    locations = geocode_addresses(
        private_locations={"home:new": "New address"},
        client=client,
        existing={},
        delay_seconds=0,
    )

    assert locations == [fetched_location]
    client.geocode.assert_called_once_with(
        "home:new",
        "New address",
        region_code="my",
    )


def test_write_and_load_locations_round_trip(tmp_path):
    output_path = tmp_path / "locations.csv"
    location = {
        "location_id": "place:beta",
        "location_type": "ROOFTOP",
        "partial_match": False,
    }

    write_locations(output_path, [location])
    loaded = load_existing_locations(output_path)

    assert loaded["place:beta"]["location_type"] == "ROOFTOP"

    with output_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["partial_match"] == "False"
    assert "address" not in rows[0]
