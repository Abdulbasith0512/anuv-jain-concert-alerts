import re


# Strong evidence that the specific event has already happened.
# Generic words such as "performance" are deliberately excluded.
PAST_PATTERNS = [
    r"\bperformed\b",
    r"\bwrapped\s+up\b",
    r"\bwraps\s+up\b",
    r"\bconcluded\b",
    r"\bconcluding\s+performance\b",
    r"\blast\s+night\b",
    r"\byesterday\b",
    r"\bafter\s+the\s+show\b",
    r"\bafter\s+a\s+successful\s+show\b",
    r"\bpost[- ]concert\b",
    r"\bconcertgoers\s+enjoyed\b",
    r"\bperformance\s+review\b",
    r"\brecap\b",
    r"\bhighlights\s+from\b",
    r"\bphotos?\s+(?:from|of)\b",
    r"\bmesmer(?:ises|ized|ised)\b",
    r"\bdelivers?\s+a\s+soulful\s+evening\b",
    r"\bkickstarts?\s+(?:his|her|the)\s+.*\s+tour\s+with\b",
    r"\b(?:fans|crowd)\s+(?:enjoyed|attended|cheered|welcomed)\b",
    r"\bwas\s+held\b",
    r"\btook\s+place\b",
    r"\bmade\s+an\s+appearance\s+at\b",
    r"\bpost[- ]tour\b",
    r"\bfarewell\s+show\b",
    # Retrospective finale language. Keep these specific so a future
    # announcement of a tour's final date is not automatically rejected.
    r"\b(?:emotional|soulful|grand|memorable)\s+finale\b",
    r"\bfinale\s+(?:before|after|following)\b",
    r"\bfinal\s+(?:show|performance|concert)\s+(?:was|has\s+been)\s+held\b",
]


UPCOMING_PATTERNS = [
    r"\bannounc(?:e|es|ed|ement)\b",
    r"\bannounced\s+for\b",
    r"\bannounced\s+as\s+part\s+of\b",
    r"\bline[- ]?up\s+(?:is\s+)?announced\b",
    r"\bupcoming\b",
    r"\bset\s+to\s+(?:perform|serenade|headline|take\s+the\s+stage)\b",
    r"\bwill\s+perform\b",
    r"\bwill\s+headline\b",
    r"\bwill\s+take\s+the\s+stage\b",
    r"\bcoming\s+to\b",
    r"\bnew\s+dates?\b",
    r"\badds?\s+(?:a\s+)?(?:new\s+)?(?:show|date|city)\b",
    r"\btickets?\s+(?:are\s+)?(?:on\s+sale|available|out)\b",
    r"\bbook(?:ing)?\s+(?:is\s+)?open\b",
    r"\bpre[- ]sale\b",
    r"\bpresale\b",
    r"\btour\s+dates?\b",
    r"\bto\s+perform\b",
    r"\blive\s+in\s+concert\b",
    r"\bconcert\s+in\b",
    r"\bscheduled\s+to\s+perform\b",
    r"\bnew\s+tour\b",
    r"\bbrings?\b.{0,100}\bto\s+the\s+stage\b",
]

# A listing-style headline can identify an event even when it does not use
# announcement language (for example, "Dastakhat Tour at Variety Playhouse").
EVENT_LISTING_PATTERNS = [
    r"\b(?:tour|concert|show|gig)\s+at\s+(?:the\s+)?[A-Z]",
]

# Editorial/interview headlines must not be promoted solely because the body
# mentions future tour plans or dates. These are deliberately headline-only.
EDITORIAL_HEADLINE_PATTERNS = [
    r"\binterview\b",
    r"\bahead\s+of\b",
    r"\bspeaks?\s+(?:about|with)\b",
    r"\btalks?\s+about\b",
    r"\bin\s+conversation\b",
    r"\bq\s*&\s*a\b",
    r"\bprofile\b",
]

POSTPONED_PATTERNS = [
    r"\bpostpon(?:e|ed|es|ing)\b",
    r"\bdate\s+awaited\b",
    r"\bnew\s+date\s+(?:is\s+)?(?:awaited|pending|to\s+be\s+announced)\b",
    r"\brescheduled\b",
    r"\bpostponement\b",
]


def _matches(patterns: list[str], text: str) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, text, re.IGNORECASE)]


def classify_event(title: str, description: str = "") -> dict:
    """Classify an Anuv Jain article; potential_upcoming is not verification."""
    title_text = re.sub(r"\s+", " ", title or "").strip().lower()
    description_text = re.sub(r"\s+", " ", description or "").strip().lower()

    if _matches(POSTPONED_PATTERNS, title_text):
        return {
            "status": "needs_review",
            "reason": "The event appears to have been postponed or rescheduled; its new date needs verification.",
        }

    if _matches(PAST_PATTERNS, title_text):
        return {
            "status": "past_or_recap",
            "reason": "The headline contains retrospective or completed-event language.",
        }

    # An interview/profile is not an event listing. Do not let future-tour
    # language buried in its body turn it into a concert alert.
    is_editorial_headline = bool(_matches(EDITORIAL_HEADLINE_PATTERNS, title_text))
    is_event_listing = bool(_matches(EVENT_LISTING_PATTERNS, title_text))
    if is_editorial_headline and not is_event_listing and not _matches(UPCOMING_PATTERNS, title_text):
        return {
            "status": "needs_review",
            "reason": "The headline appears to be an interview or editorial article, not a direct event listing.",
        }

    if _matches(UPCOMING_PATTERNS, title_text) or is_event_listing:
        return {
            "status": "potential_upcoming",
            "reason": "The headline indicates a possible upcoming event, event listing, or announcement.",
        }

    if _matches(POSTPONED_PATTERNS, description_text):
        return {
            "status": "needs_review",
            "reason": "The article mentions postponement or rescheduling; the current event date needs verification.",
        }

    if _matches(PAST_PATTERNS, description_text):
        return {
            "status": "past_or_recap",
            "reason": "The article content contains retrospective or completed-event language.",
        }

    if _matches(UPCOMING_PATTERNS, description_text):
        return {
            "status": "potential_upcoming",
            "reason": "The article content indicates a possible upcoming event or ticket announcement.",
        }

    return {
        "status": "needs_review",
        "reason": "Insufficient evidence to determine event status.",
    }
