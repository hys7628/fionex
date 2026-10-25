"""그린 클레임 체크 service. 현재: 일반 PDF·Word(.docx) 텍스트 추출(feature_spec.md).

- 추출은 별도 프로세스(pdf_worker.run, docx_worker.run)에서 실행하고, 시간 제한을 넘으면 프로세스를 종료합니다.
- 업로드 내용·추출 문구를 디스크·DB·로그에 남기지 않습니다. 로그에는 오류 code만 남깁니다.
- AI 검수·스캔 PDF OCR·이미지 판독은 아직 없습니다.
"""
import logging
import multiprocessing
import threading
import time

from features.green_claim import docx_worker, pdf_worker

logger = logging.getLogger(__name__)

# 이번 단계 초기값(실측 성능 보장 아님, 추후 조정 가능). feature_spec.md와 같은 값.
MAX_FILE_BYTES = 10_000_000
MAX_PAGES = 20
MAX_CHARS = 20_000
EXTRACT_TIMEOUT_SECONDS = 30.0
MAX_CONCURRENT_EXTRACTIONS = 2
PAGE_SEPARATOR = "\n\n"
PDF_HEADER = b"%PDF-"
PDF_HEADER_SEARCH_BYTES = 1024  # PDF 헤더는 파일 앞 1024바이트 안에 있어야 함
# Word(.docx) 초기 운영 제한(성능·메모리 상한 보장 아님)
MAX_ZIP_ENTRIES = 1_000
MAX_UNCOMPRESSED_BYTES = 50_000_000
ZIP_SIGNATURE = b"PK\x03\x04"
OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # Office 암호화 문서·이전 .doc 등이 쓰는 복합 파일
OLE_ENCRYPTED_PACKAGE = "EncryptedPackage".encode("utf-16-le")

# code: (HTTP 상태, 사용자 안내). 안내 문장에 경로·예외 원문·업로드 내용을 넣지 않습니다.
ERRORS = {
    "REQUEST_INVALID": (400, "파일 업로드 요청을 읽지 못했습니다. 페이지를 확인한 뒤 다시 시도해 주세요."),
    "FILE_MISSING": (400, "PDF 또는 Word(.docx) 파일을 선택해 주세요."),
    "FILE_MULTIPLE": (400, "파일은 한 번에 1개만 올릴 수 있습니다."),
    "FILE_EMPTY": (400, "빈 파일입니다. 내용이 있는 파일을 선택해 주세요."),
    "FILE_TOO_LARGE": (413, "파일이 10,000,000바이트(약 10MB)를 넘습니다. 문서를 나누거나 용량을 줄여 주세요."),
    "FILE_TYPE_UNSUPPORTED": (415, "현재는 일반 PDF(.pdf)와 Word(.docx) 파일만 지원합니다. "
                                   ".doc·.docm 등 다른 형식과 이미지 파일은 지원하지 않습니다."),
    "PDF_INVALID": (422, "PDF 파일 형식이 아닙니다. 확장자만 .pdf인 파일일 수 있습니다."),
    "PDF_DAMAGED": (422, "PDF를 읽지 못했습니다. 파일이 손상되었을 수 있습니다."),
    "PDF_ENCRYPTED": (422, "암호가 걸린 PDF는 지원하지 않습니다. 암호를 해제한 PDF로 다시 시도해 주세요."),
    "PDF_NO_PAGES": (422, "페이지가 없는 PDF입니다."),
    "PDF_TOO_MANY_PAGES": (422, "PDF는 20페이지까지 처리할 수 있습니다. 문서를 나눠 주세요."),
    "PDF_NO_TEXT": (422, "이 PDF에서는 텍스트를 추출하지 못했습니다. 이미지로 된 문서일 수 있으며, "
                         "스캔 PDF 글자 인식(OCR)은 아직 준비 중입니다. 문구를 직접 입력해 주세요."),
    "TEXT_TOO_LONG": (422, "추출한 문구가 20,000자를 넘습니다. 문구를 자르지 않았습니다. "
                           "문서를 나누거나 분량을 줄여 다시 시도해 주세요."),
    "DOCX_INVALID": (422, "Word(.docx) 문서 구조가 아닙니다. 확장자만 .docx인 다른 파일일 수 있습니다."),
    "DOCX_UNSUPPORTED_FORMAT": (415, "지원하지 않는 Word 형식입니다(이전 .doc, 매크로 포함 문서, 서식 파일 등일 수 있습니다). "
                                     "Word에서 .docx 문서로 저장한 뒤 다시 시도해 주세요."),
    "DOCX_DAMAGED": (422, "Word 문서를 읽지 못했습니다. 파일이 손상되었을 수 있습니다."),
    "DOCX_ENCRYPTED": (422, "암호가 걸린 Word 문서는 지원하지 않습니다. 암호를 해제한 문서로 다시 시도해 주세요."),
    "DOCX_ZIP_TOO_MANY_ENTRIES": (422, "Word 문서 내부 구성 항목이 너무 많습니다(최대 1,000개). 문서를 나눠 주세요."),
    "DOCX_ZIP_TOO_LARGE": (422, "Word 문서의 압축을 푼 크기가 너무 큽니다(최대 50,000,000바이트). "
                                "이미지 등을 줄이거나 문서를 나눠 주세요."),
    "DOCX_NO_TEXT": (422, "Word 본문 문단·표에서 텍스트를 추출하지 못했습니다. 이미지·텍스트 상자·머리글 등 "
                          "지원하지 않는 요소에만 글자가 있을 수 있습니다. 문구를 직접 입력해 주세요."),
    "EXTRACT_TIMEOUT": (504, "글자 추출이 30초 안에 끝나지 않아 중단했습니다. 문서 분량을 줄여 다시 시도해 주세요."),
    "EXTRACT_BUSY": (429, "다른 추출 작업이 진행 중입니다. 잠시 후 다시 시도해 주세요."),
    "EXTRACT_FAILED": (500, "글자 추출 중 문제가 생겼습니다. 다시 시도해 주세요."),
}

NOTICE_TEXT_ONLY = "PDF 안의 텍스트 정보만 읽었습니다. 텍스트가 나온 페이지에도 이미지 속 문구는 빠졌을 수 있습니다."
NOTICE_ORDER = "표·다단 배치 문서는 읽는 순서가 원본과 다를 수 있습니다. 원본과 비교해 확인해 주세요."
NOTICE_MISSING = ("텍스트를 추출하지 못한 페이지가 있습니다. 이미지로만 된 페이지일 수 있으나 단정할 수 없으며, "
                  "스캔 PDF 글자 인식(OCR)은 준비 중입니다. 필요한 문구는 직접 추가해 주세요.")

DOCX_NOTICE_SCOPE = "Word 본문의 문단과 표만 문서 순서대로 읽었습니다. 표는 행마다 한 줄, 셀 사이를 ' | '로 구분했습니다."
DOCX_NOTICE_EXCLUDED = ("머리글·바닥글, 텍스트 상자·도형·SmartArt, 삽입 이미지 속 글자, 메모·각주·미주, "
                        "변경 추적 내용은 추출하지 않습니다. 문서에 이런 요소가 있으면 원본과 비교해 필요한 문구를 직접 추가해 주세요.")
DOCX_NOTICE_POSITION = "Word는 페이지 수를 정확히 알 수 없어 위치를 본문 블록(문단·표) 순서로 안내합니다."
DOCX_NOTICE_NESTED = "셀 안의 표(중첩 표)는 같은 구분 기호로 이어 붙여 셀 경계가 모호할 수 있습니다."

_slots = threading.BoundedSemaphore(MAX_CONCURRENT_EXTRACTIONS)


class ExtractError(Exception):
    def __init__(self, code):
        self.code = code
        self.http_status, self.message = ERRORS[code]
        super().__init__(code)

    def to_dict(self):
        return {"code": self.code, "message": self.message}


def _check_size(data):
    if not data:
        raise ExtractError("FILE_EMPTY")
    if len(data) > MAX_FILE_BYTES:
        raise ExtractError("FILE_TOO_LARGE")


def validate_upload(filename, data):
    """확장자와 실제 PDF 헤더를 확인합니다. MIME 형식은 판단에 쓰지 않습니다."""
    _check_size(data)
    if not (filename or "").lower().endswith(".pdf"):
        raise ExtractError("FILE_TYPE_UNSUPPORTED")
    if PDF_HEADER not in data[:PDF_HEADER_SEARCH_BYTES]:
        raise ExtractError("PDF_INVALID")


def validate_docx_upload(filename, data):
    """확장자와 파일 앞부분 서명을 확인합니다. ZIP 내부 검사는 시간 제한이 있는 별도 프로세스에서 합니다."""
    _check_size(data)
    if not (filename or "").lower().endswith(".docx"):
        raise ExtractError("FILE_TYPE_UNSUPPORTED")
    if data.startswith(ZIP_SIGNATURE):
        return
    if data.startswith(OLE_SIGNATURE):
        # Office 암호화 문서는 OLE 복합 파일 안에 EncryptedPackage를 둡니다. 없으면 암호화를 단정하지 않습니다.
        raise ExtractError("DOCX_ENCRYPTED" if OLE_ENCRYPTED_PACKAGE in data else "DOCX_UNSUPPORTED_FORMAT")
    raise ExtractError("DOCX_INVALID")


def _send_bytes(conn, data):
    try:
        conn.send_bytes(data)
    except (OSError, ValueError):
        pass  # 시간 초과로 프로세스를 종료하면 전송이 끊깁니다.
    finally:
        conn.close()


def _stop(proc, wait):
    """프로세스를 회수합니다. wait=False(시간 초과)면 기다리지 않고 terminate → kill 순서로 종료합니다."""
    if wait:
        proc.join(2)
    if proc.is_alive():
        proc.terminate()
        proc.join(3)
    if proc.is_alive():
        proc.kill()
        proc.join(3)
    try:
        proc.close()
    except ValueError:
        logger.warning("추출 프로세스 종료 확인 실패")


def run_worker(data, timeout=EXTRACT_TIMEOUT_SECONDS, target=None, options=None):
    """target(기본 pdf_worker.run)을 별도 프로세스에서 실행하고 결과 dict를 돌려줍니다.

    options는 target의 세 번째 인자(PDF: 최대 페이지 수, Word: 제한 dict). 제한 시간에는 시작 시간도 포함합니다.
    """
    if target is None:
        target, options = pdf_worker.run, MAX_PAGES
    if not _slots.acquire(blocking=False):
        raise ExtractError("EXTRACT_BUSY")
    try:
        deadline = time.monotonic() + timeout
        ctx = multiprocessing.get_context("spawn")
        in_recv, in_send = ctx.Pipe(duplex=False)
        out_recv, out_send = ctx.Pipe(duplex=False)
        proc = ctx.Process(target=target, args=(in_recv, out_send, options), daemon=True)
        proc.start()
        in_recv.close()
        out_send.close()
        # 전송이 막혀도 제한 시간을 지킬 수 있도록 별도 스레드에서 보냅니다.
        sender = threading.Thread(target=_send_bytes, args=(in_send, data), daemon=True)
        sender.start()
        finished = False
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not out_recv.poll(remaining):
                raise ExtractError("EXTRACT_TIMEOUT")
            result = out_recv.recv()
            finished = True
            return result
        except (EOFError, OSError):
            raise ExtractError("EXTRACT_FAILED") from None
        finally:
            _stop(proc, wait=finished)
            out_recv.close()
            sender.join(2)
    finally:
        _slots.release()


def build_result(raw):
    """페이지별 텍스트를 이어 붙이고 페이지 범위·제한을 검사합니다. 문구를 자르거나 고치지 않습니다."""
    if raw.get("status") != "ok":
        raise ExtractError(raw.get("code") if raw.get("code") in ERRORS else "EXTRACT_FAILED")

    parts = []
    pages = []
    position = 0
    for number, text in enumerate(raw["pages"], start=1):
        if text is None:
            pages.append({"page": number, "status": "error", "char_start": None, "char_end": None})
            continue
        if text.strip() == "":
            pages.append({"page": number, "status": "no_text", "char_start": None, "char_end": None})
            continue
        if parts:
            position += len(PAGE_SEPARATOR)
        start = position
        position += len(text)
        parts.append(text)
        pages.append({"page": number, "status": "text", "char_start": start, "char_end": position})

    if not parts:
        all_failed = all(p["status"] == "error" for p in pages)
        raise ExtractError("EXTRACT_FAILED" if all_failed else "PDF_NO_TEXT")

    joined = PAGE_SEPARATOR.join(parts)
    if len(joined) > MAX_CHARS:
        raise ExtractError("TEXT_TOO_LONG")

    missing = [p["page"] for p in pages if p["status"] != "text"]
    notices = [NOTICE_TEXT_ONLY, NOTICE_ORDER]
    if missing:
        notices.append(NOTICE_MISSING)
    return {
        "format": "pdf",
        "text": joined,
        "char_count": len(joined),
        "page_count": raw["page_count"],
        "pages": pages,
        "pages_without_text": missing,
        "all_pages_have_text": not missing,
        "notices": notices,
        "limits": {
            "max_bytes": MAX_FILE_BYTES,
            "max_pages": MAX_PAGES,
            "max_chars": MAX_CHARS,
            "timeout_seconds": EXTRACT_TIMEOUT_SECONDS,
        },
    }


def extract_pdf(filename, data, timeout=EXTRACT_TIMEOUT_SECONDS):
    """업로드 PDF 검사 → 별도 프로세스 추출 → 결과 조립. 실패는 ExtractError."""
    validate_upload(filename, data)
    try:
        return build_result(run_worker(data, timeout))
    except ExtractError as err:
        if err.code in ("EXTRACT_TIMEOUT", "EXTRACT_FAILED", "EXTRACT_BUSY"):
            logger.warning("PDF 추출 실패: code=%s", err.code)
        raise


def docx_limits():
    return {
        "max_bytes": MAX_FILE_BYTES,
        "max_chars": MAX_CHARS,
        "timeout_seconds": EXTRACT_TIMEOUT_SECONDS,
        "max_zip_entries": MAX_ZIP_ENTRIES,
        "max_uncompressed_bytes": MAX_UNCOMPRESSED_BYTES,
    }


def build_docx_result(raw):
    """docx_worker 결과에 글자 수 제한과 안내를 붙입니다. 문구를 자르거나 고치지 않습니다."""
    if raw.get("status") != "ok":
        raise ExtractError(raw.get("code") if raw.get("code") in ERRORS else "EXTRACT_FAILED")
    text = raw["text"]
    if len(text) > MAX_CHARS:
        raise ExtractError("TEXT_TOO_LONG")
    notices = [DOCX_NOTICE_SCOPE, DOCX_NOTICE_EXCLUDED, DOCX_NOTICE_POSITION]
    if raw["nested_table_count"]:
        notices.append(DOCX_NOTICE_NESTED)
    return {
        "format": "docx",
        "text": text,
        "char_count": len(text),
        "block_count": raw["block_count"],
        "paragraph_count": raw["paragraph_count"],
        "table_count": raw["table_count"],
        "blocks": raw["blocks"],
        "empty_block_count": raw["empty_block_count"],
        "nested_table_count": raw["nested_table_count"],
        "detected_unsupported": raw["detected_unsupported"],
        "notices": notices,
        "limits": docx_limits(),
    }


def extract_docx(filename, data, timeout=EXTRACT_TIMEOUT_SECONDS):
    """업로드 Word 검사 → 별도 프로세스(ZIP 검사·추출) → 결과 조립. 실패는 ExtractError."""
    validate_docx_upload(filename, data)
    try:
        return build_docx_result(run_worker(data, timeout, target=docx_worker.run, options=docx_limits()))
    except ExtractError as err:
        if err.code in ("EXTRACT_TIMEOUT", "EXTRACT_FAILED", "EXTRACT_BUSY"):
            logger.warning("Word 추출 실패: code=%s", err.code)
        raise


def extract_file(filename, data, timeout=EXTRACT_TIMEOUT_SECONDS):
    """확장자로 PDF·Word 처리를 나눕니다. 실제 형식은 각 처리에서 다시 확인합니다."""
    name = (filename or "").lower()
    if name.endswith(".docx"):
        return extract_docx(filename, data, timeout)
    if name.endswith(".pdf"):
        return extract_pdf(filename, data, timeout)
    _check_size(data)
    raise ExtractError("FILE_TYPE_UNSUPPORTED")
