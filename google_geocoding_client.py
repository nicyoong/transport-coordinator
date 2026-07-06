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
        location_id: str,
        address: str,
        region_code: Optional[str] = "my",
    ) -> Dict[str, Any]:
        params = {
            "address": address,
            "key": self.api_key,
        }

        if region_code:
            params["region"] = region_code

        try:
            response = requests.get(
                self.GEOCODING_URL,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException:
            raise GeocodingError(
                f"Could not geocode location {location_id!r}: "
                "Google request failed."
            ) from None

        data = response.json()
        status = data.get("status")

        if status != "OK":
            raise GeocodingError(
                f"Could not geocode location {location_id!r}: "
                f"Google returned {status!r}."
            )

        results = data.get("results", [])

        if not results:
            raise GeocodingError(
                f"Could not geocode location {location_id!r}: "
                "response had no results."
            )

        result = results[0]
        geometry = result["geometry"]

        return {
            "location_id": location_id,
            "location_type": geometry.get("location_type", ""),
            "partial_match": bool(result.get("partial_match", False)),
        }
