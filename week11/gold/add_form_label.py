#!/usr/bin/env python3
"""阶段 0 — 给 BLIND 6 gold 加 disclosure_form 标签 + 挂牌前 date_unknown 口径.

disclosure_form 词汇表（结构感知抽取的锚点）:
  text_table   文本化表格（投资者名称/金额可从 <table> 文本解析）
  image_table  图片化表格（MinerU 里是 image，无文本 → 需回退 OCR）
  prose        纯散文披露（无表格，投资者从段落句子抽取）
  prelisting   挂牌前入股、时点未在招股书披露（BSE 摘要式披露 → date_unknown）

口径: prelisting 行 subscription_date 为空，属「未披露时点」，评估时不计入
Recall 分母（不可恢复项），这是 gold 边界规则而非抽取失败。

注: 原 gold CSV 的 notes 列含未转义的半角逗号，故本脚本按「前两列固定」做
行级插入，只读 stock_code / subscription_date，不解析整行字段。
"""
from collections import Counter
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / 'week10' / 'eval' / 'blind6_gold_draft.csv'
DST = Path(__file__).resolve().parent / 'blind6_gold_v2.csv'

FORM_BY_CODE = {
    '301629': 'text_table',   # 增资/受让明细为文本表 + 验资/变更登记段落
    '301658': 'image_table',  # 股本变化表为图片，仅「特殊投资约定」表有文本
    '920060': 'prose',        # 报告期前增资扩股纯散文，无表格
}


def form_for(code, date_ym):
    if code in FORM_BY_CODE:
        return FORM_BY_CODE[code]
    if code == '920098':
        # 有日期(2023-03定向发行)=文本表；空日期(挂牌前4家)=prelisting
        return 'prelisting' if not date_ym else 'text_table'
    return 'unknown'


def main():
    lines = SRC.read_text(encoding='utf-8-sig').splitlines()
    header = lines[0].strip()
    # 在 stock_code 列后插入 disclosure_form
    hdr_parts = header.split(',', 1)
    out_header = f"{hdr_parts[0]},disclosure_form,{hdr_parts[1]}"

    cnt = Counter()
    out = [out_header]
    for ln in lines[1:]:
        ln = ln.strip()
        if not ln:
            continue
        code, rest = ln.split(',', 1)
        date_ym = rest.split(',', 1)[0]
        form = form_for(code, date_ym)
        cnt[form] += 1
        out.append(f"{code},{form},{rest}")

    DST.write_text('\n'.join(out) + '\n', encoding='utf-8')
    print('rows:', sum(cnt.values()))
    for k, v in sorted(cnt.items()):
        print(f'  {k}: {v}')
    print('prelisting (date_unknown, 不计 Recall 分母):', cnt['prelisting'])
    print('written ->', DST)


if __name__ == '__main__':
    main()
