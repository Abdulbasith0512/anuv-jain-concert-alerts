
import os
from dotenv import load_dotenv

load_dotenv()

ARTIST_NAME = "Anuv Jain"

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "").strip()

CITY_FILTER = [
    city.strip().lower()
    for city in os.getenv("CITY_FILTER", "").split(",")
    if city.strip()
]

REQUEST_TIMEOUT = int(
    os.getenv("REQUEST_TIMEOUT", "20")
)

EVENT_KEYWORDS = [
    "concert",
    "live",
    "tour",
    "fest",
    "tickets",
    "show",
    "performing",
    "performance",
    "lineup",
    "line-up",
    "headline",
    "gig",
]


def is_relevant_event(title: str, description: str = "") -> bool:
    text = f"{title} {description}".lower()

    artist_found = ARTIST_NAME.lower() in text

    event_found = any(
        keyword in text
        for keyword in EVENT_KEYWORDS
    )

    if not artist_found or not event_found:
        return False

    if CITY_FILTER:
        return any(city in text for city in CITY_FILTER)

    return True
