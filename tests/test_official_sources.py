from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_official_sources import ManifestIndex
from official_sources import (
    SourceRecord,
    normalize_title,
    parse_sanhak_guideline_detail,
    parse_sanhak_guidelines_list,
    parse_sanhak_regulations,
    parse_ut_guideline_detail,
    parse_ut_guidelines_list,
    parse_ut_regulation_detail,
    parse_ut_regulation_history,
    parse_ut_regulations_list,
)


def test_normalize_title_ignores_institution_and_revision_metadata():
    current = "국립한국교통대학교 산학협력단 부속기관 설치·운영 지침(제669호, 2026.9.1.)"
    previous = "산학협력단 부속기관 설치 운영 지침"
    assert normalize_title(current) == normalize_title(previous)


def test_parse_ut_regulation_list_history_and_attachments():
    listing_html = """
    <table><tbody><tr>
      <td>18</td><td>법인 및 기타단체</td>
      <td>국립한국교통대학교 산학협력단 연구비 감사 규정</td>
      <td>산학협력단</td><td>2026-02-26</td>
      <td><a href="#" onclick="popup('146')">보기</a></td>
    </tr></tbody></table>
    """
    items = parse_ut_regulations_list(
        listing_html,
        "https://www.ut.ac.kr/prog/schoolRegltn/kor/sub05_03_01/SE07/list.do",
    )
    assert len(items) == 1
    assert items[0].source_record_id == "register:146"
    assert items[0].effective_date == "2026-02-26"
    assert items[0].source_page_url.endswith("register=146")

    detail_html = """
    <table><tbody><tr><th>파일</th><td>
      <a href="javascript:fn_egov_downFile('FILE_ABC','0')">제정사유.hwp ( 51 kb)</a>
      <a href="javascript:fn_egov_downFile('FILE_ABC','1')">연구비 감사 규정.hwp ( 76 kb)</a>
    </td></tr></tbody></table>
    <h3>규정히스토리</h3>
    <table><tbody><tr><td>1</td><td>
      <a href="/prog/schoolRegulations/kor/sub05_03_01/list.do?register=146&amp;cntNo=490">규정</a>
    </td><td>2026-02-26</td></tr></tbody></table>
    """
    history = parse_ut_regulation_history(detail_html, items[0].source_page_url)
    assert history[0][0].endswith("register=146&cntNo=490")
    records = parse_ut_regulation_detail(
        detail_html, history[0][0], items[0], history[0][1]
    )
    assert len(records) == 2
    assert records[0].attachment_role == "supporting"
    assert records[1].attachment_role == "document"
    assert "atchFileId=FILE_ABC" in records[1].attachment_url
    assert "fileSn=1" in records[1].attachment_url


def test_parse_ut_guideline_direct_and_detail_attachments():
    list_html = """
    <table><tbody>
      <tr><td>554</td><td>국립한국교통대학교 금고지정심의위원회 운영 지침 일부개정(2026.8.20., 지침 제668호)</td>
      <td>재무과</td><td>2026-08-20</td><td>31</td>
      <td><a href="/cmm/fms/FileDown.do?atchFileId=FILE_1&amp;fileSn=0">파일명 : 금고 지침.hwp</a></td></tr>
      <tr><td>549</td><td>총학생회칙 일부개정(2026.4.1.)</td>
      <td>학생과</td><td>2026-04-08</td><td>800</td>
      <td><a href="/cop/bbs/detail.do?nttId=1121254">상세보기</a></td></tr>
    </tbody></table>
    """
    rows = parse_ut_guidelines_list(list_html, "https://www.ut.ac.kr/list.do")
    assert len(rows) == 2
    assert rows[0].effective_date == "2026-08-20"
    assert rows[0].attachment_filename == "금고 지침.hwp"
    assert rows[1].source_record_id == "1121254"
    assert rows[1].attachment_url is None

    detail_html = """
    <a href="/cmm/fms/FileDown.do?atchFileId=FILE_2&amp;fileSn=0">회칙.hwp</a>
    <a href="/cmm/fms/FileDown.do?atchFileId=FILE_2&amp;fileSn=1">개정 사유서.hwp</a>
    """
    attachments = parse_ut_guideline_detail(
        detail_html, rows[1].source_page_url, rows[1]
    )
    assert len(attachments) == 2
    assert attachments[1].attachment_role == "supporting"


def test_parse_sanhak_regulations():
    html = """
    <table>
      <caption>정관 - 번호, 문서정보, 공포일, 다운로드 정보제공</caption>
      <tbody><tr><td>1</td><td>한국교통대학교 산학협력단 정관</td>
      <td>2024-01-05</td><td><a href="/_prog/download/?file_id=abc">다운로드</a></td></tr></tbody>
    </table>
    """
    rows = parse_sanhak_regulations(html, "https://sanhak.ut.ac.kr/kr/html/sub06/060101.html")
    assert len(rows) == 1
    assert rows[0].source_group == "정관"
    assert rows[0].source_record_id == "abc"
    assert rows[0].effective_date == "2024-01-05"


def test_parse_sanhak_guideline_list_and_detail():
    list_html = """
    <table><tbody><tr>
      <td>85</td><td>정관·운영</td>
      <td><a href="?mode=V&amp;no=record85&amp;GotoPage=1">국립한국교통대학교 산학협력단 부속기관 설치·운영 지침(제669호, 2026.9.1.)</a></td>
      <td>행정지원팀</td><td>2026-08-31</td><td>6</td>
    </tr></tbody></table>
    """
    rows = parse_sanhak_guidelines_list(
        list_html, "https://sanhak.ut.ac.kr/kr/html/sub06/060102.html"
    )
    assert len(rows) == 1
    assert rows[0].source_record_id == "record85"
    assert rows[0].source_group == "정관·운영"
    assert rows[0].department == "행정지원팀"
    assert rows[0].effective_date == "2026-09-01"

    detail_html = """
    <h2>국립한국교통대학교 산학협력단 부속기관 설치·운영 지침(제669호, 2026.9.1.)</h2>
    <a href="?mode=D&amp;no=record85&amp;file_id=2966&amp;category=01">부속기관 설치·운영 지침.hwp</a>
    """
    attachments = parse_sanhak_guideline_detail(
        detail_html, rows[0].source_page_url, rows[0]
    )
    assert len(attachments) == 1
    assert attachments[0].source_record_id.endswith(":file:2966")
    assert attachments[0].attachment_filename.endswith(".hwp")


def test_manifest_comparison_requires_date_or_hash():
    index = ManifestIndex(
        [
            {
                "document_id": "GDL-existing",
                "title": "금고지정심의위원회 운영 지침",
                "revision_date": "2021-06-01",
                "sha256": "a" * 64,
            }
        ]
    )
    record = SourceRecord(
        source_id="ut_guidelines",
        source_record_id="seq:554",
        document_type="guideline",
        source_group="지침",
        title_raw="국립한국교통대학교 금고지정심의위원회 운영 지침 일부개정(2026.8.20., 지침 제668호)",
        title_normalized=normalize_title("금고지정심의위원회 운영 지침"),
        department="재무과",
        posted_date="2026-08-20",
        effective_date="2026-08-20",
        source_page_url="https://example.test/list",
        attachment_url="https://example.test/file.hwp",
    )
    assert index.classify(record) == ("new_version_candidate", ["GDL-existing"])
    assert index.classify(SourceRecord(**{**record.to_dict(), "sha256": "a" * 64}))[0] == "present_hash"
