"""홈 환율 카드: USD/KRW(한국수출입은행), USD/BRL(BCB PTAX), BRL/KRW(USD 경유 계산값).

- 공식 고시값만 씁니다. 값을 추정하거나 AI로 보충하지 않습니다.
- 주말·공휴일에는 최근 고시일까지 최대 7일 거슬러 찾고, 실제 고시일을 함께 돌려줍니다.
- 전일 대비는 직전 고시일 값을 확보한 경우에만 코드로 계산합니다.
- 환율 소스별로 따로 가져오고 실패를 나눕니다. 실패하면 이전 값을 보여 주지 않고 "확인 불가"로 둡니다.
- 서버 메모리 캐시: 소스별 결과 1시간, 수출입은행 지난 날짜 응답은 날짜별로 보관합니다(고시 후 바뀌지 않는 값).
"""
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from time import monotonic
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

USER_AGENT = "fionex/0.1 (internal dashboard)"
TIMEOUT_SECONDS = 10
CACHE_SECONDS = 60 * 60          # 정상 결과(하루 1회 고시, 수출입은행은 영업일 11시 전후 갱신)
FAILURE_CACHE_SECONDS = 5 * 60   # 실패·설정 필요 결과. 재시도 버튼(refresh)은 바로 다시 조회
LOOKBACK_DAYS = 7          # 최근 고시값을 찾는 최대 기간
PREVIOUS_LOOKBACK_DAYS = 7  # 최근 고시일 이전에서 직전 고시값을 찾는 최대 기간
SOURCES = ("usd_krw", "usd_brl")

# 한국수출입은행 현재환율 API(개발명세 2026-10-25 확인). 비영업일·영업일 11시 이전에는 null 반환.
EXIM_URL = "https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON"
EXIM_KEY_ENV = "KOREAEXIM_API_KEY"  # 확정(2026-10-25). 값은 .env에만 두고 코드·로그·화면에 남기지 않습니다.
EXIM_RESULT_ERRORS = {2: "invalid_response", 3: "access_denied", 4: "rate_limited"}  # RESULT 1 = 성공

# BCB PTAX OData(공식 명세 2026-10-25 확인). 날짜 MM-DD-YYYY, cotacaoVenda = 달러 매도 PTAX(BRL/USD).
PTAX_URL = ("https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
            "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)")

SOURCE_INFO = {
    "usd_krw": {"pair": "USD/KRW", "source": "koreaexim", "source_name": "한국수출입은행 매매기준율", "tz": "Asia/Seoul"},
    "usd_brl": {"pair": "USD/BRL", "source": "bcb_ptax", "source_name": "Banco Central do Brasil PTAX 매도",
                "tz": "America/Sao_Paulo"},
}

ERROR_MESSAGES = {
    "key_missing": "한국수출입은행 인증키(KOREAEXIM_API_KEY)가 설정되지 않았습니다.",
    "access_denied": "인증키를 확인할 수 없습니다(인증 오류).",
    "rate_limited": "일일 호출 한도에 도달했습니다.",
    "timeout": "응답 시간이 초과되었습니다.",
    "fetch_failed": "환율을 불러오지 못했습니다.",
    "invalid_response": "응답 형식을 확인할 수 없습니다.",
    "no_recent_rate": f"최근 {LOOKBACK_DAYS}일 안에 고시된 환율을 찾지 못했습니다.",
}

# 소스 → {"result": 마지막 결과, "expires"}. 성공·실패 모두 담고, 실패는 이전 값 없이 "확인 불가"로 보입니다.
_cache = {}
# 수출입은행 날짜(YYYYMMDD) → 매매기준율 Decimal 또는 None(고시 없음). 오늘 날짜는 넣지 않습니다(11시 전후 갱신).
_exim_days = {}


class FxError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def get_fx(refresh=None):
    """{"usd_krw": {...}, "usd_brl": {...}, "brl_krw": {...} | None}

    소스 결과: status ok|error|not_configured, rate, date(고시일), previous{rate,date}|None, change_pct|None,
    source, source_name, fetched_at[, error{code,message,retryable}]
    refresh에 소스 이름을 주면 그 소스만 캐시를 무시하고 다시 가져옵니다.
    """
    now = monotonic()
    data = {}
    for name in SOURCES:
        cached = _cache.get(name)
        if name != refresh and cached and cached["expires"] > now:
            data[name] = cached["result"]
            continue
        result = _load(name)
        ttl = CACHE_SECONDS if result["status"] == "ok" else FAILURE_CACHE_SECONDS
        _cache[name] = {"result": result, "expires": monotonic() + ttl}
        data[name] = result
    data["brl_krw"] = derive_brl_krw(data["usd_krw"], data["usd_brl"])
    return data


def derive_brl_krw(usd_krw, usd_brl):
    """두 공식 고시값이 모두 있을 때만 BRL/KRW = USD/KRW ÷ USD/BRL. 하나라도 없으면 None."""
    if usd_krw.get("status") != "ok" or usd_brl.get("status") != "ok":
        return None
    rate = (Decimal(str(usd_krw["rate"])) / Decimal(str(usd_brl["rate"]))).quantize(Decimal("0.0001"), ROUND_HALF_UP)
    return {
        "rate": float(rate),
        "derived": True,
        "method": "USD/KRW ÷ USD/BRL",
        "usd_krw_date": usd_krw["date"],
        "usd_brl_date": usd_brl["date"],
    }


def change_pct(current, previous):
    """((현재 - 이전) / 이전) × 100, 소수 둘째 자리."""
    current, previous = Decimal(str(current)), Decimal(str(previous))
    if previous <= 0:
        return None
    return float(((current - previous) / previous * 100).quantize(Decimal("0.01"), ROUND_HALF_UP))


def _load(name):
    info = SOURCE_INFO[name]
    result = {"pair": info["pair"], "source": info["source"], "source_name": info["source_name"],
              "fetched_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")}
    today = _today(info["tz"])
    try:
        latest, previous = (_load_usd_krw if name == "usd_krw" else _load_usd_brl)(today)
    except FxError as err:
        if err.code == "key_missing":
            status = "not_configured"
        else:
            status = "error"
            logger.warning("환율 조회 실패(%s): %s", name, err.code)
        result.update(status=status, rate=None, date=None, previous=None, change_pct=None,
                      error={"code": err.code, "message": ERROR_MESSAGES[err.code],
                             "retryable": err.code not in ("key_missing", "access_denied", "rate_limited")})
        return result
    except Exception:  # 예상하지 못한 오류도 다른 소스에 영향을 주지 않게 합니다.
        logger.exception("환율 조회 중 오류(%s)", name)
        result.update(status="error", rate=None, date=None, previous=None, change_pct=None,
                      error={"code": "fetch_failed", "message": ERROR_MESSAGES["fetch_failed"], "retryable": True})
        return result
    result.update(
        status="ok",
        rate=float(latest[1]),
        date=latest[0].isoformat(),
        previous={"rate": float(previous[1]), "date": previous[0].isoformat()} if previous else None,
        change_pct=change_pct(latest[1], previous[1]) if previous else None,
    )
    return result


def _today(tz):
    # 소스 기준 시간대의 오늘(수출입은행 서울, PTAX 브라질리아)
    return datetime.now(ZoneInfo(tz)).date()


def _http_get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    host = urllib.parse.urlsplit(url).netloc  # 쿼리(인증키 포함 가능)는 로그에 남기지 않습니다.
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as res:
            return json.load(res)
    except urllib.error.HTTPError as err:
        logger.warning("환율 요청 실패(%s): HTTP %s", host, err.code)
        raise FxError("access_denied" if err.code in (401, 403) else "fetch_failed") from None
    except urllib.error.URLError as err:
        logger.warning("환율 요청 실패(%s): %s", host, type(err.reason).__name__)
        raise FxError("timeout" if isinstance(err.reason, TimeoutError) else "fetch_failed") from None
    except TimeoutError:
        raise FxError("timeout") from None
    except OSError:
        raise FxError("fetch_failed") from None
    except ValueError:
        raise FxError("invalid_response") from None


def _positive_decimal(value):
    try:
        number = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() and number > 0 else None


# ---------- USD/KRW: 한국수출입은행 (날짜별 조회) ----------
def _load_usd_krw(today):
    key = os.environ.get(EXIM_KEY_ENV, "").strip()
    if not key:
        raise FxError("key_missing")
    latest = _find_exim(key, today, LOOKBACK_DAYS, today)
    if latest is None:
        raise FxError("no_recent_rate")
    previous = _find_exim(key, latest[0] - timedelta(days=1), PREVIOUS_LOOKBACK_DAYS, today)
    return latest, previous


def _find_exim(key, start, days, today):
    """start부터 하루씩 거슬러 days일 안에서 고시값이 있는 첫 날 (date, Decimal). 없으면 None."""
    for offset in range(days):
        day = start - timedelta(days=offset)
        rate = _exim_rate(key, day, today)
        if rate is not None:
            return day, rate
    return None


def _exim_rate(key, day, today):
    stamp = day.strftime("%Y%m%d")
    if stamp in _exim_days:
        return _exim_days[stamp]
    query = urllib.parse.urlencode({"authkey": key, "searchdate": stamp, "data": "AP01"})
    rate = parse_exim(_http_get_json(EXIM_URL + "?" + query))
    if day < today:  # 지난 날짜는 바뀌지 않으므로 보관. 오늘은 11시 전후 갱신이라 보관하지 않음.
        _exim_days[stamp] = rate
        _prune_exim_days(today)
    return rate


def parse_exim(data):
    """명세 형식 [{"result", "cur_unit", "deal_bas_r", ...}] → USD 매매기준율 Decimal, 고시 없음이면 None."""
    if not isinstance(data, list):
        raise FxError("invalid_response")
    for item in data:
        if not isinstance(item, dict):
            raise FxError("invalid_response")
        result = item.get("result")
        if result != 1:
            raise FxError(EXIM_RESULT_ERRORS.get(result, "invalid_response"))
        if item.get("cur_unit") == "USD":
            return _positive_decimal(item.get("deal_bas_r"))
    return None  # 빈 목록 = 비영업일 또는 고시 전


def _prune_exim_days(today):
    oldest = (today - timedelta(days=60)).strftime("%Y%m%d")
    for stamp in [s for s in _exim_days if s < oldest]:
        del _exim_days[stamp]


# ---------- USD/BRL: BCB PTAX (기간 1회 조회) ----------
def _load_usd_brl(today):
    start = today - timedelta(days=LOOKBACK_DAYS + PREVIOUS_LOOKBACK_DAYS)
    query = urllib.parse.urlencode({
        "@dataInicial": "'" + start.strftime("%m-%d-%Y") + "'",
        "@dataFinalCotacao": "'" + today.strftime("%m-%d-%Y") + "'",
        "$format": "json",
    }, safe="@$'")
    rates = parse_ptax(_http_get_json(PTAX_URL + "?" + query))
    recent = [r for r in rates if r[0] > today - timedelta(days=LOOKBACK_DAYS) and r[0] <= today]
    if not recent:
        raise FxError("no_recent_rate")
    latest = recent[-1]
    earlier = [r for r in rates if r[0] < latest[0] and r[0] >= latest[0] - timedelta(days=PREVIOUS_LOOKBACK_DAYS)]
    return latest, (earlier[-1] if earlier else None)


def parse_ptax(data):
    """{"value": [{"cotacaoVenda", "dataHoraCotacao"}]} → 날짜순 [(date, Decimal)]. 같은 날짜는 마지막 시각 값."""
    try:
        rows = data["value"]
    except (KeyError, TypeError):
        raise FxError("invalid_response") from None
    if not isinstance(rows, list):
        raise FxError("invalid_response")
    by_day = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        stamp = str(row.get("dataHoraCotacao") or "")
        rate = _positive_decimal(row.get("cotacaoVenda"))
        try:
            day = date.fromisoformat(stamp[:10])
        except ValueError:
            continue
        if rate is None:
            continue
        if day not in by_day or stamp > by_day[day][0]:
            by_day[day] = (stamp, rate)
    return [(day, by_day[day][1]) for day in sorted(by_day)]
