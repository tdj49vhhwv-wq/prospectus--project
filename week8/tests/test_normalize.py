import pytest

from week8.evaluation.normalize import (
    normalize_date,
    normalize_event_type,
    normalize_name,
    normalize_number,
)


@pytest.mark.parametrize(
    ("raw", "value", "precision"),
    [
        ("2021-08-25", "2021-08-25", "day"),
        ("2021年8月25日", "2021-08-25", "day"),
        ("2021-8", "2021-08", "month"),
        ("2021年8月", "2021-08", "month"),
        ("2018", "2018", "year"),
    ],
)
def test_normalize_date_preserves_disclosed_precision(raw, value, precision):
    result = normalize_date(raw)
    assert result.value == value
    assert result.precision == precision
    assert result.status == "normalized"


def test_normalize_date_does_not_invent_a_missing_value():
    result = normalize_date(None)
    assert result.value is None
    assert result.status == "missing"
    assert result.reason == "not_disclosed"


def test_normalize_date_marks_invalid_calendar_dates():
    result = normalize_date("2021-13-40")
    assert result.value is None
    assert result.status == "invalid"


@pytest.mark.parametrize(
    ("raw", "source_unit", "value", "canonical_unit"),
    [
        (1.2, "万元", 12000.0, "元"),
        ("1,234.5", "万元", 12345000.0, "元"),
        (3, "万股", 30000.0, "股"),
        ("5.41", "元/股", 5.41, "元/股"),
    ],
)
def test_normalize_number_uses_only_the_explicit_source_unit(
    raw, source_unit, value, canonical_unit
):
    result = normalize_number(raw, source_unit)
    assert result.value == value
    assert result.unit == canonical_unit
    assert result.status == "normalized"


def test_normalize_number_keeps_null_as_missing_instead_of_zero():
    result = normalize_number(None, "万元")
    assert result.value is None
    assert result.status == "missing"


def test_normalize_number_rejects_unknown_units():
    result = normalize_number(100, "美元")
    assert result.value is None
    assert result.status == "invalid"
    assert result.reason == "unsupported_unit:美元"


def test_normalize_name_applies_bracket_and_alias_normalization():
    aliases = {
        "稳正景明": "深圳市稳正景明创业投资企业(有限合伙)",
    }
    assert normalize_name(" 稳正景明 ", aliases) == normalize_name(
        "深圳市稳正景明创业投资企业（有限合伙）", aliases
    )


def test_normalize_name_is_case_and_space_insensitive_for_english_names():
    assert normalize_name("EARN ACE LIMITED") == normalize_name("earn  ace limited")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("增资_标准发行", "增资"),
        ("员工持股平台出资", "增资"),
        ("股改", "整体变更"),
        ("资本公积转增", "其他"),
        ("股权转让", "股权转让"),
        ("增资及股权转让", "增资及股权转让"),
    ],
)
def test_normalize_event_type_uses_explicit_mapping(raw, expected):
    assert normalize_event_type(raw) == expected
