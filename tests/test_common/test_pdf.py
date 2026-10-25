"""common.pdf_utils.inspect_pdf 와 common.ai_client.generate_structured_from_pdf 모의 테스트.

실제 OpenAI 요청을 보내지 않습니다(test_ai_client의 MockTransport 도구 재사용).
테스트 PDF는 pypdf로 코드에서 만든 가상 자료입니다. 스캔 PDF 판독은 검증하지 않습니다.
실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_common -v
"""
import base64
import io
import json
import logging
import sys
import unittest
from pathlib import Path
from unittest import mock

import httpx2
import pypdf
from pypdf import PdfWriter

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ai_client, config, errors, pdf_utils  # noqa: E402
from test_ai_client import (  # noqa: E402
    FAKE_KEY, SECRET_INPUT, SECRET_PROVIDER, TEXT_MODEL,
    AIClientTestBase, Extracted, error_body, text_response,
)

SECRET_DOC = "SECRET-PDF-BODY-5521"
MiB = 1024 * 1024


def make_pdf(pages=1, encrypt=None, pad=0):
    """빈 페이지 PDF. pad: 메타데이터 문자열 길이(파일 크기 조절용)."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    metadata = {"/Title": SECRET_DOC}
    if pad:
        metadata["/Pad"] = "a" * pad
    writer.add_metadata(metadata)
    if encrypt:
        writer.encrypt(user_password="", owner_password="owner", algorithm=encrypt)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_pdf_of_size(size):
    """정확히 size bytes인 유효 PDF."""
    pad = 100
    for _ in range(5):
        data = make_pdf(pad=pad)
        if len(data) == size:
            return data
        pad += size - len(data)
    raise AssertionError("크기 맞춤 실패")


class InspectPdfTests(unittest.TestCase):
    def setUp(self):
        self.logs = io.StringIO()
        handler = logging.StreamHandler(self.logs)
        root = logging.getLogger()
        old = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        self.addCleanup(root.removeHandler, handler)
        self.addCleanup(root.setLevel, old)

    def assert_rejects(self, data, exc_type, code, **kw):
        with self.assertRaises(exc_type) as ctx:
            pdf_utils.inspect_pdf(data, **kw)
        err = ctx.exception
        self.assertEqual(err.code, code)
        self.assertIsNone(err.__cause__)
        self.assertTrue(err.__suppress_context__ or err.__context__ is None)
        self.assertNotIn(SECRET_DOC, str(err) + err.message + self.logs.getvalue())
        return err

    def test_valid_pdf(self):
        data = make_pdf(pages=3)
        info = pdf_utils.inspect_pdf(data)
        self.assertEqual(info, pdf_utils.PdfInfo(size_bytes=len(data), page_count=3))

    def test_not_bytes(self):
        for value in (None, "PDF", bytearray(make_pdf()), memoryview(make_pdf())):
            with self.subTest(type=type(value).__name__):
                self.assert_rejects(value, errors.AIInputError, "AI_INVALID_INPUT")

    def test_empty(self):
        self.assert_rejects(b"", errors.PdfEmptyError, "PDF_EMPTY")

    def test_size_boundary(self):
        exact = make_pdf_of_size(10 * MiB)
        self.assertEqual(len(exact), config.PDF_MAX_BYTES)
        self.assertEqual(pdf_utils.inspect_pdf(exact).size_bytes, 10 * MiB)
        over = make_pdf_of_size(10 * MiB + 1)
        err = self.assert_rejects(over, errors.PdfTooLargeError, "PDF_TOO_LARGE")
        self.assertEqual(err.http_status, 413)

    def test_size_checked_before_parse(self):
        with mock.patch.object(pdf_utils, "_NoDecryptReader", side_effect=AssertionError("파싱하면 안 됨")):
            self.assert_rejects(b"%PDF-" + b"0" * 20, errors.PdfTooLargeError, "PDF_TOO_LARGE", max_bytes=10)

    def test_page_boundary(self):
        self.assertEqual(pdf_utils.inspect_pdf(make_pdf(pages=20)).page_count, 20)
        self.assert_rejects(make_pdf(pages=21), errors.PdfTooManyPagesError, "PDF_TOO_MANY_PAGES")

    def test_zero_pages(self):
        self.assert_rejects(make_pdf(pages=0), errors.PdfNoPagesError, "PDF_NO_PAGES")

    def test_disguised_files(self):
        png = b"\x89PNG\r\n\x1a\n" + SECRET_DOC.encode() * 10
        self.assert_rejects(png, errors.PdfNotPdfError, "PDF_NOT_PDF")
        late_sig = b"x" * 2000 + make_pdf()
        self.assert_rejects(late_sig, errors.PdfNotPdfError, "PDF_NOT_PDF")

    def test_signature_only_is_not_valid(self):
        self.assert_rejects(b"%PDF-1.7\n" + (SECRET_DOC + " ") .encode() * 50, errors.PdfCorruptError, "PDF_CORRUPT")

    def test_truncated(self):
        data = make_pdf(pages=2)
        self.assert_rejects(data[: len(data) // 2], errors.PdfCorruptError, "PDF_CORRUPT")

    def test_encrypted_rejected_without_decrypt_attempt(self):
        # AES 암호화 PDF는 cryptography 패키지 없이 만들 수 없어 RC4만 사용(AES 검출은 미검증)
        for algorithm in ("RC4-40", "RC4-128"):
            with self.subTest(algorithm=algorithm):
                data = make_pdf(encrypt=algorithm)
                with mock.patch.object(pypdf._encryption.Encryption, "read", side_effect=AssertionError("해제 준비 금지")), \
                        mock.patch.object(pypdf._encryption.Encryption, "verify", side_effect=AssertionError("해제 시도 금지")):
                    self.assert_rejects(data, errors.PdfEncryptedError, "PDF_ENCRYPTED")

    def test_plain_reader_would_attempt_decrypt_control(self):
        # 대조: 일반 PdfReader는 빈 비밀번호로 해제를 시도함(전용 리더가 필요한 이유, pypdf 버전 변경 감지용)
        data = make_pdf(encrypt="RC4-128")
        with mock.patch.object(pypdf._encryption.Encryption, "verify", side_effect=AssertionError("attempted")):
            with self.assertRaises(AssertionError):
                pypdf.PdfReader(io.BytesIO(data))

    def test_pypdf_log_does_not_leak_content(self):
        # 서명이 앞 1024바이트 안에 있지만 0번 위치가 아니면 pypdf 6.21.2는
        # "invalid pdf header: b'<앞 5바이트>'" 경고를 남깁니다(차단하지 않으면 문서 앞부분이 로그에 들어감).
        data = b"QZXJK" + make_pdf()
        info = pdf_utils.inspect_pdf(data)
        self.assertEqual(info.page_count, 1)
        logs = self.logs.getvalue()
        self.assertNotIn("QZXJK", logs)
        self.assertNotIn("invalid pdf header", logs)
        self.assertNotIn("startxref", logs)

    def test_pypdf_log_leak_control(self):
        # 대조: 차단을 끄면 같은 입력에서 앞 5바이트가 로그에 나타나는지(테스트가 실제로 누출을 잡는지 확인)
        logger = logging.getLogger("pypdf")
        logger.propagate = True
        self.addCleanup(setattr, logger, "propagate", False)
        pdf_utils.inspect_pdf(b"QZXJK" + make_pdf())
        self.assertIn("QZXJK", self.logs.getvalue())

    def test_invalid_limits(self):
        for kw in ({"max_bytes": 0}, {"max_pages": -1}, {"max_pages": True}, {"max_bytes": "10"}):
            with self.subTest(kw=kw):
                self.assert_rejects(make_pdf(), errors.AIInputError, "AI_INVALID_INPUT", **kw)


class PdfStructuredTests(AIClientTestBase):
    def ok_responder(self, request):
        return httpx2.Response(200, json=text_response('{"product_name":"가상","unverified":["MOQ"]}'))

    def call(self, **kw):
        args = {"instructions": "지시문", "pdf_bytes": self.pdf, "schema": Extracted}
        args.update(kw)
        return ai_client.generate_structured_from_pdf(**args)

    def setUp(self):
        super().setUp()
        self.pdf = make_pdf(pages=2)

    def test_success_and_request_shape(self):
        fake = self.use(self.ok_responder)
        result = self.call(input_text="부가 " + SECRET_INPUT)
        self.assertIsInstance(result, ai_client.PdfStructuredResult)
        self.assertIsInstance(result, ai_client.StructuredResult)
        self.assertEqual(result.data.product_name, "가상")
        self.assertEqual(result.pdf, pdf_utils.PdfInfo(size_bytes=len(self.pdf), page_count=2))
        self.assertEqual(result.usage, ai_client.TokenUsage(11, 7, 18))

        self.assertEqual(fake.client_args, [{"api_key": FAKE_KEY, "timeout": 120.0, "max_retries": 0}])
        self.assertEqual(len(fake.requests), 1)
        req = fake.requests[0]
        self.assertTrue(req["path"].endswith("/responses"))
        body = req["json"]
        self.assertEqual(body["model"], TEXT_MODEL)
        self.assertEqual(body["instructions"], "지시문")
        self.assertIs(body["store"], False)
        self.assertEqual(body["max_output_tokens"], 4096)
        self.assertEqual(body["text"]["format"]["type"], "json_schema")
        self.assertIs(body["text"]["format"]["strict"], True)
        for unsupported in ("temperature", "top_p", "reasoning", "stream", "tools"):
            self.assertNotIn(unsupported, body)

        self.assertEqual(len(body["input"]), 1)
        message = body["input"][0]
        self.assertEqual(message["role"], "user")
        file_part, text_part = message["content"]
        self.assertEqual(file_part["type"], "input_file")
        self.assertEqual(file_part["filename"], "document.pdf")
        self.assertEqual(file_part["detail"], "high")
        self.assertNotIn("file_id", file_part)
        self.assertNotIn("file_url", file_part)
        prefix = "data:application/pdf;base64,"
        self.assertTrue(file_part["file_data"].startswith(prefix))
        self.assertEqual(base64.b64decode(file_part["file_data"][len(prefix):]), self.pdf)
        self.assertEqual(text_part, {"type": "input_text", "text": "부가 " + SECRET_INPUT})
        # 업무 지시는 instructions에만, PDF·부가 텍스트는 입력 데이터에만
        self.assertNotIn("지시문", json.dumps(body["input"], ensure_ascii=False))

    def test_without_input_text(self):
        fake = self.use(self.ok_responder)
        self.call()
        content = fake.requests[0]["json"]["input"][0]["content"]
        self.assertEqual([part["type"] for part in content], ["input_file"])

    def test_max_output_tokens_override(self):
        fake = self.use(self.ok_responder)
        self.call(max_output_tokens=1000)
        self.assertEqual(fake.requests[0]["json"]["max_output_tokens"], 1000)

    def test_pdf_failures_make_no_request(self):
        # 기본 setUp은 클라이언트 생성 자체를 금지(forbid_client)합니다.
        cases = {
            "empty": (b"", errors.PdfEmptyError),
            "too_large": (make_pdf_of_size(10 * MiB + 1), errors.PdfTooLargeError),
            "disguised": (b"\x89PNG\r\n\x1a\n" + b"0" * 64, errors.PdfNotPdfError),
            "corrupt": (self.pdf[: len(self.pdf) // 2], errors.PdfCorruptError),
            "encrypted": (make_pdf(encrypt="RC4-128"), errors.PdfEncryptedError),
            "zero_pages": (make_pdf(pages=0), errors.PdfNoPagesError),
            "too_many_pages": (make_pdf(pages=21), errors.PdfTooManyPagesError),
            "not_bytes": ("문자열", errors.AIInputError),
        }
        for name, (data, exc_type) in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(exc_type) as ctx:
                    self.call(pdf_bytes=data)
                self.assertIsInstance(ctx.exception, errors.AIError)
                self.assert_safe(ctx.exception)
                self.assertNotIn(SECRET_DOC, self.log_stream.getvalue())

    def test_invalid_args_make_no_request(self):
        for kw in ({"instructions": ""}, {"schema": dict}, {"input_text": ""}, {"input_text": 5},
                   {"max_output_tokens": 0}):
            with self.subTest(kw=kw):
                with self.assertRaises(errors.AIInputError):
                    self.call(**kw)

    def test_missing_settings_no_request(self):
        with mock.patch.dict("os.environ", {"OPENAI_MODEL": ""}):
            with self.assertRaises(errors.AIConfigError):
                self.call()

    def test_refusal_incomplete_invalid_output(self):
        cases = [
            (text_response(refusal="거절 " + SECRET_PROVIDER), errors.AIRefusalError),
            (text_response(status="incomplete", reason="max_output_tokens"), errors.AIIncompleteError),
            (text_response(status="incomplete", reason="content_filter"), errors.AIRefusalError),
            (text_response('{"product_name": 1}'), errors.AIOutputInvalidError),
            (text_response("not json " + SECRET_PROVIDER), errors.AIOutputInvalidError),
            (text_response(status="failed"), errors.AIProviderError),
        ]
        for body, exc_type in cases:
            with self.subTest(exc=exc_type.__name__):
                self.use(lambda r, b=body: httpx2.Response(200, json=b))
                with self.assertRaises(exc_type) as ctx:
                    self.call(input_text=SECRET_INPUT)
                self.assert_safe(ctx.exception)

    def test_provider_errors_single_attempt(self):
        def timeout(request):
            raise httpx2.ReadTimeout(SECRET_PROVIDER, request=request)

        cases = [
            (lambda r: httpx2.Response(401, json=error_body()), errors.AIAuthError),
            (lambda r: httpx2.Response(429, json=error_body("rate_limit_exceeded")), errors.AIRateLimitError),
            (lambda r: httpx2.Response(400, json=error_body("invalid_value")), errors.AIBadRequestError),
            (lambda r: httpx2.Response(500, json=error_body()), errors.AIProviderError),
            (timeout, errors.AITimeoutError),
        ]
        for responder, exc_type in cases:
            with self.subTest(exc=exc_type.__name__):
                fake = self.use(responder)
                with self.assertRaises(exc_type) as ctx:
                    self.call(input_text=SECRET_INPUT)
                self.assertEqual(len(fake.requests), 1)  # 재시도·모델/detail 변경 재호출 없음
                self.assert_safe(ctx.exception)
                self.assertNotIn(SECRET_DOC, self.log_stream.getvalue())

    def test_existing_text_call_unchanged(self):
        fake = self.use(self.ok_responder)
        ai_client.generate_structured(instructions="i", input_text="t", schema=Extracted)
        self.assertEqual(fake.requests[0]["json"]["input"], "t")
        self.assertEqual(fake.client_args[0]["timeout"], 60.0)


if __name__ == "__main__":
    unittest.main()
