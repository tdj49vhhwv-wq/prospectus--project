"""Strict, deterministic, one-to-one event evaluation."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from .normalize import NormalizedValue, normalize_date, normalize_event_type


@dataclass(frozen=True)
class PreparedEvent:
    record_id: str
    stock_code: str
    event_type: str
    date: NormalizedValue
    raw: dict


@dataclass
class EvaluationResult:
    matches: List[dict]
    false_positives: List[dict]
    false_negatives: List[dict]
    metrics: Dict[str, object]

    @property
    def tp(self) -> int:
        return len(self.matches)

    @property
    def fp(self) -> int:
        return len(self.false_positives)

    @property
    def fn(self) -> int:
        return len(self.false_negatives)


def _stable_group_id(prefix: str, key: tuple) -> str:
    digest = hashlib.sha256(repr(key).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _collapse_rows(rows: Iterable[dict], side: str) -> List[dict]:
    groups = defaultdict(list)
    for index, original in enumerate(rows, 1):
        row = dict(original)
        record_id = row.get("gold_id" if side == "gold" else "auto_id") or row.get("event_id")
        row["_member_id"] = str(record_id or f"{side[0].upper()}{index:06d}")
        code = str(row.get("stock_code", ""))
        date_value = row.get("subscription_date", row.get("date"))
        normalized_date = normalize_date(date_value)
        event_type = normalize_event_type(
            row.get("event_context", row.get("type", row.get("rule")))
        )
        if side == "gold":
            key = (
                code,
                normalized_date.value,
                event_type,
                str(row.get("source_page", "")),
                str(row.get("evidence_text", "")),
            )
        elif normalized_date.status == "normalized":
            key = (code, normalized_date.value, event_type)
        else:
            key = (
                code,
                "undated",
                event_type,
                str(row.get("source_page", "")),
                str(row.get("evidence_text", "")),
            )
        groups[key].append(row)

    collapsed = []
    for key, members in sorted(groups.items(), key=lambda item: repr(item[0])):
        members.sort(key=lambda row: row["_member_id"])
        representative = {k: v for k, v in members[0].items() if k != "_member_id"}
        member_ids = [row["_member_id"] for row in members]
        id_field = "gold_id" if side == "gold" else "auto_id"
        representative[id_field] = _stable_group_id("GE" if side == "gold" else "AE", key)
        representative["member_ids"] = member_ids
        representative["investor_count"] = len(member_ids)
        collapsed.append(representative)
    return collapsed


def collapse_gold_rows_to_events(rows: Iterable[dict]) -> List[dict]:
    return _collapse_rows(rows, "gold")


def collapse_auto_rows_to_events(rows: Iterable[dict]) -> List[dict]:
    return _collapse_rows(rows, "auto")


def _prepare(rows: Iterable[dict], side: str) -> List[PreparedEvent]:
    id_fields = ("gold_id", "event_id") if side == "gold" else ("auto_id", "event_id")
    prepared = []
    for index, row in enumerate(rows, 1):
        record_id = next((str(row.get(field)) for field in id_fields if row.get(field)), None)
        if record_id is None:
            prefix = "G" if side == "gold" else "A"
            record_id = f"{prefix}{index:06d}"
        date_value = row.get("subscription_date", row.get("date"))
        type_value = row.get("event_context", row.get("type", row.get("rule")))
        prepared.append(
            PreparedEvent(
                record_id=record_id,
                stock_code=str(row.get("stock_code", "")),
                event_type=normalize_event_type(type_value),
                date=normalize_date(date_value),
                raw=dict(row),
            )
        )
    return prepared


def _date_compatibility(gold_date: NormalizedValue, auto_date: NormalizedValue) -> Optional[Tuple[int, str]]:
    if gold_date.status != "normalized" or auto_date.status != "normalized":
        return None
    gold_value = str(gold_date.value)
    auto_value = str(auto_date.value)
    if gold_date.precision == "day":
        return (30, "exact_day") if auto_date.precision == "day" and gold_value == auto_value else None
    if gold_date.precision == "month":
        return (20, "gold_month") if auto_value[:7] == gold_value[:7] else None
    if gold_date.precision == "year":
        return (10, "gold_year") if auto_value[:4] == gold_value[:4] else None
    return None


def _type_compatibility(gold_type: str, auto_type: str) -> Optional[Tuple[int, str]]:
    if gold_type == auto_type and gold_type:
        return 2, "exact"
    if gold_type == "增资及股权转让" and auto_type in {"增资", "股权转让"}:
        return 1, "composite_component"
    return None


def _compatibility(gold: PreparedEvent, auto: PreparedEvent) -> Optional[Tuple[int, str, str]]:
    if not gold.stock_code or gold.stock_code != auto.stock_code:
        return None
    type_match = _type_compatibility(gold.event_type, auto.event_type)
    if type_match is None:
        return None
    date_match = _date_compatibility(gold.date, auto.date)
    if date_match is None:
        return None
    return date_match[0] + type_match[0], date_match[1], type_match[1]


def _metric(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    if precision is None or recall is None:
        f1 = None
    elif precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": None if precision is None else round(precision, 6),
        "recall": None if recall is None else round(recall, 6),
        "f1": None if f1 is None else round(f1, 6),
    }


def _group_metrics(
    matched: List[Tuple[PreparedEvent, PreparedEvent]],
    false_positives: List[PreparedEvent],
    false_negatives: List[PreparedEvent],
) -> Dict[str, object]:
    by_company = defaultdict(lambda: [0, 0, 0])
    by_type = defaultdict(lambda: [0, 0, 0])
    for gold, _auto in matched:
        by_company[gold.stock_code][0] += 1
        by_type[gold.event_type][0] += 1
    for auto in false_positives:
        by_company[auto.stock_code][1] += 1
        by_type[auto.event_type][1] += 1
    for gold in false_negatives:
        by_company[gold.stock_code][2] += 1
        by_type[gold.event_type][2] += 1
    return {
        "overall": _metric(len(matched), len(false_positives), len(false_negatives)),
        "by_company": {
            key: _metric(*counts) for key, counts in sorted(by_company.items())
        },
        "by_event_type": {
            key: _metric(*counts) for key, counts in sorted(by_type.items())
        },
    }


def evaluate_events(gold_rows: Iterable[dict], auto_rows: Iterable[dict]) -> EvaluationResult:
    gold = _prepare(gold_rows, "gold")
    auto = _prepare(auto_rows, "auto")

    edges: Dict[int, List[Tuple[int, int, str, str]]] = defaultdict(list)
    for auto_index, auto_event in enumerate(auto):
        for gold_index, gold_event in enumerate(gold):
            compatible = _compatibility(gold_event, auto_event)
            if compatible is None:
                continue
            score, date_reason, type_reason = compatible
            edges[auto_index].append((gold_index, score, date_reason, type_reason))
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
        for gold_index, _score, _date_reason, _type_reason in edges[auto_index]:
            if gold_index in visited_gold:
                continue
            visited_gold.add(gold_index)
            current_auto = gold_to_auto.get(gold_index)
            if current_auto is None or augment(current_auto, visited_gold):
                gold_to_auto[gold_index] = auto_index
                return True
        return False

    for auto_index in processing_order:
        augment(auto_index, set())

    auto_to_gold = {auto_index: gold_index for gold_index, auto_index in gold_to_auto.items()}
    matched_pairs = []
    match_rows = []
    for auto_index, gold_index in sorted(
        auto_to_gold.items(), key=lambda item: auto[item[0]].record_id
    ):
        gold_event = gold[gold_index]
        auto_event = auto[auto_index]
        _score, date_reason, type_reason = _compatibility(gold_event, auto_event)
        matched_pairs.append((gold_event, auto_event))
        match_rows.append(
            {
                "auto_id": auto_event.record_id,
                "gold_id": gold_event.record_id,
                "stock_code": gold_event.stock_code,
                "event_type": gold_event.event_type,
                "date_match": date_reason,
                "type_match": type_reason,
            }
        )

    unmatched_auto = [event for index, event in enumerate(auto) if index not in auto_to_gold]
    unmatched_gold = [event for index, event in enumerate(gold) if index not in gold_to_auto]
    return EvaluationResult(
        matches=match_rows,
        false_positives=[dict(event.raw, auto_id=event.record_id) for event in unmatched_auto],
        false_negatives=[dict(event.raw, gold_id=event.record_id) for event in unmatched_gold],
        metrics=_group_metrics(matched_pairs, unmatched_auto, unmatched_gold),
    )
