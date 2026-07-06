import pytest

from transport_planner import (
    route_duration,
    best_ordered_route,
    group_is_valid,
    evaluate_single_place_trip,
    evaluate_multiple_places_trip,
    option_cost,
    build_car_options,
    choose_best_options_ortools,
    plan_transport,
)


def fake_matrix(addresses):
    """
    Creates a fake duration matrix.

    For basic tests, the duration between two different addresses is 10 minutes.
    Same address is 0 minutes.
    """
    matrix = {}

    for a in addresses:
        for b in addresses:
            if a == b:
                matrix[(a, b)] = 0
            else:
                matrix[(a, b)] = 600

    return matrix


@pytest.fixture
def sample_people():
    return [
        {
            "name": "Sarah",
            "gender": "F",
            "home_address": "Sarah home",
            "can_drive": True,
            "car_capacity": 4,
        },
        {
            "name": "Maya",
            "gender": "F",
            "home_address": "Maya home",
            "can_drive": True,
            "car_capacity": 2,
        },
        {
            "name": "Daniel",
            "gender": "M",
            "home_address": "Daniel home",
            "can_drive": True,
            "car_capacity": 4,
        },
        {
            "name": "Alice",
            "gender": "F",
            "home_address": "Alice home",
            "can_drive": False,
            "car_capacity": 0,
        },
        {
            "name": "Bella",
            "gender": "F",
            "home_address": "Bella home",
            "can_drive": False,
            "car_capacity": 0,
        },
        {
            "name": "Nina",
            "gender": "F",
            "home_address": "Nina home",
            "can_drive": False,
            "car_capacity": 0,
        },
        {
            "name": "John",
            "gender": "M",
            "home_address": "John home",
            "can_drive": False,
            "car_capacity": 0,
        },
        {
            "name": "Mark",
            "gender": "M",
            "home_address": "Mark home",
            "can_drive": False,
            "car_capacity": 0,
        },
    ]


@pytest.fixture
def sample_places():
    return [
        {
            "name": "Lunch Restaurant",
            "address": "Lunch address",
        },
        {
            "name": "Mall",
            "address": "Mall address",
        },
    ]


@pytest.fixture
def sample_rules():
    return {
        "same_gender_only": True,
        "must_together": [["Alice", "Bella"]],
        "cannot_pair": [["John", "Mark"]],
        "preferred_driver": {
            "Alice": "Sarah",
        },
        "unavailable_drivers": [],
    }


@pytest.fixture
def sample_duration_matrix(sample_people, sample_places):
    addresses = []

    for person in sample_people:
        addresses.append(person["home_address"])

    for place in sample_places:
        addresses.append(place["address"])

    return fake_matrix(addresses)


def test_route_duration_adds_each_leg(sample_duration_matrix):
    route = [
        "Sarah home",
        "Alice home",
        "Lunch address",
    ]

    result = route_duration(route, sample_duration_matrix)

    assert result == 1200


def test_best_ordered_route_returns_start_stops_and_end(sample_duration_matrix):
    route, duration = best_ordered_route(
        start="Sarah home",
        stops=["Alice home", "Bella home"],
        end="Lunch address",
        duration_matrix=sample_duration_matrix,
    )

    assert route[0] == "Sarah home"
    assert route[-1] == "Lunch address"
    assert set(route[1:-1]) == {"Alice home", "Bella home"}
    assert duration == 1800


def test_best_ordered_route_with_no_stops(sample_duration_matrix):
    route, duration = best_ordered_route(
        start="Sarah home",
        stops=[],
        end="Lunch address",
        duration_matrix=sample_duration_matrix,
    )

    assert route == ["Sarah home", "Lunch address"]
    assert duration == 600


def test_group_is_valid_allows_same_gender_group(sample_people, sample_rules):
    sarah = next(p for p in sample_people if p["name"] == "Sarah")
    alice = next(p for p in sample_people if p["name"] == "Alice")
    bella = next(p for p in sample_people if p["name"] == "Bella")

    assert group_is_valid(sarah, (alice, bella), sample_rules) is True


def test_group_is_valid_rejects_mixed_gender_when_same_gender_only(sample_people, sample_rules):
    sarah = next(p for p in sample_people if p["name"] == "Sarah")
    john = next(p for p in sample_people if p["name"] == "John")

    assert group_is_valid(sarah, (john,), sample_rules) is False


def test_group_is_valid_rejects_cannot_pair(sample_people, sample_rules):
    daniel = next(p for p in sample_people if p["name"] == "Daniel")
    john = next(p for p in sample_people if p["name"] == "John")
    mark = next(p for p in sample_people if p["name"] == "Mark")

    assert group_is_valid(daniel, (john, mark), sample_rules) is False


def test_group_is_valid_rejects_partial_must_together_group(sample_people, sample_rules):
    sarah = next(p for p in sample_people if p["name"] == "Sarah")
    alice = next(p for p in sample_people if p["name"] == "Alice")

    assert group_is_valid(sarah, (alice,), sample_rules) is False


def test_evaluate_single_place_trip(sample_people, sample_places, sample_duration_matrix):
    sarah = next(p for p in sample_people if p["name"] == "Sarah")
    alice = next(p for p in sample_people if p["name"] == "Alice")
    bella = next(p for p in sample_people if p["name"] == "Bella")
    lunch = sample_places[0]

    result = evaluate_single_place_trip(
        driver=sarah,
        passengers=[alice, bella],
        place=lunch,
        duration_matrix=sample_duration_matrix,
    )

    assert result["driver"] == "Sarah"
    assert result["passengers"] == ["Alice", "Bella"]

    assert result["pickup_path"]["route"][0] == "Sarah home"
    assert result["pickup_path"]["route"][-1] == "Lunch address"

    assert result["dropoff_path"]["route"][0] == "Lunch address"
    assert result["dropoff_path"]["route"][-1] == "Sarah home"

    # Pickup has 3 legs, dropoff has 3 legs.
    # Each leg is 10 minutes.
    assert result["total_estimated_duration_min"] == 60


def test_evaluate_multiple_places_trip(sample_people, sample_places, sample_duration_matrix):
    sarah = next(p for p in sample_people if p["name"] == "Sarah")
    alice = next(p for p in sample_people if p["name"] == "Alice")
    bella = next(p for p in sample_people if p["name"] == "Bella")

    result = evaluate_multiple_places_trip(
        driver=sarah,
        passengers=[alice, bella],
        places=sample_places,
        duration_matrix=sample_duration_matrix,
    )

    assert result["driver"] == "Sarah"
    assert result["passengers"] == ["Alice", "Bella"]

    assert result["pickup_path"]["route"][0] == "Sarah home"
    assert result["pickup_path"]["route"][-1] == "Lunch address"

    assert result["place_to_place_path"]["route"] == [
        "Lunch address",
        "Mall address",
    ]

    assert result["dropoff_path"]["route"][0] == "Mall address"
    assert result["dropoff_path"]["route"][-1] == "Sarah home"

    # Pickup: 3 legs = 30 min
    # Place-to-place: 1 leg = 10 min
    # Dropoff: 3 legs = 30 min
    assert result["total_estimated_duration_min"] == 70


def test_build_car_options_respects_rules(sample_people, sample_places, sample_rules, sample_duration_matrix):
    drivers = [p for p in sample_people if p["can_drive"]]
    passengers = [p for p in sample_people if not p["can_drive"]]

    options = build_car_options(
        drivers=drivers,
        passengers=passengers,
        places=[sample_places[0]],
        trip_type="single_place",
        duration_matrix=sample_duration_matrix,
        rules=sample_rules,
        max_passengers_per_car=4,
        preferred_driver_bonus_minutes=20,
    )

    assert options

    for option in options:
        passenger_set = set(option["passengers"])

        # Alice and Bella must appear together.
        assert not (
            ("Alice" in passenger_set) ^ ("Bella" in passenger_set)
        )

        # John and Mark cannot appear together.
        assert not (
            "John" in passenger_set and "Mark" in passenger_set
        )


def test_plan_transport_single_place(sample_people, sample_places, sample_rules, sample_duration_matrix):
    result = plan_transport(
        people=sample_people,
        places=[sample_places[0]],
        rules=sample_rules,
        trip_type="single_place",
        duration_matrix=sample_duration_matrix,
        max_passengers_per_car=4,
        outside_penalty_minutes=10000,
        preferred_driver_bonus_minutes=20,
    )

    assert result["trip_type"] == "single_place"
    assert result["duty"] == "both"
    assert result["summary"]["total_people"] == 8
    assert result["summary"]["total_drivers_available"] == 3
    assert result["summary"]["total_passengers"] == 5

    assert "cars" in result
    assert "outside_due_to_no_space" in result
    assert "warnings" in result


@pytest.mark.parametrize(
    ("duty", "expected_cost"),
    [
        ("pickup", 12),
        ("dropoff", 25),
        ("both", 37),
    ],
)
def test_option_cost_uses_selected_duty(duty, expected_cost):
    trip = {
        "pickup_path": {"estimated_duration_min": 12},
        "dropoff_path": {"estimated_duration_min": 25},
        "total_estimated_duration_min": 37,
    }

    assert option_cost(
        trip=trip,
        driver={"name": "Sarah"},
        group=(),
        rules={},
        preferred_driver_bonus_minutes=20,
        duty=duty,
    ) == expected_cost


def test_plan_transport_records_selected_duty(
    sample_people,
    sample_places,
    sample_rules,
    sample_duration_matrix,
):
    result = plan_transport(
        people=sample_people,
        places=[sample_places[0]],
        rules=sample_rules,
        trip_type="single_place",
        duration_matrix=sample_duration_matrix,
        duty="pickup",
    )

    assert result["duty"] == "pickup"
    assert any("pickup duty" in warning for warning in result["warnings"])


def test_plan_transport_multiple_places(sample_people, sample_places, sample_rules, sample_duration_matrix):
    result = plan_transport(
        people=sample_people,
        places=sample_places,
        rules=sample_rules,
        trip_type="multiple_places",
        duration_matrix=sample_duration_matrix,
        max_passengers_per_car=4,
        outside_penalty_minutes=10000,
        preferred_driver_bonus_minutes=20,
    )

    assert result["trip_type"] == "multiple_places"
    assert result["places"] == sample_places

    for car in result["cars"]:
        assert "pickup_path" in car
        assert "place_to_place_path" in car
        assert "dropoff_path" in car


def test_unavailable_driver_is_excluded(sample_people, sample_places, sample_rules, sample_duration_matrix):
    sample_rules["unavailable_drivers"] = ["Sarah"]

    result = plan_transport(
        people=sample_people,
        places=[sample_places[0]],
        rules=sample_rules,
        trip_type="single_place",
        duration_matrix=sample_duration_matrix,
        max_passengers_per_car=4,
        outside_penalty_minutes=10000,
        preferred_driver_bonus_minutes=20,
    )

    drivers_used = {car["driver"] for car in result["cars"]}

    assert "Sarah" not in drivers_used
    assert any("Sarah" in warning for warning in result["warnings"])


def test_outside_passengers_when_not_enough_space(sample_people, sample_places, sample_rules, sample_duration_matrix):
    """
    Force low capacity so someone must be outside.
    """
    for person in sample_people:
        if person["can_drive"]:
            person["car_capacity"] = 1

    result = plan_transport(
        people=sample_people,
        places=[sample_places[0]],
        rules=sample_rules,
        trip_type="single_place",
        duration_matrix=sample_duration_matrix,
        max_passengers_per_car=1,
        outside_penalty_minutes=10000,
        preferred_driver_bonus_minutes=20,
    )

    assert result["summary"]["total_passengers_outside"] > 0
    assert result["outside_due_to_no_space"]


def test_invalid_trip_type_raises_error(sample_people, sample_places, sample_rules, sample_duration_matrix):
    with pytest.raises(ValueError):
        plan_transport(
            people=sample_people,
            places=[sample_places[0]],
            rules=sample_rules,
            trip_type="invalid_trip_type",
            duration_matrix=sample_duration_matrix,
            max_passengers_per_car=4,
            outside_penalty_minutes=10000,
            preferred_driver_bonus_minutes=20,
        )
