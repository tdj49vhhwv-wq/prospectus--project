"""Traceable normalization that never invents undisclosed values."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional, Union


CanonicalValue = Optional[Union[str, float]]


@dataclass(frozen=True)
class NormalizedValue:
    raw: Any
    value: CanonicalValue
    status: str
    precision: Optional[str] = None
    reason: Optional[str] = None
    unit: Optional[str] = None


DATE_PATTERNS = (
    (re.compile(r"^(\d{4})[-年](\d{1,2})[-月](\d{1,2})(?:日)?$"), "day", "%Y-%m-%d"),
    (re.compile(r"^(\d{4})[-年](\d{1,2})(?:月)?$"), "month", "%Y-%m"),
    (re.compile(r"^(\d{4})$"), "year", "%Y"),
)


def normalize_date(value: Any) -> NormalizedValue:
    if value is None or (isinstance(value, str) and not value.strip()):
        return NormalizedValue(value, None, "missing", reason="not_disclosed")
    if not isinstance(value, str):
        return NormalizedValue(value, None, "invalid", reason="date_must_be_text")

    raw = value
    text = re.sub(r"\s+", "", value.strip())
    for pattern, precision, output_format in DATE_PATTERNS:
        match = pattern.fullmatch(text)
        if not match:
            continue
        parts = [int(part) for part in match.groups()]
        normalized_input = "-".join(
            [f"{parts[0]:04d}"] + [f"{part:02d}" for part in parts[1:]]
        )
        try:
            parsed = datetime.strptime(normalized_input, output_format)
        except ValueError:
            return NormalizedValue(raw, None, "invalid", reason="invalid_calendar_date")
        return NormalizedValue(
            raw,
            parsed.strftime(output_format),
            "normalized",
            precision=precision,
        )
    return NormalizedValue(raw, None, "invalid", reason="unsupported_date_format")


UNIT_FACTORS = {
    "元": (1.0, "元"),
    "万元": (10000.0, "元"),
    "股": (1.0, "股"),
    "万股": (10000.0, "股"),
    "元/股": (1.0, "元/股"),
}


def normalize_number(value: Any, source_unit: str) -> NormalizedValue:
    if value is None or (isinstance(value, str) and not value.strip()):
        return NormalizedValue(
            value, None, "missing", reason="not_disclosed", unit=UNIT_FACTORS.get(source_unit, (1, source_unit))[1]
        )
    if source_unit not in UNIT_FACTORS:
        return NormalizedValue(
            value, None, "invalid", reason=f"unsupported_unit:{source_unit}"
        )
    if isinstance(value, bool):
        return NormalizedValue(value, None, "invalid", reason="not_numeric")

    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return NormalizedValue(value, None, "invalid", reason="not_numeric")
    factor, canonical_unit = UNIT_FACTORS[source_unit]
    return NormalizedValue(
        value,
        number * factor,
        "normalized",
        reason=f"converted_from:{source_unit}",
        unit=canonical_unit,
    )


BRACKET_TRANSLATION = str.maketrans({"（": "(", "）": ")"})


def _basic_name(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", "", str(value).translate(BRACKET_TRANSLATION)).casefold()


def normalize_name(value: Any, aliases: Optional[Mapping[str, str]] = None) -> str:
    normalized = _basic_name(value)
    if not aliases:
        return normalized
    normalized_aliases = {
        _basic_name(alias): _basic_name(canonical) for alias, canonical in aliases.items()
    }
    return normalized_aliases.get(normalized, normalized)


def normalize_event_type(value: Any) -> str:
    text = re.sub(r"\s+", "", str(value or ""))
    if text == "增资及股权转让":
        return text
    if text.startswith("增资") or text == "员工持股平台出资":
        return "增资"
    if text in {"股改", "整体变更"}:
        return "整体变更"
    if text in {"资本公积转增", "吸收合并", "其他"}:
        return "其他"
    if text == "设立":
        return "设立"
    if "股权转让" in text:
        return "股权转让"
    return text
