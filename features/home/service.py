"""홈 service. 바이어 시간 카드의 브라질 국가 공휴일과 업계 소식 카드의 뉴스 목록을 제공합니다.

공휴일 조회 순서: 서버 메모리 캐시 → BrasilAPI → 대체 자료(features/home/data/holidays_br_{연도}.json) → 없음.
공휴일을 추측해 만들지 않습니다. 대체 자료 파일은 출처가 검증된 경우에만 담당자가 추가합니다(현재 없음).
"""
import hashlib
import json
import logging
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from time import monotonic
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


# ---------- 업계 소식(뉴스) ----------
# 수집 경로(kotra·google·abit)별로 따로 가져오고 캐시합니다. 한 경로가 실패해도 다른 경로 결과는 그대로 제공합니다.
# 기사 본문은 가져오지 않습니다. 원문 제목·매체·날짜·원문 링크만 다룹니다.
NEWS_MEDIA = ("kotra", "google", "abit")
NEWS_TIMEOUT_SECONDS = 10
NEWS_CACHE_SECONDS = 60 * 60
NEWS_MAX_ITEMS_PER_MEDIUM = 20
NEWS_MAX_RESPONSE_BYTES = 2 * 1024 * 1024

GOOGLE_RSS_URL = "https://news.google.com/rss/search?q={query}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
# 2026-10-25 실제 결과 확인. 초안의 "(tecido OR malharia) têxtil"은 인체 조직·할로윈 등 무관한 결과가 많아 쓰지 않습니다.
GOOGLE_QUERY = '("fio de poliéster" OR "fios têxteis" OR "indústria têxtil" OR "reciclagem têxtil") when:7d'
# ABIT 사이트는 직접 크롤링하지 않고 Google News RSS로 찾습니다. 초안의 OR 묶음은 2026-10-25 확인 시
# abit.org.br 결과만 돌아와, 공식 발표(site:)와 ABIT를 인용한 보도를 나눠 검색해 합칩니다.
ABIT_QUERIES = ("site:abit.org.br when:30d", '"ABIT" têxtil when:30d')

# KOTRA 해외시장뉴스 Open API(공공데이터포털 15034831). 요청 변수·응답 필드는 포털 Swagger 명세 기준이며,
# 인증키가 없어 실제 데이터 응답은 아직 확인하지 못했습니다.
KOTRA_URL = "https://apis.data.go.kr/B410001/kotra_overseasMarketNews/ovseaMrktNews/ovseaMrktNews"
KOTRA_KEY_ENV = "KOTRA_API_KEY"  # 제안한 이름. .env.example 반영은 공통 합의 후
KOTRA_COUNTRY = "브라질"
KOTRA_LOOKBACK_DAYS = 180
KOTRA_ROWS = 100
# 산업분류(search5) 코드 값을 확인하지 못해 쓰지 않고, 받은 결과를 아래 낱말로 거릅니다.
KOTRA_KEYWORDS = ("섬유", "원사", "원단", "의류", "화섬", "폴리에스터", "직물")
KOTRA_DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d", "%Y.%m.%d")

NEWS_ERRORS = {
    "key_missing": "KOTRA 인증키가 설정되지 않았습니다.",
    "access_denied": "요청이 거부되었습니다. 인증·접근 권한을 확인해야 합니다.",
    "timeout": "응답 시간이 초과되었습니다.",
    "fetch_failed": "뉴스를 불러오지 못했습니다.",
    "invalid_response": "응답 형식을 확인할 수 없습니다.",
}

# 경로 → 마지막 성공 {"items", "fetched_at", "expires"}. 갱신에 실패해도 지우지 않아 이전 수집분을 계속 보여 줍니다.
_news_cache = {}


class NewsFetchError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def get_news(refresh=None):
    """{"items": [...최신순], "media": {경로: {status, fetched_at, count, stale[, error]}}}

    refresh로 지정한 경로는 캐시를 무시하고 다시 가져옵니다. 만료된 경로도 다시 가져옵니다.
    """
    now = monotonic()
    pending = [m for m in NEWS_MEDIA
               if m == refresh or m not in _news_cache or _news_cache[m]["expires"] <= now]
    errors = {}
    if pending:
        with ThreadPoolExecutor(max_workers=len(pending)) as pool:
            futures = {m: pool.submit(_NEWS_FETCHERS[m]) for m in pending}
        for medium, future in futures.items():
            try:
                items = future.result()
            except NewsFetchError as err:
                errors[medium] = err.code
                continue
            except Exception:  # 예상하지 못한 오류도 다른 경로에 영향을 주지 않게 합니다.
                logger.exception("뉴스 수집 중 오류(%s)", medium)
                errors[medium] = "fetch_failed"
                continue
            _news_cache[medium] = {
                "items": items,
                "fetched_at": _now_kst(),
                "expires": monotonic() + NEWS_CACHE_SECONDS,
            }

    lists = {}
    media = {}
    for medium in NEWS_MEDIA:
        cached = _news_cache.get(medium)
        lists[medium] = cached["items"] if cached else []
        info = {
            "status": "error" if medium in errors else "ok",
            "fetched_at": cached["fetched_at"] if cached else None,
            "count": len(lists[medium]),
            # 이번 갱신은 실패했고 이전 수집분을 보여 주는 중
            "stale": medium in errors and cached is not None,
        }
        if medium in errors:
            code = errors[medium]
            info["error"] = {"code": code, "message": NEWS_ERRORS[code], "retryable": code != "key_missing"}
        media[medium] = info
    return {"items": merge_news(lists), "media": media}


def merge_news(lists):
    """경로별 목록을 합쳐 중복을 없애고 최신순으로 정렬합니다. 같은 기사면 abit 쪽을 남깁니다."""
    combined = []
    for medium in ("abit", "kotra", "google"):
        combined.extend(lists.get(medium, []))
    return _sort_news(dedupe_news(combined))


def dedupe_news(items):
    """URL이 같거나, 공백·대소문자를 정리한 제목이 같으면 먼저 나온 항목만 남깁니다.

    버린 항목의 URL·제목도 기억해, URL로 겹친 기사와 제목이 같은 또 다른 항목도 함께 거릅니다.
    """
    seen_urls, seen_titles, result = set(), set(), []
    for item in items:
        title_key = " ".join(item["title"].split()).casefold()
        duplicate = item["url"] in seen_urls or title_key in seen_titles
        seen_urls.add(item["url"])
        seen_titles.add(title_key)
        if not duplicate:
            result.append(item)
    return result


def _sort_news(items):
    # 시각이 있는 항목은 KST로 맞춰 비교합니다. 날짜만 있는 항목(KOTRA)은 같은 날 시각 있는 항목 뒤에 둡니다.
    def key(item):
        value = item["published_at"]
        if len(value) == 10:
            return value
        return datetime.fromisoformat(value).astimezone(ZoneInfo("Asia/Seoul")).isoformat()
    return sorted(items, key=key, reverse=True)


def _news_item(title, url, media, published_at, origin, lang):
    return {
        "id": hashlib.sha1(url.encode("utf-8")).hexdigest()[:16],
        "title": title,
        "url": url,
        "media": media,
        "published_at": published_at,
        "origin": origin,
        "lang": lang,
    }


def _http_get(url, accept):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    host = urllib.parse.urlsplit(url).netloc  # 로그에 쿼리(인증키 포함 가능)를 남기지 않습니다.
    try:
        with urllib.request.urlopen(req, timeout=NEWS_TIMEOUT_SECONDS) as res:
            body = res.read(NEWS_MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as err:
        logger.warning("뉴스 요청 실패(%s): HTTP %s", host, err.code)
        raise NewsFetchError("access_denied" if err.code in (401, 403) else "fetch_failed") from None
    except urllib.error.URLError as err:
        logger.warning("뉴스 요청 실패(%s): %s", host, type(err.reason).__name__)
        raise NewsFetchError("timeout" if isinstance(err.reason, TimeoutError) else "fetch_failed") from None
    except TimeoutError:
        logger.warning("뉴스 요청 시간 초과(%s)", host)
        raise NewsFetchError("timeout") from None
    except OSError as err:
        logger.warning("뉴스 요청 실패(%s): %s", host, type(err).__name__)
        raise NewsFetchError("fetch_failed") from None
    if len(body) > NEWS_MAX_RESPONSE_BYTES:
        raise NewsFetchError("invalid_response")
    return body


def _is_http_url(url):
    return urllib.parse.urlsplit(url).scheme in ("http", "https")


# Google News RSS (비공식, 형식 변경·차단 가능성 전제)
def _fetch_google():
    return _limit(_sort_news(dedupe_news(_fetch_google_rss(GOOGLE_QUERY, "google"))))


def _fetch_abit():
    # 두 검색 중 하나라도 실패하면 이 경로 전체를 실패로 보고합니다(일부 결과만 성공으로 표시하지 않음).
    with ThreadPoolExecutor(max_workers=len(ABIT_QUERIES)) as pool:
        results = list(pool.map(lambda q: _fetch_google_rss(q, "abit"), ABIT_QUERIES))
    return _limit(_sort_news(dedupe_news([item for items in results for item in items])))


def _fetch_google_rss(query, origin):
    url = GOOGLE_RSS_URL.format(query=urllib.parse.quote(query))
    return parse_google_rss(_http_get(url, "application/rss+xml, application/xml"), origin)


def parse_google_rss(body, origin):
    """RSS의 item을 뉴스 항목으로 정리합니다. 제목·링크·날짜가 없거나 날짜를 해석할 수 없는 항목은 제외합니다."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        raise NewsFetchError("invalid_response") from None
    channel = root.find("channel")
    if channel is None:
        raise NewsFetchError("invalid_response")
    lang = (channel.findtext("language") or "").strip() or None
    items = []
    for node in channel.findall("item"):
        title = (node.findtext("title") or "").strip()
        url = (node.findtext("link") or "").strip()
        published_at = _parse_rfc822(node.findtext("pubDate"))
        source = node.find("source")
        media = (source.text or "").strip() if source is not None else ""
        if not title or not url or not published_at or not _is_http_url(url):
            continue
        # Google News 제목 끝의 " - 매체명"을 떼어 원문 제목만 남깁니다.
        suffix = " - " + media
        if media and title.endswith(suffix):
            title = title[: -len(suffix)].rstrip()
        # description은 제목과 매체명만 반복해(2026-10-25 확인) 쓰지 않습니다.
        items.append(_news_item(title, url, media or None, published_at, origin, lang))
    return items


def _parse_rfc822(value):
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value.strip())
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:  # 시간대가 없으면 임의로 정하지 않습니다.
        return None
    return parsed.astimezone(timezone.utc).isoformat()


# KOTRA 해외시장뉴스 (이용 조건: 제목·날짜·원문 링크·출처명 위주 표시, 내용 요약·본문은 쓰지 않음)
def _fetch_kotra():
    key = os.environ.get(KOTRA_KEY_ENV, "").strip()
    if not key:
        raise NewsFetchError("key_missing")
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    params = {
        "serviceKey": key,
        "type": "json",
        "numOfRows": KOTRA_ROWS,
        "pageNo": 1,
        "search1": KOTRA_COUNTRY,
        "search4": (today - timedelta(days=KOTRA_LOOKBACK_DAYS)).strftime("%Y%m%d"),
        "search7": today.strftime("%Y%m%d"),
    }
    body = _http_get(KOTRA_URL + "?" + urllib.parse.urlencode(params), "application/json")
    return _limit(_sort_news(dedupe_news(parse_kotra(body))))


def parse_kotra(body):
    """Swagger 명세의 response.body.itemList.item을 정리하고 브라질·섬유 관련 항목만 남깁니다."""
    try:
        data = json.loads(body)
        payload = data["response"]["body"]
        item_list = payload.get("itemList") or {}
    except (ValueError, KeyError, TypeError, AttributeError):
        # 인증 실패 등 게이트웨이 오류는 OpenAPI_ServiceResponse 형식이라 여기로 옵니다.
        raise NewsFetchError("invalid_response") from None
    raw = item_list.get("item", []) if isinstance(item_list, dict) else item_list
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        raise NewsFetchError("invalid_response")

    items = []
    for it in raw:
        if not isinstance(it, dict):
            continue
        country = str(it.get("natn") or "")
        if country and KOTRA_COUNTRY not in country:
            continue
        text = " ".join(str(it.get(k) or "") for k in ("newsTitl", "kwrd", "indstCl", "cmdltNmKorn"))
        if not any(word in text for word in KOTRA_KEYWORDS):
            continue
        title = str(it.get("newsTitl") or "").strip()
        url = str(it.get("kotraNewsUrl") or "").strip()
        published_at = _parse_kotra_date(it.get("othbcDt"))
        if not title or not url or not published_at or not _is_http_url(url):
            continue
        office = str(it.get("ovrofInfo") or "").strip()
        media = "KOTRA 해외시장뉴스" + (" · " + office if office else "")
        items.append(_news_item(title, url, media, published_at, "kotra", "ko"))
    return items


def _parse_kotra_date(value):
    # 게시일자 형식은 실제 응답으로 확인하지 못했습니다. 아는 형식만 받고 날짜(YYYY-MM-DD)만 씁니다.
    value = str(value or "").strip()
    for fmt in KOTRA_DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _limit(items):
    return items[:NEWS_MAX_ITEMS_PER_MEDIUM]


_NEWS_FETCHERS = {"kotra": _fetch_kotra, "google": _fetch_google, "abit": _fetch_abit}
