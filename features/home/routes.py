"""홈 routes. 화면 패널은 공통 shell(templates/base.html)이 포함합니다.

API는 /api/home 접두어를 사용합니다(docs/data_contracts.md).
"""
import logging

from flask import Blueprint, Response, jsonify, request

from features.home import service

logger = logging.getLogger(__name__)

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


@bp.get("/api/home/fx")
def fx():
    """환율. ?refresh=usd_krw|usd_brl 은 그 소스만 캐시를 무시하고 다시 조회합니다.

    성공 {"ok": true, "data": {usd_krw, usd_brl, brl_krw}}. 소스별 실패는 data.<소스>.status로 알립니다.
    brl_krw는 두 공식 고시값이 모두 있을 때만 계산한 USD 경유 값이며, 아니면 null입니다.
    """
    refresh = request.args.get("refresh")
    if refresh is not None and refresh not in service.FX_SOURCES:
        return jsonify(ok=False, error={
            "code": "invalid_refresh",
            "message": "refresh는 " + ", ".join(service.FX_SOURCES) + " 중 하나여야 합니다.",
        }), 400
    return jsonify(ok=True, data=service.get_fx(refresh))


@bp.get("/api/home/fairs")
def fairs():
    """다가오는 브라질 섬유 전시회(정적 자료). ?limit=1~ (기본 5, 최대 20으로 제한)

    성공 {"ok": true, "data": {fairs, data_checked_at, total_upcoming, invalid_count}}.
    자료 파일을 읽지 못하면 503 fairs_unavailable(다른 홈 기능에는 영향 없음).
    """
    raw = request.args.get("limit")
    limit = service.FAIRS_DEFAULT_LIMIT
    if raw is not None:
        limit = request.args.get("limit", type=int)
        if limit is None or limit < 1:
            return jsonify(ok=False, error={
                "code": "invalid_limit",
                "message": "limit은 1 이상의 정수여야 합니다.",
            }), 400
        limit = min(limit, service.FAIRS_MAX_LIMIT)
    try:
        data = service.get_upcoming_fairs(limit)
    except service.FairsDataError:
        return jsonify(ok=False, error={
            "code": "fairs_unavailable",
            "message": "전시회 일정 자료를 확인할 수 없습니다.",
        }), 503
    return jsonify(ok=True, data=data)


@bp.get("/api/home/report/daily.pdf")
def daily_report():
    """일일 브리핑 PDF. ?city=화면 기준 도시 값(IANA, 기본 America/Sao_Paulo)

    성공: application/pdf 첨부 파일(메모리에서 생성, 서버에 저장하지 않음). 영역별 수집 실패는 PDF 안에 표시합니다.
    실패: 400 invalid_city, PDF 생성 자체 실패 500 report_failed.
    """
    city = request.args.get("city", service.REPORT_DEFAULT_CITY)
    if city not in service.REPORT_CITIES:
        return jsonify(ok=False, error={
            "code": "invalid_city",
            "message": "city는 " + ", ".join(service.REPORT_CITIES) + " 중 하나여야 합니다.",
        }), 400
    try:
        pdf, filename = service.build_daily_report(city)
    except Exception:
        logger.exception("일일 브리핑 PDF 생성 실패")
        return jsonify(ok=False, error={
            "code": "report_failed",
            "message": "PDF를 만들지 못했습니다. 잠시 후 다시 시도하세요.",
        }), 500
    return Response(pdf, mimetype="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
    })
