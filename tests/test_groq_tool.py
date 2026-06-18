from tools.groq_tool import GroqClient


def test_parse_json_ignores_trailing_text() -> None:
    parsed = GroqClient._parse_json(
        '{"title": "DAAD Scholarship", "deadline": null, "warnings": []}\n\nAdditional commentary here.'
    )
    assert parsed["title"] == "DAAD Scholarship"
    assert parsed["warnings"] == []


def test_parse_json_strips_markdown_fence() -> None:
    parsed = GroqClient._parse_json(
        '```json\n{"queries": ["data science scholarships 2026"]}\n```'
    )
    assert parsed["queries"] == ["data science scholarships 2026"]
