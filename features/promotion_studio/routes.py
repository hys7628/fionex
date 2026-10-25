"""홍보 스튜디오 routes. 화면 패널은 공통 shell(templates/base.html)이 포함합니다.

API 접두어 /api/promotion-studio (docs/data_contracts.md). 요청·응답 형식은 feature_spec.md 10장.
"""
import io
import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request, send_file

from common.errors import AIError
from features.promotion_studio import pdf_builder, service

logger = logging.getLogger(__name__)

bp = Blueprint(
    "promotion_studio",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/features/promotion_studio/static",
)

# 사이드바 메뉴와 본문 머리글에 사용. icon은 templates/base.html의 아이콘 이름.
FEATURE = {
    "id": "promotion_studio",
    "label": "홍보 스튜디오",
    "title": "홍보 스튜디오",
    "description": "바이어용·소비자용 포르투갈어 홍보 영상 콘티를 구성하고 PDF로 내려받습니다.",
    "icon": "megaphone",
}


@bp.app_context_processor
def _promotion_studio_context():
    """panel.html이 service의 선택지·제한값을 그대로 쓰도록 전달합니다(화면·서버 값 일치)."""
    return {
        "promotion_studio": {
            "audiences": service.AUDIENCES,
            "purposes": service.PURPOSES,
            "tones": service.TONES,
            "durations": service.DURATIONS,
            "aspect_ratios": service.ASPECT_RATIOS,
            "image_styles": service.IMAGE_STYLES,
            "logo_scopes": service.LOGO_SCOPES,
            "pdf_editions": service.PDF_EDITIONS,
            "scene_image": {
                "quality": service.SCENE_IMAGE_QUALITY,
                "sizes": service.SCENE_IMAGE_SIZES,
                "estimated_usd": service.SCENE_IMAGE_ESTIMATED_USD,
            },
            "doc_extensions": service.DOC_EXTENSIONS,
            "image_extensions": service.IMAGE_EXTENSIONS,
            "limits": service.LIMITS,
            "defaults": service.DEFAULTS,
        }
    }


@bp.post("/api/promotion-studio/storyboard")
def create_storyboard():
    """콘티 입력 폼(multipart) → 텍스트 콘티. 입력 오류는 AI를 호출하기 전에 400으로 돌려줍니다."""
    cleaned, errors = service.validate_input(request.form, request.files)
    if errors:
        return jsonify({"ok": False, "error": {
            "code": "INVALID_INPUT", "message": "입력 내용을 확인하세요.", "fields": errors,
        }}), 400
    try:
        data = service.generate_storyboard(cleaned)
    except AIError as err:
        return jsonify({"ok": False, "error": err.to_dict()}), err.http_status
    return jsonify({"ok": True, "data": data})


def _pdf_error(code, message, status):
    return jsonify({"ok": False, "error": {"code": code, "message": message}}), status


@bp.post("/api/promotion-studio/pdf")
def download_pdf():
    """콘티 결과(JSON 문자열)·PDF 종류·선택 로고(multipart) → PDF 파일. 서버에 저장하지 않습니다."""
    try:
        board, edition, logo_bytes = service.parse_pdf_request(request.form, request.files)
        scene_images = service.parse_pdf_scene_images(request.files, len(board.scenes))
        photos = service.parse_pdf_photos(request.form, request.files)
    except service.PdfRequestError as err:
        return _pdf_error(err.code, err.message, 400)
    try:
        data = pdf_builder.build_pdf(board, edition, logo_bytes, scene_images, photos)
    except pdf_builder.LogoImageError:
        return _pdf_error("PDF_INVALID_LOGO", "로고 이미지를 읽지 못했습니다. 다른 이미지 파일을 선택하세요.", 400)
    except pdf_builder.SceneImageError:
        return _pdf_error("PDF_INVALID_SCENE_IMAGE", "장면 이미지를 읽지 못했습니다. 이미지를 다시 생성하세요.", 400)
    except Exception as exc:
        # 예외 메시지에 콘티 문구가 들어갈 수 있어 예외 종류만 기록합니다.
        logger.error("홍보 스튜디오 PDF 생성 실패: %s", type(exc).__name__)
        return _pdf_error("PDF_BUILD_FAILED", "PDF를 만들지 못했습니다. 잠시 후 다시 시도하세요.", 500)
    date = datetime.now(timezone(timedelta(hours=9))).strftime("%Y_%m_%d")
    return send_file(io.BytesIO(data), mimetype="application/pdf", as_attachment=True,
                     download_name=f"promotion_storyboard_{edition}_{date}.pdf")


@bp.post("/api/promotion-studio/scene-image")
def create_scene_image():
    """장면 1개(scene JSON) + 제품 사진(photos, 필수) → 사진을 참고한 장면 이미지(base64 PNG). 서버에 저장하지 않습니다."""
    try:
        data = service.generate_scene_image(request.form, request.files)
    except service.PdfRequestError as err:
        return _pdf_error(err.code, err.message, 400)
    except AIError as err:
        return jsonify({"ok": False, "error": err.to_dict()}), err.http_status
    return jsonify({"ok": True, "data": data})
