"""검토된 HWP 원본을 플랫폼 독립적인 Markdown 파생본으로 변환한다.

원본 HWP는 수정하지 않는다. 고정 버전 ``unhwp``의 출력이 최소 품질 기준을
모두 통과한 경우에만 Markdown과 메타데이터를 원자적으로 갱신한다.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
UNHWP_VERSION = "0.9.1"
ARTICLE_RE = re.compile(r"제\s*(\d+)\s*조(?:의\s*(\d+))?")
HANGUL_RE = re.compile(r"[가-힣]")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def yaml_value(value: object) -> str:
    return "null" if value is None else json.dumps(value, ensure_ascii=False)


def simple_text_key(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value or "").lower()


def canonical_title_key(value: str) -> str:
    text = re.sub(r"^(?:국립)?한국교통대학교", "", value or "")
    text = re.sub(r"(?:일부|전부)?\s*개정(?:안)?$", "", text)
    return simple_text_key(text)


def analyze_markdown(text: str, title: str) -> dict[str, Any]:
    non_whitespace = re.sub(r"\s", "", text)
    hangul_chars = len(HANGUL_RE.findall(text))
    articles = {match.group(0).replace(" ", "") for match in ARTICLE_RE.finditer(text)}
    title_key = canonical_title_key(title)
    return {
        "text_chars": len(text),
        "non_whitespace_chars": len(non_whitespace),
        "hangul_chars": hangul_chars,
        "hangul_ratio": round(hangul_chars / max(1, len(non_whitespace)), 6),
        "replacement_chars": text.count("\ufffd"),
        "article_count": len(articles),
        "title_present": bool(title_key) and title_key in simple_text_key(text),
    }


def quality_errors(metrics: dict[str, Any]) -> list[str]:
    errors = []
    if metrics["text_chars"] < 200:
        errors.append("본문 200자 미만")
    if metrics["hangul_chars"] < 80:
        errors.append("한글 80자 미만")
    if metrics["hangul_ratio"] < 0.15:
        errors.append("한글 비율 0.15 미만")
    if metrics["replacement_chars"]:
        errors.append("Unicode replacement 문자 포함")
    if not metrics["title_present"]:
        errors.append("본문에서 문서 제목을 확인하지 못함")
    return errors


def build_markdown(version: dict[str, Any], document: dict[str, Any], body: str) -> str:
    fields = [
        ("document_id", version["document_id"]),
        ("version_id", version["version_id"]),
        ("document_type", version["document_type"]),
        ("title", version["title"]),
        ("is_current", version.get("is_current")),
        ("current_status", version.get("current_status")),
        ("enactment_date", version.get("enactment_date")),
        ("revision_date", version.get("revision_date")),
        ("effective_date", version.get("effective_date")),
        ("issuing_organization", document.get("issuing_organization") or "국립한국교통대학교"),
        ("department", version.get("department")),
        ("source_url", version.get("source_page_url") or version.get("source_url")),
        ("source_file", version["source_file"]),
        ("sha256", version["sha256"]),
        ("access_level", version.get("access_level") or "public"),
        ("extraction_method", f"unhwp-{UNHWP_VERSION}"),
    ]
    front = ["---"] + [f"{key}: {yaml_value(value)}" for key, value in fields] + ["---", ""]
    return "\n".join(front) + body.strip() + "\n"


def offline_environment() -> dict[str, str]:
    """unhwp의 선택적 업데이트 확인이 네트워크를 사용하지 못하게 제한한다."""
    env = os.environ.copy()
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env[key] = "http://127.0.0.1:9"
    env["NO_PROXY"] = ""
    env["no_proxy"] = ""
    return env


def probe_unhwp(binary: Path) -> str:
    if not binary.is_file():
        raise FileNotFoundError(f"unhwp 실행 파일 없음: {binary}")
    result = subprocess.run(
        [str(binary), "version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
        env=offline_environment(),
    )
    output = (result.stdout + "\n" + result.stderr).strip()
    match = re.search(r"\bunhwp\s+([0-9]+(?:\.[0-9]+){2})\b", output)
    if not match:
        raise RuntimeError(f"unhwp 버전을 확인하지 못함: {output[:200]}")
    if match.group(1) != UNHWP_VERSION:
        raise RuntimeError(
            f"unhwp 버전 불일치: {match.group(1)} != {UNHWP_VERSION}"
        )
    return match.group(1)


def convert_one(binary: Path, source: Path, output: Path) -> str:
    subprocess.run(
        [
            str(binary),
            "markdown",
            str(source),
            "--cleanup",
            "minimal",
            "--refine",
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=offline_environment(),
    )
    return output.read_text(encoding="utf-8-sig")


def normalized_path(version: dict[str, Any]) -> Path:
    bucket = "regulations" if version["document_type"] == "regulation" else "guidelines"
    return Path("corpus/normalized") / bucket / version["document_id"] / f"{version['version_id']}.md"


def apply_portable_metadata(
    version: dict[str, Any],
    document: dict[str, Any],
    relative_path: str,
    markdown_sha256: str,
    metrics: dict[str, Any],
    converted_at: str,
) -> None:
    portable = {
        "normalized_file": relative_path,
        "text_extraction_status": "success_unhwp",
        "portable_conversion_status": "success",
        "portable_extraction_tool": "unhwp",
        "portable_extraction_version": UNHWP_VERSION,
        "portable_markdown_sha256": markdown_sha256,
        "portable_text_chars": metrics["text_chars"],
        "portable_hangul_chars": metrics["hangul_chars"],
        "portable_hangul_ratio": metrics["hangul_ratio"],
        "portable_replacement_chars": metrics["replacement_chars"],
        "portable_article_count": metrics["article_count"],
        "portable_converted_at": converted_at,
        "pdf_conversion_status": "not_generated_portable",
    }
    version.update(portable)
    document.update(portable)
    document["normalized_relative_path"] = relative_path
    document["updated_at"] = converted_at


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument(
        "--batch",
        type=Path,
        default=ROOT / "reports/p1_official_update_batch_2026-09-03.json",
    )
    parser.add_argument("--unhwp", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo_root.resolve()
    batch = json.loads(args.batch.resolve().read_text(encoding="utf-8"))
    binary = args.unhwp.resolve()
    probe_unhwp(binary)

    versions_path = repo / "metadata/versions.jsonl"
    documents_path = repo / "metadata/documents.jsonl"
    manifest_path = repo / "metadata/portable_hwp_manifest.jsonl"
    versions = read_jsonl(versions_path)
    documents = read_jsonl(documents_path)
    versions_by_id = {row["version_id"]: row for row in versions}
    documents_by_id = {row["document_id"]: row for row in documents}
    existing_manifest = {
        row["version_id"]: row for row in read_jsonl(manifest_path)
    }
    staged: list[dict[str, Any]] = []
    failures: list[str] = []

    with tempfile.TemporaryDirectory(prefix="hwp-portable-") as temporary:
        temp_dir = Path(temporary)
        for record in batch.get("records", []):
            version_id = record["version_id"]
            version = versions_by_id.get(version_id)
            if version is None:
                failures.append(f"{version_id}: versions.jsonl에 없음")
                continue
            document = documents_by_id.get(version["document_id"])
            if document is None:
                failures.append(f"{version_id}: documents.jsonl에 없음")
                continue
            source = repo / version["source_file"]
            if not source.is_file():
                failures.append(f"{version_id}: HWP 원본 없음")
                continue
            if sha256_file(source) != record["sha256"] or version.get("sha256") != record["sha256"]:
                failures.append(f"{version_id}: HWP SHA-256 불일치")
                continue

            relative = normalized_path(version)
            target = repo / relative
            if target.exists() and not args.force:
                expected = version.get("portable_markdown_sha256")
                if version.get("portable_conversion_status") == "success" and expected == sha256_file(target):
                    body = target.read_text(encoding="utf-8-sig")
                    metrics = analyze_markdown(body, version["title"])
                    errors = quality_errors(metrics)
                    if not errors:
                        staged.append(
                            {
                                "record": record,
                                "version": version,
                                "document": document,
                                "relative": relative,
                                "content": body,
                                "metrics": metrics,
                                "status": "reused",
                            }
                        )
                        continue
                failures.append(f"{version_id}: 기존 Markdown이 있어 --force 필요")
                continue

            extracted = temp_dir / f"{version_id}.md"
            try:
                body = convert_one(binary, source, extracted)
            except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
                failures.append(f"{version_id}: 변환 실패 ({exc})")
                continue
            metrics = analyze_markdown(body, version["title"])
            errors = quality_errors(metrics)
            if errors:
                failures.append(f"{version_id}: " + ", ".join(errors))
                continue
            content = build_markdown(version, document, body)
            staged.append(
                {
                    "record": record,
                    "version": version,
                    "document": document,
                    "relative": relative,
                    "content": content,
                    "metrics": metrics,
                    "status": "converted",
                }
            )

    if failures:
        raise RuntimeError("HWP portable 변환 Gate 실패:\n- " + "\n- ".join(failures))

    converted_at = datetime.now(timezone.utc).isoformat()
    manifest = existing_manifest.copy()
    for item in staged:
        target = repo / item["relative"]
        target.parent.mkdir(parents=True, exist_ok=True)
        content = item["content"]
        if item["status"] == "converted":
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_text(content, encoding="utf-8", newline="\n")
            temporary.replace(target)
        markdown_sha = sha256_file(target)
        apply_portable_metadata(
            item["version"],
            item["document"],
            item["relative"].as_posix(),
            markdown_sha,
            item["metrics"],
            converted_at,
        )
        manifest[item["version"]["version_id"]] = {
            "version_id": item["version"]["version_id"],
            "document_id": item["version"]["document_id"],
            "source_file": item["version"]["source_file"],
            "source_sha256": item["version"]["sha256"],
            "normalized_file": item["relative"].as_posix(),
            "normalized_sha256": markdown_sha,
            "tool": "unhwp",
            "tool_version": UNHWP_VERSION,
            "status": item["status"],
            "converted_at": converted_at,
            **item["metrics"],
        }

    write_jsonl(versions_path, versions)
    write_jsonl(documents_path, documents)
    write_jsonl(
        manifest_path,
        sorted(manifest.values(), key=lambda row: row["version_id"]),
    )
    report = [
        "# HWP portable Markdown 변환 보고서",
        "",
        f"- 변환 도구: unhwp {UNHWP_VERSION}",
        f"- 처리 성공: {len(staged)}건",
        "- 실패: 0건",
        "- 원본 HWP 변경: 없음",
        "",
        "| version_id | 상태 | 본문 글자 | 한글 글자 | 한글 비율 | 조문 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in staged:
        metrics = item["metrics"]
        report.append(
            f"| {item['version']['version_id']} | {item['status']} | "
            f"{metrics['text_chars']} | {metrics['hangul_chars']} | "
            f"{metrics['hangul_ratio']:.3f} | {metrics['article_count']} |"
        )
    report_path = repo / "reports/hwp_portable_conversion.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({"converted": len(staged), "failed": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
