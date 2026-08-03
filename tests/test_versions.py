from __future__ import annotations
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
from common import read_jsonl

def test_version_links_stay_in_document():
    versions=read_jsonl(ROOT/"metadata/versions.jsonl"); by_id={v["version_id"]:v for v in versions}
    for v in versions:
        for key in ("previous_version_id","next_version_id"):
            if v.get(key): assert by_id[v[key]]["document_id"]==v["document_id"]
