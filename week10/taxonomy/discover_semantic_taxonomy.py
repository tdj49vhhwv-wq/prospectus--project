#!/usr/bin/env python3

import csv
import math
from pathlib import Path
from collections import Counter, defaultdict

import numpy as np

from sklearn.preprocessing import RobustScaler
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import silhouette_score, adjusted_rand_score
from sklearn.decomposition import PCA


ROOT = Path(__file__).resolve().parents[2]

INPUT = ROOT / "week10/taxonomy/structure_features_v1.csv"

OUT = ROOT / "week10/taxonomy/semantic_taxonomy_v1.csv"


with INPUT.open(encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))


def num(row, key):
    try:
        return float(row.get(key, 0) or 0)
    except Exception:
        return 0.0


# --------------------------------------------------
# Semantic-only features
# --------------------------------------------------

def semantic_features(row):

    chars = max(num(row, "character_count"), 1)

    return {
        "equity_signal":
            num(row, "equity_signal_per_10k_chars"),

        "investor_signal":
            num(row, "investor_signal_per_10k_chars"),

        "restructuring_signal":
            num(row, "restructuring_term_total")
            / chars * 10000,

        "summary_table_signal":
            num(row, "summary_table_term_total")
            / chars * 10000,

        "vie_signal":
            num(row, "vie_term_total")
            / chars * 10000,

        "date_density":
            num(row, "date_expression_count")
            / chars * 10000,

        "long_list_log":
            math.log1p(
                num(row, "longest_delimited_line_score")
            ),
    }


feature_rows = [
    semantic_features(r)
    for r in rows
]

feature_names = list(feature_rows[0])

X = np.array([
    [x[k] for k in feature_names]
    for x in feature_rows
])


print()
print("===== SEMANTIC FEATURES =====")

for j, name in enumerate(feature_names):

    vals = X[:, j]

    print(
        f"{name:24s} "
        f"min={np.min(vals):.4f} "
        f"median={np.median(vals):.4f} "
        f"max={np.max(vals):.4f}"
    )


# --------------------------------------------------
# Robust scaling
#
# More appropriate than StandardScaler for the
# heavy-tailed semantic signals observed in Stage 3.
# --------------------------------------------------

scaler = RobustScaler()
Z = scaler.fit_transform(X)


# --------------------------------------------------
# KMeans
# --------------------------------------------------

print()
print("===== KMEANS SEMANTIC-ONLY =====")

kmeans_results = {}

for k in range(2, 7):

    model = KMeans(
        n_clusters=k,
        random_state=202610,
        n_init=100,
    )

    labels = model.fit_predict(Z)

    score = silhouette_score(Z, labels)

    sizes = [
        int(np.sum(labels == i))
        for i in range(k)
    ]

    kmeans_results[k] = (
        score,
        labels,
        sizes,
    )

    print(
        f"k={k}: "
        f"silhouette={score:.4f} "
        f"sizes={sizes}"
    )


best_k = max(
    kmeans_results,
    key=lambda k: kmeans_results[k][0]
)

best_score, best_labels, best_sizes = (
    kmeans_results[best_k]
)

print()
print(
    f"Best semantic KMeans: "
    f"k={best_k}, "
    f"silhouette={best_score:.4f}"
)


# --------------------------------------------------
# Hierarchical clustering
# --------------------------------------------------

print()
print("===== HIERARCHICAL SEMANTIC-ONLY =====")

hier_results = {}

for k in range(2, 7):

    model = AgglomerativeClustering(
        n_clusters=k,
        linkage="ward",
    )

    labels = model.fit_predict(Z)

    score = silhouette_score(Z, labels)

    sizes = [
        int(np.sum(labels == i))
        for i in range(k)
    ]

    hier_results[k] = (
        score,
        labels,
        sizes,
    )

    print(
        f"k={k}: "
        f"silhouette={score:.4f} "
        f"sizes={sizes}"
    )


best_hk = max(
    hier_results,
    key=lambda k: hier_results[k][0]
)

hscore, hlabels, hsizes = (
    hier_results[best_hk]
)

print()
print(
    f"Best hierarchical: "
    f"k={best_hk}, "
    f"silhouette={hscore:.4f}"
)


# --------------------------------------------------
# Cross-method agreement
# --------------------------------------------------

print()
print("===== CROSS-METHOD AGREEMENT =====")

common_k = best_k

if common_k in hier_results:

    hierarchical_same_k = (
        hier_results[common_k][1]
    )

    ari = adjusted_rand_score(
        best_labels,
        hierarchical_same_k,
    )

    print(
        f"KMeans vs Hierarchical "
        f"at k={common_k}: "
        f"ARI={ari:.4f}"
    )

else:
    ari = float("nan")


# --------------------------------------------------
# Leave-one-out stability
#
# Remove one document, re-cluster remaining documents,
# compare assignments on the common documents.
# --------------------------------------------------

print()
print("===== LEAVE-ONE-OUT STABILITY =====")

loo_aris = []

for removed in range(len(rows)):

    mask = np.array([
        i != removed
        for i in range(len(rows))
    ])

    Z_sub = Z[mask]

    model = KMeans(
        n_clusters=best_k,
        random_state=202610,
        n_init=100,
    )

    sub_labels = model.fit_predict(Z_sub)

    original_sub = best_labels[mask]

    score = adjusted_rand_score(
        original_sub,
        sub_labels,
    )

    loo_aris.append(score)


print(
    "LOO ARI:",
    f"min={min(loo_aris):.4f}",
    f"mean={np.mean(loo_aris):.4f}",
    f"median={np.median(loo_aris):.4f}",
    f"max={max(loo_aris):.4f}",
)


# --------------------------------------------------
# PCA inspection
# --------------------------------------------------

pca = PCA(n_components=2)
coords = pca.fit_transform(Z)

print()
print("===== SEMANTIC PCA =====")

print(
    "PC1:",
    f"{pca.explained_variance_ratio_[0]:.4f}"
)

print(
    "PC2:",
    f"{pca.explained_variance_ratio_[1]:.4f}"
)

print(
    "PC1+PC2:",
    f"{sum(pca.explained_variance_ratio_):.4f}"
)


# --------------------------------------------------
# Membership
# --------------------------------------------------

print()
print("===== SEMANTIC CLUSTER MEMBERSHIP =====")

clusters = defaultdict(list)

for i, label in enumerate(best_labels):
    clusters[int(label)].append(i)


for cluster in sorted(clusters):

    print()
    print(
        f"Cluster {cluster} "
        f"(n={len(clusters[cluster])})"
    )

    for i in clusters[cluster]:

        print(
            f"  {rows[i]['stock_code']} "
            f"{rows[i]['company_short_name']} "
            f"[{rows[i]['board']}] "
            f"{rows[i]['historical_role']}"
        )


# --------------------------------------------------
# Semantic profile
# --------------------------------------------------

print()
print("===== SEMANTIC CLUSTER PROFILES =====")

for cluster in sorted(clusters):

    idx = clusters[cluster]

    center = np.mean(
        Z[idx],
        axis=0,
    )

    ranked = sorted(
        zip(feature_names, center),
        key=lambda x: abs(x[1]),
        reverse=True,
    )

    print()
    print(f"Cluster {cluster}")

    for name, value in ranked:

        direction = (
            "HIGH"
            if value > 0
            else "LOW"
        )

        print(
            f"  {name:24s} "
            f"{direction:4s} "
            f"{value:+.3f}"
        )


# --------------------------------------------------
# Percentile-based structural dimensions
#
# These are NOT taxonomy labels.
# They provide interpretable continuous dimensions.
# --------------------------------------------------

print()
print("===== STRUCTURAL DIMENSION FLAGS =====")

percentiles = {}

for j, name in enumerate(feature_names):

    percentiles[name] = {
        "p75": float(
            np.percentile(X[:, j], 75)
        ),
        "p90": float(
            np.percentile(X[:, j], 90)
        ),
    }


for i, row in enumerate(rows):

    flags = []

    for j, name in enumerate(feature_names):

        if X[i, j] >= percentiles[name]["p90"]:
            flags.append(
                f"{name}:P90"
            )

    if flags:

        print(
            row["stock_code"],
            row["company_short_name"],
            " | ".join(flags),
        )


# --------------------------------------------------
# Save
# --------------------------------------------------

output_rows = []

for i, row in enumerate(rows):

    out = {
        "document_id": row["document_id"],
        "stock_code": row["stock_code"],
        "company_short_name":
            row["company_short_name"],
        "board": row["board"],
        "historical_role":
            row["historical_role"],

        "semantic_cluster":
            int(best_labels[i]),

        "semantic_best_k":
            best_k,

        "semantic_silhouette":
            round(best_score, 6),

        "pc1":
            round(float(coords[i, 0]), 6),

        "pc2":
            round(float(coords[i, 1]), 6),
    }

    for name in feature_names:
        out[name] = feature_rows[i][name]

    output_rows.append(out)


with OUT.open(
    "w",
    newline="",
    encoding="utf-8-sig",
) as f:

    fields = list(output_rows[0].keys())

    writer = csv.DictWriter(
        f,
        fieldnames=fields,
    )

    writer.writeheader()
    writer.writerows(output_rows)


print()
print("Output:")
print(
    " ",
    OUT.relative_to(ROOT)
)
