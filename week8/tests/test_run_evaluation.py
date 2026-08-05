import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "week8/run_week8_evaluation.py"


def write_jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_cli_writes_traceable_metrics_and_error_files(tmp_path):
    gold_path = tmp_path / "gold.jsonl"
    auto_path = tmp_path / "auto.jsonl"
    output_dir = tmp_path / "results"
    gold_rows = [
        {
            "gold_id": "G1",
            "stock_code": "001282",
            "subscription_date": "2020-05-01",
            "event_context": "增资",
            "subscriber_name": "正确投资人",
            "amount_subscribed": 100,
            "shares_subscribed": None,
            "price_per_share": None,
            "source_page": "PDF p1",
            "evidence_text": "第一项人工证据",
        },
        {
            "gold_id": "G2",
            "stock_code": "301563",
            "subscription_date": "2021-06-01",
            "event_context": "增资",
            "subscriber_name": "漏掉投资人",
            "amount_subscribed": 200,
            "shares_subscribed": None,
            "price_per_share": None,
            "source_page": "PDF p2",
            "evidence_text": "第二项人工证据",
        },
    ]
    auto_rows = [
        {
            "auto_id": "A1",
            "stock_code": "001282",
            "subscription_date": "2020-05-01",
            "event_context": "增资",
            "subscriber_name": "正确投资人",
            "amount_subscribed": 100,
            "shares_subscribed": None,
            "price_per_share": None,
            "source_page": "MD p1",
            "evidence_text": "自动命中证据",
        },
        {
            "auto_id": "A2",
            "stock_code": "688758",
            "subscription_date": "2022-07-01",
            "event_context": "设立",
            "subscriber_name": "错误实体",
            "amount_subscribed": None,
            "shares_subscribed": None,
            "price_per_share": None,
            "source_page": "MD p3",
            "evidence_text": "自动误报证据",
        },
    ]
    write_jsonl(gold_path, gold_rows)
    write_jsonl(auto_path, auto_rows)

    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--gold",
            str(gold_path),
            "--auto",
            str(auto_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    event_metrics = json.loads((output_dir / "event_metrics.json").read_text())
    investor_metrics = json.loads((output_dir / "investor_metrics.json").read_text())
    expected = {
        "tp": 1,
        "fp": 1,
        "fn": 1,
        "precision": 0.5,
        "recall": 0.5,
        "f1": 0.5,
    }
    assert event_metrics["overall"] == expected
    assert investor_metrics["overall"] == expected
    for filename in (
        "event_matches.csv",
        "event_errors.csv",
        "investor_matches.csv",
        "investor_errors.csv",
        "field_completeness.csv",
        "error_analysis.md",
        "run_manifest.json",
    ):
        assert (output_dir / filename).exists(), filename
    assert "自动误报证据" in (output_dir / "event_errors.csv").read_text()


def test_cli_outputs_are_byte_stable_for_the_same_inputs(tmp_path):
    row = {
        "gold_id": "G1",
        "stock_code": "001282",
        "subscription_date": "2020-05-01",
        "event_context": "增资",
        "subscriber_name": "投资人甲",
        "amount_subscribed": None,
        "shares_subscribed": None,
        "price_per_share": None,
        "source_page": "PDF p1",
        "evidence_text": "稳定人工证据",
    }
    auto = dict(row, auto_id="A1", source_page="MD p1", evidence_text="稳定自动证据")
    gold_path, auto_path = tmp_path / "gold.jsonl", tmp_path / "auto.jsonl"
    write_jsonl(gold_path, [row])
    write_jsonl(auto_path, [auto])
    env = dict(os.environ, PYTHONPATH=str(PROJECT_ROOT))
    output_hashes = []
    for name in ("first", "second"):
        output_dir = tmp_path / name
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--gold", str(gold_path), "--auto", str(auto_path), "--output-dir", str(output_dir)],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
        )
        assert completed.returncode == 0
        output_hashes.append(
            {path.name: path.read_bytes() for path in sorted(output_dir.iterdir())}
        )
    assert output_hashes[0] == output_hashes[1]
