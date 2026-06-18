from tools.prompt_loader import load_prompt, render_prompt


def test_load_opportunity_system_prompt() -> None:
    prompt = load_prompt("opportunity_extraction_system.txt")
    assert "Opportunity Extraction Agent" in prompt
    assert "Never invent information" in prompt


def test_render_opportunity_user_prompt() -> None:
    prompt = render_prompt(
        "opportunity_extraction_user.txt",
        source_url="https://example.edu/scholarship",
        title="Example Scholarship",
        deadline_analysis="None found.",
        table_data="None found.",
        content="Apply by 2026-12-01.",
    )
    assert "https://example.edu/scholarship" in prompt
    assert "Apply by 2026-12-01." in prompt
    assert '"is_opportunity"' in prompt
