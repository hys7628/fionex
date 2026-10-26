"""바이어 우선순위 등급(공개 규칙)과 바이어별 AI 브리핑 모의 테스트. 외부 요청·유료 호출을 보내지 않습니다(가짜 generate).

실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_market_analysis -v
"""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import create_app  # noqa: E402
from common.errors import AIRateLimitError  # noqa: E402
from features.market_analysis import analysis, buyer_briefing as bb, buyers, service  # noqa: E402
from test_phase2 import FakeResult, FakeUsage, make_stats  # noqa: E402

READY = {"ready": True, "api_key_set": True, "model_set": True, "missing": []}


def company(cnae, phones=("(11) 1234-5678",), domain="tex.com.br"):
    return {"cnae": cnae, "phones": list(phones), "domain": domain, "cnae_desc": "x"}


class GradeTest(unittest.TestCase):
    def test_public_rules(self):
        self.assertEqual(buyers.grade(company("1323500"))["grade"], "A")              # 합성섬유 직물 + 전화·도메인
        self.assertEqual(buyers.grade(company("1323500", domain=None))["grade"], "B")  # 관련도 높음, 연락 중간
        self.assertEqual(buyers.grade(company("1330800", phones=(), domain=None))["grade"], "B")  # 연락처 없음
        self.assertEqual(buyers.grade(company("1340502"))["grade"], "B")              # 염색·가공(중간)
        self.assertEqual(buyers.grade(company("1321900"))["grade"], "C")              # 면 직물(낮음)
        g = buyers.grade(company("1340501"))
        self.assertEqual((g["grade"], g["relevance"], g["contact"]), ("A", "high", "high"))
        self.assertIn("업종 관련도 높음(날염·가공사(텍스처링))", g["reason"])
        self.assertIn("대표 전화·회사 도메인", g["reason"])

    def test_evidence_raises_one_step(self):
        self.assertEqual(buyers.grade(company("1321900"), True)["grade"], "B")
        self.assertEqual(buyers.grade(company("1340502"), True)["grade"], "A")
        top = buyers.grade(company("1323500"), True)
        self.assertEqual((top["grade"], top["raised"]), ("A", False))
        self.assertIn("한 단계 올림", buyers.grade(company("1321900"), True)["reason"])

    def test_load_sorted_by_grade_with_counts(self):
        d = buyers.load()
        grades = [r["grade"] for r in d["companies"]]
        self.assertEqual(grades, sorted(grades))
        self.assertEqual(sum(d["counts"]["grades"].values()), len(d["companies"]))
        self.assertEqual(d["companies"][0]["grade"], "A")
        self.assertNotIn(d["companies"][0]["cnae"], ("1321900", "1322700"))  # 첫 업체가 면·천연섬유가 아님
        self.assertEqual(d["grade_note"], "수입 실적 기반 아님 · 업종과 공개 근거 기준")
        self.assertTrue(all(r["grade_reason"] for r in d["companies"]))

    def test_evidence_file_raises_and_sorts_first_within_grade(self):
        base = buyers.load()["companies"]
        target = next(r for r in base if r["grade"] == "C")
        with tempfile.TemporaryDirectory() as tmp:
            ev = Path(tmp) / "ev.json"
            ev.write_text(json.dumps({"reviewed_at": "2026-10-26", "companies": [{"cnpj": target["cnpj"], "evidence": [
                {"title": "Relatório de sustentabilidade", "url": "https://example.com/r", "published": "2026-05-01", "checked_at": "2026-10-26"}]}]}),
                encoding="utf-8")
            with mock.patch.object(buyers, "EVIDENCE_FILE", ev):
                rows = buyers.load()["companies"]
        row = next(r for r in rows if r["cnpj"] == target["cnpj"])
        self.assertEqual(row["grade"], "B")
        first_b = next(r for r in rows if r["grade"] == "B")
        self.assertEqual(first_b["cnpj"], target["cnpj"])  # B 안에서 근거 업체 먼저


def briefing(**kw):
    data = dict(
        overview=[bb.Point(text="합성섬유 직물 업체다.", source_ids=["C1"]),
                  bb.Point(text="없는 출처를 쓴 문장", source_ids=["X9"])],
        market_context=[],
        approach_points=[bb.Point(text="재생 원사 사용 계획을 첫 통화에서 확인한다.", source_ids=["C1"]),
                         bb.Point(text="연 999톤을 제안한다.", source_ids=["C1"]),
                         bb.Point(text="관세 인하를 강조한다.", source_ids=["C1"]),
                         bb.Point(text="GRS 인증 원사를 소개한다.", source_ids=["C1"]),
                         bb.Point(text="견적을 먼저 보낸다.", source_ids=["C1"])],
        expected_questions=[bb.Question(question="재생 원사를 쓰나요?", answer_direction="사용 여부를 먼저 묻는다.", source_ids=["C1"])],
        gaps=["재생·T2T 공개 근거 없음"])
    data.update(kw)
    return bb.Briefing(**data)


class FakeGen:
    def __init__(self, result, error=None):
        self.result, self.error, self.calls = result, error, []

    def __call__(self, *, instructions, input_text, schema, max_output_tokens):
        self.calls.append({"instructions": instructions, "payload": json.loads(input_text), "schema": schema})
        if self.error:
            raise self.error
        return FakeResult(self.result, "gpt-5.4-mini-2026-03-17", FakeUsage(1200, 400, 1600))


class BriefingTest(unittest.TestCase):
    def setUp(self):
        bb.clear_cache()
        self.addCleanup(bb.clear_cache)
        p = mock.patch.object(analysis, "config_status", return_value=READY)
        p.start()
        self.addCleanup(p.stop)
        self.cnpj = buyers.load()["companies"][0]["cnpj"]

    def test_code_checks_remove_unsupported_items(self):
        gen = FakeGen(briefing())
        out = bb.run(self.cnpj, generate=gen, today=date(2026, 10, 26))
        self.assertEqual([p["text"] for p in out["sections"]["overview"]], ["합성섬유 직물 업체다."])
        self.assertEqual(out["sections"]["overview"][0]["sources"][0]["id"], "C1")
        self.assertIn("Receita Federal", out["sections"]["overview"][0]["sources"][0]["name"])
        self.assertEqual([p["text"] for p in out["sections"]["approach_points"]], ["재생 원사 사용 계획을 첫 통화에서 확인한다."])
        reasons = {r["text"]: r["reason"] for r in out["removed"]}
        self.assertIn("존재하지 않는 출처 ID: X9", reasons["없는 출처를 쓴 문장"])
        self.assertIn("근거에 없는 수치: 999", reasons["연 999톤을 제안한다."])
        self.assertIn("관세", reasons["관세 인하를 강조한다."])
        self.assertIn("인증", reasons["GRS 인증 원사를 소개한다."])
        self.assertIn("공급 조건", reasons["견적을 먼저 보낸다."])
        self.assertEqual(len(out["questions"]), 1)
        self.assertFalse(out["market"]["included"])
        self.assertEqual(out["usage"]["calls"], 1)
        self.assertEqual(out["prompt_version"], "buyer_briefing_v1.md")
        payload = gen.calls[0]["payload"]
        self.assertEqual(payload["market_facts"]["items"], [])
        text = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn(self.cnpj, text)  # CNPJ 번호를 보내지 않음(전화번호는 아래 테스트)
        self.assertIn("관세·반덤핑 자료는 입력에 없다.", payload["context"]["notes"])

    def test_phone_numbers_not_sent(self):
        gen = FakeGen(briefing())
        row = buyers.load()["companies"][0]
        bb.run(self.cnpj, generate=gen, today=date(2026, 10, 26))
        text = json.dumps(gen.calls[0]["payload"], ensure_ascii=False)
        for phone in row["phones"]:
            self.assertNotIn(phone, text)

    def test_same_company_reused_without_new_call(self):
        gen = FakeGen(briefing())
        first = bb.run(self.cnpj, generate=gen)
        second = bb.run(self.cnpj, generate=gen)
        self.assertEqual(len(gen.calls), 1)
        self.assertEqual((first["reused"], second["reused"]), (False, True))

    def test_market_context_from_bundle(self):
        stats = make_stats()
        bid = service.create_bundle(stats)
        self.addCleanup(service.clear_bundles)
        facts = analysis.build_facts(stats)
        fob_line = next(f for f in facts if f.startswith("수입액(FOB)"))
        gen = FakeGen(briefing(market_context=[bb.Point(text="품목 전체 " + fob_line + "이다.", source_ids=["S1"]),
                                               bb.Point(text="T2T 수요 규모가 크다.", source_ids=["S1"])]))
        out = bb.run(self.cnpj, bundle_id=bid, bundle=service.get_bundle(bid), generate=gen)
        self.assertTrue(out["market"]["included"])
        self.assertEqual(len(out["sections"]["market_context"]), 1)
        self.assertEqual(out["sections"]["market_context"][0]["sources"][0]["id"], "S1")
        self.assertTrue(any("T2T 수요" in r["reason"] for r in out["removed"]))
        self.assertEqual(gen.calls[0]["payload"]["market_facts"]["items"], facts)

    def test_market_context_without_s1_is_removed(self):
        gen = FakeGen(briefing(market_context=[bb.Point(text="시장이 크다.", source_ids=["C1"])]))
        out = bb.run(self.cnpj, generate=gen)
        self.assertEqual(out["sections"]["market_context"], [])
        self.assertTrue(any("S1" in r["reason"] for r in out["removed"]))

    def test_errors(self):
        with self.assertRaises(bb.BriefingError) as ctx:
            bb.run("00000000000000", generate=FakeGen(briefing()))
        self.assertEqual(ctx.exception.code, "MA_BUYER_NOT_FOUND")
        with mock.patch.object(analysis, "config_status", return_value={"ready": False, "api_key_set": False, "model_set": True,
                                                                         "missing": ["OPENAI_API_KEY"]}):
            gen = FakeGen(briefing())
            with self.assertRaises(bb.BriefingError) as ctx:
                bb.run(self.cnpj, generate=gen)
            self.assertEqual(ctx.exception.code, "MA_AI_CONFIG")
            self.assertEqual(gen.calls, [])  # 설정이 없으면 호출하지 않음
        with self.assertRaises(AIRateLimitError):
            bb.run(self.cnpj, generate=FakeGen(None, error=AIRateLimitError()))
        out = bb.run(self.cnpj, generate=FakeGen(briefing()))  # 실패 뒤 다시 실행 가능(실행 중 표시 해제)
        self.assertFalse(out["reused"])


class BriefingRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = create_app().test_client()

    def setUp(self):
        bb.clear_cache()
        self.addCleanup(bb.clear_cache)
        for p in (mock.patch.object(analysis, "config_status", return_value=READY),
                  mock.patch.object(bb.ai_client, "generate_structured", FakeGen(briefing()))):
            p.start()
            self.addCleanup(p.stop)
        self.cnpj = buyers.load()["companies"][0]["cnpj"]

    def post(self, body):
        return self.client.post("/api/market-analysis/buyer-briefing", json=body)

    def test_route(self):
        self.assertEqual(self.post({"cnpj": "123"}).status_code, 400)
        res = self.post({"cnpj": self.cnpj, "bundle_id": "expired-id"})
        body = res.get_json()
        self.assertEqual(res.status_code, 200, body)
        self.assertTrue(body["ok"])
        self.assertIn("만료", body["data"]["market"]["note"])
        self.assertEqual(body["data"]["company"]["cnpj"], self.cnpj)
        self.assertEqual(self.post({"cnpj": "00000000000000"}).status_code, 404)

    def test_buyers_route_has_grades(self):
        body = self.client.get("/api/market-analysis/buyers").get_json()
        self.assertTrue(body["ok"])
        self.assertIn("grade", body["data"]["companies"][0])
        self.assertIn("grades", body["data"]["counts"])


if __name__ == "__main__":
    unittest.main()
