"""검토 완료 배치의 공식 첨부파일을 다시 받아 해시와 크기를 검증한다."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from official_sources import HttpClient


ROOT = Path(__file__).resolve().parents[1]


def download_batch(
    batch: dict[str, Any], output_dir: Path, client: HttpClient
) -> list[dict[str, Any]]:
    results = []
    errors = []
    for record in batch.get("records", []):
        version_id = record.get("version_id") or record.get("source_record_id")
        try:
            page_url = record["source_page_url"]
            client.text(page_url)
            target, digest, _ = client.download(
                record["attachment_url"],
                output_dir,
                extra_headers={"Referer": page_url},
                filename=record.get("downloaded_filename")
                or record.get("attachment_filename"),
            )
            size = target.stat().st_size
            if digest != record["sha256"]:
                raise ValueError(f"SHA-256 불일치 {digest}")
            if size != int(record["file_size"]):
                raise ValueError(f"파일 크기 불일치 {size} != {record['file_size']}")
            results.append(
                {
                    "version_id": version_id,
                    "file": target.name,
                    "sha256": digest,
                    "file_size": size,
                    "status": "verified",
                }
            )
        except Exception as exc:
            errors.append(f"{version_id}: {exc}")
    if errors:
        raise RuntimeError("공식 첨부파일 다운로드 실패:\n- " + "\n- ".join(errors))
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--batch",
        type=Path,
        default=ROOT / "reports/p1_official_update_batch_2026-09-03.json",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    batch = json.loads(args.batch.resolve().read_text(encoding="utf-8"))
    output_dir = args.output_dir.resolve()
    client = HttpClient(
        user_agent="university-policy-rag-archive/portable-gate",
        timeout_seconds=45,
        retries=2,
        delay_seconds=0.5,
    )
    results = download_batch(batch, output_dir, client)
    report = output_dir / "download-report.json"
    report.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "records": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"verified": len(results)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
