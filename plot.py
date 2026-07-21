from datetime import timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
from astral import LocationInfo
from astral.sun import sun


# ---------------------------------------------------------
# VISUAL SETTINGS
# ---------------------------------------------------------

AIRLINE_MARKERS = {
    "Delta": "triangle-up",
    "United": "star",
    "American": "x",
    "JetBlue": "square",
    "Frontier": "diamond",
    "Southwest": "hexagon",
    "Spirit": "triangle-down",
    "Alaska": "pentagon",
}

STAKEHOLDER_COLORS = {
    "SFO": "#2F6BFF",
    "BOS": "#E05252",
    "Other": "#999999",
}

ATLANTA = LocationInfo(
    name="Atlanta",
    region="Georgia",
    timezone="America/New_York",
    latitude=33.7490,
    longitude=-84.3880,
)

ATLANTA_TIMEZONE = ZoneInfo("America/New_York")


def marker_symbol(airline):
    return AIRLINE_MARKERS.get(airline, "circle")


def marker_color(stakeholder):
    return STAKEHOLDER_COLORS.get(
        stakeholder,
        STAKEHOLDER_COLORS["Other"],
    )


# ---------------------------------------------------------
# HOVER TEXT
# ---------------------------------------------------------

def hover_text(row):
    return (
        f"<b>{row['Airline']} {row['Flight Number']}</b><br>"
        f"{row['Route']}<br><br>"
        f"<b>Departs</b><br>"
        f"{row['Departure DateTime']:%a %b %d, %I:%M %p}<br><br>"
        f"<b>Arrives</b><br>"
        f"{row['Arrival DateTime']:%a %b %d, %I:%M %p}<br><br>"
        f"<b>Duration:</b> {row['Duration Label']}<br>"
        f"<b>Cost:</b> ${row['Cost ($)']:.0f}<br>"
        f"<b>Redeye:</b> {'Yes' if row['Redeye'] else 'No'}"
        f"<br><br><b>Click to select</b>"
    )


# ---------------------------------------------------------
# PREPARE PLOTTING DATA
# ---------------------------------------------------------

def prepare_plot_data(df):
    plot_df = df.copy()

    # Slightly separate flights with identical prices.
    plot_df["Plot Cost"] = (
        plot_df["Cost ($)"]
        + plot_df.groupby("Cost ($)").cumcount() * 2.5
    )

    plot_df["Hover"] = plot_df.apply(
        hover_text,
        axis=1,
    )

    return plot_df


def get_plot_range(plot_df):
    earliest = min(
        plot_df["Departure DateTime"].min(),
        plot_df["Arrival DateTime"].min(),
        plot_df["ATL Time"].min(),
    )

    latest = max(
        plot_df["Departure DateTime"].max(),
        plot_df["Arrival DateTime"].max(),
        plot_df["ATL Time"].max(),
    )

    start = earliest.normalize()
    end = latest.normalize() + pd.Timedelta(days=1)

    return start, end


# ---------------------------------------------------------
# DAYLIGHT BACKGROUND
# ---------------------------------------------------------

def local_naive(value):
    """
    Convert an Atlanta timezone-aware datetime into a
    timezone-naive local datetime for Plotly.
    """
    return pd.Timestamp(
        value.astimezone(ATLANTA_TIMEZONE)
    ).tz_localize(None)


def add_daylight_background(fig, start, end):
    current_date = start.date()
    final_date = end.date()

    while current_date <= final_date:
        solar_times = sun(
            ATLANTA.observer,
            date=current_date,
            tzinfo=ATLANTA_TIMEZONE,
        )

        sunrise = local_naive(
            solar_times["sunrise"]
        )

        sunset = local_naive(
            solar_times["sunset"]
        )

        day_start = pd.Timestamp(current_date)
        next_day = day_start + pd.Timedelta(days=1)

        # Overnight period before sunrise
        fig.add_vrect(
            x0=day_start,
            x1=sunrise,
            fillcolor="rgba(72, 92, 130, 0.10)",
            line_width=0,
            layer="below",
        )

        # Daylight period
        fig.add_vrect(
            x0=sunrise,
            x1=sunset,
            fillcolor="rgba(250, 210, 90, 0.09)",
            line_width=0,
            layer="below",
        )

        # Overnight period after sunset
        fig.add_vrect(
            x0=sunset,
            x1=next_day,
            fillcolor="rgba(72, 92, 130, 0.10)",
            line_width=0,
            layer="below",
        )

        current_date += timedelta(days=1)


# ---------------------------------------------------------
# MIDNIGHT SEPARATORS
# ---------------------------------------------------------

def add_midnight_lines(fig, start, end):
    midnight = start + pd.Timedelta(days=1)

    while midnight < end:
        fig.add_vline(
            x=midnight,
            line_width=1,
            line_dash="dot",
            line_color="rgba(50, 50, 50, 0.28)",
            layer="below",
        )

        midnight += pd.Timedelta(days=1)


# ---------------------------------------------------------
# DURATION BARS
# ---------------------------------------------------------

def duration_coordinates(rows):
    x_values = []
    y_values = []

    for _, row in rows.iterrows():
        x_values.extend(
            [
                row["Departure DateTime"],
                row["Arrival DateTime"],
                None,
            ]
        )

        y_values.extend(
            [
                row["Plot Cost"],
                row["Plot Cost"],
                None,
            ]
        )

    return x_values, y_values


def add_duration_bars(
    fig,
    plot_df,
    selected_ids,
):
    selected_ids = set(selected_ids)

    unselected = plot_df[
        ~plot_df["Flight ID"].isin(selected_ids)
    ]

    selected = plot_df[
        plot_df["Flight ID"].isin(selected_ids)
    ]

    if not unselected.empty:
        x_values, y_values = duration_coordinates(
            unselected
        )

        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                mode="lines",
                line={
                    "color": "rgba(90, 90, 90, 0.28)",
                    "width": 2,
                },
                hoverinfo="skip",
                showlegend=False,
                name="Flight duration",
            )
        )

    if not selected.empty:
        x_values, y_values = duration_coordinates(
            selected
        )

        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                mode="lines",
                line={
                    "color": "rgba(25, 25, 25, 0.80)",
                    "width": 5,
                },
                hoverinfo="skip",
                showlegend=False,
                name="Selected duration",
            )
        )


# ---------------------------------------------------------
# FLIGHT MARKERS
# ---------------------------------------------------------

def add_unselected_flights(
    fig,
    plot_df,
    selected_ids,
    show_flight_numbers,
):
    selected_ids = set(selected_ids)

    unselected = plot_df[
        ~plot_df["Flight ID"].isin(selected_ids)
    ]

    mode = (
        "markers+text"
        if show_flight_numbers
        else "markers"
    )

    fig.add_trace(
        go.Scatter(
            x=unselected["ATL Time"],
            y=unselected["Plot Cost"],
            mode=mode,
            customdata=unselected["Flight ID"],
            hovertext=unselected["Hover"],
            hovertemplate="%{hovertext}<extra></extra>",
            text=(
                unselected["Flight Number"]
                if show_flight_numbers
                else None
            ),
            textposition="top center",
            textfont={
                "size": 9,
                "color": "rgba(40, 40, 40, 0.75)",
            },
            marker={
                "size": 9,
                "symbol": unselected[
                    "Airline"
                ].map(marker_symbol),
                "color": unselected[
                    "Stakeholder"
                ].map(marker_color),
                "opacity": 0.72,
                "line": {
                    "color": "rgba(0, 0, 0, 0.38)",
                    "width": 0.7,
                },
            },
            name="Flights",
            showlegend=False,
        )
    )


def add_selected_flights(
    fig,
    plot_df,
    selected_ids,
    show_flight_numbers,
):
    selected = plot_df[
        plot_df["Flight ID"].isin(selected_ids)
    ]

    if selected.empty:
        return

    mode = (
        "markers+text"
        if show_flight_numbers
        else "markers"
    )

    fig.add_trace(
        go.Scatter(
            x=selected["ATL Time"],
            y=selected["Plot Cost"],
            mode=mode,
            customdata=selected["Flight ID"],
            hovertext=selected["Hover"],
            hovertemplate="%{hovertext}<extra></extra>",
            text=(
                selected["Flight Number"]
                if show_flight_numbers
                else None
            ),
            textposition="top center",
            textfont={
                "size": 10,
                "color": "black",
            },
            marker={
                "size": 15,
                "symbol": selected[
                    "Airline"
                ].map(marker_symbol),
                "color": selected[
                    "Stakeholder"
                ].map(marker_color),
                "opacity": 1,
                "line": {
                    "color": "black",
                    "width": 3,
                },
            },
            name="Selected",
            showlegend=False,
        )
    )


# ---------------------------------------------------------
# LEGENDS
# ---------------------------------------------------------

def add_airline_legend(fig, plot_df):
    airlines = sorted(
        plot_df["Airline"].dropna().unique()
    )

    for airline in airlines:
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker={
                    "size": 10,
                    "symbol": marker_symbol(airline),
                    "color": "#777777",
                    "line": {
                        "color": "#333333",
                        "width": 0.7,
                    },
                },
                name=airline,
                legendgroup="airlines",
                legendgrouptitle_text=(
                    "Airline"
                    if airline == airlines[0]
                    else None
                ),
                showlegend=True,
                hoverinfo="skip",
            )
        )


def add_stakeholder_legend(fig):
    groups = [
        ("SFO travelers", "SFO"),
        ("BOS travelers", "BOS"),
    ]

    for index, (label, group) in enumerate(groups):
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker={
                    "size": 10,
                    "symbol": "circle",
                    "color": marker_color(group),
                    "line": {
                        "color": "#333333",
                        "width": 0.7,
                    },
                },
                name=label,
                legendgroup="travelers",
                legendgrouptitle_text=(
                    "Traveler group"
                    if index == 0
                    else None
                ),
                showlegend=True,
                hoverinfo="skip",
            )
        )


# ---------------------------------------------------------
# LAYOUT
# ---------------------------------------------------------

def format_chart(
    fig,
    start,
    end,
):
    fig.update_layout(
        title={
            "text": (
                "Flight Timeline"
                "<br><sup>"
                "Times are local to each airport. "
                "Markers appear at the Atlanta endpoint. "
                "Click a marker to select it."
                "</sup>"
            ),
            "x": 0.5,
        },
        height=800,
        template="plotly_white",
        clickmode="event+select",
        hovermode="closest",
        margin={
            "l": 65,
            "r": 30,
            "t": 95,
            "b": 65,
        },
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.16,
            "xanchor": "center",
            "x": 0.5,
            "groupclick": "toggleitem",
        },
    )

    fig.update_xaxes(
        range=[start, end],
        tickformat="%a<br>%m/%d<br>%I %p",
        title="Atlanta coordination time",
        showgrid=False,
        fixedrange=False,
    )

    fig.update_yaxes(
        title="Ticket Cost ($)",
        tickprefix="$",
        gridcolor="rgba(0, 0, 0, 0.08)",
        fixedrange=False,
    )


# ---------------------------------------------------------
# MAIN BUILD FUNCTION
# ---------------------------------------------------------

def build_plot(
    df,
    selected_ids=None,
    show_duration_bars=True,
    show_daylight=True,
    show_flight_numbers=False,
    show_legends=True,
):
    selected_ids = list(selected_ids or [])

    plot_df = prepare_plot_data(df)
    start, end = get_plot_range(plot_df)

    fig = go.Figure()

    if show_daylight:
        add_daylight_background(
            fig,
            start,
            end,
        )

    add_midnight_lines(
        fig,
        start,
        end,
    )

    if show_duration_bars:
        add_duration_bars(
            fig,
            plot_df,
            selected_ids,
        )

    add_unselected_flights(
        fig,
        plot_df,
        selected_ids,
        show_flight_numbers,
    )

    add_selected_flights(
        fig,
        plot_df,
        selected_ids,
        show_flight_numbers,
    )

    if show_legends:
        add_airline_legend(
            fig,
            plot_df,
        )

        add_stakeholder_legend(fig)

    format_chart(
        fig,
        start,
        end,
    )

    return fig