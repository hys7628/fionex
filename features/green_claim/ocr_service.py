"""스캔 PDF AI 글자 판독(feature_spec.md "스캔 PDF AI 글자 판독").

- 공통 연결 common.ai_client.generate_structured_from_pdf를 그대로 씁니다. 모델·timeout·재시도·출력 상한은 공통 설정.
- 공통 AI 연결은 openai·pydantic이 필요하므로 판독 요청 때만 불러옵니다. 없으면 AI_DEPENDENCY_MISSING.
- 모델이 돌려준 페이지 번호를 서버가 확인한 페이지 수로 검증하고, 문구를 자르거나 고치지 않습니다.
- 자동 재시도·다른 모델 전환·분할 호출을 하지 않습니다.
- 파일·판독 결과·AI 응답을 디스크·DB·로그에 남기지 않습니다. 로그에는 오류 code만 남깁니다.
"""
import logging
import threading
from pathlib import Path

from common import config
from common.pdf_utils import inspect_pdf
from features.green_claim import service
from features.green_claim.service import ExtractError

logger = logging.getLogger(__name__)

PROMPT_VERSION = "pdf_ocr_v1"
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / f"{PROMPT_VERSION}.md"
UNREADABLE_MARK = "[판독 불가]"
PAGE_SEPARATOR = "\n\n"
MAX_CONCURRENT_OCR = 1

NOTICES = [
    "AI가 PDF를 보고 옮긴 판독 결과입니다. 원본과 비교해 빠지거나 잘못 읽힌 부분을 고쳐 주세요.",
    "작은 글자·흐린 인쇄·복잡한 표·다단 배치·장식 글꼴에서는 오류가 생길 수 있으며, 모든 누락이나 오류를 자동으로 찾지 못합니다.",
    f"{UNREADABLE_MARK}는 AI가 읽지 못했다고 표시한 자리입니다. 불확실 구간·판독 한계는 모델이 스스로 보고한 내용이며 측정한 정확도가 아닙니다.",
    "판독 완료는 그린워싱 검수 완료가 아닙니다.",
]

_ai_slots = threading.BoundedSemaphore(MAX_CONCURRENT_OCR)


def load_instructions():
    """서비스 판독 프롬프트(파일 전체를 instructions로 보냄). 체크아웃 줄바꿈과 관계없이 같은 내용을 보내도록 LF로 맞춤."""
    return _normalize(PROMPT_PATH.read_text(encoding="utf-8"))


def _load_ai():
    """공통 PDF 판독 함수와 결과 스키마를 불러옵니다. 의존 패키지가 없으면 AI_DEPENDENCY_MISSING."""
    try:
        from common.ai_client import generate_structured_from_pdf
        from features.green_claim.ocr_schema import OcrResult
    except ImportError:
        logger.warning("AI 판독 의존성 없음: code=AI_DEPENDENCY_MISSING")
        raise ExtractError("AI_DEPENDENCY_MISSING") from None
    return generate_structured_from_pdf, OcrResult


def _normalize(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def build_ocr_result(pages, limitations, page_count, model):
    """모델 결과(page·text·uncertain dict 목록)를 검증하고 화면 응답을 만듭니다. 문구를 자르거나 고치지 않습니다."""
    numbers = [p.get("page") for p in pages]
    valid = all(isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= page_count for n in numbers)
    if not valid or len(set(numbers)) != len(numbers) or set(numbers) != set(range(1, page_count + 1)):
        raise ExtractError("OCR_PAGE_MISMATCH")

    parts = []
    out_pages = []
    position = 0
    for item in sorted(pages, key=lambda p: p["page"]):
        text = _normalize(item.get("text") or "")
        uncertain = [_normalize(note) for note in item.get("uncertain") or []]
        if text.strip() == "":
            out_pages.append({"page": item["page"], "status": "no_text", "char_start": None, "char_end": None,
                              "uncertain": uncertain})
            continue
        if parts:
            position += len(PAGE_SEPARATOR)
        start = position
        position += len(text)
        parts.append(text)
        out_pages.append({"page": item["page"], "status": "text", "char_start": start, "char_end": position,
                          "uncertain": uncertain})

    if not parts:
        raise ExtractError("OCR_NO_TEXT")
    joined = PAGE_SEPARATOR.join(parts)
    if len(joined) > service.MAX_CHARS:
        raise ExtractError("TEXT_TOO_LONG")

    return {
        "format": "pdf",
        "source": "ai_ocr",
        "text": joined,
        "char_count": len(joined),
        "page_count": page_count,
        "pages": out_pages,
        "pages_without_text": [p["page"] for p in out_pages if p["status"] != "text"],
        "uncertain_count": sum(len(p["uncertain"]) for p in out_pages),
        "unreadable_mark_count": joined.count(UNREADABLE_MARK),
        "model_limitations": [_normalize(note) for note in limitations],
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "notices": list(NOTICES),
        "limits": {
            "max_bytes": service.MAX_FILE_BYTES,
            "max_pages": service.MAX_PAGES,
            "max_chars": service.MAX_CHARS,
            "ai_timeout_seconds": config.PDF_TIMEOUT_SECONDS,
            "ai_max_output_tokens": config.PDF_MAX_OUTPUT_TOKENS,
        },
    }


def run_ocr(filename, data):
    """업로드 PDF 검사 → 공통 PDF 판독 1회 호출 → 페이지 검증·결과 조립.

    오류: ExtractError(기능 코드) 또는 common.errors.AIError(공통 코드). 둘 다 to_dict()·http_status 제공.
    """
    service.validate_upload(filename, data)       # .pdf·%PDF-·10,000,000바이트(공통 10 MiB보다 엄격)
    info = inspect_pdf(data, max_pages=service.MAX_PAGES)  # 서버가 확인한 페이지 수, 구조·암호화 검사
    generate, schema = _load_ai()
    if not _ai_slots.acquire(blocking=False):
        raise ExtractError("EXTRACT_BUSY")
    try:
        result = generate(
            instructions=load_instructions(),
            pdf_bytes=data,
            schema=schema,
            input_text=f"서버가 확인한 이 PDF의 페이지 수: {info.page_count}",
        )
    finally:
        _ai_slots.release()
    pages = [page.model_dump() for page in result.data.pages]
    try:
        return build_ocr_result(pages, list(result.data.limitations), result.pdf.page_count, result.model)
    except ExtractError as err:
        logger.warning("AI 판독 결과 거부: code=%s", err.code)
        raise
