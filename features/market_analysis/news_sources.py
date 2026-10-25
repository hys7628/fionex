"""시장 분석 근거 자료 수집. 출처별 어댑터로 나눠 공급자를 바꿔 끼울 수 있게 합니다.

출처와 확인 상태
- KOTRA 해외시장뉴스(공공데이터포털 15034831): 포털 페이지의 공식 명세(swagger)로 주소·인자·응답 필드 확인(2026-10-25).
  키 없이 호출 시 HTTP 401 + SERVICE_KEY_IS_NULL(20), 미등록 키는 SERVICE_KEY_IS_NOT_REGISTERED_ERROR(30) 실측.
  이용 조건: 공공누리 제4유형(출처표시·상업적 이용금지·변경금지). AI 요약·번역·PDF 본문 수록·캐시 허용 범위가
  확인되지 않아 제목·링크·게시일과 KOTRA 원문 요약 표시만 하고, AI 입력·PDF 본문·캐시는 끕니다.
  2026-10-26 실제 응답(브라질 최근 6개월 28건)에는 명세의 요약(cntntSumar)·본문(newsBdt) 필드가 없어
  기사별 확보 범위를 응답 내용으로 판단합니다(본문이 없으면 title_only).
- 일반 뉴스: 2026-10-26 사용자 결정으로 GDELT 자동 호출을 중단하고 새 공급자 선택을 기다립니다(PROVIDERS에서 제외,
  '공급자 선택 대기' 상태 표시). 아래 GDELT 어댑터는 선택 결과가 나올 때까지 호출되지 않는 상태로 둡니다.
- GDELT DOC 2.0 API(2026-10-26 일반 뉴스 공급자로 통일했다가 같은 날 자동 호출 중단, 현재 비활성): 인증키 없음.
  공식 안내: 65개 언어 기사를 영어로 기계 번역해 영어 검색어로 찾고, 검색 범위는 최근 3개월이라고 안내하지만 2026-10-26 실측에서 120~150일 전 구간도 결과가 나와 구간을 나눠 6개월을 조회함,
  artlist 최대 250건. 이용 조건: 상업적 이용 포함 무료, 사용·재배포 시 GDELT 표기와 링크 필요.
  기사 본문은 제공하지 않으며 기사 저작권은 각 언론사에 있으므로 원문을 가져오지 않습니다(제목·메타데이터만 사용).
  seendate는 GDELT가 기사를 처음 발견한 시각이며 기사 발행일로 쓰지 않습니다.
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
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
USER_AGENT = "fionex-market-analysis/1.0"
TIMEOUT_SECONDS = 20.0
RETRY_WAIT_SECONDS = (3.0, 8.0)  # 최초 시도 이후 최대 2회(회복 가능한 실패만)

DEFAULT_MONTHS = 6
MAX_ITEMS = 20
MAX_OTHER_ITEMS = 50  # 주제 기준 밖 수집 기사(화면 참고용) 표시 상한

# 환경변수 이름. 값은 코드·저장소에 두지 않습니다.
ENV_DATA_GO_KR_KEY = "DATA_GO_KR_SERVICE_KEY"

# 기사별 사용 범위. access: full_text(원문 본문 확보) | title_only(제목·메타데이터만 확인)
# ai_input·pdf_text: 확인되기 전에는 False. 사용 범위가 확정되면 이 표만 고칩니다.
USAGE = {
    # access는 기사별 응답 내용으로 정합니다(fetch_kotra).
    "kotra": {"ai_input": False, "pdf_text": False, "cache": False,
              "note": "공공누리 제4유형(출처표시·상업적 이용금지·변경금지). 업무용 AI 요약·번역·PDF 수록·캐시 허용 여부 확인 필요"},
    "gdelt": {"access": "title_only", "ai_input": True, "pdf_text": True, "cache": True,
              "note": "GDELT 검색 결과의 제목·링크·매체·언어만 사용(본문 없음, 원문 미확인). 기사 저작권은 각 언론사. 출처 표기: The GDELT Project (gdeltproject.org)"},
}

# 관련성 판단 주제. 제목은 원문 언어로 오므로 한국어·영어·포르투갈어를 함께 봅니다.
# 제품·산업 주제(PRODUCT_TOPICS) 중 하나는 반드시 있어야 하며, 무역 정책·브라질 단어만으로는 선정하지 않습니다.
TOPICS = {
    "섬유·의류": ["섬유", "의류", "패션", "직물", "textile", "apparel", "garment", "clothing", "fashion industry",
              "têxtil", "têxteis", "texteis", "vestuário", "confecção", "confecções", "moda", "tecido", "tecelagem"],
    "폴리에스터·DTY": ["폴리에스터", "폴리에스테르", "원사", "dty", "polyester", "yarn", "textured yarn", "synthetic fiber",
                    "poliéster", "fio têxtil", "fios têxteis", "fio de poliéster", "fios de poliéster", "fibra sintética", "filamento"],
    "재생 섬유·T2T": ["재생 섬유", "재생섬유", "리사이클", "재활용 섬유", "t2t", "recycled polyester", "textile recycling",
                  "textile-to-textile", "fiber-to-fiber", "fibre-to-fibre", "circular fashion", "poliéster reciclado",
                  "reciclagem têxtil", "fibra reciclada", "moda circular"],
    "무역 정책": ["관세", "반덤핑", "수입규제", "tariff", "anti-dumping", "antidumping", "import duty", "safeguard",
              "imposto de importação", "antidumping", "gecex", "camex", "salvaguarda", "alíquota"],
}
PRODUCT_TOPICS = ("섬유·의류", "폴리에스터·DTY", "재생 섬유·T2T")
BRAZIL_WORDS = ["브라질", "brazil", "brasil", "brazilian", "brasileiro", "brasileira", "brasileiros", "brasileiras"]

# GDELT 검색어(영어, 기계 번역본 검색). 공식 안내상 OR 묶음은 중첩할 수 없습니다.
GDELT_QUERIES = [
    "(textile OR apparel OR garment OR clothing) sourcecountry:brazil",
    '(polyester OR "textured yarn" OR "synthetic fiber" OR "synthetic yarn") brazil',
    '("recycled polyester" OR "textile recycling" OR "textile-to-textile" OR "fiber-to-fiber" OR "circular fashion") brazil',
    "(tariff OR antidumping OR safeguard) textile brazil",
]
GDELT_QUERIES_WIDE = ['(textile OR polyester OR yarn) (brazil OR "latin america")']


class SourceError(Exception):
    """kind: config(키 없음) | auth(인증·권한) | rate_limited | unavailable | bad_response | rejected"""

    def __init__(self, kind, message):
        self.kind = kind
        self.message = message
        super().__init__(message)


@dataclass
class NewsItem:
    id: str
    source: str            # kotra | gdelt
    source_name: str       # 화면 표시용 출처명(KOTRA 해외시장뉴스, 매체 도메인 등)
    title: str
    url: str
    published: str | None  # 기사 게시일 YYYY-MM-DD. 제공기관이 게시일을 주지 않으면 None
    collected_at: str      # 우리가 수집한 시각(KST)
    language: str | None
    excerpt: str           # 표시용 요약·발췌(허용 범위 안). GDELT는 빈 문자열
    access: str            # full_text | title_only
    usage_note: str
    ai_input: bool
    pdf_text: bool
    seen_at: str | None = None           # GDELT 최초 발견 시각(UTC, 'YYYY-MM-DD HH:MM UTC'). 게시일 아님
    outlet: str | None = None            # 매체(도메인)
    source_country: str | None = None    # 매체 국가(GDELT sourcecountry)
    copyright_policy: str | None = None  # KOTRA dataType(저작권 정책) 원문
    brazil_context: bool = False         # 출처 단계에서 브라질 기사로 확인됨(KOTRA 국가=브라질, GDELT 브라질 매체)
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
    """HTML 태그·엔티티 제거, 공백 정리. 엔티티를 푼 뒤 생긴 태그 모양 문자열도 지웁니다."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(text or "")))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def safe_url(value):
    """화면·PDF 링크로 쓸 수 있는 http(s) 절대 주소면 그대로, 아니면 None."""
    url = str(value or "").strip()
    if not url or re.search(r"[\s\x00-\x1f\x7f<>\"']", url):
        return None
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        return None
    return url


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


def _get_json(name, url, headers=None, classify=None, min_interval=0.0, last_call=None, retry_waits=None):
    """GET + JSON. 회복 가능한 실패만 최대 2회 재시도. classify(status, doc, raw)가 SourceError를 돌려주면 그 오류로 처리."""
    waits = retry_waits or RETRY_WAIT_SECONDS
    last_error = None
    for attempt in range(len(waits) + 1):
        if attempt:
            _sleep(waits[attempt - 1])
        if last_call is not None and min_interval:
            wait = last_call[0] + min_interval - time.monotonic()
            if wait > 0:
                _sleep(wait)
            last_call[0] = time.monotonic()
        try:
            status, raw = _transport(url, headers or {}, TIMEOUT_SECONDS)
        except (urllib.error.URLError, TimeoutError, OSError):
            logger.warning("%s 연결 실패·시간 초과 attempt=%d", name, attempt + 1)
            last_error = SourceError("unavailable", "연결하지 못했거나 응답 시간이 초과되었습니다.")
            continue
        doc = None
        try:
            doc = json.loads(raw.decode("utf-8")) if raw else None
        except (ValueError, UnicodeDecodeError):
            doc = None
        err = classify(status, doc, raw) if classify else None
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


def _parse_date(value):
    """'2026-10-01 09:00:00', '20261001' → date."""
    m = re.match(r"^(\d{4})[-.]?(\d{2})[-.]?(\d{2})", str(value or "").strip())
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
    except ValueError:
        return None


# ---------- KOTRA ----------
KOTRA_URL = "https://apis.data.go.kr/B410001/kotra_overseasMarketNews/ovseaMrktNews/ovseaMrktNews"
KOTRA_PAGE_SIZE = 100
KOTRA_MAX_PAGES = 3
# 공공데이터포털 공통 오류 코드 중 인증·권한·기한 관련(반복 호출하지 않음)
_KOTRA_AUTH_CODES = {"20", "30", "31", "32"}
_KOTRA_LIMIT_CODES = {"22"}


def _kotra_key():
    return os.environ.get(ENV_DATA_GO_KR_KEY, "").strip()


def _kotra_classify(status, doc, raw):
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


def fetch_kotra(start, end, collected_at):
    """브라질 해외시장뉴스. start·end: date. 반환 (items, coverage)."""
    key = _kotra_key()
    if not key:
        raise SourceError("config", "공공데이터포털 서비스키(%s)가 서버 환경변수에 없습니다. 서버를 실행하는 환경에 설정한 뒤 "
                                    "서버를 다시 시작해 주세요(.env.example은 양식 파일이라 읽지 않습니다)." % ENV_DATA_GO_KR_KEY)
    # 포털은 인코딩 키·디코딩 키를 함께 발급합니다. 이미 인코딩된 키(%)는 다시 인코딩하지 않습니다.
    key_param = key if "%" in key else urllib.parse.quote(key, safe="")
    out = []
    policy = USAGE["kotra"]
    for page in range(1, KOTRA_MAX_PAGES + 1):
        query = urllib.parse.urlencode({"type": "json", "numOfRows": KOTRA_PAGE_SIZE, "pageNo": page,
                                        "search1": "브라질", "search4": start.strftime("%Y%m%d"), "search7": end.strftime("%Y%m%d")})
        doc = _get_json("KOTRA", KOTRA_URL + "?serviceKey=" + key_param + "&" + query, classify=_kotra_classify)
        items, total = _kotra_items(doc)
        for it in items:
            if not isinstance(it, dict):
                continue
            title = _clean(it.get("newsTitl"))
            url = safe_url(it.get("kotraNewsUrl"))
            if not title or not url:
                continue  # 제목이 없거나 http(s) 원문 주소가 아니면 표시하지 않음
            published = _parse_date(it.get("othbcDt"))
            body = _clean(it.get("newsBdt"))
            text_meta = " ".join(_clean(it.get(k)) for k in ("kwrd", "indstCl", "cmdltNmKorn", "cmdltNmEng", "hsCdNm"))
            out.append(NewsItem(
                id="", source="kotra", source_name="KOTRA 해외시장뉴스" + (" · " + _clean(it.get("ovrofInfo")) if it.get("ovrofInfo") else ""),
                title=title, url=url, published=published.isoformat() if published else None, collected_at=collected_at,
                # 요약은 KOTRA가 제공한 문장을 자르지 않고 그대로 둡니다(변경금지 조건, 자동 발췌 금지).
                language="ko", excerpt=_clean(it.get("cntntSumar")), access="full_text" if body else "title_only",
                usage_note=policy["note"], ai_input=policy["ai_input"], pdf_text=policy["pdf_text"],
                outlet="KOTRA", copyright_policy=_clean(it.get("dataType")) or None,
                brazil_context="브라질" in _clean(it.get("natn")),
                body=(body + " " + text_meta).strip(),
            ))
        if total is None or page * KOTRA_PAGE_SIZE >= total or not items:
            break
    coverage = {"requested_from": start.isoformat(), "requested_to": end.isoformat(),
                "searched_from": start.isoformat(), "searched_to": end.isoformat(), "missing": None, "truncated": False}
    return out, coverage


# ---------- GDELT ----------
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
# 공식 안내는 "최근 3개월(롤링)만 검색"이지만, 2026-10-26 실제 호출에서 120~150일 전 구간도 결과가 나왔습니다.
# 그래서 요청 기간(기본 6개월)을 92일 이하 구간으로 나눠 최근 구간부터 모두 조회하고, 구간별 성공·실패·건수를 기록합니다.
# 공식 안내 범위(90일)를 넘는 구간은 coverage에 표시해 '0건'이 실제로 기사가 없다는 뜻인지 보장하지 않음을 알립니다.
GDELT_WINDOW_DAYS = 92
GDELT_DOCUMENTED_DAYS = 90
GDELT_MAX_RECORDS = 250           # artlist 공식 최대
GDELT_MIN_INTERVAL = 6.0          # 429 안내 문구 "5초에 1회" + 여유
GDELT_RETRY_WAITS = (10.0, 20.0)  # 429·일시 오류 재시도 간격(안내 간격의 2배 이상)
GDELT_SPLIT_DEPTH = 1             # 결과가 250건 상한이면 기간을 반으로 나눠 1번 더 조회
GDELT_TIME_BUDGET = 180.0         # GDELT 수집 전체 시간 상한(초). 넘으면 남은 구간은 '시간 상한'으로 기록
_gdelt_last = [0.0]
_gdelt_lock = threading.Lock()
_monotonic = time.monotonic


def _gdelt_classify(status, doc, raw):
    if status == 429:
        return SourceError("rate_limited", "GDELT 호출 제한(5초에 1회)에 걸렸습니다.")
    if status == 200 and doc is None and raw:
        # 질의 오류 등은 200과 일반 텍스트로 옵니다(예: 너무 짧은 검색어). 원문은 로그에 남기지 않습니다.
        return SourceError("bad_response", "GDELT가 JSON이 아닌 응답을 보냈습니다(검색어·기간 오류일 수 있음).")
    if status == 200 and isinstance(doc, dict) and doc and not isinstance(doc.get("articles", []), list):
        return SourceError("bad_response", "GDELT 응답 형식이 예상과 다릅니다.")
    return None


def _seen_at(value):
    """GDELT seendate('20261001T101500Z') → '2026-10-01 10:15 UTC'. 형식이 다르면 None."""
    m = re.match(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$", str(value or "").strip())
    if not m:
        return None
    return "%s-%s-%s %s:%s UTC" % m.group(1, 2, 3, 4, 5)


def gdelt_windows(start, end):
    """[start, end]를 GDELT_WINDOW_DAYS 이하 구간으로 나눕니다. 최근 구간이 먼저."""
    out, cur_end = [], end
    while cur_end >= start:
        cur_start = max(start, cur_end - timedelta(days=GDELT_WINDOW_DAYS - 1))
        out.append((cur_start, cur_end))
        cur_end = cur_start - timedelta(days=1)
    return out


def _gdelt_call(q, start_dt, end_dt):
    url = GDELT_URL + "?" + urllib.parse.urlencode({
        "query": q, "mode": "artlist", "format": "json", "maxrecords": GDELT_MAX_RECORDS, "sort": "datedesc",
        "startdatetime": start_dt.strftime("%Y%m%d%H%M%S"), "enddatetime": end_dt.strftime("%Y%m%d%H%M%S")})
    doc = _get_json("GDELT", url, classify=_gdelt_classify, min_interval=GDELT_MIN_INTERVAL,
                    last_call=_gdelt_last, retry_waits=GDELT_RETRY_WAITS)
    return (doc or {}).get("articles") or []


def _gdelt_item(it, collected_at):
    if not isinstance(it, dict):
        return None
    link = safe_url(it.get("url"))
    title = _clean(it.get("title"))
    if not link or not title:
        return None  # 필수 필드(URL·제목)가 없으면 버림
    policy = USAGE["gdelt"]
    domain = _clean(it.get("domain")) or urllib.parse.urlsplit(link).netloc
    country = _clean(it.get("sourcecountry")) or None
    return NewsItem(
        id="", source="gdelt", source_name="GDELT · " + domain, title=title, url=link, published=None,
        collected_at=collected_at, language=_clean(it.get("language")) or None, excerpt="",
        access=policy["access"], usage_note=policy["note"], ai_input=policy["ai_input"],
        pdf_text=policy["pdf_text"], seen_at=_seen_at(it.get("seendate")), outlet=domain,
        source_country=country, brazil_context=(country or "").lower() == "brazil",
    )


def fetch_gdelt(start, end, collected_at, queries=None, today=None):
    """반환 (items, coverage). start·end: date. 구간·검색어별로 조회하고 실패한 구간은 coverage.missing에 남깁니다.
    모든 조회가 실패하면 마지막 오류를 올립니다(이전 자료 대체 판단은 collect가 함)."""
    today = today or end
    queries = list(queries or GDELT_QUERIES)
    out, truncated, windows, last_error, any_ok = [], False, [], None, False
    started, skip_reason = _monotonic(), None
    with _gdelt_lock:
        for w_from, w_to in gdelt_windows(start, end):
            rec = {"from": w_from.isoformat(), "to": w_to.isoformat(), "count": 0, "failed_queries": 0,
                   "skipped_queries": 0, "error": None,
                   "beyond_documented": (today - w_from).days > GDELT_DOCUMENTED_DAYS}
            for q in queries:
                if skip_reason is None and _monotonic() - started > GDELT_TIME_BUDGET:
                    skip_reason = "수집 시간 상한"
                if skip_reason:
                    rec["skipped_queries"] += 1
                    continue
                pending = [(datetime(w_from.year, w_from.month, w_from.day),
                            datetime(w_to.year, w_to.month, w_to.day, 23, 59, 59), 0)]
                seen = set()
                try:
                    while pending:
                        ws, we, depth = pending.pop(0)
                        arts = _gdelt_call(q, ws, we)
                        any_ok = True
                        if len(arts) >= GDELT_MAX_RECORDS:
                            # 상한에 걸린 결과도 먼저 담아 두고 반으로 나눠 다시 조회(나눈 조회가 실패해도 받은 결과는 유지)
                            if depth < GDELT_SPLIT_DEPTH:
                                mid = ws + (we - ws) / 2
                                pending += [(ws, mid, depth + 1), (mid + timedelta(seconds=1), we, depth + 1)]
                            else:
                                truncated = True
                        for a in arts:
                            item = _gdelt_item(a, collected_at)
                            if item and item.url not in seen:
                                seen.add(item.url)
                                out.append(item)
                                rec["count"] += 1
                except SourceError as err:
                    rec["failed_queries"] += 1
                    rec["error"] = err.kind
                    last_error = err
                    if err.kind == "rate_limited":
                        skip_reason = "호출 한도"  # 재시도 후에도 한도 → 남은 조회로 한도를 더 쓰지 않음
            n = len(queries)
            done = n - rec["failed_queries"] - rec["skipped_queries"]
            rec["status"] = ("ok" if done == n
                             else "partial" if done or rec["count"]
                             else "failed" if rec["failed_queries"]
                             else "skipped")
            windows.append(rec)
    if not any_ok:
        if last_error:
            raise last_error
        raise SourceError("unavailable", "GDELT 수집 시간 상한을 넘어 조회하지 못했습니다.")
    missing = []
    for w in windows:
        if w["status"] != "ok":
            reason = {"failed": "조회 실패(%s)" % (w["error"] or "?"), "skipped": "%s으로 조회하지 않음" % skip_reason,
                      "partial": "검색어 %d개 중 %d개 실패·%d개 미조회" % (len(queries), w["failed_queries"], w["skipped_queries"])}[w["status"]]
            missing.append({"from": w["from"], "to": w["to"], "reason": reason})
    ok_windows = [w for w in windows if w["status"] in ("ok", "partial")]
    coverage = {"requested_from": start.isoformat(), "requested_to": end.isoformat(),
                "searched_from": min(w["from"] for w in ok_windows), "searched_to": max(w["to"] for w in ok_windows),
                "windows": windows, "missing": missing, "truncated": truncated,
                "documented_days": GDELT_DOCUMENTED_DAYS}
    return out, coverage


# ---------- 정리: 관련성·중복 ----------
_TRACKING_PARAMS = ("utm", "fbclid", "gclid")


def _norm_url(url):
    """중복 판단용 URL 키. 추적용 파라미터(utm*·fbclid·gclid)만 빼고 쿼리는 유지합니다.
    KOTRA처럼 기사 구분이 쿼리(dataIdx)에만 있는 주소를 같은 기사로 묶지 않기 위해서입니다."""
    p = urllib.parse.urlsplit(url.strip().lower())
    host = p.netloc[4:] if p.netloc.startswith("www.") else p.netloc
    query = sorted((k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)
                   if not k.startswith(_TRACKING_PARAMS))
    return host + p.path.rstrip("/") + ("?" + urllib.parse.urlencode(query) if query else "")


def _norm_title(title):
    return re.sub(r"[\W_]+", "", title.lower())


def _has(text, word):
    # 영문 짧은 단어(dty, t2t 등)는 단어 경계로, 나머지는 포함 여부로 봅니다.
    if re.fullmatch(r"[a-z0-9\-]{1,4}", word):
        return re.search(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])", text) is not None
    return word in text


def score_item(item):
    """(점수, 주제 목록). 제품·산업 주제 1개 이상 + 브라질 관련성이 모두 있어야 선정. 무역 정책·브라질 단어만으로는 0."""
    text = " ".join([item.title, item.excerpt, item.body or ""]).lower()
    topics = [name for name, words in TOPICS.items() if any(_has(text, w) for w in words)]
    if not any(t in PRODUCT_TOPICS for t in topics):
        return 0.0, topics
    if not (item.brazil_context or any(_has(text, w) for w in BRAZIL_WORDS)):
        return 0.0, topics
    hits = sum(1 for words in TOPICS.values() for w in words if _has(text, w))
    score = 2.0 * len(topics) + 0.1 * hits
    if any(_has(item.title.lower(), w) for t in PRODUCT_TOPICS for w in TOPICS[t]):
        score += 1.0
    if item.access == "full_text":
        score += 0.5
    return round(score, 2), topics


def _date_key(it):
    d = it.published or (it.seen_at or "")[:10]
    return int(d.replace("-", "")) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d or "") else 0


def select_items(items, limit=MAX_ITEMS):
    """URL·제목 중복 제거 후 관련성 상위 limit건. 같은 기사면 원문 자료(KOTRA)를 남깁니다."""
    best = {}
    order = {"full_text": 0, "title_only": 1}
    for it in items:
        it.score, it.topics = score_item(it)
        if it.score <= 0:
            continue
        keys = {"u:" + _norm_url(it.url), "t:" + _norm_title(it.title)}
        existing = next((best[k] for k in keys if k in best), None)
        if existing is not None:
            better = (order.get(it.access, 9), -len(it.excerpt)) < (order.get(existing.access, 9), -len(existing.excerpt))
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
    # 관련성 높은 순, 같으면 최근 순(게시일 또는 GDELT 최초 발견일)
    unique.sort(key=lambda x: (-x.score, -_date_key(x)))
    picked = unique[:limit]
    for i, it in enumerate(picked, 1):
        it.id = "N%d" % i
    return picked, len(unique)


def other_items(raw, picked, limit=MAX_OTHER_ITEMS):
    """관련성 기준(제품·산업 주제 + 브라질)에 들지 않았지만 수집된 기사. 화면 참고용이며 AI 입력에 넣지 않습니다.
    URL·제목 중복과 선정 기사는 빼고 최근 순으로 limit건. id는 'R' 번호."""
    seen = set()
    for it in picked:
        seen |= {"u:" + _norm_url(it.url), "t:" + _norm_title(it.title)}
    out = []
    for it in sorted(raw, key=lambda x: -_date_key(x)):
        keys = {"u:" + _norm_url(it.url), "t:" + _norm_title(it.title)}
        if keys & seen:
            continue
        seen |= keys
        out.append(it)
    out = out[:limit]
    for i, it in enumerate(out, 1):
        it.id = "R%d" % i
    return out


# ---------- 전체 수집 ----------
# 자동으로 호출하는 출처. 일반 뉴스 공급자는 사용자 선택 전까지 비워 둡니다(GDELT 자동 호출 중단, 2026-10-26).
PROVIDERS = {"kotra": fetch_kotra}
GENERAL_NEWS_PROVIDERS = ("gdelt",)  # PROVIDERS에 이 중 하나가 있으면 일반 뉴스 공급자가 연결된 상태
SOURCE_LABELS = {"kotra": "KOTRA 해외시장뉴스", "gdelt": "GDELT (일반 뉴스 검색)", "kita": "한국무역협회(KITA)",
                 "general": "일반 뉴스"}
GENERAL_PENDING_MESSAGE = ("GDELT는 호출 간격 제한(5초에 1회)으로 수집이 계속 실패해 자동 호출을 중단했습니다. "
                           "새 무료 뉴스 공급자를 선택하기 전까지 일반 뉴스는 수집하지 않습니다(오류 아님).")


def has_general_provider():
    """일반 뉴스 공급자가 자동 수집에 연결돼 있는지. 없으면 근거 보강용 넓은 검색도 하지 않습니다."""
    return any(name in PROVIDERS for name in GENERAL_NEWS_PROVIDERS)
_STATUS_TEXT = {
    "config": "설정 필요", "auth": "인증·권한 확인 필요", "rate_limited": "호출 한도", "unavailable": "연결 실패·시간 초과",
    "bad_response": "응답 해석 실패", "rejected": "요청 거부",
}
_RETRY_HELP = {
    "rate_limited": "1~2분 뒤 '근거 자료 다시 불러오기'를 눌러 주세요.",
    "unavailable": "잠시 후 '근거 자료 다시 불러오기'를 눌러 주세요.",
    "bad_response": "잠시 후 다시 시도하고, 계속되면 담당자에게 알려 주세요.",
}

# 출처별 캐시(서버 메모리). 키 = (출처, 검색어 묶음, 요청 시작일, 요청 종료일). 같은 날(KST)은 그대로 재사용하고,
# 날짜가 지난 캐시는 새 조회가 실패했을 때만 '이전 자료'로 표시합니다. 정해진 시각에 스스로 수집하는 기능은 없습니다.
_cache_lock = threading.Lock()
_provider_cache = {}


def clear_cache():
    with _cache_lock:
        _provider_cache.clear()


def _copy(items):
    return [NewsItem(**{**it.__dict__, "topics": list(it.topics)}) for it in items]


def collect(months=DEFAULT_MONTHS, widen=False, today=None, refresh=False):
    """모든 출처에서 수집. 일부 실패해도 나머지 결과를 돌려줍니다.

    반환: {"window", "items": [NewsItem], "other_items": [NewsItem], "candidates", "raw_count", "sources": [상태],
           "widened", "collected_at"}. other_items는 관련성 기준 밖의 수집 기사(화면 참고용, AI 입력 아님).
    widen=True: 근거 보강용 넓은 검색어 추가(호출하는 쪽에서 1회로 제한).
    refresh=True: 오늘 캐시를 쓰지 않고 다시 받습니다(실패하면 이전 자료로 대체).
    """
    today = today or now_kst().date()
    start = today - timedelta(days=round(months * 30.4))
    collected_at = now_kst().isoformat(timespec="seconds")
    raw, statuses = [], []
    for name, fn in PROVIDERS.items():
        started = time.monotonic()
        queries = tuple(GDELT_QUERIES + (GDELT_QUERIES_WIDE if widen else [])) if name == "gdelt" else ()
        key = (name, queries, start.isoformat(), today.isoformat())
        with _cache_lock:
            cached = _provider_cache.get(key)
        base = {"source": name, "label": SOURCE_LABELS[name], "usage_note": USAGE[name]["note"],
                "queries": list(queries)}
        if USAGE[name]["cache"] and not refresh and cached and cached["day"] == today.isoformat():
            raw.extend(_copy(cached["items"]))
            statuses.append({**base, "state": "ok", "count": len(cached["items"]), "message": None, "seconds": 0,
                             "status_text": ("결과 없음" if not cached["items"] else "연결됨") + " · 오늘 받은 자료 재사용",
                             "collected_at": cached["collected_at"], "stale": False, "coverage": cached["coverage"]})
            continue
        try:
            got, coverage = fn(start, today, collected_at, list(queries)) if name == "gdelt" else fn(start, today, collected_at)
            if USAGE[name]["cache"]:
                with _cache_lock:
                    _provider_cache[key] = {"day": today.isoformat(), "items": _copy(got), "collected_at": collected_at,
                                            "coverage": coverage}
            raw.extend(got)
            statuses.append({**base, "state": "ok", "count": len(got), "message": None,
                             "status_text": "결과 없음" if not got else "연결됨",
                             "seconds": round(time.monotonic() - started, 1), "collected_at": collected_at,
                             "stale": False, "coverage": coverage})
        except SourceError as err:
            message = err.message + (" " + _RETRY_HELP[err.kind] if err.kind in _RETRY_HELP else "")
            if USAGE[name]["cache"] and cached:
                # 새 조회 실패 → 같은 조건의 이전 자료를 표시(수집 시각·이전 자료 사용 표시)
                raw.extend(_copy(cached["items"]))
                statuses.append({**base, "state": err.kind, "count": len(cached["items"]),
                                 "status_text": _STATUS_TEXT.get(err.kind, "실패") + " · 이전 자료 사용",
                                 "message": message + " %s에 받은 자료를 대신 표시합니다." % cached["collected_at"],
                                 "seconds": round(time.monotonic() - started, 1), "collected_at": cached["collected_at"],
                                 "stale": True, "coverage": cached["coverage"]})
            else:
                statuses.append({**base, "state": err.kind, "status_text": _STATUS_TEXT.get(err.kind, "실패"), "count": 0,
                                 "message": message, "seconds": round(time.monotonic() - started, 1),
                                 "collected_at": None, "stale": False, "coverage": None})
    if not has_general_provider():
        statuses.append({"source": "general", "label": SOURCE_LABELS["general"], "state": "pending",
                         "status_text": "공급자 선택 대기", "count": 0, "message": GENERAL_PENDING_MESSAGE, "usage_note": None,
                         "seconds": 0, "queries": [], "collected_at": None, "stale": False, "coverage": None})
    statuses.append({"source": "kita", "label": SOURCE_LABELS["kita"], "state": "pending", "status_text": "연결 확인 중",
                     "count": 0, "message": "시장뉴스·연구보고서를 자동으로 받을 공식 API·RSS를 확인하지 못했습니다(공공데이터포털 '한국무역협회' 오픈 API 0건, "
                                            "kita.net 저작권 정책상 상업적 이용·무단 자동 수집 금지, 2026-10-26). 제공·제휴는 KITA 문의가 필요합니다.",
                     "usage_note": None, "seconds": 0, "queries": [], "collected_at": None, "stale": False, "coverage": None})
    items, candidates = select_items(raw)
    others = other_items(raw, items)
    gd = next((s for s in statuses if s["source"] == "gdelt"), None)
    gd_cov = gd and gd.get("coverage")
    notes = []
    if gd and not gd_cov:
        notes.append("일반 뉴스(GDELT)를 조회하지 못해 요청 기간 %s~%s 전체의 일반 뉴스를 확보하지 못했습니다." % (start.isoformat(), today.isoformat()))
    if gd_cov:
        for m in gd_cov.get("missing") or []:
            notes.append("일반 뉴스(GDELT) %s~%s: %s. 이 기간의 일반 뉴스는 확보하지 못했거나 일부만 확보했습니다." % (m["from"], m["to"], m["reason"]))
        beyond = [w for w in gd_cov.get("windows") or [] if w["beyond_documented"] and w["status"] != "failed"]
        if beyond:
            notes.append("GDELT 공식 안내는 최근 %d일 검색만 명시합니다. 그 이전 구간(%s~%s)은 실제 조회됐지만 검색 범위가 보장되지 않아, 결과가 적거나 0건이어도 기사가 없다는 뜻은 아닙니다." % (
                gd_cov["documented_days"], min(w["from"] for w in beyond), max(w["to"] for w in beyond)))
        if gd_cov.get("truncated"):
            notes.append("GDELT 결과가 조회당 최대 250건에 걸린 구간이 있어 일부 기사가 빠졌을 수 있습니다.")
    return {
        "window": {"from": start.isoformat(), "to": today.isoformat(), "months": months, "notes": notes},
        "items": items,
        "other_items": others,
        "candidates": candidates,
        "raw_count": len(raw),
        "sources": statuses,
        "widened": widen,
        "collected_at": collected_at,
    }
