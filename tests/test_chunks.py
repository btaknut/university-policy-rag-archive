from __future__ import annotations
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
from common import read_jsonl

def test_chunks_nonempty_unique_and_bounded():
    chunks=read_jsonl(ROOT/"rag/chunks.jsonl"); assert chunks
    assert len({c["chunk_id"] for c in chunks})==len(chunks)
    assert all(c["text"].strip() and c["token_count"]<=1200 for c in chunks)

def test_chunks_are_public_and_citable():
    for c in read_jsonl(ROOT/"rag/chunks.jsonl"):
        assert c["access_level"]=="public"
        assert c["source_file"] and c["sha256"] and c["citation_label"]
