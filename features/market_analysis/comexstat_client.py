"""ComexStat(브라질 산업통상부) 공개 API 호출. 인증키가 필요하지 않습니다.

2026-10-25 실제 호출로 확인한 동작
- POST /general 의 period는 "연도 범위 × 월 범위"로 해석됩니다. 2024-01~2026-09를 요청하면
  매년 1~9월만 돌아오고, 2022-10~2026-09는 빈 목록이 됩니다. 그래서 항상 YYYY-01~YYYY-12
  전체 연도로 요청하고 필요한 월은 service에서 잘라냅니다.
- 금액(metricFOB, USD)·순중량(metricKG, kg)은 문자열로 옵니다. 국가는 포르투갈어 이름만 옵니다.
- 짧은 간격(약 30초)의 연속 호출에 HTTP 429가 반환됩니다. 공식 한도 수치는 확인하지 못했습니다.
  응답 문구는 "10초 후 재시도"이지만 실제로는 더 오래 걸릴 때가 있었습니다.

호출은 프로세스 안에서 하나씩 보내고(lock), 호출 사이 최소 간격을 둡니다.
회복 가능한 실패(429·5xx·연결 실패·시간 초과)만 최대 2회 다시 시도합니다.
"""
import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

BASE_URL = "https://api-comexstat.mdic.gov.br"
SITE_URL = "https://comexstat.mdic.gov.br/"
USER_AGENT = "fionex-market-analysis/1.0"
TIMEOUT_SECONDS = 20.0
# 프로젝트 초기 설정(2026-10-25 관측 기반). 공급자 공식 한도가 아닙니다.
MIN_INTERVAL_SECONDS = 10.0
RETRY_WAIT_SECONDS = (15.0, 30.0)  # 최초 시도 이후 최대 2회

# 품목코드 체계 → (general 필터 이름, 상세 구분 이름, 코드표 경로, 코드 키, 이름 키)
CODE_SYSTEMS = {
    "ncm": ("ncm", "ncm", "/tables/ncm", "coNcm", "noNCM"),
    "hs6": ("subHeading", "subHeading", "/tables/hs", "subHeadingCode", "subHeading"),
}


class ComexStatError(Exception):
    """사용자에게 보여도 되는 고정 문장만 담습니다. 응답 본문 원문은 보관하지 않습니다."""

    def __init__(self, code, message, http_status, retryable):
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retryable = retryable
        super().__init__(message)


def _rate_limited():
    return ComexStatError(
        "MA_SOURCE_RATE_LIMITED",
        "ComexStat 호출 한도에 걸렸습니다. 1~2분 뒤 '다시 불러오기'를 눌러 주세요.",
        429, True)


def _unavailable():
    return ComexStatError(
        "MA_SOURCE_UNAVAILABLE",
        "ComexStat 서버에 연결하지 못했습니다. 잠시 후 '다시 불러오기'를 눌러 주세요.",
        502, True)


def _bad_response():
    return ComexStatError(
        "MA_SOURCE_BAD_RESPONSE",
        "ComexStat 응답을 해석하지 못했습니다. 잠시 후 다시 시도하고, 계속되면 담당자에게 알려 주세요.",
        502, True)


def _rejected():
    return ComexStatError(
        "MA_SOURCE_REJECTED",
        "ComexStat이 조회 요청을 거부했습니다. 조회 조건을 확인하고, 계속되면 담당자에게 알려 주세요.",
        502, False)


def _transport(method, url, body, timeout):
    """(HTTP 상태, 본문 bytes). 테스트에서 교체합니다."""
    data = None
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as err:
        return err.code, b""


_lock = threading.Lock()
_last_call = [0.0]
_sleep = time.sleep
_monotonic = time.monotonic


def _request(method, path, body=None, retry=True):
    """retry=False면 실패해도 다시 시도하지 않습니다(점검 확인처럼 실패 시 저장 자료로 대신할 수 있는 호출)."""
    url = BASE_URL + path
    with _lock:
        last_error = None
        for attempt in range(len(RETRY_WAIT_SECONDS) + 1 if retry else 1):
            if attempt:
                _sleep(RETRY_WAIT_SECONDS[attempt - 1])
            wait = _last_call[0] + MIN_INTERVAL_SECONDS - _monotonic()
            if wait > 0:
                _sleep(wait)
            _last_call[0] = _monotonic()
            try:
                status, raw = _transport(method, url, body, TIMEOUT_SECONDS)
            except (urllib.error.URLError, TimeoutError, OSError):
                logger.warning("ComexStat 연결 실패 path=%s attempt=%d", path, attempt + 1)
                last_error = _unavailable()
                continue
            if status == 429:
                logger.warning("ComexStat 429 path=%s attempt=%d", path, attempt + 1)
                last_error = _rate_limited()
                continue
            if status >= 500:
                logger.warning("ComexStat %d path=%s attempt=%d", status, path, attempt + 1)
                last_error = _unavailable()
                continue
            if status != 200:
                logger.warning("ComexStat %d path=%s", status, path)
                raise _rejected()
            try:
                doc = json.loads(raw.decode("utf-8"))
                data = doc["data"]
            except (ValueError, KeyError, TypeError, UnicodeDecodeError):
                logger.warning("ComexStat 응답 형식 오류 path=%s", path)
                raise _bad_response() from None
            return data
        raise last_error


def get_latest_month():
    """통계 최신 제공 월. (연, 월, 갱신일 문자열 'YYYY-MM-DD').
    한 번만 시도합니다(재시도 대기 없음): 실패하면 서비스가 이전 값·스냅샷으로 대신하고, 점검 중임을 빨리 알 수 있게."""
    data = _request("GET", "/general/dates/updated", retry=False)
    try:
        return int(data["year"]), int(data["monthNumber"]), str(data["updated"])
    except (KeyError, TypeError, ValueError):
        raise _bad_response() from None


def query_imports(code_system, code, year_from, year_to):
    """브라질 수입, 월별 × 공급국 행 목록. 전체 연도(1~12월) 범위로 요청합니다.

    반환 행: {"year", "month", "country", "fob", "kg", "code_name"}. fob·kg는 int 또는 None(값 없음).
    """
    filter_name, detail_name, _, _, _ = CODE_SYSTEMS[code_system]
    body = {
        "flow": "import",
        "monthDetail": True,
        "period": {"from": "%04d-01" % year_from, "to": "%04d-12" % year_to},
        "filters": [{"filter": filter_name, "values": [code]}],
        "details": ["country", detail_name],
        "metrics": ["metricFOB", "metricKG"],
    }
    data = _request("POST", "/general", body)
    try:
        rows = data["list"]
        return [
            {
                "year": int(r["year"]),
                "month": int(r["monthNumber"]),
                "country": str(r["country"]),
                "fob": _to_int(r.get("metricFOB")),
                "kg": _to_int(r.get("metricKG")),
                "code_name": r.get(detail_name),
            }
            for r in rows
        ]
    except (KeyError, TypeError, ValueError):
        raise _bad_response() from None


def lookup_code(code_system, code):
    """현행 코드표에서 코드 이름(포르투갈어)을 찾습니다. 없으면 None."""
    _, _, path, code_key, name_key = CODE_SYSTEMS[code_system]
    data = _request("GET", path + "?" + urllib.parse.urlencode({"search": code}))
    try:
        for row in data["list"]:
            if str(row.get(code_key)) == code:
                return str(row.get(name_key) or "")
    except (KeyError, TypeError):
        raise _bad_response() from None
    return None


def _to_int(value):
    if value is None or value == "":
        return None
    return int(float(value))
