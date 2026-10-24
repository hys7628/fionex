"""그린 클레임 체크 routes. 화면 패널은 공통 shell(templates/base.html)이 포함합니다.

API는 기능 개발 단계에서 /api/green-claim 접두어로 추가합니다(docs/data_contracts.md).
"""
from flask import Blueprint

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
