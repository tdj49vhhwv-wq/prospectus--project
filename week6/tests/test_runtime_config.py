import sys
from pathlib import Path

import pytest


PIPELINE_DIR = Path(__file__).resolve().parents[1] / "pipeline"
sys.path.insert(0, str(PIPELINE_DIR))

import llm_extractor
import markdown_source
import run as pipeline_run
import run_md_pipeline


def test_get_api_key_requires_environment(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        llm_extractor.get_api_key()


def test_get_api_key_reads_environment(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    assert llm_extractor.get_api_key() == "test-key"


def test_default_markdown_dir_is_inside_repository(monkeypatch):
    monkeypatch.delenv("PROSPECTUS_MD_DIR", raising=False)
    expected = Path(markdown_source.__file__).resolve().parents[2] / "week1" / "review"

    assert markdown_source.get_md_dir() == expected


def test_markdown_dir_can_be_overridden(monkeypatch, tmp_path):
    monkeypatch.setenv("PROSPECTUS_MD_DIR", str(tmp_path))

    assert markdown_source.get_md_dir() == tmp_path


def test_pdf_path_resolves_from_repository_root():
    week6_dir = Path(pipeline_run.__file__).resolve().parents[1]
    expected = week6_dir.parent / "week1" / "data" / "week1PDF" / "sample.pdf"

    assert pipeline_run.resolve_pdf_path(week6_dir, "sample.pdf") == expected


def test_located_path_uses_week6_validation():
    week6_dir = Path(pipeline_run.__file__).resolve().parents[1]
    expected = week6_dir / "validation" / "located_sections_920100.json"

    assert pipeline_run.resolve_located_path(week6_dir, "920100") == expected


def test_investor_deduplication_is_sorted_and_limited():
    names = ["投资人九", "投资人三", "投资人一", "投资人三", "投资人八",
             "投资人二", "投资人七", "投资人六", "投资人五", "投资人四"]

    assert run_md_pipeline.stable_unique_names(names, limit=8) == [
        "投资人一", "投资人七", "投资人三", "投资人九",
        "投资人二", "投资人五", "投资人八", "投资人六",
    ]
