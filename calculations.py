import pandas as pd


INBOUND_ROUTES = {
    "SFO": "SFO → ATL",
    "BOS": "BOS → ATL",
}

OUTBOUND_ROUTES = {
    "SFO": "ATL → SFO",
    "BOS": "ATL → BOS",
}


def format_datetime(value):
    if value is None or pd.isna(value):
        return "—"

    return value.strftime(
        "%a %m/%d at %I:%M %p"
    ).replace(" 0", " ")


def format_short_datetime(value):
    if value is None or pd.isna(value):
        return "—"

    return value.strftime(
        "%a %m/%d, %I:%M %p"
    ).replace(" 0", " ")


def format_duration(delta):
    if delta is None or pd.isna(delta):
        return "—"

    total_minutes = max(
        0,
        int(delta.total_seconds() // 60),
    )

    days, remaining_minutes = divmod(
        total_minutes,
        24 * 60,
    )

    hours, minutes = divmod(
        remaining_minutes,
        60,
    )

    parts = []

    if days:
        parts.append(f"{days}d")

    if hours:
        parts.append(f"{hours}h")

    if minutes or not parts:
        parts.append(f"{minutes}m")

    return " ".join(parts)


def get_selected_rows(df, selected_flights):
    rows = {}

    for route, flight_id in selected_flights.items():
        match = df.loc[
            df["Flight ID"] == int(flight_id)
        ]

        if not match.empty:
            rows[route] = match.iloc[0]

    return rows


def calculate_itinerary(df, selected_flights):
    rows = get_selected_rows(
        df,
        selected_flights,
    )

    result = {
        # Keep both names so older app code continues
        # to work if it references either key.
        "rows": rows,
        "selected_rows": rows,

        "inbound_complete": False,
        "outbound_complete": False,
        "trip_complete": False,

        "meeting_time": None,
        "blue_ridge_arrival": None,
        "blue_ridge_departure": None,
        "blue_ridge_duration": None,

        "airport_arrival": None,

        "inbound_waits": {},
        "outbound_waits": {},

        "time_away": {
            "SFO": None,
            "BOS": None,
        },

        "away_ranges": {
            "SFO": None,
            "BOS": None,
        },

        "costs": {
            "SFO": 0,
            "BOS": 0,
        },
    }

    # --------------------------------------------------
    # Separate costs
    # --------------------------------------------------

    for row in rows.values():
        stakeholder = row["Stakeholder"]

        if stakeholder in result["costs"]:
            result["costs"][stakeholder] += float(
                row["Cost ($)"]
            )

    # --------------------------------------------------
    # Inbound calculations
    # --------------------------------------------------

    inbound_rows = {}

    for group, route in INBOUND_ROUTES.items():
        if route in rows:
            inbound_rows[group] = rows[route]

    if len(inbound_rows) == 2:
        result["inbound_complete"] = True

        # The groups can leave ATL together once the
        # later inbound flight has arrived.
        meeting_time = max(
            row["Arrival DateTime"]
            for row in inbound_rows.values()
        )

        result["meeting_time"] = meeting_time

        # Two-hour drive from ATL to Blue Ridge.
        result["blue_ridge_arrival"] = (
            meeting_time
            + pd.Timedelta(hours=2)
        )

        # Inbound wait is entirely coordination wait:
        # the earlier group waits for the later group.
        for group, row in inbound_rows.items():
            arrival_time = row["Arrival DateTime"]
            wait_duration = meeting_time - arrival_time

            result["inbound_waits"][group] = {
                "start": arrival_time,
                "end": meeting_time,
                "duration": max(
                    wait_duration,
                    pd.Timedelta(0),
                ),
            }

    # --------------------------------------------------
    # Outbound calculations
    # --------------------------------------------------

    outbound_rows = {}

    for group, route in OUTBOUND_ROUTES.items():
        if route in rows:
            outbound_rows[group] = rows[route]

    if len(outbound_rows) == 2:
        result["outbound_complete"] = True

        earliest_flight = min(
            row["Departure DateTime"]
            for row in outbound_rows.values()
        )

        # Everyone leaves Blue Ridge based on the earlier
        # outbound flight:
        #
        # 2 hours driving to ATL
        # + 2 hours standard airport/TSA buffer.
        result["blue_ridge_departure"] = (
            earliest_flight
            - pd.Timedelta(hours=4)
        )

        result["airport_arrival"] = (
            result["blue_ridge_departure"]
            + pd.Timedelta(hours=2)
        )

        for group, row in outbound_rows.items():
            flight_departure = row[
                "Departure DateTime"
            ]

            # Do not count the normal two-hour airport
            # buffer as waiting.
            #
            # Only count the additional time caused by
            # leaving Blue Ridge for the earlier group's
            # flight.
            extra_wait = (
                flight_departure
                - earliest_flight
            )

            result["outbound_waits"][group] = {
                "start": earliest_flight,
                "end": flight_departure,
                "duration": max(
                    extra_wait,
                    pd.Timedelta(0),
                ),
            }

    # --------------------------------------------------
    # Overall journey ranges
    # --------------------------------------------------

    for group in ["SFO", "BOS"]:
        inbound_route = INBOUND_ROUTES[group]
        outbound_route = OUTBOUND_ROUTES[group]

        if (
            inbound_route in rows
            and outbound_route in rows
        ):
            trip_start = rows[
                inbound_route
            ]["Departure DateTime"]

            trip_end = rows[
                outbound_route
            ]["Arrival DateTime"]

            result["away_ranges"][group] = {
                "start": trip_start,
                "end": trip_end,
            }

            # Retained for compatibility with saved-option
            # code, even if it is no longer displayed.
            result["time_away"][group] = (
                trip_end - trip_start
            )

    # --------------------------------------------------
    # Blue Ridge duration
    # --------------------------------------------------

    if (
        result["blue_ridge_arrival"] is not None
        and result["blue_ridge_departure"] is not None
    ):
        result["trip_complete"] = True

        blue_ridge_duration = (
            result["blue_ridge_departure"]
            - result["blue_ridge_arrival"]
        )

        result["blue_ridge_duration"] = max(
            blue_ridge_duration,
            pd.Timedelta(0),
        )

    return result