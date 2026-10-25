"""그린 클레임 체크 routes. 화면 패널은 공통 shell(templates/base.html)이 포함합니다.

API는 /api/green-claim 접두어를 사용합니다(docs/data_contracts.md). 요청·응답만 다루고 처리는 service.py가 합니다.
"""
import io

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.formparser import FormDataParser

from features.green_claim import service

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


@bp.post("/api/green-claim/extract")
def extract_text():
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
            result = service.extract_file(filename, data)  # .pdf / .docx 분기
        except service.ExtractError as err:
            return jsonify({"ok": False, "error": err.to_dict()}), err.http_status
        return jsonify({"ok": True, "data": result})
    finally:
        for _, storage in files.items(multi=True):
            storage.close()
