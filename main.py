import argparse
import yaml
import pandas as pd
import os
from dotenv import load_dotenv

from google_routes_client import GoogleRoutesClient
from output_formatter import (
    format_transport_plan,
    write_csv_result,
    write_json_result,
)
from routes_usage import RoutesUsageStore
from transport_planner import plan_transport

load_dotenv()

def parse_bool(value):
    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in ["true", "1", "yes", "y"]


def load_people(path: str) -> list[dict]:
    df = pd.read_csv(path)
    records = df.to_dict("records")

    for record in records:
        record["can_drive"] = parse_bool(record["can_drive"])
        record["car_capacity"] = int(record.get("car_capacity", 0))

    return records


def load_places(path: str) -> list[dict]:
    df = pd.read_csv(path)
    return df.to_dict("records")


def select_trip_places(all_places: list[dict], wanted_names: list[str]) -> list[dict]:
    by_name = {place["name"]: place for place in all_places}

    selected = []

    for name in wanted_names:
        if name not in by_name:
            raise ValueError(f"Place not found in places.csv: {name}")

        selected.append(by_name[name])

    return selected


def collect_addresses(people: list[dict], places: list[dict]) -> list[str]:
    addresses = []

    for person in people:
        addresses.append(person["home_address"])

    for place in places:
        addresses.append(place["address"])

    return list(dict.fromkeys(addresses))


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description="Build a pickup, drop-off, or combined transport plan.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""duties:
  pickup   Optimize and print pickup assignments.
  dropoff  Optimize and print drop-off assignments.
  both     Optimize pickup and drop-off together (default).
  help     Show this help message.

output files:
  transport_plan_pickup.json
  transport_plan_dropoff.json
  transport_plan_both.json
  transport_plan_pickup.csv
  transport_plan_dropoff.csv
  transport_plan_both.csv""",
    )
    parser.add_argument(
        "duty",
        nargs="?",
        choices=("pickup", "dropoff", "both", "help"),
        default="both",
        help="Duty to optimize, or help. Defaults to both.",
    )
    return parser


def parse_args(arguments=None):
    parser = build_argument_parser()
    return parser.parse_args(arguments)


def main():
    args = parse_args()
    if args.duty == "help":
        build_argument_parser().print_help()
        return

    google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not google_maps_api_key:
        raise ValueError("Missing GOOGLE_MAPS_API_KEY in .env file.")

    with open("config.yml", "r") as f:
        config = yaml.safe_load(f)

    with open("rules.yml", "r") as f:
        rules = yaml.safe_load(f)

    people = load_people("people.csv")
    all_places = load_places("places.csv")

    trip_type = config["trip"]["type"]
    trip_place_names = config["trip"]["places"]

    places = select_trip_places(all_places, trip_place_names)

    if trip_type == "single_place" and len(places) != 1:
        raise ValueError("single_place trips must have exactly one place.")

    if trip_type == "multiple_places" and len(places) < 2:
        raise ValueError("multiple_places trips must have two or more places.")

    addresses = collect_addresses(people, places)

    usage_store = RoutesUsageStore(
        config["settings"].get(
            "routes_usage_database",
            "routes_usage.sqlite3",
        )
    )
    routes_client = GoogleRoutesClient(
        api_key=google_maps_api_key,
        usage_store=usage_store,
        matrix_element_limit_30_days=config["settings"].get(
            "routes_matrix_element_limit_30_days",
            10000,
        ),
    )

    duration_matrix = routes_client.compute_duration_matrix(addresses)

    result = plan_transport(
        people=people,
        places=places,
        rules=rules,
        trip_type=trip_type,
        duration_matrix=duration_matrix,
        max_passengers_per_car=config["settings"].get("max_passengers_per_car", 4),
        outside_penalty_minutes=config["settings"].get(
            "outside_penalty_minutes",
            10000,
        ),
        preferred_driver_bonus_minutes=config["settings"].get(
            "preferred_driver_bonus_minutes",
            20,
        ),
        duty=args.duty,
    )

    result["routes_api_usage_30_days"] = usage_store.get_usage_summary(
        days=30,
        api_key_last6=routes_client.api_key_last6,
    )
    output_path = config["settings"].get(
        "output_json_path",
        "transport_plan_{duty}.json",
    ).replace("{duty}", args.duty)
    write_json_result(result, output_path)
    csv_output_path = config["settings"].get(
        "output_csv_path",
        "transport_plan_{duty}.csv",
    ).replace("{duty}", args.duty)
    write_csv_result(result, people, csv_output_path)
    print(format_transport_plan(result, people))


if __name__ == "__main__":
    main()
