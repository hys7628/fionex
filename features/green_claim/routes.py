"""그린 클레임 체크 routes. 화면 패널은 공통 shell(templates/base.html)이 포함합니다.

API는 /api/green-claim 접두어를 사용합니다(docs/data_contracts.md). 요청·응답만 다루고 처리는 service.py(일반 추출)·
ocr_service.py(AI 판독)·review_service.py(문구 검수)·report_service.py(검수 결과 PDF)가 합니다.
"""
import io

from flask import Blueprint, Response, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.formparser import FormDataParser

from common.errors import AIError
from features.green_claim import ocr_service, report_service, review_service, service

bp = Blueprint(
    "green_claim",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/features/green_claim/static",
)

# 사이드바 메뉴와 본문 머리글에 사용. icon은 templates/base.html의 아이콘 이름.
FEATURE = {
    "id": "green_claim",
    "label": "그린 클레임 체크",
    "title": "그린 클레임 체크",
    "description": "인증 요건 대비 보유 증빙의 차이와 친환경 주장 문구의 위험을 확인하고 포르투갈어 수정안을 검토합니다.",
    "icon": "shield",
}

# 요청 본문 상한: 파일 상한 + multipart 경계·헤더 여유. 파일 크기 자체는 service에서 정확히 검사합니다.
MAX_REQUEST_BYTES = service.MAX_FILE_BYTES + 64 * 1024
MAX_FORM_PARTS = 8
# 텍스트 필드·파서 내부 버퍼 상한(Werkzeug가 수신 버퍼에도 적용). Flask 기본값과 같은 500,000바이트.
MAX_FORM_MEMORY_BYTES = 500_000


def _memory_stream(total_content_length, content_type, filename, content_length=None):
    # Werkzeug 기본값은 500KB를 넘는 업로드를 임시 파일로 옮깁니다. 요청별 메모리에만 둡니다.
    return io.BytesIO()


def _error(code):
    err = service.ExtractError(code)
    return jsonify({"ok": False, "error": err.to_dict()}), err.http_status


def _fail(err):
    return jsonify({"ok": False, "error": err.to_dict()}), err.http_status


@bp.post("/api/green-claim/extract")
def extract_text():
    return _handle_upload(service.extract_file)  # .pdf / .docx 분기


@bp.post("/api/green-claim/ocr")
def ocr_text():
    """사용자가 AI 판독 버튼을 눌렀을 때만 호출되는 AI 글자 판독(PDF·JPG·JPEG·PNG, 공통 OpenAI PDF 연결)."""
    try:
        return _handle_upload(ocr_service.run_file_ocr)  # .pdf / .jpg·.jpeg·.png 분기
    except AIError as err:
        return _fail(err)
    except Exception:
        # 예외 원문·경로를 응답에 넣지 않고 공통 기본 오류의 고정 문장만 돌려줍니다.
        return _fail(AIError())


@bp.post("/api/green-claim/review")
def review_text():
    """그린워싱 문구 표현 위험 검수(JSON {"text": ...}만). 처리는 review_service가 합니다."""
    if request.mimetype != "application/json":
        return _error("REQUEST_INVALID")
    if request.content_length is not None and request.content_length > review_service.MAX_REQUEST_BYTES:
        return _error("REVIEW_REQUEST_TOO_LARGE")
    request.max_content_length = review_service.MAX_REQUEST_BYTES  # 길이 표시 없는 요청도 읽으면서 제한
    try:
        raw = request.get_data(cache=False)
    except RequestEntityTooLarge:
        return _error("REVIEW_REQUEST_TOO_LARGE")
    try:
        return jsonify({"ok": True, "data": review_service.run_review_request(raw)})
    except (service.ExtractError, AIError) as err:
        return _fail(err)
    except Exception:
        # 예외 원문·경로·문구를 응답·로그에 넣지 않고 공통 기본 오류의 고정 문장만 돌려줍니다.
        return _fail(AIError())


@bp.post("/api/green-claim/report")
def review_report():
    """화면이 보관한 마지막 유효 검수 결과 → PDF 보고서(attachment). 검수·공식 확인을 다시 하지 않습니다(report_service)."""
    if request.mimetype != "application/json":
        return _error("REPORT_JSON_INVALID")
    if request.content_length is not None and request.content_length > report_service.MAX_REQUEST_BYTES:
        return _error("REPORT_REQUEST_TOO_LARGE")
    request.max_content_length = report_service.MAX_REQUEST_BYTES
    try:
        raw = request.get_data(cache=False)
    except RequestEntityTooLarge:
        return _error("REPORT_REQUEST_TOO_LARGE")
    try:
        pdf = report_service.build_report(raw)
    except service.ExtractError as err:
        return _fail(err)
    except Exception:
        # 예외 원문·경로·문구를 응답·로그에 넣지 않습니다.
        return _error("REPORT_FAILED")
    response = Response(pdf, status=200, mimetype="application/pdf")
    response.headers["Content-Disposition"] = f'attachment; filename="{report_service.REPORT_FILENAME}"'
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _handle_upload(process):
    """promo_file 1개를 메모리로 받아 process(filename, data)를 실행하고 공통 응답 형식으로 돌려줍니다."""
    if request.mimetype != "multipart/form-data":
        return _error("REQUEST_INVALID")

    parser = FormDataParser(
        stream_factory=_memory_stream,
        max_content_length=MAX_REQUEST_BYTES,
        max_form_memory_size=MAX_FORM_MEMORY_BYTES,
        max_form_parts=MAX_FORM_PARTS,
        silent=False,
    )
    try:
        _, _, files = parser.parse_from_environ(request.environ)
    except RequestEntityTooLarge:
        return _error("FILE_TOO_LARGE")
    except Exception:
        return _error("REQUEST_INVALID")

    uploads = files.getlist("promo_file")
    try:
        if not uploads:
            return _error("FILE_MISSING")
        if len(uploads) > 1:
            return _error("FILE_MULTIPLE")
        upload = uploads[0]
        data = upload.stream.read()
        filename = upload.filename or ""
        try:
            result = process(filename, data)
        except service.ExtractError as err:
            return _fail(err)
        return jsonify({"ok": True, "data": result})
    finally:
        for _, storage in files.items(multi=True):
            storage.close()
