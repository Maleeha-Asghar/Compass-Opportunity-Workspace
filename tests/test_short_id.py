import pytest

from tools.short_id import (
    format_compass_user_id,
    generate_opportunity_id,
    normalize_compass_user_id,
    normalize_opportunity_id,
)


def test_generate_opportunity_id_is_eight_characters() -> None:
    value = generate_opportunity_id()
    assert len(value) == 8
    assert value.isalnum()
    assert value == value.lower()


def test_normalize_opportunity_id_rejects_long_values() -> None:
    with pytest.raises(ValueError, match="1-8 characters"):
        normalize_opportunity_id("abcd12345")


def test_normalize_opportunity_id_lowercases() -> None:
    assert normalize_opportunity_id("A1B") == "a1b"


def test_format_compass_user_id() -> None:
    assert format_compass_user_id(1) == "cu_1"
    assert format_compass_user_id(42) == "cu_42"


def test_normalize_compass_user_id() -> None:
    assert normalize_compass_user_id("CU_7") == "cu_7"
    with pytest.raises(ValueError):
        normalize_compass_user_id("user-123")
