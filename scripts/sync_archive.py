"""원본 신규·변경을 비파괴 증분 반영하는 전체 오케스트레이터."""
from __future__ import annotations

import subprocess
import sys

from common import ROOT


def main() -> int:
    for script, args in (("audit_source.py", []), ("migrate_sources.py", ["--execute"]), ("extract_text.py", []), ("normalize_documents.py", []), ("build_versions.py", [])):
        subprocess.run([sys.executable, str(ROOT/"scripts"/script), *args], cwd=ROOT, check=True)
    if sys.platform == "win32":
        subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT/"scripts/convert_hwp_to_pdf.ps1")], cwd=ROOT, check=True)
        subprocess.run([sys.executable, str(ROOT/"scripts/index_pdf_derivatives.py")], cwd=ROOT, check=True)
    for script in ("build_chunks.py", "build_catalog.py", "validate_corpus.py"):
        subprocess.run([sys.executable, str(ROOT/"scripts"/script)], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__": raise SystemExit(main())
