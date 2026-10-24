"""시장 분석 routes. 화면 패널은 공통 shell(templates/base.html)이 포함합니다.

API는 기능 개발 단계에서 /api/market-analysis 접두어로 추가합니다(docs/data_contracts.md).
"""
from flask import Blueprint

bp = Blueprint(
    "market_analysis",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/features/market_analysis/static",
)

# 사이드바 메뉴와 본문 머리글에 사용. icon은 templates/base.html의 아이콘 이름.
FEATURE = {
    "id": "market_analysis",
    "label": "시장 분석",
    "title": "시장 분석",
    "description": "브라질 수입 통계와 업계 소식을 바탕으로 수입액·수입량·공급국·평균단가 추세를 살펴봅니다.",
    "icon": "chart",
}
