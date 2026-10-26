"""시장 분석 AI 분석·조회 묶음·PDF와 집계 경계 상황 모의 테스트(뉴스 수집 기능은 2026-10-26 삭제). 외부 요청·유료 호출을 보내지 않습니다.

실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_market_analysis -v
"""
import io
import json
import os
import sys
import threading
import time
import unittest
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.errors import AIRateLimitError  # noqa: E402
from features.market_analysis import analysis, pdf_report, service  # noqa: E402
from features.market_analysis import comexstat_client as comex  # noqa: E402

LATEST = service.month_index(2026, 9)


def row(ym, country, fob, kg):
    y, m = ym.split("-")
    return {"year": int(y), "month": int(m), "country": country, "fob": fob, "kg": kg, "code_name": "Fios crus"}


def make_stats(rows=None, start="2025-10", end="2026-09", countries=("190",)):
    if rows is None:
        rows = []
        for i in range(24):
            y, m = 2024 + (9 + i) // 12, (9 + i) % 12 + 1
            ym = "%04d-%02d" % (y, m)
            rows += [row(ym, "China", 20_000_000 + i * 10_000, 18_000_000), row(ym, "Índia", 3_000_000, 2_600_000),
                     row(ym, "Taiwan (Formosa)", 100_000, 30_000)]
        rows.append(row("2026-07", "Coreia do Sul", 39_600, 14_400))
    req = service.validate_request({"code_system": "ncm", "code": "54023310", "from": start, "to": end,
                                    "countries": list(countries)}, LATEST)
    out = service.compute(rows, req, "Fios texturizados de poliésteres, crus")
    out["sources"] = [{"name": "ComexStat (MDIC)", "url": "https://comexstat.mdic.gov.br/", "data_updated": "2026-10-06",
                       "latest_month": "2026-09", "fetched_at": "2026-10-25T17:35:36+09:00", "cache_status": "fresh"}]
    return out


# ---------- AI 분석 ----------
@dataclass
class FakeUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass
class FakeResult:
    data: object
    model: str
    usage: FakeUsage


def rows_ok():
    return [
        {"section": "핵심 요약", "content": "수입액(FOB) USD %s" % "{:,}".format(0), "implication": "x", "status": "사실", "source_ids": ["S1"]},
    ]


class FakeModel:
    """초안·검토 응답을 돌려주는 가짜 generate_structured. 호출 기록을 남깁니다."""

    def __init__(self, draft_rows, review_rows=None, fail_at=None):
        self.draft_rows = draft_rows
        self.review_rows = review_rows
        self.fail_at = fail_at
        self.calls = []

    def __call__(self, *, instructions, input_text, schema, max_output_tokens):
        payload = json.loads(input_text)
        self.calls.append({"schema": schema.__name__, "round": (payload.get("round") or {}).get("number"),
                           "instructions": instructions, "payload": payload})
        if self.fail_at is not None and len(self.calls) == self.fail_at:
            raise AIRateLimitError()
        usage = FakeUsage(1000, 500, 1500)
        if schema is analysis.Draft:
            return FakeResult(analysis.Draft(rows=[analysis.Row(**r) for r in self.draft_rows], gaps=["T2T 관련 기사 없음"]), "gpt-5.4-mini-2026-03-17", usage)
        rows = self.review_rows if self.review_rows is not None else payload["current_rows"]
        return FakeResult(analysis.Review(checked=["확인 %d" % payload["round"]["number"]], changes=[], evidence=["S1"], unresolved=[],
                                          completed=True, rows=[analysis.Row(**r) for r in rows]), "gpt-5.4-mini-2026-03-17", usage)


class AnalysisTest(unittest.TestCase):
    def setUp(self):
        self.stats = make_stats()
        fob = self.stats["summary"]["fob"]
        self.fob_text = "{:,}".format(fob)
        self.good = [
            {"section": "핵심 요약", "content": "수입액(FOB) USD %s" % self.fob_text, "implication": "시장 규모 파악", "status": "사실", "source_ids": ["S1"]},
            {"section": "핵심 요약", "content": "중국 비중이 높다", "implication": "경쟁 확인", "status": "사실", "source_ids": ["S1"]},
            {"section": "핵심 요약", "content": "수입이 계속 늘어날 것", "implication": "추이 확인", "status": "추정", "source_ids": ["S1"]},
        ]

    def run_with(self, model, state=None, clock=None):
        state = state or analysis.new_state()
        kwargs = {"generate": model}
        if clock:
            kwargs["clock"] = clock
        return analysis.run(state, self.stats, **kwargs)

    def test_draft_plus_five_distinct_rounds(self):
        m = FakeModel(self.good)
        st = self.run_with(m)
        self.assertEqual([c["schema"] for c in m.calls], ["Draft"] + ["Review"] * 5)
        self.assertEqual([c["round"] for c in m.calls[1:]], [1, 2, 3, 4, 5])
        self.assertEqual(st["status"], "complete")
        res = st["result"]
        self.assertTrue(res["complete"])
        self.assertEqual(len(res["rounds"]), 5)
        self.assertEqual(res["rounds"][2]["title"], "원문·공식 출처 검증")
        self.assertEqual(res["usage"]["calls"], 6)
        self.assertAlmostEqual(res["usage"]["estimated_cost_usd"], round(6000 / 1e6 * 0.75 + 3000 / 1e6 * 4.5, 4))
        # 출처명·URL은 코드가 붙임
        self.assertEqual(res["rows"][0]["sources"][0]["url"], "https://comexstat.mdic.gov.br/")
        self.assertEqual(res["rows"][0]["status"], "사실")
        self.assertEqual(res["rows"][0]["flags"], [])

    def test_payload_has_stats_only(self):
        m = FakeModel(self.good)
        self.run_with(m)
        draft = m.calls[0]
        self.assertEqual(draft["payload"]["evidence"], [])  # 기사 근거 없음(뉴스 수집 삭제)
        self.assertEqual(draft["instructions"], analysis._prompt(analysis.DRAFT_PROMPT))
        self.assertIn("기사 근거는 없다", " ".join(draft["payload"]["context"]["notes"]))

    def test_fabricated_number_and_source_flagged(self):
        bad = self.good + [
            {"section": "영업 기회", "content": "수입액이 USD 999,999,999로 증가", "implication": "x", "status": "사실", "source_ids": ["S1"]},
            {"section": "위험", "content": "경쟁 심화", "implication": "x", "status": "사실", "source_ids": ["N99", "S9"]},
        ]
        m = FakeModel(bad)  # 검토에서도 고치지 않는 경우
        res = self.run_with(m)["result"]
        # 검토에서도 고치지 않으면 미확인으로 낮아져 표·PDF에서 빠지고 뺀 사유가 남음(2026-10-26)
        self.assertFalse(any(r["section"] in ("영업 기회", "위험") for r in res["rows"]))
        removed = {r["section"]: r for r in res["removed_rows"]}
        self.assertIn("999999999", removed["영업 기회"]["reason"])
        self.assertIn("유효한 출처가 없음", removed["위험"]["reason"])
        self.assertTrue(all(r["status"] == "사실" for r in res["rows"]))
        # 코드 검사 결과가 검토 입력으로 들어감
        self.assertTrue(m.calls[1]["payload"]["code_findings"])

    def test_t2t_and_quote_interpretation_flagged(self):
        rows = self.good + [
            {"section": "영업 기회", "content": "T2T 수요가 큰 시장", "implication": "x", "status": "추정", "source_ids": ["S1"]},
            {"section": "위험", "content": "평균 수입단가를 견적 기준으로 사용", "implication": "x", "status": "추정", "source_ids": ["S1"]},
        ]
        res = self.run_with(FakeModel(rows))["result"]
        reasons = " ".join(r["reason"] for r in res["removed_rows"])  # 해석 위험 행은 표에서 빠지고 사유가 남음
        self.assertIn("T2T", reasons)
        self.assertIn("견적", reasons)

    def test_unconfirmed_rows_reviewed_five_times_then_removed(self):
        rows = self.good + [
            {"section": "영업 기회", "content": "중국 외 공급선 수요가 있을 것", "implication": "x", "status": "추정", "source_ids": ["S1"]},
            {"section": "위험", "content": "가격 경쟁 심화 가능성", "implication": "x", "status": "미확인", "source_ids": []},
        ]
        m = FakeModel(rows)  # 5회 내내 고치지 않는 경우
        res = self.run_with(m)["result"]
        self.assertEqual(analysis.REVIEW_PROMPT, "market_analysis_review_v3.md")
        for call in m.calls[1:]:  # 1~5회차 모두에 '확정하거나 삭제' 검사가 들어감
            self.assertTrue(any(f["kind"] == "unconfirmed" for f in call["payload"]["code_findings"]))
        self.assertTrue(all(r["status"] == "사실" for r in res["rows"]))
        self.assertEqual(sorted(r["status"] for r in res["removed_rows"]), ["미확인", "추정", "추정"])  # 기본 초안의 추정 행 1건 포함
        self.assertFalse(any("확정하거나 삭제" in f for f in res["remaining_findings"]))

    def test_small_number_not_in_sources_is_flagged_but_month_words_allowed(self):
        pack, _ = analysis.build_pack(self.stats)
        rows = [{"section": "핵심 요약", "content": "나머지 국가는 모두 개별 비중이 1% 미만이다", "implication": "x", "status": "사실", "source_ids": ["S1"]},
                {"section": "핵심 요약", "content": "3개월 연속 증가, 7월 최고", "implication": "x", "status": "사실", "source_ids": ["S1"]}]
        kinds = {(f["row"], f["kind"]) for f in analysis.check_rows(rows, pack)}
        self.assertIn((0, "unverified_number"), kinds)      # '1%'는 근거에 없는 수치
        self.assertNotIn((1, "unverified_number"), kinds)   # 'N개월'·'N월'은 허용

    def test_unconfirmed_row_confirmed_in_review_is_kept(self):
        draft = self.good + [{"section": "영업 기회", "content": "중국 의존이 높다", "implication": "x", "status": "추정", "source_ids": ["S1"]}]
        fixed = [dict(r, status="사실", source_ids=["S1"]) for r in draft if r["status"] != "추정" or r["section"] == "영업 기회"]
        res = self.run_with(FakeModel(draft, review_rows=fixed))["result"]
        self.assertIn("중국 의존이 높다", [r["content"] for r in res["rows"]])
        self.assertEqual(res["removed_rows"], [])

    def test_section_limits_trimmed(self):
        rows = self.good + [{"section": "영업 기회", "content": "기회 %d" % i, "implication": "x", "status": "사실", "source_ids": ["S1"]} for i in range(5)]
        res = self.run_with(FakeModel(rows))["result"]
        self.assertEqual(sum(1 for r in res["rows"] if r["section"] == "영업 기회"), 3)

    def test_failure_then_resume_without_repeating(self):
        m = FakeModel(self.good, fail_at=4)  # 초안, 1, 2 회차 후 3회차 실패
        st = self.run_with(m)
        self.assertEqual(st["status"], "failed")
        self.assertFalse(st["result"]["complete"])
        self.assertEqual(len(st["result"]["rounds"]), 2)
        self.assertEqual(st["result"]["error"]["failed_at"], "3회차 검토")
        m2 = FakeModel(self.good)
        st = self.run_with(m2, state=st)
        self.assertEqual([c["round"] for c in m2.calls], [3, 4, 5])  # 초안·1·2회차 재호출 없음
        self.assertEqual(st["status"], "complete")

    def test_missing_openai_key_no_calls_no_fake_findings(self):
        from common.errors import AIConfigError

        def no_key(**kwargs):
            raise AIConfigError()
        st = self.run_with(no_key)
        res = st["result"]
        self.assertEqual((st["status"], res["has_draft"], res["usage"]["calls"]), ("failed", False, 0))
        self.assertEqual((res["rows"], res["remaining_findings"]), ([], []))
        self.assertEqual(res["error"]["code"], "AI_CONFIG_MISSING")
        data = pdf_report.build_pdf({"stats": self.stats, "ai": res})
        self.assertTrue(data.startswith(b"%PDF-"))

    def test_real_client_without_key_no_calls(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "", "OPENAI_MODEL": ""}):
            st = analysis.run(analysis.new_state(), self.stats)
        self.assertEqual((st["status"], st["error"]["code"], st["result"]["usage"]["calls"]), ("failed", "AI_CONFIG_MISSING", 0))

    def test_config_diagnostic_key_model_separately(self):
        cases = [({"OPENAI_API_KEY": "", "OPENAI_MODEL": "m"}, "key_missing", ["OPENAI_API_KEY"]),
                 ({"OPENAI_API_KEY": "sk-FAKE-secret", "OPENAI_MODEL": ""}, "model_missing", ["OPENAI_MODEL"]),
                 ({"OPENAI_API_KEY": " ", "OPENAI_MODEL": ""}, "key_and_model_missing", ["OPENAI_API_KEY", "OPENAI_MODEL"])]
        for env, kind, missing in cases:
            with self.subTest(kind=kind), mock.patch.dict(os.environ, env):
                st = analysis.run(analysis.new_state(), self.stats)
                err = st["result"]["error"]
                self.assertEqual((err["diagnostic"]["kind"], err["diagnostic"]["env_missing"]), (kind, missing))
                self.assertTrue(err["needs_restart"])
                self.assertEqual(st["result"]["usage"]["calls"], 0)
                self.assertNotIn("FAKE-secret", json.dumps(st["result"], ensure_ascii=False))  # 값은 담지 않음
                self.assertEqual(analysis.config_status()["missing"], missing)

    def test_provider_errors_diagnosed_separately(self):
        from common.errors import AIAuthError, AIModelUnavailableError
        for exc, kind in ((AIAuthError(status_code=401), "auth_failed"), (AIRateLimitError(status_code=429), "rate_limited"),
                          (AIModelUnavailableError(status_code=404), "model_unavailable")):
            def fail(**kwargs):
                raise exc
            with self.subTest(kind=kind):
                res = self.run_with(fail)["result"]
                d = res["error"]["diagnostic"]
                self.assertEqual((d["kind"], d["status_code"], res["error"]["needs_restart"]), (kind, exc.status_code, False))
                self.assertEqual(res["error"]["message"], exc.message)  # 공급자 오류는 설정 안내와 다른 문장

    def test_time_budget_stops(self):
        ticks = iter([0, 0, 1, 1, 2, 2, 999, 999, 999, 999, 999, 999, 999])
        st = self.run_with(FakeModel(self.good), clock=lambda: next(ticks))
        self.assertEqual(st["status"], "incomplete")
        self.assertEqual(st["error"]["code"], "MA_AI_TIME_BUDGET")
        self.assertLess(len(st["rounds"]), 5)

class BundleTest(unittest.TestCase):
    def setUp(self):
        service.clear_bundles()
        self.addCleanup(service.clear_bundles)
        self.bid = service.create_bundle(make_stats())

    def test_ai_runs_on_stats_and_reuses_complete(self):
        b = service.get_bundle(self.bid)
        self.assertNotIn("news", b)  # 뉴스 단계 없이 바로 AI 분석
        stats = b["stats"]
        good = [{"section": "핵심 요약", "content": "수입액(FOB) USD {:,}".format(stats["summary"]["fob"]), "implication": "x", "status": "사실", "source_ids": ["S1"]}]
        m = FakeModel(good)
        with mock.patch.object(analysis.ai_client, "generate_structured", m), \
                mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-FAKE", "OPENAI_MODEL": "test-model"}):
            first = service.run_ai(self.bid)
            second = service.run_ai(self.bid)
        self.assertEqual(len(m.calls), 6)  # 두 번째는 재호출 없음
        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])

    def test_concurrent_run_blocked(self):
        b = service.get_bundle(self.bid)
        b["lock"].acquire()
        try:
            with self.assertRaises(service.BundleError) as ctx:
                service.run_ai(self.bid)
            self.assertEqual((ctx.exception.code, ctx.exception.http_status), ("MA_AI_RUNNING", 409))
        finally:
            b["lock"].release()

    def test_server_restart_expires_bundle(self):
        service.clear_bundles()  # 서버 재시작과 같은 효과(메모리 비움)
        with self.assertRaises(service.BundleError) as ctx:
            service.run_ai(self.bid)
        self.assertEqual(ctx.exception.http_status, 410)

    def test_config_missing_route_reports_diagnostic(self):
        from app import create_app
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "", "OPENAI_MODEL": ""}):
            res = create_app().test_client().post("/api/market-analysis/ai", json={"bundle_id": self.bid})
        body = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(body["data"]["error"]["diagnostic"]["kind"], "key_and_model_missing")
        self.assertEqual(body["data"]["usage"]["calls"], 0)

    def test_meta_reports_presence_only(self):
        service.clear_cache()
        self.addCleanup(service.clear_cache)
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-FAKE-secret", "OPENAI_MODEL": ""}), \
                mock.patch.object(comex, "get_latest_month", return_value=(2026, 9, "2026-10-06")):
            m = service.meta()
        self.assertEqual(m["ai"], {"ready": False, "api_key_set": True, "model_set": False, "missing": ["OPENAI_MODEL"]})
        self.assertNotIn("general_news", m)  # 뉴스 공급자 정보 없음(뉴스 수집 삭제)
        self.assertNotIn("FAKE-secret", json.dumps(m, ensure_ascii=False))

# ---------- 집계 경계 상황 ----------
class EdgeTest(unittest.TestCase):
    def test_partial_missing_weight_does_not_inflate_price(self):
        rows = [row("2026-01", "China", 1000, 1000), row("2026-01", "Índia", 5000, None)]
        req = service.validate_request({"code_system": "ncm", "code": "54023310", "from": "2026-01", "to": "2026-01"}, LATEST)
        r = service.compute(rows, req)
        self.assertEqual(r["summary"]["fob"], 6000)          # 합계는 있는 값 모두
        self.assertAlmostEqual(r["summary"]["unit_price"], 1.0)  # 단가는 짝이 맞는 행만(6.0이 아님)
        self.assertAlmostEqual(r["monthly"][0]["unit_price"], 1.0)
        self.assertIn("빠진 행이 1건", " ".join(r["notes"]))

    def test_brasil_origin_note(self):
        rows = [row("2026-01", "China", 1000, 1000), row("2026-01", "Brasil", 50, 10)]
        req = service.validate_request({"code_system": "ncm", "code": "54023310", "from": "2026-01", "to": "2026-01"}, LATEST)
        self.assertIn("원산지", " ".join(service.compute(rows, req)["notes"]))

    def test_brasil_excluded_from_supplier_list_but_kept_in_total(self):
        rows = [row("2026-01", "China", 900, 900), row("2026-01", "Brasil", 100, 10), row("2026-01", "Coreia do Sul", 50, 20)]
        req = service.validate_request({"code_system": "ncm", "code": "54023310", "from": "2026-01", "to": "2026-01"}, LATEST)
        r = service.compute(rows, req)
        names = [c["country"]["name_pt"] for c in r["suppliers"]["top"]]
        self.assertEqual(names, ["China", "Coreia do Sul"])  # 브라질 제외, 순위 다시 매김
        self.assertEqual((r["suppliers"]["count"], r["suppliers"]["korea"]["rank"]), (2, 2))
        self.assertEqual(r["summary"]["fob"], 1050)  # 전체 수입액(공식 합계)은 브라질 포함
        self.assertAlmostEqual(r["suppliers"]["top"][0]["share"], 900 / 1050 * 100)
        self.assertIn("USD 100(전체의 9.5%)", " ".join(r["notes"]))

    def test_brasil_not_selectable(self):
        self.assertNotIn(service.BRAZIL_CODE, [c["code"] for c in service.country_list()])
        with self.assertRaises(service.InputError) as ctx:
            service.validate_request({"code_system": "ncm", "code": "54023310", "from": "2026-01", "to": "2026-01",
                                      "countries": [service.BRAZIL_CODE]}, LATEST)
        self.assertIn("대상 시장", ctx.exception.fields["countries"])


class CacheDateTest(unittest.TestCase):
    def setUp(self):
        service.clear_cache()
        self.addCleanup(service.clear_cache)

    def test_kst_date_change_refetches(self):
        days = iter([datetime(2026, 10, 25, 23, 59, tzinfo=service.KST)] * 6 + [datetime(2026, 10, 26, 0, 1, tzinfo=service.KST)] * 10)
        payload = {"code_system": "ncm", "code": "54023310", "from": "2026-01", "to": "2026-03"}
        with mock.patch.object(service, "now_kst", lambda: next(days)), \
                mock.patch.object(comex, "get_latest_month", return_value=(2026, 9, "2026-10-06")) as latest, \
                mock.patch.object(comex, "query_imports", return_value=[row("2026-01", "China", 10, 5)]) as q:
            service.analyze(payload)
            service.analyze(payload)  # 같은 날: 재사용
            service.analyze(payload)  # 날짜 바뀜: 다시 조회
        self.assertEqual(q.call_count, 2)
        self.assertEqual(latest.call_count, 2)


class ComexConcurrencyTest(unittest.TestCase):
    def test_parallel_requests_are_serialized_with_interval(self):
        active, peak, starts = [0], [0], []
        lock = threading.Lock()

        def fake(method, url, body, timeout):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
                starts.append(time.monotonic())
            time.sleep(0.05)
            with lock:
                active[0] -= 1
            return 200, json.dumps({"data": {"year": "2026", "monthNumber": "09", "updated": "2026-10-06"}}).encode()
        comex._last_call[0] = 0.0
        with mock.patch.object(comex, "_transport", fake), mock.patch.object(comex, "MIN_INTERVAL_SECONDS", 0.1):
            threads = [threading.Thread(target=comex.get_latest_month) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(peak[0], 1)
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        # Windows 타이머 해상도(약 15ms) 오차 허용
        self.assertTrue(all(g >= 0.08 for g in gaps), gaps)


# ---------- PDF ----------
class PdfTest(unittest.TestCase):
    def payload(self, ai=True):
        stats = make_stats(start="2023-10", end="2026-09", countries=("190", "160", "249"))
        stats["sources"][0]["url"] = "https://www.example.com/" + "muito-longo-caminho/" * 12 + "?q=ação&x=ç"
        ai_res = None
        if ai:
            pack, sources = analysis.build_pack(stats)
            rows = [{"section": "핵심 요약", "content": "수입액 확인 <b>& 원사</b> " + "긴 문장 " * 30, "implication": "포르투갈어 Coreia do Sul · ação", "status": "사실", "source_ids": ["S1"]}]
            final, _, _ = analysis.finalize_rows(rows, pack, sources)
            ai_res = {"complete": False, "rows": final, "gaps": ["T2T 근거 없음"], "remaining_findings": [], "rounds": [
                {"number": 1, "title": "자료 적합성", "checked": ["범위 확인"], "changes": [], "evidence": ["S1"], "unresolved": [], "status": "done"}],
                "rounds_total": 5, "usage": {"model": "gpt-5.4-mini", "calls": 2}, "prompt_versions": {"draft": "d", "review": "r"},
                "error": {"message": "2회차 실패"}}
        return {"stats": stats, "ai": ai_res}

    def test_pdf_renders_korean_portuguese_long_tables(self):
        from pypdf import PdfReader
        data = pdf_report.build_pdf(self.payload())
        self.assertTrue(data.startswith(b"%PDF-"))
        reader = PdfReader(io.BytesIO(data))
        self.assertGreaterEqual(len(reader.pages), 3)
        text = "\n".join(p.extract_text() for p in reader.pages)
        for s in ("브라질 시장/바이어 분석 보고서", "Coreia do Sul", "ação", "검토 미완료", "미실행", "Índia", "<b>& 원사</b>"):
            self.assertIn(s, text)
        for s in ("KOTRA", "NewsData", "GDELT", "기사 제목", "출처별 연결 상태"):  # 뉴스 영역 없음
            self.assertNotIn(s, text)
        self.assertEqual(reader.pages[0].mediabox.width, 595.2756)  # A4 세로
        links = [a.get_object()["/A"]["/URI"] for p in reader.pages for a in (p.get("/Annots") or [])
                 if a.get_object().get("/A") and "/URI" in a.get_object()["/A"]]
        self.assertTrue(any("muito-longo-caminho" in u for u in links))

    def test_pdf_only_fact_rows(self):
        from pypdf import PdfReader
        p = self.payload()
        p["ai"]["rows"].append({"section": "위험", "content": "추정위험문장", "implication": "x", "status": "추정", "model_status": "추정",
                                "source_ids": [], "sources": [], "flags": []})
        p["ai"]["removed_rows"] = [{"section": "영업 기회", "content": "뺀항목문장", "status": "미확인", "model_status": "추정", "reason": "r"}]
        text = "\n".join(pg.extract_text() for pg in PdfReader(io.BytesIO(pdf_report.build_pdf(p))).pages)
        self.assertNotIn("추정위험문장", text)  # 사실이 아닌 행은 PDF 표에 없음
        self.assertIn("표에서 뺀 항목 1건", text)

    def test_supplier_price_has_no_check_flag(self):
        from pypdf import PdfReader
        p = self.payload(ai=False)
        for c in p["stats"]["suppliers"]["top"]:
            c["price_flag"] = "high"  # 데이터에 표시가 있어도 공급국 표에는 출력하지 않음
        text = "\n".join(pg.extract_text() for pg in PdfReader(io.BytesIO(pdf_report.build_pdf(p))).pages)
        self.assertNotIn("· 확인 필요", text)

    def test_route_pdf_and_errors(self):
        from app import create_app
        client = create_app().test_client()
        res = client.post("/api/market-analysis/pdf", json=self.payload())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "application/pdf")
        self.assertIn("attachment; filename=\"market_analysis_54023310_2023-10_2026-09_", res.headers["Content-Disposition"])
        self.assertEqual(client.post("/api/market-analysis/pdf", json={}).status_code, 400)
        broken = self.payload()
        del broken["stats"]["summary"]
        self.assertEqual(client.post("/api/market-analysis/pdf", json=broken).status_code, 400)

    def test_route_news_removed_and_ai_expired(self):
        from app import create_app
        client = create_app().test_client()
        self.assertEqual(client.post("/api/market-analysis/news", json={"bundle_id": "nope"}).status_code, 404)  # 뉴스 API 삭제
        self.assertEqual(client.post("/api/market-analysis/ai", json={"bundle_id": "nope"}).status_code, 410)


if __name__ == "__main__":
    unittest.main()
