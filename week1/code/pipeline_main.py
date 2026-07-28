#!/usr/bin/env python3
"""
==========================================================================
 招股书PEVC融资历史提取 - 主运行脚本
 功能: 按顺序执行所有处理步骤, 输出日志到 logs/ 目录
==========================================================================
步骤:
  1. group_files    - 按公司名分组MD文件
  2. extract_toc    - 提取目录/章节标题
  3. locate_chapters- 定位融资历史相关章节
  4. extract_text   - 截取候选文本
  5. build_json     - 构建结构化JSON
  6. save_outputs   - 保存到各公司文件夹
  7. verify         - 校验JSON完整性和Schema
==========================================================================
"""
import sys
import json
import re
import time
import traceback
import csv
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    PROJECT_ROOT, REVIEW_DIR, OUTPUTS_DIR, LOG_DIR,
    FINANCING_KEYWORDS, REQUIRED_EVENT_FIELDS, REQUIRED_INVESTOR_FIELDS
)
from logger_util import setup_logger, log_error, log_step, log_stats

# === 初始化日志 ===
RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f"pipeline_{RUN_ID}.log"
ERROR_LOG_FILE = LOG_DIR / f"errors_{RUN_ID}.log"
STEP_LOG_CSV = LOG_DIR / f"step_log_{RUN_ID}.csv"

logger, _ = setup_logger("pipeline", LOG_FILE)
error_logger, _ = setup_logger("errors", ERROR_LOG_FILE)

# === 步骤日志 CSV ===
_step_log_rows = []


def record_step(step_name, status, detail=""):
    """记录步骤执行状态到 step_log.csv"""
    _step_log_rows.append({
        "timestamp": datetime.now().isoformat(),
        "step": step_name,
        "status": status,
        "detail": detail,
    })
    # 实时写入
    with open(STEP_LOG_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["timestamp", "step", "status", "detail"])
        w.writeheader()
        w.writerows(_step_log_rows)


# === 全局统计 ===
STATS = {
    "start_time": datetime.now().isoformat(),
    "total_files": 0,
    "total_companies": 0,
    "financing_chapters_found": 0,
    "candidate_texts_extracted": 0,
    "json_outputs_created": 0,
    "errors": 0,
    "warnings": 0,
}


# ============================================================
# Step 1: 按公司名分组MD文件
# ============================================================
def step1_group_files():
    step_name = "Step1_group_files"
    log_step(logger, "Step 1: 按公司名分组MD文件")
    record_step(step_name, "START")
    company_files = defaultdict(list)

    try:
        for f in sorted(REVIEW_DIR.glob("*.md")):
            if f.name.startswith("."):
                continue
            name = f.stem
            name = name.replace("MinerU_markdown_", "")
            name = re.sub(r'md$', '', name)
            company = re.sub(r'\d+$', '', name)
            if company:
                company_files[company].append(f)

        STATS["total_files"] = sum(len(v) for v in company_files.values())
        STATS["total_companies"] = len(company_files)

        logger.info(f"  发现 {STATS['total_companies']} 家公司, 共 {STATS['total_files']} 个MD文件")
        for company, files in sorted(company_files.items()):
            logger.info(f"    {company}: {len(files)} 文件 -> {[f.name for f in sorted(files)]}")

        log_step(logger, "Step 1: 按公司名分组MD文件", "DONE")
        record_step(step_name, "DONE", f"companies={STATS['total_companies']}, files={STATS['total_files']}")
        return company_files
    except Exception as e:
        log_error(error_logger, e, "Step 1 失败")
        STATS["errors"] += 1
        log_step(logger, "Step 1: 按公司名分组MD文件", "FAIL")
        record_step(step_name, "FAIL", str(e))
        raise


# ============================================================
# Step 2: 提取目录和章节标题
# ============================================================
def step2_extract_toc(company_files):
    step_name = "Step2_extract_toc"
    log_step(logger, "Step 2: 提取目录/章节标题")
    record_step(step_name, "START")
    all_toc = {}

    for company, files in sorted(company_files.items()):
        try:
            toc_entries = []
            for f in sorted(files):
                with open(f, "r", encoding="utf-8") as fh:
                    lines = fh.readlines()[:300]

                for line in lines:
                    m = re.match(r'^#\s+(第[一二三四五六七八九十\d]+节.*)', line)
                    if m:
                        toc_entries.append(m.group(1).strip()[:120])
                    m2 = re.match(r'^#\s+(一、|二、|三、|四、|五、|六、).*', line)
                    if m2:
                        toc_entries.append(f"  {m2.group(0).strip()[:120]}")

            all_toc[company] = list(dict.fromkeys(toc_entries))
            logger.info(f"  {company}: {len(all_toc[company])} 条目录")
        except Exception as e:
            log_error(error_logger, e, f"Step 2: {company} 目录提取失败")
            STATS["warnings"] += 1
            all_toc[company] = []

    # 保存目录汇总
    toc_summary = LOG_DIR / f"toc_summary_{RUN_ID}.md"
    with open(toc_summary, "w", encoding="utf-8") as f:
        f.write(f"# 目录汇总 ({RUN_ID})\n\n")
        for company, entries in sorted(all_toc.items()):
            f.write(f"## {company}\n\n")
            for e in entries:
                f.write(f"- {e}\n")
            f.write("\n")

    logger.info(f"  目录汇总已保存: {toc_summary.name}")
    log_step(logger, "Step 2: 提取目录/章节标题", "DONE")
    record_step(step_name, "DONE", f"companies={len(all_toc)}, toc_summary={toc_summary.name}")
    return all_toc


# ============================================================
# Step 3 & 4: 定位融资历史章节 + 截取候选文本（保留原文）
# ============================================================
def step3_4_locate_and_extract(company_files):
    step_name = "Step3_4_locate_and_extract"
    log_step(logger, "Step 3+4: 定位融资历史章节 & 截取候选文本")
    record_step(step_name, "START")
    candidates = defaultdict(list)

    for company, files in sorted(company_files.items()):
        try:
            all_text = ""
            for f in sorted(files):
                with open(f, "r", encoding="utf-8") as fh:
                    all_text += fh.read() + "\n\n"

            # 找章节边界
            boundaries = []
            for m in re.finditer(r'^# (.+)$', all_text, re.MULTILINE):
                boundaries.append((m.start(), m.group(1).strip()))

            # 定位融资章节
            found = 0
            for i, (start, title) in enumerate(boundaries):
                for kw in FINANCING_KEYWORDS:
                    if re.search(kw, title):
                        next_start = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(all_text)
                        content = all_text[start:next_start].strip()
                        if len(content) > 100:
                            candidates[company].append({
                                "chapter": title[:120],
                                "text": content,  # 保留完整原文，不再截断
                                "length": len(content),
                            })
                            found += 1
                            break

            STATS["financing_chapters_found"] += found
            STATS["candidate_texts_extracted"] += len(candidates[company])
            logger.info(f"  {company}: {found} 个融资相关章节, {len(candidates[company])} 段候选文本（保留原文）")

        except Exception as e:
            log_error(error_logger, e, f"Step 3+4: {company} 失败")
            STATS["errors"] += 1

    log_step(logger, "Step 3+4: 定位融资历史章节 & 截取候选文本", "DONE")
    record_step(step_name, "DONE",
                f"chapters_found={STATS['financing_chapters_found']}, texts_extracted={STATS['candidate_texts_extracted']}")
    return candidates


# ============================================================
# Step 5: 保存候选文本到各公司文件夹（带原文+行号定位）
# ============================================================
def step5_save_candidates(candidates):
    step_name = "Step5_save_candidates"
    log_step(logger, "Step 5: 保存候选文本")
    record_step(step_name, "START")

    for company, texts in sorted(candidates.items()):
        try:
            company_dir = OUTPUTS_DIR / company
            company_dir.mkdir(parents=True, exist_ok=True)

            md_path = company_dir / f"{company}_候选文本.md"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(f"# {company} - 融资历史候选文本\n\n")
                f.write(f"提取时间: {datetime.now().isoformat()}\n")
                f.write(f"# 以下为原文片段，可回源校验\n\n")
                for i, ct in enumerate(texts):
                    f.write(f"## {i+1}. {ct['chapter']}\n\n")
                    f.write(f"原文长度: {ct['length']:,} 字符\n\n")
                    f.write(f"{ct['text']}\n\n---\n\n")

            logger.info(f"  {company}: 候选文本 -> {md_path.name}")
            STATS["json_outputs_created"] += 1

        except Exception as e:
            log_error(error_logger, e, f"Step 5: {company} 保存失败")
            STATS["errors"] += 1

    log_step(logger, "Step 5: 保存候选文本", "DONE")
    record_step(step_name, "DONE", f"outputs={STATS['json_outputs_created']}")


# ============================================================
# Step 6: 保存章节列表
# ============================================================
def step6_save_toc(company_files, all_toc):
    step_name = "Step6_save_toc"
    log_step(logger, "Step 6: 保存章节列表")
    record_step(step_name, "START")

    for company in sorted(company_files.keys()):
        try:
            company_dir = OUTPUTS_DIR / company
            company_dir.mkdir(parents=True, exist_ok=True)

            toc_path = company_dir / f"{company}_章节列表.md"
            with open(toc_path, "w", encoding="utf-8") as f:
                f.write(f"# {company} - 章节列表\n\n")
                f.write(f"源文件: {[x.name for x in sorted(company_files[company])]}\n\n")
                for entry in all_toc.get(company, []):
                    f.write(f"- {entry}\n")

            logger.info(f"  {company}: 章节列表 -> {toc_path.name}")

        except Exception as e:
            log_error(error_logger, e, f"Step 6: {company} 保存失败")
            STATS["errors"] += 1

    log_step(logger, "Step 6: 保存章节列表", "DONE")
    record_step(step_name, "DONE", f"companies={len(company_files)}")


# ============================================================
# Step 7: 校验JSON (更新为顶层 financing_events 的 Schema)
# ============================================================
def step7_verify_json():
    step_name = "Step7_verify"
    log_step(logger, "Step 7: 校验JSON输出")
    record_step(step_name, "START")

    verify_results = []
    for json_file in sorted(OUTPUTS_DIR.glob("*/*_结构化.json")):
        company = json_file.parent.name
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 新 Schema: financing_events 在顶层
            company_info = data.get("company", {})
            events = data.get("financing_events", [])

            # 如果 events 为空，尝试从旧格式读取
            if not events:
                events = company_info.get("financing_events", [])

            # 检查 events
            event_issues = []
            for i, e in enumerate(events):
                missing = [f for f in REQUIRED_EVENT_FIELDS if f not in e]
                if missing:
                    event_issues.append(f"事件{i+1}缺少字段: {missing}")

                # 检查 evidence_text 是否为原文片段（非概括性语言）
                evidence = e.get("evidence_text", "")
                if evidence and any(kw in evidence[:30] for kw in ["招股书显示", "招股书披露", "根据招股书"]):
                    event_issues.append(f"事件{i+1} evidence_text 疑似概括性语言，应为原文片段")

                for j, inv in enumerate(e.get("investors", [])):
                    inv_missing = [f for f in REQUIRED_INVESTOR_FIELDS if f not in inv]
                    if inv_missing:
                        event_issues.append(f"事件{i+1}投资人{j+1}缺少字段: {inv_missing}")

            status = "PASS" if not event_issues else "FAIL"
            logger.info(f"  {status}: {company} ({len(events)}事件, {sum(len(e.get('investors',[])) for e in events)}投资人)")
            if event_issues:
                for issue in event_issues:
                    logger.warning(f"    {issue}")
                STATS["warnings"] += 1

            verify_results.append({
                "company": company,
                "status": status,
                "events": len(events),
                "issues": event_issues,
            })

        except json.JSONDecodeError as e:
            log_error(error_logger, e, f"JSON解析失败: {json_file.name}")
            STATS["errors"] += 1
            verify_results.append({"company": company, "status": "JSON_INVALID", "issues": [str(e)]})
        except Exception as e:
            log_error(error_logger, e, f"校验失败: {json_file.name}")
            STATS["errors"] += 1

    # 保存校验报告
    verify_report = LOG_DIR / f"verify_report_{RUN_ID}.json"
    with open(verify_report, "w", encoding="utf-8") as f:
        json.dump(verify_results, f, ensure_ascii=False, indent=2)
    logger.info(f"  校验报告: {verify_report.name}")

    log_step(logger, "Step 7: 校验JSON输出", "DONE")
    record_step(step_name, "DONE", f"checked={len(verify_results)}")
    return verify_results


# ============================================================
# Step 8: 生成总报告
# ============================================================
def step8_generate_report():
    step_name = "Step8_report"
    log_step(logger, "Step 8: 生成运行总报告")
    record_step(step_name, "START")

    STATS["end_time"] = datetime.now().isoformat()
    elapsed = (datetime.fromisoformat(STATS["end_time"]) -
               datetime.fromisoformat(STATS["start_time"])).total_seconds()

    report_path = LOG_DIR / f"run_report_{RUN_ID}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# 招股书融资历史提取 - 运行报告\n\n")
        f.write(f"**运行ID**: {RUN_ID}\n")
        f.write(f"**开始时间**: {STATS['start_time']}\n")
        f.write(f"**结束时间**: {STATS['end_time']}\n")
        f.write(f"**耗时**: {elapsed:.2f} 秒\n\n")

        f.write(f"## 统计\n\n")
        f.write(f"| 指标 | 数值 |\n")
        f.write(f"|------|------|\n")
        f.write(f"| MD文件总数 | {STATS['total_files']} |\n")
        f.write(f"| 公司总数 | {STATS['total_companies']} |\n")
        f.write(f"| 融资相关章节 | {STATS['financing_chapters_found']} |\n")
        f.write(f"| 候选文本段 | {STATS['candidate_texts_extracted']} |\n")
        f.write(f"| JSON输出 | {STATS['json_outputs_created']} |\n")
        f.write(f"| 错误数 | {STATS['errors']} |\n")
        f.write(f"| 警告数 | {STATS['warnings']} |\n\n")

        f.write(f"## 日志文件\n\n")
        f.write(f"- 运行日志: `{LOG_FILE.name}`\n")
        f.write(f"- 错误日志: `{ERROR_LOG_FILE.name}`\n")
        f.write(f"- 步骤日志: `{STEP_LOG_CSV.name}` (可机器校验每一步成功/失败)\n\n")

        f.write(f"## 输出目录\n\n")
        f.write(f"```\n{OUTPUTS_DIR}\n```\n")

    logger.info(f"  运行报告: {report_path.name}")
    record_step(step_name, "DONE", f"report={report_path.name}, elapsed={elapsed:.0f}s")


# ============================================================
# Main
# ============================================================
def main():
    logger.info("╔══════════════════════════════════════════════════╗")
    logger.info("║  招股书 PEVC 融资历史提取 Pipeline             ║")
    logger.info(f"║  Run ID: {RUN_ID}                    ║")
    logger.info("╚══════════════════════════════════════════════════╝")

    try:
        # Step 1: 分组
        company_files = step1_group_files()

        # Step 2: 提取目录
        all_toc = step2_extract_toc(company_files)

        # Step 3+4: 定位章节 + 截取原文
        candidates = step3_4_locate_and_extract(company_files)

        # Step 5: 保存候选文本（原文片段）
        step5_save_candidates(candidates)

        # Step 6: 保存章节列表
        step6_save_toc(company_files, all_toc)

        # Step 7: 校验JSON
        verify_results = step7_verify_json()

        # Step 8: 生成报告
        step8_generate_report()

        # 最终统计
        log_stats(logger, STATS)
        logger.info(f"\n{'='*50}")
        logger.info(f"  Pipeline 完成! 日志: {LOG_FILE}")
        logger.info(f"  错误日志: {ERROR_LOG_FILE}")
        logger.info(f"  步骤日志: {STEP_LOG_CSV}")
        logger.info(f"{'='*50}")

        return 0

    except Exception as e:
        log_error(error_logger, e, "Pipeline 致命错误")
        logger.critical(f"Pipeline 失败: {e}")
        traceback.print_exc()
        record_step("Pipeline", "FATAL", str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
