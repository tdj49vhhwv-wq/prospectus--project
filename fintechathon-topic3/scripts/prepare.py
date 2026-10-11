"""Build anonymous merchant-level features from the pinned Cleveland Yelp subset.

This is cross-sectional status identification, not time-to-closure prediction.
No calendar last-review date, current business stars, review_count, or closure
wording is used as a model input. Raw reviews remain local and are not exported.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
TOPICS = {
    "service_negative_share": r"\b(?:service|staff|waiter|waitress|server|rude|wait|waiting|slow)\b",
    "hygiene_negative_share": r"\b(?:dirty|dirt|filthy|cockroaches?|roaches?|mold|mould|unsanitary|hair|food poisoning)\b",
    "price_negative_share": r"\b(?:price|prices|expensive|overpriced|costly|rip[ -]?off|value|charged|charge)\b",
    "food_negative_share": r"\b(?:bland|cold|undercooked|overcooked|burnt|burned|stale|raw|tasteless|greasy|oily)\b",
}
FEATURES = {
    "quality": ["rating_mean_360", "low_rating_share_360", "rating_std_360", "rating_change_180"],
    "activity": ["recent_reviews_180", "previous_reviews_180", "review_growth_log", "monthly_activity_cv"],
    "text": list(TOPICS),
}
LABELS = {
    "rating_mean_360": "近360天评论均分",
    "low_rating_share_360": "近360天低分评论占比",
    "rating_std_360": "近360天评分标准差",
    "rating_change_180": "近期较前期均分变化",
    "recent_reviews_180": "近180天评论数",
    "previous_reviews_180": "前180天评论数",
    "review_growth_log": "评论活跃度对数变化",
    "monthly_activity_cv": "六个30天窗口评论数变异系数",
    "service_negative_share": "近期低分且提及服务的评论占比",
    "hygiene_negative_share": "近期低分且提及卫生的评论占比",
    "price_negative_share": "近期低分且提及价格的评论占比",
    "food_negative_share": "近期低分且提及食物问题的评论占比",
}


def categories(value):
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        return []
    return [part.strip() for part in value.split(",")]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    business_path = ROOT / "data/cleveland_business.jsonl"
    review_path = ROOT / "data/cleveland_reviews.jsonl"
    b = pd.read_json(business_path, lines=True)
    r = pd.read_json(review_path, lines=True)
    audit = {"business_rows_raw": len(b), "review_rows_raw": len(r)}
    assert {"business_id", "categories", "is_open", "city"} <= set(b)
    assert {"business_id", "review_id", "date", "stars", "text"} <= set(r)
    assert b.business_id.notna().all() and not b.business_id.duplicated().any()
    audit["duplicate_reviews_removed"] = int(r.review_id.duplicated().sum())
    r = r.drop_duplicates("review_id").copy()
    r["date"] = pd.to_datetime(r.date, errors="coerce")
    invalid = r.date.isna() | ~r.stars.between(1, 5) | r.business_id.isna()
    audit["invalid_reviews_removed"] = int(invalid.sum())
    r = r.loc[~invalid].copy()
    audit["unmatched_reviews"] = int((~r.business_id.isin(b.business_id)).sum())
    actual_counts = r.groupby("business_id").size()
    expected_counts = b.set_index("business_id").review_count.reindex(actual_counts.index)
    audit["business_review_count_mismatches"] = int((actual_counts != expected_counts).sum())
    audit["review_date_min"] = str(r.date.min().date())
    audit["review_date_max"] = str(r.date.max().date())
    restaurant_mask = b.categories.map(categories).map(lambda x: "Restaurants" in x)
    restaurants = b.loc[restaurant_mask & b.is_open.isin([0, 1])].copy()
    audit["restaurants_with_valid_status"] = len(restaurants)
    audit["restaurants_closed"] = int((restaurants.is_open == 0).sum())
    r = r.loc[r.business_id.isin(restaurants.business_id)].copy()
    audit["restaurant_review_rows"] = len(r)
    rows = []
    exclusions = {"fewer_than_10_reviews": 0, "history_shorter_than_365_days": 0, "fewer_than_3_recent_reviews": 0}
    status = restaurants.set_index("business_id")
    patterns = {key: re.compile(value, re.I) for key, value in TOPICS.items()}
    # Merchant ID only breaks ties in review order; it never enters the model.
    for merchant_id, group in r.groupby("business_id", sort=True):
        group = group.sort_values(["date", "review_id"])
        anchor = group.date.max()
        span = int((anchor - group.date.min()).days)
        age = (anchor - group.date).dt.days
        recent = group.loc[age < 180]
        previous = group.loc[(age >= 180) & (age < 360)]
        year = group.loc[age < 360]
        if len(group) < 10:
            exclusions["fewer_than_10_reviews"] += 1
            continue
        if span < 365:
            exclusions["history_shorter_than_365_days"] += 1
            continue
        if len(recent) < 3:
            exclusions["fewer_than_3_recent_reviews"] += 1
            continue
        monthly = np.bincount((age.loc[age < 180] // 30).astype(int), minlength=6)
        row = {
            "merchant_id": hashlib.sha256(("fintechathon2026:" + merchant_id).encode()).hexdigest()[:16],
            "closed": int(status.loc[merchant_id, "is_open"] == 0),
            "city": status.loc[merchant_id, "city"],
            "review_total_audit_only": len(group),
            "history_days_audit_only": span,
            "anchor_year_audit_only": int(anchor.year),
            "anchor_date_audit_only": str(anchor.date()),
            "rating_mean_360": year.stars.mean(),
            "low_rating_share_360": (year.stars <= 2).mean(),
            "rating_std_360": year.stars.std(ddof=0),
            "rating_change_180": recent.stars.mean() - previous.stars.mean() if len(previous) else np.nan,
            "recent_reviews_180": len(recent),
            "previous_reviews_180": len(previous),
            "review_growth_log": np.log1p(len(recent)) - np.log1p(len(previous)),
            "monthly_activity_cv": monthly.std(ddof=0) / monthly.mean(),
        }
        for key, pattern in patterns.items():
            mentions = recent.text.fillna("").map(lambda text: bool(pattern.search(text)))
            row[key] = ((recent.stars <= 2) & mentions).mean()
        rows.append(row)
    features = pd.DataFrame(rows).sort_values("merchant_id").reset_index(drop=True)
    assert not features.merchant_id.duplicated().any()
    assert len(features) > 0 and features.closed.nunique() == 2
    for name in ["low_rating_share_360", *TOPICS]:
        assert features[name].between(0, 1).all()
    assert np.isfinite(features[[c for cols in FEATURES.values() for c in cols]].drop(columns="rating_change_180")).all().all()
    audit.update({
        "exclusions_sequential": exclusions,
        "final_merchants": len(features),
        "final_closed": int(features.closed.sum()),
        "final_open": int((features.closed == 0).sum()),
        "missing_previous_window": int(features.rating_change_180.isna().sum()),
        "cities_final": features.city.value_counts().to_dict(),
        "anchor_year_by_status": pd.crosstab(features.anchor_year_audit_only, features.closed).to_dict(),
        "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [business_path, review_path]},
    })
    features.to_csv(OUT / "merchant_features.csv", index=False)
    (OUT / "data_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    dictionary = []
    formulas = [
        "mean(stars), age_days < 360", "mean(stars <= 2), age_days < 360",
        "population_std(stars), age_days < 360", "mean(stars, age < 180) - mean(stars, 180 <= age < 360)",
        "count(age < 180)", "count(180 <= age < 360)",
        "log(1 + recent_count) - log(1 + previous_count)",
        "population_std(six 30-day counts) / mean(six 30-day counts)",
    ]
    for i, name in enumerate([c for v in FEATURES.values() for c in v]):
        formula = formulas[i] if i < 8 else "count(stars <= 2 AND topic_match, age < 180) / count(age < 180)"
        dictionary.append({"field": name, "中文解释": LABELS[name], "formula": formula, "regex": TOPICS.get(name, ""), "missing_policy": "拟合数据中位数填补并加缺失指示；调参仅训练集，最终训练+验证集" if name == "rating_change_180" else "无缺失"})
    pd.DataFrame(dictionary).to_csv(OUT / "feature_dictionary.csv", index=False)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
