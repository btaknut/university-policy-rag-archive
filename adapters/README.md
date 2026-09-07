# 검색 어댑터

실제 지원되는 기본 검색은 `scripts/build_search_index.py`와 `scripts/search_corpus.py`의 SQLite FTS5 구현이다. 외부 API가 필요 없으며 FTS5 미지원 Python에서는 SQLite `LIKE` 대체 검색으로 동작한다.

`chroma_adapter.py`, `faiss_adapter.py`, `qdrant_adapter.py`는 입력·필터 계약을 보여 주는 **미구현 예시**다. 임베딩 생성이나 벡터 DB 적재 기능으로 간주하지 말아야 하며, provider·클라이언트·인증·재시도 정책을 구현하고 별도 검증하기 전에는 운영에 사용하지 않는다.
