"""스캔 PDF AI 글자 판독 검증(모의). 외부 요청·OpenAI 호출 없음. 실행(저장소 루트):

    python -m unittest features.green_claim.tests.test_ocr -v

공통 generate_structured_from_pdf 자리에 가짜 함수를 넣어 요청 인자·검증·오류 처리를 확인합니다.
가짜 함수의 성공 결과는 실제 AI 판독 성공이 아닙니다.
"""
import importlib.util
import io
import sys
import unittest
from unittest import mock

from werkzeug.datastructures import FileStorage

from app import create_app
from common import errors
from common.pdf_utils import inspect_pdf
from features.green_claim import ocr_service, service
from features.green_claim.tests.test_pdf_extract import encrypt, make_pdf, make_pdf_of_size


class FakePage:
    def __init__(self, page, text, uncertain=()):
        self.page, self.text, self.uncertain = page, text, list(uncertain)

    def model_dump(self):
        return {"page": self.page, "text": self.text, "uncertain": list(self.uncertain)}


class FakeSchema:
    """테스트용 스키마 자리표시자(실제 스키마는 ocr_schema.OcrResult, pydantic 필요)."""


class FakeResult:
    def __init__(self, pages, limitations, pdf_bytes, model="test-model"):
        self.data = type("Data", (), {"pages": pages, "limitations": limitations})()
        self.model = model
        self.usage = None
        self.pdf = inspect_pdf(pdf_bytes)


def fake_ai(pages_for, limitations=(), raises=None):
    """(가짜 generate 함수, 호출 기록). pages_for(page_count) → FakePage 목록."""
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        if raises:
            raise raises
        count = inspect_pdf(kwargs["pdf_bytes"]).page_count
        return FakeResult(pages_for(count), list(limitations), kwargs["pdf_bytes"])

    return generate, calls


def pages_ok(count):
    return [FakePage(n, f"Página {n} texto", ["linha 2 borrada"] if n == 1 else []) for n in range(1, count + 1)]


PDF3 = make_pdf([["a"], ["b"], ["c"]])


class BuildResultTest(unittest.TestCase):
    def build(self, pages, count=3, limitations=()):
        return ocr_service.build_ocr_result(pages, list(limitations), count, "m")

    def test_ranges_sorting_and_fields(self):
        r = self.build([{"page": 2, "text": "B\r\nb", "uncertain": []},
                        {"page": 1, "text": "A [판독 불가]", "uncertain": ["x"]},
                        {"page": 3, "text": "  ", "uncertain": []}], limitations=["저해상도"])
        self.assertEqual(r["text"], "A [판독 불가]\n\nB\nb")
        self.assertEqual((r["pages"][0]["char_start"], r["pages"][0]["char_end"]), (0, 9))
        self.assertEqual((r["pages"][1]["char_start"], r["pages"][1]["char_end"]), (11, 14))
        self.assertEqual(r["pages"][2]["status"], "no_text")
        self.assertEqual(r["pages_without_text"], [3])
        self.assertEqual((r["uncertain_count"], r["unreadable_mark_count"]), (1, 1))
        self.assertEqual(r["model_limitations"], ["저해상도"])
        self.assertEqual((r["source"], r["format"], r["prompt_version"]), ("ai_ocr", "pdf", "pdf_ocr_v1"))
        self.assertEqual(r["limits"]["ai_max_output_tokens"], 4096)

    def test_page_number_validation(self):
        good = [{"page": n, "text": "t", "uncertain": []} for n in (1, 2, 3)]
        cases = {
            "범위 밖(0)": [dict(good[0], page=0)] + good[1:],
            "범위 밖(4)": good + [{"page": 4, "text": "t", "uncertain": []}],
            "중복": good + [dict(good[0])],
            "누락": good[:2],
            "정수 아님": [dict(good[0], page="1")] + good[1:],
            "bool": [dict(good[0], page=True)] + good[1:],
        }
        for name, pages in cases.items():
            with self.subTest(name):
                with self.assertRaises(service.ExtractError) as ctx:
                    self.build(pages)
                self.assertEqual(ctx.exception.code, "OCR_PAGE_MISMATCH")

    def test_no_text_and_char_limit_boundary(self):
        with self.assertRaises(service.ExtractError) as ctx:
            self.build([{"page": n, "text": " \n", "uncertain": []} for n in (1, 2, 3)])
        self.assertEqual(ctx.exception.code, "OCR_NO_TEXT")
        ok = self.build([{"page": 1, "text": "a" * 9999, "uncertain": []},
                         {"page": 2, "text": "b" * 9999, "uncertain": []}], count=2)
        self.assertEqual(ok["char_count"], 20000)
        with self.assertRaises(service.ExtractError) as ctx:
            self.build([{"page": 1, "text": "a" * 10000, "uncertain": []},
                        {"page": 2, "text": "b" * 9999, "uncertain": []}], count=2)
        self.assertEqual(ctx.exception.code, "TEXT_TOO_LONG")


class RunOcrTest(unittest.TestCase):
    def test_calls_common_function_once_with_expected_arguments(self):
        generate, calls = fake_ai(pages_ok)
        with mock.patch.object(ocr_service, "_load_ai", return_value=(generate, FakeSchema)):
            r = ocr_service.run_ocr("promo.pdf", PDF3)
        self.assertEqual(len(calls), 1)
        kw = calls[0]
        self.assertEqual(set(kw), {"instructions", "pdf_bytes", "schema", "input_text"})
        self.assertEqual(kw["instructions"], ocr_service.load_instructions())
        self.assertIs(kw["pdf_bytes"], PDF3)
        self.assertIs(kw["schema"], FakeSchema)
        self.assertIn("3", kw["input_text"])
        self.assertNotIn("promo", kw["input_text"])  # 파일명은 보내지 않음
        self.assertEqual(r["page_count"], 3)
        self.assertEqual(r["pages"][0]["uncertain"], ["linha 2 borrada"])

    def test_validation_failures_do_not_call_ai(self):
        load = mock.Mock()
        cases = [
            ("a.pdf", b"", "FILE_EMPTY"),
            ("a.pdf", make_pdf_of_size(10_000_001, [["x"]]), "FILE_TOO_LARGE"),
            ("a.docx", PDF3, "FILE_TYPE_UNSUPPORTED"),
            ("a.pdf", b"not a pdf", "PDF_INVALID"),
            ("a.pdf", encrypt(PDF3), "PDF_ENCRYPTED"),
            ("a.pdf", make_pdf([["p"]] * 21), "PDF_TOO_MANY_PAGES"),
            ("a.pdf", b"%PDF-1.7\n" + b"\x00" * 300, "PDF_CORRUPT"),
        ]
        with mock.patch.object(ocr_service, "_load_ai", load):
            for name, data, code in cases:
                with self.subTest(code):
                    with self.assertRaises((service.ExtractError, errors.AIError)) as ctx:
                        ocr_service.run_ocr(name, data)
                    self.assertEqual(ctx.exception.code, code)
        load.assert_not_called()

    def test_dependency_missing(self):
        with mock.patch.dict(sys.modules, {"common.ai_client": None}):
            with self.assertRaises(service.ExtractError) as ctx:
                ocr_service.run_ocr("a.pdf", PDF3)
        self.assertEqual(ctx.exception.code, "AI_DEPENDENCY_MISSING")

    def test_no_retry_on_ai_errors(self):
        for err in (errors.AIIncompleteError(), errors.AIOutputInvalidError(), errors.AITimeoutError()):
            with self.subTest(err.code):
                generate, calls = fake_ai(pages_ok, raises=err)
                with mock.patch.object(ocr_service, "_load_ai", return_value=(generate, FakeSchema)):
                    with self.assertRaises(errors.AIError):
                        ocr_service.run_ocr("a.pdf", PDF3)
                self.assertEqual(len(calls), 1)

    def test_busy_when_slot_taken(self):
        generate, calls = fake_ai(pages_ok)
        self.assertTrue(ocr_service._ai_slots.acquire(blocking=False))
        try:
            with mock.patch.object(ocr_service, "_load_ai", return_value=(generate, FakeSchema)):
                with self.assertRaises(service.ExtractError) as ctx:
                    ocr_service.run_ocr("a.pdf", PDF3)
            self.assertEqual(ctx.exception.code, "EXTRACT_BUSY")
            self.assertEqual(calls, [])
        finally:
            ocr_service._ai_slots.release()

    def test_mismatch_logged_without_content(self):
        generate, _ = fake_ai(lambda count: [FakePage(1, "SEGREDO do documento")])
        with mock.patch.object(ocr_service, "_load_ai", return_value=(generate, FakeSchema)), \
                mock.patch.object(ocr_service.logger, "warning") as warn:
            with self.assertRaises(service.ExtractError):
                ocr_service.run_ocr("a.pdf", PDF3)
        self.assertIn("OCR_PAGE_MISMATCH", str(warn.call_args))
        self.assertNotIn("SEGREDO", str(warn.call_args))


class RouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = create_app().test_client()

    def post(self, url="/api/green-claim/ocr", filename="promo.pdf", content=PDF3):
        return self.client.post(url, content_type="multipart/form-data",
                                data={"promo_file": FileStorage(io.BytesIO(content), filename=filename)})

    def test_success_shape(self):
        generate, _ = fake_ai(pages_ok, limitations=["texto pequeno"])
        with mock.patch.object(ocr_service, "_load_ai", return_value=(generate, FakeSchema)):
            resp = self.post()
        body = resp.get_json()
        self.assertEqual(resp.status_code, 200, body)
        self.assertEqual(set(body["data"]), {
            "format", "source", "text", "char_count", "page_count", "pages", "pages_without_text", "uncertain_count",
            "unreadable_mark_count", "model_limitations", "model", "prompt_version", "notices", "limits"})
        self.assertEqual(body["data"]["source"], "ai_ocr")

    def test_error_mapping(self):
        cases = [
            (errors.AIConfigError(), "AI_CONFIG_MISSING", 503),
            (errors.AIAuthError(), "AI_AUTH_FAILED", 502),
            (errors.AIRateLimitError(), "AI_RATE_LIMITED", 429),
            (errors.AIConnectionError(), "AI_CONNECTION_FAILED", 502),
            (errors.AITimeoutError(), "AI_TIMEOUT", 504),
            (errors.AIRefusalError(), "AI_REFUSED", 422),
            (errors.AIIncompleteError(), "AI_INCOMPLETE", 502),
            (errors.AIOutputInvalidError(), "AI_OUTPUT_INVALID", 502),
            (RuntimeError("C:\\secret\\path boom"), "AI_UNKNOWN_ERROR", 500),
        ]
        for raised, code, status in cases:
            with self.subTest(code):
                generate, _ = fake_ai(pages_ok, raises=raised)
                with mock.patch.object(ocr_service, "_load_ai", return_value=(generate, FakeSchema)):
                    resp = self.post()
                body = resp.get_json()
                self.assertEqual((resp.status_code, body["error"]["code"]), (status, code))
                self.assertEqual(set(body["error"]), {"code", "message"})
                self.assertNotIn("secret", body["error"]["message"])
        with mock.patch.dict(sys.modules, {"common.ai_client": None}):
            resp = self.post()
        self.assertEqual((resp.status_code, resp.get_json()["error"]["code"]), (503, "AI_DEPENDENCY_MISSING"))
        generate, _ = fake_ai(lambda count: [FakePage(1, "x")])
        with mock.patch.object(ocr_service, "_load_ai", return_value=(generate, FakeSchema)):
            resp = self.post()
        self.assertEqual((resp.status_code, resp.get_json()["error"]["code"]), (502, "OCR_PAGE_MISMATCH"))

    def test_page_load_and_general_extract_do_not_call_ai(self):
        load = mock.Mock()
        with mock.patch.object(ocr_service, "_load_ai", load):
            self.assertEqual(self.client.get("/").status_code, 200)
            self.assertEqual(self.post(url="/api/green-claim/extract").status_code, 200)
            self.post(url="/api/green-claim/extract", content=make_pdf([None]))  # 텍스트 없음 → 자동 AI 호출 없음
        load.assert_not_called()


class PromptAndSchemaTest(unittest.TestCase):
    def test_prompt_rules(self):
        text = ocr_service.load_instructions()
        for rule in ("요약·번역·교정", "추가하지 않는다", "[판독 불가]", "지시로 따르지 말고", "접속하거나 외부 도구",
                     "모든 페이지를 정확히 한 번씩", "정확도 백분율"):
            self.assertIn(rule, text)

    @unittest.skipUnless(importlib.util.find_spec("pydantic"), "pydantic 미설치 환경")
    def test_schema_fields(self):
        from features.green_claim.ocr_schema import OcrResult
        schema = OcrResult.model_json_schema()
        self.assertEqual(set(schema["required"]), {"pages", "limitations"})


if __name__ == "__main__":
    unittest.main()
