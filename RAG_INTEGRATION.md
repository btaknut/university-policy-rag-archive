# RAG 통합

`rag/chunks.jsonl`은 조문 중심 JSONL이다. 각 행에는 안정적인 chunk/document/version ID, 유형·부서·공개범위·현행상태, 계층 위치, 본문과 embedding 입력, 토큰 근사치, 원본·정규화 경로, SHA-256과 인용 label이 포함된다.

권장 필터는 현재 공개 규정 `access_level == public AND is_current == true`, 과거본 포함 검색은 `current_status in [confirmed, candidate, unknown, historical]`이다. 벡터 DB에는 `text_for_embedding`을 임베딩하고 나머지 필드를 payload로 저장한다. 모델을 바꾸면 기존 벡터를 폐기하고 JSONL에서 전량 재색인한다.

상위 저장소는 `git submodule add https://github.com/btaknut/university-policy-rag-archive.git data/university-policy`로 연결하거나 `rag/exports` bundle을 배포받을 수 있다. 정기 동기화는 source 수집 후 `sync_archive.py`, 검증, 변경 PR 순서로 수행한다. 외부 API를 쓰는 임베딩 생성은 이 저장소의 기본 파이프라인에서 실행하지 않는다.
