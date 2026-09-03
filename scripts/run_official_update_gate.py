"""검토 완료 공식 원천 배치를 교차 플랫폼 파이프라인으로 반영한다.

이 스크립트는 git add/commit/push 또는 PR 병합을 수행하지 않는다. 기본 실행은
배치·해시·기존 버전 연결을 점검하는 plan-only 모드다.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

from convert_hwp_portable import UNHWP_VERSION, probe_unhwp, sha256_file


ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def run_command(command: list[str], repo: Path) -> None:
    print("+ " + subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=repo, check=True)


def ensure_clean_worktree(repo: Path) -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        raise RuntimeError(
            "작업 트리에 미커밋 변경이 있습니다. 공식 업데이트 전 별도 보관 또는 커밋이 필요합니다."
        )


def ensure_portable_requirements(repo: Path, unhwp: Path) -> None:
    if shutil.which("git") is None:
        raise RuntimeError("git 실행 파일을 찾지 못했습니다")
    subprocess.run(
        ["git", "lfs", "version"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    probe_unhwp(unhwp)


def default_unhwp(repo: Path) -> Path:
    executable = "unhwp.exe" if os.name == "nt" else "unhwp"
    return repo / ".tools/unhwp" / f"v{UNHWP_VERSION}" / executable


def build_pipeline_commands(
    repo: Path,
    batch: Path,
    downloads_dir: Path,
    unhwp: Path,
    force_markdown: bool = False,
) -> list[list[str]]:
    python = sys.executable
    apply_command = [
        python,
        str(repo / "scripts/apply_official_updates.py"),
        "--repo-root",
        str(repo),
        "--batch",
        str(batch),
        "--downloads-dir",
        str(downloads_dir),
        "--apply",
    ]
    convert_command = [
        python,
        str(repo / "scripts/convert_hwp_portable.py"),
        "--repo-root",
        str(repo),
        "--batch",
        str(batch),
        "--unhwp",
        str(unhwp),
    ]
    if force_markdown:
        convert_command.append("--force")
    python_steps = [
        "build_versions.py",
        "build_chunks.py",
        "build_catalog.py",
        "validate_corpus.py",
    ]
    return [apply_command, convert_command] + [
        [python, str(repo / "scripts" / script)] for script in python_steps
    ] + [[python, "-m", "pytest", "-q"]]


def native_pdf_complete(repo: Path, version: dict[str, Any]) -> bool:
    relative = version.get("pdf_relative_path")
    expected = version.get("pdf_sha256")
    if version.get("pdf_conversion_status") != "success" or not relative or not expected:
        return False
    path = repo / relative
    return path.is_file() and sha256_file(path) == expected and bool(version.get("pdf_pages"))


def portable_markdown_complete(repo: Path, version: dict[str, Any]) -> bool:
    relative = version.get("normalized_file")
    expected = version.get("portable_markdown_sha256")
    if (
        version.get("portable_conversion_status") != "success"
        or version.get("portable_extraction_tool") != "unhwp"
        or version.get("portable_extraction_version") != UNHWP_VERSION
        or not relative
        or not expected
    ):
        return False
    path = repo / relative
    return (
        path.is_file()
        and sha256_file(path) == expected
        and int(version.get("portable_text_chars") or 0) >= 200
        and int(version.get("portable_hangul_chars") or 0) >= 80
        and float(version.get("portable_hangul_ratio") or 0) >= 0.15
        and int(version.get("portable_replacement_chars") or 0) == 0
    )


def verify_gate_versions(repo: Path, batch: dict[str, Any]) -> list[dict[str, Any]]:
    versions = {
        row["version_id"]: row
        for row in read_jsonl(repo / "metadata/versions.jsonl")
    }
    results = []
    errors = []
    for record in batch.get("records", []):
        version_id = record["version_id"]
        version = versions.get(version_id)
        if version is None:
            errors.append(f"{version_id}: versions.jsonl에 없음")
            continue
        source = repo / version["source_file"]
        normalized = version.get("normalized_file")
        portable = portable_markdown_complete(repo, version)
        native_pdf = native_pdf_complete(repo, version)
        required = {
            "metadata_sha256": version.get("sha256") == record["sha256"],
            "source_sha256": source.is_file() and sha256_file(source) == record["sha256"],
            "is_current": version.get("is_current") is True,
            "normalized_file": bool(normalized) and (repo / normalized).is_file(),
            "portable_markdown_complete": portable,
            "native_pdf_complete": native_pdf,
            "derivative_complete": portable or native_pdf,
        }
        failed = [
            name
            for name in (
                "metadata_sha256",
                "source_sha256",
                "is_current",
                "normalized_file",
                "derivative_complete",
            )
            if not required[name]
        ]
        if failed:
            errors.append(f"{version_id}: {', '.join(failed)}")
        results.append({"version_id": version_id, "checks": required})
    if errors:
        raise RuntimeError("공식 업데이트 최종 Gate 실패:\n- " + "\n- ".join(errors))
    return results


def verify_lfs_attributes(repo: Path, batch: dict[str, Any]) -> None:
    versions = {
        row["version_id"]: row
        for row in read_jsonl(repo / "metadata/versions.jsonl")
    }
    paths = []
    for record in batch.get("records", []):
        version = versions[record["version_id"]]
        paths.append(version["source_file"])
        if version.get("pdf_relative_path"):
            paths.append(version["pdf_relative_path"])
    result = subprocess.run(
        ["git", "check-attr", "filter", "--", *paths],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    invalid = [line for line in result.stdout.splitlines() if not line.endswith(": lfs")]
    if invalid:
        raise RuntimeError("Git LFS 속성 누락:\n- " + "\n- ".join(invalid))


def write_gate_report(
    repo: Path,
    status: str,
    batch_path: Path,
    results: list[dict[str, Any]] | None = None,
    error: str | None = None,
) -> Path:
    generated_at = datetime.now(timezone.utc)
    target = repo / ".artifacts/official-update" / (
        "gate-" + generated_at.strftime("%Y%m%dT%H%M%SZ") + ".json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "generated_at": generated_at.isoformat(),
                "status": status,
                "platform": sys.platform,
                "unhwp_version": UNHWP_VERSION,
                "batch": str(batch_path),
                "results": results or [],
                "error": error,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument(
        "--batch",
        type=Path,
        default=ROOT / "reports/p1_official_update_batch_2026-09-03.json",
    )
    parser.add_argument("--downloads-dir", type=Path, required=True)
    parser.add_argument("--unhwp", type=Path)
    parser.add_argument("--install-unhwp", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--force-markdown", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo_root.resolve()
    batch_path = args.batch.resolve()
    downloads_dir = args.downloads_dir.resolve()
    binary = args.unhwp.resolve() if args.unhwp else default_unhwp(repo)
    batch = json.loads(batch_path.read_text(encoding="utf-8"))

    plan = [
        sys.executable,
        str(repo / "scripts/apply_official_updates.py"),
        "--repo-root",
        str(repo),
        "--batch",
        str(batch_path),
        "--downloads-dir",
        str(downloads_dir),
    ]
    run_command(plan, repo)
    if not args.apply:
        print("plan-only 완료. 실제 반영에는 --apply가 필요합니다.")
        return 0

    try:
        ensure_clean_worktree(repo)
        if args.install_unhwp:
            if args.unhwp:
                raise RuntimeError("--install-unhwp와 --unhwp는 함께 사용할 수 없습니다")
            run_command(
                [
                    sys.executable,
                    str(repo / "scripts/install_unhwp.py"),
                    "--target",
                    str(binary.parent),
                ],
                repo,
            )
        ensure_portable_requirements(repo, binary)
        for command in build_pipeline_commands(
            repo,
            batch_path,
            downloads_dir,
            binary,
            args.force_markdown,
        ):
            run_command(command, repo)
        results = verify_gate_versions(repo, batch)
        verify_lfs_attributes(repo, batch)
        report = write_gate_report(repo, "success", batch_path, results)
        print(f"Gate 성공: {report.relative_to(repo).as_posix()}")
        print("git add/commit/push는 수행하지 않았습니다. 변경 파일을 검토한 뒤 PR 절차로 진행하십시오.")
        return 0
    except Exception as exc:
        report = write_gate_report(repo, "failed", batch_path, error=str(exc))
        print(f"Gate 실패: {report.relative_to(repo).as_posix()}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
