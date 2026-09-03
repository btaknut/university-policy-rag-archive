"""4개 공식 원천을 조회하고 기존 version manifest와 비파괴 대조한다."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
from typing import Any

import yaml

from official_sources import (
    HttpClient,
    OfficialSourceCrawler,
    SourceRecord,
    download_record,
    utc_now,
)


ROOT = Path(__file__).resolve().parents[1]


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
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


class ManifestIndex:
    def __init__(self, versions: list[dict[str, Any]]) -> None:
        self.hashes = {row.get("sha256") for row in versions if row.get("sha256")}
        self.title_dates: dict[str, set[str]] = defaultdict(set)
        self.title_document_ids: dict[str, set[str]] = defaultdict(set)
        for row in versions:
            key = row.get("title_normalized")
            if not key:
                from official_sources import normalize_title

                key = normalize_title(row.get("title", ""))
            if not key:
                continue
            for field in ("revision_date", "effective_date"):
                if row.get(field):
                    self.title_dates[key].add(row[field])
            if row.get("document_id"):
                self.title_document_ids[key].add(row["document_id"])

    def classify(self, record: SourceRecord) -> tuple[str, list[str]]:
        if record.attachment_role == "supporting":
            return "supporting_attachment", []
        if record.sha256 and record.sha256 in self.hashes:
            return "present_hash", []
        key = record.title_normalized
        document_ids = sorted(self.title_document_ids.get(key, set()))
        if key and record.effective_date in self.title_dates.get(key, set()):
            return "present_metadata", document_ids
        if key and key in self.title_document_ids:
            return "new_version_candidate", document_ids
        return "new_document_candidate", []


def make_client(config: dict[str, Any]) -> HttpClient:
    http = config.get("http", {})
    return HttpClient(
        user_agent=http.get(
            "user_agent", "university-policy-rag-archive/0.2"
        ),
        timeout_seconds=int(http.get("timeout_seconds", 30)),
        retries=int(http.get("retries", 2)),
        delay_seconds=float(http.get("delay_seconds", 0.5)),
    )


def markdown_report(
    rows: list[dict[str, Any]], errors: dict[str, str], generated_at: str
) -> str:
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        by_source[row["source_id"]][row["comparison_status"]] += 1

    lines = [
        "# 공식 원천 자동 대조 결과",
        "",
        f"- 생성 시각(UTC): {generated_at}",
        f"- 수집 레코드: {len(rows)}",
        f"- 원천 오류: {len(errors)}",
        "",
        "## 원천별 요약",
        "",
        "| source_id | 전체 | 해시 일치 | 메타데이터 일치 | 신규 버전 후보 | 신규 문서 후보 | 보조 첨부 | 오류 |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    source_ids = sorted(set(by_source) | set(errors))
    for source_id in source_ids:
        counts = by_source[source_id]
        total = sum(counts.values())
        lines.append(
            "| {source} | {total} | {hash_match} | {metadata} | {new_version} | {new_document} | {supporting} | {error} |".format(
                source=source_id,
                total=total,
                hash_match=counts["present_hash"],
                metadata=counts["present_metadata"],
                new_version=counts["new_version_candidate"],
                new_document=counts["new_document_candidate"],
                supporting=counts["supporting_attachment"],
                error=errors.get(source_id, ""),
            )
        )

    candidates = [
        row
        for row in rows
        if row["comparison_status"]
        in {"new_version_candidate", "new_document_candidate"}
        and row.get("attachment_role") != "supporting"
    ]
    lines.extend(
        [
            "",
            "## 검토 후보",
            "",
            "| source_id | 판정 | 시행일 | 제목 | 기존 document_id | 원천 |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in sorted(
        candidates,
        key=lambda item: (
            item.get("effective_date") or "",
            item.get("source_id") or "",
        ),
        reverse=True,
    ):
        title = str(row.get("title_raw", "")).replace("|", "\\|")
        ids = ", ".join(row.get("matched_document_ids") or [])
        url = row.get("source_page_url") or ""
        lines.append(
            f"| {row['source_id']} | {row['comparison_status']} | {row.get('effective_date') or ''} | {title} | {ids} | {url} |"
        )

    if errors:
        lines.extend(["", "## 원천 오류", ""])
        for source_id, message in sorted(errors.items()):
            lines.append(f"- `{source_id}`: {message}")

    lines.extend(
        [
            "",
            "## 판정 기준",
            "",
            "1. 원본 SHA-256이 같으면 `present_hash`",
            "2. 정규화 제목과 시행일이 같으면 `present_metadata`",
            "3. 제목만 같으면 `new_version_candidate`",
            "4. 제목 그룹도 없으면 `new_document_candidate`",
            "5. 사유서·대비표 등은 `supporting_attachment`",
            "",
            "후보는 자동으로 manifest에 반영하지 않는다. 원본 해시와 문서 그룹을 검토한 뒤 별도 갱신 절차를 실행한다.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "official_sources.yaml",
    )
    parser.add_argument(
        "--versions",
        type=Path,
        default=ROOT / "metadata" / "versions.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / ".artifacts" / "official-source-check",
    )
    parser.add_argument(
        "--source",
        action="append",
        help="source_id를 반복 지정하면 해당 원천만 조회",
    )
    parser.add_argument(
        "--download-new",
        action="store_true",
        help="신규 문서·버전 후보 원본을 output-dir/downloads 아래에 저장",
    )
    parser.add_argument("--fail-on-source-error", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    versions = read_jsonl(args.versions)
    if not versions:
        raise SystemExit(f"version manifest가 비어 있거나 없습니다: {args.versions}")

    index = ManifestIndex(versions)
    client = make_client(config)
    crawler = OfficialSourceCrawler(config, client)
    selected = set(args.source or [])
    records: list[SourceRecord] = []
    errors: dict[str, str] = {}

    for source in config.get("sources", []):
        source_id = source["source_id"]
        if not source.get("enabled", True) or (selected and source_id not in selected):
            continue
        try:
            records.extend(crawler.crawl(source))
        except Exception as exc:  # 원천 단위 실패 격리
            errors[source_id] = f"{type(exc).__name__}: {exc}"

    classified: list[tuple[SourceRecord, str, list[str]]] = []
    for record in records:
        status, document_ids = index.classify(record)
        if (
            args.download_new
            and record.attachment_url
            and record.attachment_role == "document"
            and status in {"new_version_candidate", "new_document_candidate"}
        ):
            try:
                record = download_record(client, record, args.output_dir / "downloads")
                status, document_ids = index.classify(record)
            except Exception as exc:
                status = "download_error"
                document_ids = []
                errors[f"{record.source_id}:{record.source_record_id}"] = (
                    f"{type(exc).__name__}: {exc}"
                )
        classified.append((record, status, document_ids))

    generated_at = utc_now()
    output_rows = []
    for record, status, document_ids in classified:
        row = record.to_dict()
        row["comparison_status"] = status
        row["matched_document_ids"] = document_ids
        row["check_generated_at"] = generated_at
        output_rows.append(row)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "official_source_snapshot.jsonl", output_rows)
    (args.output_dir / "official_source_check.md").write_text(
        markdown_report(output_rows, errors, generated_at), encoding="utf-8"
    )
    (args.output_dir / "errors.json").write_text(
        json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "generated_at": generated_at,
                "records": len(output_rows),
                "errors": len(errors),
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
        )
    )
    return 2 if errors and args.fail_on_source_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
