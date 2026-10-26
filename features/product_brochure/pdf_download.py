"""제품소개서 카탈로그 PDF 다운로드: 요청 최상위 검사, 기능 전용 동시 렌더링 제한, 응답 헤더.

catalog 내부 형식·문구 검증과 렌더링은 pdf_catalog.parse_catalog/build_pdf를 그대로 씁니다(중복 스키마 없음).
기본 배경은 application/json, 사용자가 적용한 AI 표지 배경이 있으면 multipart/form-data(catalog 텍스트 + cover_image 파일)로 받습니다.
OpenAI 재호출·업로드 원본 재분석·결과 영구 저장·이력 저장을 하지 않습니다. 단, multipart 파서(Werkzeug)는 큰 파일 부분을
OS 임시 파일로 받을 수 있으므로 "디스크에 전혀 쓰지 않음"은 아닙니다(라우트가 finally에서 request.close()로 정리).

동시 실행 제한은 이 프로세스 안에서만 적용됩니다(여러 워커·서버 전체의 전역 제한이 아님).
대기열 없이 자리가 없으면 즉시 429로 거부하고, 렌더링 시간 강제 제한은 두지 않습니다.
"""
import io
import json
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


# ---------- AI 표지 배경 포함 요청(multipart/form-data) ----------
# 필드: catalog(텍스트 1개, {"catalog": ...} JSON 문자열) + cover_image(파일 1개, 파일명 cover.png)
CATALOG_FIELD = "catalog"
COVER_FIELD = "cover_image"
COVER_FILENAME = "cover.png"
MAX_COVER_BYTES = 16 * 1024 * 1024                    # 공통 이미지 상한(config.IMAGE_MAX_BYTES)과 같은 값
MAX_MULTIPART_BYTES = MAX_COVER_BYTES + 96 * 1024     # 이미지 + JSON 필드(32 KiB) + multipart 경계·헤더 여유
MAX_FORM_PARTS = 4                                    # 정상 2개. 중복·추가 필드는 형식 오류로 알리기 위해 약간의 여유
COVER_SIZE = (1024, 1536)
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class PdfDownloadInvalidFormError(AIInputError):
    code = "BROCHURE_PDF_INVALID_FORM"
    message = "PDF 요청 형식이 올바르지 않습니다(catalog 필드 1개와 cover_image 파일 1개)."


class PdfCoverTooLargeError(AIInputError):
    code = "BROCHURE_PDF_COVER_TOO_LARGE"
    message = "표지 이미지가 허용 크기(16 MiB)를 넘습니다."
    http_status = 413


class PdfCoverInvalidError(AIInputError):
    code = "BROCHURE_PDF_COVER_INVALID"
    message = "표지 이미지가 1024×1536 단일 프레임 PNG가 아니거나 손상되었습니다."


def read_multipart(form, files):
    """multipart 필드 → ({"catalog": ...} 객체, 이미지 bytes). 누락·중복·예상 밖 필드, 파일명, 크기를 검사합니다.
    이미지 스트림은 상한+1바이트까지만 읽습니다. 사용자 파일명·경로는 쓰거나 기록하지 않습니다."""
    if (set(form.keys()) != {CATALOG_FIELD} or len(form.getlist(CATALOG_FIELD)) != 1
            or set(files.keys()) != {COVER_FIELD} or len(files.getlist(COVER_FIELD)) != 1):
        raise PdfDownloadInvalidFormError()
    text = form[CATALOG_FIELD]
    if len(text.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise PdfDownloadTooLargeError()
    try:
        payload = json.loads(text)
    except ValueError:
        raise PdfDownloadInvalidJsonError() from None
    upload = files[COVER_FIELD]
    if upload.filename != COVER_FILENAME:
        raise PdfDownloadInvalidFormError()
    data = upload.stream.read(MAX_COVER_BYTES + 1)
    if len(data) > MAX_COVER_BYTES:
        raise PdfCoverTooLargeError()
    if not data:
        raise PdfCoverInvalidError()
    return payload, data


def validate_cover(data):
    """브라우저 검사를 믿지 않고 다시 검사: PNG 서명 → 헤더의 형식·크기·프레임 수(디코딩 전) → verify → 전체 디코딩.
    통과하면 픽셀만으로 새 RGB 이미지를 만들어(메타데이터 미전달) 투명 부분은 화면 표지 영역 바탕색에 합성합니다.
    Pillow 전역 설정(LOAD_TRUNCATED_IMAGES·MAX_IMAGE_PIXELS)은 바꾸지 않습니다. 실제 AI 생성 출처는 인증하지 않습니다."""
    from PIL import Image
    if not data.startswith(_PNG_SIGNATURE):
        raise PdfCoverInvalidError()
    try:
        with Image.open(io.BytesIO(data), formats=["PNG"]) as probe:
            if probe.format != "PNG" or probe.size != COVER_SIZE or getattr(probe, "n_frames", 1) != 1:
                raise PdfCoverInvalidError()
            probe.verify()  # 청크·CRC 검사(이후 다시 열어야 함)
        with Image.open(io.BytesIO(data), formats=["PNG"]) as im:
            im.load()       # 잘린 파일은 여기서 실패(LOAD_TRUNCATED_IMAGES 기본값 유지)
            rgba = im.convert("RGBA")
    except PdfCoverInvalidError:
        raise
    except Exception:
        raise PdfCoverInvalidError() from None
    try:
        out = Image.new("RGB", COVER_SIZE, pdf_catalog.COLORS["paper_deep"])  # 화면 .catalog-figure 바탕색
        out.paste(rgba, mask=rgba.getchannel("A"))
        return out
    finally:
        rgba.close()


def parse_request(payload):
    """최상위는 {"catalog": {...}}만 허용합니다. catalog 내부 검사는 렌더러의 parse_catalog가 맡습니다."""
    if payload is None:
        raise PdfDownloadInvalidJsonError()
    if not isinstance(payload, dict) or set(payload) != {"catalog"} or not isinstance(payload["catalog"], dict):
        raise pdf_catalog.CatalogPdfInputError()
    return payload["catalog"]


def render(payload, cover_bytes=None):
    """검증 → (자리가 있으면) 표지 이미지 디코딩·렌더링 → PDF bytes. 자리가 없으면 렌더러를 실행하지 않고 429.
    형식 오류는 슬롯을 잡기 전에 걸러 렌더러·슬롯을 쓰지 않습니다. 비용이 큰 이미지 디코딩도 슬롯 안에서 합니다.
    cover_bytes가 없으면 기존(기본 배경) 동작과 같습니다."""
    catalog = parse_request(payload)
    pdf_catalog.parse_catalog(catalog)  # 빠른 형식 검사(실패 시 슬롯 미사용). build_pdf도 다시 검사함
    if not _slots.acquire(blocking=False):
        raise PdfDownloadBusyError()
    image = None
    try:
        if cover_bytes is not None:
            image = validate_cover(cover_bytes)
            return pdf_catalog.build_pdf(catalog, cover_image=image)
        return pdf_catalog.build_pdf(catalog)
    finally:
        if image is not None:
            image.close()
        _slots.release()
