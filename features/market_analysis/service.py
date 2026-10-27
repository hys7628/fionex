"""시장 분석 service: 입력 검증, ComexStat 조회·캐시, 수치 계산(코드 계산, AI 미사용).

통계(ComexStat)와 함께 조회 묶음(AI 분석 진행 상태)을 관리합니다. AI는 analysis. 뉴스 수집 기능은 2026-10-26 담당자 결정으로 삭제.
- 평균 수입단가 = FOB 금액 합계(USD) ÷ 순중량 합계(kg). 월별·국가별 단가를 단순 평균하지 않습니다.
- 행이 없는 월은 0으로 채우지 않고 '기록 없음'으로 둡니다.
- 단가 '확인 필요': 같은 조회의 단가 중앙값 대비 ½배 미만 또는 2배 초과. 값은 삭제하지 않습니다.
- 공개 통계 캐시는 서버 메모리에만 둡니다(서버 재시작 시 비워짐). 같은 날(KST) 같은 조건은 재사용합니다.
  사용자 입력·결과는 저장하지 않습니다.
"""
import hashlib
import json
import re
import secrets
import statistics
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from features.market_analysis import analysis
from features.market_analysis import comexstat_client as comex
from features.market_analysis.comexstat_client import ComexStatError

KST = timezone(timedelta(hours=9))  # 한국은 서머타임이 없어 고정 오프셋 사용

DEFAULT_CODE_SYSTEM = "ncm"
DEFAULT_CODE = "54023310"  # 폴리에스터 DTY 미염색(2026-10-25 사용자 결정, 수출 신고 코드 확정 아님)
DEFAULT_MONTHS = 36
MAX_MONTHS = 120
MAX_COUNTRIES = 20
FIRST_DATA_YEAR = 1997  # ComexStat 일반 통계 시작 연도
KOREA_CODE = "190"
# 대상 시장(브라질) 자신. 원산지가 브라질인 재수입분은 공급국 목록·순위·선택에서 빼고 전체 수입액(비중 분모)에는 둡니다(2026-10-26 담당자 결정).
BRAZIL_CODE = "105"
TOP_N = 10
OUTLIER_LOW, OUTLIER_HIGH = 0.5, 2.0

CODE_LENGTH = {"ncm": 8, "hs6": 6}
CODE_LABEL = {"ncm": "NCM 8자리", "hs6": "HS 6자리"}
_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")

_DATA_FILE = Path(__file__).resolve().parent / "data" / "countries.json"
_COUNTRIES = json.loads(_DATA_FILE.read_text(encoding="utf-8"))["countries"]
_BY_CODE = {c["code"]: c for c in _COUNTRIES}
_BY_PT = {c["name_pt"]: c for c in _COUNTRIES}


class InputError(Exception):
    """입력란별 오류. fields: {입력 이름: 안내 문장}."""

    code = "MA_INVALID_INPUT"
    http_status = 400

    def __init__(self, fields):
        self.fields = fields
        self.message = "입력값을 확인해 주세요."
        super().__init__(self.message)


@dataclass(frozen=True)
class AnalysisRequest:
    code_system: str
    code: str
    start: int  # 월 번호 = 연 × 12 + (월 − 1)
    end: int
    countries: tuple
    refresh: bool


# ---------- 월 계산 ----------
def month_index(year, month):
    return year * 12 + month - 1


def month_label(index):
    return "%04d-%02d" % (index // 12, index % 12 + 1)


def _parse_month(value):
    m = _MONTH_RE.match(str(value or "").strip())
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        return None
    return month_index(year, month)


def now_kst():
    return datetime.now(KST)


# ---------- 국가 ----------
def country_info(code=None, name_pt=None):
    c = _BY_CODE.get(code) if code is not None else _BY_PT.get(name_pt)
    if c is None:
        return {"code": None, "name_pt": name_pt, "name_ko": None}
    return dict(c)


def country_list():
    """선택 목록: 한국어명이 있는 국가를 먼저, 한국어(없으면 원문) 이름순. 대상 시장 브라질은 공급국이 아니므로 뺍니다."""
    return sorted((dict(c) for c in _COUNTRIES if c["code"] != BRAZIL_CODE),
                  key=lambda c: (c["name_ko"] is None, c["name_ko"] or c["name_pt"]))


# ---------- 캐시 ----------
# 서버 메모리만 씁니다(디스크·DB 저장 없음, 서버를 다시 시작하면 사라짐). 성공한 조회 결과만 담고,
# 조회가 실패하면 기존 캐시를 stale(이전 자료)로 돌려줍니다.
CACHE_TTL_SECONDS = 6 * 3600       # 최신 제공 월·통계 행 재사용 시간(ComexStat은 월 단위로 갱신)
REFRESH_MIN_SECONDS = 10 * 60      # '다시 불러오기'라도 이 시간 안에 받은 자료는 다시 조회하지 않음(호출 한도 보호)
MAX_ROWS_CACHE = 20                # 품목코드별 통계 행 캐시 최대 개수(넘치면 가장 오래 쓰지 않은 것부터 삭제)
_cache_lock = threading.Lock()
_latest_cache = {}   # {"at": monotonic, "value": (y, m, updated), "checked_at": iso}
_rows_cache = {}     # (system, code) → {"at", "used", "year_from", "year_to", "rows", "fetched_at"}


# ---------- 스냅샷(ComexStat 점검·장애 대비) ----------
# build_snapshot.py로 수동 생성한 MDIC 공개 원본 CSV 요약. ComexStat 조회가 실패하고 메모리 캐시도 없을 때만 씁니다.
SNAPSHOT_FILE = Path(__file__).resolve().parent / "data" / "comexstat_snapshot.json"
SNAPSHOT_LABEL = "MDIC 공개 원본 자료"
_snapshot_state = {"mtime": None, "data": None}


def load_snapshot():
    """스냅샷 dict 또는 None(파일 없음·깨짐). 파일이 새로 생기거나 바뀌면(수정 시각 비교) 서버를 다시 시작하지 않아도 다시 읽습니다."""
    try:
        mtime = SNAPSHOT_FILE.stat().st_mtime
    except OSError:
        mtime = None
    with _cache_lock:
        if mtime != _snapshot_state["mtime"]:
            data = None
            if mtime is not None:
                try:
                    data = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
                    if not isinstance(data.get("rows"), list) or not data.get("source", {}).get("latest_month"):
                        data = None
                except (OSError, ValueError, AttributeError):
                    data = None
            _snapshot_state.update(mtime=mtime, data=data)
        return _snapshot_state["data"]


def snapshot_date(snap):
    return str(snap["source"].get("retrieved_at") or "")[:10]


def snapshot_rows(code_system, code, year_from, year_to):
    """스냅샷에서 query_imports와 같은 형식의 행. 범위(코드·연도) 밖이면 None.
    hs6은 그 6자리로 시작하는 NCM 행을 연·월·국가별로 합산합니다."""
    snap = load_snapshot()
    if not snap:
        return None
    src = snap["source"]
    prefix = str(src.get("ncm_prefix") or "")
    years = set(src.get("years") or [])
    if not all(y in years for y in range(year_from, year_to + 1)):
        return None
    if code_system == "ncm" and code.startswith(prefix):
        return [{k: r[k] for k in ("year", "month", "country", "fob", "kg", "code_name")}
                for r in snap["rows"] if r["ncm"] == code and year_from <= r["year"] <= year_to]
    if code_system == "hs6" and code == prefix:
        name = (snap.get("code_names") or {}).get("hs6", {}).get(code)
        sums = {}
        for r in snap["rows"]:
            if r["ncm"].startswith(code) and year_from <= r["year"] <= year_to:
                acc = sums.setdefault((r["year"], r["month"], r["country"]), [0, 0])
                acc[0] += r["fob"] or 0
                acc[1] += r["kg"] or 0
        return [{"year": y, "month": m, "country": c, "fob": fob, "kg": kg, "code_name": name}
                for (y, m, c), (fob, kg) in sorted(sums.items())]
    return None


def snapshot_code_name(code_system, code):
    snap = load_snapshot() or {}
    return ((snap.get("code_names") or {}).get(code_system) or {}).get(code)


# ---------- ComexStat 점검·장애 기억 ----------
# 연결 실패·5xx·호출 한도는 한 번 실패에 재시도까지 약 1분이 걸립니다. 실패를 확인하면 10분 동안은 ComexStat을 건너뛰고
# 바로 저장 자료(메모리 캐시·스냅샷)를 씁니다. 사용자가 '다시 불러오기'(refresh)를 누르면 이 기간에도 다시 시도합니다.
SOURCE_DOWN_SECONDS = 10 * 60
_DOWN_CODES = ("MA_SOURCE_UNAVAILABLE", "MA_SOURCE_RATE_LIMITED")
_source_down = {"until": 0.0, "error": None}


def _comex(call, *args, refresh=False):
    """ComexStat 호출. 최근 점검·장애를 확인했으면(refresh가 아니면) 호출하지 않고 그때 오류를 바로 냅니다."""
    with _cache_lock:
        down = _source_down["error"] if _monotonic() < _source_down["until"] else None
    if down is not None and not refresh:
        raise down
    try:
        result = call(*args)
    except ComexStatError as err:
        if err.code in _DOWN_CODES:
            with _cache_lock:
                _source_down.update(until=_monotonic() + SOURCE_DOWN_SECONDS, error=err)
        raise
    with _cache_lock:
        _source_down.update(until=0.0, error=None)
    return result


def source_down():
    """최근 ComexStat 점검·장애를 확인해 건너뛰는 중인지."""
    with _cache_lock:
        return _monotonic() < _source_down["until"]


def _usable(entry, refresh):
    """캐시를 그대로 쓸지: 6시간 안이고, 다시 불러오기여도 받은 지 10분 안이면 재사용."""
    age = _monotonic() - entry["at"]
    return age < (REFRESH_MIN_SECONDS if refresh else CACHE_TTL_SECONDS)


def get_latest(refresh=False):
    """최신 제공 월. 6시간 동안 재사용하고, 실패 시 이전 값이 있으면 그 값을 stale로 돌려줍니다."""
    with _cache_lock:
        cached = dict(_latest_cache) if _latest_cache else None
    if cached and _usable(cached, refresh):
        return cached, False
    try:
        value = _comex(comex.get_latest_month, refresh=refresh)
    except ComexStatError:
        if cached:
            return cached, True
        snap = load_snapshot()
        if snap:  # 캐시도 없으면 스냅샷의 최신 월(메모리 캐시에는 넣지 않아 다음 요청에서 다시 확인)
            y, m = (int(v) for v in snap["source"]["latest_month"].split("-"))
            return {"at": _monotonic(), "value": (y, m, snapshot_date(snap)), "checked_at": snap["source"].get("retrieved_at"),
                    "snapshot": True}, True
        raise
    entry = {"at": _monotonic(), "value": value, "checked_at": now_kst().isoformat(timespec="seconds")}
    with _cache_lock:
        _latest_cache.clear()
        _latest_cache.update(entry)
    return entry, False


def _get_rows(code_system, code, year_from, year_to, refresh):
    """(rows, cache_status, fetched_at). cache_status: fresh | cached | stale | snapshot."""
    key = (code_system, code)
    with _cache_lock:
        cached = _rows_cache.get(key)
        if cached:
            cached["used"] = _monotonic()
    covers = cached and cached["year_from"] <= year_from and cached["year_to"] >= year_to
    if covers and _usable(cached, refresh):
        return cached["rows"], "cached", cached["fetched_at"]
    try:
        rows = _comex(comex.query_imports, code_system, code, year_from, year_to, refresh=refresh)
    except ComexStatError:
        if covers:
            return cached["rows"], "stale", cached["fetched_at"]
        snap_rows = snapshot_rows(code_system, code, year_from, year_to)
        if snap_rows is not None:  # 캐시도 없으면 MDIC 공개 원본 스냅샷(범위 밖이면 원래 오류)
            return snap_rows, "snapshot", load_snapshot()["source"].get("retrieved_at")
        raise
    now = _monotonic()
    entry = {"at": now, "used": now, "year_from": year_from, "year_to": year_to, "rows": rows,
             "fetched_at": now_kst().isoformat(timespec="seconds")}
    with _cache_lock:
        _rows_cache[key] = entry
        while len(_rows_cache) > MAX_ROWS_CACHE:
            del _rows_cache[min(_rows_cache, key=lambda k: _rows_cache[k]["used"])]
    return rows, "fresh", entry["fetched_at"]


def clear_cache():
    with _cache_lock:
        _latest_cache.clear()
        _rows_cache.clear()
        _snapshot_state.update(mtime=None, data=None)  # 스냅샷 파일을 다시 읽게 함
        _source_down.update(until=0.0, error=None)
    with _ai_cache_lock:
        _ai_cache.clear()


# ---------- 입력 검증 ----------
def validate_request(payload, latest_index):
    """payload(JSON dict) → AnalysisRequest. latest_index가 None이면 최신 월 상한 검사를 생략합니다."""
    payload = payload if isinstance(payload, dict) else {}
    fields = {}

    code_system = str(payload.get("code_system") or "").strip()
    if code_system not in CODE_LENGTH:
        fields["code_system"] = "코드 체계를 선택해 주세요(NCM 8자리 또는 HS 6자리)."
    code = re.sub(r"[\s.\-]", "", str(payload.get("code") or ""))
    if not code:
        fields["code"] = "품목코드를 입력해 주세요."
    elif not code.isdigit():
        fields["code"] = "품목코드는 숫자로 입력해 주세요. 점(.)은 넣어도 됩니다."
    elif code_system in CODE_LENGTH and len(code) != CODE_LENGTH[code_system]:
        fields["code"] = "%s 코드는 숫자 %d자리입니다. 입력한 코드는 %d자리입니다." % (
            CODE_LABEL[code_system], CODE_LENGTH[code_system], len(code))

    start = _parse_month(payload.get("from"))
    end = _parse_month(payload.get("to"))
    if payload.get("from") in (None, ""):
        fields["from"] = "시작 월을 선택해 주세요."
    elif start is None:
        fields["from"] = "시작 월 형식이 올바르지 않습니다. YYYY-MM으로 선택해 주세요."
    elif start < month_index(FIRST_DATA_YEAR, 1):
        fields["from"] = "ComexStat 통계는 %d-01부터 제공됩니다. 시작 월을 다시 선택해 주세요." % FIRST_DATA_YEAR
    if payload.get("to") in (None, ""):
        fields["to"] = "종료 월을 선택해 주세요."
    elif end is None:
        fields["to"] = "종료 월 형식이 올바르지 않습니다. YYYY-MM으로 선택해 주세요."
    elif latest_index is not None and end > latest_index:
        fields["to"] = "통계는 %s까지 제공됩니다. 종료 월을 %s 이전으로 선택해 주세요." % (
            month_label(latest_index), month_label(latest_index))
    if start is not None and end is not None and "from" not in fields and "to" not in fields:
        if start > end:
            fields["from"] = "시작 월이 종료 월보다 늦습니다. 기간을 다시 선택해 주세요."
        elif end - start + 1 > MAX_MONTHS:
            fields["from"] = "조회 기간은 최대 %d개월입니다. 지금은 %d개월입니다. 기간을 줄여 주세요." % (
                MAX_MONTHS, end - start + 1)

    raw_countries = payload.get("countries") or []
    if not isinstance(raw_countries, list):
        raw_countries = []
    countries = []
    for value in raw_countries:
        value = str(value)
        if value == BRAZIL_CODE:
            fields["countries"] = "브라질은 대상 시장이라 공급국으로 선택할 수 없습니다."
            break
        if value not in _BY_CODE:
            fields["countries"] = "알 수 없는 공급국이 포함되어 있습니다. 목록에서 다시 선택해 주세요."
            break
        if value not in countries:
            countries.append(value)
    if len(countries) > MAX_COUNTRIES:
        fields["countries"] = "공급국은 최대 %d개까지 선택할 수 있습니다." % MAX_COUNTRIES

    if fields:
        raise InputError(fields)
    return AnalysisRequest(code_system, code, start, end, tuple(countries), bool(payload.get("refresh")))


# ---------- 계산 ----------
def unit_price(fob, kg):
    """(값, 사유). 중량이 없거나 0이면 계산 불가."""
    if fob is None or kg is None:
        return None, "금액 또는 중량 값 없음"
    if kg == 0:
        return None, "중량 0"
    return fob / kg, None


def change_rate(current, prior, prior_label="전년 동기"):
    """증감률(%) = (현재 − 전년) ÷ 전년 × 100. (값, 사유)."""
    if current is None:
        return None, "현재 값 없음"
    if prior is None:
        return None, "%s 기록 없음" % prior_label
    if prior == 0:
        return None, "%s 값 0" % prior_label
    return (current - prior) / prior * 100, None


def price_flags(prices):
    """{key: "low"|"high"} 와 중앙값. prices: {key: 단가 또는 None}."""
    valid = [p for p in prices.values() if p is not None]
    if len(valid) < 3:
        return {}, (statistics.median(valid) if valid else None)
    median = statistics.median(valid)
    flags = {}
    for key, p in prices.items():
        if p is None or median <= 0:
            continue
        if p < median * OUTLIER_LOW:
            flags[key] = "low"
        elif p > median * OUTLIER_HIGH:
            flags[key] = "high"
    return flags, median


def _sum(values):
    """None 제외 합. 모두 None이면 None."""
    values = [v for v in values if v is not None]
    return sum(values) if values else None


def _aggregate(rows):
    """{(월 번호, 국가 원문): [fob, kg, 짝 fob, 결측 행 수]} — 같은 칸이 여러 행이면 합산.

    짝 fob: 중량도 있는 행의 금액만 더한 값. 금액만 있고 중량이 빠진 행이 단가를 부풀리지 않도록
    평균 수입단가는 짝 fob ÷ 중량으로 계산합니다. 수입액·수입량 합계는 있는 값을 모두 더합니다.
    """
    cells = {}
    for r in rows:
        key = (month_index(r["year"], r["month"]), r["country"])
        cell = cells.setdefault(key, [None, None, None, 0])
        if r["fob"] is not None:
            cell[0] = (cell[0] or 0) + r["fob"]
        if r["kg"] is not None:
            cell[1] = (cell[1] or 0) + r["kg"]
        if r["fob"] is not None and r["kg"] is not None:
            cell[2] = (cell[2] or 0) + r["fob"]
        else:
            cell[3] += 1
    return cells


def _period_totals(cells, start, end, country=None):
    fob, kg, paired, missing, months = [], [], [], 0, set()
    for (idx, name), (f, k, pf, miss) in cells.items():
        if start <= idx <= end and (country is None or name == country):
            fob.append(f)
            kg.append(k)
            paired.append(pf)
            missing += miss
            months.add(idx)
    return {"fob": _sum(fob), "kg": _sum(kg), "paired_fob": _sum(paired), "missing_rows": missing,
            "months_with_record": len(months)}


def _metric_block(current, prior):
    price, price_reason = unit_price(current["paired_fob"], current["kg"])
    prior_price, _ = unit_price(prior["paired_fob"], prior["kg"])
    out = {"fob": current["fob"], "kg": current["kg"], "unit_price": price, "unit_price_reason": price_reason,
           "prior": {"fob": prior["fob"], "kg": prior["kg"], "unit_price": prior_price}}
    out["yoy"] = {}
    for key, cur, pri in (("fob", current["fob"], prior["fob"]), ("kg", current["kg"], prior["kg"]),
                          ("unit_price", price, prior_price)):
        value, reason = change_rate(cur, pri)
        out["yoy"][key] = {"value": value, "reason": reason}
    return out


def compute(rows, req, code_name=None):
    """조회 행 → 화면용 결과(원본 값, 반올림은 화면에서). 순수 함수."""
    cells = _aggregate(rows)
    start, end = req.start, req.end
    span = end - start + 1
    prior_start, prior_end = start - 12, end - 12

    current = _period_totals(cells, start, end)
    prior = _period_totals(cells, prior_start, prior_end)
    summary = _metric_block(current, prior)
    summary["months"] = span
    summary["months_with_record"] = current["months_with_record"]
    summary["prior_months_with_record"] = prior["months_with_record"]
    summary["prior_period"] = {"from": month_label(prior_start), "to": month_label(prior_end)}

    # 월별 추세
    monthly, month_prices = [], {}
    by_month = {}
    for (idx, _), (f, k, pf, _miss) in cells.items():
        entry = by_month.setdefault(idx, [[], [], []])
        entry[0].append(f)
        entry[1].append(k)
        entry[2].append(pf)
    for idx in range(start, end + 1):
        cur = by_month.get(idx)
        pri = by_month.get(idx - 12)
        fob = _sum(cur[0]) if cur else None
        kg = _sum(cur[1]) if cur else None
        price, price_reason = unit_price(_sum(cur[2]), kg) if cur else (None, "기록 없음")
        p_fob = _sum(pri[0]) if pri else None
        p_kg = _sum(pri[1]) if pri else None
        p_price = unit_price(_sum(pri[2]), p_kg)[0] if pri else None
        item = {"month": month_label(idx), "has_record": cur is not None, "fob": fob, "kg": kg,
                "unit_price": price, "unit_price_reason": price_reason, "yoy": {}}
        for key, c, p in (("fob", fob, p_fob), ("kg", kg, p_kg), ("unit_price", price, p_price)):
            value, reason = change_rate(c, p, "전년 동월")
            item["yoy"][key] = {"value": value, "reason": reason}
        monthly.append(item)
        month_prices[item["month"]] = price
    flags, month_median = price_flags(month_prices)
    for item in monthly:
        item["price_flag"] = flags.get(item["month"])

    # 공급국(브라질 원산지 재수입분은 목록에서 제외, 전체 수입액에는 포함)
    names = sorted({name for (idx, name) in cells if start <= idx <= end})
    brazil_names = [n for n in names if country_info(name_pt=n)["code"] == BRAZIL_CODE]
    names = [n for n in names if n not in brazil_names]
    brazil_fob = _sum(_period_totals(cells, start, end, n)["fob"] for n in brazil_names)
    per_country = []
    for name in names:
        cur = _period_totals(cells, start, end, name)
        pri = _period_totals(cells, prior_start, prior_end, name)
        block = _metric_block(cur, pri)
        info = country_info(name_pt=name)
        block.update({"country": info, "months_with_record": cur["months_with_record"]})
        total = current["fob"]
        block["share"] = (cur["fob"] / total * 100) if (cur["fob"] is not None and total) else None
        per_country.append(block)
    per_country.sort(key=lambda c: (-(c["fob"] or 0), c["country"]["name_pt"]))
    for rank, c in enumerate(per_country, 1):
        c["rank"] = rank
    c_flags, country_median = price_flags({c["country"]["name_pt"]: c["unit_price"] for c in per_country})
    for c in per_country:
        c["price_flag"] = c_flags.get(c["country"]["name_pt"])

    def find(code):
        return next((c for c in per_country if c["country"]["code"] == code), None)

    korea = find(KOREA_CODE)
    selected = []
    for code in req.countries:
        found = find(code)
        selected.append(found if found else {"country": country_info(code=code), "rank": None, "no_record": True})

    notes = []
    missing = span - current["months_with_record"]
    if missing:
        notes.append("조회 기간 %d개월 중 %d개월은 수입 기록이 없습니다. 0으로 채우지 않고 '기록 없음'으로 표시했습니다." % (span, missing))
    prior_missing = span - prior["months_with_record"]
    if prior["months_with_record"] and prior_missing:
        notes.append("전년 동기(%s~%s) 중 %d개월은 기록이 없습니다. 전년 대비 증감률 해석에 주의하세요." % (
            month_label(prior_start), month_label(prior_end), prior_missing))
    if current["missing_rows"]:
        notes.append("조회 기간에 금액 또는 중량이 빠진 행이 %d건 있습니다. 수입액·수입량 합계에는 있는 값만 더했고, "
                     "평균 수입단가는 금액과 중량이 모두 있는 행만으로 계산했습니다. 합계가 실제보다 작을 수 있습니다." % current["missing_rows"])
    if brazil_names:
        share = (brazil_fob / current["fob"] * 100) if (brazil_fob is not None and current["fob"]) else None
        notes.append("원산지가 브라질(Brasil)인 재수입분%s은 대상 시장 자신이라 공급국 목록·순위에서 제외했습니다. "
                     "전체 수입액과 비중의 분모(MDIC 공식 합계)에는 포함되어 있습니다. MDIC 수입 통계는 원산지 기준이라 "
                     "브라질에서 만든 상품이 수리·반송 등으로 다시 들어오면 원산지가 브라질로 기록됩니다(MDIC 통계 이용 매뉴얼)." % (
                         " USD {:,}(전체의 {:.1f}%)".format(int(round(brazil_fob)), share) if share is not None else ""))
    unmapped = sorted({c["country"]["name_pt"] for c in per_country if c["country"]["code"] is None})
    if unmapped:
        notes.append("국가 코드표에 없는 공급국 이름이 있어 원문으로 표시했습니다: %s" % ", ".join(unmapped))

    return {
        "query": {
            "market": "브라질 수입",
            "flow": "import",
            "code_system": req.code_system,
            "code_system_label": CODE_LABEL[req.code_system],
            "code": req.code,
            "code_name": code_name,
            "from": month_label(start),
            "to": month_label(end),
            "months": span,
            "countries": [country_info(code=c) for c in req.countries],
        },
        "has_data": bool(current["months_with_record"]),
        "summary": summary,
        "monthly": monthly,
        "suppliers": {
            "count": len(per_country),
            "top": per_country[:TOP_N],
            "korea": korea,
            "korea_code": KOREA_CODE,
            "selected": selected,
        },
        "outlier": {
            "rule": "같은 조회의 단가 중앙값 대비 ½배 미만 또는 2배 초과이면 '확인 필요'로 표시합니다(값은 삭제하지 않음). 단가가 3개 미만이면 판정하지 않습니다.",
            "country_basis": "공급국은 MDIC 통계 기준 원산지 국가입니다(판매 회사 국가 아님).",
            "monthly_median": month_median,
            "country_median": country_median,
        },
        "notes": notes,
    }


# ---------- 조회 흐름 ----------
def meta():
    """화면 초기값. ComexStat 실패 시 latest는 None이고 error에 사유를 담습니다."""
    out = {
        "default": {"code_system": DEFAULT_CODE_SYSTEM, "code": DEFAULT_CODE, "months": DEFAULT_MONTHS},
        "max_months": MAX_MONTHS,
        "max_countries": MAX_COUNTRIES,
        "first_month": "%d-01" % FIRST_DATA_YEAR,
        "korea_code": KOREA_CODE,
        "countries": country_list(),
        "latest": None,
        "error": None,
        # OpenAI 설정 존재 여부(값 없음, 환경변수 이름만). 화면이 AI 실행 전에 안내할 수 있게 합니다.
        "ai": analysis.config_status(),
    }
    try:
        entry, stale = get_latest()
    except ComexStatError as err:
        out["error"] = {"code": err.code, "message": err.message}
        return out
    y, m, updated = entry["value"]
    latest = month_index(y, m)
    out["latest"] = {"month": month_label(latest), "updated": updated, "checked_at": entry["checked_at"], "stale": stale,
                     "snapshot": bool(entry.get("snapshot"))}
    out["default"]["from"] = month_label(latest - DEFAULT_MONTHS + 1)
    out["default"]["to"] = month_label(latest)
    return out


def analyze(payload):
    """검증 → 조회(캐시) → 계산. InputError·ComexStatError를 그대로 올립니다."""
    latest_entry, latest_stale, latest_error = None, False, None
    try:
        latest_entry, latest_stale = get_latest()
    except ComexStatError as err:
        latest_error = err
    latest_index = month_index(*latest_entry["value"][:2]) if latest_entry else None
    req = validate_request(payload, latest_index)

    year_from = (req.start - 12) // 12  # 전년 동기 비교분 포함
    year_to = req.end // 12
    rows, cache_status, fetched_at = _get_rows(req.code_system, req.code, year_from, year_to, req.refresh)

    code_name = next((r["code_name"] for r in rows if r.get("code_name")), None)
    if not rows and cache_status == "snapshot":
        # 스냅샷 대체 중에는 코드표 조회(ComexStat)도 못 하므로 스냅샷 코드표로 확인합니다.
        code_name = snapshot_code_name(req.code_system, req.code)
        if code_name is None:
            raise InputError({"code": "MDIC 공개 원본 자료에서 %s 코드 %s를 찾지 못했습니다. 코드를 확인해 주세요." % (
                CODE_LABEL[req.code_system], req.code)})
    elif not rows:
        # 결과 없음과 존재하지 않는 코드를 구분합니다(현행 코드표 기준).
        found = _comex(comex.lookup_code, req.code_system, req.code, refresh=req.refresh)
        if found is None:
            raise InputError({"code": "ComexStat 현행 코드표에서 %s 코드 %s를 찾지 못했습니다. 코드를 확인해 주세요." % (
                CODE_LABEL[req.code_system], req.code)})
        code_name = found or None

    result = compute(rows, req, code_name)
    snapshot_used = cache_status == "snapshot"
    result["notes"].insert(0, ("품목코드 이름은 MDIC 공개 코드표(NCM.csv) 기준입니다. " if snapshot_used else
                               "품목코드 이름과 유효성은 ComexStat 현행 코드표 기준입니다. ") +
                           "과거 기간에 같은 코드가 적용됐는지(NCM 개정)는 확인하지 않았습니다.")
    result["notes"].append("MDIC는 올해 각 달의 수치를 매월 다시 집계하고, 지난해 수치는 이듬해 2월에 한 번 수정한 뒤 고정합니다(MDIC 통계 이용 매뉴얼). "
                           + ("이번 자료는 원본을 받은 날 기준이라 이후 수정된 최근 수치와 다를 수 있습니다." if snapshot_used else
                              "같은 조건이라도 조회 시점에 따라 최근 수치가 달라질 수 있습니다."))
    if latest_error:
        result["notes"].insert(0, "최신 제공 월을 확인하지 못해 종료 월 상한을 검사하지 않았습니다.")
    snap = load_snapshot() if cache_status == "snapshot" else None
    if snap:
        result["notes"].insert(0, "ComexStat이 점검 중이거나 연결되지 않아 %s(기준: %s)를 사용했습니다. MDIC가 공개한 원본 CSV를 미리 받아 요약한 자료이며 "
                               "ComexStat 실시간 조회 결과가 아닙니다." % (SNAPSHOT_LABEL, snapshot_date(snap)))
    result["sources"] = [{
        "name": snap["source"]["name"] if snap else "ComexStat (브라질 산업통상서비스부 MDIC)",
        "url": (snap["source"]["files"][-1]["url"] if snap and snap["source"].get("files") else comex.SITE_URL),
        "api": comex.BASE_URL + "/general",
        "metrics": "FOB 금액(USD), 순중량(kg)",
        "data_updated": latest_entry["value"][2] if latest_entry else None,
        "latest_month": month_label(latest_index) if latest_index is not None else None,
        "fetched_at": fetched_at,
        "cache_status": cache_status,
        "latest_stale": latest_stale,
    }]
    result["bundle_id"] = create_bundle(result)
    return result


# ---------- 분석 묶음 ----------
# 한 번의 조회 결과(공개 통계)와 AI 진행 상태를 서버 메모리에 짧게 보관합니다.
# AI 분석이 화면에 표시된 것과 같은 통계를 쓰게 하고, 같은 묶음의 유료 분석이 중복 실행되지 않게 합니다.
# 디스크·DB에 쓰지 않으며 서버를 다시 시작하면 사라집니다.
BUNDLE_TTL_SECONDS = 3 * 3600
MAX_BUNDLES = 30
_bundles = {}
_bundles_lock = threading.Lock()


class BundleError(Exception):
    def __init__(self, code, message, http_status):
        self.code, self.message, self.http_status = code, message, http_status
        super().__init__(message)


def _monotonic():
    return time.monotonic()


def create_bundle(stats):
    bid = secrets.token_urlsafe(16)
    with _bundles_lock:
        now = _monotonic()
        for k in [k for k, b in _bundles.items() if now - b["created"] > BUNDLE_TTL_SECONDS]:
            del _bundles[k]
        while len(_bundles) >= MAX_BUNDLES:
            del _bundles[min(_bundles, key=lambda k: _bundles[k]["created"])]
        _bundles[bid] = {"created": now, "stats": stats, "ai": None, "lock": threading.Lock()}
    return bid


def get_bundle(bundle_id):
    with _bundles_lock:
        b = _bundles.get(str(bundle_id or ""))
        if b and _monotonic() - b["created"] > BUNDLE_TTL_SECONDS:
            del _bundles[bundle_id]
            b = None
    if not b:
        raise BundleError("MA_BUNDLE_EXPIRED", "조회 결과가 만료되었거나 서버가 다시 시작되었습니다. '분석 실행'으로 통계를 다시 조회해 주세요.", 410)
    return b


def clear_bundles():
    with _bundles_lock:
        _bundles.clear()
    with _ai_cache_lock:  # 서버 재시작과 같은 효과: AI 결과 캐시도 비움
        _ai_cache.clear()


# 같은 통계(새 '분석 실행'으로 묶음이 달라도 수치가 같으면)의 완료된 AI 결과. 유료 재호출을 막습니다.
AI_CACHE_TTL_SECONDS = 6 * 3600
MAX_AI_CACHE = 10
_ai_cache = {}   # 통계 서명 → {"at", "state"}
_ai_cache_lock = threading.Lock()


def stats_signature(stats):
    """AI 입력이 되는 통계 내용의 서명. 받은 시각·캐시 상태·묶음 번호처럼 수치와 무관한 값은 뺍니다."""
    body = {k: v for k, v in stats.items() if k not in ("sources", "bundle_id")}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _cached_ai(sig):
    with _ai_cache_lock:
        hit = _ai_cache.get(sig)
        if hit and _monotonic() - hit["at"] > AI_CACHE_TTL_SECONDS:
            del _ai_cache[sig]
            hit = None
        return hit["state"] if hit else None


def _store_ai(sig, state):
    with _ai_cache_lock:
        now = _monotonic()
        for k in [k for k, v in _ai_cache.items() if now - v["at"] > AI_CACHE_TTL_SECONDS]:
            del _ai_cache[k]
        _ai_cache[sig] = {"at": now, "state": state}
        while len(_ai_cache) > MAX_AI_CACHE:
            del _ai_cache[min(_ai_cache, key=lambda k: _ai_cache[k]["at"])]


def run_ai(bundle_id):
    """AI 분석(초안+5차례 검토). 이미 끝난 묶음, 또는 같은 통계로 6시간 안에 끝난 결과가 있으면 저장된 결과를 돌려주고
    다시 호출하지 않습니다. 실패·중단된 묶음은 끝난 단계 다음부터 이어서 진행합니다(미완료 결과는 공유 캐시에 넣지 않음).
    같은 묶음이 실행 중이면 409."""
    b = get_bundle(bundle_id)
    if not b["lock"].acquire(blocking=False):
        raise BundleError("MA_AI_RUNNING", "이 조회의 AI 분석이 이미 진행 중입니다. 끝날 때까지 기다려 주세요.", 409)
    try:
        if b["ai"] is not None and b["ai"]["status"] == "complete":
            return {**b["ai"]["result"], "reused": True}
        sig = stats_signature(b["stats"])
        if b["ai"] is None:
            done = _cached_ai(sig)
            if done is not None:
                b["ai"] = done
                return {**done["result"], "reused": True}
        state = b["ai"] or analysis.new_state()
        state = analysis.run(state, b["stats"])
        b["ai"] = state
        if state["status"] == "complete":
            _store_ai(sig, state)
        return {**state["result"], "reused": False}
    finally:
        b["lock"].release()
