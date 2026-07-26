from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests


SERPAPI_ENDPOINT = "https://serpapi.com/search"

OUTPUT_FILE = Path(__file__).parent / "flights.xlsx"

# Change these dates as needed.
SEARCHES = [
    {
        "departure": "BOS",
        "arrival": "ATL",
        "date": "2026-10-22",
    },
    {
        "departure": "SFO",
        "arrival": "ATL",
        "date": "2026-10-22",
    },
    {
        "departure": "ATL",
        "arrival": "BOS",
        "date": "2026-10-25",
    },
    {
        "departure": "ATL",
        "arrival": "SFO",
        "date": "2026-10-25",
    },
]


def parse_google_datetime(value: str) -> datetime:
    """Parse a SerpApi Google Flights local date and time."""
    return datetime.strptime(value, "%Y-%m-%d %H:%M")


def search_flights(
    api_key: str,
    departure: str,
    arrival: str,
    date: str,
) -> dict[str, Any]:
    """Retrieve nonstop one-way flights from Google Flights through SerpApi."""

    params = {
        "engine": "google_flights",
        "api_key": api_key,
        "departure_id": departure,
        "arrival_id": arrival,
        "outbound_date": date,
        "type": 2,                # One way
        "travel_class": 1,        # Economy
        "adults": 1,
        "stops": 1,               # Nonstop only
        "bags": 1,                # One carry-on
        "currency": "USD",
        "gl": "us",
        "hl": "en",
        "show_hidden": "true",
        "deep_search": "true",
        "no_cache": "true",
    }

    response = requests.get(
        SERPAPI_ENDPOINT,
        params=params,
        timeout=90,
    )
    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise RuntimeError(
            f"{departure} → {arrival} on {date}: {data['error']}"
        )

    return data


def extract_rows(
    data: dict[str, Any],
    expected_departure: str,
    expected_arrival: str,
) -> list[dict[str, Any]]:
    """Convert Google Flights itineraries into the app's spreadsheet schema."""

    itineraries = (
        data.get("best_flights", [])
        + data.get("other_flights", [])
    )

    rows: list[dict[str, Any]] = []

    for itinerary in itineraries:
        segments = itinerary.get("flights", [])

        # This should already be enforced by stops=1, but keep the check.
        if len(segments) != 1:
            continue

        flight = segments[0]

        departure_airport = flight.get("departure_airport", {})
        arrival_airport = flight.get("arrival_airport", {})

        departure_id = departure_airport.get("id")
        arrival_id = arrival_airport.get("id")

        if (
            departure_id != expected_departure
            or arrival_id != expected_arrival
        ):
            continue

        departure_text = departure_airport.get("time")
        arrival_text = arrival_airport.get("time")
        price = itinerary.get("price")
        flight_number = flight.get("flight_number")

        if not all(
            [
                departure_text,
                arrival_text,
                price is not None,
                flight_number,
            ]
        ):
            continue

        departure_dt = parse_google_datetime(departure_text)
        arrival_dt = parse_google_datetime(arrival_text)

        rows.append(
            {
                "Departure Airport": departure_id,
                "Arrival Airport": arrival_id,
                "Departure Date": departure_dt.date(),
                "Departure Time (Local)": departure_dt.time(),
                "Arrival Time (Local)": arrival_dt.time(),
                "Cost ($)": price,
                "Flight Number": flight_number,
            }
        )

    return rows


def main() -> None:
    api_key = os.getenv("SERPAPI_KEY")

    if not api_key:
        sys.exit(
            "SERPAPI_KEY is not set.\n"
            "Set it before running the script."
        )

    all_rows: list[dict[str, Any]] = []

    for search in SEARCHES:
        departure = search["departure"]
        arrival = search["arrival"]
        date = search["date"]

        print(f"Searching {departure} → {arrival} on {date}...")

        data = search_flights(
            api_key=api_key,
            departure=departure,
            arrival=arrival,
            date=date,
        )

        rows = extract_rows(
            data=data,
            expected_departure=departure,
            expected_arrival=arrival,
        )

        print(f"  Found {len(rows)} nonstop flights.")
        all_rows.extend(rows)

    if not all_rows:
        sys.exit("No flights were returned. The spreadsheet was not changed.")

    df = pd.DataFrame(all_rows)

    # Remove duplicate results that appear in both result groups.
    df = df.drop_duplicates(
        subset=[
            "Departure Airport",
            "Arrival Airport",
            "Departure Date",
            "Departure Time (Local)",
            "Flight Number",
        ]
    )

    df = df.sort_values(
        by=[
            "Departure Date",
            "Departure Airport",
            "Departure Time (Local)",
            "Cost ($)",
        ]
    ).reset_index(drop=True)

    with pd.ExcelWriter(
        OUTPUT_FILE,
        engine="openpyxl",
        datetime_format="mm/dd/yyyy",
    ) as writer:
        df.to_excel(writer, index=False, sheet_name="Flights")

        worksheet = writer.sheets["Flights"]

        worksheet.column_dimensions["A"].width = 20
        worksheet.column_dimensions["B"].width = 18
        worksheet.column_dimensions["C"].width = 17
        worksheet.column_dimensions["D"].width = 24
        worksheet.column_dimensions["E"].width = 22
        worksheet.column_dimensions["F"].width = 12
        worksheet.column_dimensions["G"].width = 17

        for cell in worksheet["C"][1:]:
            cell.number_format = "mm/dd/yyyy"

        for column in ("D", "E"):
            for cell in worksheet[column][1:]:
                cell.number_format = "h:mm AM/PM"

    print()
    print(f"Saved {len(df)} flights to:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()