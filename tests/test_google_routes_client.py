from unittest.mock import Mock

import pytest

from google_routes_client import GoogleRoutesClient
from routes_usage import RoutesUsageLimitError, RoutesUsageStore


def mock_routes_response():
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = []
    return response


def computed_routes_response(*args, **kwargs):
    payload = kwargs["json"]
    elements = []

    for origin_index in range(len(payload["origins"])):
        for destination_index in range(len(payload["destinations"])):
            elements.append(
                {
                    "originIndex": origin_index,
                    "destinationIndex": destination_index,
                    "duration": "60s",
                }
            )

    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = elements
    return response


def private_locations(count):
    return {
        f"location:{index}": f"Private Address {index}"
        for index in range(count)
    }


def test_compute_duration_matrix_allows_exactly_625_elements(monkeypatch):
    post = Mock(return_value=mock_routes_response())
    monkeypatch.setattr("google_routes_client.requests.post", post)
    locations = private_locations(25)

    GoogleRoutesClient("test-key").compute_duration_matrix(locations)

    post.assert_called_once()
    payload = post.call_args.kwargs["json"]
    assert len(payload["origins"]) == 25
    assert len(payload["destinations"]) == 25


def test_compute_duration_matrix_batches_and_merges_more_than_625_elements(
    monkeypatch,
):
    post = Mock(side_effect=computed_routes_response)
    monkeypatch.setattr("google_routes_client.requests.post", post)
    locations = private_locations(26)

    matrix = GoogleRoutesClient("test-key").compute_duration_matrix(locations)

    assert post.call_count == 4
    assert len(matrix) == 26 * 26
    assert matrix[("location:0", "location:25")] == 60
    assert matrix[("location:25", "location:0")] == 60
    assert matrix[("location:25", "location:25")] == 0

    for call in post.call_args_list:
        payload = call.kwargs["json"]
        element_count = (
            len(payload["origins"]) * len(payload["destinations"])
        )
        assert element_count <= GoogleRoutesClient.MAX_MATRIX_ELEMENTS


def test_compute_duration_matrix_sends_addresses_but_keys_by_location_id(
    monkeypatch,
):
    post = Mock(return_value=mock_routes_response())
    monkeypatch.setattr("google_routes_client.requests.post", post)
    locations = private_locations(25)

    GoogleRoutesClient("test-key").compute_duration_matrix(locations)

    payload = post.call_args.kwargs["json"]
    assert len(payload["origins"]) == 25
    assert len(payload["destinations"]) == 25
    assert payload["origins"][0]["waypoint"]["address"] == "Private Address 0"


@pytest.mark.parametrize(
    ("origin_count", "destination_count"),
    [
        (1, 625),
        (5, 125),
        (25, 25),
    ],
)
def test_validate_matrix_size_accepts_rectangular_625_element_requests(
    origin_count,
    destination_count,
):
    GoogleRoutesClient._validate_matrix_size(
        origin_count=origin_count,
        destination_count=destination_count,
    )


def test_validate_matrix_size_rejects_rectangular_request_over_limit():
    with pytest.raises(
        ValueError,
        match=r"26 origins x 25 destinations produces 650 elements",
    ):
        GoogleRoutesClient._validate_matrix_size(
            origin_count=26,
            destination_count=25,
        )


def test_compute_duration_matrix_records_usage(monkeypatch, tmp_path):
    post = Mock(side_effect=computed_routes_response)
    monkeypatch.setattr("google_routes_client.requests.post", post)
    store = RoutesUsageStore(tmp_path / "usage.sqlite3")

    GoogleRoutesClient(
        "test-key",
        usage_store=store,
        matrix_element_limit_30_days=100,
    ).compute_duration_matrix(private_locations(2))

    assert store.get_usage_summary() == {
        "window_days": 30,
        "api_key_last6": "all",
        "request_count": 1,
        "matrix_element_count": 4,
        "status_counts": {
            "reserved": 0,
            "succeeded": 1,
            "failed": 0,
        },
    }


def test_compute_duration_matrix_blocks_all_batches_before_api_call(
    monkeypatch,
    tmp_path,
):
    post = Mock(side_effect=computed_routes_response)
    monkeypatch.setattr("google_routes_client.requests.post", post)
    store = RoutesUsageStore(tmp_path / "usage.sqlite3")
    locations = private_locations(26)

    with pytest.raises(RoutesUsageLimitError, match=r"676 requested > 650"):
        GoogleRoutesClient(
            "test-key",
            usage_store=store,
            matrix_element_limit_30_days=650,
        ).compute_duration_matrix(locations)

    post.assert_not_called()
    assert store.get_usage_summary()["request_count"] == 0


def test_compute_duration_matrix_records_failed_attempt(monkeypatch, tmp_path):
    response = Mock()
    response.raise_for_status.side_effect = RuntimeError("API failed")
    post = Mock(return_value=response)
    monkeypatch.setattr("google_routes_client.requests.post", post)
    store = RoutesUsageStore(tmp_path / "usage.sqlite3")

    with pytest.raises(RuntimeError, match="API failed"):
        GoogleRoutesClient(
            "test-key",
            usage_store=store,
        ).compute_duration_matrix(private_locations(2))

    summary = store.get_usage_summary()
    assert summary["matrix_element_count"] == 4
    assert summary["status_counts"]["failed"] == 1
