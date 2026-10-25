"""common.ai_client.generate_image_from_references 모의 테스트. 실제 OpenAI 요청을 보내지 않습니다.

2026-10-25 정은진 추가(공통 담당 검토 대기). 실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_common -v
"""
import base64
import sys
import unittest
from pathlib import Path
from unittest import mock

import httpx2
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common import ai_client, config, errors  # noqa: E402
from tests.test_common.test_ai_client import (  # noqa: E402
    IMAGE_MODEL, SECRET_INPUT, AIClientTestBase, error_body, make_png)

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 64


class MultipartMock:
    """multipart 요청 본문을 기록하고 지정한 응답을 돌려주는 가짜 전송."""

    def __init__(self, responder):
        self.responder = responder
        self.requests = []

    def factory(self, api_key, timeout, max_retries):
        def handler(request):
            self.requests.append({"path": request.url.path, "body": request.read(),
                                  "content_type": request.headers.get("content-type", ""), "timeout": timeout})
            return self.responder(request)

        return OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries,
                      http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))


def image_response(png, usage=True):
    body = {"created": 0, "data": [{"b64_json": base64.b64encode(png).decode()}]}
    if usage:
        body["usage"] = {"input_tokens": 1200, "output_tokens": 800, "total_tokens": 2000,
                         "input_tokens_details": {"image_tokens": 1100, "text_tokens": 100}}
    return body


class ReferenceImageTests(AIClientTestBase):
    def use_multipart(self, responder):
        fake = MultipartMock(responder)
        p = mock.patch.object(ai_client, "_create_client", fake.factory)
        p.start()
        self.addCleanup(p.stop)
        return fake

    def call(self, **kw):
        args = {"prompt": "장면 " + SECRET_INPUT, "reference_images": [make_png(8, 8)], "size": "1024x1024"}
        args.update(kw)
        return ai_client.generate_image_from_references(**args)

    def test_success_sends_edit_request_with_fixed_names(self):
        fake = self.use_multipart(lambda r: httpx2.Response(200, json=image_response(make_png(1536, 1024))))
        result = self.call(reference_images=[make_png(8, 8), JPEG, WEBP], size="1536x1024")
        self.assertEqual((result.image.width, result.image.height), (1536, 1024))
        self.assertEqual(result.image.model, IMAGE_MODEL)
        self.assertEqual(result.usage.output_tokens, 800)
        self.assertEqual(result.usage.input_image_tokens, 1100)
        req = fake.requests[0]
        self.assertEqual(req["path"], "/v1/images/edits")
        self.assertIn("multipart/form-data", req["content_type"])
        body = req["body"]
        for name in (b'filename="reference_1.png"', b'filename="reference_2.jpg"', b'filename="reference_3.webp"'):
            self.assertIn(name, body)
        self.assertIn(IMAGE_MODEL.encode(), body)
        self.assertNotIn(b"input_fidelity", body)
        self.assertEqual(req["timeout"], config.IMAGE_TIMEOUT_SECONDS)

    def test_usage_optional(self):
        self.use_multipart(lambda r: httpx2.Response(200, json=image_response(make_png(1024, 1024), usage=False)))
        self.assertIsNone(self.call().usage)

    def test_input_checked_before_api(self):
        # 기본 _create_client는 호출 시 실패하므로 아래는 모두 API 호출 전 오류여야 합니다.
        for refs in ([], None, [b""], [b"GIF89a" + b"\x00" * 10], [make_png(8, 8)] * (config.IMAGE_REF_MAX_FILES + 1)):
            with self.assertRaises(errors.AIInputError):
                self.call(reference_images=refs)
        with mock.patch.object(config, "IMAGE_REF_MAX_BYTES", 10):
            with self.assertRaises(errors.AIInputError) as ctx:
                self.call()
            self.assertEqual(ctx.exception.http_status, 413)
        with self.assertRaises(errors.AIInputError):
            self.call(size="999x999")
        with self.assertRaises(errors.AIInputError):
            self.call(prompt=" ")

    def test_missing_image_model(self):
        with mock.patch.dict("os.environ", {"OPENAI_IMAGE_MODEL": ""}):
            with self.assertRaises(errors.AIConfigError):
                self.call()

    def test_wrong_size_and_moderation(self):
        self.use_multipart(lambda r: httpx2.Response(200, json=image_response(make_png(1024, 1024))))
        with self.assertRaises(errors.AIImageInvalidError) as ctx:
            self.call(size="1536x1024")
        self.assert_safe(ctx.exception)
        self.use_multipart(lambda r: httpx2.Response(400, json=error_body("moderation_blocked")))
        with self.assertRaises(errors.AIRefusalError) as ctx:
            self.call()
        self.assert_safe(ctx.exception)


if __name__ == "__main__":
    unittest.main()
