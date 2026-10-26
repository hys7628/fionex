"""홈 service. 바이어 시간 카드의 브라질 국가 공휴일과 업계 소식 카드의 뉴스 목록을 제공합니다.

공휴일 조회 순서: 서버 메모리 캐시 → BrasilAPI → 대체 자료(features/home/data/holidays_br_{연도}.json) → 없음.
공휴일을 추측해 만들지 않습니다. 대체 자료 파일은 출처가 검증된 경우에만 담당자가 추가합니다(현재 없음).
"""
import hashlib
import json
import logging
import os
import re
import socket
import unicodedata
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

from features.home import buyer_time, fairs, fx, news_summary, report

# 환율은 features/home/fx.py, 전시회 일정은 features/home/fairs.py에서 처리합니다.
FX_SOURCES = fx.SOURCES
get_fx = fx.get_fx
FAIRS_DEFAULT_LIMIT = fairs.DEFAULT_LIMIT
FAIRS_MAX_LIMIT = fairs.MAX_LIMIT
FAIRS_MIN_BRAZIL_IN_ALL = fairs.MIN_BRAZIL_IN_ALL
FairsDataError = fairs.FairsDataError
get_upcoming_fairs = fairs.get_upcoming
# 일일 브리핑 PDF는 features/home/report.py가 위 함수들을 모아 만듭니다.
REPORT_CITIES = buyer_time.CITIES
REPORT_DEFAULT_CITY = buyer_time.DEFAULT_CITY
build_daily_report = report.build_daily

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

# Google News·ABIT 관련성 필터(2026-10-25 실제 RSS 4건으로 조정, 근거: docs/worklogs/hong_eunju/validation.md).
# 제목에 아래 낱말(악센트·대소문자 무시, 낱말 단위) 또는 구절이 하나 이상 있어야 남깁니다. RSS description은 제목 반복이라 보지 않습니다.
TEXTILE_NEWS_KEYWORDS = (
    "têxtil", "têxteis", "tecido", "tecidos", "fio", "fios", "fibra", "fibras", "malha", "malharia",
    "confecção", "confecções", "vestuário", "poliéster", "polyester", "algodão",
    "reciclado", "reciclada", "reciclados", "recicladas", "reciclagem",
)
# "moda" 단독은 패션·생활 기사까지 통과시켜(예: "Encontro exclusivo une moda, mulheres e bem-estar") 구절로만 인정합니다.
TEXTILE_NEWS_PHRASES = ("indústria da moda", "setor da moda", "cadeia da moda")
# 섬유 업계 단체 공식 사이트. 제목에 섬유 낱말이 없어도 업계 소식(세제·수출 쿼터·총회 등)이라 키워드 검사를 면제합니다.
TEXTILE_TRUSTED_DOMAINS = ("abit.org.br",)
# 브라질 시장용 목록이라 포르투갈 매체를 뺍니다. RSS <source url>의 매체 도메인으로 판단합니다(링크는 news.google.com).
EXCLUDED_MEDIA_TLDS = (".pt",)
# .pt가 아니어도 매체를 확인해 브라질 시장과 무관하다고 본 곳(2026-10-25 실제 RSS 기준):
# portugaltextil.com = 포르투갈 섬유 업계지, vietnam.vn = 베트남 산업 기사 포르투갈어판(필터 통과 21건 중 6건).
EXCLUDED_MEDIA_DOMAINS = ("portugaltextil.com", "vietnam.vn")
# 일일 브리핑 등 상위 N건을 고를 때 경로별 최소 건수(필터를 통과한 기사가 있을 때만 채움).
NEWS_SOURCE_MINIMUM = {"kotra": 1}

# 업계 소식 상세 화면의 Google News 추가 검색(사용자가 버튼을 누를 때만). 지역·언어는 GOOGLE_RSS_URL 그대로(브라질·포르투갈어).
# 검색어를 그대로 넓게 찾지 않도록 섬유 낱말 묶음과 기간을 붙이고, 결과는 위 관련성 필터를 똑같이 통과해야 합니다.
NEWS_SEARCH_LIMIT = 20
NEWS_SEARCH_MIN_LENGTH = 2
NEWS_SEARCH_MAX_LENGTH = 80
NEWS_SEARCH_CONTEXT = "(têxtil OR tecido OR fio OR confecção OR vestuário)"
NEWS_SEARCH_WINDOW = "when:90d"

# 뉴스 주제 태그(코드 기반 분류, AI 없음). 위 관련성 필터(포함/제외)와 목적이 달라 키워드를 따로 둡니다.
# 초안(2026-10-25): feature_spec에 (4-1) 키워드 표가 아직 없어 관련성 필터 낱말과 필수 검증 사례를 바탕으로 정함.
# 표가 확정되면 이 상수만 바꿉니다. 순서 = 우선순위(여러 태그가 맞으면 앞쪽부터 최대 2개, 없으면 "기타").
# 포르투갈어는 악센트·대소문자를 떼고 낱말 단위(여러 낱말은 구절 단위)로, 한국어(KOTRA 제목)는 글자 그대로 포함 여부로 봅니다.
NEWS_TOPIC_ORDER = ("원사", "원단", "규제·무역", "리사이클·ESG", "패션·리테일")
NEWS_TOPIC_OTHER = "기타"
NEWS_TOPIC_MAX = 2
NEWS_TOPIC_KEYWORDS = {
    "원사": ("fio", "fios", "fiação", "filamento", "filamentos", "fibra", "fibras", "poliéster", "polyester",
             "poliamida", "nylon", "elastano", "viscose", "algodão",
             "원사", "화섬", "폴리에스터", "면화"),
    "원단": ("tecido", "tecidos", "malha", "malhas", "malharia", "tecelagem", "tinturaria", "estamparia", "denim",
             "원단", "직물", "편직"),
    "규제·무역": ("exportação", "exportações", "importação", "importações", "cota", "cotas", "tarifa", "tarifas",
               "imposto", "impostos", "tributária", "tributário", "antidumping", "dumping", "regulamenta",
               "regulamentação", "mercosul", "acordo comercial", "comércio exterior",
               "수출", "수입", "관세", "무역", "규제", "통관", "협정"),
    "리사이클·ESG": ("reciclagem", "reciclado", "reciclada", "reciclados", "recicladas", "sustentabilidade",
                  "sustentável", "sustentáveis", "esg", "circular", "economia circular", "resíduos", "carbono",
                  "emissões", "rastreabilidade",
                  "재활용", "리사이클", "친환경", "지속가능", "탄소"),
    "패션·리테일": ("moda", "varejo", "vestuário", "confecção", "confecções", "coleção", "roupa", "roupas",
                "desfile", "fashion", "loja", "lojas",
                "패션", "의류", "소매", "유통", "브랜드"),
}

# KOTRA 해외시장뉴스 Open API(공공데이터포털 15034831). 요청 변수·응답 필드는 포털 Swagger 명세 기준이며,
# 인증키가 없어 실제 데이터 응답은 아직 확인하지 못했습니다.
KOTRA_URL = "https://apis.data.go.kr/B410001/kotra_overseasMarketNews/ovseaMrktNews/ovseaMrktNews"
KOTRA_KEY_ENV = "KOTRA_API_KEY"  # 확정(2026-10-25). 값은 .env에만 두고 코드·로그·화면에 남기지 않습니다.
KOTRA_COUNTRY = "브라질"
KOTRA_LOOKBACK_DAYS = 180
KOTRA_ROWS = 100
# 산업분류(search5) 코드 값을 확인하지 못해 쓰지 않고, 받은 결과를 아래 낱말로 거릅니다.
KOTRA_KEYWORDS = ("섬유", "원사", "원단", "의류", "화섬", "폴리에스터", "직물")
KOTRA_DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d", "%Y.%m.%d")

NEWS_ERRORS = {
    "key_missing": "KOTRA 인증키(KOTRA_API_KEY)가 설정되지 않아 KOTRA 뉴스는 가져오지 않습니다.",
    "access_denied": "요청이 거부되었습니다. 인증·접근 권한을 확인해야 합니다.",
    "timeout": "응답 시간이 초과되었습니다.",
    "fetch_failed": "뉴스를 불러오지 못했습니다.",
    "invalid_response": "응답 형식을 확인할 수 없습니다.",
}

# 경로 → 마지막 성공 {"items", "collected", "after_filter", "fetched_at", "expires"}.
# 갱신에 실패해도 지우지 않아 이전 수집분을 계속 보여 줍니다.
_news_cache = {}


class NewsSearchQueryError(ValueError):
    """검색어가 비었거나 너무 짧거나 김(외부 요청 전에 거절)."""


class NewsFetchError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def get_news(refresh=None):
    """{"items": [...최신순], "media": {경로: {status, fetched_at, collected, after_filter, count, stale[, error]}}}

    status: ok | error | not_configured(KOTRA 인증키 없음, 설정 필요. 다른 경로에는 영향 없음)
    collected: 응답에서 읽은 건수(형식이 맞는 항목, 경로 안 중복 제외) · after_filter: 관련성 필터 후 · count: 표시(최대 20)
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
                result = future.result()
            except NewsFetchError as err:
                errors[medium] = err.code
                continue
            except Exception:  # 예상하지 못한 오류도 다른 경로에 영향을 주지 않게 합니다.
                logger.exception("뉴스 수집 중 오류(%s)", medium)
                errors[medium] = "fetch_failed"
                continue
            if isinstance(result, list):  # 건수 없이 목록만 돌려주는 수집 함수(테스트 대역 등)
                result = {"items": result, "collected": len(result), "after_filter": len(result)}
            _news_cache[medium] = {
                "items": result["items"],
                "collected": result["collected"],
                "after_filter": result["after_filter"],
                "fetched_at": _now_kst(),
                "expires": monotonic() + NEWS_CACHE_SECONDS,
            }
            # 집계만 남깁니다(제목·본문·키 없음). KOTRA 0건 원인: collected=0 응답 0건 / filtered=0 필터 후 0건.
            logger.info("뉴스 %s: collected=%d filtered=%d shown=%d", medium, result["collected"],
                        result["after_filter"], len(result["items"]))

    lists = {}
    media = {}
    for medium in NEWS_MEDIA:
        cached = _news_cache.get(medium)
        lists[medium] = cached["items"] if cached else []
        code = errors.get(medium)
        info = {
            "status": "ok" if code is None else ("not_configured" if code == "key_missing" else "error"),
            "fetched_at": cached["fetched_at"] if cached else None,
            "collected": cached["collected"] if cached else None,
            "after_filter": cached["after_filter"] if cached else None,
            "count": len(lists[medium]),
            # 이번 갱신은 실패했고 이전 수집분을 보여 주는 중
            "stale": medium in errors and cached is not None,
        }
        if code is not None:
            info["error"] = {"code": code, "message": NEWS_ERRORS[code], "retryable": code != "key_missing"}
        media[medium] = info
    # 이미 만든 AI 요약만 붙입니다(새 요약은 summarize_news에서 따로 요청해 목록 표시를 늦추지 않음).
    items = []
    for item in merge_news(lists):
        item = dict(item)
        item["tags"] = news_topics(item["title"])  # 수집·정규화된 제목만 사용(발췌 없음)
        summary = news_summary.cached(item) if news_summary.is_target(item) else None
        if summary:
            item["summary_ko"] = summary
        items.append(item)
    return {"items": items, "media": media, "summary": {"pending": news_summary.pending_count(items)}}


def summarize_news():
    """현재 서버에 수집된 뉴스(새로 가져오지 않음) 중 요약이 없는 Google·ABIT 포르투갈어 제목을 요약합니다."""
    lists = {m: _news_cache[m]["items"] for m in NEWS_MEDIA if m in _news_cache}
    return news_summary.summarize(merge_news(lists))


def merge_news(lists):
    """경로별 목록을 합쳐 중복을 없애고 최신순으로 정렬합니다. 같은 기사면 abit 쪽을 남깁니다."""
    combined = []
    for medium in ("abit", "kotra", "google"):
        combined.extend(lists.get(medium, []))
    return _sort_news(dedupe_news(combined))


def select_top_news(items, limit, source_minimum=None):
    """최신순 목록에서 limit건을 고릅니다. source_minimum={"kotra": 1}이면 그 경로 기사가 있을 때 최신 n건을 먼저 넣고
    나머지를 최신순으로 채웁니다. 없는 경로를 채우지 않고, 결과는 다시 최신순입니다.

    반환 (선정 목록, {경로: 선정 건수})
    """
    chosen = []
    for origin, minimum in (source_minimum or {}).items():
        chosen += [item for item in items if item["origin"] == origin][:minimum]
    chosen = chosen[:limit]
    ids = {id(item) for item in chosen}
    for item in items:
        if len(chosen) >= limit:
            break
        if id(item) not in ids:
            chosen.append(item)
            ids.add(id(item))
    order = {id(item): index for index, item in enumerate(items)}
    chosen.sort(key=lambda item: order[id(item)])
    counts = {}
    for item in chosen:
        counts[item["origin"]] = counts.get(item["origin"], 0) + 1
    return chosen, counts


def _plain(text):
    """악센트를 떼고 소문자로(têxtil = textil = TÊXTIL)."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").casefold()


_TEXTILE_WORDS = {_plain(word) for word in TEXTILE_NEWS_KEYWORDS}
_TEXTILE_PHRASES = tuple(" ".join(re.findall(r"[a-z0-9]+", _plain(p))) for p in TEXTILE_NEWS_PHRASES)


def _topic_rules(keywords):
    """(라틴 낱말 집합, 라틴 구절, 한국어 낱말). 라틴 키워드는 판정용으로만 정규화합니다."""
    words, phrases, hangul = set(), [], []
    for keyword in keywords:
        if re.search(r"[가-힣]", keyword):
            hangul.append(keyword)
            continue
        tokens = re.findall(r"[a-z0-9]+", _plain(keyword))
        if len(tokens) == 1:
            words.add(tokens[0])
        else:
            phrases.append(" ".join(tokens))
    return words, tuple(phrases), tuple(hangul)


_TOPIC_RULES = {topic: _topic_rules(NEWS_TOPIC_KEYWORDS[topic]) for topic in NEWS_TOPIC_ORDER}


def news_topics(title):
    """제목만으로 주제 태그 1~2개(NEWS_TOPIC_ORDER 순). AI 요약·생성 문장은 쓰지 않습니다.

    짧은 낱말은 낱말 단위라 "desafio" 안의 "fio"처럼 단어 일부로는 맞지 않습니다.
    """
    words = re.findall(r"[a-z0-9]+", _plain(title))
    word_set = set(words)
    joined = " " + " ".join(words) + " "
    raw = title.casefold()
    tags = []
    for topic in NEWS_TOPIC_ORDER:
        latin, phrases, hangul = _TOPIC_RULES[topic]
        if (word_set & latin or any(" " + p + " " in joined for p in phrases)
                or any(k in raw for k in hangul)):
            tags.append(topic)
            if len(tags) == NEWS_TOPIC_MAX:
                break
    return tags or [NEWS_TOPIC_OTHER]


def _domain_matches(domain, rules):
    return any(domain == rule or domain.endswith("." + rule) for rule in rules)


def is_relevant_news(item):
    """Google News·ABIT 항목 관련성. 제외 매체(.pt 등) → 제외, 섬유 단체 공식 도메인 → 통과, 그 밖은 제목 키워드."""
    domain = item.get("media_domain") or ""
    if domain and (domain.endswith(EXCLUDED_MEDIA_TLDS) or _domain_matches(domain, EXCLUDED_MEDIA_DOMAINS)):
        return False
    if domain and _domain_matches(domain, TEXTILE_TRUSTED_DOMAINS):
        return True
    words = re.findall(r"[a-z0-9]+", _plain(item["title"]))
    if _TEXTILE_WORDS.intersection(words):
        return True
    joined = " " + " ".join(words) + " "
    return any(" " + phrase + " " in joined for phrase in _TEXTILE_PHRASES)


def _collected(items, keep=None):
    """{"items": 최신 20건, "collected", "after_filter"}. 경로 안 중복을 먼저 없앤 뒤 셉니다."""
    unique = _sort_news(dedupe_news(items))
    kept = [item for item in unique if keep(item)] if keep else unique
    return {"items": _limit(kept), "collected": len(unique), "after_filter": len(kept)}


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


def _news_item(title, url, media, published_at, origin, lang, media_domain=None):
    return {
        "id": hashlib.sha1(url.encode("utf-8")).hexdigest()[:16],
        "title": title,
        "url": url,
        "media": media,
        # 원문 매체 도메인(RSS <source url>, KOTRA는 원문 링크). Google 링크가 경유 주소라 PDF·필터에 씁니다.
        "media_domain": media_domain,
        "published_at": published_at,
        "origin": origin,
        "lang": lang,
    }


def _domain_of(url):
    host = (urllib.parse.urlsplit(url or "").hostname or "").lower()
    return host[4:] if host.startswith("www.") else host or None


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
    return _collected(_fetch_google_rss(GOOGLE_QUERY, "google"), is_relevant_news)


def _fetch_abit():
    # 두 검색 중 하나라도 실패하면 이 경로 전체를 실패로 보고합니다(일부 결과만 성공으로 표시하지 않음).
    with ThreadPoolExecutor(max_workers=len(ABIT_QUERIES)) as pool:
        results = list(pool.map(lambda q: _fetch_google_rss(q, "abit"), ABIT_QUERIES))
    return _collected([item for items in results for item in items], is_relevant_news)


def search_news(query):
    """업계 소식 상세 화면의 Google News 추가 검색. 사용자가 버튼을 눌렀을 때만 호출됩니다.

    검색어에 섬유 낱말 묶음(NEWS_SEARCH_CONTEXT)을 붙여 기존 Google News RSS(브라질·포르투갈어 설정)로 찾고,
    수집 뉴스와 같은 관련성 필터(.pt·제외 매체·섬유 낱말)·중복 제거·주제 태그를 적용합니다.
    새 AI 요약은 만들지 않고, 같은 기사(id·제목)에 이미 만든 요약만 붙입니다. 결과는 저장·캐시하지 않습니다.
    반환 {"query", "items", "count", "source", "collected", "after_filter"}. 실패는 NewsFetchError.
    """
    q = normalize_search_query(query)
    result = _collected(_fetch_google_rss(f'"{q}" {NEWS_SEARCH_CONTEXT} {NEWS_SEARCH_WINDOW}', "google"), is_relevant_news)
    items = []
    for item in result["items"][:NEWS_SEARCH_LIMIT]:
        item = dict(item)
        item["tags"] = news_topics(item["title"])
        summary = news_summary.cached(item) if news_summary.is_target(item) else None
        if summary:
            item["summary_ko"] = summary
        items.append(item)
    logger.info("뉴스 검색: collected=%d filtered=%d shown=%d", result["collected"], result["after_filter"], len(items))
    return {"query": q, "items": items, "count": len(items), "source": "google_news_rss",
            "collected": result["collected"], "after_filter": result["after_filter"]}


def normalize_search_query(query):
    """앞뒤 공백 제거·연속 공백 정리·따옴표 제거. 너무 짧거나 길면 NewsSearchQueryError(외부 요청 없음)."""
    q = " ".join(str(query or "").replace('"', " ").split())
    if len(q) < NEWS_SEARCH_MIN_LENGTH or len(q) > NEWS_SEARCH_MAX_LENGTH:
        raise NewsSearchQueryError()
    return q


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
        media_domain = _domain_of(source.get("url")) if source is not None else None
        if not title or not url or not published_at or not _is_http_url(url):
            continue
        # Google News 제목 끝의 " - 매체명"을 떼어 원문 제목만 남깁니다.
        suffix = " - " + media
        if media and title.endswith(suffix):
            title = title[: -len(suffix)].rstrip()
        # description은 제목과 매체명만 반복해(2026-10-25 확인) 쓰지 않습니다.
        items.append(_news_item(title, url, media or None, published_at, origin, lang, media_domain))
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
    raw = _kotra_raw_items(body)
    result = _collected(_kotra_items(raw))
    result["collected"] = len(raw)  # KOTRA는 API 응답 건수(국가·섬유 필터 전)를 수집 건수로 셉니다.
    return result


def parse_kotra(body):
    """Swagger 명세의 response.body.itemList.item을 정리하고 브라질·섬유 관련 항목만 남깁니다."""
    return _kotra_items(_kotra_raw_items(body))


def _kotra_raw_items(body):
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
    return raw


def _kotra_items(raw):
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
        items.append(_news_item(title, url, media, published_at, "kotra", "ko", _domain_of(url)))
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
