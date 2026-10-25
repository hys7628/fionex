"""홈 뉴스 AI 요약 모의 테스트. 실제 OpenAI·뉴스 요청을 보내지 않습니다.

실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_home -v

common.ai_client._create_client를 httpx2.MockTransport 클라이언트로 바꿔 공통 클라이언트 경로를 그대로 지나갑니다.
키·모델 값은 가짜 문자열이며 실제 .env를 읽지 않습니다. 뉴스 제목은 가상 문장입니다.
"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

import httpx2
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common import ai_client  # noqa: E402
from features.home import news_summary, service  # noqa: E402

FAKE_KEY = "sk-test-FAKE-KEY-DO-NOT-USE-0000"


def news(id_, title, origin="google", lang="pt-BR"):
    return {"id": id_, "title": title, "url": "https://example.com/" + id_, "media": "TEST",
            "published_at": "2026-10-25T10:00:00+00:00", "origin": origin, "lang": lang}


def response_body(text):
    return {
        "id": "resp_test", "object": "response", "created_at": 0, "status": "completed", "model": "test-model-2026",
        "output": [{"type": "message", "id": "msg_test", "status": "completed", "role": "assistant",
                    "content": [{"type": "output_text", "text": text, "annotations": []}]}],
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    }


class FakeOpenAI:
    """요청을 기록하고 responder(요청 JSON) 결과를 돌려줍니다. responder는 (status, body) 반환."""

    def __init__(self, responder):
        self.responder = responder
        self.requests = []

    def factory(self, api_key, timeout, max_retries):
        def handler(request):
            payload = json.loads(request.content or b"{}")
            self.requests.append(payload)
            status, body = self.responder(payload)
            return httpx2.Response(status, json=body)
        return OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries,
                      http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))

    def inputs(self, index=-1):
        return json.loads(self.requests[index]["input"])


def echo(summaries):
    """요청 입력의 id마다 summaries[title] 값을 돌려주는 정상 응답."""
    def responder(payload):
        items = [{"id": i["id"], "summary_ko": summaries.get(i["title"], "")} for i in json.loads(payload["input"])]
        return 200, response_body(json.dumps({"items": items}, ensure_ascii=False))
    return responder


class SummaryTestBase(unittest.TestCase):
    env = {"OPENAI_API_KEY": FAKE_KEY, "OPENAI_MODEL": "test-model"}

    def setUp(self):
        clean = {k: v for k, v in os.environ.items() if not k.startswith("OPENAI_")}
        clean.update(self.env)
        p = mock.patch.dict(os.environ, clean, clear=True)
        p.start()
        self.addCleanup(p.stop)
        news_summary._cache.clear()
        self.addCleanup(news_summary._cache.clear)

    def use(self, responder):
        fake = FakeOpenAI(responder)
        p = mock.patch.object(ai_client, "_create_client", fake.factory)
        p.start()
        self.addCleanup(p.stop)
        return fake


class ValidationTests(unittest.TestCase):
    def test_numbers(self):
        src = "Exportações de fios sobem 12,5% e somam US$ 1,2 bilhão em 2026"
        self.assertEqual(news_summary.unverified_numbers("2026년 원사 수출 12,5% 증가", src), [])
        self.assertEqual(news_summary.unverified_numbers("원사 수출 12.5% 늘어 1.2 bilhão", src), [])
        self.assertEqual(news_summary.unverified_numbers("원사 수출 12억 달러", src), ["12"])
        self.assertEqual(news_summary.unverified_numbers("2027년 원사 수출 증가", src), ["2027"])
        self.assertEqual(news_summary.unverified_numbers("수출 15% 증가", "Setor têxtil espera retomada em 2027"), ["15"])
        self.assertEqual(news_summary.unverified_numbers("수출 1200톤", "Venda de 1.200 toneladas"), ["1200"])
        self.assertEqual(news_summary.unverified_numbers("수출 ２０２６년", "em 2026"), ["non_ascii_digit"])

    def test_check_summary(self):
        title = "Setor têxtil espera retomada em 2027"
        self.assertEqual(news_summary.check_summary("섬유 업계, 2027년 회복 기대", title), ("섬유 업계, 2027년 회복 기대", None))
        self.assertEqual(news_summary.check_summary("섬유 업계 2027년 회복, 성장률 15% 전망", title)[1], "unverified_number")
        self.assertEqual(news_summary.check_summary("", title), ("", "empty"))
        self.assertEqual(news_summary.check_summary(123, title)[1], "not_string")
        self.assertEqual(news_summary.check_summary("가" * 81, title)[1], "too_long")
        self.assertEqual(news_summary.check_summary("첫 줄\n둘째 줄", title)[1], "multiline")
        self.assertEqual(news_summary.check_summary("Setor têxtil espera retomada", title)[1], "not_korean")

    def test_ids(self):
        requested = [{"id": "a", "title": "Fábricas ampliam uso de fio reciclado"},
                     {"id": "b", "title": "Setor têxtil espera retomada"},
                     {"id": "c", "title": "Lojas abrem vagas temporárias no Natal"}]
        output = [{"id": "a", "summary_ko": "공장들, 재활용 원사 사용 확대"},
                  {"id": "zzz", "summary_ko": "요청하지 않은 id"},
                  {"id": "b", "summary_ko": "섬유 업계 회복 기대"},
                  {"id": "b", "summary_ko": "다른 값"},
                  "not a dict"]
        summaries, reasons = news_summary.validate_summaries(requested, output)
        self.assertEqual(summaries, {"a": "공장들, 재활용 원사 사용 확대", "b": "", "c": ""})
        self.assertEqual(reasons["unknown_id"], 1)
        self.assertEqual(reasons["duplicate_id"], 1)
        self.assertEqual(reasons["missing_id"], 1)
        self.assertEqual(reasons["invalid_entry"], 1)
        same, _ = news_summary.validate_summaries(requested[:1], [output[0], output[0]])
        self.assertEqual(same, {"a": "공장들, 재활용 원사 사용 확대"})

    def test_targets(self):
        self.assertTrue(news_summary.is_target(news("1", "Fábricas ampliam uso de fio")))
        self.assertTrue(news_summary.is_target(news("1", "Fábricas ampliam uso de fio", origin="abit")))
        self.assertFalse(news_summary.is_target(news("1", "브라질 섬유 시장 동향", origin="kotra", lang="ko")))
        self.assertFalse(news_summary.is_target(news("1", "Brazil textile market news", origin="kotra", lang="pt-BR")))
        self.assertFalse(news_summary.is_target(news("1", "Textile market grows fast", lang="en")))
        self.assertFalse(news_summary.is_target(news("1", "Moda têxtil")))

    def test_prompts_load(self):
        for name in ("news_summary_v1.md", "news_summary_v2.md"):
            text = news_summary.load_prompt(name)
            self.assertIn("규칙:", text)
            self.assertNotIn("## instructions", text)
            self.assertNotIn("코드 검증", text)  # 머리말은 지시문에 들어가지 않음
        self.assertIn("예시", news_summary.load_prompt("news_summary_v2.md"))
        self.assertNotIn("예시", news_summary.load_prompt("news_summary_v1.md"))

    def test_prompt_v3_rules_and_examples(self):
        self.assertEqual(news_summary.PROMPT_FILE, "news_summary_v3.md")
        text = news_summary.load_prompt()
        self.assertIn("의미 범위를 임의로 넓히거나 일반화하지 않습니다", text)
        self.assertIn("title에 없는 숫자", text)  # 기존 규칙 유지
        requested = json.loads(text.split("입력:\n", 1)[1].split("\n출력:", 1)[0])
        output = json.loads(text.split("출력:\n", 1)[1])["items"]
        self.assertEqual([r["id"] for r in requested], ["ex1", "ex2", "ex3", "ex4"])  # 정확히 4개
        self.assertEqual([o["id"] for o in output], ["ex1", "ex2", "ex3", "ex4"])
        self.assertIn("12,5%", requested[1]["title"])  # 수치 함정
        self.assertEqual(output[2]["summary_ko"], "")  # 정보 부족
        self.assertIn("resíduos florestais", requested[3]["title"])  # 용어 보존
        self.assertIn("산림 부산물", output[3]["summary_ko"])
        # 예시 출력도 코드 검증(숫자·id·형식)을 통과해야 합니다.
        summaries, reasons = news_summary.validate_summaries(requested, output)
        self.assertEqual(dict(reasons), {"empty": 1})
        self.assertEqual(summaries["ex2"], output[1]["summary_ko"])


class SummarizeTests(SummaryTestBase):
    ITEMS = [
        news("g1", "Fábricas do Nordeste ampliam uso de fio de poliéster reciclado"),
        news("g2", "Setor têxtil espera retomada em 2027"),
        news("a1", "Veja as novidades da semana", origin="abit"),
        news("k1", "브라질 섬유 시장 동향 보고", origin="kotra", lang="ko"),
    ]
    ANSWERS = {
        "Fábricas do Nordeste ampliam uso de fio de poliéster reciclado": "북동부 공장들, 재활용 폴리에스터 원사 사용 확대",
        "Setor têxtil espera retomada em 2027": "섬유 업계, 2027년 회복 기대하며 성장률 15% 전망",  # 없는 숫자 15
        "Veja as novidades da semana": "",
    }

    def test_batch_validation_and_cache(self):
        fake = self.use(echo(self.ANSWERS))
        result = news_summary.summarize(self.ITEMS)
        self.assertEqual(len(fake.requests), 1)  # 한 번에 묶어 요청
        sent = fake.inputs()
        self.assertEqual({i["id"] for i in sent}, {"g1", "g2", "a1"})  # KOTRA 제외
        self.assertEqual(set(sent[0]), {"id", "title"})  # 제목만 보냄
        self.assertEqual(fake.requests[0]["model"], "test-model")
        self.assertIs(fake.requests[0]["store"], False)
        self.assertEqual(result, {"status": "ok", "summaries": {"g1": "북동부 공장들, 재활용 폴리에스터 원사 사용 확대"}})
        # 없는 숫자 → 요약 폐기, 정보 부족 → 빈 값. 둘 다 캐시해 다시 묻지 않음
        self.assertEqual(news_summary.cached(self.ITEMS[1]), "")
        self.assertEqual(news_summary.cached(self.ITEMS[2]), "")
        again = news_summary.summarize(self.ITEMS)
        self.assertEqual(len(fake.requests), 1)
        self.assertEqual(again, result)

    def test_only_new_articles_requested(self):
        fake = self.use(echo(self.ANSWERS))
        news_summary.summarize(self.ITEMS[:1])
        newer = news("g3", "Indústria têxtil abre novas vagas em Blumenau")
        news_summary.summarize(self.ITEMS[:1] + [newer])
        self.assertEqual(len(fake.requests), 2)
        self.assertEqual([i["id"] for i in fake.inputs()], ["g3"])
        # 같은 id라도 제목이 바뀌면 새 기사로 봅니다.
        changed = dict(self.ITEMS[0], title="Fábricas do Nordeste ampliam uso de fio reciclado")
        news_summary.summarize([changed])
        self.assertEqual(len(fake.requests), 3)

    def test_cache_expires(self):
        fake = self.use(echo(self.ANSWERS))
        news_summary.summarize(self.ITEMS[:1])
        for entry in news_summary._cache.values():
            entry["expires"] = 0
        news_summary.summarize(self.ITEMS[:1])
        self.assertEqual(len(fake.requests), 2)

    def test_batches_large_input(self):
        fake = self.use(echo({}))
        many = [news(f"g{i}", f"Notícia têxtil número {i} do dia") for i in range(news_summary.BATCH_SIZE + 5)]
        news_summary.summarize(many)
        self.assertEqual([len(json.loads(r["input"])) for r in fake.requests], [news_summary.BATCH_SIZE, 5])

    def test_broken_json_keeps_nothing_cached(self):
        fake = self.use(lambda payload: (200, response_body('{"items": [{"id": "g1", "summary_ko": ')))
        result = news_summary.summarize(self.ITEMS)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["summaries"], {})
        self.assertIsNone(news_summary.cached(self.ITEMS[0]))  # 실패는 캐시하지 않음 → 다음에 재시도
        news_summary.summarize(self.ITEMS)
        self.assertEqual(len(fake.requests), 2)

    def test_wrong_shape_json(self):
        self.use(lambda payload: (200, response_body(json.dumps([{"id": "g1", "summary_ko": "목록 형태"}]))))
        self.assertEqual(news_summary.summarize(self.ITEMS)["status"], "error")

    def test_unknown_ids_ignored(self):
        self.use(lambda payload: (200, response_body(json.dumps({"items": [{"id": "x9", "summary_ko": "가짜 id 요약"}]}))))
        result = news_summary.summarize(self.ITEMS)
        self.assertEqual(result, {"status": "ok", "summaries": {}})
        self.assertEqual(news_summary.cached(self.ITEMS[0]), "")

    def test_api_error(self):
        self.use(lambda payload: (500, {"error": {"message": "server", "type": "error", "code": None}}))
        result = news_summary.summarize(self.ITEMS)
        self.assertEqual(result["status"], "error")
        self.assertIn("원문 제목만", result["message"])

    def test_rate_limit(self):
        self.use(lambda payload: (429, {"error": {"message": "limit", "type": "error", "code": None}}))
        self.assertEqual(news_summary.summarize(self.ITEMS)["status"], "error")

    def test_no_kotra_request(self):
        fake = self.use(echo({}))
        result = news_summary.summarize(self.ITEMS[3:])
        self.assertEqual(fake.requests, [])
        self.assertEqual(result, {"status": "ok", "summaries": {}})


class NoKeyTests(SummaryTestBase):
    env = {"OPENAI_MODEL": "test-model"}

    def test_no_key_unavailable_without_request(self):
        fake = self.use(echo({}))
        result = news_summary.summarize(SummarizeTests.ITEMS)
        self.assertEqual(fake.requests, [])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["message"], "AI 요약을 사용할 수 없습니다. 원문 제목만 표시합니다.")
        self.assertIsNone(news_summary.cached(SummarizeTests.ITEMS[0]))


class ServiceTests(SummaryTestBase):
    """뉴스 수집 결과에 요약을 붙이는 부분. 외부 뉴스 요청은 가짜 수집 함수로 바꿉니다."""

    def setUp(self):
        super().setUp()
        service._news_cache.clear()
        self.addCleanup(service._news_cache.clear)
        fetchers = {
            "kotra": lambda: [news("k1", "브라질 섬유 시장 동향 보고", origin="kotra", lang="ko")],
            "google": lambda: [news("g1", "Fábricas do Nordeste ampliam uso de fio de poliéster reciclado")],
            "abit": lambda: [news("a1", "Setor têxtil espera retomada em 2027", origin="abit")],
        }
        p = mock.patch.dict(service._NEWS_FETCHERS, fetchers)
        p.start()
        self.addCleanup(p.stop)

    def test_news_then_summaries(self):
        fake = self.use(echo({"Fábricas do Nordeste ampliam uso de fio de poliéster reciclado": "북동부 공장들, 재활용 원사 사용 확대",
                              "Setor têxtil espera retomada em 2027": "섬유 업계, 2027년 회복 기대"}))
        first = service.get_news()
        self.assertEqual(fake.requests, [])  # 목록 요청은 AI를 부르지 않음
        self.assertEqual(first["summary"], {"pending": 2})
        self.assertFalse(any("summary_ko" in i for i in first["items"]))

        summaries = service.summarize_news()
        self.assertEqual(len(fake.requests), 1)
        self.assertEqual(summaries["summaries"], {"g1": "북동부 공장들, 재활용 원사 사용 확대", "a1": "섬유 업계, 2027년 회복 기대"})

        second = service.get_news()
        by_id = {i["id"]: i for i in second["items"]}
        self.assertEqual(by_id["g1"]["summary_ko"], "북동부 공장들, 재활용 원사 사용 확대")
        self.assertNotIn("summary_ko", by_id["k1"])  # KOTRA
        self.assertEqual(second["summary"], {"pending": 0})
        self.assertNotIn("summary_ko", service._news_cache["google"]["items"][0])  # 수집 캐시는 원문 그대로

        # 같은 기사를 다시 수집(refresh)해도 요약은 재사용
        service.get_news(refresh="google")
        service.summarize_news()
        self.assertEqual(len(fake.requests), 1)

    def test_no_key_news_still_listed(self):
        os.environ.pop("OPENAI_API_KEY")
        self.use(echo({}))
        data = service.get_news()
        self.assertEqual(len(data["items"]), 3)
        self.assertEqual(service.summarize_news()["status"], "unavailable")
        self.assertEqual(len(service.get_news()["items"]), 3)


if __name__ == "__main__":
    unittest.main()
