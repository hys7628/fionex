"""시장 분석 AI 분석: 초안 1회 + 회차별 목적이 다른 검토 5회. common.ai_client.generate_structured를 재사용합니다.

- 수치는 코드 계산값(facts)과 근거 기사에 있는 값만 허용합니다. 회차마다 코드가 표를 검사해
  (존재하지 않는 출처 ID, 근거에 없는 수치, 개수 초과, 사실 표시인데 출처 없음, T2T·견적 해석 위험)
  다음 회차 입력에 넣고, 마지막에는 남은 문제를 표에 표시하고 상태를 낮춥니다.
- 근거 기사는 사용 범위상 AI 입력이 허용된 항목만 넣습니다(news_sources.USAGE).
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
# v2(2026-10-26): 일반 뉴스를 GDELT(제목·메타데이터만)로 통일하며 title_only·최초 발견 시각 규칙 추가. v1은 미실행으로 보존.
DRAFT_PROMPT = "market_analysis_draft_v2.md"
REVIEW_PROMPT = "market_analysis_review_v2.md"
MAX_OUTPUT_TOKENS = 4096
TIME_BUDGET_SECONDS = 480.0
MIN_EVIDENCE_FOR_NO_WIDEN = 5

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


def build_pack(stats, news_items):
    """AI 입력 JSON(데이터)과 출처 표. 사용 범위상 AI 입력이 허용된 기사만 넣습니다."""
    facts = build_facts(stats)
    allowed = [it for it in news_items if it.get("ai_input")]
    excluded = [it for it in news_items if not it.get("ai_input")]
    evidence = [{"id": it["id"], "title": it["title"], "source": it["source_name"], "outlet": it.get("outlet"),
                 "language": it.get("language"), "date": evidence_date(it)[0], "date_basis": evidence_date(it)[1],
                 "access": it["access"], "summary": it.get("excerpt") or ""} for it in allowed]
    q = stats["query"]
    pack = {
        "context": {
            "market": "브라질 수입", "product": "%s %s" % (q["code_system_label"], q["code"]),
            "product_name_pt": q.get("code_name"), "period": "%s~%s" % (q["from"], q["to"]),
            "notes": [
                "통계는 해당 코드의 전체 폴리에스터 DTY 시장이며 일반·재생·T2T 원사를 구분하지 않는다.",
                "평균 수입단가는 FOB 기준이며 견적·판매가·도착가격이 아니다.",
                "공급국은 ComexStat 기준 원산지(origin) 국가다.",
                "사용 범위가 확인되지 않은 기사 %d건(KOTRA 등)은 AI 입력에서 제외했다." % len(excluded),
                "일반 뉴스는 GDELT 검색 결과의 제목·메타데이터만 있고 본문은 확인하지 않았다(access=title_only).",
            ],
        },
        "facts": [{"id": "S1", "items": facts}],
        "evidence": evidence,
    }
    src = stats["sources"][0]
    sources = {"S1": {"name": src["name"], "url": src["url"],
                      "date": "자료 갱신 %s · 최신 월 %s" % (src.get("data_updated") or "?", src.get("latest_month") or "?")}}
    for it in allowed:
        date, basis = evidence_date(it)
        sources[it["id"]] = {"name": it["source_name"], "url": it["url"],
                             "date": ("%s %s" % (basis, date)) if date else "게시일 미확인",
                             "title": it["title"], "access": it["access"]}
    return pack, sources, len(excluded)


def evidence_date(it):
    """(날짜 문자열, 기준). 게시일이 있으면 게시일, 없으면 GDELT 최초 발견 시각(게시일 아님)."""
    if it.get("published"):
        return it["published"], "게시일"
    if it.get("seen_at"):
        return it["seen_at"], "GDELT 최초 발견 시각"
    return None, "날짜 미확인"


# ---------- 코드 검사 ----------
_NUM_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


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
    findings = []
    counts = {}
    for i, r in enumerate(rows):
        counts[r["section"]] = counts.get(r["section"], 0) + 1
        bad = [s for s in r["source_ids"] if s not in ids]
        if bad:
            findings.append({"row": i, "kind": "unknown_source", "detail": "존재하지 않는 출처 ID: %s" % ", ".join(bad)})
        if r["status"] == "사실" and not [s for s in r["source_ids"] if s in ids]:
            findings.append({"row": i, "kind": "fact_without_source", "detail": "사실로 표시했지만 유효한 출처가 없음"})
        text = r["content"] + " " + r["implication"]
        loose = [n for n in _numbers(text) if n not in nums and not (n.is_integer() and 1 <= n <= 12)]
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
    """마지막 코드 검사 결과를 표에 반영. 잘못된 출처 ID 제거, 문제가 남은 행은 미확인으로 낮추고 표시."""
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
        flags = [f["detail"] for f in by_row.get(i, [])]
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
    return {"status": "not_started", "draft": None, "rounds": [], "calls": [], "widened": False,
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


def run(state, stats, news, widen_fn=None, generate=None, clock=time.monotonic):
    """state를 진행시킵니다(호출한 쪽이 보관). 성공·실패와 무관하게 state를 돌려줍니다.

    news: news_sources.collect() 결과를 공개 형식으로 바꾼 dict({"items": [...], ...}).
    widen_fn: 근거가 부족할 때 1회만 호출할 넓은 재수집 함수(→ 새 news dict). None이면 생략.
    generate: 테스트용 교체(기본 common.ai_client.generate_structured).
    """
    started = clock()
    state["status"] = "running"
    state["error"] = None
    if generate is None:
        # 키·모델이 없으면 근거 재수집 등 다른 작업 없이 바로 멈춥니다(유료 호출 없음).
        if not config.get_openai_api_key() or not config.get_text_model():
            err = AIConfigError()
            state["status"] = "failed"
            state["error"] = {"code": err.code, "message": err.message, "retryable": False, "failed_at": "초안"}
            pack, sources, state["excluded_count"] = build_pack(stats, news["items"])
            return _finish(state, pack, sources)
        generate = ai_client.generate_structured

    # 근거 보강: AI 입력 가능 기사가 적으면 넓은 검색 1회(상한)
    if state["draft"] is None and widen_fn and not state["widened"]:
        if sum(1 for it in news["items"] if it.get("ai_input")) < MIN_EVIDENCE_FOR_NO_WIDEN:
            state["widened"] = True
            try:
                news = widen_fn()
                state["widen_result"] = "넓은 검색 1회 수행"
            except Exception:
                state["widen_result"] = "넓은 검색 실패(기존 근거로 진행)"
    state["news_used"] = news

    pack, sources, excluded = build_pack(stats, news["items"])
    state["excluded_count"] = excluded
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
        state["error"] = {"code": err.code, "message": err.message, "retryable": err.retryable,
                          "failed_at": "초안" if state["draft"] is None else "%d회차 검토" % (len(state["rounds"]) + 1)}
    return _finish(state, pack, sources)


def _finish(state, pack, sources):
    rows = state["rounds"][-1]["rows"] if state["rounds"] else (state["draft"]["rows"] if state["draft"] else [])
    final_rows, findings = finalize_rows(rows, pack, sources)
    if state["draft"] is None:
        findings = []  # 초안이 없으면 표 검사 결과(0행 등)는 의미가 없습니다. 실패 사유만 보여 줍니다.
    state["result"] = {
        "complete": state["status"] == "complete",
        "has_draft": state["draft"] is not None,
        "rows": final_rows,
        "gaps": state["draft"]["gaps"] if state["draft"] else [],
        "remaining_findings": [f["detail"] for f in findings],
        "rounds": [{k: v for k, v in r.items() if k != "rows"} for r in state["rounds"]],
        "rounds_total": len(ROUNDS),
        "excluded_count": state.get("excluded_count", 0),
        "evidence_count": len(pack["evidence"]),
        "widened": state["widened"],
        "widen_result": state.get("widen_result"),
        "usage": usage_summary(state),
        "prompt_versions": state["prompt_versions"],
        "status": state["status"],
        "error": state.get("error"),
    }
    return state
