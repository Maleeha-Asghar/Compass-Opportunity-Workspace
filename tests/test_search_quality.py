from tools.search_intent import (
    OpportunityTypeIntent,
    detect_opportunity_type_intent,
    matches_opportunity_type_intent,
)
from tools.source_policy_gate import SourcePolicyGate


def test_detect_internship_intent() -> None:
    assert detect_opportunity_type_intent("quantum physics internships in Europe") == OpportunityTypeIntent.INTERNSHIP


def test_detect_masters_intent() -> None:
    assert detect_opportunity_type_intent("masters scholarships in quantum physics") == OpportunityTypeIntent.MASTERS


def test_detect_mixed_when_both_requested() -> None:
    assert (
        detect_opportunity_type_intent("internships or masters scholarships in physics")
        == OpportunityTypeIntent.MIXED
    )


def test_matches_internship_type() -> None:
    assert matches_opportunity_type_intent(
        OpportunityTypeIntent.INTERNSHIP,
        {"title": "Summer research internship", "summary": "Undergraduate placement"},
    )
    assert not matches_opportunity_type_intent(
        OpportunityTypeIntent.INTERNSHIP,
        {"title": "MSc scholarship", "summary": "Fully funded masters program"},
    )


def test_reddit_is_denied() -> None:
    assert SourcePolicyGate.search_result_score("https://www.reddit.com/r/scholarships/post") is None


def test_edu_domain_is_preferred() -> None:
    edu_score = SourcePolicyGate.search_result_score("https://physics.mit.edu/internships")
    reddit_score = SourcePolicyGate.search_result_score("https://www.reddit.com/r/scholarships")
    aggregator_score = SourcePolicyGate.search_result_score("https://www.scholarshipsads.com/list")
    assert edu_score == 100
    assert reddit_score is None
    assert aggregator_score is None


def test_rank_search_results_prefers_official_domains() -> None:
    ranked = SourcePolicyGate.rank_search_results(
        [
            {"url": "https://www.scholarshipsads.com/a", "title": "A"},
            {"url": "https://physics.stanford.edu/internships", "title": "B"},
            {"url": "https://www.reddit.com/r/a", "title": "C"},
            {"url": "https://gradschool.cornell.edu/funding", "title": "D"},
        ],
        min_results=2,
    )
    urls = [item["url"] for item in ranked]
    assert "https://physics.stanford.edu/internships" in urls
    assert "https://gradschool.cornell.edu/funding" in urls
    assert all("reddit.com" not in url for url in urls)
