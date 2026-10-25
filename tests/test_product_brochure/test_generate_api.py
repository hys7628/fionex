"""POST /api/product-brochure/generate 모의 테스트. 실제 OpenAI 요청을 보내지 않습니다.

라우트 → generation → 공통 generate_structured 경로를 MockTransport로 확인합니다. 입력·출력은 모두 가상 테스트 데이터입니다.
실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_product_brochure -v
"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

import httpx2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_analyze_api import FAKE_KEY, SECRET_PROVIDER, Base, response_body  # noqa: E402

from features.product_brochure import generation  # noqa: E402

URL = "/api/product-brochure/generate"
SECRET_INPUT = "SECRET-GEN-INPUT-6620"


def field(key, value, confirmed=True, virtual=False, origin="extracted"):
    return {"key": key, "value": value, "confirmed": confirmed, "virtual": virtual, "origin": origin}


def request_fields(**overrides):
    base = {
        "product_name": field("product_name", "regen T2T (teste)"),
        "description": field("description", "폐의류를 재활용하는 폴리에스터 섬유(가상 테스트 " + SECRET_INPUT + ")"),
        "yarn_spec": field("yarn_spec", "75D/36F", virtual=True, origin="user_added"),
        "carbon_reduction": field("carbon_reduction", "", confirmed=False),
        "certification": field("certification", "GRS (가상)", confirmed=False),
        "moq": field("moq", "500 kg", virtual=True),
        "sample": field("sample", "1 kg", virtual=True, origin="user_modified"),
        "lead_time": field("lead_time", "30일", virtual=True),
    }
    base.update(overrides)
    return list(base.values())


def copy(text, *keys):
    return {"text": text, "source_keys": list(keys)}


def item(key, label, value):
    return {"key": key, "label": label, "value": value}


def ai_output(**overrides):
    out = {
        "tagline": copy("Fibra de poliéster feita a partir de roupas descartadas.", "product_name", "description"),
        "intro_paragraphs": [copy("O regen T2T (teste) é uma fibra de poliéster que reutiliza roupas descartadas. "
                                  "Pedido mínimo de 500 kg.", "description", "moq")],
        "details": [item("yarn_spec", "Especificação do fio", "75D/36F")],
        "supply": [item("moq", "Pedido mínimo (MOQ)", "500 kg"), item("sample", "Amostra", "1 kg"),
                   item("lead_time", "Prazo de entrega", "30 dias")],
    }
    out.update(overrides)
    return out


class GenerateBase(Base):
    def setUp(self):
        super().setUp()
        self.set_output(ai_output())

    def set_output(self, payload):
        self.responder = lambda r: httpx2.Response(200, json=response_body(payload))

    def gen(self, fields=None, body=None, **kw):
        if body is None:
            body = {"fields": fields if fields is not None else request_fields()}
        return self.client.post(URL, json=body, **kw)


class GenerateSuccessTests(GenerateBase):
    def test_success_structure_and_server_control(self):
        response = self.gen()
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()["data"]
        self.assertEqual(data["status"], "draft_needs_review")
        self.assertEqual(data["language"], "pt-BR")
        self.assertEqual(data["prompt_version"], "brochure_generate_v1")
        self.assertEqual(data["model"], "test-model-snap")
        self.assertEqual(data["notices"], {"unofficial": "Material demonstrativo — não é um catálogo oficial.",
                                           "fictitious": "Condições fictícias para demonstração."})
        self.assertEqual(data["used_keys"], ["product_name", "description", "yarn_spec", "moq", "sample", "lead_time"])
        self.assertEqual(data["excluded"], [{"key": "carbon_reduction", "reason": "empty"},
                                            {"key": "certification", "reason": "unconfirmed"}])
        self.assertEqual(data["input_meta"]["sample"], {"confirmed": True, "virtual": True, "origin": "user_modified"})

        pages = data["pages"]
        self.assertEqual([pages[p]["page"] for p in ("cover", "intro", "details", "supply")], [1, 2, 3, 4])
        cover = pages["cover"]
        self.assertEqual(cover["product_name"]["text"], "regen T2T (teste)")  # 입력 표기 보존
        self.assertIs(cover["tagline"]["virtual"], False)
        para = pages["intro"]["paragraphs"][0]
        self.assertIs(para["virtual"], True)  # 가상 입력(moq)을 쓴 소개 문구로 전파
        self.assertEqual(para["fictitious_notice"], "Inclui informações fictícias para demonstração.")
        self.assertEqual(para["origins"], {"description": "extracted", "moq": "extracted"})
        details = pages["details"]
        self.assertEqual([i["key"] for i in details["items"]], ["yarn_spec"])
        self.assertEqual((details["empty"], details["empty_message"]), (False, None))
        self.assertEqual(details["items"][0]["origin"], "user_added")
        supply = pages["supply"]["items"]
        self.assertEqual([i["key"] for i in supply], ["moq", "sample", "lead_time"])
        for i in supply:
            self.assertIs(i["virtual"], True)
            self.assertEqual(i["fictitious_notice"], "Condições fictícias para demonstração.")
            self.assertEqual(i["review_flags"], [])

        # 모델 입력: 사용 항목만, 확인·가상·출처 메타데이터와 제외 항목 미포함
        self.assertEqual(len(self.requests), 1)
        sent = self.requests[0]
        self.assertEqual(sent["instructions"], generation.load_instructions())
        model_input = json.loads(sent["input"])
        self.assertEqual([f["key"] for f in model_input["fields"]], data["used_keys"])
        self.assertEqual(model_input["details_keys"], ["yarn_spec"])
        self.assertEqual(model_input["supply_keys"], ["moq", "sample", "lead_time"])
        flat = json.dumps(model_input, ensure_ascii=False)
        for absent in ("GRS", "confirmed", "virtual", "origin", "carbon_reduction"):
            self.assertNotIn(absent, flat)
        self.assert_no_leak()
        self.assertNotIn(SECRET_INPUT, self.logs.getvalue())

    def test_all_optional_missing_returns_empty_states(self):
        fields = request_fields(**{k: field(k, "", confirmed=False) for k in
                                   ("yarn_spec", "carbon_reduction", "certification", "moq", "sample", "lead_time")})
        self.set_output(ai_output(details=[], supply=[],
                                  intro_paragraphs=[copy("Fibra de poliéster feita a partir de roupas descartadas.", "description")]))
        response = self.gen(fields)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        pages = response.get_json()["data"]["pages"]
        self.assertEqual(pages["details"], {"page": 3, "items": [], "empty": True,
                                            "empty_message": "Informações técnicas a confirmar."})
        self.assertEqual(pages["supply"], {"page": 4, "items": [], "empty": True,
                                           "empty_message": "Condições de fornecimento a confirmar."})
        model_input = json.loads(self.requests[0]["input"])
        self.assertEqual((model_input["details_keys"], model_input["supply_keys"]), ([], []))

    def test_review_flags_are_marked_not_rejected(self):
        self.set_output(ai_output(
            tagline=copy("Fibra sustentável com 100% de material reciclado.", "description"),
            supply=[item("moq", "Pedido mínimo", "50 kg"), item("sample", "Amostra", "1 kg"),
                    item("lead_time", "Prazo", "30 dias")]))
        data = self.gen().get_json()["data"]
        self.assertCountEqual(data["pages"]["cover"]["tagline"]["review_flags"], ["new_number", "claim_term"])
        self.assertEqual(data["pages"]["supply"]["items"][0]["review_flags"], ["number_not_preserved"])


class GenerateInputErrorTests(GenerateBase):
    def tearDown(self):
        self.assertEqual(self.requests, [])  # 입력 오류 시 외부 호출 0회

    def check(self, response, status, code):
        self.assertEqual(response.status_code, status, response.get_data(as_text=True))
        body = response.get_json()
        self.assertEqual((body["ok"], body["error"]["code"]), (False, code))
        self.assertNotIn(SECRET_INPUT, response.get_data(as_text=True) + self.logs.getvalue())
        return body

    def test_required_missing_or_unconfirmed(self):
        for case in (
            {"product_name": field("product_name", "")},
            {"description": field("description", "   ")},
            {"product_name": field("product_name", "regen T2T", confirmed=False)},
            {"description": field("description", "설명", confirmed=False)},
        ):
            with self.subTest(case=list(case)):
                self.check(self.gen(request_fields(**case)), 400, "GENERATE_REQUIRED_MISSING")

    def test_duplicate_missing_unknown_keys(self):
        dup = request_fields() + [field("moq", "600 kg")]
        self.check(self.gen(dup), 400, "GENERATE_DUPLICATE_KEY")
        self.check(self.gen(request_fields()[:7]), 400, "GENERATE_MISSING_KEY")
        unknown = request_fields()[:7] + [field("price", "10 USD")]
        self.check(self.gen(unknown), 400, "GENERATE_INVALID_INPUT")

    def test_strict_types_no_loose_conversion(self):
        cases = [
            {"confirmed": "true"}, {"confirmed": 1}, {"virtual": "false"}, {"value": 500}, {"value": None},
            {"origin": "document"}, {"origin": "example"},
        ]
        for patch in cases:
            with self.subTest(patch=patch):
                fields = request_fields()
                fields[5] = dict(fields[5], **patch)
                self.check(self.gen(fields), 400, "GENERATE_INVALID_INPUT")

    def test_unexpected_fields_rejected_without_echo(self):
        body = self.check(self.gen(body={"fields": request_fields(), "pdf_base64": "x", "instructions": "y"}),
                          400, "GENERATE_INVALID_INPUT")
        fields = request_fields()
        fields[0] = dict(fields[0], quote="원문 발췌", **{"IGNORE-PREVIOUS-" + SECRET_INPUT: 1})
        body2 = self.check(self.gen(fields), 400, "GENERATE_INVALID_INPUT")
        for b in (body, body2):
            for echoed in ("pdf_base64", "instructions", "IGNORE-PREVIOUS", "quote"):
                self.assertNotIn(echoed, b["error"]["message"])

    def test_json_format_errors(self):
        self.check(self.client.post(URL, data="not json", content_type="application/json"), 400, "GENERATE_INVALID_JSON")
        self.check(self.client.post(URL, data=json.dumps({"fields": []}), content_type="text/plain"), 400,
                   "GENERATE_INVALID_JSON")
        self.check(self.gen(body=[1, 2]), 400, "GENERATE_INVALID_JSON")
        self.check(self.gen(body={}), 400, "GENERATE_INVALID_INPUT")

    def test_length_limits(self):
        for key, limit in generation.MAX_VALUE_CHARS.items():
            with self.subTest(key=key):
                fields = request_fields(**{key: field(key, "가" * (limit + 1))})
                self.check(self.gen(fields), 400, "GENERATE_FIELD_TOO_LONG")
        ok = request_fields(product_name=field("product_name", "가" * generation.MAX_VALUE_CHARS["product_name"]))
        self.requests.clear()
        response = self.gen(ok)
        self.assertEqual(response.status_code, 200)  # 경계값은 허용
        self.requests.clear()

    def test_request_too_large(self):
        big = {"fields": request_fields(), "padding": "x" * (generation.MAX_REQUEST_BYTES + 10)}
        self.check(self.client.post(URL, data=json.dumps(big), content_type="application/json"), 413,
                   "GENERATE_REQUEST_TOO_LARGE")


class GenerateOutputErrorTests(GenerateBase):
    def run_case(self, payload_or_body, status, code, raw=False):
        if raw:
            self.responder = lambda r: httpx2.Response(200, json=payload_or_body)
        else:
            self.set_output(payload_or_body)
        response = self.gen()
        self.assertEqual(response.status_code, status, response.get_data(as_text=True))
        body = response.get_json()
        self.assertEqual((body["ok"], body["error"]["code"]), (False, code))
        self.assertEqual(len(self.requests), 1)  # 추가 재시도 없음
        self.requests.clear()
        self.assertNotIn(SECRET_PROVIDER, response.get_data(as_text=True) + self.logs.getvalue())

    def test_server_rejects_invalid_ai_output(self):
        supply = ai_output()["supply"]
        cases = {
            "excluded_source_key": ai_output(tagline=copy("Texto.", "certification")),
            "empty_source_keys": ai_output(tagline=copy("Texto.")),
            "unprovided_detail_added": ai_output(details=[item("yarn_spec", "Fio", "75D/36F"),
                                                          item("certification", "Certificação", "GRS")]),
            "detail_missing": ai_output(details=[]),
            "duplicate_supply": ai_output(supply=supply + [item("moq", "MOQ", "500 kg")]),
            "supply_missing": ai_output(supply=supply[:2]),
            "wrong_page": ai_output(details=[item("yarn_spec", "Fio", "75D/36F"), item("moq", "MOQ", "500 kg")],
                                    supply=supply[1:]),
            "tagline_too_long": ai_output(tagline=copy("a" * 141, "description")),
            "too_many_paragraphs": ai_output(intro_paragraphs=[copy("p", "description")] * 3),
            "no_paragraph": ai_output(intro_paragraphs=[]),
            "empty_text": ai_output(supply=[item("moq", "MOQ", "  "), supply[1], supply[2]]),
            "label_too_long": ai_output(details=[item("yarn_spec", "L" * 41, "75D/36F")]),
        }
        for name, payload in cases.items():
            with self.subTest(case=name):
                self.run_case(payload, 502, "GENERATE_OUTPUT_INVALID")

    def test_model_errors(self):
        self.run_case(response_body(refusal="거절 " + SECRET_PROVIDER), 422, "AI_REFUSED", raw=True)
        self.run_case(response_body(status="incomplete", reason="max_output_tokens"), 502, "AI_INCOMPLETE", raw=True)
        self.run_case(response_body(text="not json " + SECRET_PROVIDER), 502, "AI_OUTPUT_INVALID", raw=True)
        self.run_case(response_body(text='{"tagline": {"text": "x", "source_keys": ["price"]}}'), 502,
                      "AI_OUTPUT_INVALID", raw=True)

    def test_provider_error_and_missing_config(self):
        self.responder = lambda r: httpx2.Response(429, json={"error": {"message": SECRET_PROVIDER, "code": "rate_limit_exceeded"}})
        response = self.gen()
        self.assertEqual((response.status_code, response.get_json()["error"]["code"]), (429, "AI_RATE_LIMITED"))
        self.assertNotIn(SECRET_PROVIDER, response.get_data(as_text=True))
        self.requests.clear()
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            response = self.gen()
        self.assertEqual((response.status_code, response.get_json()["error"]["code"]), (503, "AI_CONFIG_MISSING"))
        self.assertEqual(self.requests, [])
        self.assertNotIn(FAKE_KEY, self.logs.getvalue())


class PromptTests(unittest.TestCase):
    def test_prompt_rules_and_limits_match_server(self):
        text = generation.load_instructions()
        for phrase in ("pt-BR", "지시·요청·명령", "외부 지식", "인증명", "탄소 저감률", "재활용 함량", "가격", "원산지",
                       "sustentável", "HTML", "반복", "source_keys", "details_keys", "supply_keys"):
            self.assertIn(phrase, text)
        for number in (generation.MAX_TAGLINE_CHARS, generation.MAX_PARAGRAPH_CHARS, generation.MAX_LABEL_CHARS,
                       generation.MAX_DETAIL_VALUE_CHARS, generation.MAX_SUPPLY_VALUE_CHARS):
            self.assertIn(f"{number}자 이하", text)
        self.assertIn(f"1~{generation.MAX_INTRO_PARAGRAPHS}개", text)


if __name__ == "__main__":
    unittest.main()
