"""제품소개서 routes. 화면 패널은 공통 shell(templates/base.html)이 포함합니다.

API는 기능 개발 단계에서 /api/product-brochure 접두어로 추가합니다(docs/data_contracts.md).
"""
from flask import Blueprint

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
    "description": "한국어 제품 자료로 브라질 포르투갈어 소개서를 만들고 검토한 뒤 PDF로 내려받습니다.",
    "icon": "document",
}
