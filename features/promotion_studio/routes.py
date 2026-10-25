"""홍보 스튜디오 routes. 화면 패널은 공통 shell(templates/base.html)이 포함합니다.

API는 기능 개발 단계에서 /api/promotion-studio 접두어로 추가합니다(docs/data_contracts.md).
"""
from flask import Blueprint

from features.promotion_studio import service

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
            "doc_extensions": service.DOC_EXTENSIONS,
            "image_extensions": service.IMAGE_EXTENSIONS,
            "limits": service.LIMITS,
            "defaults": service.DEFAULTS,
        }
    }
