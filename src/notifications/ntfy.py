
import logging

import requests

from src.config import NTFY_TOPIC, REQUEST_TIMEOUT


logger = logging.getLogger(__name__)

NTFY_BASE_URL = "https://ntfy.sh"


def send_notification(
    title: str,
    message: str,
    click_url: str = "",
    priority: str = "default",
) -> bool:
    """Send a notification through ntfy."""

    if not NTFY_TOPIC:
        logger.warning("NTFY_TOPIC is not configured.")
        return False

    if not title or not message:
        raise ValueError("Notification title and message are required.")

    url = f"{NTFY_BASE_URL}/{NTFY_TOPIC}"

    headers = {
        "Title": title,
        "Priority": priority,
        "Tags": "musical_notes",
    }

    if click_url:
        headers["Click"] = click_url

    response = requests.post(
        url,
        data=message.encode("utf-8"),
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    logger.info("Notification successfully delivered.")

    return True
