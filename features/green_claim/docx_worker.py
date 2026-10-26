"""Word(.docx) 텍스트 추출 작업. service.py가 별도 프로세스(multiprocessing spawn)에서 run()을 실행합니다.

- ZIP 검사(항목 수·선언 크기·실제 압축 해제 크기)부터 추출까지 모두 이 프로세스에서 하므로 시간 제한을 받습니다.
- ZIP을 디스크에 풀지 않고, XML은 외부 엔티티를 확장하지 않는 파서로만 읽습니다. 외부 링크·포함 개체를 가져오거나 실행하지 않습니다.
- 본문 문단·표를 문서 순서대로 읽습니다. 줄바꿈 정규화와 구분 문자 외에 문구를 바꾸지 않습니다.
- 업로드 내용·추출 문구를 디스크·로그에 남기지 않습니다.
"""
import io
import re
import zipfile

BLOCK_SEPARATOR = "\n\n"
ROW_SEPARATOR = "\n"
CELL_SEPARATOR = " | "
READ_CHUNK = 64 * 1024

CT_DOCX_MAIN = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
CT_UNSUPPORTED_MAIN = {
    "application/vnd.ms-word.document.macroEnabled.main+xml",           # .docm
    "application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml",  # .dotx
    "application/vnd.ms-word.template.macroEnabledTemplate.main+xml",  # .dotm
}
NS = {
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "v": "urn:schemas-microsoft-com:vml",
    "dgm": "http://schemas.openxmlformats.org/drawingml/2006/diagram",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}

# 본문에서 감지할 미지원 요소: (code, 화면 안내, XPath)
BODY_CHECKS = [
    ("text_boxes", "텍스트 상자·도형 안 글자", ".//w:txbxContent | .//v:textbox"),
    ("smartart", "SmartArt", ".//dgm:relIds"),
    ("images", "이미지·그림(이미지 속 글자)", ".//w:drawing | .//w:pict"),
    ("comments", "메모(주석)", ".//w:commentReference"),
    ("notes", "각주·미주", ".//w:footnoteReference | .//w:endnoteReference"),
    ("tracked_changes", "변경 추적 내용", ".//w:ins | .//w:del | .//w:moveFrom | .//w:moveTo"),
    ("content_controls", "콘텐츠 컨트롤 안 글자", ".//w:sdt"),
    ("wrapped_text", "필드·스마트 태그 등 감싸인 영역 안 글자", ".//w:fldSimple | .//w:smartTag | .//w:customXml"),
    ("embedded_objects", "포함된 개체·외부 콘텐츠 조각", ".//w:object | .//w:altChunk"),
    ("equations", "수식", ".//m:oMath"),
]
HEADER_FOOTER_PART = re.compile(r"^word/(header|footer)\d*\.xml$")


class _Fail(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _normalize(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _xml_parser():
    from lxml import etree

    return etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)


def _check_zip(zf, max_entries, max_uncompressed):
    """항목 수·선언 크기를 보고, 모든 항목을 실제로 압축 해제하며 크기를 셉니다(헤더 값만 믿지 않음)."""
    infos = zf.infolist()
    if len(infos) > max_entries:
        raise _Fail("DOCX_ZIP_TOO_MANY_ENTRIES")
    if sum(info.file_size for info in infos) > max_uncompressed:
        raise _Fail("DOCX_ZIP_TOO_LARGE")
    total = 0
    for info in infos:
        if info.flag_bits & 0x1:  # ZIP 항목 암호화(Word 문서 암호화와 다름)
            raise _Fail("DOCX_DAMAGED")
        with zf.open(info) as stream:
            while True:
                chunk = stream.read(READ_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_uncompressed:
                    raise _Fail("DOCX_ZIP_TOO_LARGE")


def _check_main_part(zf):
    """[Content_Types].xml로 주 문서가 일반 Word 문서인지 확인합니다."""
    from lxml import etree

    if "[Content_Types].xml" not in zf.namelist():
        raise _Fail("DOCX_INVALID")
    root = etree.fromstring(zf.read("[Content_Types].xml"), parser=_xml_parser())
    types = {el.get("ContentType") for el in root.findall("ct:Override", NS) + root.findall("ct:Default", NS)}
    if types & CT_UNSUPPORTED_MAIN:
        raise _Fail("DOCX_UNSUPPORTED_FORMAT")
    if CT_DOCX_MAIN not in types:
        raise _Fail("DOCX_INVALID")


def _detect_unsupported(zf, body):
    """알려진 미지원 요소를 감지합니다. 모든 누락을 찾는다고 보장하지 않습니다."""
    from lxml import etree

    found = []
    for name in zf.namelist():
        if HEADER_FOOTER_PART.match(name):
            part = etree.fromstring(zf.read(name), parser=_xml_parser())
            if any((t.text or "").strip() for t in part.iterfind(".//w:t", NS)):
                found.append({"code": "headers_footers", "label": "머리글·바닥글"})
                break
    # python-docx 요소의 xpath()는 자체 네임스페이스만 받으므로 lxml XPath로 직접 평가합니다.
    for code, label, xpath in BODY_CHECKS:
        if etree.XPath(xpath, namespaces=NS)(body):
            found.append({"code": code, "label": label})
    return found


class _Writer:
    """문구를 이어 쓰면서 코드 포인트 위치를 셉니다(Python str 길이 = 코드 포인트 수)."""

    def __init__(self):
        self.parts = []
        self.pos = 0

    def add(self, text):
        self.parts.append(text)
        self.pos += len(text)

    def text(self):
        return "".join(self.parts)


class _Extractor:
    def __init__(self):
        self.nested_tables = 0

    def table(self, table, out, top_level):
        from docx.table import _Cell

        rows = []
        for r_index, tr in enumerate(table._tbl.tr_lst, start=1):
            if r_index > 1:
                out.add(ROW_SEPARATOR)
            row_start = out.pos
            cells = []
            # row.cells는 병합 셀을 반복해서 돌려주므로 실제 셀 요소(tc)를 한 번씩만 읽습니다.
            for c_index, tc in enumerate(tr.tc_lst, start=1):
                if c_index > 1:
                    out.add(CELL_SEPARATOR)
                cell_start = out.pos
                continued = tc.vMerge == "continue"
                if not continued:
                    self.cell(_Cell(tc, table), out)
                cells.append({"cell": c_index, "char_start": cell_start, "char_end": out.pos,
                              "merged_continue": continued})
            rows.append({"row": r_index, "char_start": row_start, "char_end": out.pos, "cells": cells})
        return rows if top_level else None

    def cell(self, cell, out):
        from docx.text.paragraph import Paragraph

        for index, item in enumerate(cell.iter_inner_content()):
            if index:
                out.add("\n")
            if isinstance(item, Paragraph):
                out.add(_normalize(item.text))
            else:
                self.nested_tables += 1
                self.table(item, out, top_level=False)


def _shift(ranges, base):
    for row in ranges:
        row["char_start"] += base
        row["char_end"] += base
        for cell in row["cells"]:
            cell["char_start"] += base
            cell["char_end"] += base


def extract(data, limits):
    """DOCX bytes → 문서 순서의 본문 텍스트와 블록 범위.

    성공: {"status": "ok", ...}  실패: {"status": "error", "code": str}
    """
    import docx
    from docx.text.paragraph import Paragraph

    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, zipfile.LargeZipFile, ValueError, OSError):
        return {"status": "error", "code": "DOCX_DAMAGED"}
    try:
        with zf:
            _check_zip(zf, limits["max_zip_entries"], limits["max_uncompressed_bytes"])
            _check_main_part(zf)
            document = docx.Document(io.BytesIO(data))
            detected = _detect_unsupported(zf, document.element.body)
    except _Fail as fail:
        return {"status": "error", "code": fail.code}
    except Exception:
        # 손상된 ZIP·XML은 zipfile·lxml·python-docx에서 다양한 예외를 냅니다. 원문을 옮기지 않습니다.
        return {"status": "error", "code": "DOCX_DAMAGED"}

    extractor = _Extractor()
    out = _Writer()
    blocks = []
    counts = {"block": 0, "paragraph": 0, "table": 0, "empty": 0}
    for item in document.iter_inner_content():
        counts["block"] += 1
        local = _Writer()
        if isinstance(item, Paragraph):
            counts["paragraph"] += 1
            kind, number = "paragraph", counts["paragraph"]
            local.add(_normalize(item.text))
            rows = None
        else:
            counts["table"] += 1
            kind, number = "table", counts["table"]
            rows = extractor.table(item, local, top_level=True)
        text = local.text()
        if text.strip() == "":
            counts["empty"] += 1
            continue
        if out.pos:
            out.add(BLOCK_SEPARATOR)
        base = out.pos
        out.add(text)
        block = {"block": counts["block"], "type": kind, "number": number,
                 "char_start": base, "char_end": out.pos}
        if rows is not None:
            _shift(rows, base)
            block["rows"] = rows
        blocks.append(block)
        if out.pos > limits["max_chars"]:
            return {"status": "error", "code": "TEXT_TOO_LONG"}  # 큰 결과를 보내지 않고 바로 중단

    if not blocks:
        return {"status": "error", "code": "DOCX_NO_TEXT"}
    return {
        "status": "ok",
        "text": out.text(),
        "blocks": blocks,
        "block_count": counts["block"],
        "paragraph_count": counts["paragraph"],
        "table_count": counts["table"],
        "empty_block_count": counts["empty"],
        "nested_table_count": extractor.nested_tables,
        "detected_unsupported": detected,
    }


def run(in_conn, out_conn, limits):
    """프로세스 진입점. in_conn으로 DOCX bytes를 받고 out_conn으로 결과 dict를 보냅니다."""
    try:
        result = extract(in_conn.recv_bytes(), limits)
    except Exception:
        result = {"status": "error", "code": "EXTRACT_FAILED"}
    try:
        out_conn.send(result)
    except OSError:
        pass  # 시간 초과로 부모가 연결을 닫은 경우. 부모가 이 프로세스를 종료합니다.
    finally:
        in_conn.close()
        out_conn.close()
