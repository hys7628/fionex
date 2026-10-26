"""AI 글자 판독(feature_spec.md "스캔 PDF AI 글자 판독", "홍보 이미지 AI 글자 판독").

- 공통 연결 common.ai_client.generate_structured_from_pdf를 그대로 씁니다. 모델·timeout·재시도·출력 상한은 공통 설정.
- 공통 AI 연결은 openai·pydantic이 필요하므로 판독 요청 때만 불러옵니다. 없으면 AI_DEPENDENCY_MISSING.
- 모델이 돌려준 페이지 번호를 서버가 확인한 페이지 수로 검증하고, 문구를 자르거나 고치지 않습니다.
- 이미지(JPG·JPEG·PNG)는 공통 연결에 이미지 입력 함수가 없어, image_worker(Pillow, 별도 프로세스·30초)가 검사·디코딩해
  메타데이터 없는 판독용 PNG 사본을 만들고, image_input이 그 사본을 1페이지 PDF에 담아 같은 공통 PDF 함수로 보냅니다.
  원본 파일은 보내지 않습니다. 응답에는 이미지 정보만 넣고 페이지 수를 만들지 않습니다.
- 자동 재시도·다른 모델 전환·분할 호출을 하지 않습니다.
- 파일·판독 결과·AI 응답을 디스크·DB·로그에 남기지 않습니다. 로그에는 오류 code만 남깁니다.
"""
import logging
import threading
from pathlib import Path

from common import config
from common.errors import PdfTooLargeError, PdfValidationError
from common.pdf_utils import inspect_pdf
from features.green_claim import image_input, image_worker, service
from features.green_claim.service import ExtractError

logger = logging.getLogger(__name__)

PROMPT_VERSION = "pdf_ocr_v1"
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / f"{PROMPT_VERSION}.md"
IMAGE_PROMPT_VERSION = "image_ocr_v1"
IMAGE_PROMPT_PATH = PROMPT_PATH.with_name(f"{IMAGE_PROMPT_VERSION}.md")
UNREADABLE_MARK = "[판독 불가]"
PAGE_SEPARATOR = "\n\n"
MAX_CONCURRENT_OCR = 1

NOTICES = [
    "AI가 PDF를 보고 옮긴 판독 결과입니다. 원본과 비교해 빠지거나 잘못 읽힌 부분을 고쳐 주세요.",
    "작은 글자·흐린 인쇄·복잡한 표·다단 배치·장식 글꼴에서는 오류가 생길 수 있으며, 모든 누락이나 오류를 자동으로 찾지 못합니다.",
    f"{UNREADABLE_MARK}는 AI가 읽지 못했다고 표시한 자리입니다. 불확실 구간·판독 한계는 모델이 스스로 보고한 내용이며 측정한 정확도가 아닙니다.",
    "판독 완료는 그린워싱 검수 완료가 아닙니다.",
]

IMAGE_NOTICES = [
    "AI가 이미지를 보고 옮긴 판독 결과입니다. 원본 이미지와 비교해 빠지거나 잘못 읽힌 부분을 고쳐 주세요.",
    "작은 글자·흐린 사진·기울어진 촬영·복잡한 배치·장식 글꼴·배경과 대비가 낮은 글자에서는 오류가 생길 수 있으며, "
    "모든 누락이나 오류를 자동으로 찾지 못합니다.",
    f"{UNREADABLE_MARK}는 AI가 읽지 못했다고 표시한 자리입니다. 불확실 구간·판독 한계는 모델이 스스로 보고한 내용이며 측정한 정확도가 아닙니다.",
    "글자만 옮겼으며 디자인·색상·그림·로고는 평가하지 않았습니다. 판독 완료는 그린워싱 검수 완료가 아닙니다.",
]
NOTICE_METADATA = ("원본 파일 대신 판독용 사본을 보냈습니다. 사본에는 촬영 정보·위치(EXIF·GPS)·XMP·주석 등 파일 메타데이터를 넣지 않았습니다. "
                   "이미지에 보이는 글자·사람·개인정보는 지우지 않으므로 그대로 전송됩니다.")
NOTICE_ORIENTATION = "사진에 저장된 방향 정보(EXIF)에 맞춰 판독용 사본의 방향을 돌렸습니다. 원본 파일은 바뀌지 않습니다."
NOTICE_TRANSPARENCY = ("투명한 부분을 흰색 배경으로 채운 판독용 사본을 보냈습니다. 흰색·밝은 글자가 투명 배경 위에 있었다면 "
                       "배경과 구별되지 않아 판독에서 빠질 수 있습니다. 원본과 비교해 확인해 주세요.")
# 로컬 검사·변환 작업 프로세스 오류 → 이미지 안내 코드(일반 추출 문구가 나오지 않도록)
_WORKER_CODES = {"EXTRACT_TIMEOUT": "IMAGE_PREPARE_TIMEOUT", "EXTRACT_FAILED": "IMAGE_CONVERT_FAILED"}

_ai_slots = threading.BoundedSemaphore(MAX_CONCURRENT_OCR)


def load_instructions(path=PROMPT_PATH):
    """서비스 판독 프롬프트(파일 전체를 instructions로 보냄). 체크아웃 줄바꿈과 관계없이 같은 내용을 보내도록 LF로 맞춤."""
    return _normalize(path.read_text(encoding="utf-8"))


def _load_ai(schema_name="OcrResult"):
    """공통 PDF 판독 함수와 결과 스키마(ocr_schema의 클래스 이름)를 불러옵니다. 의존 패키지가 없으면 AI_DEPENDENCY_MISSING."""
    try:
        from common.ai_client import generate_structured_from_pdf
        from features.green_claim import ocr_schema
    except ImportError:
        logger.warning("AI 판독 의존성 없음: code=AI_DEPENDENCY_MISSING")
        raise ExtractError("AI_DEPENDENCY_MISSING") from None
    return generate_structured_from_pdf, getattr(ocr_schema, schema_name)


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
            **_ai_limits(),
        },
    }


def _ai_limits():
    return {"ai_timeout_seconds": config.PDF_TIMEOUT_SECONDS, "ai_max_output_tokens": config.PDF_MAX_OUTPUT_TOKENS}


def _call_once(generate, **kwargs):
    """동시 AI 판독 1건 제한 안에서 공통 함수를 1회 호출합니다(재시도 없음)."""
    if not _ai_slots.acquire(blocking=False):
        raise ExtractError("EXTRACT_BUSY")
    try:
        return generate(**kwargs)
    finally:
        _ai_slots.release()


def run_file_ocr(filename, data):
    """확장자로 PDF·이미지 판독을 나눕니다. 실제 형식은 각 처리에서 다시 확인합니다."""
    if (filename or "").lower().endswith(".pdf"):
        return run_ocr(filename, data)
    if image_input.is_image_name(filename):
        return run_image_ocr(filename, data)
    service._check_size(data)
    raise ExtractError("FILE_TYPE_UNSUPPORTED")


def run_ocr(filename, data):
    """업로드 PDF 검사 → 공통 PDF 판독 1회 호출 → 페이지 검증·결과 조립.

    오류: ExtractError(기능 코드) 또는 common.errors.AIError(공통 코드). 둘 다 to_dict()·http_status 제공.
    """
    service.validate_upload(filename, data)       # .pdf·%PDF-·10,000,000바이트(공통 10 MiB보다 엄격)
    info = inspect_pdf(data, max_pages=service.MAX_PAGES)  # 서버가 확인한 페이지 수, 구조·암호화 검사
    generate, schema = _load_ai()
    result = _call_once(
        generate,
        instructions=load_instructions(),
        pdf_bytes=data,
        schema=schema,
        input_text=f"서버가 확인한 이 PDF의 페이지 수: {info.page_count}",
    )
    pages = [page.model_dump() for page in result.data.pages]
    try:
        return build_ocr_result(pages, list(result.data.limitations), result.pdf.page_count, result.model)
    except ExtractError as err:
        logger.warning("AI 판독 결과 거부: code=%s", err.code)
        raise


def image_limits(expected):
    """image_worker에 넘기는 제한. 사본 PNG 상한은 공통 PDF 상한(10 MiB)이며 PDF 크기는 공통 검사에서 다시 확인합니다."""
    return {
        "expected": expected,
        "max_width": image_input.MAX_WIDTH,
        "max_height": image_input.MAX_HEIGHT,
        "max_pixels": image_input.MAX_PIXELS,
        "max_sent_bytes": config.PDF_MAX_BYTES,
    }


def prepare_image(filename, data, timeout=service.EXTRACT_TIMEOUT_SECONDS):
    """업로드 이미지 → (판독용 PNG 사본, 이미지 정보). Pillow 검사·변환은 시간 제한이 있는 별도 프로세스에서 합니다."""
    expected = image_input.check_upload(filename, data)
    try:
        raw = service.run_worker(data, timeout, target=image_worker.run, options=image_limits(expected))
    except ExtractError as err:
        code = _WORKER_CODES.get(err.code, err.code)
        logger.warning("이미지 검사·변환 실패: code=%s", code)
        raise ExtractError(code) from None
    if raw.get("status") != "ok":
        code = raw.get("code") if raw.get("code") in service.ERRORS else "IMAGE_CONVERT_FAILED"
        if code in ("IMAGE_CONVERT_FAILED", "IMAGE_DEPENDENCY_MISSING"):
            logger.warning("이미지 검사·변환 실패: code=%s", code)
        raise ExtractError(code)
    return raw["png"], raw["image"]


def build_image_result(text, uncertain, limitations, image, model):
    """이미지 판독 결과를 검사하고 화면 응답을 만듭니다. 문구를 자르거나 고치지 않습니다(CRLF·CR→LF만)."""
    text = _normalize(text or "")
    if text.strip() == "":
        raise ExtractError("OCR_NO_TEXT")
    if len(text) > service.MAX_CHARS:
        raise ExtractError("TEXT_TOO_LONG")
    uncertain = [_normalize(note) for note in uncertain]
    notices = list(IMAGE_NOTICES) + [NOTICE_METADATA]
    if image["orientation_applied"]:
        notices.append(NOTICE_ORIENTATION)
    if image["transparency_flattened"]:
        notices.append(NOTICE_TRANSPARENCY)
    return {
        "format": "image",
        "source": "ai_ocr",
        "image": dict(image),
        "text": text,
        "char_count": len(text),
        "uncertain": uncertain,
        "uncertain_count": len(uncertain),
        "unreadable_mark_count": text.count(UNREADABLE_MARK),
        "model_limitations": [_normalize(note) for note in limitations],
        "model": model,
        "prompt_version": IMAGE_PROMPT_VERSION,
        "notices": notices,
        "limits": {
            "max_bytes": service.MAX_FILE_BYTES,
            "max_width": image_input.MAX_WIDTH,
            "max_height": image_input.MAX_HEIGHT,
            "max_pixels": image_input.MAX_PIXELS,
            "max_chars": service.MAX_CHARS,
            "local_timeout_seconds": service.EXTRACT_TIMEOUT_SECONDS,
            "max_sent_bytes": config.PDF_MAX_BYTES,
            **_ai_limits(),
        },
    }


def run_image_ocr(filename, data):
    """업로드 이미지 검사·판독용 사본(별도 프로세스) → 사본을 담은 1페이지 PDF → 공통 PDF 판독 1회 호출 → 결과 조립.

    오류: ExtractError(기능 코드) 또는 common.errors.AIError(공통 코드). 사본 PDF가 공통 PDF 크기 상한을 넘으면
    IMAGE_CONVERTED_TOO_LARGE, 그 밖의 공통 PDF 검사 실패는 IMAGE_CONVERT_FAILED로 알립니다(PDF 오류로 표시하지 않음).
    """
    png, image = prepare_image(filename, data)
    pdf = image_input.build_pdf(png)
    del png
    try:
        inspect_pdf(pdf)
        generate, schema = _load_ai("ImageOcrResult")
        result = _call_once(generate, instructions=load_instructions(IMAGE_PROMPT_PATH), pdf_bytes=pdf, schema=schema)
    except PdfTooLargeError:
        logger.warning("이미지 판독용 PDF 크기 초과: code=IMAGE_CONVERTED_TOO_LARGE")
        raise ExtractError("IMAGE_CONVERTED_TOO_LARGE") from None
    except PdfValidationError as err:
        logger.warning("이미지 판독용 PDF 검사 실패: code=%s", err.code)
        raise ExtractError("IMAGE_CONVERT_FAILED") from None
    try:
        return build_image_result(result.data.text, list(result.data.uncertain), list(result.data.limitations),
                                  image, result.model)
    except ExtractError as err:
        logger.warning("AI 이미지 판독 결과 거부: code=%s", err.code)
        raise
