from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_retrieval_cases_have_real_nonempty_ids():
    config=json.loads((ROOT/"config/retrieval_eval.json").read_text(encoding="utf-8"))
    assert len(config["cases"])>=12
    assert all(case.get("expected") for case in config["cases"])
    assert all(e.get("document_id") and e.get("version_id") for case in config["cases"] for e in case["expected"])

def test_local_source_config_has_no_personal_absolute_path():
    text=(ROOT/"config/sources.yaml").read_text(encoding="utf-8")
    assert r"C:\Users" not in text
    assert "UNIVERSITY_POLICY_SOURCE_ROOT" in text
