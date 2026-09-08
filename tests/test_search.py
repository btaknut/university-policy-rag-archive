from __future__ import annotations
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
from common import read_jsonl
from search_lib import build_index, classify_section, normalize_search_text, search

def test_korean_normalization_handles_spacing_and_punctuation():
    assert normalize_search_text("운영·지침",compact=True)==normalize_search_text("운영 지침",compact=True)
    assert normalize_search_text("ＡＩ(규정)")=="ai 규정"

def test_section_classification_excludes_amendment_material_by_default():
    assert classify_section("개정 사유\n조직 개편")[1:]==("secondary","non_normative")
    assert classify_section("신·구조문 대비표\n| 현 행 | 개 정 안 |","")[1:]==("secondary","historical_context")
    assert classify_section("제3조(구성) 위원회는 구성한다.")[0]=="operative_text"
    assert classify_section("부칙\n이 규정은 공포한 날부터 시행한다.")[0]=="supplementary_provision"

def test_local_index_search_is_citable_and_deduplicated(tmp_path):
    database=tmp_path/"search.sqlite3"; count,engine=build_index(database)
    assert count==len(read_jsonl(ROOT/"rag/chunks.jsonl")) and engine.startswith("fts5")
    rows=search(database,query="휴학",filters={},limit=5,per_document=1)
    assert rows and len({r["document_id"] for r in rows})==len(rows)
    assert all(r["source_page_url"] and r["sha256"] and r["citation_label"] for r in rows)

def test_secondary_comparison_is_not_a_default_result(tmp_path):
    database=tmp_path/"search.sqlite3"; build_index(database)
    rows=search(database,query="금고지정심의위원회",filters={},limit=5,per_document=2)
    assert rows
    assert all(r["section_kind"] not in {"comparison_old","comparison_new","amendment_reason","major_changes"} for r in rows)
