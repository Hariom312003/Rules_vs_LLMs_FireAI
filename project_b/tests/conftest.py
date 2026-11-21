"""Synthetic CLEAN 311-like frame so tests never depend on the real download."""
import numpy as np
import pandas as pd
import pytest

from project_b.schema import CORE_COLUMNS

PAIRS = [("Noise - Residential", "Loud Music/Party"), ("Noise - Residential", "Banging/Pounding"),
         ("Illegal Parking", "Blocked Hydrant"), ("Illegal Parking", "Double Parked Blocking Traffic"),
         ("HEAT/HOT WATER", "ENTIRE BUILDING"), ("Street Condition", "Pothole")]
BOR = {"MANHATTAN": ("10001", 40.75, -73.99), "BRONX": ("10451", 40.82, -73.92),
       "BROOKLYN": ("11201", 40.69, -73.99), "QUEENS": ("11101", 40.74, -73.93),
       "STATEN ISLAND": ("10301", 40.63, -74.10)}
AGENCIES = {"NYPD": "New York City Police Department", "HPD": "Department of Housing Preservation and Development",
            "DOT": "Department of Transportation"}
CLOSED_TXT = ["The Police Department responded to the complaint and took action to fix the condition.",
              "The Department inspected and resolved the issue; the complaint was closed."]
OPEN_TXT = ["The complaint has been assigned and is under review.", "Your request is being processed."]


@pytest.fixture(scope="session")
def clean() -> pd.DataFrame:
    rng = np.random.default_rng(1)
    rows = []
    for i in range(1500):
        b = list(BOR)[i % 5]
        z, la, lo = BOR[b]
        ag = list(AGENCIES)[i % 3]
        t, d = PAIRS[int(rng.integers(0, len(PAIRS)))]
        cr = pd.Timestamp("2023-01-01") + pd.Timedelta(seconds=int(rng.integers(0, 365 * 86400)))
        closed = i % 4 != 0
        cl = cr + pd.Timedelta(hours=int(rng.integers(1, 500))) if closed else None
        rows.append({
            "unique_key": str(50_000_000 + i),
            "created_date": cr.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "closed_date": cl.strftime("%Y-%m-%dT%H:%M:%S.000") if cl is not None else None,
            "agency": ag, "agency_name": AGENCIES[ag], "complaint_type": t, "descriptor": d,
            "location_type": "RESIDENTIAL BUILDING", "incident_zip": z,
            "incident_address": f"{int(rng.integers(1, 999))} MAIN STREET {i}", "street_name": "MAIN STREET",
            "city": b.title(), "borough": b, "status": "Closed" if closed else "Open",
            "resolution_description": (CLOSED_TXT if closed else OPEN_TXT)[int(rng.integers(0, 2))],
            "open_data_channel_type": "PHONE",
            "latitude": la + float(rng.normal(0, 0.01)), "longitude": lo + float(rng.normal(0, 0.01)),
        })
    df = pd.DataFrame(rows, columns=CORE_COLUMNS)
    return df
