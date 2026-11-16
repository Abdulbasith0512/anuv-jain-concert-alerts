
import re


# Articles describing events that have already happened.
PAST_PATTERNS = [
    r"\bperformed\b",
    r"\bwrapped up\b",
    r"\bconcluded\b",
    r"\blast night\b",
    r"\byesterday\b",
    r"\bafter the show\b",
    r"\bpost[- ]concert\b",
    r"\bconcertgoers enjoyed\b",
    r"\bperformance review\b",
    r"\brecap\b",
]


# Language suggesting a new or upcoming event.
UPCOMING_PATTERNS = [
    r"\bannounces?\b",
    r"\bannouncement\b",
    r"\bupcoming\b",
    r"\bset to perform\b",
    r"\bwill perform\b",
    r"\bcoming to\b",
    r"\bnew dates?\b",
    r"\badds? (?:a )?(?:new )?(?:show|date|city)\b",
    r"\btickets? (?:are )?(?:on sale|available|out)\b",
    r"\bbook(?:ing)? (?:is )?open\b",
    r"\bpre[- ]sale\b",
    r"\bpresale\b",
    r"\btour dates?\b",
    r"\bto perform\b",
    r"\blive in\b",
    r"\bconcert in\b",
]


def classify_event(
    title: str,
    description: str = "",
) -> dict:
    """
    Classify an Anuv Jain-related article.

    Returns:
        status:
            potential_upcoming
            past_or_recap
            needs_review

        reason:
            Explanation of classification.
    """

    text = f"{title} {description}".lower()

    # First identify clearly past-event language.
    past_matches = [
        pattern
        for pattern in PAST_PATTERNS
        if re.search(pattern, text)
    ]

    if past_matches:
        return {
            "status": "past_or_recap",
            "reason": "Contains past-event language",
        }

    # Identify potential upcoming announcements.
    upcoming_matches = [
        pattern
        for pattern in UPCOMING_PATTERNS
        if re.search(pattern, text)
    ]

    if upcoming_matches:
        return {
            "status": "potential_upcoming",
            "reason": "Contains upcoming event or ticket language",
        }

    # Do not assume an unclear article is a concert.
    return {
        "status": "needs_review",
        "reason": "Insufficient evidence to determine event status",
    }
