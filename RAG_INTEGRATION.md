# RAG 통합

`rag/chunks.jsonl`은 조문 중심 JSONL이다. 각 행에는 안정적인 chunk/document/version ID, 유형·부서·공개범위·현행상태, 계층 위치, 본문과 embedding 입력, 토큰 근사치, 원본·정규화 경로, SHA-256과 인용 label이 포함된다.

HWP는 `corpus/pdf`의 검색 가능한 PDF로도 제공한다. 상위 ChatGPT 작업은 PDF를 직접 첨부·열람할 수 있고, 검색 파이프라인은 같은 PDF의 텍스트 레이어에서 생성된 `corpus/normalized`와 chunks를 사용한다. PDF 경로와 해시는 `metadata/versions.jsonl`에 기록된다.

권장 기본 필터는 `access_level == public AND is_latest_version == true AND retrieval_scope == primary`다. 법적 현행 시행본만 요구할 때는 `validity_status == in_force AND status_confidence == confirmed`를 추가한다. 기존 `is_current`와 `current_status`는 최신 확보본 호환 필드이며 시행상태 근거로 단독 사용하지 않는다. 벡터 DB에는 `text_for_embedding`을 임베딩하고 나머지 필드를 payload로 저장한다.

개정사유·주요내용·신구조문 대비표는 `retrieval_scope=secondary`로 보존한다. 기본 답변 근거에는 쓰지 않고 개정 연혁을 명시적으로 찾을 때만 포함한다. SQLite FTS5가 기본 구현이며 Chroma·FAISS·Qdrant는 계약 예시로서 별도 설치·구현 없이는 동작하는 검색 서비스가 아니다.

상위 저장소는 `git submodule add https://github.com/btaknut/university-policy-rag-archive.git data/university-policy`로 연결하거나 `rag/exports` bundle을 배포받을 수 있다. 정기 동기화는 source 수집 후 `sync_archive.py`, 검증, 변경 PR 순서로 수행한다. 외부 API를 쓰는 임베딩 생성은 이 저장소의 기본 파이프라인에서 실행하지 않는다.
