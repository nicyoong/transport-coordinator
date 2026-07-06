from typing import Any, Dict, Optional

import requests


class GeocodingError(RuntimeError):
    pass


class GoogleGeocodingClient:
    GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def geocode(
        self,
        address: str,
        region_code: Optional[str] = "my",
    ) -> Dict[str, Any]:
        params = {
            "address": address,
            "key": self.api_key,
        }

        if region_code:
            params["region"] = region_code

        response = requests.get(
            self.GEOCODING_URL,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        status = data.get("status")

        if status != "OK":
            detail = data.get("error_message", "No additional details.")
            raise GeocodingError(
                f"Could not geocode {address!r}: {status}. {detail}"
            )

        results = data.get("results", [])

        if not results:
            raise GeocodingError(
                f"Could not geocode {address!r}: response had no results."
            )

        result = results[0]
        geometry = result["geometry"]
        location = geometry["location"]

        return {
            "address": address,
            "formatted_address": result.get("formatted_address", ""),
            "latitude": location["lat"],
            "longitude": location["lng"],
            "place_id": result.get("place_id", ""),
            "location_type": geometry.get("location_type", ""),
            "partial_match": bool(result.get("partial_match", False)),
        }
