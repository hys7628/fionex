"""홈 '다가오는 전시회' 카드: 기능 전용 정적 자료(data/br_textile_fairs.json, 브라질 + 중남미)에서 다가오는 행사만 골라 줍니다.

- 외부 수집·AI 생성 없음. 출처 링크가 없거나 형식이 틀린 항목은 내보내지 않습니다(값을 보충하지 않음).
- country(표시용 국가명)·region(화면 필터 구분)은 필수. region은 "brazil"(브라질) 또는 "latin_america"(브라질 외 중남미)
  하나뿐이라 브라질 행사가 두 구분에 겹치지 않습니다. 정확한 날짜가 없는 행사는 자료에 넣지 않습니다.
- 기준 날짜는 서울. 종료일이 오늘 이후인 행사만, 시작일 순. D-day는 코드로 계산합니다.
- 파일이 작아 요청마다 읽습니다(자료 수정이 서버 재시작 없이 반영되고 캐시 무효화가 필요 없음).
"""
import json
import logging
import urllib.parse
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parent / "data" / "br_textile_fairs.json"
DEFAULT_LIMIT = 5
MAX_LIMIT = 20
OPTIONAL_TEXT = ("city", "venue", "focus", "note")
REGIONS = ("brazil", "latin_america")
# 가정값: 전체 보기(브라질+중남미)에서 브라질 행사가 상위 목록에서 밀려나지 않도록 최소 건수를 보장합니다
# (브라질 행사가 그보다 적으면 있는 만큼만). 화면(home.js FAIR_MIN_BRAZIL_IN_ALL)과 같은 값입니다.
MIN_BRAZIL_IN_ALL = 2


class FairsDataError(Exception):
    """자료 파일이 없거나 형식이 틀림. 화면에는 '일정 확인 불가'로만 보입니다."""


def get_upcoming(limit=DEFAULT_LIMIT, today=None, path=None, min_brazil=0):
    """{"fairs": [...], "data_checked_at", "total_upcoming", "invalid_count"}

    min_brazil > 0이면 select_for_all로 브라질 최소 건수를 보장해 고릅니다(일일 브리핑 PDF). API 기본은 날짜순.
    """
    if today is None:
        today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    fairs, checked_at, invalid = load_fairs(path or DATA_FILE)
    upcoming = sorted((f for f in fairs if f["end"] >= today), key=lambda f: (f["start"], f["name"]))
    chosen = select_for_all(upcoming, limit, min_brazil) if min_brazil else upcoming[:limit]
    return {
        "fairs": [_present(f, today) for f in chosen],
        "data_checked_at": checked_at,
        "total_upcoming": len(upcoming),
        "invalid_count": invalid,
    }


def select_for_all(fairs, limit, min_brazil=MIN_BRAZIL_IN_ALL):
    """날짜순 목록에서 limit건. 브라질 행사를 앞에서부터 min_brazil건(있는 만큼) 먼저 넣고 나머지를 날짜순으로 채운 뒤
    다시 날짜순으로 돌려줍니다. 행사를 새로 만들지 않습니다."""
    chosen = [f for f in fairs if f["region"] == "brazil"][:min(min_brazil, limit)]
    for fair in fairs:
        if len(chosen) >= limit:
            break
        if fair not in chosen:
            chosen.append(fair)
    order = {id(f): i for i, f in enumerate(fairs)}
    return sorted(chosen, key=lambda f: order[id(f)])


def d_day(start, end, today):
    if today < start:
        return f"D-{(start - today).days}", "upcoming"
    if today == start:
        return "D-DAY", "today"
    if today <= end:
        return "진행 중", "ongoing"
    return None, "ended"


def load_fairs(path):
    """(유효한 행사 목록, 자료 확인일, 제외한 항목 수). 파일·최상위 형식이 틀리면 FairsDataError."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as err:
        logger.warning("전시회 자료를 읽지 못함(%s): %s", Path(path).name, type(err).__name__)
        raise FairsDataError() from None
    if not isinstance(data, dict) or not isinstance(data.get("fairs"), list):
        logger.warning("전시회 자료 형식 오류: fairs 목록 없음")
        raise FairsDataError()
    checked_at = _date(data.get("checked_at"))

    fairs, invalid = [], 0
    for index, item in enumerate(data["fairs"]):
        fair = _validate(item)
        if fair is None:
            invalid += 1
            logger.warning("전시회 자료 %d번째 항목 제외(필수 값 누락·형식 오류)", index + 1)
            continue
        fairs.append(fair)
    return fairs, checked_at.isoformat() if checked_at else None, invalid


def _validate(item):
    if not isinstance(item, dict):
        return None
    name, url, source = (str(item.get(k) or "").strip() for k in ("name", "url", "source"))
    start, end, checked = _date(item.get("start")), _date(item.get("end")), _date(item.get("checked_at"))
    if not name or not source or not start or not end or not checked or end < start:
        return None
    if urllib.parse.urlsplit(url).scheme not in ("http", "https") or not urllib.parse.urlsplit(url).netloc:
        return None
    if not isinstance(item.get("verified"), bool):
        return None
    country = str(item.get("country") or "").strip()
    if not country or item.get("region") not in REGIONS:
        return None
    fair = {"name": name, "start": start, "end": end, "url": url, "source": source,
            "verified": item["verified"], "checked_at": checked, "country": country, "region": item["region"]}
    for key in OPTIONAL_TEXT:
        value = item.get(key)
        fair[key] = value.strip() if isinstance(value, str) and value.strip() else None
    return fair


def _date(value):
    try:
        return date.fromisoformat(value) if isinstance(value, str) and len(value) == 10 else None
    except ValueError:
        return None


def _present(fair, today):
    label, status = d_day(fair["start"], fair["end"], today)
    return {
        "name": fair["name"],
        "start": fair["start"].isoformat(),
        "end": fair["end"].isoformat(),
        "d_day": label,
        "status": status,
        "country": fair["country"],
        "region": fair["region"],
        "city": fair["city"],
        "venue": fair["venue"],
        "focus": fair["focus"],
        "note": fair["note"],
        "url": fair["url"],
        "source": fair["source"],
        "verified": fair["verified"],
        "checked_at": fair["checked_at"].isoformat(),
    }
