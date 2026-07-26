from pathlib import Path
import pandas as pd

# --------------------------------------------------------
# Airline lookup
# --------------------------------------------------------

AIRLINES = {
    "DL": "Delta",
    "UA": "United",
    "AA": "American",
    "B6": "JetBlue",
    "F9": "Frontier",
    "WN": "Southwest",
    "NK": "Spirit",
    "AS": "Alaska",
}

# --------------------------------------------------------
# Helper functions
# --------------------------------------------------------


def stakeholder(row):
    airports = {
        row["Departure Airport"],
        row["Arrival Airport"],
    }

    if "SFO" in airports:
        return "SFO"

    if "BOS" in airports:
        return "BOS"

    return "Other"


def atl_time(row):
    if row["Arrival Airport"] == "ATL":
        return row["Arrival DateTime"]

    return row["Departure DateTime"]


# --------------------------------------------------------
# Main loading function
# --------------------------------------------------------

def load_flights(filename):

    filename = Path(filename)

    raw = pd.read_excel(
        filename,
        header=None
    )

    header_row = raw[
        raw.astype(str)
        .apply(
            lambda r: r.str.contains(
                "Flight Number",
                case=False,
                na=False
            ).any(),
            axis=1
        )
    ].index[0]

    df = pd.read_excel(
        filename,
        skiprows=header_row
    )

    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
    )

    # -----------------------------
    # Date and time
    # -----------------------------

    df["Departure Date"] = pd.to_datetime(
        df["Departure Date"],
        errors="coerce",
    )

def combine_date_and_time(date_value, time_value):
    if pd.isna(date_value) or pd.isna(time_value):
        return pd.NaT

    date_value = pd.Timestamp(date_value).normalize()

    # Excel time cells may be datetime.time or datetime.datetime objects.
    if hasattr(time_value, "hour"):
        return date_value + pd.Timedelta(
            hours=time_value.hour,
            minutes=time_value.minute,
            seconds=getattr(time_value, "second", 0),
        )

    # Fallback for strings such as:
    # 5:30 AM, 05:30:00, or 17:30
    parsed_time = pd.to_datetime(
        str(time_value).strip(),
        format="mixed",
        errors="coerce",
    )

    if pd.isna(parsed_time):
        return pd.NaT

    return date_value + pd.Timedelta(
        hours=parsed_time.hour,
        minutes=parsed_time.minute,
        seconds=parsed_time.second,
    )

    df["Departure DateTime"] = [
        combine_date_and_time(date_value, time_value)
        for date_value, time_value in zip(
            df["Departure Date"],
            df["Departure Time (Local)"],
        )
    ]

    df["Arrival DateTime"] = [
        combine_date_and_time(date_value, time_value)
        for date_value, time_value in zip(
            df["Departure Date"],
            df["Arrival Time (Local)"],
        )
    ]

    invalid_datetime_rows = (
        df["Departure DateTime"].isna()
        | df["Arrival DateTime"].isna()
    )

    if invalid_datetime_rows.any():
        bad_rows = df.loc[
            invalid_datetime_rows,
            [
                "Departure Date",
                "Departure Time (Local)",
                "Arrival Time (Local)",
                "Flight Number",
            ],
        ]

        raise ValueError(
            "Could not parse dates or times for these flights:\n"
            + bad_rows.to_string(index=False)
        )

    overnight = (
        df["Arrival DateTime"]
        < df["Departure DateTime"]
    )

    df.loc[
        overnight,
        "Arrival DateTime"
    ] += pd.Timedelta(days=1)

    # -----------------------------
    # Duration
    # -----------------------------

    df["Duration (min)"] = (
        (
            df["Arrival DateTime"]
            - df["Departure DateTime"]
        )
        .dt.total_seconds()
        .div(60)
        .astype(int)
    )

    hrs = df["Duration (min)"] // 60
    mins = df["Duration (min)"] % 60

    df["Duration Label"] = (
        hrs.astype(str)
        + "h "
        + mins.astype(str)
        + "m"
    )

    # -----------------------------
    # Airline
    # -----------------------------

    prefix = (
        df["Flight Number"]
        .astype(str)
        .str.split()
        .str[0]
    )

    df["Airline"] = (
        prefix.map(AIRLINES)
        .fillna(prefix)
    )

    # -----------------------------
    # Redeye
    # -----------------------------

    df["Redeye"] = (
        (df["Departure DateTime"].dt.hour >= 21)
        |
        (df["Arrival DateTime"].dt.hour < 7)
    )

    # -----------------------------
    # Stakeholder
    # -----------------------------

    df["Stakeholder"] = df.apply(
        stakeholder,
        axis=1,
    )

    # -----------------------------
    # ATL Coordination Time
    # -----------------------------

    df["ATL Time"] = df.apply(
        atl_time,
        axis=1,
    )

    # -----------------------------
    # Route
    # -----------------------------

    df["Route"] = (
        df["Departure Airport"]
        + " → "
        + df["Arrival Airport"]
    )
    
    # Stable ID used for chart selections
    df = df.reset_index(drop=True)
    df["Flight ID"] = df.index.astype(int)

    return df
