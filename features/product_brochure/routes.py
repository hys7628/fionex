"""제품소개서 routes. 화면 패널은 공통 shell(templates/base.html)이 포함합니다.

API(docs/data_contracts.md 접두어 규칙):
- POST /api/product-brochure/analyze  PDF 분석(추출)
- POST /api/product-brochure/generate  확인된 항목 → pt-BR 카탈로그 문구 초안
- POST /api/product-brochure/pdf  적용된 편집본(catalog) → A4 4쪽 PDF 다운로드
- POST /api/product-brochure/cover-image  표시명·설명·분위기 → AI 표지 배경 PNG 1장(화면·PDF 연결 전)
"""
import logging

from flask import Blueprint, Response, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from common import config
from common.errors import AIError, PdfTooLargeError
from features.product_brochure import cover_image, generation, pdf_catalog, pdf_download, service

logger = logging.getLogger(__name__)

bp = Blueprint(
    "product_brochure",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/features/product_brochure/static",
)

# 사이드바 메뉴와 본문 머리글에 사용. icon은 templates/base.html의 아이콘 이름.
FEATURE = {
    "id": "product_brochure",
    "label": "제품소개서",
    "title": "제품소개서",
    "description": "한국어 제품 자료로 포르투갈어 소개서 PDF를 만듭니다.",
    "icon": "document",
}

FILE_FIELD = "source_file"
# 요청 전체 상한 = PDF 파일 상한 + multipart 경계·헤더 여유. 파일 자체 상한은 따로 검사합니다.
REQUEST_OVERHEAD_BYTES = 64 * 1024
MAX_REQUEST_BYTES = config.PDF_MAX_BYTES + REQUEST_OVERHEAD_BYTES
MAX_FORM_PARTS = 8
# max_form_memory_size는 재정의하지 않습니다(Flask 기본 500 KB). Werkzeug 3.1.9의 MultipartDecoder는
# 파트 종류와 무관하게 수신 버퍼 크기를 이 값과 비교하므로, 작게 잡으면 파일 업로드도 413으로 거부됩니다(실측).


def _error(err):
    return jsonify({"ok": False, "error": err.to_dict()}), err.http_status


def _read_upload():
    """source_file 1개를 검사하고 bytes로 읽습니다(최대 PDF 상한 + 1바이트)."""
    files = request.files
    unexpected = [name for name in files.keys() if name != FILE_FIELD]
    if unexpected:
        raise service.UploadUnexpectedFieldError()
    uploads = files.getlist(FILE_FIELD)
    if not uploads:
        raise service.UploadFileMissingError()
    if len(uploads) > 1:
        raise service.UploadMultipleFilesError()
    upload = uploads[0]
    if not upload.filename:
        raise service.UploadFilenameMissingError()
    data = upload.stream.read(config.PDF_MAX_BYTES + 1)
    if len(data) > config.PDF_MAX_BYTES:
        raise PdfTooLargeError()
    return data  # 빈 파일·서명·구조·암호화·페이지는 공통 inspect_pdf가 검사


@bp.post("/api/product-brochure/analyze")
def analyze():
    # request.files를 읽기 전에 이 요청에만 크기·파트 제한을 적용합니다(다른 탭·앱 설정에는 영향 없음).
    request.max_content_length = MAX_REQUEST_BYTES
    request.max_form_parts = MAX_FORM_PARTS
    try:
        try:
            pdf_bytes = _read_upload()
        except RequestEntityTooLarge:
            raise service.UploadTooLargeError() from None
        data = service.analyze_pdf(pdf_bytes)
        return jsonify({"ok": True, "data": data})
    except AIError as err:
        # 원본 파일명·PDF·추출 내용은 로그에 남기지 않습니다.
        logger.warning("product_brochure analyze 실패: code=%s", err.code)
        return _error(err)
    except Exception as exc:
        logger.error("product_brochure analyze 예기치 않은 오류: type=%s", type(exc).__name__)
        return _error(AIError())
    finally:
        # Werkzeug는 500 KB를 넘는 파일 부분을 임시 파일(SpooledTemporaryFile)로 받을 수 있습니다.
        # 요청 종료 시 Flask도 request.close()를 호출하지만, 여기서 먼저 닫아 임시 파일을 정리합니다.
        request.close()


@bp.post("/api/product-brochure/generate")
def generate():
    # 본문을 읽기 전에 이 요청에만 크기 제한을 적용합니다(다른 탭·앱 설정에는 영향 없음).
    request.max_content_length = generation.MAX_REQUEST_BYTES
    try:
        if not request.is_json:
            raise generation.GenerateInvalidJsonError()
        try:
            payload = request.get_json(silent=True)  # 잘못된 JSON은 None
        except RequestEntityTooLarge:
            raise generation.GenerateRequestTooLargeError() from None
        data = generation.generate_catalog(payload)
        return jsonify({"ok": True, "data": data})
    except AIError as err:
        # 입력 값·생성 결과는 로그에 남기지 않습니다.
        logger.warning("product_brochure generate 실패: code=%s", err.code)
        return _error(err)
    except RequestEntityTooLarge:
        logger.warning("product_brochure generate 실패: code=%s", generation.GenerateRequestTooLargeError.code)
        return _error(generation.GenerateRequestTooLargeError())
    except Exception as exc:
        logger.error("product_brochure generate 예기치 않은 오류: type=%s", type(exc).__name__)
        return _error(AIError())


@bp.post("/api/product-brochure/pdf")
def download_pdf():
    # 본문을 읽기 전에 이 요청에만 크기·파트 제한을 적용합니다(다른 탭·앱 설정에는 영향 없음).
    # 기본 배경: application/json 32 KiB. 적용한 AI 표지 배경 포함: multipart/form-data 16 MiB + 96 KiB, 파트 4개 이하.
    multipart = request.mimetype == "multipart/form-data"
    request.max_content_length = pdf_download.MAX_MULTIPART_BYTES if multipart else pdf_download.MAX_REQUEST_BYTES
    if multipart:
        request.max_form_parts = pdf_download.MAX_FORM_PARTS
    try:
        cover_bytes = None
        if multipart:
            try:
                payload, cover_bytes = pdf_download.read_multipart(request.form, request.files)
            except RequestEntityTooLarge:
                raise pdf_download.PdfDownloadTooLargeError() from None
        else:
            if not request.is_json:
                raise pdf_download.PdfDownloadInvalidJsonError()
            try:
                payload = request.get_json(silent=True)  # 잘못된 JSON·빈 본문은 None
            except RequestEntityTooLarge:
                raise pdf_download.PdfDownloadTooLargeError() from None
        pdf = pdf_download.render(payload, cover_bytes)
        # 완성된 bytes를 그대로 응답(버퍼 수명 문제 없음). 파일명·헤더에 사용자 입력을 쓰지 않습니다.
        return Response(pdf, mimetype="application/pdf", headers=pdf_download.RESPONSE_HEADERS)
    except AIError as err:
        # 카탈로그 문구·PDF는 로그에 남기지 않습니다.
        logger.warning("product_brochure pdf 실패: code=%s", err.code)
        return _error(err)
    except RequestEntityTooLarge:
        logger.warning("product_brochure pdf 실패: code=%s", pdf_download.PdfDownloadTooLargeError.code)
        return _error(pdf_download.PdfDownloadTooLargeError())
    except Exception as exc:
        logger.error("product_brochure pdf 예기치 않은 오류: type=%s", type(exc).__name__)
        return _error(pdf_catalog.CatalogPdfRenderError())
    finally:
        # multipart 파일 부분은 OS 임시 파일(SpooledTemporaryFile)일 수 있어 성공·실패 모두 먼저 닫습니다.
        request.close()


@bp.post("/api/product-brochure/cover-image")
def generate_cover_image():
    # 본문을 읽기 전에 이 요청에만 크기 제한을 적용합니다(다른 탭·앱 설정에는 영향 없음).
    request.max_content_length = cover_image.MAX_REQUEST_BYTES
    try:
        if not request.is_json:
            raise cover_image.CoverImageInvalidJsonError()
        try:
            payload = request.get_json(silent=True)  # 잘못된 JSON·빈 본문은 None
        except RequestEntityTooLarge:
            raise cover_image.CoverImageRequestTooLargeError() from None
        image = cover_image.generate_cover(payload)
        # 공통 함수가 검증한 PNG bytes를 메모리에서 그대로 반환(base64·파일 저장 없음)
        return Response(image.data, mimetype=image.mime_type, headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Prompt-Version": cover_image.PROMPT_VERSION,
        })
    except AIError as err:
        # 입력 값·프롬프트·이미지는 로그에 남기지 않습니다.
        logger.warning("product_brochure cover-image 실패: code=%s", err.code)
        return _error(err)
    except RequestEntityTooLarge:
        logger.warning("product_brochure cover-image 실패: code=%s", cover_image.CoverImageRequestTooLargeError.code)
        return _error(cover_image.CoverImageRequestTooLargeError())
    except Exception as exc:
        logger.error("product_brochure cover-image 예기치 않은 오류: type=%s", type(exc).__name__)
        return _error(AIError())
