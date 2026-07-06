import csv
import json

from output_formatter import (
    format_transport_plan,
    write_csv_result,
    write_json_result,
)


def sample_result():
    return {
        "trip_type": "single_place",
        "summary": {
            "total_people": 3,
            "total_drivers_available": 2,
            "total_passengers": 1,
            "total_passengers_assigned": 1,
            "total_passengers_outside": 0,
        },
        "places": [
            {
                "name": "Office",
            }
        ],
        "cars": [
            {
                "driver": "Sarah",
                "passengers": ["Alice"],
                "pickup_path": {
                    "route": [
                        "home:sarah",
                        "home:alice",
                        "place:office",
                    ],
                    "estimated_duration_min": 12,
                },
                "dropoff_path": {
                    "route": [
                        "place:office",
                        "home:alice",
                        "home:sarah",
                    ],
                    "estimated_duration_min": 13,
                },
                "total_estimated_duration_min": 25,
            }
        ],
        "outside_due_to_no_space": [],
        "warnings": ["This is only a proposed arrangement."],
        "routes_api_usage_30_days": {
            "window_days": 30,
            "api_key_last6": "abc123",
            "request_count": 1,
            "matrix_element_count": 9,
            "status_counts": {
                "reserved": 0,
                "succeeded": 1,
                "failed": 0,
            },
        },
    }


def sample_people():
    return [
        {
            "name": "Sarah",
            "home_location_id": "home:sarah",
            "can_drive": True,
        },
        {
            "name": "Alice",
            "home_location_id": "home:alice",
            "can_drive": False,
        },
        {
            "name": "John",
            "home_location_id": "home:john",
            "can_drive": True,
        },
    ]


def test_format_transport_plan_is_human_readable():
    report = format_transport_plan(sample_result(), sample_people())

    assert "TRANSPORT PLAN" in report
    assert "CAR 1" in report
    assert "Driver: Sarah" in report
    assert "Pickup passenger order: Alice" in report
    assert "DRIVERS WITHOUT ASSIGNMENTS\n  John" in report
    assert "1 Driver Road" not in report
    assert "Matrix elements" not in report
    assert '"trip_type"' not in report


def test_write_json_result_preserves_raw_result(tmp_path):
    result = sample_result()
    output_path = write_json_result(result, tmp_path / "plan.json")

    with output_path.open(encoding="utf-8") as output_file:
        assert json.load(output_file) == result


def test_write_csv_result_uses_driver_columns_and_empty_cells(tmp_path):
    output_path = write_csv_result(
        sample_result(),
        sample_people(),
        tmp_path / "plan.csv",
    )

    with output_path.open(encoding="utf-8", newline="") as output_file:
        rows = list(csv.reader(output_file))

    assert rows == [
        ["Driver", "Sarah", "John"],
        ["", "Alice", ""],
    ]


def test_format_transport_plan_lists_unassigned_passenger_reason():
    result = sample_result()
    result["outside_due_to_no_space"] = [
        {
            "name": "Alice",
            "reason": "No valid available car space",
        }
    ]

    report = format_transport_plan(result, sample_people())

    assert "- Alice: No valid available car space" in report


def test_format_transport_plan_shows_only_selected_duty():
    result = sample_result()
    result["duty"] = "pickup"

    report = format_transport_plan(result, sample_people())

    assert "Passengers in pickup order: Alice" in report
    assert "Passengers in drop-off order" not in report
    assert "Total estimated driving time: 12 min" in report


def test_format_transport_plan_uses_optimized_passenger_order():
    result = sample_result()
    result["duty"] = "pickup"
    result["cars"][0]["passengers"] = ["Alice", "Bella"]
    result["cars"][0]["pickup_path"]["route"] = [
        "home:sarah",
        "home:bella",
        "home:alice",
        "place:office",
    ]
    people = [
        *sample_people(),
        {
            "name": "Bella",
            "home_location_id": "home:bella",
            "can_drive": False,
        },
    ]

    report = format_transport_plan(result, people)

    assert "Passengers in pickup order: Bella -> Alice" in report


def test_write_csv_result_uses_dropoff_order(tmp_path):
    result = sample_result()
    result["duty"] = "dropoff"
    result["cars"][0]["passengers"] = ["Alice", "Bella"]
    result["cars"][0]["dropoff_path"]["route"] = [
        "place:office",
        "home:bella",
        "home:alice",
        "home:sarah",
    ]
    people = [
        *sample_people(),
        {
            "name": "Bella",
            "home_location_id": "home:bella",
            "can_drive": False,
        },
    ]

    output_path = write_csv_result(
        result,
        people,
        tmp_path / "dropoff.csv",
    )

    with output_path.open(encoding="utf-8", newline="") as output_file:
        rows = list(csv.reader(output_file))

    assert rows == [
        ["Driver", "Sarah", "John"],
        ["", "Bella", ""],
        ["", "Alice", ""],
    ]
