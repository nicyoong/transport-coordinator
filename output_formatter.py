import csv
import json
from pathlib import Path


def write_json_result(result: dict, output_path: str | Path) -> Path:
    path = Path(output_path)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(result, output_file, indent=2)
        output_file.write("\n")
    return path


def passengers_in_route_order(
    car: dict,
    path: dict,
    people: list[dict],
) -> list[str]:
    people_by_name = {person["name"]: person for person in people}
    names_by_address: dict[str, list[str]] = {}

    for name in car["passengers"]:
        address = people_by_name[name]["home_address"]
        names_by_address.setdefault(address, []).append(name)

    ordered_names = []
    for address in path["route"][1:-1]:
        names = names_by_address.get(address, [])
        if names:
            ordered_names.append(names.pop(0))

    return ordered_names


def write_csv_result(
    result: dict,
    people: list[dict],
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    driver_names = [
        person["name"]
        for person in people
        if person["can_drive"]
    ]
    passengers_by_driver = {name: [] for name in driver_names}
    duty = result.get("duty", "both")
    path_key = "dropoff_path" if duty == "dropoff" else "pickup_path"

    for car in result["cars"]:
        passengers_by_driver[car["driver"]] = passengers_in_route_order(
            car,
            car[path_key],
            people,
        )

    passenger_row_count = max(
        (len(names) for names in passengers_by_driver.values()),
        default=0,
    )

    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(["Driver", *driver_names])
        for passenger_index in range(passenger_row_count):
            writer.writerow(
                [
                    "",
                    *[
                        (
                            passengers_by_driver[driver][passenger_index]
                            if passenger_index
                            < len(passengers_by_driver[driver])
                            else ""
                        )
                        for driver in driver_names
                    ],
                ]
            )

    return path


def format_transport_plan(result: dict, people: list[dict]) -> str:
    duty = result.get("duty", "both")

    lines = [
        "TRANSPORT PLAN",
        "==============",
        "",
    ]

    for car_number, car in enumerate(result["cars"], start=1):
        lines.extend(
            [
                f"CAR {car_number}",
                f"  Driver: {car['driver']}",
            ]
        )
        if duty in {"pickup", "both"}:
            pickup_order = passengers_in_route_order(
                car,
                car["pickup_path"],
                people,
            )
            pickup_label = (
                "Pickup passenger order"
                if duty == "both"
                else "Passengers in pickup order"
            )
            lines.append(
                f"  {pickup_label}: "
                + (" -> ".join(pickup_order) if pickup_order else "None")
            )
        if duty in {"dropoff", "both"}:
            dropoff_order = passengers_in_route_order(
                car,
                car["dropoff_path"],
                people,
            )
            dropoff_label = (
                "Drop-off passenger order"
                if duty == "both"
                else "Passengers in drop-off order"
            )
            lines.append(
                f"  {dropoff_label}: "
                + (" -> ".join(dropoff_order) if dropoff_order else "None")
            )

        if duty == "pickup":
            selected_duration = car["pickup_path"]["estimated_duration_min"]
        elif duty == "dropoff":
            selected_duration = car["dropoff_path"]["estimated_duration_min"]
        else:
            selected_duration = car["total_estimated_duration_min"]
        lines.extend(
            [
                (
                    "  Total estimated driving time: "
                    f"{selected_duration} min"
                ),
                "",
            ]
        )

    assigned_drivers = {car["driver"] for car in result["cars"]}
    unused_drivers = [
        person["name"]
        for person in people
        if person["can_drive"] and person["name"] not in assigned_drivers
    ]
    lines.extend(
        [
            "DRIVERS WITHOUT ASSIGNMENTS",
            "  " + (", ".join(unused_drivers) if unused_drivers else "None"),
            "",
            "UNASSIGNED PASSENGERS",
        ]
    )
    outside = result["outside_due_to_no_space"]
    if outside:
        lines.extend(
            f"  - {passenger['name']}: {passenger['reason']}"
            for passenger in outside
        )
    else:
        lines.append("  None")
    lines.append("")

    if result.get("warnings"):
        lines.extend(["NOTES"])
        lines.extend(f"  - {warning}" for warning in result["warnings"])

    return "\n".join(lines)
