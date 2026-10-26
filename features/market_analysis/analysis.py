"""시장 분석 AI 분석: 초안 1회 + 회차별 목적이 다른 검토 5회. common.ai_client.generate_structured를 재사용합니다.

- 수치는 코드 계산값(facts, 출처 S1)에 있는 값만 허용합니다. 회차마다 코드가 표를 검사해
  (존재하지 않는 출처 ID, 근거에 없는 수치, 개수 초과, 사실 표시인데 출처 없음, T2T·견적 해석 위험)
  다음 회차 입력에 넣고, 마지막에는 남은 문제를 표에 표시하고 상태를 낮춥니다.
- 기사 근거는 쓰지 않습니다(2026-10-26 담당자 결정으로 뉴스 수집 기능 삭제). evidence는 빈 목록으로 보냅니다.
- 출처명·URL·기준일은 모델이 아니라 코드가 출처 ID로 붙입니다.
- 진행 상태(state)는 호출한 쪽이 보관합니다. 실패한 회차부터 다시 시작하며 끝난 호출은 다시 하지 않습니다.
- 호출 상한: 초안 1 + 검토 5 = 6회, 전체 시간 상한 TIME_BUDGET_SECONDS. 무한 반복 없음.
"""
import json
import re
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from common import ai_client, config
from common.errors import AIConfigError, AIError

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
# v2(2026-10-26): 기사 근거 규칙(title_only 등) 포함. 뉴스 수집 삭제 후에는 evidence가 비어 그 규칙은 적용되지 않음. v1은 미실행으로 보존.
DRAFT_PROMPT = "market_analysis_draft_v2.md"
# v3(2026-10-26): 매 회차 추정·미확인 행을 출처로 확정하거나 삭제. 최종 표에는 사실 행만 남깁니다(finalize_rows).
REVIEW_PROMPT = "market_analysis_review_v3.md"
MAX_OUTPUT_TOKENS = 4096
TIME_BUDGET_SECONDS = 480.0

SECTIONS = ("핵심 요약", "변화 배경", "영업 기회", "위험")
SECTION_LIMITS = {"핵심 요약": (3, 5), "변화 배경": (0, 4), "영업 기회": (0, 3), "위험": (0, 3)}
ROUNDS = (
    (1, "자료 적합성"),
    (2, "수치 정확성"),
    (3, "원문·공식 출처 검증"),
    (4, "사실·추정과 해석 검토"),
    (5, "표현·표·출처 연결 최종 검토"),
)

# 2026-10-25 OpenAI 공식 모델 페이지의 gpt-5.4-mini 단가(USD / 1M 토큰). 다른 모델은 금액을 계산하지 않습니다.
PRICE_PER_MTOK = {"gpt-5.4-mini": (0.75, 4.50)}


class Row(BaseModel):
    section: Literal["핵심 요약", "변화 배경", "영업 기회", "위험"]
    content: str
    implication: str
    status: Literal["사실", "추정", "미확인"]
    source_ids: list[str]


class Draft(BaseModel):
    rows: list[Row]
    gaps: list[str]


class Review(BaseModel):
    checked: list[str]
    changes: list[str]
    evidence: list[str]
    unresolved: list[str]
    completed: bool
    rows: list[Row]


def _prompt(name):
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


# ---------- 설정·오류 진단 (값은 담지 않고 환경변수 이름·상태만) ----------
CONFIG_MESSAGE = ("AI 분석에 필요한 서버 설정(OpenAI 키·텍스트 모델)이 없어 분석을 시작하지 않았습니다. "
                  "통계와 근거 자료는 그대로 볼 수 있습니다. 관리자가 서버 실행 환경에 설정한 뒤 서버를 다시 시작해야 합니다.")

# 공통 AIError 코드 → 개발자 진단 분류
DIAGNOSTICS = {
    "AI_AUTH_FAILED": ("auth_failed", "인증 실패", "OpenAI가 키를 거부했습니다(키 오류·폐기·다른 조직 키)."),
    "AI_PERMISSION_DENIED": ("permission_denied", "권한 없음", "키에 이 모델·기능 사용 권한이 없습니다."),
    "AI_MODEL_UNAVAILABLE": ("model_unavailable", "모델 사용 불가", "OPENAI_MODEL 값의 모델을 찾지 못했거나 접근할 수 없습니다."),
    "AI_RATE_LIMITED": ("rate_limited", "한도 초과", "호출 한도 또는 사용 가능 금액(크레딧)을 넘었습니다."),
    "AI_TIMEOUT": ("timeout", "시간 초과", "응답 시간이 초과되었습니다."),
    "AI_CONNECTION_FAILED": ("connection_failed", "연결 실패", "OpenAI 서버에 연결하지 못했습니다(네트워크·프록시)."),
    "AI_PROVIDER_ERROR": ("provider_error", "공급자 서버 오류", "OpenAI 서버 오류(5xx) 또는 실패 상태 응답입니다."),
    "AI_BAD_REQUEST": ("bad_request", "요청 거부", "요청 형식·파라미터가 거부되었습니다."),
    "AI_REFUSED": ("refused", "응답 거절", "모델이 요청을 거절했습니다."),
    "AI_INCOMPLETE": ("incomplete", "응답 미완료", "출력 토큰 상한 등으로 응답이 끝나지 않았습니다."),
    "AI_OUTPUT_INVALID": ("output_invalid", "응답 형식 오류", "응답을 결과 스키마로 해석하지 못했습니다."),
}


def config_status():
    """OpenAI 설정 존재 여부(값 없음). missing: 비어 있는 환경변수 이름."""
    key, model = bool(config.get_openai_api_key()), bool(config.get_text_model())
    missing = [name for name, ok in ((config.ENV_OPENAI_API_KEY, key), (config.ENV_OPENAI_MODEL, model)) if not ok]
    return {"ready": not missing, "api_key_set": key, "model_set": model, "missing": missing}


def config_diagnostic(status):
    if not status["missing"]:
        # 미리 확인할 때는 있었는데 공통 연결이 설정 누락을 보고한 경우(호출 사이 환경 변경 등)
        return {"kind": "config_missing", "label": "설정 누락", "env_missing": [], "status_code": None,
                "detail": "공통 AI 연결이 설정 누락을 보고했습니다. 서버 로그의 'AI 설정 누락' 줄에서 환경변수 이름을 확인하세요."}
    kind = ("key_and_model_missing" if len(status["missing"]) == 2
            else "key_missing" if not status["api_key_set"] else "model_missing")
    label = {"key_and_model_missing": "키·모델 미설정", "key_missing": "키 미설정", "model_missing": "모델 미설정"}[kind]
    return {"kind": kind, "label": label, "env_missing": status["missing"], "status_code": None,
            "detail": "서버 프로세스 환경변수에 %s 값이 없습니다. .env 파일은 앱이 직접 읽지 않으므로(python-dotenv 미설치 시) "
                      "실행 셸에 설정한 뒤 서버를 다시 시작해야 합니다." % ", ".join(status["missing"])}


def error_diagnostic(err):
    kind, label, detail = DIAGNOSTICS.get(err.code, ("unknown", "알 수 없는 오류", "분류되지 않은 AI 오류입니다."))
    return {"kind": kind, "label": label, "env_missing": [], "status_code": err.status_code, "detail": detail}


# ---------- 근거 묶음 ----------
def _fmt_int(v):
    return "{:,}".format(int(round(v)))


def _fmt1(v):
    return "{:,.1f}".format(v)


def _fmt2(v):
    return "{:,.2f}".format(v)


def _signed(v):
    return ("+" if v > 0 else "") + _fmt1(v) + "%"


def build_facts(stats):
    """코드 계산값 → 사실 문장 목록. 화면과 같은 반올림(USD 정수, t 1자리, USD/kg 2자리, % 1자리)."""
    q, s, sup = stats["query"], stats["summary"], stats["suppliers"]
    facts = ["조회 조건: 브라질 수입, %s %s%s, %s~%s(%d개월)" % (
        q["code_system_label"], q["code"], (" (" + q["code_name"] + ")") if q.get("code_name") else "",
        q["from"], q["to"], q["months"])]
    if s.get("fob") is not None:
        facts.append("수입액(FOB) USD %s" % _fmt_int(s["fob"]))
    if s.get("kg") is not None:
        facts.append("수입량 %s t" % _fmt1(s["kg"] / 1000))
    if s.get("unit_price") is not None:
        facts.append("평균 수입단가(FOB) %s USD/kg" % _fmt2(s["unit_price"]))
    pp = s["prior_period"]
    for key, label in (("fob", "수입액"), ("kg", "수입량"), ("unit_price", "평균 수입단가")):
        y = s["yoy"][key]
        if y["value"] is not None:
            facts.append("%s 전년 동기(%s~%s) 대비 %s" % (label, pp["from"], pp["to"], _signed(y["value"])))
        else:
            facts.append("%s 전년 동기 대비: 계산 불가(%s)" % (label, y["reason"]))
    for c in sup["top"][:5]:
        name = c["country"].get("name_ko") or c["country"].get("name_pt")
        facts.append("공급국 %d위 %s: 수입액 USD %s, 비중 %s%%" % (
            c["rank"], name, _fmt_int(c["fob"] or 0), _fmt1(c["share"]) if c["share"] is not None else "?"))
    k = sup.get("korea")
    facts.append("한국: %s" % ("%d위, 비중 %s%%, 수입액 USD %s" % (k["rank"], _fmt1(k["share"]), _fmt_int(k["fob"]))
                              if k else "조회 기간 수입 기록 없음"))
    months = [m for m in stats["monthly"] if m["has_record"] and m["fob"] is not None]
    if months:
        hi = max(months, key=lambda m: m["fob"])
        lo = min(months, key=lambda m: m["fob"])
        facts.append("월 수입액 최고 %s USD %s, 최저 %s USD %s" % (hi["month"], _fmt_int(hi["fob"]), lo["month"], _fmt_int(lo["fob"])))
    return facts


def build_pack(stats):
    """AI 입력 JSON(데이터)과 출처 표. 근거는 코드 계산 통계(S1)뿐입니다. 초안·검토 프롬프트 형식에 맞춰 evidence는 빈 목록."""
    facts = build_facts(stats)
    q = stats["query"]
    pack = {
        "context": {
            "market": "브라질 수입", "product": "%s %s" % (q["code_system_label"], q["code"]),
            "product_name_pt": q.get("code_name"), "period": "%s~%s" % (q["from"], q["to"]),
            "notes": [
                "통계는 해당 코드의 전체 폴리에스터 DTY 시장이며 일반·재생·T2T 원사를 구분하지 않는다.",
                "평균 수입단가는 FOB 기준이며 견적·판매가·도착가격이 아니다.",
                "공급국은 ComexStat 기준 원산지(origin) 국가다.",
                "기사 근거는 없다. 수치·사실은 facts(S1)에 있는 것만 쓰고, 기사로 뒷받침되는 내용을 만들지 않는다.",
            ],
        },
        "facts": [{"id": "S1", "items": facts}],
        "evidence": [],
    }
    src = stats["sources"][0]
    if src.get("cache_status") == "snapshot":
        # ComexStat 점검·장애로 MDIC 공개 원본 CSV 스냅샷을 쓴 경우: 모델과 출처 표에 그 사실을 그대로 알립니다.
        basis = str(src.get("fetched_at") or "")[:10]
        pack["context"]["data_source"] = "MDIC 공개 원본 자료(Comex Stat 기본 데이터 CSV, 기준: %s). ComexStat 실시간 조회가 아님" % basis
        pack["context"]["notes"].append(
            "이번 통계는 ComexStat 조회 실패로 MDIC가 공개한 원본 CSV를 미리 받아 요약한 자료(기준 %s, 최신 월 %s)로 계산했다. "
            "같은 MDIC 공식 통계이지만 실시간 조회가 아니므로 최신성을 단정하지 않는다." % (basis, src.get("latest_month") or "?"))
        date = "MDIC 공개 원본 자료(기준: %s) · 최신 월 %s" % (basis, src.get("latest_month") or "?")
    else:
        date = "자료 갱신 %s · 최신 월 %s" % (src.get("data_updated") or "?", src.get("latest_month") or "?")
    sources = {"S1": {"name": src["name"], "url": src["url"], "date": date}}
    return pack, sources


# ---------- 코드 검사 ----------
_NUM_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
_MONTH_WORD_RE = re.compile(r"(?<![\d.])(\d{1,2})\s*(?:월|개월)")
_PCT_RE = re.compile(r"([-+]?\d[\d,]*(?:\.\d+)?)\s*%")


def _percents(text):
    return {float(m.lstrip("+-").replace(",", "")) for m in _PCT_RE.findall(text or "")}


def allowed_percents(pack):
    """근거(facts·evidence)에 '%'로 나온 값. 행의 비율은 이 값이어야 합니다(순위 '1위'의 1로 '1%'가 통과하지 않게)."""
    pcts = set()
    for f in pack["facts"]:
        for line in f["items"]:
            pcts |= _percents(line)
    for e in pack["evidence"]:
        pcts |= _percents(e["title"]) | _percents(e["summary"])
    return pcts


def _numbers(text):
    out = set()
    for m in _NUM_RE.finditer(text or ""):
        raw = m.group(0).lstrip("+-").replace(",", "")
        if raw:
            try:
                out.add(float(raw))
            except ValueError:
                pass
    return out


def allowed_numbers(pack):
    nums = set()
    for f in pack["facts"]:
        for line in f["items"]:
            nums |= _numbers(line)
    for e in pack["evidence"]:
        nums |= _numbers(e["title"]) | _numbers(e["summary"]) | _numbers(e.get("date") or "")
    nums |= _numbers(pack["context"]["period"]) | _numbers(pack["context"]["product"])
    return nums


_T2T_RE = re.compile(r"(T2T|리젠|재생\s*원사)")
_DEMAND_RE = re.compile(r"(수요|시장\s*규모|시장규모)")
_QUOTE_RE = re.compile(r"(견적|판매\s*가|판매가격|오퍼\s*가|도착\s*가)")
_PRICE_RE = re.compile(r"(단가|USD/kg)")


def check_rows(rows, pack):
    """코드 검사 결과 목록. 각 항목: {row, kind, detail}. row는 0부터."""
    ids = {"S1"} | {e["id"] for e in pack["evidence"]}
    nums = allowed_numbers(pack)
    pcts = allowed_percents(pack)
    findings = []
    counts = {}
    for i, r in enumerate(rows):
        counts[r["section"]] = counts.get(r["section"], 0) + 1
        bad = [s for s in r["source_ids"] if s not in ids]
        if bad:
            findings.append({"row": i, "kind": "unknown_source", "detail": "존재하지 않는 출처 ID: %s" % ", ".join(bad)})
        if r["status"] == "사실" and not [s for s in r["source_ids"] if s in ids]:
            findings.append({"row": i, "kind": "fact_without_source", "detail": "사실로 표시했지만 유효한 출처가 없음"})
        if r["status"] != "사실":
            findings.append({"row": i, "kind": "unconfirmed",
                             "detail": "%s 행 '%s'이(가) %s 상태: 출처로 확정하거나 삭제" % (r["section"], r["content"][:30], r["status"])})
        text = r["content"] + " " + r["implication"]
        # 근거에 없는 숫자는 문제로 봅니다. 예외는 'N월'·'N개월'처럼 쓰인 1~12뿐입니다
        # (예전에는 1~12를 모두 허용해 "비중 1% 미만" 같은 근거 없는 문장이 통과함, 2026-10-26 실측).
        months = {float(m) for m in _MONTH_WORD_RE.findall(text) if 1 <= int(m) <= 12}
        loose = [n for n in _numbers(text) if n not in nums and n not in months]
        loose += [n for n in _percents(text) if n not in pcts and n not in loose]  # 비율은 근거의 비율과 단위까지 대조
        if loose:
            findings.append({"row": i, "kind": "unverified_number",
                             "detail": "근거에 없는 수치: %s" % ", ".join(_fmt_plain(n) for n in sorted(loose))})
        if "S1" in r["source_ids"] and _T2T_RE.search(text) and _DEMAND_RE.search(text):
            findings.append({"row": i, "kind": "t2t_interpretation",
                             "detail": "전체 DTY 통계(S1)를 T2T 수요·시장 규모로 해석했을 수 있음"})
        if _QUOTE_RE.search(text) and _PRICE_RE.search(text):
            findings.append({"row": i, "kind": "price_as_quote", "detail": "평균 수입단가를 견적·판매가로 제시했을 수 있음"})
    for sec, (lo, hi) in SECTION_LIMITS.items():
        n = counts.get(sec, 0)
        if n > hi:
            findings.append({"row": None, "kind": "too_many", "detail": "%s %d행(최대 %d행)" % (sec, n, hi)})
        if n < lo:
            findings.append({"row": None, "kind": "too_few", "detail": "%s %d행(권장 %d~%d행). 근거가 부족하면 그대로 두고 부족 사유를 남김" % (sec, n, lo, hi)})
    return findings


def _fmt_plain(n):
    return str(int(n)) if n.is_integer() else str(n)


def finalize_rows(rows, pack, sources):
    """마지막 코드 검사 결과를 표에 반영하고 출처로 확인된 사실 행만 남깁니다.

    잘못된 출처 ID 제거, 문제가 남은 행은 미확인으로 낮춘 뒤, 사실이 아닌 행(추정·미확인)은 표에서 뺍니다(2026-10-26 담당자 지시).
    반환: (남은 행, 남은 행 기준 검사 결과, 뺀 행 목록)
    """
    out, _ = _apply_findings(rows, pack, sources)
    kept = [r for r in out if r["status"] == "사실"]
    removed = [{"section": r["section"], "content": r["content"], "status": r["status"], "model_status": r["model_status"],
                "reason": "; ".join(r["flags"]) or "5차례 검토 후에도 출처로 확정되지 않음(%s)" % r["status"]}
               for r in out if r["status"] != "사실"]
    findings = check_rows(kept, pack)
    return kept, findings, removed


def _apply_findings(rows, pack, sources):
    """코드 검사 결과를 행에 표시. 문제가 남은 행은 미확인으로 낮춥니다."""
    findings = check_rows(rows, pack)
    by_row = {}
    for f in findings:
        if f["row"] is not None:
            by_row.setdefault(f["row"], []).append(f)
    out = []
    kept = {}
    for i, r in enumerate(rows):
        sec = r["section"]
        kept[sec] = kept.get(sec, 0) + 1
        if kept[sec] > SECTION_LIMITS[sec][1]:
            continue  # 최대 개수 초과분은 표에서 뺍니다(검토 기록에 남음)
        # 'unconfirmed'는 검토 회차에 넘기는 지시용 검사라 행 표시(flags)에는 넣지 않습니다.
        flags = [f["detail"] for f in by_row.get(i, []) if f["kind"] != "unconfirmed"]
        status = r["status"]
        if any(f["kind"] in ("unverified_number", "fact_without_source", "t2t_interpretation", "price_as_quote")
               for f in by_row.get(i, [])):
            status = "미확인"
        valid_ids = [s for s in r["source_ids"] if s in sources]
        out.append({
            "section": sec, "content": r["content"], "implication": r["implication"], "status": status,
            "model_status": r["status"], "source_ids": valid_ids,
            "sources": [{"id": s, **sources[s]} for s in valid_ids],
            "flags": flags,
        })
    out.sort(key=lambda r: SECTIONS.index(r["section"]))
    return out, findings


# ---------- 실행 ----------
def new_state():
    return {"status": "not_started", "draft": None, "rounds": [], "calls": [],
            "prompt_versions": {"draft": DRAFT_PROMPT, "review": REVIEW_PROMPT}}


def _record_call(state, kind, result, seconds):
    u = result.usage
    state["calls"].append({"kind": kind, "model": result.model, "seconds": round(seconds, 1),
                           "input_tokens": u.input_tokens if u else None, "output_tokens": u.output_tokens if u else None})


def usage_summary(state):
    calls = state["calls"]
    inp = sum(c["input_tokens"] or 0 for c in calls)
    out = sum(c["output_tokens"] or 0 for c in calls)
    model = calls[-1]["model"] if calls else None
    cost = None
    if model:
        for prefix, (pin, pout) in PRICE_PER_MTOK.items():
            if model.startswith(prefix):
                cost = round(inp / 1e6 * pin + out / 1e6 * pout, 4)
    return {"calls": len(calls), "input_tokens": inp, "output_tokens": out, "model": model,
            "seconds": round(sum(c["seconds"] for c in calls), 1), "estimated_cost_usd": cost,
            "cost_basis": "gpt-5.4-mini 공식 단가($0.75/$4.50 per 1M, 2026-10-25 조회) 기준 추정" if cost is not None else None}


def run(state, stats, generate=None, clock=time.monotonic):
    """state를 진행시킵니다(호출한 쪽이 보관). 성공·실패와 무관하게 state를 돌려줍니다.

    stats: service.analyze 결과(통계). generate: 테스트용 교체(기본 common.ai_client.generate_structured).
    """
    started = clock()
    state["status"] = "running"
    state["error"] = None
    if generate is None:
        # 키·모델이 없으면 바로 멈춥니다(유료 호출 없음).
        status = config_status()
        if not status["ready"]:
            err = AIConfigError()
            state["status"] = "failed"
            state["error"] = {"code": err.code, "message": CONFIG_MESSAGE, "retryable": False, "failed_at": "초안",
                              "needs_restart": True, "diagnostic": config_diagnostic(status)}
            pack, sources = build_pack(stats)
            return _finish(state, pack, sources)
        generate = ai_client.generate_structured

    pack, sources = build_pack(stats)
    payload_base = {"context": pack["context"], "facts": pack["facts"], "evidence": pack["evidence"]}

    try:
        if state["draft"] is None:
            t = clock()
            res = generate(instructions=_prompt(DRAFT_PROMPT), input_text=json.dumps(payload_base, ensure_ascii=False),
                           schema=Draft, max_output_tokens=MAX_OUTPUT_TOKENS)
            _record_call(state, "draft", res, clock() - t)
            rows = [r.model_dump() for r in res.data.rows]
            state["draft"] = {"rows": rows, "gaps": list(res.data.gaps), "findings": check_rows(rows, pack)}

        rows = state["rounds"][-1]["rows"] if state["rounds"] else state["draft"]["rows"]
        for number, title in ROUNDS[len(state["rounds"]):]:
            if clock() - started > TIME_BUDGET_SECONDS:
                state["status"] = "incomplete"
                state["error"] = {"code": "MA_AI_TIME_BUDGET", "message": "분석 시간 상한을 넘어 %d회차부터 멈췄습니다. 다시 실행하면 이어서 진행합니다." % number}
                return _finish(state, pack, sources)
            before = check_rows(rows, pack)
            payload = dict(payload_base, round={"number": number, "focus": title}, current_rows=rows, code_findings=before)
            t = clock()
            res = generate(instructions=_prompt(REVIEW_PROMPT), input_text=json.dumps(payload, ensure_ascii=False),
                           schema=Review, max_output_tokens=MAX_OUTPUT_TOKENS)
            _record_call(state, "review_%d" % number, res, clock() - t)
            rv = res.data
            new_rows = [r.model_dump() for r in rv.rows]
            after = check_rows(new_rows, pack)
            state["rounds"].append({
                "number": number, "title": title, "checked": list(rv.checked), "changes": list(rv.changes),
                "evidence": list(rv.evidence), "unresolved": list(rv.unresolved), "model_completed": bool(rv.completed),
                "code_findings_before": [f["detail"] for f in before], "code_findings_after": [f["detail"] for f in after],
                "rows_changed": new_rows != rows, "status": "done", "rows": new_rows,
            })
            rows = new_rows
        state["status"] = "complete"
    except AIError as err:
        state["status"] = "failed"
        is_config = isinstance(err, AIConfigError)
        state["error"] = {"code": err.code, "message": CONFIG_MESSAGE if is_config else err.message, "retryable": err.retryable,
                          "failed_at": "초안" if state["draft"] is None else "%d회차 검토" % (len(state["rounds"]) + 1),
                          "needs_restart": is_config,
                          "diagnostic": config_diagnostic(config_status()) if is_config else error_diagnostic(err)}
    return _finish(state, pack, sources)


def _finish(state, pack, sources):
    rows = state["rounds"][-1]["rows"] if state["rounds"] else (state["draft"]["rows"] if state["draft"] else [])
    final_rows, findings, removed = finalize_rows(rows, pack, sources)
    if state["draft"] is None:
        findings = []  # 초안이 없으면 표 검사 결과(0행 등)는 의미가 없습니다. 실패 사유만 보여 줍니다.
    state["result"] = {
        "complete": state["status"] == "complete",
        "has_draft": state["draft"] is not None,
        "rows": final_rows,
        "removed_rows": removed,  # 출처로 확정되지 않아 표·PDF에서 뺀 행(검토 기록용)
        "gaps": state["draft"]["gaps"] if state["draft"] else [],
        "remaining_findings": [f["detail"] for f in findings],
        "rounds": [{k: v for k, v in r.items() if k != "rows"} for r in state["rounds"]],
        "rounds_total": len(ROUNDS),
        "usage": usage_summary(state),
        "prompt_versions": state["prompt_versions"],
        "status": state["status"],
        "error": state.get("error"),
    }
    return state
