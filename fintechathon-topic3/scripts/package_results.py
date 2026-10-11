"""Package aggregate results into a convenient workbook, excluding raw records."""
from pathlib import Path
import json
import pandas as pd
from prepare import OUT


def main():
    mapping = {
        "指标说明": "feature_dictionary.csv",
        "描述分析": "descriptive_stats.csv",
        "模型比较": "model_metrics.csv",
        "复核预算": "review_budget.csv",
        "敏感性检查": "sensitivity_checks.csv",
        "主模型置换重要性": "permutation_importance.csv",
        "主模型回归系数": "primary_logistic_coefficients.csv",
        "追加日期审计": "additional_robustness.csv",
    }
    summary = json.loads((OUT / "analysis_summary.json").read_text())
    audit = json.loads((OUT / "data_audit.json").read_text())
    intervals = []
    for model, measures in summary["confidence_intervals"]["per_model"].items():
        for metric, (lower, upper) in measures.items():
            intervals.append({"model": model, "metric": metric, "lower95": lower, "upper95": upper})
    notes = pd.DataFrame({"注意事项": [
        "这是海外历史样本营业状态识别，不能称为提前预测停业或信用违约预测。",
        "评论截至2017-07-26；营业状态采集日期未说明。",
        "当前官方使用条款及镜像再分发许可尚未确认，参赛发布前须核实。",
        "主模型按验证集选为LR_QAT；不能根据测试集效果回头改选HGB_QAT。",
        "模型差异的配对区间见analysis_summary.json；增量区间包含0。",
        "随机复核命中数为理论期望，不是实际抽查命中的小数家。",
        "Bootstrap只覆盖固定模型本次测试样本的不确定性，不涵盖训练和选择过程。",
        "置换重要性及回归系数均不表示因果效应；词典主题尚未经独立人工标注验证。",
        "追加日期审计在原测试结果之后设计，不调参，不作为确认性检验；2017子组只有2家停业。",
    ]})
    destination = OUT / "分析结果汇总.xlsx"
    with pd.ExcelWriter(destination, engine="openpyxl") as writer:
        notes.to_excel(writer, sheet_name="阅读说明", index=False)
        for sheet, filename in mapping.items():
            if (OUT / filename).exists():
                pd.read_csv(OUT / filename).to_excel(writer, sheet_name=sheet, index=False)
        pd.DataFrame(intervals).to_excel(writer, sheet_name="模型置信区间", index=False)
        pd.DataFrame([{"字段": k, "值": str(v)} for k, v in audit.items()]).to_excel(writer, sheet_name="数据审计", index=False)
        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for column in worksheet.columns:
                length = min(80, max(12, max(len(str(cell.value or "")) for cell in column) + 2))
                worksheet.column_dimensions[column[0].column_letter].width = length
    print("Wrote", destination)


if __name__ == "__main__":
    main()
