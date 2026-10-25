"""홈 service. 바이어 시간 카드가 쓰는 브라질 국가 공휴일을 제공합니다.

조회 순서: 서버 메모리 캐시 → BrasilAPI → 대체 자료(features/home/data/holidays_br_{연도}.json) → 없음.
공휴일을 추측해 만들지 않습니다. 대체 자료 파일은 출처가 검증된 경우에만 담당자가 추가합니다(현재 없음).
"""
import json
import logging
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

BRASILAPI_URL = "https://brasilapi.com.br/api/feriados/v1/{year}"
TIMEOUT_SECONDS = 5
# urllib 기본 User-Agent는 BrasilAPI가 403으로 거부함(2026-10-25 확인).
USER_AGENT = "fionex/0.1 (internal dashboard)"
# BrasilAPI 지원 연도 범위(2026-10-25 범위 밖 요청의 404 응답 문구로 확인).
MIN_YEAR = 1900
MAX_YEAR = 2199

FALLBACK_DIR = Path(__file__).resolve().parent / "data"

# 연도 → 결과. BrasilAPI 성공 결과만 담아 실패한 연도는 다음 요청에서 다시 시도합니다.
_cache = {}


def get_holidays(year):
    """{"source": "brasilapi"|"fallback"|"none", "fetched_at": ISO 문자열|None, "holidays": [{"date", "name"}]}"""
    cached = _cache.get(year)
    if cached:
        return cached

    try:
        result = {
            "source": "brasilapi",
            "fetched_at": _now_kst(),
            "holidays": _fetch_brasilapi(year),
        }
        _cache[year] = result
        return result
    except (urllib.error.URLError, OSError, ValueError) as err:
        # HTTPError·timeout은 URLError/OSError, JSON·형식 오류는 ValueError 계열입니다.
        logger.warning("BrasilAPI 공휴일 조회 실패(year=%s): %s", year, err)

    fallback = _load_fallback(year)
    if fallback is not None:
        return {"source": "fallback", "fetched_at": None, "holidays": fallback}
    return {"source": "none", "fetched_at": None, "holidays": []}


def _now_kst():
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")


def _fetch_brasilapi(year):
    req = urllib.request.Request(
        BRASILAPI_URL.format(year=year),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as res:
        data = json.load(res)
    return _parse_holidays(data, year)


def _load_fallback(year):
    path = FALLBACK_DIR / f"holidays_br_{year}.json"
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            return _parse_holidays(json.load(f), year)
    except (OSError, ValueError) as err:
        logger.warning("공휴일 대체 자료를 읽지 못함(%s): %s", path.name, err)
        return None


def _parse_holidays(data, year):
    """국가 공휴일만 [{"date": "YYYY-MM-DD", "name": str}]로 정리합니다. 형식이 다르면 ValueError."""
    if not isinstance(data, list):
        raise ValueError("공휴일 응답이 목록이 아닙니다")
    holidays = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("공휴일 항목 형식 오류")
        # BrasilAPI 응답은 type을 포함합니다. 대체 자료는 type 없이 국가 공휴일만 둘 수 있습니다.
        if item.get("type", "national") != "national":
            continue
        day = date.fromisoformat(str(item.get("date", "")))
        name = item.get("name")
        if day.year != year or not isinstance(name, str) or not name.strip():
            raise ValueError("공휴일 날짜·이름 형식 오류")
        holidays.append({"date": day.isoformat(), "name": name.strip()})
    if not holidays:
        raise ValueError("국가 공휴일이 없습니다")
    holidays.sort(key=lambda h: h["date"])
    return holidays
