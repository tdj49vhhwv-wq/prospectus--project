# Week 5: 工程化升级 — event_id / processing_status / traceability

**学生**: 赵秉清
**日期**: 2026-07-16
**项目**: 招股书 PE/VC 融资历史提取
**本周主题**: 借鉴上届 CVC 项目经验，补上三条工程化基础设施

---

## 1. 背景

老师点评指出需要"先理解融资行为类别再设计提取方案"，并参考上届 CVC 项目的方法论。
上届项目在工程化方面有三条成熟实践：

| 上届实践 | 我们之前的状态 | 本周补上 |
|------|:--:|:--:|
| event_id 统一主键 | ❌ 无主键，四类 JSONL 之间无法关联 | ✅ |
| processing_status 状态追踪 | ⚠ 只有 step_log.csv（步骤级），无记录级追踪 | ✅ |
| 数据溯源显式声明 | ⚠ 有 evidence_text 但未显式化为原则 | ✅ |

---

## 2. event_id 统一主键

### 设计规范

```
格式: {stock_code}_{prospectus_date}_{record_type_abbr}_{seq:03d}
示例: 920100_20250711_sf_001
```

| 记录类型 | 缩写 | 示例 |
|:--|:--:|------|
| subscription_flow | sf | `920100_20250711_sf_001` |
| equity_snapshot | es | `920100_20250711_es_001` |
| pe_fund_detail | pf | `920100_20250711_pf_001` |
| share_transfer_flow | st | `920100_20250711_st_001` |

### 设计理由

- **可追溯**: 从任意一条记录可反向定位到公司 + 招股书版本 + 记录类型 + 序号
- **跨文件关联**: sf_001 的股东可以在 es_001 中验证持股变化
- **增量兼容**: 同一公司多版本招股书（申报稿/注册稿/正式稿）通过 prospectus_date 区分
- **换公司只改两个参数**: stock_code 和 prospectus_date，无需修改 ID 生成逻辑

---

## 3. processing_status 状态机

### 状态流转图

```
PENDING ──→ EXTRACTED ──→ SCHEMA_VALIDATED ──→ CROSS_CHECKED ──→ VERIFIED
   │            │                    │
   ↓            ↓                    ↓
 ERROR    MANUAL_REVIEW      MANUAL_REVIEW
```

### 状态含义

| 状态 | 含义 | 什么触发 |
|------|------|------|
| PENDING | 待提取 | 初始状态 |
| EXTRACTED | 已自动提取 | `extract_pevc.py` 完成 |
| SCHEMA_VALIDATED | Pydantic 校验通过 | `validate_schema.py` 通过 |
| CROSS_CHECKED | 数值交叉验证通过 | cross-check 无差异 |
| VERIFIED | 人工确认通过（终态） | 人工回PDF确认无误 |
| MANUAL_REVIEW | 需人工复核 | 数据矛盾 / 金额无法拆分 / confidence=low |
| ERROR | 提取/校验失败 | 格式错误 / 必填字段缺失 |

### 实现方式

每条记录新增三个字段：

```json
{
  "event_id": "920100_20250711_sf_001",
  "processing_status": "EXTRACTED",
  "status_detail": null
}
```

`status_detail` 记录阻塞原因，如：`"PDF只披露稳正景明+长泽创投合计2,374.40万元，未单独披露各自金额"`

### 当前产出状态

| 状态 | 数量 |
|------|:--:|
| EXTRACTED | 19 |
| MANUAL_REVIEW | 0 |
| VERIFIED | 0 |

---

## 4. 数据溯源显式声明

### 溯源链

```
PDF页码 (source_page)
  └─ raw_text (MinerU/PyMuPDF 逐字提取)
       └─ evidence_text (原文摘录, 逐字不概括)
            └─ structured_field (amount, shares, ratio, name...)
```

### 溯源级别

| 级别 | 含义 | 判断标准 |
|------|------|------|
| `pdf_disclosed` | PDF 直接披露 | evidence_text 包含该字段的原文，可直接抄录 |
| `calculated` | 从 PDF 数据计算 | price × shares = amount，非照抄 |
| `inferred` | 基于上下文推断 | 影石 VIE 拆分、轮次推断 |
| `external_required` | 需外部数据源 | 设立出资额需公开转让说明书 |

### 当前产出溯源分布

| 级别 | 数量 | 说明 |
|------|:--:|------|
| pdf_disclosed | 15 | 大部分字段直接可抄 |
| external_required | 4 | 代持还原详情在公开转让说明书 |

### 规则

- evidence_text 不包含的字段 → `data_source="calculated"`，不得标 `"pdf_disclosed"`
- evidence_text 有但 PDF 无法直接确认 → `data_source="inferred"`
- evidence_text 与 PDF 原文一致 → `data_source="pdf_disclosed"`
- 招股书本身不披露 → `data_source="external_required"` + notes 说明外部数据源

---

## 5. 文件结构

```
week5/
├── week5.md                         # 本文件
├── schemas/
│   └── models.py                    # Pydantic v2: BaseRecord + ProcessingStatus + TraceabilityLevel
├── scripts/
│   ├── config.py                    # event_id规范 / 状态转换表 / 溯源链声明
│   └── extract_pevc.py              # 带 event_id生成 + 状态追踪的四类提取
├── outputs/
│   ├── jsonl/                       # 结构化输出（四类，19行，含 event_id）
│   │   ├── subscription_flow.jsonl
│   │   ├── equity_snapshot.jsonl
│   │   ├── pe_fund_detail.jsonl
│   │   └── share_transfer_flow.jsonl
│   └── extraction_summary.json      # 含状态分布 + 溯源分布统计
└── logs/
    └── step_log.csv                 # 流水线步骤日志
```

---

## 6. 下一步

- [ ] P0: 补充公开转让说明书 → 修复 t0 出资结构
- [ ] P0: 融资行为类型归纳（增资/转让/代持/VIE/转增/减资）→ 设计分类体系
- [ ] P0: 按融资行为类型设计专用 prompt（非通用 prompt）
- [ ] P1: 跑 MinerU 重新解析三协电机招股书 → 对比 PyMuPDF 表格质量
- [ ] P1: Schema 校验 + Cross-Check 自动流转 processing_status
