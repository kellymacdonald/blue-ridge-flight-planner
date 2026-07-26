import pandas as pd
import streamlit as st

from calculations import (
    calculate_itinerary,
    format_datetime,
    format_short_datetime,
    format_duration,
)
from data import load_flights
from plot import build_plot
from storage import (
    delete_option,
    load_saved_options,
    save_option,
)


st.set_page_config(
    
    page_title="Flight Planner",
    layout="wide",
)

st.markdown(
    """
    <style>

    /* Make the Plotly chart use the normal arrow cursor */
    .js-plotly-plot,
    .js-plotly-plot *,
    .plotly,
    .plotly * {
        cursor: default !important;
    }

    /* Keep the pointer hand over clickable flight markers */
    .scatterlayer .trace .points path {
        cursor: pointer !important;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


st.title("Flight Planner")


def get_data():
    return load_flights("flights.xlsx")


df = get_data()


# ---------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------

if "selected_flights" not in st.session_state:
    st.session_state.selected_flights = {}

if "active_saved_option" not in st.session_state:
    st.session_state.active_saved_option = None

if "save_message" not in st.session_state:
    st.session_state.save_message = None


selected_ids = list(
    st.session_state.selected_flights.values()
)


# ---------------------------------------------------------
# CHART
# ---------------------------------------------------------

# ---------------------------------------------------------
# CHART DISPLAY CONTROLS
# ---------------------------------------------------------

with st.expander(
    "Chart display options",
    expanded=False,
):
    control_1, control_2, control_3, control_4 = (
        st.columns(4)
    )

    with control_1:
        show_duration_bars = st.toggle(
            "Duration bars",
            value=True,
        )

    with control_2:
        show_daylight = st.toggle(
            "Daylight shading",
            value=True,
        )

    with control_3:
        show_flight_numbers = st.toggle(
            "Flight numbers",
            value=False,
        )

    with control_4:
        show_legends = st.toggle(
            "Chart legends",
            value=True,
        )

fig = build_plot(
    df,
    selected_ids=selected_ids,
    show_duration_bars=show_duration_bars,
    show_daylight=show_daylight,
    show_flight_numbers=show_flight_numbers,
    show_legends=show_legends,
)
chart_event = st.plotly_chart(
    fig,
    key="flight_chart",
    use_container_width=True,
    on_select="rerun",
    selection_mode="points",
    config={
        "displaylogo": False,
        "scrollZoom": True,
        "modeBarButtonsToRemove": [
            "lasso2d",
            "select2d",
        ],
    },
)


# ---------------------------------------------------------
# PROCESS FLIGHT CLICK
# ---------------------------------------------------------

points = chart_event.selection.points

if points:
    clicked_id = int(
        points[0]["customdata"]
    )

    clicked_row = df.loc[
        df["Flight ID"] == clicked_id
    ].iloc[0]

    route = clicked_row["Route"]

    previous_id = (
        st.session_state
        .selected_flights
        .get(route)
    )

    if previous_id != clicked_id:
        st.session_state.selected_flights[
            route
        ] = clicked_id

        # The user has modified the itinerary, so it is no
        # longer identical to the loaded saved option.
        st.session_state.active_saved_option = None
        st.rerun()


# ---------------------------------------------------------
# CALCULATE ITINERARY
# ---------------------------------------------------------

itinerary = calculate_itinerary(
    df,
    st.session_state.selected_flights,
)

selected_rows = itinerary["rows"]


# ---------------------------------------------------------
# FLIGHT CARD
# ---------------------------------------------------------

def display_flight(route, heading):
    st.markdown(f"#### {heading}")

    if route not in selected_rows:
        st.info("No flight selected.")
        return

    row = selected_rows[route]

    st.markdown(
        f"""
**{row['Airline']} {row['Flight Number']}**

{row['Departure Airport']} → {row['Arrival Airport']}

**Depart:** {format_datetime(row['Departure DateTime'])}  
**Arrive:** {format_datetime(row['Arrival DateTime'])}  
**Duration:** {row['Duration Label']}  
**Cost:** ${row['Cost ($)']:.0f}
        """
    )


# ---------------------------------------------------------
# WAIT SUMMARY
# ---------------------------------------------------------

def display_wait_summary(
    wait_data,
    label,
    zero_message,
):
    duration = wait_data["duration"]

    if duration <= pd.Timedelta(0):
        st.write(zero_message)
        return

    st.markdown(
        f"""
**{label}**

{format_short_datetime(wait_data['start'])}  
→ {format_short_datetime(wait_data['end'])}

**Wait duration:** {format_duration(duration)}
        """
    )

def display_extra_wait(wait, label="Waiting"):
    if not wait:
        st.caption(f"{label}: —")
        return

    duration = wait.get("duration")

    if duration is None or duration <= pd.Timedelta(0):
        st.caption("No waiting")
        return

    start = wait.get("start")
    end = wait.get("end")

    st.caption(f"**{label}**")

    if start is not None and end is not None:
        st.caption(
            f"{format_short_datetime(start)}"
            f" → "
            f"{format_short_datetime(end)}"
        )

    st.caption(f"({format_duration(duration)})")
    
# ---------------------------------------------------------
# LIVE ITINERARY SUMMARY
# ---------------------------------------------------------

# ---------------------------------------------------------
# COMPACT ITINERARY SUMMARY
# ---------------------------------------------------------

st.divider()

selected_rows = itinerary["selected_rows"]

sfo_inbound = selected_rows.get("SFO → ATL")
bos_inbound = selected_rows.get("BOS → ATL")
sfo_outbound = selected_rows.get("ATL → SFO")
bos_outbound = selected_rows.get("ATL → BOS")


# ---------------------------------------------------------
# BLUE RIDGE TIME — MOST IMPORTANT SUMMARY
# ---------------------------------------------------------

st.subheader("Time in Blue Ridge")

blue_ridge_duration = itinerary.get(
    "blue_ridge_duration"
)

blue_ridge_arrival = itinerary.get(
    "blue_ridge_arrival"
)

blue_ridge_departure = itinerary.get(
    "blue_ridge_departure"
)

if blue_ridge_duration is not None:
    st.metric(
        "Total time in Blue Ridge",
        format_duration(blue_ridge_duration),
        border=True,
    )

    if (
        blue_ridge_arrival is not None
        and blue_ridge_departure is not None
    ):
        st.caption(
            f"{format_datetime(blue_ridge_arrival)}"
            f" → "
            f"{format_datetime(blue_ridge_departure)}"
        )
else:
    st.info(
        "Select all inbound and outbound flights "
        "to calculate time in Blue Ridge."
    )


# ---------------------------------------------------------
# TRIP AND RETURN COORDINATION
# ---------------------------------------------------------

trip_column, return_column = st.columns(2)

with trip_column:
    st.markdown("#### Trip to Blue Ridge")

    meeting_time = itinerary.get("meeting_time")

    if meeting_time is not None:
        st.write(
            f"**Everyone at ATL:** "
            f"{format_datetime(meeting_time)}"
        )

    if blue_ridge_arrival is not None:
        st.write(
            f"**Arrive in Blue Ridge:** "
            f"{format_datetime(blue_ridge_arrival)}"
        )


with return_column:
    st.markdown("#### Return from Blue Ridge")

    if blue_ridge_departure is not None:
        st.write(
            f"**Leave Blue Ridge:** "
            f"{format_datetime(blue_ridge_departure)}"
        )

    airport_arrival = itinerary.get(
        "airport_arrival"
    )

    if airport_arrival is not None:
        st.write(
            f"**Arrive at ATL:** "
            f"{format_datetime(airport_arrival)}"
        )


# ---------------------------------------------------------
# TRAVELER-SPECIFIC FLIGHT DETAILS
# ---------------------------------------------------------

st.subheader("Traveler Details")

sfo_column, bos_column = st.columns(2)


# ---------------------------------------------------------
# SFO TRAVELERS
# ---------------------------------------------------------

with sfo_column:
    with st.container(border=True):
        st.markdown("### San Francisco")

        st.metric(
            "Flight cost",
            f"${itinerary['costs']['SFO']:,.0f}",
        )

        if sfo_inbound is not None:
            st.markdown("**To Atlanta**")

            st.write(
                f"{sfo_inbound['Airline']} "
                f"{sfo_inbound['Flight Number']}"
            )

            st.caption(
                f"{format_datetime(sfo_inbound['Departure DateTime'])}"
                f" → "
                f"{format_datetime(sfo_inbound['Arrival DateTime'])}"
            )

            display_extra_wait(
                itinerary[
                    "inbound_waits"
                ].get("SFO"),
                label="Extra wait for BOS",
            )

        if sfo_outbound is not None:
            st.markdown("**From Atlanta**")

            st.write(
                f"{sfo_outbound['Airline']} "
                f"{sfo_outbound['Flight Number']}"
            )

            st.caption(
                f"{format_datetime(sfo_outbound['Departure DateTime'])}"
                f" → "
                f"{format_datetime(sfo_outbound['Arrival DateTime'])}"
            )

            display_extra_wait(
                itinerary[
                    "outbound_waits"
                ].get("SFO"),
                label="Extra wait for BOS",
            )

        if (
            sfo_inbound is not None
            and sfo_outbound is not None
        ):
            st.markdown("**Overall journey**")

            st.caption(
                f"Start: "
                f"{format_datetime(sfo_inbound['Departure DateTime'])}"
            )

            st.caption(
                f"End: "
                f"{format_datetime(sfo_outbound['Arrival DateTime'])}"
            )


# ---------------------------------------------------------
# BOS TRAVELERS
# ---------------------------------------------------------

with bos_column:
    with st.container(border=True):
        st.markdown("### Boston")

        st.metric(
            "Flight cost",
            f"${itinerary['costs']['BOS']:,.0f}",
        )

        if bos_inbound is not None:
            st.markdown("**To Atlanta**")

            st.write(
                f"{bos_inbound['Airline']} "
                f"{bos_inbound['Flight Number']}"
            )

            st.caption(
                f"{format_datetime(bos_inbound['Departure DateTime'])}"
                f" → "
                f"{format_datetime(bos_inbound['Arrival DateTime'])}"
            )

            display_extra_wait(
                itinerary[
                    "inbound_waits"
                ].get("BOS"),
                label="Extra wait for SFO",
            )

        if bos_outbound is not None:
            st.markdown("**From Atlanta**")

            st.write(
                f"{bos_outbound['Airline']} "
                f"{bos_outbound['Flight Number']}"
            )

            st.caption(
                f"{format_datetime(bos_outbound['Departure DateTime'])}"
                f" → "
                f"{format_datetime(bos_outbound['Arrival DateTime'])}"
            )

            display_extra_wait(
                itinerary[
                    "outbound_waits"
                ].get("BOS"),
                label="Extra wait for SFO",
            )

        if (
            bos_inbound is not None
            and bos_outbound is not None
        ):
            st.markdown("**Overall journey**")

            st.caption(
                f"Start: "
                f"{format_datetime(bos_inbound['Departure DateTime'])}"
            )

            st.caption(
                f"End: "
                f"{format_datetime(bos_outbound['Arrival DateTime'])}"
            )

# ---------------------------------------------------------
# SAVE CURRENT OPTION
# ---------------------------------------------------------

st.divider()
st.header("Saved Itinerary Options")

all_routes_selected = (
    len(st.session_state.selected_flights) == 4
)

if not all_routes_selected:
    st.info(
        "Select one flight for each of the four routes "
        "before saving an itinerary option."
    )

with st.form(
    "save_itinerary_form",
    clear_on_submit=True,
):
    save_name = st.text_input(
        "Option name",
        placeholder=(
            "For example: Cheapest, Most Blue Ridge Time, "
            "or Best for Work"
        ),
    )

    save_submitted = st.form_submit_button(
        "Save Current Option",
        use_container_width=True,
        disabled=not all_routes_selected,
    )

    if save_submitted:
        cleaned_name = save_name.strip()

        if not cleaned_name:
            st.warning(
                "Enter a name for this itinerary option."
            )

        else:
            saved = save_option(
                cleaned_name,
                st.session_state.selected_flights,
            )

            st.session_state.active_saved_option = saved["id"]
            st.session_state.save_message = (
                f'Saved "{cleaned_name}".'
            )

            st.rerun()


if st.session_state.save_message:
    st.success(st.session_state.save_message)
    st.session_state.save_message = None

# ---------------------------------------------------------
# SAVED OPTION DISPLAY HELPERS
# ---------------------------------------------------------

ROUTE_ORDER = [
    "SFO → ATL",
    "BOS → ATL",
    "ATL → SFO",
    "ATL → BOS",
]


def get_saved_flight_rows(df, saved_selection):
    """Return the selected flight rows indexed by route."""
    rows_by_route = {}

    for route, flight_id in saved_selection.items():
        matches = df[df["Flight ID"] == int(flight_id)]

        if not matches.empty:
            rows_by_route[route] = matches.iloc[0]

    return rows_by_route


def flight_summary(row):
    """Create a compact airline and flight-number label."""
    if row is None:
        return "Not selected"

    return f"{row['Airline']} · {row['Flight Number']}"


def format_wait(wait):
    """Format one wait dictionary from calculate_itinerary()."""
    if not wait:
        return "—"

    return format_duration(wait.get("duration"))


def total_wait_time(itinerary, group):
    """Combine inbound and outbound ATL waiting time."""
    inbound = itinerary["inbound_waits"].get(group)
    outbound = itinerary["outbound_waits"].get(group)

    total = pd.Timedelta(0)

    if inbound:
        total += inbound["duration"]

    if outbound:
        total += outbound["duration"]

    return total


def display_saved_flight_detail(route, row):
    """Display one flight inside the details popover."""
    if row is None:
        st.markdown(f"**{route}**")
        st.caption("Flight no longer found in the spreadsheet.")
        return

    st.markdown(
        f"**{route} · {row['Airline']} "
        f"{row['Flight Number']}**"
    )

    st.caption(
        f"{format_short_datetime(row['Departure DateTime'])}"
        f" → "
        f"{format_short_datetime(row['Arrival DateTime'])}"
        f"  |  "
        f"{row['Duration Label']}"
        f"  |  "
        f"${row['Cost ($)']:,.0f}"
    )
# ---------------------------------------------------------
# DISPLAY SAVED OPTIONS
# ---------------------------------------------------------
# ---------------------------------------------------------
# DISPLAY SAVED OPTIONS
# ---------------------------------------------------------

saved_options = load_saved_options()

if not saved_options:
    st.caption(
        "No itinerary options have been saved yet."
    )

else:
    st.markdown(
        "Load an option to restore its four flights, or compare "
        "the main cost and timing tradeoffs below."
    )

    for option_number, option in enumerate(
        saved_options,
        start=1,
    ):
        option_id = option["id"]

        option_name = option.get(
            "name",
            f"Option {option_number}",
        )

        saved_selection = {
            route: int(flight_id)
            for route, flight_id
            in option.get(
                "selected_flights",
                {},
            ).items()
        }

        saved_itinerary = calculate_itinerary(
            df,
            saved_selection,
        )

        flight_rows = get_saved_flight_rows(
            df,
            saved_selection,
        )

        is_active = (
            st.session_state.active_saved_option
            == option_id
        )

        sfo_cost = saved_itinerary["costs"]["SFO"]
        bos_cost = saved_itinerary["costs"]["BOS"]
        total_cost = sfo_cost + bos_cost

        sfo_total_wait = total_wait_time(
            saved_itinerary,
            "SFO",
        )

        bos_total_wait = total_wait_time(
            saved_itinerary,
            "BOS",
        )

        # -------------------------------------------------
        # OPTION CARD
        # -------------------------------------------------

        with st.container(border=True):
            # ---------------------------------------------
            # HEADER
            # ---------------------------------------------

            title_column, load_column, delete_column = (
                st.columns(
                    [5, 1.4, 1],
                    vertical_alignment="center",
                )
            )

            with title_column:
                if is_active:
                    st.markdown(
                        f"### {option_name} · Active"
                    )
                else:
                    st.markdown(
                        f"### {option_name}"
                    )

            with load_column:
                if st.button(
                    (
                        "Loaded"
                        if is_active
                        else "Load"
                    ),
                    key=f"load_{option_id}",
                    width="stretch",
                    type=(
                        "primary"
                        if is_active
                        else "secondary"
                    ),
                    disabled=is_active,
                ):
                    st.session_state.selected_flights = (
                        saved_selection.copy()
                    )

                    st.session_state.active_saved_option = (
                        option_id
                    )

                    st.rerun()

            with delete_column:
                if st.button(
                    "Delete",
                    key=f"delete_{option_id}",
                    width="stretch",
                ):
                    delete_option(option_id)

                    if (
                        st.session_state.active_saved_option
                        == option_id
                    ):
                        st.session_state.active_saved_option = (
                            None
                        )

                    st.rerun()

            # ---------------------------------------------
            # RECOGNIZABLE FLIGHT SUMMARY
            # ---------------------------------------------

            inbound_column, outbound_column = st.columns(2)

            with inbound_column:
                st.markdown("**To Atlanta**")

                sfo_inbound = flight_rows.get(
                    "SFO → ATL"
                )

                bos_inbound = flight_rows.get(
                    "BOS → ATL"
                )

                st.caption(
                    "SFO: "
                    + flight_summary(sfo_inbound)
                )

                st.caption(
                    "BOS: "
                    + flight_summary(bos_inbound)
                )

            with outbound_column:
                st.markdown("**From Atlanta**")

                sfo_outbound = flight_rows.get(
                    "ATL → SFO"
                )

                bos_outbound = flight_rows.get(
                    "ATL → BOS"
                )

                st.caption(
                    "SFO: "
                    + flight_summary(sfo_outbound)
                )

                st.caption(
                    "BOS: "
                    + flight_summary(bos_outbound)
                )

            # ---------------------------------------------
            # PRIMARY COMPARISON METRICS
            # ---------------------------------------------

            metric_1, metric_2, metric_3 = st.columns(3)

            with metric_1:
                st.metric(
                    "Blue Ridge Time",
                    format_duration(
                        saved_itinerary[
                            "blue_ridge_duration"
                        ]
                    ),
                    border=True,
                )

            with metric_2:
                st.metric(
                    "Combined Airfare",
                    f"${total_cost:,.0f}",
                    border=True,
                )

            with metric_3:
                meeting_time = saved_itinerary.get(
                    "meeting_time"
                )

                st.metric(
                    "Everyone at ATL",
                    (
                        meeting_time.strftime(
                            "%a %I:%M %p"
                        )
                        if meeting_time is not None
                        else "—"
                    ),
                    border=True,
                )

            # ---------------------------------------------
            # TRAVELER COMPARISON
            # ---------------------------------------------

            sfo_column, bos_column = st.columns(2)

            with sfo_column:
                st.markdown("#### SFO Travelers")

                sfo_metric_1, sfo_metric_2, sfo_metric_3 = (
                    st.columns(3)
                )

                with sfo_metric_1:
                    st.metric(
                        "Cost",
                        f"${sfo_cost:,.0f}",
                    )

                with sfo_metric_2:
                    st.metric(
                        "Time Away",
                        format_duration(
                            saved_itinerary[
                                "time_away"
                            ]["SFO"]
                        ),
                    )

                with sfo_metric_3:
                    st.metric(
                        "ATL Wait",
                        format_duration(
                            sfo_total_wait
                        ),
                    )

            with bos_column:
                st.markdown("#### BOS Travelers")

                bos_metric_1, bos_metric_2, bos_metric_3 = (
                    st.columns(3)
                )

                with bos_metric_1:
                    st.metric(
                        "Cost",
                        f"${bos_cost:,.0f}",
                    )

                with bos_metric_2:
                    st.metric(
                        "Time Away",
                        format_duration(
                            saved_itinerary[
                                "time_away"
                            ]["BOS"]
                        ),
                    )

                with bos_metric_3:
                    st.metric(
                        "ATL Wait",
                        format_duration(
                            bos_total_wait
                        ),
                    )

            # ---------------------------------------------
            # EXPANDED DETAILS
            # ---------------------------------------------

            with st.popover(
                "View flight and timing details",
                width="stretch",
            ):
                st.markdown("### Flights")

                for route in ROUTE_ORDER:
                    display_saved_flight_detail(
                        route,
                        flight_rows.get(route),
                    )

                st.divider()
                st.markdown("### Atlanta Coordination")

                detail_1, detail_2 = st.columns(2)

                with detail_1:
                    st.markdown("**Inbound waits**")

                    for group in ["SFO", "BOS"]:
                        wait = saved_itinerary[
                            "inbound_waits"
                        ].get(group)

                        if wait:
                            st.write(
                                f"{group}: "
                                f"{format_short_datetime(wait['start'])}"
                                f" → "
                                f"{format_short_datetime(wait['end'])}"
                            )

                            st.caption(
                                format_duration(
                                    wait["duration"]
                                )
                            )

                with detail_2:
                    st.markdown("**Return waits**")

                    for group in ["SFO", "BOS"]:
                        wait = saved_itinerary[
                            "outbound_waits"
                        ].get(group)

                        if wait:
                            st.write(
                                f"{group}: "
                                f"{format_short_datetime(wait['start'])}"
                                f" → "
                                f"{format_short_datetime(wait['end'])}"
                            )

                            st.caption(
                                format_duration(
                                    wait["duration"]
                                )
                            )

                st.divider()
                st.markdown("### Blue Ridge")

                blue_ridge_arrival = saved_itinerary.get(
                    "blue_ridge_arrival"
                )

                blue_ridge_departure = saved_itinerary.get(
                    "blue_ridge_departure"
                )

                if (
                    blue_ridge_arrival is not None
                    and blue_ridge_departure is not None
                ):
                    st.write(
                        f"Arrive: "
                        f"{format_datetime(blue_ridge_arrival)}"
                    )

                    st.write(
                        f"Leave: "
                        f"{format_datetime(blue_ridge_departure)}"
                    )

                    st.write(
                        "**Total stay: "
                        f"{format_duration(saved_itinerary['blue_ridge_duration'])}"
                        "**"
                    )
