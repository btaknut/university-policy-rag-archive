# 공식 규정·지침 증분 반영 절차

이 절차는 공식 원천 자동 대조 결과 중 원문 해시와 기존 문서 그룹 검토가 끝난 배치만 실제 코퍼스에 반영한다. Windows 한컴오피스에 의존하지 않으며 Linux, macOS, Windows에서 같은 Gate를 사용한다.

## 파생본 정책

- 공식 HWP는 변경하지 않는 권위 원본이며 Git LFS로 보관한다.
- 신규 HWP는 고정 버전 `unhwp 0.9.1`로 구조화 Markdown을 생성한다.
- 설치 스크립트는 운영체제별 공식 배포본의 SHA-256을 확인한 뒤 `.tools/`에 설치한다.
- Markdown은 원본 해시, 결과 해시, 도구 버전, 글자 수, 한글 비율, 대체문자, 조문 수를 기록한다.
- 기존 한컴오피스 PDF 파생본은 그대로 인정한다. 신규 portable 경로에서는 품질이 불확실한 PDF를 만들지 않는다.

## 사전 조건

- 작업 브랜치가 최신이고 작업 트리에 미커밋 변경이 없어야 한다.
- Python 의존성과 Git LFS가 설치되어 있어야 한다.
- 자동 수집 결과의 `new_version_candidate`를 사람이 기존 `document_id`와 직전 `version_id`에 연결한 검토 배치를 사용한다.
- 지원 플랫폼은 Linux x86_64, macOS x86_64/Apple Silicon, Windows x86_64이다.

## 1. 공식 원문 다운로드

배치에 기록된 상세 페이지를 먼저 방문해 쿠키를 유지하고, 같은 세션과 `Referer`로 첨부파일을 받는다. 다운로드 직후 파일 크기와 SHA-256이 배치와 정확히 일치해야 한다.

```bash
python scripts/download_official_batch.py \
  --batch reports/p1_official_update_batch_2026-09-03.json \
  --output-dir .artifacts/official-downloads
```

수동으로 확보한 파일을 사용할 때는 위 단계를 생략하고 해당 폴더를 `--downloads-dir`에 지정할 수 있다. Gate가 같은 해시 검증을 다시 수행한다.

## 2. 계획 검증

```bash
python scripts/run_official_update_gate.py \
  --batch reports/p1_official_update_batch_2026-09-03.json \
  --downloads-dir .artifacts/official-downloads
```

계획 검증에서는 파일 크기, SHA-256, 기존 `document_id`, 직전 `version_id`, 신규 `version_id` 충돌 여부를 확인한다. 저장소 파일은 변경하지 않는다.

## 3. 실제 반영 Gate

처음 실행할 때는 검증된 `unhwp` 배포본을 함께 설치한다.

```bash
python scripts/run_official_update_gate.py \
  --batch reports/p1_official_update_batch_2026-09-03.json \
  --downloads-dir .artifacts/official-downloads \
  --install-unhwp \
  --apply
```

이미 설치한 실행 파일이나 별도 검증한 실행 파일을 지정할 수도 있다.

```bash
python scripts/run_official_update_gate.py \
  --batch reports/p1_official_update_batch_2026-09-03.json \
  --downloads-dir .artifacts/official-downloads \
  --unhwp /path/to/unhwp \
  --apply
```

실행 순서는 다음과 같다.

1. 기존 메타데이터 3종 백업
2. HWP 원본을 `sources/raw/.../official/`에 해시 검증 복사
3. 기존 현행본을 과거본으로 전환하고 신규 버전 연결
4. `unhwp 0.9.1`로 Markdown 변환
5. 제목 존재, 본문 200자 이상, 한글 80자 이상, 한글 비율 0.15 이상, Unicode 대체문자 0건 검증
6. Markdown SHA-256과 변환 지표를 버전·문서·portable manifest에 기록
7. 버전 링크, RAG 청크, 카탈로그 재생성
8. JSON Schema·현행본 단일성·원본/파생본 해시·청크 검증
9. 전체 단위 테스트와 HWP Git LFS 속성 검증

스크립트는 `git add`, commit, push, PR 병합을 수행하지 않는다.

## 4. GitHub에서 실제 반영 PR 생성

Actions의 `Apply official update`를 수동 실행한다.

- `mode=plan`: 공식 파일을 다시 받고 계획 검증만 수행한다.
- `mode=create_pr`: 전체 Gate를 통과한 변경만 새 브랜치에 commit하고 draft PR을 만든다.
- 워크플로는 PR을 병합하거나 기본 브랜치에 직접 push하지 않는다.

실패 여부와 관계없이 다운로드 및 Gate 보고서는 workflow artifact로 남는다.

## 5. 결과 검토

성공 또는 실패 결과는 `.artifacts/official-update/gate-*.json`에 기록된다. 성공 후 다음 항목을 확인한다.

```bash
git status --short
git diff --stat
git lfs status
```

- 신규 HWP와 Markdown 수가 배치 레코드 수와 같은지
- `metadata/documents.jsonl`, `metadata/versions.jsonl`, `metadata/source_manifest.jsonl`
- `metadata/portable_hwp_manifest.jsonl`
- `metadata/current_documents.jsonl`
- `rag/chunks.jsonl`, `rag/document_catalog.jsonl`, `rag/corpus_manifest.json`
- `reports/hwp_portable_conversion.md`, `reports/corpus_validation.md`

## 실패 처리

자동 롤백은 수행하지 않는다. 변환 실패의 원인을 보존하기 위한 조치다. 메타데이터 원본은 `.artifacts/official-update/backups/<UTC 시각>/`에 저장된다.

- 배포본 해시 불일치: 설치를 중단하고 `unhwp` 공식 릴리스의 자산과 해시를 재검토한다.
- HWP 해시 불일치: 파일을 폐기하고 공식 상세 페이지에서 다시 수집한다.
- 한글·제목·대체문자 품질 실패: 코퍼스 반영을 중단하고 해당 파일을 수동 검토한다.
- 기존 버전 불일치: 최신 브랜치에서 배치를 재생성하고 문서 그룹을 재검토한다.
- 코퍼스 검증 실패: commit·push하지 않고 검증 보고서의 FAIL 항목을 수정한다.

기존 `sync_archive.py`는 레거시 로컬 아카이브 전체를 다시 구축하는 경로이므로 공식 웹 증분 배치 반영에는 사용하지 않는다.
