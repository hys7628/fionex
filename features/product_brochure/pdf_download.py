"""제품소개서 카탈로그 PDF 다운로드: 요청 최상위 검사, 기능 전용 동시 렌더링 제한, 응답 헤더.

catalog 내부 형식·문구 검증과 렌더링은 pdf_catalog.parse_catalog/build_pdf를 그대로 씁니다(중복 스키마 없음).
OpenAI 재호출·업로드 원본 재분석·디스크 저장·이력 저장을 하지 않습니다.

동시 실행 제한은 이 프로세스 안에서만 적용됩니다(여러 워커·서버 전체의 전역 제한이 아님).
대기열 없이 자리가 없으면 즉시 429로 거부하고, 렌더링 시간 강제 제한은 두지 않습니다.
"""
import threading

from common.errors import AIInputError
from features.product_brochure import pdf_catalog

MAX_REQUEST_BYTES = 32 * 1024
MAX_CONCURRENT_RENDERS = 2
DOWNLOAD_NAME = "fionex_catalog_pt-BR.pdf"  # 고정 ASCII 파일명(사용자 입력을 쓰지 않음)
RESPONSE_HEADERS = {
    "Content-Disposition": f'attachment; filename="{DOWNLOAD_NAME}"',
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
}

_slots = threading.BoundedSemaphore(MAX_CONCURRENT_RENDERS)


class PdfDownloadInvalidJsonError(AIInputError):
    code = "BROCHURE_PDF_INVALID_JSON"
    message = "JSON 형식(application/json)의 요청 본문이 필요합니다."


class PdfDownloadTooLargeError(AIInputError):
    code = "BROCHURE_PDF_REQUEST_TOO_LARGE"
    message = "요청 크기가 허용 범위를 넘습니다."
    http_status = 413


class PdfDownloadBusyError(AIInputError):
    code = "BROCHURE_PDF_BUSY"
    message = "PDF를 만드는 요청이 많습니다. 잠시 후 다시 시도하세요."
    http_status = 429
    retryable = True


def parse_request(payload):
    """최상위는 {"catalog": {...}}만 허용합니다. catalog 내부 검사는 렌더러의 parse_catalog가 맡습니다."""
    if payload is None:
        raise PdfDownloadInvalidJsonError()
    if not isinstance(payload, dict) or set(payload) != {"catalog"} or not isinstance(payload["catalog"], dict):
        raise pdf_catalog.CatalogPdfInputError()
    return payload["catalog"]


def render(payload):
    """검증 → (자리가 있으면) 렌더링 → PDF bytes. 자리가 없으면 렌더러를 실행하지 않고 429.
    형식 오류는 슬롯을 잡기 전에 걸러 렌더러·슬롯을 쓰지 않습니다."""
    catalog = parse_request(payload)
    pdf_catalog.parse_catalog(catalog)  # 빠른 형식 검사(실패 시 슬롯 미사용). build_pdf도 다시 검사함
    if not _slots.acquire(blocking=False):
        raise PdfDownloadBusyError()
    try:
        return pdf_catalog.build_pdf(catalog)
    finally:
        _slots.release()
