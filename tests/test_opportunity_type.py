from tools.opportunity_type import normalize_opportunity_type, opportunity_display_group


def test_normalize_opportunity_type_detects_masters_before_scholarship() -> None:
    result = normalize_opportunity_type(
        {
            "opportunity_type": "Scholarship",
            "title": "Fully funded MSc Data Science scholarship",
            "summary": "Masters program for international students",
        }
    )

    assert result == "masters"


def test_normalize_opportunity_type_keeps_internship_authoritative() -> None:
    result = normalize_opportunity_type(
        {
            "opportunity_type": "internship",
            "title": "Summer research placement",
        }
    )

    assert result == "internship"


def test_normalize_opportunity_type_covers_other_categories() -> None:
    assert normalize_opportunity_type({"title": "Postdoctoral fellowship"}) == "fellowship"
    assert normalize_opportunity_type({"title": "Graduate assistantship"}) == "assistantship"
    assert normalize_opportunity_type({"title": "General funding award"}) == "other"


def test_opportunity_display_group_is_authoritative() -> None:
    assert opportunity_display_group("masters") == "masters"
    assert opportunity_display_group("internship") == "internships"
    assert opportunity_display_group("scholarship") == "other"
