from __future__ import annotations
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
from common import read_jsonl, verify_content_or_lfs_pointer

def test_source_manifest_paths_and_hashes():
    rows=read_jsonl(ROOT/"metadata/source_manifest.jsonl"); assert rows
    assert all((ROOT/r["archive_file"]).is_file() for r in rows)
    assert all(verify_content_or_lfs_pointer(ROOT/r["archive_file"],r["sha256"]) for r in rows)

def test_lfs_pointer_oid_verification(tmp_path):
    digest="a"*64; pointer=tmp_path/"sample.hwp"
    pointer.write_text(f"version https://git-lfs.github.com/spec/v1\noid sha256:{digest}\nsize 123\n",encoding="utf-8")
    assert verify_content_or_lfs_pointer(pointer,digest)

def test_hwp_versions_have_verified_derivatives():
    versions=read_jsonl(ROOT/"metadata/versions.jsonl")
    hwp=[v for v in versions if v["source_file"].lower().endswith(".hwp")]
    assert hwp
    def verified(version):
        if version.get("pdf_relative_path") and version.get("pdf_pages",0)>0:
            return verify_content_or_lfs_pointer(ROOT/version["pdf_relative_path"],version["pdf_sha256"])
        return bool(
            version.get("portable_conversion_status") == "success"
            and version.get("normalized_file")
            and version.get("portable_markdown_sha256")
            and verify_content_or_lfs_pointer(
                ROOT/version["normalized_file"], version["portable_markdown_sha256"]
            )
        )
    assert all(verified(version) for version in hwp)
