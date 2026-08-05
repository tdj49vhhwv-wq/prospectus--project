"""Investor-row evaluation inside compatible financing events."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from .event_evaluator import _date_compatibility, _metric, _type_compatibility
from .normalize import (
    NormalizedValue,
    normalize_date,
    normalize_event_type,
    normalize_name,
    normalize_number,
)


NUMERIC_FIELDS = {
    "amount_subscribed": "万元",
    "shares_subscribed": "万股",
    "price_per_share": "元/股",
}


@dataclass(frozen=True)
class PreparedInvestor:
    record_id: str
    stock_code: str
    event_type: str
    date: NormalizedValue
    investor_name: str
    raw: dict


@dataclass
class InvestorEvaluationResult:
    matches: List[dict]
    false_positives: List[dict]
    false_negatives: List[dict]
    metrics: Dict[str, object]
    field_metrics: Dict[str, dict]

    @property
    def tp(self) -> int:
        return len(self.matches)

    @property
    def fp(self) -> int:
        return len(self.false_positives)

    @property
    def fn(self) -> int:
        return len(self.false_negatives)


def _prepare(
    rows: Iterable[dict], side: str, aliases: Mapping[str, str]
) -> List[PreparedInvestor]:
    prepared = []
    for index, row in enumerate(rows, 1):
        id_fields = ("gold_id", "event_id") if side == "gold" else ("auto_id", "event_id")
        record_id = next((str(row.get(field)) for field in id_fields if row.get(field)), None)
        if record_id is None:
            record_id = f"{side[0].upper()}{index:06d}"
        prepared.append(
            PreparedInvestor(
                record_id=record_id,
                stock_code=str(row.get("stock_code", "")),
                event_type=normalize_event_type(
                    row.get("event_context", row.get("type", row.get("rule")))
                ),
                date=normalize_date(row.get("subscription_date", row.get("date"))),
                investor_name=normalize_name(
                    row.get("subscriber_name", row.get("investor_name", row.get("party"))),
                    aliases,
                ),
                raw=dict(row),
            )
        )
    return prepared


def _compatible(gold: PreparedInvestor, auto: PreparedInvestor) -> Optional[int]:
    if not gold.stock_code or gold.stock_code != auto.stock_code:
        return None
    if not gold.investor_name or gold.investor_name != auto.investor_name:
        return None
    type_result = _type_compatibility(gold.event_type, auto.event_type)
    date_result = _date_compatibility(gold.date, auto.date)
    if type_result is None or date_result is None:
        return None
    return type_result[0] + date_result[0]


def _field_status(gold: dict, auto: dict, field: str, source_unit: str) -> str:
    gold_value = normalize_number(gold.get(field), source_unit)
    auto_value = normalize_number(auto.get(field), source_unit)
    if gold_value.status == "missing":
        return "gold_not_disclosed"
    if gold_value.status != "normalized":
        return "gold_invalid"
    if auto_value.status == "missing":
        return "auto_missing"
    if auto_value.status != "normalized":
        return "auto_invalid"
    gold_number = float(gold_value.value)
    auto_number = float(auto_value.value)
    tolerance = max(abs(gold_number) * 0.005, 1e-9)
    return "match" if abs(auto_number - gold_number) <= tolerance else "mismatch"


def _metrics(
    matched: List[Tuple[PreparedInvestor, PreparedInvestor]],
    fps: List[PreparedInvestor],
    fns: List[PreparedInvestor],
) -> Dict[str, object]:
    by_company = defaultdict(lambda: [0, 0, 0])
    by_type = defaultdict(lambda: [0, 0, 0])
    for gold, _auto in matched:
        by_company[gold.stock_code][0] += 1
        by_type[gold.event_type][0] += 1
    for auto in fps:
        by_company[auto.stock_code][1] += 1
        by_type[auto.event_type][1] += 1
    for gold in fns:
        by_company[gold.stock_code][2] += 1
        by_type[gold.event_type][2] += 1
    return {
        "overall": _metric(len(matched), len(fps), len(fns)),
        "by_company": {key: _metric(*value) for key, value in sorted(by_company.items())},
        "by_event_type": {key: _metric(*value) for key, value in sorted(by_type.items())},
    }


def evaluate_investors(
    gold_rows: Iterable[dict],
    auto_rows: Iterable[dict],
    aliases: Optional[Mapping[str, str]] = None,
) -> InvestorEvaluationResult:
    aliases = aliases or {}
    gold = _prepare(gold_rows, "gold", aliases)
    auto = _prepare(auto_rows, "auto", aliases)
    edges = defaultdict(list)
    for auto_index, auto_row in enumerate(auto):
        for gold_index, gold_row in enumerate(gold):
            score = _compatible(gold_row, auto_row)
            if score is not None:
                edges[auto_index].append((gold_index, score))
        edges[auto_index].sort(key=lambda edge: (-edge[1], gold[edge[0]].record_id))

    processing_order = sorted(
        range(len(auto)),
        key=lambda index: (
            -max((edge[1] for edge in edges[index]), default=-1),
            len(edges[index]),
            auto[index].record_id,
        ),
    )
    gold_to_auto: Dict[int, int] = {}

    def augment(auto_index: int, visited_gold: set) -> bool:
        for gold_index, _score in edges[auto_index]:
            if gold_index in visited_gold:
                continue
            visited_gold.add(gold_index)
            current = gold_to_auto.get(gold_index)
            if current is None or augment(current, visited_gold):
                gold_to_auto[gold_index] = auto_index
                return True
        return False

    for auto_index in processing_order:
        augment(auto_index, set())

    auto_to_gold = {auto_index: gold_index for gold_index, auto_index in gold_to_auto.items()}
    match_rows = []
    matched_pairs = []
    field_counts = {field: Counter() for field in NUMERIC_FIELDS}
    for auto_index, gold_index in sorted(
        auto_to_gold.items(), key=lambda item: auto[item[0]].record_id
    ):
        gold_row = gold[gold_index]
        auto_row = auto[auto_index]
        statuses = {
            field: _field_status(gold_row.raw, auto_row.raw, field, unit)
            for field, unit in NUMERIC_FIELDS.items()
        }
        for field, status in statuses.items():
            field_counts[field][status] += 1
        matched_pairs.append((gold_row, auto_row))
        match_rows.append(
            {
                "auto_id": auto_row.record_id,
                "gold_id": gold_row.record_id,
                "stock_code": gold_row.stock_code,
                "event_type": gold_row.event_type,
                "investor_name": gold_row.raw.get("subscriber_name"),
                "name_match": "normalized_exact",
                "field_status": statuses,
            }
        )

    fps = [row for index, row in enumerate(auto) if index not in auto_to_gold]
    fns = [row for index, row in enumerate(gold) if index not in gold_to_auto]
    return InvestorEvaluationResult(
        matches=match_rows,
        false_positives=[dict(row.raw, auto_id=row.record_id) for row in fps],
        false_negatives=[dict(row.raw, gold_id=row.record_id) for row in fns],
        metrics=_metrics(matched_pairs, fps, fns),
        field_metrics={field: dict(counts) for field, counts in field_counts.items()},
    )
