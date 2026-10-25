"""common.ai_client 모의 테스트. 실제 OpenAI 요청을 보내지 않습니다.

실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_common -v

모든 테스트는 ai_client._create_client를 httpx2.MockTransport 클라이언트로 교체합니다.
키·모델 값은 테스트용 가짜 문자열이며 실제 .env를 읽지 않습니다.
"""
import base64
import io
import json
import logging
import os
import struct
import sys
import unittest
import zlib
from pathlib import Path
from unittest import mock

import httpx2
import pydantic
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common import ai_client, config  # noqa: E402
from common import errors  # noqa: E402

FAKE_KEY = "sk-test-FAKE-KEY-DO-NOT-USE-0000"
SECRET_INPUT = "SECRET-USER-INPUT-7781"
SECRET_PROVIDER = "PROVIDER-RAW-MESSAGE-4410"
TEXT_MODEL = "test-text-model"
IMAGE_MODEL = "test-image-model"


def make_png(width, height):
    """코드로 만든 회색조 가상 PNG(모든 픽셀 0)."""
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x00" * width for _ in range(height))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class Extracted(pydantic.BaseModel):
    product_name: str
    unverified: list[str]


def text_response(text=None, status="completed", reason=None, refusal=None, model="test-text-model-2026"):
    content = []
    if text is not None:
        content.append({"type": "output_text", "text": text, "annotations": []})
    if refusal is not None:
        content.append({"type": "refusal", "refusal": refusal})
    body = {
        "id": "resp_test", "object": "response", "created_at": 0, "status": status, "model": model,
        "output": [{"type": "message", "id": "msg_test", "status": "completed", "role": "assistant", "content": content}],
        "usage": {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
    }
    if reason:
        body["incomplete_details"] = {"reason": reason}
    return body


def error_body(code=None):
    return {"error": {"message": SECRET_PROVIDER + " " + SECRET_INPUT, "type": "error", "code": code}}


class MockOpenAI:
    """요청을 기록하고 지정한 응답을 돌려주는 가짜 전송."""

    def __init__(self, responder):
        self.responder = responder
        self.requests = []
        self.client_args = []

    def factory(self, api_key, timeout, max_retries):
        self.client_args.append({"api_key": api_key, "timeout": timeout, "max_retries": max_retries})

        def handler(request):
            self.requests.append({"path": request.url.path, "json": json.loads(request.content or b"{}")})
            return self.responder(request)

        return OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries,
                      http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))


def forbid_client(*args, **kwargs):
    raise AssertionError("API 클라이언트가 생성되면 안 됩니다")


class AIClientTestBase(unittest.TestCase):
    env = {"OPENAI_API_KEY": FAKE_KEY, "OPENAI_MODEL": TEXT_MODEL, "OPENAI_IMAGE_MODEL": IMAGE_MODEL}

    def setUp(self):
        clean = {k: v for k, v in os.environ.items() if not k.startswith("OPENAI_")}
        clean.update(self.env)
        patcher = mock.patch.dict(os.environ, clean, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        # 기본은 클라이언트 생성 금지. 각 테스트가 필요할 때만 MockOpenAI로 교체.
        factory_patch = mock.patch.object(ai_client, "_create_client", forbid_client)
        factory_patch.start()
        self.addCleanup(factory_patch.stop)
        # 모든 로거 출력을 수집해 비밀값 노출을 검사
        self.log_stream = io.StringIO()
        handler = logging.StreamHandler(self.log_stream)
        handler.setLevel(logging.DEBUG)
        root = logging.getLogger()
        old_level = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        self.addCleanup(root.removeHandler, handler)
        self.addCleanup(root.setLevel, old_level)

    def use(self, responder):
        fake = MockOpenAI(responder)
        p = mock.patch.object(ai_client, "_create_client", fake.factory)
        p.start()
        self.addCleanup(p.stop)
        return fake

    def assert_safe(self, err):
        """오류 메시지·로그에 키·입력·공급자 원문이 없는지 확인."""
        visible = " ".join([str(err), err.message, json.dumps(err.to_dict(), ensure_ascii=False),
                            repr(err.__cause__), repr(err.__context__) if err.__suppress_context__ is False else "",
                            self.log_stream.getvalue()])
        for secret in (FAKE_KEY, SECRET_INPUT, SECRET_PROVIDER):
            self.assertNotIn(secret, visible)
        self.assertIsNone(err.__cause__)
        self.assertTrue(err.__suppress_context__ or err.__context__ is None)


class TextTests(AIClientTestBase):
    def call(self, **kw):
        args = {"instructions": "지시문", "input_text": SECRET_INPUT, "schema": Extracted}
        args.update(kw)
        return ai_client.generate_structured(**args)

    def test_success_returns_validated_model_and_metadata(self):
        fake = self.use(lambda r: httpx2.Response(200, json=text_response(
            json.dumps({"product_name": "가상 제품", "unverified": ["MOQ"]}, ensure_ascii=False))))
        result = self.call()
        self.assertIsInstance(result.data, Extracted)
        self.assertEqual(result.data.product_name, "가상 제품")
        self.assertEqual(result.model, "test-text-model-2026")
        self.assertEqual(result.usage, ai_client.TokenUsage(11, 7, 18))
        self.assertEqual(len(fake.requests), 1)

    def test_request_options(self):
        fake = self.use(lambda r: httpx2.Response(200, json=text_response('{"product_name":"a","unverified":[]}')))
        self.call()
        self.assertEqual(fake.client_args, [{"api_key": FAKE_KEY, "timeout": 60.0, "max_retries": 0}])
        req = fake.requests[0]
        self.assertTrue(req["path"].endswith("/responses"))
        body = req["json"]
        self.assertEqual(body["model"], TEXT_MODEL)
        self.assertEqual(body["instructions"], "지시문")
        self.assertEqual(body["input"], SECRET_INPUT)
        self.assertEqual(body["max_output_tokens"], 4096)
        self.assertIs(body["store"], False)
        self.assertEqual(body["text"]["format"]["type"], "json_schema")
        self.assertIs(body["text"]["format"]["strict"], True)
        for unsupported in ("temperature", "top_p", "reasoning", "stream"):
            self.assertNotIn(unsupported, body)

    def test_max_output_tokens_override(self):
        fake = self.use(lambda r: httpx2.Response(200, json=text_response('{"product_name":"a","unverified":[]}')))
        self.call(max_output_tokens=1000)
        self.assertEqual(fake.requests[0]["json"]["max_output_tokens"], 1000)

    def test_invalid_input_does_not_call_api(self):
        cases = [
            {"instructions": ""}, {"instructions": None}, {"input_text": "   "}, {"input_text": 3},
            {"schema": dict}, {"schema": Extracted(product_name="a", unverified=[])},
            {"max_output_tokens": 0}, {"max_output_tokens": True}, {"max_output_tokens": "10"},
        ]
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(errors.AIInputError) as ctx:
                    self.call(**case)
                self.assertEqual(ctx.exception.code, "AI_INVALID_INPUT")
                self.assert_safe(ctx.exception)

    def test_refusal(self):
        self.use(lambda r: httpx2.Response(200, json=text_response(refusal="거절 " + SECRET_PROVIDER)))
        with self.assertRaises(errors.AIRefusalError) as ctx:
            self.call()
        self.assertEqual(ctx.exception.code, "AI_REFUSED")
        self.assert_safe(ctx.exception)

    def test_incomplete_max_tokens(self):
        self.use(lambda r: httpx2.Response(200, json=text_response(status="incomplete", reason="max_output_tokens")))
        with self.assertRaises(errors.AIIncompleteError) as ctx:
            self.call()
        self.assert_safe(ctx.exception)

    def test_incomplete_content_filter_is_refusal(self):
        self.use(lambda r: httpx2.Response(200, json=text_response(status="incomplete", reason="content_filter")))
        with self.assertRaises(errors.AIRefusalError):
            self.call()

    def test_incomplete_with_truncated_json(self):
        # 잘린 JSON은 SDK parse 단계의 검증 실패로 나타남 → 출력 형식 오류로 처리
        self.use(lambda r: httpx2.Response(200, json=text_response(
            '{"product_name": "' + SECRET_INPUT, status="incomplete", reason="max_output_tokens")))
        with self.assertRaises(errors.AIOutputInvalidError) as ctx:
            self.call()
        self.assert_safe(ctx.exception)

    def test_failed_status(self):
        self.use(lambda r: httpx2.Response(200, json=text_response(status="failed")))
        with self.assertRaises(errors.AIProviderError):
            self.call()

    def test_schema_mismatch(self):
        self.use(lambda r: httpx2.Response(200, json=text_response('{"product_name": 5, "secret": "' + SECRET_INPUT + '"}')))
        with self.assertRaises(errors.AIOutputInvalidError) as ctx:
            self.call()
        self.assertEqual(ctx.exception.code, "AI_OUTPUT_INVALID")
        self.assert_safe(ctx.exception)

    def test_not_json(self):
        self.use(lambda r: httpx2.Response(200, json=text_response("not json " + SECRET_PROVIDER)))
        with self.assertRaises(errors.AIOutputInvalidError) as ctx:
            self.call()
        self.assert_safe(ctx.exception)

    def test_no_output_text(self):
        self.use(lambda r: httpx2.Response(200, json=text_response()))
        with self.assertRaises(errors.AIOutputInvalidError):
            self.call()


class ImageTests(AIClientTestBase):
    def image_ok(self, width=1024, height=1024):
        png = make_png(width, height)
        return png, lambda r: httpx2.Response(200, json={"created": 0, "data": [{"b64_json": base64.b64encode(png).decode()}]})

    def test_success_returns_bytes_and_mime(self):
        png, responder = self.image_ok()
        fake = self.use(responder)
        image = ai_client.generate_image(prompt=SECRET_INPUT)
        self.assertEqual(image.data, png)
        self.assertEqual(image.mime_type, "image/png")
        self.assertEqual((image.width, image.height), (1024, 1024))
        self.assertEqual(image.model, IMAGE_MODEL)
        self.assertNotIn(png[:16].hex(), repr(image))
        self.assertEqual(len(fake.requests), 1)

    def test_request_options_defaults(self):
        _, responder = self.image_ok()
        fake = self.use(responder)
        ai_client.generate_image(prompt="가상 제품 사진")
        self.assertEqual(fake.client_args, [{"api_key": FAKE_KEY, "timeout": 180.0, "max_retries": 0}])
        req = fake.requests[0]
        self.assertTrue(req["path"].endswith("/images/generations"))
        self.assertEqual(req["json"], {"model": IMAGE_MODEL, "prompt": "가상 제품 사진", "n": 1,
                                       "size": "1024x1024", "quality": "low", "output_format": "png"})

    def test_all_supported_sizes_and_qualities(self):
        for size in config.IMAGE_SIZES:
            for quality in config.IMAGE_QUALITIES:
                with self.subTest(size=size, quality=quality):
                    w, h = (int(v) for v in size.split("x"))
                    _, responder = self.image_ok(w, h)
                    fake = self.use(responder)
                    image = ai_client.generate_image(prompt="p", size=size, quality=quality)
                    self.assertEqual((image.width, image.height), (w, h))
                    self.assertEqual(fake.requests[0]["json"]["size"], size)
                    self.assertEqual(fake.requests[0]["json"]["quality"], quality)

    def test_invalid_input_does_not_call_api(self):
        cases = [{"prompt": ""}, {"prompt": None}, {"prompt": "p", "size": "512x512"}, {"prompt": "p", "size": "auto"},
                 {"prompt": "p", "quality": "auto"}, {"prompt": "p", "quality": "max"}, {"prompt": "p", "quality": "hd"}]
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(errors.AIInputError):
                    ai_client.generate_image(**case)

    def assert_image_error(self, body, exc_type):
        self.use(lambda r: httpx2.Response(200, json=body))
        with self.assertRaises(exc_type) as ctx:
            ai_client.generate_image(prompt=SECRET_INPUT)
        self.assert_safe(ctx.exception)

    def test_empty_results(self):
        for body in ({"created": 0, "data": []}, {"created": 0}, {"created": 0, "data": [{"b64_json": None}]},
                     {"created": 0, "data": [{"b64_json": ""}]}, {"created": 0, "data": [{"url": "https://x.invalid/a.png"}]}):
            with self.subTest(body=body):
                self.assert_image_error(body, errors.AIImageEmptyError)

    def test_invalid_base64(self):
        for b64 in ("@@not-base64@@", "abc", SECRET_PROVIDER):
            with self.subTest(b64=b64):
                self.assert_image_error({"created": 0, "data": [{"b64_json": b64}]}, errors.AIImageDecodeError)

    def test_invalid_image_data(self):
        png = make_png(1024, 1024)
        cases = {
            "not_png": base64.b64encode(b"GIF89a" + b"\x00" * 64).decode(),
            "truncated": base64.b64encode(png[:-6]).decode(),
            "wrong_size": base64.b64encode(make_png(1024, 1536)).decode(),
        }
        for name, b64 in cases.items():
            with self.subTest(case=name):
                self.assert_image_error({"created": 0, "data": [{"b64_json": b64}]}, errors.AIImageInvalidError)

    def test_multiple_images_rejected(self):
        b64 = base64.b64encode(make_png(1024, 1024)).decode()
        self.assert_image_error({"created": 0, "data": [{"b64_json": b64}, {"b64_json": b64}]}, errors.AIImageInvalidError)

    def test_oversized_base64_rejected_before_decode(self):
        with mock.patch.object(ai_client, "_IMAGE_MAX_B64_CHARS", 8), \
                mock.patch.object(ai_client.base64, "b64decode", side_effect=AssertionError("디코딩하면 안 됨")):
            self.assert_image_error({"created": 0, "data": [{"b64_json": "A" * 16}]}, errors.AIImageInvalidError)

    def test_moderation_blocked_is_refusal(self):
        self.use(lambda r: httpx2.Response(400, json=error_body("moderation_blocked")))
        with self.assertRaises(errors.AIRefusalError) as ctx:
            ai_client.generate_image(prompt=SECRET_INPUT)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assert_safe(ctx.exception)


class ProviderErrorTests(AIClientTestBase):
    cases = [
        (401, None, errors.AIAuthError, "AI_AUTH_FAILED"),
        (403, None, errors.AIPermissionError, "AI_PERMISSION_DENIED"),
        (404, "model_not_found", errors.AIModelUnavailableError, "AI_MODEL_UNAVAILABLE"),
        (429, "rate_limit_exceeded", errors.AIRateLimitError, "AI_RATE_LIMITED"),
        (400, "invalid_value", errors.AIBadRequestError, "AI_BAD_REQUEST"),
        (500, None, errors.AIProviderError, "AI_PROVIDER_ERROR"),
        (503, None, errors.AIProviderError, "AI_PROVIDER_ERROR"),
    ]

    def run_both(self, responder, exc_type):
        for name, fn in (("text", lambda: ai_client.generate_structured(
                instructions="i", input_text=SECRET_INPUT, schema=Extracted)),
                ("image", lambda: ai_client.generate_image(prompt=SECRET_INPUT))):
            with self.subTest(kind=name):
                fake = self.use(responder)
                with self.assertRaises(exc_type) as ctx:
                    fn()
                self.assert_safe(ctx.exception)
                # SDK·앱 모두 재시도하지 않음
                self.assertLessEqual(len(fake.requests), 1)
                yield ctx.exception

    def test_status_errors(self):
        for status, code, exc_type, err_code in self.cases:
            with self.subTest(status=status):
                for err in self.run_both(lambda r, s=status, c=code: httpx2.Response(s, json=error_body(c)), exc_type):
                    self.assertEqual(err.code, err_code)
                    self.assertEqual(err.status_code, status)

    def test_timeout(self):
        def responder(request):
            raise httpx2.ReadTimeout(SECRET_PROVIDER, request=request)
        for err in self.run_both(responder, errors.AITimeoutError):
            self.assertEqual(err.code, "AI_TIMEOUT")
            self.assertTrue(err.retryable)

    def test_connection_error(self):
        def responder(request):
            raise httpx2.ConnectError(SECRET_PROVIDER, request=request)
        for err in self.run_both(responder, errors.AIConnectionError):
            self.assertEqual(err.code, "AI_CONNECTION_FAILED")

    def test_to_dict_shape(self):
        err = errors.AIRateLimitError()
        self.assertEqual(err.to_dict(), {"code": "AI_RATE_LIMITED", "message": err.message})
        self.assertEqual(err.http_status, 429)


class SettingsTests(AIClientTestBase):
    env = {}

    def test_missing_key_text_no_call(self):
        os.environ["OPENAI_MODEL"] = TEXT_MODEL
        with self.assertRaises(errors.AIConfigError) as ctx:
            ai_client.generate_structured(instructions="i", input_text="t", schema=Extracted)
        self.assertEqual(ctx.exception.code, "AI_CONFIG_MISSING")
        self.assertIn("OPENAI_API_KEY", self.log_stream.getvalue())

    def test_missing_models_no_call(self):
        os.environ["OPENAI_API_KEY"] = FAKE_KEY
        with self.assertRaises(errors.AIConfigError):
            ai_client.generate_structured(instructions="i", input_text="t", schema=Extracted)
        with self.assertRaises(errors.AIConfigError) as ctx:
            ai_client.generate_image(prompt="p")
        self.assert_safe(ctx.exception)
        self.assertIn("OPENAI_IMAGE_MODEL", self.log_stream.getvalue())

    def test_text_works_without_image_model(self):
        os.environ.update({"OPENAI_API_KEY": FAKE_KEY, "OPENAI_MODEL": TEXT_MODEL})
        self.use(lambda r: httpx2.Response(200, json=text_response('{"product_name":"a","unverified":[]}')))
        self.assertEqual(ai_client.generate_structured(instructions="i", input_text="t", schema=Extracted).data.product_name, "a")

    def test_image_works_without_text_model(self):
        os.environ.update({"OPENAI_API_KEY": FAKE_KEY, "OPENAI_IMAGE_MODEL": IMAGE_MODEL})
        png = make_png(1024, 1024)
        self.use(lambda r: httpx2.Response(200, json={"created": 0, "data": [{"b64_json": base64.b64encode(png).decode()}]}))
        self.assertEqual(ai_client.generate_image(prompt="p").data, png)

    def test_settings_read_at_call_time(self):
        os.environ.update({"OPENAI_API_KEY": FAKE_KEY, "OPENAI_MODEL": "model-a"})
        fake = self.use(lambda r: httpx2.Response(200, json=text_response('{"product_name":"a","unverified":[]}')))
        ai_client.generate_structured(instructions="i", input_text="t", schema=Extracted)
        os.environ["OPENAI_MODEL"] = "model-b"
        ai_client.generate_structured(instructions="i", input_text="t", schema=Extracted)
        self.assertEqual([r["json"]["model"] for r in fake.requests], ["model-a", "model-b"])

    def test_app_import_and_home_without_key(self):
        import importlib
        import app as app_module
        importlib.reload(app_module)
        response = app_module.app.test_client().get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("fionex", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
