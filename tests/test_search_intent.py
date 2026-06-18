from agents.search_planner_agent import SearchPlannerAgent
from schemas.profile_schema import StudentProfile
from tools.search_intent import (
    OpportunityTypeIntent,
    detect_opportunity_type_intent,
    extract_intent_terms,
    extract_location_intents,
    extract_topic_terms,
    is_opportunity_relevant,
    matches_location_intent,
)


def test_extract_intent_terms_keeps_field_keywords() -> None:
    terms = extract_intent_terms("internships or masters scholarships in quantum physics")
    assert "quantum" in terms
    assert "physics" in terms
    assert "internships" not in terms
    assert "scholarships" not in terms


def test_extract_topic_terms_excludes_geography() -> None:
    terms = extract_topic_terms("AI scholarships in Europe for Pakistani students")
    assert "ai" in terms
    assert "europe" not in terms
    assert "pakistani" not in terms


def test_is_opportunity_relevant_filters_unrelated_field() -> None:
    assert not is_opportunity_relevant(
        "masters scholarships in quantum physics",
        {"title": "Fully funded data science scholarship", "summary": "For ML and AI students"},
    )
    assert is_opportunity_relevant(
        "masters scholarships in quantum physics",
        {"title": "Quantum information masters scholarship", "summary": "For physics students"},
    )


def test_location_intent_filters_requested_country() -> None:
    assert extract_location_intents("software internships in Pakistan") == ["pakistan"]
    assert matches_location_intent(
        "software internships in Pakistan",
        {"title": "Software engineering internship", "country": "Pakistan"},
    )
    assert not matches_location_intent(
        "software internships in Pakistan",
        {"title": "Software engineering internship", "country": "United States"},
    )


def test_nationality_phrase_is_not_location_intent() -> None:
    assert extract_location_intents("AI scholarships for Pakistani students") == []
    assert matches_location_intent(
        "AI scholarships for Pakistani students",
        {"title": "Global AI scholarship", "country": "United States"},
    )


def test_search_planner_anchors_user_request() -> None:
    profile = StudentProfile(field="Data Science", country="Pakistan")
    request = "internships or masters scholarships in quantum physics"
    queries = SearchPlannerAgent()._anchor_user_request(
        request,
        [
            "fully funded data science scholarships Europe 2026",
            "DAAD data science masters Pakistan 2026",
            "data science research internship Europe 2026",
            "Erasmus Mundus data science scholarship 2026",
            "AI scholarships Europe Pakistani students 2027",
        ],
        today=__import__("datetime").date(2026, 6, 12),
        type_intent=detect_opportunity_type_intent(request),
    )
    assert queries[0].endswith("site:.edu official")
    assert "quantum physics" in queries[0]
