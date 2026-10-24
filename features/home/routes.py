"""홈 routes. 화면 패널은 공통 shell(templates/base.html)이 포함합니다.

API는 기능 개발 단계에서 /api/home 접두어로 추가합니다(docs/data_contracts.md).
"""
from flask import Blueprint

bp = Blueprint(
    "home",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/features/home/static",
)

# 사이드바 메뉴와 본문 머리글에 사용. icon은 templates/base.html의 아이콘 이름.
FEATURE = {
    "id": "home",
    "label": "홈",
    "title": "홈",
    "description": "브라질 바이어 현지 시간과 원단·원사·섬유 업계 소식을 확인하고 보고서를 내려받습니다.",
    "icon": "home",
}
