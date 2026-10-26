"""시장 분석 routes. 화면 패널은 공통 shell(templates/base.html)이 포함합니다.

API(docs/data_contracts.md 응답 형식)
- GET  /api/market-analysis/meta     화면 초기값(최신 제공 월, 기본 품목·기간, 공급국 목록)
- POST /api/market-analysis/analyze  조회 조건(JSON) → 통계 결과 + bundle_id
- POST /api/market-analysis/ai       {bundle_id} → AI 분석(초안+5차례 검토). 유료 호출. 끝난 묶음은 재호출 없음
- POST /api/market-analysis/pdf      화면에 표시된 결과 {stats, ai} → PDF 파일(재조회·재분석 없음)
요청·응답 필드: features/market_analysis/feature_spec.md
"""
import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, jsonify, request

from common.errors import AIError
from features.market_analysis import pdf_report, service
from features.market_analysis.comexstat_client import ComexStatError

PDF_MAX_REQUEST_BYTES = 3 * 1024 * 1024  # 화면 결과 JSON 상한(PDF 요청)

logger = logging.getLogger(__name__)

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
    "description": "브라질 수입 통계를 바탕으로 수입액·수입량·공급국·평균단가 추세를 살펴봅니다.",
    "icon": "chart",
}


def _fail(code, message, status, **extra):
    error = {"code": code, "message": message}
    error.update(extra)
    return jsonify({"ok": False, "error": error}), status


@bp.get("/api/market-analysis/meta")
def meta():
    return jsonify({"ok": True, "data": service.meta()})


@bp.post("/api/market-analysis/analyze")
def analyze():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _fail("MA_INVALID_INPUT", "요청 형식이 올바르지 않습니다.", 400)
    try:
        data = service.analyze(payload)
    except service.InputError as err:
        return _fail(err.code, err.message, err.http_status, fields=err.fields)
    except ComexStatError as err:
        return _fail(err.code, err.message, err.http_status, retryable=err.retryable)
    except Exception:  # 예외 원문·입력값을 응답과 로그에 남기지 않습니다.
        logger.error("시장 분석 처리 중 예상하지 못한 오류")
        return _fail("MA_INTERNAL_ERROR", "분석 중 알 수 없는 오류가 발생했습니다. 다시 시도해 주세요.", 500)
    return jsonify({"ok": True, "data": data})


def _bundle_id():
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


@bp.post("/api/market-analysis/ai")
def ai():
    payload = _bundle_id()
    try:
        data = service.run_ai(payload.get("bundle_id"))
    except service.BundleError as err:
        return _fail(err.code, err.message, err.http_status)
    except AIError as err:
        return _fail(err.code, err.message, err.http_status, retryable=err.retryable)
    except Exception:
        logger.error("AI 분석 중 예상하지 못한 오류")
        return _fail("MA_INTERNAL_ERROR", "AI 분석 중 알 수 없는 오류가 발생했습니다.", 500)
    # 분석이 실패·중단돼도 끝난 단계까지의 결과와 상태를 200으로 돌려줍니다(화면이 '검토 미완료'로 표시).
    return jsonify({"ok": True, "data": data})


@bp.post("/api/market-analysis/pdf")
def pdf():
    if (request.content_length or 0) > PDF_MAX_REQUEST_BYTES:
        return _fail("MA_PDF_TOO_LARGE", "PDF로 만들 결과가 너무 큽니다.", 413)
    payload = request.get_json(silent=True)
    stats = payload.get("stats") if isinstance(payload, dict) else None
    if not isinstance(stats, dict) or not isinstance(stats.get("query"), dict):
        return _fail("MA_INVALID_INPUT", "PDF로 만들 조회 결과가 없습니다. 먼저 분석을 실행해 주세요.", 400)
    try:
        data = pdf_report.build_pdf({"stats": stats, "ai": payload.get("ai")})
    except (KeyError, TypeError, ValueError, AttributeError):
        logger.warning("PDF 입력 형식 오류")
        return _fail("MA_INVALID_INPUT", "결과 형식이 올바르지 않아 PDF를 만들지 못했습니다. 분석을 다시 실행해 주세요.", 400)
    except Exception:
        logger.error("PDF 생성 중 예상하지 못한 오류")
        return _fail("MA_PDF_FAILED", "PDF를 만들지 못했습니다. 다시 시도해 주세요.", 500)
    q = stats["query"]
    stamp = datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m%d")
    filename = "market_analysis_%s_%s_%s_%s.pdf" % (q.get("code", ""), q.get("from", ""), q.get("to", ""), stamp)
    return Response(data, mimetype="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="%s"' % filename.replace('"', "")})
