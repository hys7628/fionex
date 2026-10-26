"""POST /api/product-brochure/pdf 테스트. 실제 렌더러(pdf_catalog.build_pdf)를 거치며 OpenAI·네트워크를 쓰지 않습니다.
입력은 고정 가상 데이터(pdf_fixtures)이고 PDF는 메모리에서만 확인합니다(파일 저장 없음).
실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_product_brochure -v
"""
import builtins
import gc
import io
import json
import logging
import os
import socket
import sys
import threading
import unittest
import warnings
from pathlib import Path
from unittest import mock

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pdf_fixtures  # noqa: E402

from app import create_app  # noqa: E402
from common import ai_client  # noqa: E402
from features.product_brochure import generation, pdf_catalog, pdf_download  # noqa: E402

URL = "/api/product-brochure/pdf"
SECRET_INPUT = "SECRETPDFINPUT7731"
SECRET_PATH = "C:\\Users\\someone\\secret_dir\\internal.py"


def flat(text):
    return " ".join(text.split())


class Base(unittest.TestCase):
    def setUp(self):
        # OpenAI 키 없이 동작해야 함(PDF 생성은 AI를 쓰지 않음)
        env = {k: v for k, v in os.environ.items() if not k.startswith("OPENAI_")}
        p = mock.patch.dict(os.environ, env, clear=True)
        p.start()
        self.addCleanup(p.stop)

        def no_ai(*a, **k):
            raise AssertionError("PDF 다운로드 중 OpenAI 클라이언트 생성 금지")
        p2 = mock.patch.object(ai_client, "_create_client", no_ai)
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

    def post(self, body=None, *, raw=None, content_type="application/json"):
        data = raw if raw is not None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        res = self.client.post(URL, data=data, content_type=content_type)
        self.addCleanup(res.close)
        return res

    def assertError(self, res, status, code):
        self.assertEqual(res.status_code, status, res.get_data(as_text=True))
        self.assertTrue(res.is_json)
        body = res.get_json()
        self.assertEqual(body["ok"], False)
        self.assertEqual(body["error"]["code"], code)
        self.assertEqual(set(body["error"]), {"code", "message"})
        self.assertNotIn("Content-Disposition", res.headers)
        return body["error"]

    def assertSlotsFree(self):
        acquired = [pdf_download._slots.acquire(blocking=False) for _ in range(pdf_download.MAX_CONCURRENT_RENDERS)]
        for ok in acquired:
            if ok:
                pdf_download._slots.release()
        self.assertEqual(acquired, [True] * pdf_download.MAX_CONCURRENT_RENDERS)


class SuccessTests(Base):
    def test_download_response_and_four_a4_pages(self):
        res = self.post({"catalog": pdf_fixtures.base()})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "application/pdf")
        self.assertEqual(res.headers["Content-Disposition"], 'attachment; filename="fionex_catalog_pt-BR.pdf"')
        self.assertEqual(res.headers["Cache-Control"], "no-store")
        self.assertEqual(res.headers["X-Content-Type-Options"], "nosniff")
        pdf = res.get_data()
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertEqual(int(res.headers["Content-Length"]), len(pdf))
        reader = PdfReader(io.BytesIO(pdf))
        self.assertEqual(len(reader.pages), 4)
        for page in reader.pages:
            self.assertAlmostEqual(float(page.mediabox.width), 595.28, places=1)
            self.assertAlmostEqual(float(page.mediabox.height), 841.89, places=1)
        self.assertSlotsFree()

    def test_edited_values_and_virtual_notices_without_mock_text(self):
        catalog = pdf_fixtures.edited()
        res = self.post({"catalog": catalog})
        self.assertEqual(res.status_code, 200)
        texts = [flat(p.extract_text()) for p in PdfReader(io.BytesIO(res.get_data())).pages]
        self.assertIn("Fio Ação & Têxtil <Demo>", texts[0])
        self.assertIn("800 kg por pedido (editado)", texts[3])
        self.assertIn(generation.NOTICE_FICTITIOUS_CONTENT, texts[1])   # 가상 문단
        self.assertEqual(texts[3].count(generation.NOTICE_FICTITIOUS), 3)
        joined = " ".join(texts)
        self.assertIn(generation.NOTICE_UNOFFICIAL, texts[0])
        for mock_text in ("regen T2T", "Fibra de poliéster feita a partir", "O regen T2T"):
            self.assertNotIn(mock_text, joined)  # 고정 디자인 시안 문구 미혼입
        self.assertNotIn(catalog["cover"]["product_name"]["text"], self.logs.getvalue())

    def test_filename_and_headers_ignore_user_input(self):
        catalog = pdf_fixtures.base()
        catalog["cover"]["product_name"]["text"] = 'Fio evil"; f=x.exe ..\\'
        res = self.post({"catalog": catalog})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["Content-Disposition"], 'attachment; filename="fionex_catalog_pt-BR.pdf"')
        self.assertNotIn("evil", " ".join(f"{k}: {v}" for k, v in res.headers.items()))

    def test_app_and_existing_screen_work_without_key(self):
        self.assertNotIn("OPENAI_API_KEY", os.environ)
        page = self.client.get("/")
        self.addCleanup(page.close)
        self.assertEqual(page.status_code, 200)
        self.assertIn("data-catalog-dialog", page.get_data(as_text=True))
        self.assertEqual(self.post({"catalog": pdf_fixtures.base()}).status_code, 200)


class RequestValidationTests(Base):
    def setUp(self):
        super().setUp()
        self.renders = 0
        real = pdf_catalog.build_pdf

        def counting(payload):
            self.renders += 1
            return real(payload)
        p = mock.patch.object(pdf_catalog, "build_pdf", counting)
        p.start()
        self.addCleanup(p.stop)

    def tearDown(self):
        self.assertEqual(self.renders, 0, "잘못된 요청에서 렌더러가 실행됨")
        self.assertSlotsFree()

    def test_content_type_json_and_empty_body(self):
        good = json.dumps({"catalog": pdf_fixtures.base()}).encode()
        self.assertError(self.post(raw=good, content_type="text/plain"), 400, "BROCHURE_PDF_INVALID_JSON")
        self.assertError(self.post(raw=good, content_type="application/x-www-form-urlencoded"), 400,
                         "BROCHURE_PDF_INVALID_JSON")
        self.assertError(self.post(raw=b'{"catalog": {', content_type="application/json"), 400,
                         "BROCHURE_PDF_INVALID_JSON")
        self.assertError(self.post(raw=b"", content_type="application/json"), 400, "BROCHURE_PDF_INVALID_JSON")

    def test_top_level_shape(self):
        catalog = pdf_fixtures.base()
        for body in ([catalog], "catalog", 1, None, {}, {"catalog": catalog, "html": "<b>x</b>"},
                     {"catalog": catalog, "filename": "x.pdf"}, {"data": catalog}, {"catalog": [catalog]},
                     {"catalog": "x"}, {"catalog": None}):
            with self.subTest(body=str(body)[:40]):
                code = "BROCHURE_PDF_INVALID_JSON" if body is None else "BROCHURE_PDF_INVALID_INPUT"
                self.assertError(self.post(body), 400, code)

    def test_catalog_contract_reused_from_renderer(self):
        cases = []
        d = pdf_fixtures.base(); d["cover"]["tagline"]["virtual"] = "true"; cases.append(d)        # noqa: E702
        d = pdf_fixtures.base(); d["supply"]["items"][0]["label"] = "Rótulo"; cases.append(d)     # noqa: E702
        d = pdf_fixtures.base(); d["image_url"] = "file:///etc/passwd"; cases.append(d)           # noqa: E702
        d = pdf_fixtures.base(); d["cover"]["tagline"]["text"] = "리젠"; cases.append(d)          # noqa: E702
        d = pdf_fixtures.base(); d["intro"]["paragraphs"] = []; cases.append(d)                   # noqa: E702
        d = pdf_fixtures.base(); d["details"]["items"][0]["value"] = "a" * 301; cases.append(d)   # noqa: E702
        for catalog in cases:
            with self.subTest():
                self.assertError(self.post({"catalog": catalog}), 400, "BROCHURE_PDF_INVALID_INPUT")

    def test_body_over_32kib(self):
        catalog = pdf_fixtures.base()
        catalog["cover"]["tagline"]["text"] = "a" * (pdf_download.MAX_REQUEST_BYTES + 10)
        err = self.assertError(self.post({"catalog": catalog}), 413, "BROCHURE_PDF_REQUEST_TOO_LARGE")
        self.assertNotIn("aaaa", err["message"])

    def test_limit_applies_only_to_this_route(self):
        self.assertIsNone(self.client.application.config.get("MAX_CONTENT_LENGTH"))


class RendererErrorTests(Base):
    def tearDown(self):
        self.assertSlotsFree()  # 실패 후에도 슬롯 반환

    def test_overflow_glyph_asset_keep_codes_and_status(self):
        self.assertError(self.post({"catalog": pdf_fixtures.overflow_details()}), 422, "BROCHURE_PDF_LAYOUT_OVERFLOW")
        d = pdf_fixtures.base()
        d["cover"]["tagline"]["text"] = "emoji \U0001F600"
        self.assertError(self.post({"catalog": d}), 422, "BROCHURE_PDF_GLYPH_MISSING")
        files = dict(pdf_catalog.IMAGE_FILES)
        files["cover"] = Path(SECRET_PATH)
        with mock.patch.object(pdf_catalog, "IMAGE_FILES", files):
            err = self.assertError(self.post({"catalog": pdf_fixtures.base()}), 500, "BROCHURE_PDF_ASSET_UNAVAILABLE")
        self.assertNotIn("secret_dir", json.dumps(err) + self.logs.getvalue())

    def test_unexpected_error_is_generic_and_leaks_nothing(self):
        def boom(payload):
            raise RuntimeError(f"{SECRET_INPUT} {SECRET_PATH} sk-test-SECRET")
        catalog = pdf_fixtures.base()
        catalog["cover"]["tagline"]["text"] = SECRET_INPUT
        with mock.patch.object(pdf_catalog, "build_pdf", boom):
            res = self.post({"catalog": catalog})
        err = self.assertError(res, 500, "BROCHURE_PDF_RENDER_FAILED")
        self.assertEqual(err["message"], pdf_catalog.CatalogPdfRenderError.message)
        exposed = res.get_data(as_text=True) + self.logs.getvalue()
        for secret in (SECRET_INPUT, "secret_dir", "sk-test-SECRET", "Traceback"):
            self.assertNotIn(secret, exposed)
        self.assertIn("type=RuntimeError", self.logs.getvalue())


class ConcurrencyTests(Base):
    def test_busy_returns_429_without_rendering(self):
        held = [pdf_download._slots.acquire(blocking=False) for _ in range(2)]
        try:
            self.assertEqual(held, [True, True])
            with mock.patch.object(pdf_catalog, "build_pdf", side_effect=AssertionError("렌더링 금지")):
                err = self.assertError(self.post({"catalog": pdf_fixtures.base()}), 429, "BROCHURE_PDF_BUSY")
            self.assertIn("잠시 후", err["message"])
        finally:
            for _ in held:
                pdf_download._slots.release()
        self.assertEqual(self.post({"catalog": pdf_fixtures.base()}).status_code, 200)
        self.assertSlotsFree()

    def test_two_running_third_rejected_immediately_then_released(self):
        started, release = threading.Semaphore(0), threading.Event()
        results = []

        def slow(payload):
            started.release()
            release.wait(10)
            return b"%PDF-fake"

        def worker():
            client = create_app().test_client()
            res = client.post(URL, json={"catalog": pdf_fixtures.base()})
            results.append(res.status_code)
            res.close()

        with mock.patch.object(pdf_catalog, "build_pdf", slow):
            threads = [threading.Thread(target=worker) for _ in range(2)]
            for t in threads:
                t.start()
            for _ in range(2):
                self.assertTrue(started.acquire(timeout=10))
            self.assertError(self.post({"catalog": pdf_fixtures.base()}), 429, "BROCHURE_PDF_BUSY")  # 대기 없이 즉시
            release.set()
            for t in threads:
                t.join(10)
        self.assertEqual(sorted(results), [200, 200])
        self.assertSlotsFree()

    def test_slot_released_after_unexpected_error(self):
        with mock.patch.object(pdf_catalog, "build_pdf", side_effect=RuntimeError("x")):
            for _ in range(3):  # 슬롯이 새면 세 번째부터 429가 됨
                self.assertError(self.post({"catalog": pdf_fixtures.base()}), 500, "BROCHURE_PDF_RENDER_FAILED")
        self.assertSlotsFree()


class IsolationTests(Base):
    def test_no_network_ai_file_write_or_resource_warning(self):
        def forbid(*a, **k):
            raise AssertionError("PDF 다운로드 중 네트워크 연결 금지")
        real_open = builtins.open
        writes = []

        def guarded_open(file, mode="r", *a, **k):
            if any(m in mode for m in "wax+"):
                writes.append(str(file))
            return real_open(file, mode, *a, **k)
        with warnings.catch_warnings(record=True) as caught, \
                mock.patch.object(socket.socket, "connect", forbid), \
                mock.patch.object(generation, "generate_structured", forbid), \
                mock.patch("builtins.open", guarded_open):
            warnings.simplefilter("always", ResourceWarning)
            self.assertEqual(self.post({"catalog": pdf_fixtures.edited()}).status_code, 200)
            self.assertError(self.post({"catalog": pdf_fixtures.overflow_details()}), 422, "BROCHURE_PDF_LAYOUT_OVERFLOW")
            gc.collect()
        self.assertEqual(writes, [])
        self.assertEqual([w for w in caught if issubclass(w.category, ResourceWarning)], [])

    def test_routes_wire_download_through_helper(self):
        src = (Path(__file__).resolve().parents[2] / "features" / "product_brochure" / "routes.py").read_text(encoding="utf-8")
        start = src.index('@bp.post("/api/product-brochure/pdf")')
        block = src[start:]
        self.assertIn("pdf_download.render(payload, cover_bytes)", block)
        self.assertIn("request.close()", block)  # multipart 임시 파일 정리(성공·실패 모두)
        for forbidden in ("generate_catalog", "analyze_pdf", "send_file", "download_name=", "save(", "str(exc", "repr(exc",
                          ", exc)", "exc_info", "logger.exception"):
            self.assertNotIn(forbidden, block)


if __name__ == "__main__":
    unittest.main()
