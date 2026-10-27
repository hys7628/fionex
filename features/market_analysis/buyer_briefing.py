"""바이어별 AI 브리핑(바이어 목록에서 고른 1곳의 1쪽 브리핑). common.ai_client.generate_structured를 1회 호출합니다.

- 입력 근거: C1 = 국세청 CNPJ 공개 자료(buyers.find로 기준 자료에서 다시 찾음, 화면이 보낸 회사 정보는 믿지 않음),
  S1 = 시장 통계 탭에서 조회한 ComexStat 계산값(조회 묶음 bundle이 있을 때만), T1… = 재생·T2T 공개 근거(사람 검토).
- 관세·반덤핑 자료는 아직 정적 자료 파일이 없어 넣지 않습니다(프롬프트에서 언급 금지, 코드도 검사).
- 모델 출력은 항목마다 코드가 검사합니다: 없는 출처 ID, 근거에 없는 수치, 관세·인증·공급 조건 언급,
  전체 DTY 통계를 T2T 수요로 해석. 문제가 있는 항목은 화면에 넣지 않고 '코드 검사로 뺀 문장'에 이유와 함께 남깁니다.
- 출처명·URL·기준일은 모델이 아니라 코드가 출처 ID로 붙입니다.
- 같은 업체·같은 조회 묶음의 결과는 서버 메모리에 BRIEFING_TTL_SECONDS 동안 두고 다시 호출하지 않습니다(디스크 저장 없음).
- 결과마다 briefing_id를 붙입니다. PDF는 화면이 보낸 내용이 아니라 이 ID로 서버가 보관한 결과를 찾아 만듭니다(재호출 없음).
"""
import json
import re
import secrets
import threading
import time
from pathlib import Path

from pydantic import BaseModel

from common import ai_client
from common.errors import AIConfigError
from features.market_analysis import analysis, buyers

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT = "buyer_briefing_v1.md"
MAX_OUTPUT_TOKENS = 2048
LIMITS = {"overview": 4, "market_context": 3, "approach_points": 4, "expected_questions": 4}
SECTION_LABELS = {"overview": "회사 개요", "market_context": "시장 맥락", "approach_points": "접근 포인트",
                  "expected_questions": "예상 질문"}
BRIEFING_TTL_SECONDS = 3 * 3600
MAX_CACHED = 50
CONFIG_MESSAGE = ("AI 브리핑에 필요한 서버 설정(OpenAI 키·텍스트 모델)이 없어 시작하지 않았습니다. "
                  "등급과 바이어 목록은 그대로 볼 수 있습니다. 관리자가 서버 실행 환경에 설정한 뒤 서버를 다시 시작해야 합니다.")
FIXED_NOTES = [
    "AI가 출처 있는 자료로 작성한 초안입니다. 연락 전 담당자가 원문을 확인해야 합니다.",
    "이 회사의 수입 실적은 공개 자료로 확인할 수 없습니다. 시장 통계(S1)는 품목 전체 수입이며 이 회사의 거래가 아닙니다.",
    "관세·반덤핑 현황은 정적 자료를 준비하기 전이라 포함하지 않았습니다.",
]


class Point(BaseModel):
    text: str
    source_ids: list[str]


class Question(BaseModel):
    question: str
    answer_direction: str
    source_ids: list[str]


class Briefing(BaseModel):
    overview: list[Point]
    market_context: list[Point]
    approach_points: list[Point]
    expected_questions: list[Question]
    gaps: list[str]


class BriefingError(Exception):
    def __init__(self, code, message, http_status, **extra):
        self.code, self.message, self.http_status, self.extra = code, message, http_status, extra
        super().__init__(message)


# ---------- 근거 묶음 ----------
def company_facts(c, today):
    """국세청 공개 자료 → 사실 문장(C1). 전화번호·CNPJ 숫자는 보내지 않습니다(필요 없고 숫자 검사를 흐리게 함)."""
    facts = ["회사명: %s%s" % (c["razao_social"], (" (상호 %s)" % c["nome_fantasia"]) if c.get("nome_fantasia") else ""),
             "주 업종(CNAE): %s · %s" % (c.get("cnae_label") or "", c.get("cnae_desc") or ""),
             "지역: %s, %s주" % (c.get("municipio") or "미상", c.get("uf") or "미상"),
             "국세청 규모 코드: %s" % (c.get("porte") or "미상")]
    start = c.get("inicio_atividade") or ""
    if re.fullmatch(r"\d{8}", start):
        years = today.year - int(start[:4]) - ((today.month, today.day) < (int(start[4:6]), int(start[6:])))
        facts.append("개업일 %s-%s-%s, 업력 %d년(%s 기준)" % (start[:4], start[4:6], start[6:], years, today.isoformat()))
    facts.append("사업장: %s, 대상 업종 사업장 %d곳" % ("본점(matriz)" if c.get("matriz") else "지점 자료(본점 아님)", c.get("sites_matched") or 1))
    if c.get("natureza"):
        facts.append("법인 형태: %s" % c["natureza"])
    facts.append("연락처 등록: 대표 전화 %s, 회사 도메인 %s" % ("있음" if c.get("phones") else "없음",
                                                     c["domain"] if c.get("domain") else "없음"))
    facts.append("우선순위 등급(코드 공개 규칙, 수입 실적 기반 아님): %s · %s" % (c["grade"], c["grade_reason"]))
    return facts


def build_pack(company, buyers_data, stats, today):
    """(AI 입력 JSON, 출처 표)."""
    src = buyers_data["source"]
    sources = {"C1": {"name": src["name"], "url": src["url"], "date": "자료 기준월 %s" % src.get("reference_month")}}
    market_facts = []
    if stats:
        market_facts = analysis.build_facts(stats)
        s = stats["sources"][0]
        snapshot = s.get("cache_status") == "snapshot"  # ComexStat 점검으로 MDIC 공개 원본 스냅샷을 쓴 통계
        sources["S1"] = {"name": s["name"], "url": s["url"],
                         "date": ("MDIC 공개 원본 자료(기준: %s) · 최신 월 %s" % (str(s.get("fetched_at") or "")[:10], s.get("latest_month") or "?"))
                         if snapshot else "자료 갱신 %s · 최신 월 %s" % (s.get("data_updated") or "?", s.get("latest_month") or "?")}
    evidence = []
    for i, e in enumerate(company.get("evidence") or [], 1):
        eid = "T%d" % i
        evidence.append({"id": eid, "title": e.get("title") or "", "published": e.get("published") or "", "checked_at": e.get("checked_at") or ""})
        sources[eid] = {"name": e.get("title") or "공개 근거", "url": e.get("url"), "date": "확인 %s" % (e.get("checked_at") or "?")}
    pack = {
        "company": {"id": "C1", "items": company_facts(company, today)},
        "market_facts": {"id": "S1", "items": market_facts},
        "evidence": evidence,
        "context": {"notes": [
            "이 회사의 수입 실적·수입 품목은 공개 자료로 확인할 수 없다.",
            "S1은 해당 품목코드의 브라질 전체 수입 통계다. 일반·재생·T2T 원사를 구분하지 않는다.",
        ] + ([
            "S1은 ComexStat 조회 실패로 MDIC가 공개한 원본 CSV를 미리 받아 요약한 자료로 계산했다(실시간 조회 아님).",
        ] if stats and stats["sources"][0].get("cache_status") == "snapshot" else []) + [
            "평균 수입단가는 FOB 기준이며 견적·판매가·도착가격이 아니다.",
            "관세·반덤핑 자료는 입력에 없다.",
            "evidence가 비어 있으면 재생·T2T 관련 공개 근거가 없다." if not evidence else "evidence는 사람이 검토한 공개 근거다.",
        ]},
    }
    return pack, sources


# ---------- 코드 검사 ----------
_TARIFF_RE = re.compile(r"(관세|반덤핑|덤핑|세이프가드|antidumping|anti-dumping|tarifa)", re.I)
_CERT_RE = re.compile(r"(인증|GRS|OEKO|Global Recycled|ISO\s?\d)", re.I)
_TERMS_RE = re.compile(r"(견적|판매\s*가|공급\s*가|오퍼|납기|최소\s*주문|MOQ|결제\s*조건|리드\s*타임)", re.I)
_T2T_RE = re.compile(r"(T2T|리젠|재생\s*원사)")
_DEMAND_RE = re.compile(r"(수요|시장\s*규모|시장규모)")


def allowed_numbers(pack):
    nums, pcts = set(), set()
    lines = pack["company"]["items"] + pack["market_facts"]["items"]
    lines += [e["title"] + " " + e["published"] + " " + e["checked_at"] for e in pack["evidence"]]
    for line in lines:
        nums |= analysis._numbers(line)
        pcts |= analysis._percents(line)
    return nums, pcts


def check_text(text, source_ids, pack, valid_ids, nums, pcts):
    """(남길 출처 ID, 문제 목록)."""
    problems = []
    ids = [s for s in source_ids if s in valid_ids]
    if len(ids) != len(source_ids):
        problems.append("존재하지 않는 출처 ID: %s" % ", ".join(s for s in source_ids if s not in valid_ids))
    if not ids:
        problems.append("유효한 출처 없음")
    months = {float(m) for m in analysis._MONTH_WORD_RE.findall(text) if 1 <= int(m) <= 12}
    loose = [n for n in analysis._numbers(text) if n not in nums and n not in months]
    loose += [n for n in analysis._percents(text) if n not in pcts and n not in loose]
    if loose:
        problems.append("근거에 없는 수치: %s" % ", ".join(analysis._fmt_plain(n) for n in sorted(loose)))
    if _TARIFF_RE.search(text):
        problems.append("관세·반덤핑 언급(입력 자료 없음)")
    evidence_text = " ".join(e["title"] for e in pack["evidence"])
    cert = _CERT_RE.search(text)
    if cert and cert.group(0).lower() not in evidence_text.lower():
        problems.append("근거 없는 인증 언급")
    if _TERMS_RE.search(text):
        problems.append("공급 조건(가격·견적·납기 등) 언급")
    if "S1" in ids and _T2T_RE.search(text) and _DEMAND_RE.search(text):
        problems.append("전체 DTY 통계(S1)를 T2T 수요·시장 규모로 해석했을 수 있음")
    return ids, problems


def finalize(data, pack, sources):
    """검사를 통과한 항목만 남기고 출처를 붙입니다. 반환: (sections, questions, removed)."""
    valid = set(sources)
    nums, pcts = allowed_numbers(pack)
    removed, sections = [], {}

    def attach(ids):
        return [dict(sources[i], id=i) for i in ids]

    for key in ("overview", "market_context", "approach_points"):
        kept = []
        for p in getattr(data, key):
            ids, problems = check_text(p.text, p.source_ids, pack, valid, nums, pcts)
            if key == "market_context" and "S1" not in ids and not problems:
                problems.append("시장 맥락인데 시장 통계(S1) 출처 없음")
            if problems:
                removed.append({"section": SECTION_LABELS[key], "text": p.text, "reason": "; ".join(problems)})
            elif len(kept) >= LIMITS[key]:
                removed.append({"section": SECTION_LABELS[key], "text": p.text, "reason": "최대 %d개 초과" % LIMITS[key]})
            else:
                kept.append({"text": p.text, "sources": attach(ids)})
        sections[key] = kept
    questions = []
    for q in data.expected_questions:
        ids, problems = check_text(q.question + " " + q.answer_direction, q.source_ids, pack, valid, nums, pcts)
        if problems:
            removed.append({"section": SECTION_LABELS["expected_questions"], "text": q.question, "reason": "; ".join(problems)})
        elif len(questions) >= LIMITS["expected_questions"]:
            removed.append({"section": SECTION_LABELS["expected_questions"], "text": q.question, "reason": "최대 %d개 초과" % LIMITS["expected_questions"]})
        else:
            questions.append({"question": q.question, "answer_direction": q.answer_direction, "sources": attach(ids)})
    return sections, questions, removed


# ---------- 실행·메모리 보관 ----------
_results = {}
_by_id = {}
_running = set()
_lock = threading.Lock()


def clear_cache():
    with _lock:
        _results.clear()
        _by_id.clear()
        _running.clear()


def _cached(key, now):
    hit = _results.get(key)
    if hit and now - hit[0] <= BRIEFING_TTL_SECONDS:
        return hit[1]
    _results.pop(key, None)
    return None


def get(briefing_id, clock=time.monotonic):
    """보관 중인 브리핑 결과(run이 돌려준 dict) 또는 None(만료·서버 재시작·없는 ID)."""
    with _lock:
        hit = _by_id.get(str(briefing_id or ""))
        if hit and clock() - hit[0] <= BRIEFING_TTL_SECONDS:
            return hit[1]
        _by_id.pop(str(briefing_id or ""), None)
    return None


def run(cnpj, bundle_id=None, bundle=None, bundle_note=None, generate=None, clock=time.monotonic, today=None):
    """브리핑 결과 dict. bundle: service.get_bundle(bundle_id) 결과(없으면 시장 맥락 없이). bundle_note: 묶음을 못 쓴 이유(화면 안내).
    오류: BriefingError(업체 없음·실행 중·설정 누락), AIError(공통 연결)."""
    from features.market_analysis import service  # 순환 import 방지

    company, data = buyers.find(cnpj)
    if company is None:
        raise BriefingError("MA_BUYER_NOT_FOUND", "바이어 목록에서 이 업체를 찾지 못했습니다. 목록을 다시 불러와 주세요.", 404)
    status = analysis.config_status()
    if not status["ready"]:
        raise BriefingError("MA_AI_CONFIG", CONFIG_MESSAGE, 503, needs_restart=True, diagnostic=analysis.config_diagnostic(status))
    key = (cnpj, bundle_id if bundle else None)
    now = clock()
    with _lock:
        hit = _cached(key, now)
        if hit is not None:
            return {**hit, "reused": True}
        if key in _running:
            raise BriefingError("MA_BRIEFING_RUNNING", "이 업체의 브리핑을 이미 만들고 있습니다. 끝날 때까지 기다려 주세요.", 409)
        _running.add(key)
    try:
        today = today or service.now_kst().date()
        stats = bundle["stats"] if bundle else None
        pack, sources = build_pack(company, data, stats, today)
        generate = generate or ai_client.generate_structured
        started = clock()
        try:
            res = generate(instructions=(PROMPT_DIR / PROMPT).read_text(encoding="utf-8"),
                           input_text=json.dumps(pack, ensure_ascii=False), schema=Briefing, max_output_tokens=MAX_OUTPUT_TOKENS)
        except AIConfigError:
            raise BriefingError("MA_AI_CONFIG", CONFIG_MESSAGE, 503, needs_restart=True, diagnostic=analysis.config_diagnostic(analysis.config_status()))
        seconds = round(clock() - started, 1)
        sections, questions, removed = finalize(res.data, pack, sources)
        usage = {"model": res.model, "calls": 1, "seconds": seconds,
                 "input_tokens": res.usage.input_tokens if res.usage else 0, "output_tokens": res.usage.output_tokens if res.usage else 0}
        price = next((v for k, v in analysis.PRICE_PER_MTOK.items() if (res.model or "").startswith(k)), None)
        if price and res.usage:
            usage["estimated_cost_usd"] = round(res.usage.input_tokens / 1e6 * price[0] + res.usage.output_tokens / 1e6 * price[1], 4)
            usage["cost_basis"] = "OpenAI 공식 단가 기준 추정"
        q = stats["query"] if stats else None
        result = {
            "briefing_id": secrets.token_urlsafe(12),
            "company": {k: company.get(k) for k in ("cnpj", "razao_social", "nome_fantasia", "uf", "municipio", "cnae", "cnae_label",
                                                     "grade", "grade_reason")},
            "market": {"included": bool(stats),
                       "query": {"code": q["code"], "code_system_label": q["code_system_label"], "from": q["from"], "to": q["to"]} if q else None,
                       "note": None if stats else (bundle_note or "시장 통계를 조회하지 않아 시장 맥락을 넣지 않았습니다. '시장 통계'에서 분석을 실행한 뒤 다시 받으면 포함됩니다.")},
            "sections": sections,
            "questions": questions,
            "gaps": [g for g in res.data.gaps if g.strip()][:6],
            "removed": removed,
            "notes": FIXED_NOTES,
            "usage": usage,
            "prompt_version": PROMPT,
            "generated_at": service.now_kst().isoformat(timespec="seconds"),
        }
        with _lock:
            if len(_results) >= MAX_CACHED:
                old = min(_results, key=lambda k: _results[k][0])
                _by_id.pop(_results.pop(old)[1]["briefing_id"], None)
            stamp = clock()
            _results[key] = (stamp, result)
            _by_id[result["briefing_id"]] = (stamp, result)
        return {**result, "reused": False}
    finally:
        with _lock:
            _running.discard(key)
