"""시장 분석 2단계: 뉴스·보고서 수집. 공급자를 바꿔 끼울 수 있게 출처별 어댑터로 나눕니다.

출처와 확인 상태(2026-10-25)
- KOTRA 해외시장뉴스(공공데이터포털 15034831): 포털 페이지의 공식 명세(swagger)로 주소·인자·응답 필드 확인.
  키 없이 호출 시 HTTP 401 + SERVICE_KEY_IS_NULL(20), 미등록 키는 SERVICE_KEY_IS_NOT_REGISTERED_ERROR(30) 실측.
  이용 조건: 공공누리 제4유형(출처표시·상업적 이용금지·변경금지). AI 요약·번역·PDF 본문 수록·캐시 허용 범위가
  확인되지 않아 제목·링크·게시일과 KOTRA 원문 요약 표시만 하고, AI 입력·PDF 본문·캐시는 끕니다.
- 네이버 뉴스 검색 API: 공식 문서(developers.naver.com)로 주소·헤더·인자·필드 확인. 키 없이 401 + errorCode 024 실측.
  검색 결과의 제목·요약(description)·링크만 받습니다(원문 본문 아님).
- GDELT DOC 2.0: 공식 안내(2017 블로그)로 주소·인자 확인. 응답 필드는 제3자 클라이언트 문서 기준이며
  실제 응답은 429(5초에 1회 제한 안내)로 확인하지 못했습니다. 기본 검색 범위는 최근 3개월입니다.
- KITA: 시장뉴스·보고서용 공식 API·제휴 경로를 찾지 못해 '연결 확인 중' 상태만 표시합니다.

인증키는 서버 환경변수에서만 읽고 응답·로그·오류 문장에 넣지 않습니다. URL에 키가 들어가는 KOTRA는
URL을 로그에 남기지 않습니다.
"""
import html
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
USER_AGENT = "fionex-market-analysis/1.0"
TIMEOUT_SECONDS = 15.0
RETRY_WAIT_SECONDS = (3.0, 8.0)  # 최초 시도 이후 최대 2회(회복 가능한 실패만)

DEFAULT_MONTHS = 6
MAX_ITEMS = 20

# 환경변수 이름. 값은 코드·저장소에 두지 않습니다.
ENV_DATA_GO_KR_KEY = "DATA_GO_KR_SERVICE_KEY"
ENV_NAVER_ID = "NAVER_CLIENT_ID"
ENV_NAVER_SECRET = "NAVER_CLIENT_SECRET"

# 기사별 사용 범위. access: full_text(원문 본문 확보) | publisher_summary(제공기관 요약) | snippet(검색 결과 요약만)
# ai_input·pdf_text: 확인되기 전에는 False. 사용 범위가 확정되면 이 표만 고칩니다.
USAGE = {
    "kotra": {"access": "full_text", "ai_input": False, "pdf_text": False, "cache": False,
              "note": "공공누리 제4유형(출처표시·상업적 이용금지·변경금지). 업무용 AI 요약·번역·PDF 수록·캐시 허용 여부 확인 필요"},
    "naver": {"access": "snippet", "ai_input": True, "pdf_text": True, "cache": True,
              "note": "네이버 검색 결과의 제목·요약만 사용. 원문은 링크로 확인. 기사 저작권은 각 언론사"},
    "gdelt": {"access": "snippet", "ai_input": True, "pdf_text": True, "cache": True,
              "note": "GDELT 검색 결과의 제목·링크만 사용(본문 없음). 기사 저작권은 각 언론사"},
}

# 관련성 판단 주제(명세의 기본 주제). 모든 언어 키워드를 소문자로 비교합니다.
TOPICS = {
    "섬유·의류": ["섬유", "의류", "패션", "직물", "textile", "apparel", "garment", "clothing", "têxtil", "texteis",
              "têxteis", "vestuário", "confecção", "tecido"],
    "폴리에스터 원사": ["폴리에스터", "폴리에스테르", "원사", "dty", "polyester", "yarn", "filament", "poliéster",
                  "fio", "fios", "filamento"],
    "재생 섬유·T2T": ["재생", "리사이클", "재활용", "순환", "t2t", "recycled", "recycling", "circular",
                  "reciclado", "reciclagem", "circularidade"],
    "무역 정책": ["관세", "반덤핑", "수입규제", "통관", "무역", "tariff", "anti-dumping", "antidumping", "import duty",
              "tarifa", "imposto de importação", "gecex", "camex", "importação", "salvaguarda"],
}
BRAZIL_WORDS = ["브라질", "brazil", "brasil", "brazilian", "brasileiro", "brasileira"]

# 출처별 검색어. 네이버는 한국어, GDELT는 영어·포르투갈어.
NAVER_QUERIES = ["브라질 섬유", "브라질 폴리에스터", "브라질 원사", "브라질 의류 수입", "브라질 리사이클 섬유", "브라질 관세 섬유"]
NAVER_QUERIES_WIDE = ["브라질 섬유 시장", "중남미 섬유", "폴리에스터 원사 시장", "리사이클 폴리에스터"]
GDELT_QUERIES = [
    '(textile OR polyester OR yarn OR apparel) sourcecountry:brazil',
    '(têxtil OR poliéster OR vestuário OR fios) sourcelang:portuguese',
]
GDELT_QUERIES_WIDE = ['("recycled polyester" OR "textile recycling") brazil']


class SourceError(Exception):
    """kind: config(키 없음) | auth(인증·권한) | rate_limited | unavailable | bad_response | rejected"""

    def __init__(self, kind, message):
        self.kind = kind
        self.message = message
        super().__init__(message)


@dataclass
class NewsItem:
    id: str
    source: str            # kotra | naver | gdelt
    source_name: str       # 화면 표시용 출처명(KOTRA 해외시장뉴스, 언론사 도메인 등)
    title: str
    url: str
    published: str | None  # YYYY-MM-DD (확인 못 하면 None)
    collected_at: str
    language: str | None
    excerpt: str           # 표시용 요약·발췌(허용 범위 안)
    access: str            # full_text | publisher_summary | snippet
    usage_note: str
    ai_input: bool
    pdf_text: bool
    copyright_policy: str | None = None  # KOTRA dataType(저작권 정책) 원문
    brazil_context: bool = False  # 출처 단계에서 브라질 기사로 확인됨(KOTRA 국가=브라질, GDELT 브라질 매체)
    topics: list = field(default_factory=list)
    score: float = 0.0
    body: str | None = field(default=None, repr=False)  # 원문 본문(허용된 처리에만 사용, 응답에는 넣지 않음)

    def public(self):
        d = asdict(self)
        d.pop("body", None)
        return d


def now_kst():
    return datetime.now(KST)


def _clean(text):
    """HTML 태그·엔티티 제거, 공백 정리."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(text or "")))
    return re.sub(r"\s+", " ", text).strip()


def _transport(url, headers, timeout):
    """(HTTP 상태, 본문 bytes). 테스트에서 교체합니다. 예외 문장에 URL을 넣지 않습니다."""
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT, **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as err:
        try:
            body = err.read()
        except Exception:
            body = b""
        return err.code, body


_sleep = time.sleep


def _get_json(name, url, headers=None, classify=None, min_interval=0.0, last_call=None):
    """GET + JSON. 회복 가능한 실패만 최대 2회 재시도. classify(status, doc)가 SourceError를 돌려주면 그 오류로 처리."""
    last_error = None
    for attempt in range(len(RETRY_WAIT_SECONDS) + 1):
        if attempt:
            _sleep(RETRY_WAIT_SECONDS[attempt - 1])
        if last_call is not None and min_interval:
            wait = last_call[0] + min_interval - time.monotonic()
            if wait > 0:
                _sleep(wait)
            last_call[0] = time.monotonic()
        try:
            status, raw = _transport(url, headers or {}, TIMEOUT_SECONDS)
        except (urllib.error.URLError, TimeoutError, OSError):
            logger.warning("%s 연결 실패 attempt=%d", name, attempt + 1)
            last_error = SourceError("unavailable", "연결하지 못했습니다.")
            continue
        doc = None
        try:
            doc = json.loads(raw.decode("utf-8")) if raw else None
        except (ValueError, UnicodeDecodeError):
            doc = None
        err = classify(status, doc) if classify else None
        if err is None and status != 200:
            err = _default_status_error(status)
        if err is None and doc is None:
            err = SourceError("bad_response", "응답을 해석하지 못했습니다.")
        if err is None:
            return doc
        logger.warning("%s 오류 kind=%s status=%s attempt=%d", name, err.kind, status, attempt + 1)
        if err.kind not in ("rate_limited", "unavailable"):
            raise err
        last_error = err
    raise last_error


def _default_status_error(status):
    if status in (401, 403):
        return SourceError("auth", "인증 또는 권한 오류입니다. 키와 활용 신청 상태를 확인해 주세요.")
    if status == 429:
        return SourceError("rate_limited", "호출 한도에 걸렸습니다. 잠시 후 다시 시도해 주세요.")
    if status >= 500:
        return SourceError("unavailable", "제공기관 서버 오류입니다.")
    return SourceError("rejected", "제공기관이 요청을 거부했습니다.")


# ---------- KOTRA ----------
KOTRA_URL = "https://apis.data.go.kr/B410001/kotra_overseasMarketNews/ovseaMrktNews/ovseaMrktNews"
KOTRA_PAGE_SIZE = 100
KOTRA_MAX_PAGES = 3
# 공공데이터포털 공통 오류 코드 중 인증·권한·기한 관련(반복 호출하지 않음)
_KOTRA_AUTH_CODES = {"20", "30", "31", "32"}
_KOTRA_LIMIT_CODES = {"22"}


def _kotra_key():
    return os.environ.get(ENV_DATA_GO_KR_KEY, "").strip()


def _kotra_classify(status, doc):
    if isinstance(doc, dict) and "OpenAPI_ServiceResponse" in doc:
        header = (doc["OpenAPI_ServiceResponse"] or {}).get("cmmMsgHeader") or {}
        code = str(header.get("returnReasonCode") or "")
        if code in _KOTRA_AUTH_CODES:
            return SourceError("auth", "공공데이터포털 서비스키가 없거나 승인되지 않았습니다(코드 %s)." % code)
        if code in _KOTRA_LIMIT_CODES:
            return SourceError("rate_limited", "공공데이터포털 일일 호출 한도를 넘었습니다.")
        return SourceError("rejected", "공공데이터포털이 요청을 거부했습니다(코드 %s)." % (code or "?"))
    if isinstance(doc, dict) and "response" in doc:
        header = (doc["response"] or {}).get("header") or {}
        code = str(header.get("resultCode") or "")
        if code and code not in ("00", "0", "000", "200"):
            if code in _KOTRA_AUTH_CODES:
                return SourceError("auth", "공공데이터포털 서비스키가 승인되지 않았습니다(코드 %s)." % code)
            if code in _KOTRA_LIMIT_CODES:
                return SourceError("rate_limited", "공공데이터포털 일일 호출 한도를 넘었습니다.")
            return SourceError("rejected", "KOTRA API 결과 코드 %s" % code)
    return None


def _kotra_items(doc):
    body = ((doc or {}).get("response") or {}).get("body") or {}
    items = (body.get("itemList") or {}).get("item") or []
    if isinstance(items, dict):
        items = [items]
    total = body.get("totalCnt")
    return items, int(total) if str(total or "").isdigit() else None


def _yyyymmdd(d):
    return d.strftime("%Y%m%d")


def _parse_date(value):
    """'2026-10-01 09:00:00', '20261001', '20261001T093000Z', RFC 822('Mon, 26 Sep 2016 07:50:00 +0900') → date."""
    value = str(value or "").strip()
    m = re.match(r"^(\d{4})[-.]?(\d{2})[-.]?(\d{2})", value)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
        except ValueError:
            return None
    try:
        return parsedate_to_datetime(value).astimezone(KST).date()
    except (TypeError, ValueError, IndexError):
        return None


def fetch_kotra(start, end, collected_at):
    """브라질 해외시장뉴스. start·end: date."""
    key = _kotra_key()
    if not key:
        raise SourceError("config", "공공데이터포털 서비스키(%s)가 설정되지 않았습니다." % ENV_DATA_GO_KR_KEY)
    # 포털은 인코딩 키·디코딩 키를 함께 발급합니다. 이미 인코딩된 키(%)는 다시 인코딩하지 않습니다.
    key_param = key if "%" in key else urllib.parse.quote(key, safe="")
    out = []
    for page in range(1, KOTRA_MAX_PAGES + 1):
        query = urllib.parse.urlencode({"type": "json", "numOfRows": KOTRA_PAGE_SIZE, "pageNo": page,
                                        "search1": "브라질", "search4": _yyyymmdd(start), "search7": _yyyymmdd(end)})
        doc = _get_json("KOTRA", KOTRA_URL + "?serviceKey=" + key_param + "&" + query, classify=_kotra_classify)
        items, total = _kotra_items(doc)
        policy = USAGE["kotra"]
        for it in items:
            title = _clean(it.get("newsTitl"))
            url = str(it.get("kotraNewsUrl") or "").strip()
            if not title or not url:
                continue
            published = _parse_date(it.get("othbcDt"))
            text_meta = " ".join(_clean(it.get(k)) for k in ("kwrd", "indstCl", "cmdltNmKorn", "cmdltNmEng", "hsCdNm"))
            out.append(NewsItem(
                id="", source="kotra", source_name="KOTRA 해외시장뉴스" + (" · " + _clean(it.get("ovrofInfo")) if it.get("ovrofInfo") else ""),
                title=title, url=url, published=published.isoformat() if published else None, collected_at=collected_at,
                language="ko", excerpt=_clean(it.get("cntntSumar"))[:400], access=policy["access"],
                usage_note=policy["note"], ai_input=policy["ai_input"], pdf_text=policy["pdf_text"],
                copyright_policy=_clean(it.get("dataType")) or None,
                brazil_context="브라질" in _clean(it.get("natn")),
                body=(_clean(it.get("newsBdt")) + " " + text_meta).strip(),
            ))
        if total is None or page * KOTRA_PAGE_SIZE >= total or not items:
            break
    return out


# ---------- 네이버 뉴스 검색 ----------
NAVER_URL = "https://openapi.naver.com/v1/search/news.json"


def _naver_keys():
    return os.environ.get(ENV_NAVER_ID, "").strip(), os.environ.get(ENV_NAVER_SECRET, "").strip()


def _naver_classify(status, doc):
    if status in (401, 403):
        return SourceError("auth", "네이버 검색 API 인증·권한 오류입니다. 애플리케이션의 검색 API 사용 설정과 키를 확인해 주세요.")
    if status == 429:
        return SourceError("rate_limited", "네이버 검색 API 호출 한도에 걸렸습니다.")
    return None


def fetch_naver(start, end, collected_at, queries=None):
    cid, secret = _naver_keys()
    if not cid or not secret:
        raise SourceError("config", "네이버 검색 API 키(%s, %s)가 설정되지 않았습니다." % (ENV_NAVER_ID, ENV_NAVER_SECRET))
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret}
    policy = USAGE["naver"]
    out = []
    for q in queries or NAVER_QUERIES:
        url = NAVER_URL + "?" + urllib.parse.urlencode({"query": q, "display": 100, "start": 1, "sort": "date"})
        doc = _get_json("네이버", url, headers=headers, classify=_naver_classify)
        for it in (doc or {}).get("items") or []:
            published = _parse_date(it.get("pubDate"))
            if published and not (start <= published <= end):
                continue
            link = str(it.get("originallink") or it.get("link") or "").strip()
            title = _clean(it.get("title"))
            if not link or not title:
                continue
            out.append(NewsItem(
                id="", source="naver", source_name="네이버 뉴스 검색 · " + (urllib.parse.urlsplit(link).netloc or "언론사"),
                title=title, url=link, published=published.isoformat() if published else None, collected_at=collected_at,
                language="ko", excerpt=_clean(it.get("description"))[:400], access=policy["access"],
                usage_note=policy["note"], ai_input=policy["ai_input"], pdf_text=policy["pdf_text"],
            ))
    return out


# ---------- GDELT ----------
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_MIN_INTERVAL = 6.0  # 안내 문구 "5초에 1회" + 여유
_gdelt_last = [0.0]
_gdelt_lock = threading.Lock()


def _gdelt_classify(status, doc):
    if status == 429:
        return SourceError("rate_limited", "GDELT 호출 제한(5초에 1회)에 걸렸습니다.")
    return None


def fetch_gdelt(start, end, collected_at, queries=None):
    """GDELT는 최근 3개월 범위만 검색합니다(공식 안내). 6개월 요청이어도 3개월까지만 나옵니다."""
    policy = USAGE["gdelt"]
    out = []
    window_start = max(start, end - timedelta(days=90))
    with _gdelt_lock:
        for q in queries or GDELT_QUERIES:
            url = GDELT_URL + "?" + urllib.parse.urlencode({
                "query": q, "mode": "artlist", "maxrecords": 75, "format": "json", "sort": "datedesc",
                "startdatetime": window_start.strftime("%Y%m%d000000"), "enddatetime": end.strftime("%Y%m%d235959")})
            doc = _get_json("GDELT", url, classify=_gdelt_classify, min_interval=GDELT_MIN_INTERVAL, last_call=_gdelt_last)
            for it in (doc or {}).get("articles") or []:
                link = str(it.get("url") or "").strip()
                title = _clean(it.get("title"))
                if not link or not title:
                    continue
                published = _parse_date(it.get("seendate"))
                out.append(NewsItem(
                    id="", source="gdelt", source_name="GDELT · " + (str(it.get("domain") or "") or urllib.parse.urlsplit(link).netloc),
                    title=title, url=link, published=published.isoformat() if published else None, collected_at=collected_at,
                    language=(str(it.get("language") or "") or None), excerpt="", access=policy["access"],
                    usage_note=policy["note"], ai_input=policy["ai_input"], pdf_text=policy["pdf_text"],
                    brazil_context=str(it.get("sourcecountry") or "").lower() == "brazil",
                ))
    return out


# ---------- 정리: 관련성·중복 ----------
def _norm_url(url):
    p = urllib.parse.urlsplit(url.strip().lower())
    host = p.netloc[4:] if p.netloc.startswith("www.") else p.netloc
    return host + p.path.rstrip("/")


def _norm_title(title):
    return re.sub(r"[\W_]+", "", title.lower())


def score_item(item):
    """(점수, 주제 목록). 브라질 관련성 + 주제 일치 + 최근성. 주제가 하나도 없으면 0."""
    text = " ".join([item.title, item.excerpt, item.body or ""]).lower()
    topics = [name for name, words in TOPICS.items() if any(w in text for w in words)]
    if not topics:
        return 0.0, []
    if not (item.brazil_context or any(w in text for w in BRAZIL_WORDS)):
        return 0.0, topics
    score = 2.0 * len(topics) + sum(text.count(w) for words in TOPICS.values() for w in words) * 0.1
    if item.title and any(w in item.title.lower() for words in TOPICS.values() for w in words):
        score += 1.0
    if item.access == "full_text":
        score += 0.5
    return round(score, 2), topics


def select_items(items, limit=MAX_ITEMS):
    """중복 제거 후 관련성 상위 limit건. 같은 기사면 본문을 가진 쪽(KOTRA)·요약이 긴 쪽을 남깁니다."""
    best = {}
    order = {"full_text": 0, "publisher_summary": 1, "snippet": 2}
    for it in items:
        it.score, it.topics = score_item(it)
        if it.score <= 0:
            continue
        keys = {"u:" + _norm_url(it.url), "t:" + _norm_title(it.title)}
        existing = next((best[k] for k in keys if k in best), None)
        if existing is not None:
            better = (order[it.access], -len(it.excerpt)) < (order[existing.access], -len(existing.excerpt))
            if not better:
                continue
            for k in list(best):
                if best[k] is existing:
                    del best[k]
        for k in keys:
            best[k] = it
    unique = []
    for it in best.values():
        if it not in unique:
            unique.append(it)
    # 관련성 높은 순, 같으면 최근 순(게시일 없으면 뒤)
    unique.sort(key=lambda x: (-x.score, -int((x.published or "0000-00-00").replace("-", ""))))
    picked = unique[:limit]
    for i, it in enumerate(picked, 1):
        it.id = "N%d" % i
    return picked, len(unique)


# ---------- 전체 수집 ----------
PROVIDERS = {"kotra": fetch_kotra, "naver": fetch_naver, "gdelt": fetch_gdelt}
SOURCE_LABELS = {"kotra": "KOTRA 해외시장뉴스", "naver": "네이버 뉴스 검색", "gdelt": "GDELT", "kita": "한국무역협회(KITA)"}
_STATUS_TEXT = {
    "config": "설정 필요", "auth": "인증·권한 확인 필요", "rate_limited": "호출 한도", "unavailable": "연결 실패",
    "bad_response": "응답 해석 실패", "rejected": "요청 거부",
}


# 출처별 하루 캐시(서버 메모리, KST 날짜 기준). USAGE[출처]["cache"]가 True인 출처만. 요청이 들어올 때 날짜를 비교하며
# 정해진 시각에 스스로 수집하는 기능이 아닙니다.
_cache_lock = threading.Lock()
_provider_cache = {}  # (출처, widen) → {"day", "items", "collected_at"}


def clear_cache():
    with _cache_lock:
        _provider_cache.clear()


def collect(months=DEFAULT_MONTHS, widen=False, today=None, refresh=False):
    """모든 출처에서 수집. 일부 실패해도 나머지 결과를 돌려줍니다.

    반환: {"window": {...}, "items": [NewsItem], "candidates": int, "sources": [상태], "widened": bool}
    widen=True: 근거 보강용 넓은 검색어 추가(호출하는 쪽에서 1회로 제한).
    refresh=True: 하루 캐시를 쓰지 않고 다시 받습니다.
    """
    today = today or now_kst().date()
    start = today - timedelta(days=round(months * 30.4))
    collected_at = now_kst().isoformat(timespec="seconds")
    raw, statuses = [], []
    for name, fn in PROVIDERS.items():
        started = time.monotonic()
        key = (name, widen)
        with _cache_lock:
            cached = _provider_cache.get(key)
        if USAGE[name]["cache"] and not refresh and cached and cached["day"] == today.isoformat():
            raw.extend(NewsItem(**{**it.__dict__}) for it in cached["items"])
            statuses.append({"source": name, "label": SOURCE_LABELS[name], "state": "ok", "status_text": "연결됨(오늘 받은 자료 재사용)",
                             "count": len(cached["items"]), "message": None, "usage_note": USAGE[name]["note"],
                             "seconds": 0, "collected_at": cached["collected_at"]})
            continue
        try:
            if widen and name == "naver":
                got = fn(start, today, collected_at, NAVER_QUERIES + NAVER_QUERIES_WIDE)
            elif widen and name == "gdelt":
                got = fn(start, today, collected_at, GDELT_QUERIES + GDELT_QUERIES_WIDE)
            else:
                got = fn(start, today, collected_at)
            if USAGE[name]["cache"]:
                with _cache_lock:
                    _provider_cache[key] = {"day": today.isoformat(), "items": [NewsItem(**{**it.__dict__}) for it in got],
                                            "collected_at": collected_at}
            raw.extend(got)
            statuses.append({"source": name, "label": SOURCE_LABELS[name], "state": "ok", "status_text": "연결됨",
                             "count": len(got), "message": None, "usage_note": USAGE[name]["note"],
                             "seconds": round(time.monotonic() - started, 1), "collected_at": collected_at})
        except SourceError as err:
            statuses.append({"source": name, "label": SOURCE_LABELS[name], "state": err.kind,
                             "status_text": _STATUS_TEXT.get(err.kind, "실패"), "count": 0, "message": err.message,
                             "usage_note": USAGE[name]["note"], "seconds": round(time.monotonic() - started, 1)})
    statuses.append({"source": "kita", "label": SOURCE_LABELS["kita"], "state": "pending", "status_text": "연결 확인 중",
                     "count": 0, "message": "시장뉴스·연구보고서용 공식 API 또는 허용된 제공·제휴 경로를 확인하지 못했습니다(공공데이터포털 '한국무역협회' 오픈 API 0건, 2026-10-25).",
                     "usage_note": None, "seconds": 0})
    items, candidates = select_items(raw)
    return {
        "window": {"from": start.isoformat(), "to": today.isoformat(), "months": months,
                   "note": "GDELT는 최근 3개월까지만 검색됩니다."},
        "items": items,
        "candidates": candidates,
        "raw_count": len(raw),
        "sources": statuses,
        "widened": widen,
        "collected_at": collected_at,
    }
