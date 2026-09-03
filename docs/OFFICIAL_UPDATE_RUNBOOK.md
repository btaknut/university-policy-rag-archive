# 공식 규정·지침 증분 반영 절차

이 절차는 공식 원천 자동 대조 결과 중 원문 해시와 기존 문서 그룹 검토가 끝난 배치만 실제 코퍼스에 반영한다. HWP 파생 PDF의 한글 텍스트 정확도를 유지하기 위해 실제 반영은 Windows와 한컴오피스 2020 COM 환경에서 수행한다.

## 사전 조건

- 작업 브랜치가 최신이고 작업 트리에 미커밋 변경이 없어야 한다.
- Python 의존성, Git LFS, 한컴오피스 2020이 설치되어 있어야 한다.
- 검토 완료 배치와 해당 HWP 원문이 같은 로컬 폴더에 있어야 한다.
- 자동 수집 결과의 `new_version_candidate`를 사람이 기존 `document_id`에 연결한 뒤 사용한다.

## 1. 계획 검증

```powershell
python scripts\run_official_update_gate.py `
  --batch reports\p1_official_update_batch_2026-09-03.json `
  --downloads-dir C:\path\to\official-downloads
```

계획 검증에서는 파일 크기, SHA-256, 기존 `document_id`, 직전 `version_id`, 신규 `version_id` 충돌 여부를 확인한다. 저장소 파일은 변경하지 않는다.

## 2. 실제 반영 및 전체 Gate

```powershell
python scripts\run_official_update_gate.py `
  --batch reports\p1_official_update_batch_2026-09-03.json `
  --downloads-dir C:\path\to\official-downloads `
  --apply
```

실행 순서는 다음과 같다.

1. 기존 메타데이터 3종 백업
2. HWP 원본을 `sources/raw/.../official/`에 해시 검증 복사
3. 기존 현행본을 과거본으로 전환하고 신규 버전 연결
4. 한컴오피스 COM으로 HWP를 PDF로 변환
5. PDF 페이지·텍스트 레이어·SHA-256 검증
6. Markdown, 버전 링크, RAG 청크, 카탈로그 재생성
7. JSON Schema·현행본 단일성·원본/PDF 해시·청크 검증
8. 전체 단위 테스트
9. HWP와 PDF에 Git LFS 속성이 적용되는지 확인

스크립트는 `git add`, commit, push, PR 병합을 수행하지 않는다.

## 3. 결과 검토

성공 또는 실패 결과는 `.artifacts/official-update/gate-*.json`에 기록된다. 성공 후 다음 항목을 수동 확인한다.

```powershell
git status --short
git diff --stat
git lfs status
```

- 신규 HWP 5건과 PDF 5건
- 신규 Markdown 5건
- `metadata/documents.jsonl`
- `metadata/versions.jsonl`
- `metadata/source_manifest.jsonl`
- `metadata/current_documents.jsonl`
- `rag/chunks.jsonl`
- `rag/document_catalog.jsonl`
- `rag/corpus_manifest.json`
- 변환 및 코퍼스 검증 보고서

## 실패 처리

자동 롤백은 수행하지 않는다. 변환 실패의 원인을 보존하기 위한 조치다. 메타데이터 원본은 `.artifacts/official-update/backups/<UTC 시각>/`에 저장된다.

- HWP 열기 실패: 한컴오피스 COM 등록과 파일 손상 여부 확인
- PDF 텍스트 없음: OCR 후보로 분리하고 현행 코퍼스 반영 보류
- 해시 불일치: 해당 원문을 폐기하고 공식 상세 페이지에서 다시 수집
- 기존 버전 불일치: 최신 브랜치에서 배치를 재생성하고 문서 그룹 재검토
- 코퍼스 검증 실패: commit·push하지 않고 검증 보고서의 FAIL 항목 수정

기존 `sync_archive.py`는 레거시 로컬 아카이브 전체를 다시 구축하는 경로이므로, 공식 웹 증분 배치 반영에는 사용하지 않는다.
