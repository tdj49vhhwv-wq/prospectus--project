#!/usr/bin/env python3

import csv
import math
from pathlib import Path
from collections import defaultdict

import numpy as np

from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.decomposition import PCA


ROOT = Path(__file__).resolve().parents[2]

INPUT = ROOT / "week10/taxonomy/structure_features_v1.csv"

OUT_CLUSTER = ROOT / "week10/taxonomy/taxonomy_clusters_v1.csv"
OUT_DIAG = ROOT / "week10/taxonomy/feature_diagnostics_v1.csv"
OUT_PCA = ROOT / "week10/taxonomy/pca_coordinates_v1.csv"


# ============================================================
# 1. Load
# ============================================================

with INPUT.open(encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))


def f(row, key):
    try:
        return float(row.get(key, 0) or 0)
    except Exception:
        return 0.0


# ============================================================
# 2. Derived structural features
#
# Do NOT use:
# company name / stock code / board / historical role /
# extractor result / Gold / P-R-F1
# ============================================================

def derived(row):
    chars = max(f(row, "character_count"), 1)

    return {
        # document organization
        "heading_density":
            f(row, "heading_density_per_10k_chars"),

        "numbered_heading_density":
            f(row, "numbered_heading_count") / chars * 10000,

        "equity_heading_density":
            f(row, "equity_heading_count") / chars * 10000,

        # table structure
        "html_table_density":
            f(row, "html_table_count") / chars * 10000,

        "markdown_table_density":
            f(row, "markdown_table_line_count") / chars * 10000,

        "table_line_ratio":
            f(row, "table_line_ratio"),

        # diagram structure
        "mermaid_density":
            f(row, "mermaid_count") / chars * 10000,

        # PE/VC-related structural signals, normalized
        "equity_signal":
            f(row, "equity_signal_per_10k_chars"),

        "investor_signal":
            f(row, "investor_signal_per_10k_chars"),

        "restructuring_signal":
            f(row, "restructuring_term_total") / chars * 10000,

        "summary_table_signal":
            f(row, "summary_table_term_total") / chars * 10000,

        "vie_signal":
            f(row, "vie_term_total") / chars * 10000,

        # list complexity
        "long_list_log":
            math.log1p(f(row, "longest_delimited_line_score")),

        # narrative vs structured
        "narrative_ratio":
            f(row, "narrative_line_ratio"),

        # date intensity
        "date_density":
            f(row, "date_expression_count") / chars * 10000,
    }


feature_rows = [derived(r) for r in rows]
feature_names = list(feature_rows[0].keys())

X = np.array(
    [[x[k] for k in feature_names] for x in feature_rows],
    dtype=float
)


# ============================================================
# 3. Feature diagnostics
# ============================================================

print()
print("===== FEATURE DIAGNOSTICS =====")

diagnostics = []

for j, name in enumerate(feature_names):
    vals = X[:, j]

    q25 = np.percentile(vals, 25)
    q50 = np.percentile(vals, 50)
    q75 = np.percentile(vals, 75)
    iqr = q75 - q25

    lower = q25 - 1.5 * iqr
    upper = q75 + 1.5 * iqr

    outlier_idx = [
        i for i, v in enumerate(vals)
        if v < lower or v > upper
    ]

    diagnostics.append({
        "feature": name,
        "min": float(np.min(vals)),
        "q25": float(q25),
        "median": float(q50),
        "q75": float(q75),
        "max": float(np.max(vals)),
        "mean": float(np.mean(vals)),
        "std": float(np.std(vals)),
        "iqr_outlier_count": len(outlier_idx),
    })

    print(
        f"{name:28s} "
        f"median={q50:.4f} "
        f"max={np.max(vals):.4f} "
        f"outliers={len(outlier_idx)}"
    )

with OUT_DIAG.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:
    w = csv.DictWriter(
        f,
        fieldnames=list(diagnostics[0].keys())
    )
    w.writeheader()
    w.writerows(diagnostics)


# ============================================================
# 4. Extreme documents
# ============================================================

print()
print("===== STRUCTURAL EXTREMES =====")

important = [
    "html_table_density",
    "markdown_table_density",
    "mermaid_density",
    "restructuring_signal",
    "summary_table_signal",
    "vie_signal",
    "long_list_log",
    "investor_signal",
]

for name in important:
    j = feature_names.index(name)

    idx = sorted(
        range(len(rows)),
        key=lambda i: X[i, j],
        reverse=True
    )[:3]

    print()
    print(name)

    for i in idx:
        print(
            f"  {rows[i]['stock_code']} "
            f"{rows[i]['company_short_name']} "
            f"value={X[i,j]:.4f}"
        )


# ============================================================
# 5. Correlation check
# ============================================================

corr = np.corrcoef(X, rowvar=False)

print()
print("===== HIGH CORRELATIONS |r| >= 0.85 =====")

found_corr = False

for i in range(len(feature_names)):
    for j in range(i + 1, len(feature_names)):
        r = corr[i, j]

        if abs(r) >= 0.85:
            found_corr = True
            print(
                f"{feature_names[i]} <-> "
                f"{feature_names[j]}: {r:.3f}"
            )

if not found_corr:
    print("None")


# ============================================================
# 6. Standardization
# ============================================================

scaler = StandardScaler()
Z = scaler.fit_transform(X)


# ============================================================
# 7. K selection
# ============================================================

print()
print("===== CLUSTER MODEL SELECTION =====")

scores = {}

max_k = min(6, len(rows) - 1)

for k in range(2, max_k + 1):

    model = KMeans(
        n_clusters=k,
        random_state=202610,
        n_init=50,
    )

    labels = model.fit_predict(Z)

    score = silhouette_score(Z, labels)
    scores[k] = score

    sizes = [
        int(np.sum(labels == c))
        for c in range(k)
    ]

    print(
        f"k={k}: "
        f"silhouette={score:.4f} "
        f"sizes={sizes}"
    )


best_k = max(scores, key=scores.get)

print()
print(
    f"Best k by silhouette: "
    f"{best_k} "
    f"(score={scores[best_k]:.4f})"
)


# ============================================================
# 8. Final exploratory clustering
#
# Important:
# this is NOT yet a semantic taxonomy.
# ============================================================

model = KMeans(
    n_clusters=best_k,
    random_state=202610,
    n_init=100,
)

labels = model.fit_predict(Z)


# ============================================================
# 9. PCA for inspection only
# ============================================================

pca = PCA(n_components=2)
coords = pca.fit_transform(Z)

print()
print("===== PCA =====")
print(
    "PC1 explained variance:",
    f"{pca.explained_variance_ratio_[0]:.4f}"
)
print(
    "PC2 explained variance:",
    f"{pca.explained_variance_ratio_[1]:.4f}"
)
print(
    "PC1+PC2:",
    f"{sum(pca.explained_variance_ratio_):.4f}"
)


# ============================================================
# 10. Cluster membership
# ============================================================

print()
print("===== CLUSTER MEMBERSHIP =====")

clusters = defaultdict(list)

for i, label in enumerate(labels):
    clusters[int(label)].append(i)

for c in sorted(clusters):

    print()
    print(f"Cluster {c} (n={len(clusters[c])})")

    for i in clusters[c]:
        print(
            f"  {rows[i]['stock_code']} "
            f"{rows[i]['company_short_name']} "
            f"[{rows[i]['board']}] "
            f"{rows[i]['historical_role']}"
        )


# ============================================================
# 11. Cluster profiles
# ============================================================

print()
print("===== CLUSTER FEATURE PROFILES =====")

overall = np.mean(Z, axis=0)

for c in sorted(clusters):

    idx = clusters[c]
    center = np.mean(Z[idx], axis=0)

    ranked = sorted(
        zip(feature_names, center),
        key=lambda x: abs(x[1]),
        reverse=True
    )

    print()
    print(f"Cluster {c}")

    for name, value in ranked[:6]:
        direction = "HIGH" if value > 0 else "LOW"

        print(
            f"  {name:28s} "
            f"{direction:4s} "
            f"z={value:+.3f}"
        )


# ============================================================
# 12. Save cluster result
# ============================================================

cluster_out = []

for i, row in enumerate(rows):

    x = {
        "document_id": row["document_id"],
        "stock_code": row["stock_code"],
        "company_short_name": row["company_short_name"],
        "board": row["board"],
        "historical_role": row["historical_role"],
        "exploratory_cluster": int(labels[i]),
        "best_k": best_k,
        "silhouette_score": round(scores[best_k], 6),
        "pc1": round(float(coords[i, 0]), 6),
        "pc2": round(float(coords[i, 1]), 6),
    }

    for name in feature_names:
        x[name] = feature_rows[i][name]

    cluster_out.append(x)


with OUT_CLUSTER.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    fields = list(cluster_out[0].keys())

    w = csv.DictWriter(
        f,
        fieldnames=fields
    )

    w.writeheader()
    w.writerows(cluster_out)


# ============================================================
# 13. PCA output
# ============================================================

with OUT_PCA.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    fields = [
        "document_id",
        "stock_code",
        "company_short_name",
        "board",
        "historical_role",
        "cluster",
        "pc1",
        "pc2",
    ]

    w = csv.DictWriter(
        f,
        fieldnames=fields
    )

    w.writeheader()

    for i, row in enumerate(rows):

        w.writerow({
            "document_id": row["document_id"],
            "stock_code": row["stock_code"],
            "company_short_name":
                row["company_short_name"],
            "board": row["board"],
            "historical_role":
                row["historical_role"],
            "cluster": int(labels[i]),
            "pc1": float(coords[i, 0]),
            "pc2": float(coords[i, 1]),
        })


print()
print("Outputs:")
print(
    " ",
    OUT_DIAG.relative_to(ROOT)
)
print(
    " ",
    OUT_CLUSTER.relative_to(ROOT)
)
print(
    " ",
    OUT_PCA.relative_to(ROOT)
)
