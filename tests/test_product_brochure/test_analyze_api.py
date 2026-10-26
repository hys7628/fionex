"""POST /api/product-brochure/analyze 와 추출 후처리 모의 테스트.

실제 OpenAI 요청을 보내지 않습니다. common.ai_client._create_client를 httpx2.MockTransport 클라이언트로 교체해
라우트 → 서비스 → 공통 generate_structured_from_pdf 경로 전체를 확인합니다.
테스트 PDF는 pypdf로 만든 가상 자료입니다. 스캔 PDF 판독 품질은 검증하지 않습니다.
실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_product_brochure -v
"""
import io
import json
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import httpx2
from openai import OpenAI
from pypdf import PdfWriter

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from common import ai_client, config  # noqa: E402
from features.product_brochure import routes, service  # noqa: E402

URL = "/api/product-brochure/analyze"
FAKE_KEY = "sk-test-FAKE-KEY-BROCHURE-0000"
SECRET_DOC = "SECRET-BROCHURE-DOC-8812"
SECRET_PROVIDER = "PROVIDER-RAW-BROCHURE-3301"
SECRET_FILENAME = "C:/Users/someone/비밀폴더/고객자료_SECRETNAME.pdf"
MiB = 1024 * 1024


def make_pdf(pages=1, pad=0, encrypt=None):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    meta = {"/Title": SECRET_DOC}
    if pad:
        meta["/Pad"] = "a" * pad
    writer.add_metadata(meta)
    if encrypt:
        writer.encrypt(user_password="", owner_password="o", algorithm=encrypt)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_pdf_of_size(size):
    pad = 100
    for _ in range(5):
        data = make_pdf(pad=pad)
        if len(data) == size:
            return data
        pad += size - len(data)
    raise AssertionError("크기 맞춤 실패")


def field(key, value=None, status="not_found", evidence=(), virtual=False, note=None):
    return {"key": key, "value": value, "status": status, "evidence": list(evidence),
            "marked_virtual": virtual, "note": note}


def full_extraction(**overrides):
    base = {
        "product_name": field("product_name", "리젠 T2T", "found", [{"page": 1, "quote": "리젠 T2T"}]),
        "description": field("description", "폐의류 재활용 폴리에스터", "found", [{"page": 1, "quote": "폐의류"}]),
        "yarn_spec": field("yarn_spec"),
        "carbon_reduction": field("carbon_reduction"),
        "certification": field("certification"),
        "moq": field("moq", "500 kg", "found", [{"page": 2, "quote": "MOQ 500 kg (시연용)"}], virtual=True),
        "sample": field("sample", "1 kg", "found", [{"page": 2, "quote": "샘플 1 kg"}], virtual=True),
        "lead_time": field("lead_time", "30일", "found", [{"page": 2, "quote": "납기 30일"}], virtual=True),
    }
    base.update(overrides)
    return {"fields": list(base.values()), "multiple_products": False, "review_notes": []}


def response_body(payload=None, text=None, status="completed", reason=None, refusal=None):
    content = []
    if payload is not None or text is not None:
        content.append({"type": "output_text", "text": text if text is not None else json.dumps(payload, ensure_ascii=False),
                        "annotations": []})
    if refusal:
        content.append({"type": "refusal", "refusal": refusal})
    body = {"id": "resp_t", "object": "response", "created_at": 0, "status": status, "model": "test-model-snap",
            "output": [{"type": "message", "id": "m", "status": "completed", "role": "assistant", "content": content}],
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}
    if reason:
        body["incomplete_details"] = {"reason": reason}
    return body


class Base(unittest.TestCase):
    def setUp(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("OPENAI_")}
        env.update({"OPENAI_API_KEY": FAKE_KEY, "OPENAI_MODEL": "test-model"})
        p = mock.patch.dict(os.environ, env, clear=True)
        p.start()
        self.addCleanup(p.stop)
        self.requests = []
        self.responder = lambda r: httpx2.Response(200, json=response_body(full_extraction()))
        p2 = mock.patch.object(ai_client, "_create_client", self.factory)
        p2.start()
        self.addCleanup(p2.stop)
        self.client = create_app().test_client()
        self.logs = io.StringIO()
        handler = logging.StreamHandler(self.logs)
        root = logging.getLogger()
        old = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        self.addCleanup(root.removeHandler, handler)
        self.addCleanup(root.setLevel, old)

    def factory(self, api_key, timeout, max_retries):
        def handler(request):
            self.requests.append(json.loads(request.content))
            return self.responder(request)
        return OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries,
                      http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))

    def post(self, files=None, data=None, **kw):
        form = dict(data or {})
        for name, items in (files or {}).items():
            form[name] = [(io.BytesIO(content), filename) for content, filename in items]
        return self.client.post(URL, data=form, content_type="multipart/form-data", **kw)

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status, response.get_data(as_text=True))
        body = response.get_json()
        self.assertEqual(body["ok"], False)
        self.assertEqual(body["error"]["code"], code)
        self.assertEqual(set(body["error"]), {"code", "message"})
        self.assert_no_leak(response.get_data(as_text=True))
        return body

    def assert_no_leak(self, text=""):
        visible = text + self.logs.getvalue()
        for secret in (FAKE_KEY, SECRET_DOC, SECRET_PROVIDER, "SECRETNAME", "비밀폴더"):
            self.assertNotIn(secret, visible)


class AnalyzeSuccessTests(Base):
    def test_success_eight_fields_through_common_function(self):
        pdf = make_pdf(pages=3)
        response = self.post({"source_file": [(pdf, SECRET_FILENAME)]})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertIs(body["ok"], True)
        data = body["data"]
        self.assertEqual(data["extraction_status"], "unconfirmed")
        self.assertEqual(data["prompt_version"], "brochure_extract_v1")
        self.assertEqual(data["source"], {"size_bytes": len(pdf), "page_count": 3})
        self.assertEqual(data["model"], "test-model-snap")
        self.assertEqual([f["key"] for f in data["fields"]], list(service.FIELD_KEYS))
        for f in data["fields"]:
            self.assertIs(f["confirmed"], False)
            for ev in f["evidence"]:
                self.assertEqual(ev["check"], "not_checked")
        moq = data["fields"][5]
        self.assertEqual((moq["value"], moq["status"], moq["marked_virtual"]), ("500 kg", "found", True))
        self.assertEqual(data["fields"][2]["status"], "not_found")
        self.assertIs(data["multiple_products"], False)

        # 공통 함수 경유: 요청 1회, 지시문=프롬프트 v1, 고정 파일명, 원본 파일명 미전송
        self.assertEqual(len(self.requests), 1)
        sent = self.requests[0]
        self.assertEqual(sent["instructions"], service.load_instructions())
        part = sent["input"][0]["content"][0]
        self.assertEqual(part["filename"], "document.pdf")
        self.assertEqual(part["detail"], "high")
        self.assertIs(sent["store"], False)
        self.assertNotIn("SECRETNAME", json.dumps(sent, ensure_ascii=False))
        self.assertNotIn("SECRETNAME", response.get_data(as_text=True))
        self.assert_no_leak()

    def test_exact_size_limit_accepted(self):
        pdf = make_pdf_of_size(config.PDF_MAX_BYTES)
        response = self.post({"source_file": [(pdf, "a.pdf")]})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["data"]["source"]["size_bytes"], 10 * MiB)

    def test_large_upload_spools_to_temp_file_and_is_closed(self):
        # Werkzeug 기본 stream factory는 500 KB를 넘는 파일 부분을 임시 파일로 넘깁니다(실제 확인).
        seen = {}
        original = routes._read_upload

        def spy():
            upload = routes.request.files["source_file"]
            seen["stream"] = upload.stream
            seen["rolled"] = getattr(upload.stream, "_rolled", None)
            return original()

        with mock.patch.object(routes, "_read_upload", spy):
            response = self.post({"source_file": [(make_pdf(pad=700 * 1024), "a.pdf")]})
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(seen["stream"], tempfile.SpooledTemporaryFile)
        self.assertIs(seen["rolled"], True)        # 디스크 임시 파일로 넘어감
        self.assertTrue(seen["stream"].closed)     # 요청 종료 시 닫힘(정리)


class UploadValidationTests(Base):
    def setUp(self):
        super().setUp()
        self.responder = lambda r: (_ for _ in ()).throw(AssertionError("외부 요청 금지"))

    def tearDown(self):
        self.assertEqual(self.requests, [])  # 입력 검사 실패 시 외부 호출 0회

    def test_missing_file(self):
        self.assert_error(self.post(data={"other": "x"}), 400, "UPLOAD_FILE_MISSING")
        self.assert_error(self.client.post(URL), 400, "UPLOAD_FILE_MISSING")

    def test_empty_filename(self):
        self.assert_error(self.post({"source_file": [(b"", "")]}), 400, "UPLOAD_FILENAME_MISSING")

    def test_duplicate_files(self):
        pdf = make_pdf()
        self.assert_error(self.post({"source_file": [(pdf, "a.pdf"), (pdf, "b.pdf")]}), 400, "UPLOAD_MULTIPLE_FILES")

    def test_unexpected_file_field(self):
        pdf = make_pdf()
        self.assert_error(self.post({"source_file": [(pdf, "a.pdf")], "image": [(pdf, "x.png")]}),
                          400, "UPLOAD_UNEXPECTED_FIELD")

    def test_empty_file(self):
        self.assert_error(self.post({"source_file": [(b"", "a.pdf")]}), 400, "PDF_EMPTY")

    def test_file_over_limit_within_request_limit(self):
        # 파일 자체 10 MiB + 1 byte: 요청 전체 상한 안이지만 파일 상한 초과
        over = make_pdf_of_size(config.PDF_MAX_BYTES + 1)
        self.assert_error(self.post({"source_file": [(over, "a.pdf")]}), 413, "PDF_TOO_LARGE")

    def test_file_read_is_capped(self):
        # 파일 스트림은 상한+1바이트까지만 읽고(전체 읽기 -1 없음) 분석 서비스는 호출하지 않음
        reads = []
        original = tempfile.SpooledTemporaryFile.read

        def tracking_read(self_, *args):
            reads.append(args[0] if args else -1)
            return original(self_, *args)

        with mock.patch.object(routes.service, "analyze_pdf", side_effect=AssertionError("호출 금지")):
            with mock.patch.object(tempfile.SpooledTemporaryFile, "read", tracking_read):
                over = make_pdf_of_size(config.PDF_MAX_BYTES + 1000)
                self.assert_error(self.post({"source_file": [(over, "a.pdf")]}), 413, "PDF_TOO_LARGE")
        self.assertIn(config.PDF_MAX_BYTES + 1, reads)
        self.assertNotIn(-1, reads)

    def test_request_over_total_limit(self):
        big = b"%PDF-" + b"0" * (routes.MAX_REQUEST_BYTES + 10)
        self.assert_error(self.post({"source_file": [(big, "a.pdf")]}), 413, "UPLOAD_TOO_LARGE")

    def test_too_many_parts(self):
        data = {f"t{i}": "x" for i in range(routes.MAX_FORM_PARTS + 2)}
        self.assert_error(self.post({"source_file": [(make_pdf(), "a.pdf")]}, data=data), 413, "UPLOAD_TOO_LARGE")

    def test_invalid_pdfs(self):
        cases = [
            (b"\x89PNG\r\n\x1a\n" + SECRET_DOC.encode(), "a.pdf", 400, "PDF_NOT_PDF"),   # 위장 확장자
            (b"%PDF-1.7\n" + SECRET_DOC.encode() * 20, "a.pdf", 400, "PDF_CORRUPT"),
            (make_pdf(encrypt="RC4-128"), "a.pdf", 400, "PDF_ENCRYPTED"),
            (make_pdf(pages=0), "a.pdf", 400, "PDF_NO_PAGES"),
            (make_pdf(pages=21), "a.pdf", 400, "PDF_TOO_MANY_PAGES"),
        ]
        for content, name, status, code in cases:
            with self.subTest(code=code):
                self.assert_error(self.post({"source_file": [(content, name)]}), status, code)

    def test_valid_pdf_with_wrong_extension_still_checked_by_content(self):
        # 확장자·MIME이 아니라 내용으로 판단: .txt 이름이어도 PDF 검사는 내용 기준(여기서는 손상)
        self.assert_error(self.post({"source_file": [(b"%PDF-1.7 broken", "a.txt")]}), 400, "PDF_CORRUPT")

    def test_pdf_checked_before_settings(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            self.assert_error(self.post({"source_file": [(b"", "a.pdf")]}), 400, "PDF_EMPTY")
            self.assert_error(self.post({"source_file": [(make_pdf(), "a.pdf")]}), 503, "AI_CONFIG_MISSING")


class AIErrorTests(Base):
    def run_case(self, responder, status, code):
        self.responder = responder
        response = self.post({"source_file": [(make_pdf(), SECRET_FILENAME)]})
        self.assert_error(response, status, code)
        self.assertEqual(len(self.requests), 1)  # 기능에서 추가 재시도 없음
        self.requests.clear()

    def test_provider_errors(self):
        def err(status, code=None):
            return lambda r: httpx2.Response(status, json={"error": {"message": SECRET_PROVIDER, "code": code}})

        def timeout(request):
            raise httpx2.ReadTimeout(SECRET_PROVIDER, request=request)

        for responder, status, code in [
            (err(401), 502, "AI_AUTH_FAILED"),
            (err(429, "rate_limit_exceeded"), 429, "AI_RATE_LIMITED"),
            (err(500), 502, "AI_PROVIDER_ERROR"),
            (timeout, 504, "AI_TIMEOUT"),
        ]:
            with self.subTest(code=code):
                self.run_case(responder, status, code)

    def test_output_errors(self):
        for body, status, code in [
            (response_body(refusal="거절 " + SECRET_PROVIDER), 422, "AI_REFUSED"),
            (response_body(status="incomplete", reason="max_output_tokens"), 502, "AI_INCOMPLETE"),
            (response_body(text="not json " + SECRET_PROVIDER), 502, "AI_OUTPUT_INVALID"),
            (response_body(text='{"fields": [{"key": "unknown_key"}]}'), 502, "AI_OUTPUT_INVALID"),
        ]:
            with self.subTest(code=code):
                self.run_case(lambda r, b=body: httpx2.Response(200, json=b), status, code)

    def test_unexpected_exception_is_json(self):
        with mock.patch.object(routes.service, "analyze_pdf", side_effect=RuntimeError(SECRET_DOC)):
            self.assert_error(self.post({"source_file": [(make_pdf(), "a.pdf")]}), 500, "AI_UNKNOWN_ERROR")


class NormalizeTests(unittest.TestCase):
    def norm(self, page_count=3, multiple=False, notes=(), **overrides):
        payload = full_extraction(**overrides)
        payload["multiple_products"] = multiple
        payload["review_notes"] = list(notes)
        return service.normalize_extraction(service.BrochureExtraction.model_validate(payload), page_count)

    def get(self, result, key):
        return next(f for f in result["fields"] if f["key"] == key)

    def test_found_without_valid_evidence_is_downgraded(self):
        result = self.norm(moq=field("moq", "500 kg", "found", []),
                           sample=field("sample", "1 kg", "found", [{"page": 1, "quote": "   "}]))
        for key in ("moq", "sample"):
            f = self.get(result, key)
            self.assertEqual((f["status"], f["ai_status"]), ("unclear", "found"))
            self.assertTrue(f["server_notes"])

    def test_found_with_empty_value_is_downgraded(self):
        f = self.get(self.norm(moq=field("moq", "  ", "found", [{"page": 1, "quote": "MOQ"}])), "moq")
        self.assertEqual((f["value"], f["status"]), (None, "unclear"))

    def test_page_out_of_range(self):
        result = self.norm(page_count=3, moq=field("moq", "500 kg", "found", [{"page": 9, "quote": "MOQ 500"}]),
                           sample=field("sample", "1 kg", "found", [{"page": 0, "quote": "샘플"}, {"page": 2, "quote": "샘플 1 kg"}]))
        moq = self.get(result, "moq")
        self.assertEqual(moq["status"], "unclear")
        self.assertIs(moq["evidence"][0]["page_in_range"], False)
        sample = self.get(result, "sample")
        self.assertEqual(sample["status"], "found")  # 유효한 근거가 하나 남아 있음
        self.assertTrue(any("페이지" in n for n in sample["server_notes"]))
        self.assertTrue(any("MOQ" in n["message"] and "페이지" in n["message"] for n in result["review_notes"]))

    def test_page_none_is_not_valid_evidence(self):
        f = self.get(self.norm(moq=field("moq", "500 kg", "found", [{"page": None, "quote": "MOQ"}])), "moq")
        self.assertEqual(f["status"], "unclear")

    def test_not_found_with_value_is_contradiction(self):
        f = self.get(self.norm(certification=field("certification", "GRS", "not_found")), "certification")
        self.assertEqual((f["value"], f["status"], f["ai_status"]), ("GRS", "unclear", "not_found"))

    def test_missing_keys(self):
        payload = full_extraction()
        payload["fields"] = [f for f in payload["fields"] if f["key"] not in ("yarn_spec", "lead_time")]
        result = service.normalize_extraction(service.BrochureExtraction.model_validate(payload), 3)
        self.assertEqual([f["key"] for f in result["fields"]], list(service.FIELD_KEYS))
        for key in ("yarn_spec", "lead_time"):
            f = self.get(result, key)
            self.assertEqual((f["status"], f["value"], f["ai_status"]), ("unclear", None, None))

    def test_duplicate_keys_keep_candidates(self):
        payload = full_extraction()
        payload["fields"].append(field("moq", "1000 kg", "found", [{"page": 3, "quote": "MOQ 1000 kg"}]))
        result = service.normalize_extraction(service.BrochureExtraction.model_validate(payload), 3)
        self.assertEqual(len(result["fields"]), 8)
        moq = self.get(result, "moq")
        self.assertEqual(moq["status"], "unclear")
        self.assertEqual(moq["candidates"], ["500 kg", "1000 kg"])
        self.assertEqual(len(moq["evidence"]), 2)

    def test_unknown_key_rejected_by_schema(self):
        payload = full_extraction()
        payload["fields"].append(field("price", "1 USD", "found"))
        with self.assertRaises(Exception):
            service.BrochureExtraction.model_validate(payload)

    def test_virtual_flag_preserved(self):
        result = self.norm(moq=field("moq", "500 kg", "found", [], virtual=True),
                           yarn_spec=field("yarn_spec", None, "not_found", [], virtual=True))
        self.assertIs(self.get(result, "moq")["marked_virtual"], True)   # 강등돼도 가상 표시 유지
        self.assertIs(self.get(result, "yarn_spec")["marked_virtual"], True)  # 미제공+가상 동시

    def test_multiple_products_note(self):
        result = self.norm(multiple=True, notes=["두 제품 등급이 함께 있음"])
        self.assertIs(result["multiple_products"], True)
        sources = [(n["source"], n["message"]) for n in result["review_notes"]]
        self.assertTrue(any(s == "server" and "복수 제품" in m for s, m in sources))
        self.assertIn(("ai", "두 제품 등급이 함께 있음"), sources)

    def test_long_quote_truncated(self):
        f = self.get(self.norm(moq=field("moq", "500 kg", "found", [{"page": 1, "quote": "가" * 1000}])), "moq")
        self.assertEqual(len(f["evidence"][0]["quote"]), service.MAX_QUOTE_CHARS)

    def test_no_field_marked_confirmed(self):
        for f in self.norm()["fields"]:
            self.assertIs(f["confirmed"], False)


class PromptAndScopeTests(unittest.TestCase):
    def test_prompt_file_rules(self):
        text = service.load_instructions()
        for key in service.FIELD_KEYS:
            self.assertIn(key, text)
        for phrase in ("지시·요청·명령", "외부 지식", "not_found", "unclear", "marked_virtual",
                       "합치지 않습니다", "번역"):
            self.assertIn(phrase, text)

    def test_field_keys_match_screen(self):
        js = (ROOT / "features/product_brochure/static/product_brochure.js").read_text(encoding="utf-8")
        for key in service.FIELD_KEYS:
            self.assertIn(f'key: "{key}"', js)

    def test_other_routes_unaffected(self):
        client = create_app().test_client()
        self.assertEqual(client.get("/").status_code, 200)
        self.assertIsNone(create_app().config["MAX_CONTENT_LENGTH"])  # 앱 전역 제한 변경 없음
        self.assertEqual(client.get(URL).status_code, 405)


if __name__ == "__main__":
    unittest.main()
