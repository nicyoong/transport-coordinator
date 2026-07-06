import csv
from pathlib import Path
from typing import Dict


def load_private_locations(path: str | Path) -> Dict[str, str]:
    source = Path(path)

    with source.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {"location_id", "address"}

        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(
                f"{source} must contain location_id and address columns."
            )

        locations: Dict[str, str] = {}
        for row_number, row in enumerate(reader, start=2):
            location_id = (row.get("location_id") or "").strip()
            address = (row.get("address") or "").strip()

            if not location_id or not address:
                raise ValueError(
                    f"{source}:{row_number} has a blank location_id or address."
                )

            if location_id in locations:
                raise ValueError(
                    f"{source}:{row_number} repeats location_id {location_id!r}."
                )

            locations[location_id] = address

    return locations


def require_private_locations(
    location_ids: list[str],
    private_locations: Dict[str, str],
) -> Dict[str, str]:
    unique_ids = list(dict.fromkeys(location_ids))
    missing = [
        location_id
        for location_id in unique_ids
        if location_id not in private_locations
    ]

    if missing:
        raise ValueError(
            "Missing private location records for: " + ", ".join(missing)
        )

    return {
        location_id: private_locations[location_id]
        for location_id in unique_ids
    }
