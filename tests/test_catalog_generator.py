from __future__ import annotations
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
from build_github_catalog import build

def test_github_catalog_is_deterministic_and_linked(tmp_path):
    assert build(tmp_path)==403
    first={p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob("*.md")}
    assert build(tmp_path)==403
    second={p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob("*.md")}
    assert first==second
    assert (tmp_path/"latest/regulations-001.md").exists()
    assert "document_id" in (tmp_path/"by-title.md").read_text(encoding="utf-8")
