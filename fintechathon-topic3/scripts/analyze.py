"""Honest held-out evaluation and review-budget simulation for status recognition."""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss, precision_recall_curve
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from prepare import ROOT, OUT, FEATURES, LABELS

SEED = 20261011
FEATURE_SETS = {
    "Q": FEATURES["quality"],
    "QA": FEATURES["quality"] + FEATURES["activity"],
    "QAT": FEATURES["quality"] + FEATURES["activity"] + FEATURES["text"],
}


def budget(y, score, fraction=0.1):
    k = max(1, math.ceil(len(y) * fraction))
    ordered = np.argsort(-np.asarray(score), kind="stable")[:k]
    captured = int(np.asarray(y)[ordered].sum())
    prevalence = float(np.mean(y))
    return {"budget_fraction": fraction, "reviewed": k, "captured": captured,
            "precision": captured / k, "recall": captured / int(np.sum(y)),
            "lift": (captured / k) / prevalence}


def metrics(y, score):
    return {"roc_auc": float(roc_auc_score(y, score)), "pr_auc_ap": float(average_precision_score(y, score)),
            "brier": float(brier_score_loss(y, score)), **{f"top10_{k}": v for k, v in budget(y, score).items()}}


def interval(values):
    return [float(x) for x in np.percentile(values, [2.5, 97.5])]


def bootstrap(y, scores, baseline_name, selected_name, repetitions=1500):
    rng = np.random.default_rng(SEED)
    samples = {name: {"roc_auc": [], "pr_auc_ap": [], "precision10": [], "recall10": [], "lift10": []} for name in scores}
    differences = {"pr_auc_ap": [], "roc_auc": [], "precision10": []}
    tree_differences = {"pr_auc_ap": [], "roc_auc": [], "precision10": []}
    y = np.asarray(y)
    for _ in range(repetitions):
        ix = rng.integers(0, len(y), len(y))
        yy = y[ix]
        if len(np.unique(yy)) != 2:
            continue
        for name, prediction in scores.items():
            p = np.asarray(prediction)[ix]
            b = budget(yy, p)
            samples[name]["roc_auc"].append(roc_auc_score(yy, p))
            samples[name]["pr_auc_ap"].append(average_precision_score(yy, p))
            for key in ["precision", "recall", "lift"]:
                samples[name][key + "10"].append(b[key])
        for key in differences:
            differences[key].append(samples[selected_name][key][-1] - samples[baseline_name][key][-1])
            tree_differences[key].append(samples["HGB_QAT"][key][-1] - samples["HGB_Q"][key][-1])
    return {
        "method": "1500 paired merchant-level nonparametric percentile bootstrap draws; conditional on fitted models and this one split",
        "per_model": {name: {key: interval(v) for key, v in d.items()} for name, d in samples.items()},
        "selected_minus_baseline": {key: interval(v) for key, v in differences.items()},
        "tree_enhanced_minus_tree_quality": {key: interval(v) for key, v in tree_differences.items()},
    }


def fit_candidates(family, columns, x, y, train, valid):
    candidates = []
    if family == "LR":
        for c in [0.1, 1.0, 10.0]:
            candidates.append(({"C": c}, make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(), LogisticRegression(C=c, max_iter=2000, random_state=SEED))))
    else:
        for leaf in [7, 15]:
            for l2 in [1.0, 5.0]:
                candidates.append(({"max_leaf_nodes": leaf, "l2_regularization": l2}, make_pipeline(SimpleImputer(strategy="median", add_indicator=True), HistGradientBoostingClassifier(max_iter=150, learning_rate=0.05, max_leaf_nodes=leaf, min_samples_leaf=20, l2_regularization=l2, early_stopping=False, random_state=SEED))))
    results = []
    for parameters, model in candidates:
        model.fit(x.iloc[train][columns], y[train])
        score = model.predict_proba(x.iloc[valid][columns])[:, 1]
        results.append((average_precision_score(y[valid], score), parameters, model))
    results.sort(key=lambda result: result[0], reverse=True)
    return results[0], [{"parameters": p, "validation_ap": float(ap)} for ap, p, _ in results]


def plots(df, results, predictions, selected, baseline, test):
    plt.rcParams.update({"font.size": 10, "figure.dpi": 160, "axes.spines.top": False, "axes.spines.right": False})
    closed = df.closed.to_numpy()
    # All chart labels are English to avoid missing-font rendering; Chinese captions are in the report.
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.5))
    for ax, column, label in zip(axes, ["rating_mean_360", "review_growth_log", "service_negative_share"], ["Mean rating (last 360 days)", "Log review-count change", "Low-rating service-topic share"]):
        ax.boxplot([df.loc[closed == 0, column].dropna(), df.loc[closed == 1, column].dropna()], tick_labels=["Open", "Closed"], showfliers=False)
        ax.set_ylabel(label)
    fig.tight_layout(); fig.savefig(OUT / "fig01_group_comparison.png"); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4))
    model_names = list(results)
    ax.bar(np.arange(len(model_names)) - .17, [results[m]["roc_auc"] for m in model_names], .34, label="ROC-AUC")
    ax.bar(np.arange(len(model_names)) + .17, [results[m]["pr_auc_ap"] for m in model_names], .34, label="PR-AUC (AP)")
    ax.axhline(predictions.closed.mean(), color="gray", ls="--", label="Random AP reference")
    ax.set_xticks(np.arange(len(model_names)), model_names); ax.set_ylim(0, 1); ax.legend(ncol=3)
    ax.set_title("Held-out test: Q = quality; A = activity; T = topic shares")
    fig.tight_layout(); fig.savefig(OUT / "fig02_model_comparison.png"); plt.close(fig)
    fig, ax = plt.subplots(figsize=(6, 4))
    for name in [baseline, selected, "HGB_QAT"]:
        precision, recall, _ = precision_recall_curve(predictions.closed, predictions[name])
        ax.plot(recall, precision, label=name)
    ax.axhline(predictions.closed.mean(), color="gray", ls="--", label="Random reference")
    ax.set_xlabel("Recall"); ax.set_ylabel("Precision"); ax.legend()
    fig.tight_layout(); fig.savefig(OUT / "fig03_precision_recall.png"); plt.close(fig)
    fig, ax = plt.subplots(figsize=(6, 4))
    fractions = np.arange(.05, .51, .05)
    for name in ["low_rating", baseline, selected, "HGB_QAT"]:
        recalls = [budget(predictions.closed, predictions[name], f)["recall"] for f in fractions]
        ax.plot(fractions, recalls, marker="o", label=name)
    ax.plot(fractions, [math.ceil(len(predictions) * f) / len(predictions) for f in fractions], ls="--", label="Random expected")
    ax.set_xlabel("Share of merchants reviewed"); ax.set_ylabel("Share of closed merchants captured"); ax.legend()
    fig.tight_layout(); fig.savefig(OUT / "fig04_review_budget.png"); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4))
    years = pd.crosstab(df.anchor_year_audit_only, df.closed)
    years.columns = ["Open", "Closed"]
    years.plot(kind="bar", stacked=True, ax=ax, color=["#4c78a8", "#f58518"])
    ax.set_xlabel("Last-review year (audit only; excluded from models)"); ax.set_ylabel("Merchants")
    fig.tight_layout(); fig.savefig(OUT / "fig05_calendar_confounding.png"); plt.close(fig)


def main():
    df = pd.read_csv(OUT / "merchant_features.csv")
    y = df.closed.to_numpy()
    all_idx = np.arange(len(df))
    train_valid, test = train_test_split(all_idx, test_size=.2, stratify=y, random_state=SEED)
    train, valid = train_test_split(train_valid, test_size=.25, stratify=y[train_valid], random_state=SEED)
    assert not (set(train) & set(valid) or set(train) & set(test) or set(valid) & set(test))
    assert len(train) + len(valid) + len(test) == len(df)
    split = np.full(len(df), "train", dtype=object); split[valid] = "validation"; split[test] = "test"
    pd.DataFrame({"merchant_id": df.merchant_id, "closed": y, "split": split}).to_csv(OUT / "sample_split.csv", index=False)
    final_models, validations, candidates, selected_parameters = {}, {}, {}, {}
    for family in ["LR", "HGB"]:
        for set_name, columns in FEATURE_SETS.items():
            name = family + "_" + set_name
            (ap, params, fitted), tuning = fit_candidates(family, columns, df, y, train, valid)
            validations[name] = float(ap)
            candidates[name] = tuning
            selected_parameters[name] = params
            model = clone(fitted)
            model.fit(df.iloc[train_valid][columns], y[train_valid])
            final_models[name] = (model, columns)
            print(name, "validation AP", round(ap, 4), "params", params, flush=True)
    # Selection uses only validation AP, before any test evaluation.
    selected = max(["LR_QAT", "HGB_QAT"], key=validations.get)
    baseline = max(["LR_Q", "HGB_Q"], key=validations.get)
    pred = df.iloc[test][["merchant_id", "closed", "city", "review_total_audit_only", "anchor_year_audit_only"]].reset_index(drop=True)
    for name, (model, columns) in final_models.items():
        pred[name] = model.predict_proba(df.iloc[test][columns])[:, 1]
    pred["low_rating"] = -df.iloc[test].rating_mean_360.to_numpy()
    pred.to_csv(OUT / "test_predictions.csv", index=False)
    results = {name: metrics(y[test], pred[name]) for name in final_models}
    pd.DataFrame(results).T.rename_axis("model").to_csv(OUT / "model_metrics.csv")
    model_scores = {name: pred[name].to_numpy() for name in final_models}
    ci = bootstrap(y[test], model_scores, baseline, selected)
    comparisons = []
    for frac in [.1, .2, .3]:
        k = math.ceil(len(test) * frac)
        p = y[test].mean()
        comparisons.append({"strategy": "random_expected", "budget_fraction": frac, "reviewed": k, "captured": k * p, "precision": p, "recall": k / len(test), "lift": 1.0})
        for name in ["low_rating", *final_models]:
            comparisons.append({"strategy": name, **budget(y[test], pred[name], frac)})
    pd.DataFrame(comparisons).to_csv(OUT / "review_budget.csv", index=False)
    desc = []
    for name in [c for v in FEATURES.values() for c in v]:
        open_values = df.loc[y == 0, name].dropna(); closed_values = df.loc[y == 1, name].dropna()
        desc.append({"feature": name, "中文解释": LABELS[name], "open_mean": open_values.mean(), "closed_mean": closed_values.mean(), "open_median": open_values.median(), "closed_median": closed_values.median(), "open_n": len(open_values), "closed_n": len(closed_values), "missing_count": int(df[name].isna().sum()), "mann_whitney_p_exploratory": float(mannwhitneyu(open_values, closed_values, alternative="two-sided").pvalue)})
    descriptive = pd.DataFrame(desc)
    p_values = descriptive.mann_whitney_p_exploratory.to_numpy()
    order = np.argsort(p_values)
    adjusted = np.empty(len(order))
    adjusted[order] = np.minimum(1, np.maximum.accumulate(p_values[order] * (len(order) - np.arange(len(order)))))
    descriptive["holm_adjusted_p_exploratory"] = adjusted
    descriptive.to_csv(OUT / "descriptive_stats.csv", index=False)
    model, columns = final_models[selected]
    transformed_names = model[0].get_feature_names_out(columns)
    pd.DataFrame({"transformed_feature": transformed_names, "standardized_coefficient": model[-1].coef_[0]}).to_csv(OUT / "primary_logistic_coefficients.csv", index=False)
    importance = permutation_importance(model, df.iloc[test][columns], y[test], scoring="average_precision", n_repeats=20, random_state=SEED, n_jobs=1)
    pd.DataFrame({"feature": columns, "中文解释": [LABELS[c] for c in columns], "ap_drop_mean": importance.importances_mean, "ap_drop_std": importance.importances_std}).sort_values("ap_drop_mean", ascending=False).to_csv(OUT / "permutation_importance.csv", index=False)
    robustness = []
    for name, mask in {
        "all_test": np.ones(len(pred), dtype=bool),
        "at_least_20_lifetime_reviews": pred.review_total_audit_only >= 20,
        "exact_Cleveland_city": pred.city == "Cleveland",
        "last_review_2015_or_later": pred.anchor_year_audit_only >= 2015,
    }.items():
        subset = pred.loc[mask]
        row = {"subset": name, "n": len(subset), "closed": int(subset.closed.sum())}
        if subset.closed.nunique() == 2:
            row.update({"roc_auc": roc_auc_score(subset.closed, subset[selected]), "pr_auc_ap": average_precision_score(subset.closed, subset[selected]), "base_prevalence": subset.closed.mean()})
        robustness.append(row)
    pd.DataFrame(robustness).to_csv(OUT / "sensitivity_checks.csv", index=False)
    summary = {
        "seed": SEED, "target": "snapshot closed status (not default, not prospective closure)",
        "splits": {name: {"n": int((split == name).sum()), "closed": int(y[split == name].sum())} for name in ["train", "validation", "test"]},
        "selection_metric": "validation average precision; no test-driven selection",
        "selected_enhanced_model": selected, "selected_quality_baseline": baseline,
        "validation_ap": validations, "hyperparameters": selected_parameters,
        "test_prevalence": float(y[test].mean()), "test_metrics": results,
        "confidence_intervals": ci,
        "enhanced_minus_quality_ap": results[selected]["pr_auc_ap"] - results[baseline]["pr_auc_ap"],
        "enhanced_minus_quality_roc_auc": results[selected]["roc_auc"] - results[baseline]["roc_auc"],
        "text_increment_lr_ap": results["LR_QAT"]["pr_auc_ap"] - results["LR_QA"]["pr_auc_ap"],
        "text_increment_hgb_ap": results["HGB_QAT"]["pr_auc_ap"] - results["HGB_QA"]["pr_auc_ap"],
        "tuning_details": candidates,
    }
    (OUT / "analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    plots(df, results, pred, selected, baseline, test)
    print(json.dumps({k: v for k, v in summary.items() if k not in ["tuning_details", "confidence_intervals"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    with threadpool_limits(limits=2):
        main()
