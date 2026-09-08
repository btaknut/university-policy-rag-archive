"""원본 신규·변경을 비파괴 증분 반영하는 전체 오케스트레이터."""
from __future__ import annotations

import argparse
import subprocess
import sys

from common import ROOT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rechunk",
        action="store_true",
        help="기존 chunk_id 변경을 승인하고 canonical 청크를 전체 재생성",
    )
    return parser.parse_args()


def main() -> int:
    options = parse_args()
    for script, script_args in (("audit_source.py", []), ("migrate_sources.py", ["--execute"]), ("extract_text.py", []), ("normalize_documents.py", []), ("build_versions.py", [])):
        subprocess.run([sys.executable, str(ROOT/"scripts"/script), *script_args], cwd=ROOT, check=True)
    if sys.platform == "win32":
        subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT/"scripts/convert_hwp_to_pdf.ps1")], cwd=ROOT, check=True)
        subprocess.run([sys.executable, str(ROOT/"scripts/index_pdf_derivatives.py")], cwd=ROOT, check=True)
    chunk_args = ["--mode", "rechunk", "--allow-id-changes"] if options.rechunk else ["--mode", "incremental"]
    subprocess.run([sys.executable, str(ROOT/"scripts/build_chunks.py"), *chunk_args], cwd=ROOT, check=True)
    for script in ("build_catalog.py", "build_github_catalog.py", "validate_corpus.py", "build_search_index.py", "evaluate_retrieval.py"):
        subprocess.run([sys.executable, str(ROOT/"scripts"/script)], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__": raise SystemExit(main())
