from src.discovery.classifier import classify_event


def test_concluding_tour_performance_is_past():
    result = classify_event(
        "PHOTOS: Anuv Jain mesmerises Bengaluru fans "
        "in concluding performance of India tour"
    )
    assert result["status"] == "past_or_recap"


def test_soulful_evening_is_past():
    result = classify_event("Anuv Jain Delivers A Soulful Evening In Hyderabad")
    assert result["status"] == "past_or_recap"


def test_kickstarts_tour_with_show_is_past():
    result = classify_event(
        "Anuv Jain kickstarts his Dastakhat tour "
        "with a soulful show in Delhi"
    )
    assert result["status"] == "past_or_recap"


def test_upcoming_announcement_is_potential():
    result = classify_event("Anuv Jain announces new concert dates for 2027")
    assert result["status"] == "potential_upcoming"


def test_generic_tour_mention_needs_review():
    result = classify_event("Anuv Jain's first US tour")
    assert result["status"] == "needs_review"


def test_past_evidence_takes_priority():
    result = classify_event(
        "Anuv Jain announces tour highlights after a successful show"
    )
    assert result["status"] == "past_or_recap"


def test_generic_performance_mention_needs_review():
    result = classify_event("Anuv Jain discusses his performance and musical journey")
    assert result["status"] == "needs_review"


def test_postponed_concert_needs_review():
    result = classify_event(
        "Anuv Jain postpones Dubai concert scheduled for April 12, "
        "new date awaited"
    )
    assert result["status"] == "needs_review"


def test_upcoming_headline_not_overridden_by_unrelated_past_text():
    result = classify_event(
        "Anuv Jain announces new 2027 concert dates",
        "The article also discusses highlights from his previous tour.",
    )
    assert result["status"] == "potential_upcoming"


def test_past_headline_takes_priority():
    result = classify_event(
        "Anuv Jain mesmerises Hyderabad crowd on Dastakhat tour",
        "The article also mentions upcoming tour plans.",
    )
    assert result["status"] == "past_or_recap"


def test_interview_headline_is_not_promoted_by_future_tour_body():
    result = classify_event(
        "My biggest audience is in Delhi: Anuv Jain ahead of his Dastakhat World Tour",
        "Anuv Jain is set to perform in Delhi on 16 January 2027.",
    )
    assert result["status"] == "needs_review"


def test_event_listing_headline_is_potential_upcoming():
    result = classify_event("Anuv Jain Dastakhat Tour at Variety Playhouse")
    assert result["status"] == "potential_upcoming"


def test_interview_guard_does_not_override_direct_announcement():
    result = classify_event(
        "Anuv Jain announces Delhi concert ahead of his Dastakhat World Tour"
    )
    assert result["status"] == "potential_upcoming"


def test_indulgexpress_emotional_finale_before_global_tour_is_past():
    result = classify_event(
        "Bengaluru hosts Anuv Jain's emotional finale before global tour"
    )
    assert result["status"] == "past_or_recap"


def test_soulful_finale_before_world_tour_is_past():
    result = classify_event("Anuv Jain's soulful finale before his world tour")
    assert result["status"] == "past_or_recap"


def test_future_final_concert_announcement_is_not_marked_past():
    result = classify_event(
        "Anuv Jain announces final concert of his 2027 tour in Delhi"
    )
    assert result["status"] == "potential_upcoming"


def test_generic_finale_word_without_context_needs_review():
    result = classify_event("Anuv Jain discusses the finale of his new album")
    assert result["status"] == "needs_review"
