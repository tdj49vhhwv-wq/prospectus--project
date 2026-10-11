"""Check real result integrity, split isolation, ranking counts and workbook sheets."""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from prepare import OUT, FEATURES


def main():
    features = pd.read_csv(OUT / "merchant_features.csv")
    split = pd.read_csv(OUT / "sample_split.csv")
    pred = pd.read_csv(OUT / "test_predictions.csv")
    metrics = pd.read_csv(OUT / "model_metrics.csv", index_col="model")
    summary = json.loads((OUT / "analysis_summary.json").read_text())
    budget = pd.read_csv(OUT / "review_budget.csv")
    assert len(features) == 674 and int(features.closed.sum()) == 123
    assert len(split) == len(features) and split.merchant_id.nunique() == len(features)
    assert set(features.merchant_id) == set(split.merchant_id)
    assert set(pred.merchant_id) == set(split.loc[split.split == "test", "merchant_id"])
    assert len(pred) == 135 and int(pred.closed.sum()) == 25
    assert len([c for group in FEATURES.values() for c in group]) == 12
    assert summary["selected_enhanced_model"] == max(["LR_QAT", "HGB_QAT"], key=summary["validation_ap"].get)
    for name in metrics.index:
        assert pred[name].between(0, 1).all()
        assert np.isclose(roc_auc_score(pred.closed, pred[name]), metrics.loc[name, "roc_auc"])
        assert np.isclose(average_precision_score(pred.closed, pred[name]), metrics.loc[name, "pr_auc_ap"])
    for row in budget.itertuples():
        k = math.ceil(len(pred) * row.budget_fraction)
        assert k == row.reviewed
        if row.strategy == "random_expected":
            assert np.isclose(row.captured, k * pred.closed.mean())
        else:
            order = np.argsort(-pred[row.strategy].to_numpy(), kind="stable")[:k]
            assert int(pred.iloc[order].closed.sum()) == row.captured
    report = (OUT / "阶段分析报告.md").read_text()
    assert "许可" in report and "包含0" in report and "2017" in report
    for name in ["fig01_group_comparison.png", "fig02_model_comparison.png", "fig03_precision_recall.png", "fig04_review_budget.png", "fig05_calendar_confounding.png"]:
        from PIL import Image
        with Image.open(OUT / name) as image:
            assert image.width >= 800 and image.height >= 500
            image.verify()
    excel = pd.ExcelFile(OUT / "分析结果汇总.xlsx")
    assert len(excel.sheet_names) == 10
    print("PASS: input cohort, 12 indicators, split isolation, all six model metrics, all review-budget counts, report, five figures, ten workbook sheets")


if __name__ == "__main__":
    main()
