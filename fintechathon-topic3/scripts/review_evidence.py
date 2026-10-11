"""Post-result robustness audit; no refitting or model/threshold selection.

Input is the local held-out predictions produced by analyze.py. Only anonymous
aggregate outputs are published. This audit was designed AFTER original results.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--predictions', type=Path, default=ROOT / 'outputs/test_predictions.csv')
    args = parser.parse_args()
    predictions = pd.read_csv(args.predictions)
    assert len(predictions) == 135 and predictions.closed.sum() == 25
    assert predictions.merchant_id.is_unique
    rows = []
    for name in ['LR_Q', 'LR_QA', 'LR_QAT', 'HGB_Q', 'HGB_QA', 'HGB_QAT']:
        for subset, frame in [('all_test', predictions), ('year_2017', predictions[predictions.anchor_year_audit_only == 2017])]:
            rows.append(dict(model=name, subset=subset, merchants=len(frame), closed=int(frame.closed.sum()),
                             prevalence=frame.closed.mean(), roc_auc=roc_auc_score(frame.closed, frame[name]),
                             ap=average_precision_score(frame.closed, frame[name])))
        # Pairwise AUC restricted to positive-negative pairs in the same year.
        concordance, pairs = 0., 0
        for _, frame in predictions.groupby('anchor_year_audit_only'):
            positive = frame.loc[frame.closed == 1, name].to_numpy()
            negative = frame.loc[frame.closed == 0, name].to_numpy()
            difference = positive[:, None] - negative[None, :]
            concordance += np.sum(difference > 0) + .5 * np.sum(difference == 0)
            pairs += difference.size
        rows.append(dict(model=name, subset='same_year_pairs', merchants=len(predictions), closed=25,
                         prevalence=predictions.closed.mean(), roc_auc=concordance / pairs, ap=np.nan))
    pd.DataFrame(rows).to_csv(ROOT / 'outputs/additional_robustness.csv', index=False)
    notes = dict(design='post-result diagnostic, not confirmatory; fixed predictions, no refitting',
                 same_year_positive_negative_pairs=pairs,
                 year_2017_merchants=107, year_2017_closed=2,
                 limitations=['Only 2016 and 2017 contain both labels; only 260 within-year pairs.',
                              'Year-restricted diagnostics do not establish prospective validity.',
                              'No confidence intervals; do not interpret subgroup estimates as stable gains.'],
                 economics={'absolute_net_value': 'k*(p*v-c)-F',
                            'increment_vs_equal_budget_low_rating': '(h_model-h_low_rating)*v-F_increment',
                            'definitions': 'p=prospectively verified actionable-risk precision; v=measured net value per actionable hit; c=cost per review; F=period fixed cost',
                            'historical_status_hits_are_not_actionable_risk': True,
                            'illustration_only': 'At 14 reviews, historical tree-minus-low-rating hit difference is 4, primary difference is 0; no monetary savings inferred.'})
    (ROOT / 'outputs/additional_robustness_notes.json').write_text(json.dumps(notes, ensure_ascii=False, indent=2))
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == '__main__':
    main()
