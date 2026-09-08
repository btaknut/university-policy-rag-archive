"""기존 청크와 명시적 재청킹 결과 사이의 결정적 ID 매핑을 만든다."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from jsonschema import validate

from common import ROOT, read_jsonl, sha256_file, write_json


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _shingles(value: str, width: int = 5) -> set[str]:
    normalized = re.sub(r"\s+", "", value or "")
    if not normalized:
        return set()
    if len(normalized) <= width:
        return {normalized}
    return {normalized[index : index + width] for index in range(len(normalized) - width + 1)}


def overlap_ratio(left: str, right: str) -> float:
    left_set, right_set = _shingles(left), _shingles(right)
    if not left_set or not right_set:
        return 0.0
    return round(len(left_set & right_set) / min(len(left_set), len(right_set)), 6)


def _location(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in ("section_path", "article_no", "paragraph_no", "item_no", "appendix_no", "chunk_index")}


def _same_location(left: dict[str, Any], right: dict[str, Any]) -> bool:
    keys = ("article_no", "appendix_no", "section_path")
    populated = [key for key in keys if left.get(key) is not None]
    return bool(populated) and all(left.get(key) == right.get(key) for key in populated)


def validate_mapping_references(value: dict[str, Any], old_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]) -> None:
    old_ids = {row["chunk_id"] for row in old_rows}
    new_ids = {row["chunk_id"] for row in new_rows}
    mapped_old = [row["old_chunk_id"] for row in value["mappings"] if row["old_chunk_id"] is not None]
    if len(mapped_old) != len(set(mapped_old)) or set(mapped_old) != old_ids:
        raise RuntimeError("매핑이 기존 chunk_id를 정확히 한 번씩 포함하지 않습니다")
    targets = {chunk_id for row in value["mappings"] for chunk_id in row["new_chunk_ids"]}
    if not targets <= new_ids:
        raise RuntimeError("매핑이 존재하지 않는 신규 chunk_id를 참조합니다")
    new_rows_in_map = {
        row["new_chunk_ids"][0]
        for row in value["mappings"]
        if row["relation"] == "new" and len(row["new_chunk_ids"]) == 1
    }
    if new_rows_in_map != new_ids - old_ids:
        raise RuntimeError("신규 chunk_id 목록이 실제 ID 차이와 일치하지 않습니다")


def build_migration_map(old_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]) -> dict[str, Any]:
    old_by_id = {row["chunk_id"]: row for row in old_rows}
    new_by_id = {row["chunk_id"]: row for row in new_rows}
    if len(old_by_id) != len(old_rows) or len(new_by_id) != len(new_rows):
        raise RuntimeError("중복 chunk_id가 있어 매핑할 수 없습니다")
    new_by_version: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in new_rows:
        new_by_version[row["version_id"]].append(row)

    provisional: list[dict[str, Any]] = []
    inbound: Counter[str] = Counter()
    for old in old_rows:
        old_id = old["chunk_id"]
        if old_id in new_by_id:
            candidates = [(new_by_id[old_id], overlap_ratio(old["text"], new_by_id[old_id]["text"]))]
        else:
            pool = new_by_version.get(old["version_id"], [])
            located = [row for row in pool if _same_location(old, row)]
            scored = [(row, overlap_ratio(old["text"], row["text"])) for row in (located or pool)]
            scored = [item for item in scored if item[1] >= (0.15 if located else 0.5)]
            scored.sort(key=lambda item: (-item[1], item[0]["chunk_id"]))
            if scored:
                best = scored[0][1]
                candidates = [item for item in scored if item[1] >= max(0.35, best * 0.8)][:4]
            else:
                candidates = []
        for candidate, _ in candidates:
            inbound[candidate["chunk_id"]] += 1
        provisional.append({"old": old, "candidates": candidates})

    mappings: list[dict[str, Any]] = []
    relation_counts: Counter[str] = Counter()
    for item in provisional:
        old, candidates = item["old"], item["candidates"]
        old_id = old["chunk_id"]
        if old_id in new_by_id:
            relation = "unchanged" if old["text"] == new_by_id[old_id]["text"] else "modified"
        elif not candidates:
            relation = "removed"
        elif len(candidates) > 1:
            relation = "split"
        elif inbound[candidates[0][0]["chunk_id"]] > 1:
            relation = "merged"
        else:
            relation = "modified"
        relation_counts[relation] += 1
        scores = [score for _, score in candidates]
        automatic = relation in {"unchanged", "modified"} and bool(scores) and scores[0] >= 0.8
        mappings.append({
            "document_id": old["document_id"], "version_id": old["version_id"], "old_chunk_id": old_id,
            "new_chunk_ids": [row["chunk_id"] for row, _ in candidates], "relation": relation,
            "old_text_sha256": text_sha256(old["text"]), "new_text_sha256": [text_sha256(row["text"]) for row, _ in candidates],
            "old_location": _location(old), "new_locations": [_location(row) for row, _ in candidates], "overlap_scores": scores,
            "evidence": "same_chunk_id" if old_id in new_by_id else "same_version_location_text_shingles",
            "automatic_match": automatic, "review_required": relation in {"split", "merged", "removed"} or not automatic,
        })

    old_ids, new_ids = set(old_by_id), set(new_by_id)
    for new_id in sorted(new_ids - old_ids):
        new = new_by_id[new_id]
        relation_counts["new"] += 1
        mappings.append({
            "document_id": new["document_id"], "version_id": new["version_id"], "old_chunk_id": None,
            "new_chunk_ids": [new_id], "relation": "new", "old_text_sha256": None,
            "new_text_sha256": [text_sha256(new["text"])], "old_location": None, "new_locations": [_location(new)],
            "overlap_scores": [], "evidence": "new_id_not_in_reference", "automatic_match": False, "review_required": True,
        })
    value = {
        "schema_version": "1.0",
        "summary": {
            "old_chunks": len(old_rows), "new_chunks": len(new_rows), "retained_ids": len(old_ids & new_ids),
            "removed_ids": len(old_ids - new_ids), "new_ids": len(new_ids - old_ids),
            "relations": {key: relation_counts.get(key, 0) for key in ("unchanged", "modified", "split", "merged", "removed", "new")},
            "review_required": sum(1 for row in mappings if row["review_required"]),
        },
        "mappings": mappings,
    }
    validate_mapping_references(value, old_rows, new_rows)
    return value


def write_and_validate(path: Path, value: dict[str, Any], root: Path = ROOT) -> None:
    schema = json.loads((root / "schemas/chunk-migration-map.schema.json").read_text(encoding="utf-8"))
    validate(value, schema)
    write_json(path, value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--old", type=Path, required=True)
    parser.add_argument("--new", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, old_path, new_path = args.repo_root.resolve(), args.old.resolve(), args.new.resolve()
    value = build_migration_map(read_jsonl(old_path), read_jsonl(new_path))
    value["source"] = {
        "old_path": old_path.relative_to(root).as_posix() if old_path.is_relative_to(root) else str(old_path),
        "new_path": new_path.relative_to(root).as_posix() if new_path.is_relative_to(root) else str(new_path),
        "old_sha256": sha256_file(old_path), "new_sha256": sha256_file(new_path),
    }
    write_and_validate(args.output.resolve(), value, root)
    print(json.dumps(value["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
