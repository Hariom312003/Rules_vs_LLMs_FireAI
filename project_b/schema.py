"""Shared facts about the NYC 311 schema and geography.

These are the "expected schema" and domain rules that the rule-based
detectors check against and that the injector uses to build realistic
corruptions. Column names are the Socrata (lower_snake) names.
"""
from __future__ import annotations

# Columns a clean batch must contain (subset of the full 311 table we rely on).
CORE_COLUMNS = [
    "unique_key", "created_date", "closed_date", "agency", "agency_name",
    "complaint_type", "descriptor", "location_type", "incident_zip",
    "incident_address", "street_name", "city", "borough", "status",
    "resolution_description", "open_data_channel_type", "latitude", "longitude",
]

DATE_COLS = ["created_date", "closed_date"]
FLOAT_COLS = ["latitude", "longitude"]
FREE_TEXT_COLS = ["descriptor", "resolution_description"]

# Expected dtype family per core column in a CLEAN batch.
EXPECTED_KIND = {
    "unique_key": "string", "created_date": "datestr", "closed_date": "datestr",
    "agency": "string", "agency_name": "string", "complaint_type": "string",
    "descriptor": "string", "location_type": "string", "incident_zip": "string",
    "incident_address": "string", "street_name": "string", "city": "string",
    "borough": "string", "status": "string", "resolution_description": "string",
    "open_data_channel_type": "string", "latitude": "float", "longitude": "float",
}

# Canonical date string used by the dataset: 2023-01-05T14:30:00.000
ISO_FMT = "%Y-%m-%dT%H:%M:%S.%f"
ISO_REGEX = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$"
ALT_FMT = "%m/%d/%Y %I:%M:%S %p"  # the "switched" format used by the injector

BOROUGHS = ["MANHATTAN", "BRONX", "BROOKLYN", "QUEENS", "STATEN ISLAND"]

# Rough NYC bounding box (lat, lon). Swapped values fall far outside it.
LAT_RANGE = (40.45, 40.95)
LON_RANGE = (-74.30, -73.65)

STATUSES_CLOSED = {"Closed"}
STATUSES_OPEN = {"Open", "Pending", "Assigned", "Started", "In Progress", "Unspecified"}


def zip_borough(z: str | None) -> str | None:
    """Borough implied by a NYC ZIP code (prefix rule), or None if not NYC/invalid."""
    if z is None:
        return None
    z = str(z).strip()
    if len(z) < 5 or not z[:5].isdigit():
        return None
    p3, p5 = z[:3], z[:5]
    if p3 in ("100", "101", "102"):
        return "MANHATTAN"
    if p3 == "103":
        return "STATEN ISLAND"
    if p3 == "104":
        return "BRONX"
    if p3 == "112":
        return "BROOKLYN"
    if p5 in ("11004", "11005", "11101", "11102", "11103", "11104", "11105",
              "11106") or p3 in ("111", "113", "114", "116"):
        return "QUEENS"
    return None
