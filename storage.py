import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4


DEFAULT_FILE = Path("saved_options.json")


def load_saved_options(filename=DEFAULT_FILE):
    path = Path(filename)

    if not path.exists():
        path.write_text("[]", encoding="utf-8")
        return []

    try:
        contents = path.read_text(encoding="utf-8")
        options = json.loads(contents)

        if not isinstance(options, list):
            return []

        return options

    except (json.JSONDecodeError, OSError):
        return []


def write_saved_options(options, filename=DEFAULT_FILE):
    path = Path(filename)

    path.write_text(
        json.dumps(
            options,
            indent=2,
        ),
        encoding="utf-8",
    )


def save_option(
    name,
    selected_flights,
    filename=DEFAULT_FILE,
):
    options = load_saved_options(filename)

    option = {
        "id": str(uuid4()),
        "name": name.strip(),
        "created_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "selected_flights": {
            route: int(flight_id)
            for route, flight_id
            in selected_flights.items()
        },
    }

    options.append(option)
    write_saved_options(options, filename)

    return option


def delete_option(option_id, filename=DEFAULT_FILE):
    options = load_saved_options(filename)

    remaining = [
        option
        for option in options
        if option.get("id") != option_id
    ]

    write_saved_options(remaining, filename)


def rename_option(
    option_id,
    new_name,
    filename=DEFAULT_FILE,
):
    options = load_saved_options(filename)

    for option in options:
        if option.get("id") == option_id:
            option["name"] = new_name.strip()
            break

    write_saved_options(options, filename)