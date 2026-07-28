"""
数据溯源追踪 — 学习李泽润 provenance.py

记录每条数据从原始PDF到最终数据库的完整路径:
  PDF页码 → raw_text → evidence_text → structured_field → 数据库记录

每条记录包含:
  - source_page: PDF原始页码
  - evidence_text: 原文逐字摘录
  - extraction_method: 提取方法（pdfplumber / mineru_md / pymupdf / manual）
  - data_source: pdf_disclosed / calculated / inferred / external_required
  - processing_status: 处理状态链（PENDING → EXTRACTED → VERIFIED）
  - created_at: 时间戳
"""
import json
import hashlib
import re
from datetime import datetime
from pathlib import Path


class Provenance:
    """单条记录的溯源信息"""

    def __init__(self, event_id, record_type):
        self.event_id = event_id
        self.record_type = record_type
        self.source_page = None        # PDF页码
        self.source_file = None        # 源文件名
        self.evidence_text = ""        # 原文逐字摘录
        self.evidence_hash = ""        # 原文SHA256
        self.extraction_method = ""    # pdfplumber | mineru_md | pymupdf | manual
        self.data_source = "pdf_disclosed"  # pdf_disclosed | calculated | inferred | external_required
        self.processing_status = "PENDING"
        self.status_history = []       # [{timestamp, from_status, to_status, reason}]
        self.notes = ""
        self.created_at = datetime.now().isoformat()

    def set_evidence(self, text, method, source_page=None, source_file=None):
        self.evidence_text = text[:500] if text else ""
        self.evidence_hash = hashlib.sha256(text.encode() if text else b"").hexdigest()[:16]
        self.extraction_method = method
        if source_page:
            self.source_page = source_page
        if source_file:
            self.source_file = source_file
        return self

    def transition(self, new_status, reason=""):
        self.status_history.append({
            "timestamp": datetime.now().isoformat(),
            "from": self.processing_status,
            "to": new_status,
            "reason": reason,
        })
        self.processing_status = new_status
        return self

    def to_dict(self):
        return {
            "event_id": self.event_id,
            "record_type": self.record_type,
            "source_page": self.source_page,
            "source_file": self.source_file,
            "evidence_text": self.evidence_text,
            "evidence_hash": self.evidence_hash,
            "extraction_method": self.extraction_method,
            "data_source": self.data_source,
            "processing_status": self.processing_status,
            "status_history": self.status_history[-5:],  # 最近5次状态变化
            "notes": self.notes,
            "created_at": self.created_at,
        }


class ProvenanceTracker:
    """批量溯源追踪器 — 管理所有记录的溯源信息"""

    def __init__(self, output_dir=None):
        self.records = []
        self.output_dir = Path(output_dir) if output_dir else Path.cwd()

    def add(self, event_id, record_type):
        record = Provenance(event_id, record_type)
        self.records.append(record)
        return record

    def to_jsonl(self, filepath=None):
        if not filepath:
            filepath = self.output_dir / f"provenance_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
        with open(filepath, 'w', encoding='utf-8') as f:
            for r in self.records:
                f.write(json.dumps(r.to_dict(), ensure_ascii=False) + '\n')
        return filepath

    def summary(self):
        """生成溯源摘要"""
        methods = {}
        pages = set()
        statuses = {}
        for r in self.records:
            d = r.to_dict()
            m = d['extraction_method'] or 'unknown'
            methods[m] = methods.get(m, 0) + 1
            if d['source_page']:
                pages.add(d['source_page'])
            s = d['processing_status']
            statuses[s] = statuses.get(s, 0) + 1

        return {
            "total_records": len(self.records),
            "extraction_methods": methods,
            "unique_pages": len(pages),
            "processing_status": statuses,
            "generated_at": datetime.now().isoformat(),
        }


def verify_evidence_chain(record_dict):
    """
    验证溯源链完整性（学习李泽润 numeric_rules 校验思路）

    返回 (is_valid, issues):
      - source_page 缺失 → "missing_source_page"
      - evidence_text 为空 → "missing_evidence"
      - evidence_text 过短（<20字符） → "evidence_too_short"
      - extraction_method 未知 → "unknown_method"
    """
    issues = []

    if not record_dict.get("source_page"):
        issues.append("missing_source_page")

    evidence = record_dict.get("evidence_text", "")
    if not evidence:
        issues.append("missing_evidence")
    elif len(evidence) < 20:
        issues.append("evidence_too_short")

    method = record_dict.get("extraction_method", "")
    valid_methods = {"pdfplumber", "mineru_md", "pymupdf", "manual", "auto", "supplement_from_final"}
    if method and method not in valid_methods:
        issues.append(f"unknown_method: {method}")

    return len(issues) == 0, issues


# ── 辅助函数：批量验证 ──

def validate_jsonl_provenance(jsonl_path):
    """对JSONL文件做溯源链批量验证"""
    stats = {"total": 0, "pass": 0, "fail": 0, "issues": []}

    if not Path(jsonl_path).exists():
        return stats

    with open(jsonl_path) as f:
        for line_num, line in enumerate(f, 1):
            try:
                record = json.loads(line.strip())
                ok, issues = verify_evidence_chain(record)
                stats['total'] += 1
                if ok:
                    stats['pass'] += 1
                else:
                    stats['fail'] += 1
                    stats['issues'].append({
                        "line": line_num,
                        "event_id": record.get("event_id", ""),
                        "issues": issues,
                    })
            except json.JSONDecodeError:
                stats['issues'].append({"line": line_num, "error": "invalid_json"})

    return stats


if __name__ == "__main__":
    # 测试
    tracker = ProvenanceTracker()
    rec = tracker.add("920100_20250711_es_001", "equity_snapshot")
    rec.set_evidence("盛祎直接持有公司62.97%的股份", "pdfplumber", 35, "三协电机_招股书.pdf")
    rec.transition("EXTRACTED", "pdfplumber table extraction ok")
    rec.transition("VERIFIED", "cross-check passed")

    print(json.dumps(rec.to_dict(), ensure_ascii=False, indent=2))
    print(f"\n溯源摘要: {tracker.summary()}")
