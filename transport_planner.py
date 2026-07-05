from itertools import combinations, permutations
from typing import Dict, List, Tuple, Any


def route_duration(route: List[str], duration_matrix: Dict[Tuple[str, str], int]) -> int:
    total = 0

    for a, b in zip(route, route[1:]):
        total += duration_matrix.get((a, b), 10**9)

    return total


def best_ordered_route(
    start: str,
    stops: List[str],
    end: str,
    duration_matrix: Dict[Tuple[str, str], int],
) -> Tuple[List[str], int]:
    """
    Finds the fastest:
        start -> stops in best order -> end

    This is safe because each car has only up to 4 passengers.
    """

    if not stops:
        route = [start, end]
        return route, route_duration(route, duration_matrix)

    best_route = None
    best_duration = float("inf")

    for order in permutations(stops):
        route = [start, *order, end]
        duration = route_duration(route, duration_matrix)

        if duration < best_duration:
            best_route = route
            best_duration = duration

    return best_route, int(best_duration)


def possible_groups(passengers: List[dict], max_size: int) -> List[Tuple[dict, ...]]:
    groups = []

    for size in range(1, max_size + 1):
        groups.extend(combinations(passengers, size))

    return groups


def group_has_people(group: Tuple[dict, ...], names: List[str]) -> bool:
    group_names = {person["name"] for person in group}
    return all(name in group_names for name in names)


def group_has_any(group: Tuple[dict, ...], names: List[str]) -> bool:
    group_names = {person["name"] for person in group}
    return any(name in group_names for name in names)


def group_is_valid(driver: dict, group: Tuple[dict, ...], rules: dict) -> bool:
    group_names = {person["name"] for person in group}

    if rules.get("same_gender_only", False):
        for passenger in group:
            if passenger["gender"] != driver["gender"]:
                return False

    for pair in rules.get("cannot_pair", []):
        a, b = pair

        if a == driver["name"] and b in group_names:
            return False

        if b == driver["name"] and a in group_names:
            return False

        if a in group_names and b in group_names:
            return False

    for must_group in rules.get("must_together", []):
        present = [name for name in must_group if name in group_names]

        if present and len(present) != len(must_group):
            return False

    return True


def evaluate_single_place_trip(
    driver: dict,
    passengers: List[dict],
    place: dict,
    duration_matrix: Dict[Tuple[str, str], int],
) -> dict:
    driver_home = driver["home_address"]
    passenger_homes = [passenger["home_address"] for passenger in passengers]
    place_address = place["address"]

    pickup_route, pickup_duration = best_ordered_route(
        start=driver_home,
        stops=passenger_homes,
        end=place_address,
        duration_matrix=duration_matrix,
    )

    dropoff_route, dropoff_duration = best_ordered_route(
        start=place_address,
        stops=passenger_homes,
        end=driver_home,
        duration_matrix=duration_matrix,
    )

    return {
        "driver": driver["name"],
        "passengers": [p["name"] for p in passengers],
        "pickup_path": {
            "description": "Driver home to passenger homes to place",
            "route": pickup_route,
            "estimated_duration_min": round(pickup_duration / 60),
        },
        "dropoff_path": {
            "description": "Place to passenger homes to driver home",
            "route": dropoff_route,
            "estimated_duration_min": round(dropoff_duration / 60),
        },
        "total_estimated_duration_min": round(
            (pickup_duration + dropoff_duration) / 60
        ),
    }


def evaluate_multiple_places_trip(
    driver: dict,
    passengers: List[dict],
    places: List[dict],
    duration_matrix: Dict[Tuple[str, str], int],
) -> dict:
    driver_home = driver["home_address"]
    passenger_homes = [passenger["home_address"] for passenger in passengers]

    place_addresses = [place["address"] for place in places]
    first_place = place_addresses[0]
    final_place = place_addresses[-1]

    pickup_route, pickup_duration = best_ordered_route(
        start=driver_home,
        stops=passenger_homes,
        end=first_place,
        duration_matrix=duration_matrix,
    )

    place_to_place_route = place_addresses
    place_to_place_duration = route_duration(
        place_to_place_route,
        duration_matrix,
    )

    dropoff_route, dropoff_duration = best_ordered_route(
        start=final_place,
        stops=passenger_homes,
        end=driver_home,
        duration_matrix=duration_matrix,
    )

    return {
        "driver": driver["name"],
        "passengers": [p["name"] for p in passengers],
        "pickup_path": {
            "description": "Driver home to passenger homes to first place",
            "route": pickup_route,
            "estimated_duration_min": round(pickup_duration / 60),
        },
        "place_to_place_path": {
            "description": "First place to final place in listed order",
            "route": place_to_place_route,
            "estimated_duration_min": round(place_to_place_duration / 60),
        },
        "dropoff_path": {
            "description": "Final place to passenger homes to driver home",
            "route": dropoff_route,
            "estimated_duration_min": round(dropoff_duration / 60),
        },
        "total_estimated_duration_min": round(
            (pickup_duration + place_to_place_duration + dropoff_duration) / 60
        ),
    }


def option_cost(
    trip: dict,
    driver: dict,
    group: Tuple[dict, ...],
    rules: dict,
    preferred_driver_bonus_minutes: int,
) -> int:
    cost = trip["total_estimated_duration_min"]

    preferred_driver = rules.get("preferred_driver", {})

    for passenger in group:
        preferred = preferred_driver.get(passenger["name"])

        if preferred and preferred == driver["name"]:
            cost -= preferred_driver_bonus_minutes

    return max(cost, 0)


def build_car_options(
    drivers: List[dict],
    passengers: List[dict],
    places: List[dict],
    trip_type: str,
    duration_matrix: Dict[Tuple[str, str], int],
    rules: dict,
    max_passengers_per_car: int,
    preferred_driver_bonus_minutes: int,
) -> List[dict]:
    options = []

    for driver in drivers:
        capacity = min(
            int(driver.get("car_capacity", 0)),
            max_passengers_per_car,
        )

        if capacity <= 0:
            continue

        for group in possible_groups(passengers, capacity):
            if not group_is_valid(driver, group, rules):
                continue

            if trip_type == "single_place":
                trip = evaluate_single_place_trip(
                    driver=driver,
                    passengers=list(group),
                    place=places[0],
                    duration_matrix=duration_matrix,
                )
            elif trip_type == "multiple_places":
                trip = evaluate_multiple_places_trip(
                    driver=driver,
                    passengers=list(group),
                    places=places,
                    duration_matrix=duration_matrix,
                )
            else:
                raise ValueError(f"Unknown trip_type: {trip_type}")

            options.append(
                {
                    "driver": driver["name"],
                    "passengers": tuple(p["name"] for p in group),
                    "cost": option_cost(
                        trip=trip,
                        driver=driver,
                        group=group,
                        rules=rules,
                        preferred_driver_bonus_minutes=preferred_driver_bonus_minutes,
                    ),
                    "trip": trip,
                }
            )

    return options


from ortools.sat.python import cp_model


def choose_best_options_ortools(
    options: List[dict],
    passengers: List[dict],
    outside_penalty_minutes: int,
) -> Tuple[List[dict], List[str]]:
    model = cp_model.CpModel()

    selected = [
        model.NewBoolVar(f"select_option_{i}")
        for i in range(len(options))
    ]

    passenger_names = [p["name"] for p in passengers]
    driver_names = sorted({option["driver"] for option in options})

    passenger_assigned = {
        name: model.NewBoolVar(f"passenger_assigned_{name}")
        for name in passenger_names
    }

    # Each driver can be used at most once.
    for driver in driver_names:
        model.Add(
            sum(
                selected[i]
                for i, option in enumerate(options)
                if option["driver"] == driver
            ) <= 1
        )

    # Each passenger can be used at most once.
    for passenger in passenger_names:
        related_options = [
            selected[i]
            for i, option in enumerate(options)
            if passenger in option["passengers"]
        ]

        model.Add(sum(related_options) == passenger_assigned[passenger])

    # Minimize route cost plus outside penalty.
    objective = []

    for i, option in enumerate(options):
        objective.append(option["cost"] * selected[i])

    for passenger in passenger_names:
        objective.append(
            outside_penalty_minutes * (1 - passenger_assigned[passenger])
        )

    model.Minimize(sum(objective))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10

    status = solver.Solve(model)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        return [], passenger_names

    chosen = []

    for i, option in enumerate(options):
        if solver.Value(selected[i]):
            chosen.append(option)

    assigned = set()

    for option in chosen:
        assigned.update(option["passengers"])

    outside = sorted(set(passenger_names) - assigned)

    return chosen, outside


def plan_transport(
    people: List[dict],
    places: List[dict],
    rules: dict,
    trip_type: str,
    duration_matrix: Dict[Tuple[str, str], int],
    max_passengers_per_car: int = 4,
    outside_penalty_minutes: int = 10000,
    preferred_driver_bonus_minutes: int = 20,
) -> dict:

    if trip_type not in {"single_place", "multiple_places"}:
        raise ValueError(f"Unknown trip_type: {trip_type}")
    
    unavailable = set(rules.get("unavailable_drivers", []))

    drivers = [
        person for person in people
        if person["can_drive"] is True and person["name"] not in unavailable
    ]

    passengers = [
        person for person in people
        if person["can_drive"] is False
    ]

    options = build_car_options(
        drivers=drivers,
        passengers=passengers,
        places=places,
        trip_type=trip_type,
        duration_matrix=duration_matrix,
        rules=rules,
        max_passengers_per_car=max_passengers_per_car,
        preferred_driver_bonus_minutes=preferred_driver_bonus_minutes,
    )

    selected_options, outside = choose_best_options_ortools(
        options=options,
        passengers=passengers,
        outside_penalty_minutes=outside_penalty_minutes,
    )

    cars = [option["trip"] for option in selected_options]

    outside_due_to_no_space = [
        {
            "name": name,
            "reason": "No valid available car space or no valid rule-compatible car",
        }
        for name in outside
    ]

    warnings = [
        "This is only a proposed arrangement.",
        "Pickup route is optimized separately from drop-off route.",
        "Passengers may be outside if there is insufficient valid car space.",
    ]

    if unavailable:
        warnings.append(
            "Unavailable drivers excluded: " + ", ".join(sorted(unavailable))
        )

    return {
        "trip_type": trip_type,
        "summary": {
            "total_people": len(people),
            "total_drivers_available": len(drivers),
            "total_passengers": len(passengers),
            "total_passengers_assigned": len(passengers) - len(outside),
            "total_passengers_outside": len(outside),
        },
        "places": places,
        "cars": cars,
        "outside_due_to_no_space": outside_due_to_no_space,
        "warnings": warnings,
    }