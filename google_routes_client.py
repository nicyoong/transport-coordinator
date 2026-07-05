import requests
import re
from typing import Dict, List, Tuple


class GoogleRoutesClient:
    """
    Small wrapper around Google Maps Routes API Compute Route Matrix.

    It returns a duration matrix:
        duration_matrix[(origin_address, destination_address)] = seconds
    """

    ROUTE_MATRIX_URL = (
        "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
    )

    def __init__(self, api_key: str):
        self.api_key = api_key

    @staticmethod
    def _waypoint(address: str) -> dict:
        return {
            "waypoint": {
                "address": address
            }
        }

    @staticmethod
    def _parse_duration(duration: str) -> int:
        """
        Google duration strings are commonly like '123s'.
        """
        if not duration:
            return 10**9

        match = re.match(r"(\d+)s", duration)

        if not match:
            return 10**9

        return int(match.group(1))

    def compute_duration_matrix(
        self,
        addresses: List[str],
        travel_mode: str = "DRIVE",
        routing_preference: str = "TRAFFIC_AWARE",
    ) -> Dict[Tuple[str, str], int]:
        """
        Computes pairwise travel duration between all addresses.

        Note:
        - Compute Route Matrix has request limits.
        - For very large groups, batch the addresses.
        """

        unique_addresses = list(dict.fromkeys(addresses))

        origins = [self._waypoint(address) for address in unique_addresses]
        destinations = [self._waypoint(address) for address in unique_addresses]

        payload = {
            "origins": origins,
            "destinations": destinations,
            "travelMode": travel_mode,
            "routingPreference": routing_preference,
        }

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "originIndex,destinationIndex,status,condition,"
                "distanceMeters,duration"
            ),
        }

        response = requests.post(
            self.ROUTE_MATRIX_URL,
            json=payload,
            headers=headers,
            timeout=60,
        )

        response.raise_for_status()

        data = response.json()

        duration_matrix = {}

        for element in data:
            origin_index = element["originIndex"]
            destination_index = element["destinationIndex"]

            origin = unique_addresses[origin_index]
            destination = unique_addresses[destination_index]

            if origin == destination:
                duration_matrix[(origin, destination)] = 0
                continue

            if "duration" not in element:
                duration_matrix[(origin, destination)] = 10**9
                continue

            duration_matrix[(origin, destination)] = self._parse_duration(
                element["duration"]
            )

        return duration_matrix