from __future__ import annotations
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
from common import read_jsonl

def test_document_and_version_ids_unique():
    docs=read_jsonl(ROOT/"metadata/documents.jsonl"); versions=read_jsonl(ROOT/"metadata/versions.jsonl")
    assert docs and versions
    assert len({d["document_id"] for d in docs})==len(docs)
    assert len({v["version_id"] for v in versions})==len(versions)

def test_current_version_not_ambiguous():
    versions=read_jsonl(ROOT/"metadata/versions.jsonl"); current={}
    for v in versions:
        if v.get("is_current") is True: assert v["document_id"] not in current; current[v["document_id"]]=v["version_id"]
