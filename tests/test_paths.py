from __future__ import annotations
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
from common import read_jsonl, sha256_file

def test_source_manifest_paths_and_hashes():
    rows=read_jsonl(ROOT/"metadata/source_manifest.jsonl"); assert rows
    assert all((ROOT/r["archive_file"]).is_file() for r in rows)
    assert all(sha256_file(ROOT/r["archive_file"])==r["sha256"] for r in rows)
