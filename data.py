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
    # Date
    # -----------------------------

    df["Departure Date"] = pd.to_datetime(
        df["Departure Date"]
    )

    dep = df["Departure Time (Local)"].apply(clean_time)
    arr = df["Arrival Time (Local)"].apply(clean_time)

    df["Departure DateTime"] = pd.to_datetime(
        df["Departure Date"].dt.strftime("%m/%d/%Y")
        + " "
        + dep,
        format="%m/%d/%Y %I:%M %p",
    )

    df["Arrival DateTime"] = pd.to_datetime(
        df["Departure Date"].dt.strftime("%m/%d/%Y")
        + " "
        + arr,
        format="%m/%d/%Y %I:%M %p",
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