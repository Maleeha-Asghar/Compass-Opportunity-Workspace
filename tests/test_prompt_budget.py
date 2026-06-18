from tools.prompt_budget import focus_text, slim_candidate, slim_opportunity, truncate_text


def test_truncate_text_limits_length() -> None:
    assert truncate_text("one two three four five", 10) == "one two th"


def test_focus_text_prioritizes_deadline_sentences() -> None:
    filler = "General website navigation and unrelated blog content. " * 40
    text = f"{filler} Application deadline is 2027-08-15 for international students from Pakistan."
    focused = focus_text(text, 220)
    assert "2027-08-15" in focused
    assert len(focused) <= 220


def test_slim_candidate_omits_page_text() -> None:
    slim = slim_candidate(
        {
            "source_url": "https://example.com",
            "title": "Scholarship",
            "snippet": "short",
            "page_text": "x" * 5000,
            "source_tier": "B",
        }
    )
    assert "page_text" not in slim
    assert slim["source_url"] == "https://example.com"


def test_slim_opportunity_caps_summary() -> None:
    slim = slim_opportunity({"title": "Grant", "summary": "a" * 1000})
    assert len(slim["summary"]) == 400
