import argparse
import csv
import os
import time
from pathlib import Path
from typing import Dict, Iterable, List

from dotenv import load_dotenv

from google_geocoding_client import GoogleGeocodingClient


LOCATION_FIELDS = [
    "address",
    "formatted_address",
    "latitude",
    "longitude",
    "place_id",
    "location_type",
    "partial_match",
]


def read_address_column(path: Path, column: str) -> List[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames or column not in reader.fieldnames:
            raise ValueError(f"{path} does not contain a {column!r} column.")

        return [
            row[column].strip()
            for row in reader
            if row.get(column) and row[column].strip()
        ]


def collect_unique_addresses(
    people_path: Path,
    places_path: Path,
) -> List[str]:
    addresses = [
        *read_address_column(people_path, "home_address"),
        *read_address_column(places_path, "address"),
    ]
    return list(dict.fromkeys(addresses))


def load_existing_locations(path: Path) -> Dict[str, dict]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return {
            row["address"]: row
            for row in csv.DictReader(file)
            if row.get("address")
        }


def location_is_complete(location: dict) -> bool:
    return all(
        location.get(field) not in (None, "")
        for field in ("latitude", "longitude", "place_id")
    )


def geocode_addresses(
    addresses: Iterable[str],
    client: GoogleGeocodingClient,
    existing: Dict[str, dict],
    region_code: str = "my",
    refresh: bool = False,
    delay_seconds: float = 0.05,
) -> List[dict]:
    locations = []

    for address in addresses:
        cached = existing.get(address)

        if not refresh and cached and location_is_complete(cached):
            locations.append(cached)
            continue

        locations.append(client.geocode(address, region_code=region_code))

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    return locations


def write_locations(path: Path, locations: Iterable[dict]) -> None:
    temporary_path = path.with_name(f".{path.name}.tmp")

    with temporary_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=LOCATION_FIELDS)
        writer.writeheader()

        for location in locations:
            writer.writerow(
                {
                    field: location.get(field, "")
                    for field in LOCATION_FIELDS
                }
            )

    temporary_path.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Geocode unique people and place addresses into locations.csv."
        )
    )
    parser.add_argument("--people", type=Path, default=Path("people.csv"))
    parser.add_argument("--places", type=Path, default=Path("places.csv"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("locations.csv"),
    )
    parser.add_argument(
        "--region",
        default="my",
        help="Google region bias; defaults to Malaysia (my).",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Geocode all addresses again instead of using existing output.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0.05,
        help="Delay between API requests; defaults to 0.05 seconds.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv()
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")

    if not api_key:
        raise ValueError("Missing GOOGLE_MAPS_API_KEY in .env file.")

    addresses = collect_unique_addresses(args.people, args.places)
    existing = load_existing_locations(args.output)
    client = GoogleGeocodingClient(api_key)
    locations = geocode_addresses(
        addresses=addresses,
        client=client,
        existing=existing,
        region_code=args.region,
        refresh=args.refresh,
        delay_seconds=args.delay_seconds,
    )
    write_locations(args.output, locations)

    geocoded_count = sum(
        1
        for location in locations
        if location["address"] not in existing
        or args.refresh
        or not location_is_complete(existing[location["address"]])
    )
    print(
        f"Wrote {len(locations)} unique locations to {args.output} "
        f"({geocoded_count} API requests)."
    )


if __name__ == "__main__":
    main()
