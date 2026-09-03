"""공식 규정·지침 사이트를 읽어 공통 원천 레코드로 변환한다.

이 모듈은 원천 수집만 담당한다. 기존 corpus/metadata 파일을 직접 수정하지 않는다.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from email.message import Message
from hashlib import sha256
from pathlib import Path
import re
import time
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


ISO_DATE_RE = re.compile(r"(?:19|20)\d{2}[-.]\d{1,2}[-.]\d{1,2}")
KOREAN_DATE_RE = re.compile(
    r"((?:19|20)\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})"
)
REGISTER_RE = re.compile(r"popup\(['\"]?(\d+)['\"]?\)")
UT_FILE_RE = re.compile(
    r"fn_egov_downFile\(['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\)"
)
SUPPORTING_RE = re.compile(
    r"(?:제정|개정)\s*사유|신[·ㆍ]?구\s*조문|대비표|검토서|의견서|공포문",
    re.I,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    match = KOREAN_DATE_RE.search(value)
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def extract_effective_date(title: str, fallback: str | None = None) -> str | None:
    matches = list(KOREAN_DATE_RE.finditer(title or ""))
    if matches:
        return normalize_date(matches[-1].group(0))
    return normalize_date(fallback)


def normalize_title(title: str) -> str:
    """기관명·개정표시·날짜를 제거한 보수적 제목 키를 만든다."""
    text = (title or "").strip().lower()
    text = re.sub(r"^\s*\[[^]]+]\s*", "", text)
    text = re.sub(
        r"(?:국립\s*)?한국\s*교통\s*대학교|충주\s*대학교", "", text
    )
    text = re.sub(
        r"\([^)]*(?:제\s*\d+\s*호|지침|규정|제정|개정|시행|(?:19|20)\d{2})[^)]*\)",
        "",
        text,
    )
    text = re.sub(r"(?:일부|전부)?\s*개정안?", "", text)
    text = re.sub(r"설치\s*[·ㆍ.\-]?\s*운영", "설치운영", text)
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def attachment_role(filename: str | None) -> str:
    return "supporting" if SUPPORTING_RE.search(filename or "") else "document"


def query_value(url: str, key: str) -> str | None:
    values = parse_qs(urlparse(url).query).get(key)
    return values[0] if values else None


def with_query(url: str, **updates: Any) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    for key, value in updates.items():
        query[key] = [str(value)]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def safe_filename(value: str) -> str:
    name = Path(unquote(value)).name.strip().replace("\x00", "")
    name = re.sub(r"[<>:\"/\\|?*]", "_", name)
    return name or "download.bin"


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    source_record_id: str
    document_type: str
    source_group: str | None
    title_raw: str
    title_normalized: str
    department: str | None
    posted_date: str | None
    effective_date: str | None
    source_page_url: str
    attachment_url: str | None = None
    attachment_filename: str | None = None
    attachment_role: str = "document"
    sha256: str | None = None
    retrieved_at: str | None = None
    http_etag: str | None = None
    last_modified: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HttpClient:
    """제한된 재시도와 요청 간격을 적용하는 표준 라이브러리 HTTP 클라이언트."""

    def __init__(
        self,
        *,
        user_agent: str,
        timeout_seconds: int = 30,
        retries: int = 2,
        delay_seconds: float = 0.5,
    ) -> None:
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.delay_seconds = delay_seconds

    def _request(self, url: str) -> tuple[bytes, Message]:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                request = Request(
                    url,
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept": "text/html,application/xhtml+xml,application/octet-stream;q=0.9,*/*;q=0.8",
                    },
                )
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = response.read()
                    headers = response.headers
                if self.delay_seconds:
                    time.sleep(self.delay_seconds)
                return payload, headers
            except (HTTPError, URLError, TimeoutError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    raise
                time.sleep(self.delay_seconds * (attempt + 1))
        raise RuntimeError(f"unreachable request failure: {last_error}")

    def text(self, url: str) -> tuple[str, Message]:
        payload, headers = self._request(url)
        charset = headers.get_content_charset()
        for encoding in (charset, "utf-8", "cp949", "euc-kr"):
            if not encoding:
                continue
            try:
                return payload.decode(encoding), headers
            except (LookupError, UnicodeDecodeError):
                continue
        return payload.decode("utf-8", errors="replace"), headers

    def download(self, url: str, target_dir: Path) -> tuple[Path, str, Message]:
        payload, headers = self._request(url)
        disposition = headers.get("Content-Disposition", "")
        name: str | None = None
        encoded = re.search(r"filename\*=UTF-8''([^;]+)", disposition, flags=re.I)
        quoted = re.search(r'filename="([^"]+)"', disposition, flags=re.I)
        plain = re.search(r"filename=([^;]+)", disposition, flags=re.I)
        if encoded:
            name = unquote(encoded.group(1))
        elif quoted:
            name = quoted.group(1)
        elif plain:
            name = plain.group(1).strip()
        if not name:
            name = Path(urlparse(url).path).name or "download.bin"
        filename = safe_filename(name)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        if target.exists() and sha256(target.read_bytes()).digest() != sha256(payload).digest():
            target = target_dir / f"{target.stem}-{sha256(payload).hexdigest()[:8]}{target.suffix}"
        target.write_bytes(payload)
        return target, sha256(payload).hexdigest(), headers


def parse_ut_regulations_list(
    html: str, page_url: str, source_id: str = "ut_regulations"
) -> list[SourceRecord]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[SourceRecord] = []
    for row in soup.select("table tbody tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 6 or not clean_text(cells[0].get_text()).isdigit():
            continue
        view = cells[-1].find("a")
        match = REGISTER_RE.search((view or {}).get("onclick", "")) if view else None
        if not match:
            continue
        register = match.group(1)
        title = clean_text(cells[2].get_text(" "))
        date = normalize_date(clean_text(cells[4].get_text(" ")))
        detail_url = urljoin(
            page_url,
            f"/prog/schoolRegulations/kor/sub05_03_01/list.do?register={register}",
        )
        records.append(
            SourceRecord(
                source_id=source_id,
                source_record_id=f"register:{register}",
                document_type="regulation",
                source_group=clean_text(cells[1].get_text(" ")) or None,
                title_raw=title,
                title_normalized=normalize_title(title),
                department=clean_text(cells[3].get_text(" ")) or None,
                posted_date=None,
                effective_date=date,
                source_page_url=detail_url,
            )
        )
    return records


def parse_ut_regulation_history(html: str, page_url: str) -> list[tuple[str, str | None]]:
    soup = BeautifulSoup(html, "html.parser")
    history: list[tuple[str, str | None]] = []
    for table in soup.find_all("table"):
        if "히스토리" not in clean_text(table.get_text(" ")):
            continue
        for row in table.select("tbody tr"):
            cells = row.find_all("td", recursive=False)
            if len(cells) < 3:
                continue
            link = cells[1].find("a", href=True)
            if link:
                history.append(
                    (
                        urljoin(page_url, link["href"]),
                        normalize_date(clean_text(cells[2].get_text(" "))),
                    )
                )
    return history


def parse_ut_regulation_detail(
    html: str,
    page_url: str,
    base: SourceRecord,
    effective_date: str | None = None,
) -> list[SourceRecord]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[SourceRecord] = []
    cnt_no = query_value(page_url, "cntNo") or "current"
    for link in soup.find_all("a", href=True):
        match = UT_FILE_RE.search(link.get("href", ""))
        if not match:
            continue
        attachment_id, file_sn = match.groups()
        filename = re.sub(r"\s*\(\s*\d+\s*kb\s*\)\s*$", "", clean_text(link.get_text(" ")), flags=re.I)
        download_url = urljoin(
            page_url,
            "/cmm/fms/FileDown.do?" + urlencode({"atchFileId": attachment_id, "fileSn": file_sn}),
        )
        records.append(
            replace(
                base,
                source_record_id=f"{base.source_record_id}:cnt:{cnt_no}:file:{file_sn}",
                source_page_url=page_url,
                effective_date=effective_date or base.effective_date,
                attachment_url=download_url,
                attachment_filename=filename,
                attachment_role=attachment_role(filename),
            )
        )
    return records or [replace(base, source_page_url=page_url, effective_date=effective_date or base.effective_date)]


def parse_ut_guidelines_list(
    html: str, page_url: str, source_id: str = "ut_guidelines"
) -> list[SourceRecord]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[SourceRecord] = []
    for row in soup.select("table tbody tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 6:
            continue
        seq = clean_text(cells[0].get_text(" "))
        if not seq.isdigit():
            continue
        title = clean_text(cells[1].get_text(" "))
        department = clean_text(cells[2].get_text(" ")) or None
        posted = normalize_date(clean_text(cells[3].get_text(" ")))
        attachment_link = cells[-1].find("a", href=True)
        href = urljoin(page_url, attachment_link["href"]) if attachment_link else None
        filename: str | None = None
        attachment_url: str | None = None
        source_page_url = page_url
        if href and "FileDown.do" in href:
            attachment_url = href
            filename = clean_text(attachment_link.get_text(" "))
            filename = re.sub(r"^파일명\s*:\s*", "", filename)
        elif href:
            source_page_url = href
        record_key = query_value(href or "", "nttId") or f"seq:{seq}"
        records.append(
            SourceRecord(
                source_id=source_id,
                source_record_id=record_key,
                document_type="guideline",
                source_group="지침",
                title_raw=title,
                title_normalized=normalize_title(title),
                department=department,
                posted_date=posted,
                effective_date=extract_effective_date(title, posted),
                source_page_url=source_page_url,
                attachment_url=attachment_url,
                attachment_filename=filename,
                attachment_role=attachment_role(filename),
            )
        )
    return records


def parse_ut_guideline_detail(html: str, page_url: str, base: SourceRecord) -> list[SourceRecord]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[SourceRecord] = []
    for link in soup.find_all("a", href=True):
        href = urljoin(page_url, link["href"])
        if "FileDown.do" not in href:
            continue
        filename = clean_text(link.get_text(" "))
        filename = re.sub(r"^파일명\s*:\s*", "", filename)
        file_sn = query_value(href, "fileSn") or str(len(records))
        records.append(
            replace(
                base,
                source_record_id=f"{base.source_record_id}:file:{file_sn}",
                source_page_url=page_url,
                attachment_url=href,
                attachment_filename=filename,
                attachment_role=attachment_role(filename),
            )
        )
    return records or [base]


def parse_sanhak_regulations(
    html: str, page_url: str, source_id: str = "sanhak_regulations"
) -> list[SourceRecord]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[SourceRecord] = []
    for table in soup.find_all("table"):
        caption = clean_text(table.caption.get_text(" ")) if table.caption else ""
        if "공포일" not in caption or "다운로드" not in caption:
            continue
        group = caption.split(" - ", 1)[0].strip() or None
        for row in table.select("tbody tr"):
            cells = row.find_all("td", recursive=False)
            if len(cells) < 4 or not clean_text(cells[0].get_text()).isdigit():
                continue
            title = clean_text(cells[1].get_text(" "))
            date = normalize_date(clean_text(cells[2].get_text(" ")))
            link = cells[-1].find("a", href=True)
            if not link:
                continue
            attachment_url = urljoin(page_url, link["href"])
            record_key = query_value(attachment_url, "file_id") or sha256(attachment_url.encode()).hexdigest()[:16]
            records.append(
                SourceRecord(
                    source_id=source_id,
                    source_record_id=record_key,
                    document_type="regulation",
                    source_group=group,
                    title_raw=title,
                    title_normalized=normalize_title(title),
                    department="산학협력단",
                    posted_date=None,
                    effective_date=date,
                    source_page_url=page_url,
                    attachment_url=attachment_url,
                )
            )
    return records


def parse_sanhak_guidelines_list(
    html: str, page_url: str, source_id: str = "sanhak_guidelines"
) -> list[SourceRecord]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[SourceRecord] = []
    for row in soup.select("table tbody tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 4:
            continue
        seq = clean_text(cells[0].get_text(" "))
        if not seq.isdigit():
            continue
        detail = row.find("a", href=re.compile(r"(?:mode=V|mode=VIEW)", re.I))
        if not detail:
            continue
        title = clean_text(detail.get_text(" "))
        detail_index = next((i for i, cell in enumerate(cells) if detail in cell.descendants), 1)
        cell_texts = [clean_text(cell.get_text(" ")) for cell in cells]
        posted = next((normalize_date(text) for text in cell_texts if ISO_DATE_RE.search(text)), None)
        category = cell_texts[1] if detail_index > 1 else "지침"
        department = cell_texts[detail_index + 1] if detail_index + 1 < len(cells) else None
        if department and normalize_date(department):
            department = None
        detail_url = urljoin(page_url, detail["href"])
        record_key = query_value(detail_url, "no") or f"seq:{seq}"
        records.append(
            SourceRecord(
                source_id=source_id,
                source_record_id=record_key,
                document_type="guideline",
                source_group=category,
                title_raw=title,
                title_normalized=normalize_title(title),
                department=department,
                posted_date=posted,
                effective_date=extract_effective_date(title, posted),
                source_page_url=detail_url,
            )
        )
    return records


def parse_sanhak_guideline_detail(html: str, page_url: str, base: SourceRecord) -> list[SourceRecord]:
    soup = BeautifulSoup(html, "html.parser")
    # 해당 사이트의 h1은 사이트명이고 게시물 제목은 h2에 있다.
    heading = soup.find("h2") or soup.find(["h1", "h3"], string=re.compile(r"\S"))
    title = clean_text(heading.get_text(" ")) if heading else base.title_raw
    records: list[SourceRecord] = []
    for link in soup.find_all("a", href=True):
        href = urljoin(page_url, link["href"])
        if "mode=D" not in href:
            continue
        filename = clean_text(link.get_text(" ")) or None
        file_id = query_value(href, "file_id") or str(len(records))
        records.append(
            replace(
                base,
                source_record_id=f"{base.source_record_id}:file:{file_id}",
                title_raw=title,
                title_normalized=normalize_title(title),
                effective_date=extract_effective_date(title, base.effective_date),
                source_page_url=page_url,
                attachment_url=href,
                attachment_filename=filename,
                attachment_role=attachment_role(filename),
            )
        )
    return records or [replace(base, title_raw=title, title_normalized=normalize_title(title))]


def deduplicate(records: Iterable[SourceRecord]) -> list[SourceRecord]:
    seen: set[tuple[str, str, str | None]] = set()
    result: list[SourceRecord] = []
    for record in records:
        key = (record.source_id, record.source_record_id, record.attachment_url)
        if key not in seen:
            seen.add(key)
            result.append(record)
    return result


class OfficialSourceCrawler:
    def __init__(self, config: dict[str, Any], client: HttpClient) -> None:
        self.config = config
        self.client = client

    def crawl(self, source: dict[str, Any]) -> list[SourceRecord]:
        kind = source["kind"]
        handler = getattr(self, f"_crawl_{kind}", None)
        if not handler:
            raise ValueError(f"unsupported source kind: {kind}")
        return deduplicate(handler(source))

    def _crawl_ut_regulations(self, source: dict[str, Any]) -> list[SourceRecord]:
        output: list[SourceRecord] = []
        seen_registers: set[str] = set()
        max_pages = int(source.get("max_pages", 20))
        for category in source["categories"]:
            base_url = source["base_url_template"].format(category=category)
            for page in range(1, max_pages + 1):
                page_url = with_query(base_url, pageIndex=page)
                html, _ = self.client.text(page_url)
                listings = parse_ut_regulations_list(html, page_url, source["source_id"])
                listings = [row for row in listings if row.source_record_id not in seen_registers]
                if not listings:
                    break
                for listing in listings:
                    seen_registers.add(listing.source_record_id)
                    detail_html, _ = self.client.text(listing.source_page_url)
                    history = parse_ut_regulation_history(detail_html, listing.source_page_url)
                    if history and source.get("include_history", True):
                        for history_url, revision_date in history:
                            history_html, _ = self.client.text(history_url)
                            output.extend(
                                parse_ut_regulation_detail(
                                    history_html, history_url, listing, revision_date
                                )
                            )
                    else:
                        output.extend(
                            parse_ut_regulation_detail(
                                detail_html,
                                listing.source_page_url,
                                listing,
                                listing.effective_date,
                            )
                        )
        return output

    def _crawl_ut_guidelines(self, source: dict[str, Any]) -> list[SourceRecord]:
        output: list[SourceRecord] = []
        seen: set[str] = set()
        base_url = source["url"]
        for page in range(1, int(source.get("max_pages", 100)) + 1):
            page_url = with_query(base_url, pageIndex=page)
            html, _ = self.client.text(page_url)
            listings = parse_ut_guidelines_list(html, page_url, source["source_id"])
            listings = [row for row in listings if row.source_record_id not in seen]
            if not listings:
                break
            for listing in listings:
                seen.add(listing.source_record_id)
                if listing.attachment_url:
                    output.append(listing)
                else:
                    detail_html, _ = self.client.text(listing.source_page_url)
                    output.extend(
                        parse_ut_guideline_detail(
                            detail_html, listing.source_page_url, listing
                        )
                    )
        return output

    def _crawl_sanhak_regulations(self, source: dict[str, Any]) -> list[SourceRecord]:
        html, _ = self.client.text(source["url"])
        return parse_sanhak_regulations(html, source["url"], source["source_id"])

    def _crawl_sanhak_guidelines(self, source: dict[str, Any]) -> list[SourceRecord]:
        output: list[SourceRecord] = []
        seen: set[str] = set()
        base_url = source["url"]
        for page in range(1, int(source.get("max_pages", 30)) + 1):
            page_url = with_query(base_url, mode="L", GotoPage=page)
            html, _ = self.client.text(page_url)
            listings = parse_sanhak_guidelines_list(html, page_url, source["source_id"])
            listings = [row for row in listings if row.source_record_id not in seen]
            if not listings:
                break
            for listing in listings:
                seen.add(listing.source_record_id)
                detail_html, _ = self.client.text(listing.source_page_url)
                output.extend(
                    parse_sanhak_guideline_detail(
                        detail_html, listing.source_page_url, listing
                    )
                )
        return output


def download_record(
    client: HttpClient, record: SourceRecord, root: Path
) -> SourceRecord:
    if not record.attachment_url:
        return replace(record, retrieved_at=utc_now())
    target_dir = root / record.source_id / (record.effective_date or "unknown-date")
    target, digest, headers = client.download(record.attachment_url, target_dir)
    return replace(
        record,
        attachment_filename=record.attachment_filename or target.name,
        sha256=digest,
        retrieved_at=utc_now(),
        http_etag=headers.get("ETag"),
        last_modified=headers.get("Last-Modified"),
    )
