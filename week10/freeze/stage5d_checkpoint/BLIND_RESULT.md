# BLIND 6 One-shot Result (frozen extractor, no code changes)

Run date: 2026-08-27.  Frozen code from this checkpoint; BLIND 6 PE/VC content
was NOT read before this run (gold drafted from canonical markdown first).

## Result

- Gold PE/VC: 28  ·  Auto PE/VC: 16
- **TP 3 / FP 13 / FN 25**
- **Precision 18.75% · Recall 10.71% · F1 13.64%**

## Per-company

| code | 板 | Gold | Auto | TP | FP | FN |
|---|---|---|---|---|---|---|
| 603257 | 主 | 0 | 0 | 0 | 0 | 0 |
| 603210 | 主 | 0 | 3 | 0 | 3 | 0 |
| 301629 | 创 | 9 | 11 | 3 | 8 | 6 |
| 301658 | 创 | 11 | 1 | 0 | 1 | 11 |
| 920060 | 北 | 3 | 0 | 0 | 0 | 3 |
| 920098 | 北 | 5 | 1 | 0 | 1 | 5 |

## Conclusion

Cross-board generalization FAILS at F1 13.64% (vs VAL 100% / DEV 82.61%).
Six systematic root causes documented in `week10/CONCLUSION.md`:
员工持股平台排除失效, 图片化表格, 日期/事件口径差异, clean_name 前缀残留,
名称未归一化, BSE 挂牌前入股时点未披露.

No extractor code changes made (freeze respected).
