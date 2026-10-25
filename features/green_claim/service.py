"""그린 클레임 체크 service. 현재: 일반 PDF 텍스트 추출(feature_spec.md "일반 PDF 텍스트 추출").

- 추출은 별도 프로세스(pdf_worker.run)에서 실행하고, 시간 제한을 넘으면 프로세스를 종료합니다.
- 업로드 내용·추출 문구를 디스크·DB·로그에 남기지 않습니다. 로그에는 오류 code만 남깁니다.
- AI 검수·스캔 PDF OCR·Word·이미지 판독은 아직 없습니다.
"""
import logging
import multiprocessing
import threading
import time

from features.green_claim import pdf_worker

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

# code: (HTTP 상태, 사용자 안내). 안내 문장에 경로·예외 원문·업로드 내용을 넣지 않습니다.
ERRORS = {
    "REQUEST_INVALID": (400, "파일 업로드 요청을 읽지 못했습니다. 페이지를 확인한 뒤 다시 시도해 주세요."),
    "FILE_MISSING": (400, "PDF 파일을 선택해 주세요."),
    "FILE_MULTIPLE": (400, "PDF 파일은 한 번에 1개만 올릴 수 있습니다."),
    "FILE_EMPTY": (400, "빈 파일입니다. 내용이 있는 PDF를 선택해 주세요."),
    "FILE_TOO_LARGE": (413, "파일이 10,000,000바이트(약 10MB)를 넘습니다. 문서를 나누거나 용량을 줄여 주세요."),
    "FILE_TYPE_UNSUPPORTED": (415, "현재는 PDF(.pdf) 파일만 지원합니다. Word·이미지 파일은 준비 중입니다."),
    "PDF_INVALID": (422, "PDF 파일 형식이 아닙니다. 확장자만 .pdf인 파일일 수 있습니다."),
    "PDF_DAMAGED": (422, "PDF를 읽지 못했습니다. 파일이 손상되었을 수 있습니다."),
    "PDF_ENCRYPTED": (422, "암호가 걸린 PDF는 지원하지 않습니다. 암호를 해제한 PDF로 다시 시도해 주세요."),
    "PDF_NO_PAGES": (422, "페이지가 없는 PDF입니다."),
    "PDF_TOO_MANY_PAGES": (422, "PDF는 20페이지까지 처리할 수 있습니다. 문서를 나눠 주세요."),
    "PDF_NO_TEXT": (422, "이 PDF에서는 텍스트를 추출하지 못했습니다. 이미지로 된 문서일 수 있으며, "
                         "스캔 PDF 글자 인식(OCR)은 아직 준비 중입니다. 문구를 직접 입력해 주세요."),
    "TEXT_TOO_LONG": (422, "추출한 문구가 20,000자를 넘습니다. 문구를 자르지 않았습니다. "
                           "문서를 나누거나 분량을 줄여 다시 시도해 주세요."),
    "EXTRACT_TIMEOUT": (504, "글자 추출이 30초 안에 끝나지 않아 중단했습니다. 페이지 수를 줄여 다시 시도해 주세요."),
    "EXTRACT_BUSY": (429, "다른 추출 작업이 진행 중입니다. 잠시 후 다시 시도해 주세요."),
    "EXTRACT_FAILED": (500, "글자 추출 중 문제가 생겼습니다. 다시 시도해 주세요."),
}

NOTICE_TEXT_ONLY = "PDF 안의 텍스트 정보만 읽었습니다. 텍스트가 나온 페이지에도 이미지 속 문구는 빠졌을 수 있습니다."
NOTICE_ORDER = "표·다단 배치 문서는 읽는 순서가 원본과 다를 수 있습니다. 원본과 비교해 확인해 주세요."
NOTICE_MISSING = ("텍스트를 추출하지 못한 페이지가 있습니다. 이미지로만 된 페이지일 수 있으나 단정할 수 없으며, "
                  "스캔 PDF 글자 인식(OCR)은 준비 중입니다. 필요한 문구는 직접 추가해 주세요.")

_slots = threading.BoundedSemaphore(MAX_CONCURRENT_EXTRACTIONS)


class ExtractError(Exception):
    def __init__(self, code):
        self.code = code
        self.http_status, self.message = ERRORS[code]
        super().__init__(code)

    def to_dict(self):
        return {"code": self.code, "message": self.message}


def validate_upload(filename, data):
    """확장자와 실제 PDF 헤더를 확인합니다. MIME 형식은 판단에 쓰지 않습니다."""
    if not data:
        raise ExtractError("FILE_EMPTY")
    if len(data) > MAX_FILE_BYTES:
        raise ExtractError("FILE_TOO_LARGE")
    if not (filename or "").lower().endswith(".pdf"):
        raise ExtractError("FILE_TYPE_UNSUPPORTED")
    if PDF_HEADER not in data[:PDF_HEADER_SEARCH_BYTES]:
        raise ExtractError("PDF_INVALID")


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
        logger.warning("PDF 추출 프로세스 종료 확인 실패")


def run_worker(data, timeout=EXTRACT_TIMEOUT_SECONDS):
    """pdf_worker.run을 별도 프로세스에서 실행하고 결과 dict를 돌려줍니다. 제한 시간에는 시작 시간도 포함합니다."""
    if not _slots.acquire(blocking=False):
        raise ExtractError("EXTRACT_BUSY")
    try:
        deadline = time.monotonic() + timeout
        ctx = multiprocessing.get_context("spawn")
        in_recv, in_send = ctx.Pipe(duplex=False)
        out_recv, out_send = ctx.Pipe(duplex=False)
        proc = ctx.Process(target=pdf_worker.run, args=(in_recv, out_send, MAX_PAGES), daemon=True)
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
