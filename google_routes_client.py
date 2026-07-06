import requests
import re
from typing import Dict, List, Mapping, Tuple

from routes_usage import RoutesUsageStore


class GoogleRoutesClient:
    """
    Small wrapper around Google Maps Routes API Compute Route Matrix.

    It returns a duration matrix:
        duration_matrix[(origin_location_id, destination_location_id)] = seconds
    """

    ROUTE_MATRIX_URL = (
        "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
    )
    MAX_MATRIX_ELEMENTS = 625
    MAX_ADDRESSES_PER_BATCH = 25

    def __init__(
        self,
        api_key: str,
        usage_store: RoutesUsageStore | None = None,
        matrix_element_limit_30_days: int | None = None,
    ):
        self.api_key = api_key
        self.api_key_last6 = api_key[-6:]
        self.usage_store = usage_store
        self.matrix_element_limit_30_days = matrix_element_limit_30_days

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

    @classmethod
    def _validate_matrix_size(
        cls,
        origin_count: int,
        destination_count: int,
    ) -> None:
        element_count = origin_count * destination_count

        if element_count > cls.MAX_MATRIX_ELEMENTS:
            raise ValueError(
                "Google Route Matrix limit exceeded: "
                f"{origin_count} origins x {destination_count} destinations "
                f"produces {element_count} elements; "
                f"maximum is {cls.MAX_MATRIX_ELEMENTS}."
            )

    @staticmethod
    def _chunks(
        locations: List[Tuple[str, str]],
        size: int,
    ) -> List[List[Tuple[str, str]]]:
        return [
            locations[index:index + size]
            for index in range(0, len(locations), size)
        ]

    def _compute_duration_matrix_batch(
        self,
        origins: List[Tuple[str, str]],
        destinations: List[Tuple[str, str]],
        travel_mode: str = "DRIVE",
        routing_preference: str = "TRAFFIC_AWARE",
    ) -> Dict[Tuple[str, str], int]:
        self._validate_matrix_size(
            origin_count=len(origins),
            destination_count=len(destinations),
        )

        origin_waypoints = [
            self._waypoint(address)
            for _, address in origins
        ]
        destination_waypoints = [
            self._waypoint(address)
            for _, address in destinations
        ]

        payload = {
            "origins": origin_waypoints,
            "destinations": destination_waypoints,
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

            origin_id = origins[origin_index][0]
            destination_id = destinations[destination_index][0]

            if origin_id == destination_id:
                duration_matrix[(origin_id, destination_id)] = 0
                continue

            if "duration" not in element:
                duration_matrix[(origin_id, destination_id)] = 10**9
                continue

            duration_matrix[(origin_id, destination_id)] = self._parse_duration(
                element["duration"]
            )

        return duration_matrix

    def compute_duration_matrix(
        self,
        locations: Mapping[str, str],
        travel_mode: str = "DRIVE",
        routing_preference: str = "TRAFFIC_AWARE",
    ) -> Dict[Tuple[str, str], int]:
        """
        Computes pairwise travel duration between opaque location IDs.

        The complete matrix is split into safe API requests and merged so
        transport assignment can still be optimized globally. Raw addresses
        are used only to construct the Google request payload and are never
        used as matrix keys.
        """

        private_locations = list(locations.items())
        batches = self._chunks(
            private_locations,
            self.MAX_ADDRESSES_PER_BATCH,
        )
        duration_matrix = {}
        batch_pairs = [
            (origins_batch, destinations_batch)
            for origins_batch in batches
            for destinations_batch in batches
        ]

        if self.usage_store:
            request_ids = self.usage_store.reserve_requests(
                [
                    (len(origins_batch), len(destinations_batch))
                    for origins_batch, destinations_batch in batch_pairs
                ],
                days=30,
                matrix_element_limit=self.matrix_element_limit_30_days,
                api_key_last6=self.api_key_last6,
            )
        else:
            request_ids = [None] * len(batch_pairs)

        for index, (
            origins_batch,
            destinations_batch,
        ) in enumerate(batch_pairs):
            request_id = request_ids[index]
            try:
                batch_matrix = self._compute_duration_matrix_batch(
                    origins=origins_batch,
                    destinations=destinations_batch,
                    travel_mode=travel_mode,
                    routing_preference=routing_preference,
                )
            except Exception as error:
                if self.usage_store and request_id is not None:
                    self.usage_store.set_status(
                        request_id,
                        "failed",
                        str(error)[:1000],
                    )
                    self.usage_store.cancel_requests(request_ids[index + 1:])
                raise
            else:
                if self.usage_store and request_id is not None:
                    self.usage_store.set_status(request_id, "succeeded")
                duration_matrix.update(batch_matrix)

        return duration_matrix
