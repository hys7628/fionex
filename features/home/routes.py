"""홈 routes. 화면 패널은 공통 shell(templates/base.html)이 포함합니다.

API는 /api/home 접두어를 사용합니다(docs/data_contracts.md).
"""
from flask import Blueprint, jsonify, request

from features.home import service

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


@bp.get("/api/home/holidays")
def holidays():
    """브라질 국가 공휴일. ?year=YYYY. 성공 {"ok": true, "data": {source, fetched_at, holidays}}"""
    year = request.args.get("year", type=int)
    if year is None or not service.MIN_YEAR <= year <= service.MAX_YEAR:
        return jsonify(ok=False, error={
            "code": "invalid_year",
            "message": f"year는 {service.MIN_YEAR}~{service.MAX_YEAR} 사이의 정수여야 합니다.",
        }), 400
    return jsonify(ok=True, data=service.get_holidays(year))


@bp.get("/api/home/news")
def news():
    """업계 소식. ?refresh=kotra|google|abit 은 그 경로만 캐시를 무시하고 다시 가져옵니다.

    성공 {"ok": true, "data": {items, media}}. 경로별 실패는 data.media[경로].status로 알립니다.
    """
    refresh = request.args.get("refresh")
    if refresh is not None and refresh not in service.NEWS_MEDIA:
        return jsonify(ok=False, error={
            "code": "invalid_refresh",
            "message": "refresh는 " + ", ".join(service.NEWS_MEDIA) + " 중 하나여야 합니다.",
        }), 400
    return jsonify(ok=True, data=service.get_news(refresh))


@bp.post("/api/home/news/summaries")
def news_summaries():
    """서버에 수집된 Google News·ABIT 포르투갈어 제목의 한국어 한 줄 요약. KOTRA는 대상이 아닙니다.

    성공 {"ok": true, "data": {status: ok|unavailable|error, message?, summaries: {id: 요약}}}.
    요약 실패는 뉴스 표시에 영향을 주지 않도록 data.status로만 알립니다. 클라이언트가 보낸 문장은 받지 않습니다.
    """
    return jsonify(ok=True, data=service.summarize_news())
