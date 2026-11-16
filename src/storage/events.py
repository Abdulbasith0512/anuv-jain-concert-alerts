
import json
import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
EVENTS_FILE = DATA_DIR / "events.json"


def load_events() -> list[dict[str, Any]]:
    """Load previously discovered events."""

    if not EVENTS_FILE.exists():
        return []

    try:
        with EVENTS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Event storage is corrupted: {EVENTS_FILE}"
        ) from exc

    if not isinstance(data, list):
        raise RuntimeError("Event storage must contain a JSON list.")

    return data


def save_events(events: list[dict[str, Any]]) -> None:
    """Atomically save event records."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    temporary_file = EVENTS_FILE.with_suffix(".tmp")

    try:
        with temporary_file.open("w", encoding="utf-8") as file:
            json.dump(
                events,
                file,
                indent=2,
                ensure_ascii=False,
            )
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary_file, EVENTS_FILE)

    finally:
        if temporary_file.exists():
            temporary_file.unlink()


def add_event(event: dict[str, Any]) -> bool:
    """
    Add an event if its ID is not already stored.

    Returns True when a new event is added.
    """

    event_id = event.get("id")

    if not event_id:
        raise ValueError("Event must contain a unique ID.")

    events = load_events()

    if any(existing.get("id") == event_id for existing in events):
        return False

    events.append(event)
    save_events(events)

    return True
