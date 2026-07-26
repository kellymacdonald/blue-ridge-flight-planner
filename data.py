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

def clean_time(value):
    """Convert Excel time cells to a consistent string."""

    if pd.isna(value):
        return None

    if hasattr(value, "strftime"):
        return value.strftime("%I:%M %p")

    return str(value)


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
    raw = pd.read_excel(filename, header=None)

    # Locate the actual header row.
    header_row = None
    for index, row in raw.iterrows():
        values = row.astype(str).str.strip().tolist()
        if "Departure Airport" in values and "Arrival Airport" in values:
            header_row = index
            break

    if header_row is None:
        raise ValueError(
            "Could not find the flight-data header row in the spreadsheet."
        )

    df = pd.read_excel(filename, header=header_row)

    required_columns = [
        "Departure Airport",
        "Arrival Airport",
        "Departure Date",
        "Departure Time (Local)",
        "Arrival Time (Local)",
        "Cost ($)",
        "Flight Number",
    ]

    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing required spreadsheet columns: "
            + ", ".join(missing_columns)
        )

    # Remove empty rows and normalize text fields.
    df = df.dropna(
        subset=[
            "Departure Airport",
            "Arrival Airport",
            "Departure Date",
            "Departure Time (Local)",
            "Arrival Time (Local)",
            "Flight Number",
        ]
    ).copy()

    for column in [
        "Departure Airport",
        "Arrival Airport",
        "Flight Number",
    ]:
        df[column] = df[column].astype(str).str.strip()

    df["Departure Airport"] = df["Departure Airport"].str.upper()
    df["Arrival Airport"] = df["Arrival Airport"].str.upper()

    df["Departure Date"] = pd.to_datetime(
        df["Departure Date"],
        errors="coerce",
    )

    def combine_date_and_time(date_value, time_value):
        if pd.isna(date_value) or pd.isna(time_value):
            return pd.NaT

        date_value = pd.Timestamp(date_value).normalize()

        # Excel time cells normally arrive as datetime.time objects.
        if hasattr(time_value, "hour"):
            return date_value + pd.Timedelta(
                hours=time_value.hour,
                minutes=time_value.minute,
                seconds=getattr(time_value, "second", 0),
            )

        # Also supports strings such as:
        # "5:30 AM", "05:30:00", and "17:30".
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

    # Arrival times earlier than departure times occur on the next day.
    overnight = (
        df["Arrival DateTime"].notna()
        & df["Departure DateTime"].notna()
        & (df["Arrival DateTime"] < df["Departure DateTime"])
    )

    df.loc[overnight, "Arrival DateTime"] += pd.Timedelta(days=1)

    # Remove rows containing invalid dates or times.
    df = df.dropna(
        subset=[
            "Departure DateTime",
            "Arrival DateTime",
        ]
    ).copy()

    df["Cost ($)"] = pd.to_numeric(
        df["Cost ($)"],
        errors="coerce",
    )

    df = df.dropna(subset=["Cost ($)"]).copy()

    # Preserve the derived columns expected elsewhere in the app.
    df["Flight ID"] = (
        df["Flight Number"].str.replace(" ", "", regex=False)
        + "-"
        + df["Departure DateTime"].dt.strftime("%Y%m%d%H%M")
    )

    df["Route"] = (
        df["Departure Airport"]
        + " → "
        + df["Arrival Airport"]
    )

    df["Stakeholder"] = df.apply(
        lambda row: (
            "BOS"
            if "BOS" in {
                row["Departure Airport"],
                row["Arrival Airport"],
            }
            else "SFO"
        ),
        axis=1,
    )

    df["Duration"] = (
        df["Arrival DateTime"]
        - df["Departure DateTime"]
    )

    df["Redeye"] = (
        df["Departure DateTime"].dt.hour >= 20
    )

    return df
