"""POST /api/product-brochure/pdf — 적용한 AI 표지 배경 포함(multipart) 경로 테스트. OpenAI·네트워크를 쓰지 않습니다.

이미지는 코드로 만든 가상 PNG(단색)이며 실제 AI 생성 이미지가 아닙니다. PDF는 메모리에서만 확인합니다(파일 저장 없음).
"""
import gc
import hashlib
import io
import json
import struct
import sys
import unittest
import warnings
import zlib
from pathlib import Path
from unittest import mock

from PIL import Image
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pdf_fixtures  # noqa: E402
from test_pdf_download_api import Base, flat  # noqa: E402

from features.product_brochure import generation, pdf_catalog, pdf_download  # noqa: E402

URL = "/api/product-brochure/pdf"


def png_bytes(color=(200, 30, 30), size=(1024, 1536), mode="RGB", **save):
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, format="PNG", **save)
    return buf.getvalue()


def apng_bytes():
    buf = io.BytesIO()
    frames = [Image.new("RGB", (1024, 1536), c) for c in ((255, 0, 0), (0, 0, 255))]
    frames[0].save(buf, format="PNG", save_all=True, append_images=frames[1:])
    return buf.getvalue()


RED = png_bytes((210, 20, 20))
BLUE = png_bytes((20, 40, 210))


def page_images(pdf):
    """쪽별 이미지 XObject (가로, 세로, 데이터 해시, 가운데 화소 색)."""
    out = []
    for page in PdfReader(io.BytesIO(pdf)).pages:
        row = []
        for xo in page["/Resources"]["/XObject"].values():
            obj = xo.get_object()
            data = obj.get_data()
            with Image.open(io.BytesIO(data)) as im:
                center = im.convert("RGB").getpixel((im.width // 2, im.height // 2))
            row.append((int(obj["/Width"]), int(obj["/Height"]), hashlib.sha256(data).hexdigest()[:16], center))
        out.append(row)
    return out


def near(color, target, tol=40):
    return all(abs(a - b) <= tol for a, b in zip(color, target))


class CoverBase(Base):
    def post_multipart(self, catalog_text=None, image=RED, filename="cover.png", extra=None, fields=None):
        if fields is None:
            fields = {}
            if catalog_text is not None:
                fields["catalog"] = catalog_text
            if image is not None:
                fields["cover_image"] = (io.BytesIO(image), filename)
        if extra:
            fields.update(extra)
        res = self.client.post(URL, data=fields, content_type="multipart/form-data")
        self.addCleanup(res.close)
        # Werkzeug 테스트 클라이언트가 큰 multipart 본문을 만들며 연 임시 입력 스트림.
        # 서버의 FileStorage 정리와 별개인 테스트 소유 자원이므로 직접 닫는다.
        self.addCleanup(res.request.environ["wsgi.input"].close)
        return res

    def catalog_text(self, data=None):
        return json.dumps({"catalog": data or pdf_fixtures.base()}, ensure_ascii=False)


class CoverSuccessTests(CoverBase):
    def test_multipart_pdf_uses_cover_only_on_page1(self):
        default = page_images(self.post({"catalog": pdf_fixtures.base()}).get_data())   # 기존 JSON 경로
        res = self.post_multipart(self.catalog_text(), RED)
        self.assertEqual(res.status_code, 200, res.get_data(as_text=True)[:200] if res.is_json else "")
        self.assertEqual(res.mimetype, "application/pdf")
        self.assertEqual(res.headers["Content-Disposition"], 'attachment; filename="fionex_catalog_pt-BR.pdf"')
        self.assertEqual(res.headers["Cache-Control"], "no-store")
        pdf = res.get_data()
        reader = PdfReader(io.BytesIO(pdf))
        self.assertEqual(len(reader.pages), 4)
        for p in reader.pages:
            self.assertAlmostEqual(float(p.mediabox.width), 595.28, places=1)
        imgs = page_images(pdf)
        self.assertEqual(imgs[0][0][:2], (1024, 1536))
        self.assertTrue(near(imgs[0][0][3], (210, 20, 20)), imgs[0][0][3])     # 1쪽: 적용 이미지(빨강)
        self.assertNotEqual(imgs[0][0][2], default[0][0][2])
        self.assertEqual([r[0][2] for r in imgs[1:]], [r[0][2] for r in default[1:]])  # 2·3·4쪽 그대로(4쪽 기본 표지 크롭 포함)
        texts = [flat(p.extract_text()) for p in reader.pages]
        self.assertIn("Fibra Exemplo D1", texts[0])                           # 제목·소개는 선택 가능한 텍스트
        self.assertIn("Imagem conceitual gerada por IA", texts[0])
        self.assertIn(generation.NOTICE_UNOFFICIAL, texts[0])

    def test_replace_and_restore_change_page1_only(self):
        blue = page_images(self.post_multipart(self.catalog_text(), BLUE).get_data())
        self.assertTrue(near(blue[0][0][3], (20, 40, 210)))
        default = page_images(self.post({"catalog": pdf_fixtures.base()}).get_data())   # 기본 배경으로 복원 = JSON
        self.assertFalse(near(default[0][0][3], (20, 40, 210)))
        self.assertEqual([r[0][2] for r in blue[1:]], [r[0][2] for r in default[1:]])

    def test_transparent_png_composited_on_cover_background(self):
        rgba = png_bytes((0, 0, 0, 0), mode="RGBA")                          # 완전 투명
        imgs = page_images(self.post_multipart(self.catalog_text(), rgba).get_data())
        self.assertTrue(near(imgs[0][0][3], (0xef, 0xeb, 0xe2), tol=6), imgs[0][0][3])  # 화면 표지 영역 바탕색

    def test_validated_image_is_rebuilt_without_metadata(self):
        from PIL import PngImagePlugin
        info = PngImagePlugin.PngInfo()
        info.add_text("Comment", "SECRET-METADATA-7781")
        seen = []
        real = pdf_catalog.build_pdf

        def spy(catalog, cover_image=None):
            seen.append((cover_image.mode, cover_image.size, dict(cover_image.info)))
            return real(catalog, cover_image=cover_image)
        with mock.patch.object(pdf_catalog, "build_pdf", spy):
            res = self.post_multipart(self.catalog_text(), png_bytes(pnginfo=info))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(seen, [("RGB", (1024, 1536), {})])
        self.assertNotIn(b"SECRET-METADATA-7781", res.get_data())

    def test_no_ai_network_or_resource_leak(self):
        def forbid(*a, **k):
            raise AssertionError("PDF 생성 중 AI 호출 금지")
        with warnings.catch_warnings(record=True) as caught, mock.patch.object(generation, "generate_structured", forbid):
            warnings.simplefilter("always", ResourceWarning)
            self.assertEqual(self.post_multipart(self.catalog_text(), RED).status_code, 200)
            self.assertError(self.post_multipart(self.catalog_text(), b"not png"), 400, "BROCHURE_PDF_COVER_INVALID")
            gc.collect()
        self.assertEqual([w for w in caught if issubclass(w.category, ResourceWarning)], [])
        self.assertNotIn("cover.png", self.logs.getvalue())
        self.assertNotIn("Fibra Exemplo", self.logs.getvalue())
        self.assertSlotsFree()


class CoverRejectTests(CoverBase):
    def setUp(self):
        super().setUp()
        self.renders = 0
        real = pdf_catalog.build_pdf

        def counting(*a, **k):
            self.renders += 1
            return real(*a, **k)
        p = mock.patch.object(pdf_catalog, "build_pdf", counting)
        p.start()
        self.addCleanup(p.stop)

    def tearDown(self):
        self.assertEqual(self.renders, 0, "거부해야 할 요청에서 렌더러 실행")
        self.assertSlotsFree()

    def test_form_shape(self):
        cat = self.catalog_text()
        cases = [
            self.post_multipart(None, RED),                                              # catalog 누락
            self.post_multipart(cat, None),                                              # 이미지 누락
            self.post_multipart(cat, RED, extra={"html": "<b>x</b>"}),                   # 추가 텍스트 필드
            self.post_multipart(cat, RED, extra={"extra_file": (io.BytesIO(BLUE), "cover.png")}),  # 추가 파일
            self.post_multipart(fields={"catalog": [cat, cat], "cover_image": (io.BytesIO(RED), "cover.png")}),  # 중복
            self.post_multipart(fields={"catalog": cat, "cover_image": [(io.BytesIO(RED), "cover.png"),
                                                                        (io.BytesIO(BLUE), "cover.png")]}),
            self.post_multipart(fields={"catalog": (io.BytesIO(cat.encode()), "catalog.json"),
                                        "cover_image": (io.BytesIO(RED), "cover.png")}),  # catalog를 파일로
            self.post_multipart(cat, RED, filename="../../etc/passwd.png"),              # 파일명 고정
        ]
        for res in cases:
            with self.subTest():
                self.assertError(res, 400, "BROCHURE_PDF_INVALID_FORM")

    def test_catalog_field_json_and_contract(self):
        self.assertError(self.post_multipart('{"catalog": ', RED), 400, "BROCHURE_PDF_INVALID_JSON")
        self.assertError(self.post_multipart(json.dumps({"catalog": pdf_fixtures.base(), "x": 1}), RED), 400,
                         "BROCHURE_PDF_INVALID_INPUT")
        bad = pdf_fixtures.base()
        bad["cover"]["tagline"]["text"] = "리젠"
        self.assertError(self.post_multipart(self.catalog_text(bad), RED), 400, "BROCHURE_PDF_INVALID_INPUT")
        big = json.dumps({"catalog": pdf_fixtures.base(), "pad": "x" * (32 * 1024)})
        self.assertError(self.post_multipart(big, RED), 413, "BROCHURE_PDF_REQUEST_TOO_LARGE")

    def test_image_rejections(self):
        truncated = RED[:len(RED) // 2]
        cases = {
            "fake": b"GIF89a" + b"\x00" * 100,
            "png_sig_only": b"\x89PNG\r\n\x1a\n" + b"\x00" * 50,
            "truncated": truncated,
            "corrupt_crc": RED[:40] + bytes([RED[40] ^ 0xFF]) + RED[41:],
            "wrong_size": png_bytes(size=(1024, 1024)),
            "landscape": png_bytes(size=(1536, 1024)),
            "jpeg": (lambda b: (Image.new("RGB", (1024, 1536)).save(b, format="JPEG"), b.getvalue())[1])(io.BytesIO()),
            "apng": apng_bytes(),
        }
        for name, data in cases.items():
            with self.subTest(name=name):
                self.assertError(self.post_multipart(self.catalog_text(), data), 400, "BROCHURE_PDF_COVER_INVALID")
        self.assertError(self.post_multipart(self.catalog_text(), b""), 400, "BROCHURE_PDF_COVER_INVALID")

    def test_size_limits(self):
        with mock.patch.object(pdf_download, "MAX_COVER_BYTES", 1000):
            self.assertError(self.post_multipart(self.catalog_text(), RED), 413, "BROCHURE_PDF_COVER_TOO_LARGE")
        huge = b"\x89PNG\r\n\x1a\n" + b"\x00" * (pdf_download.MAX_MULTIPART_BYTES + 10)   # 전체 요청 상한 초과
        self.assertError(self.post_multipart(self.catalog_text(), huge), 413, "BROCHURE_PDF_REQUEST_TOO_LARGE")
        self.assertIsNone(self.client.application.config.get("MAX_CONTENT_LENGTH"))
        self.assertEqual(pdf_download.MAX_MULTIPART_BYTES, 16 * 1024 * 1024 + 96 * 1024)

    def test_too_many_parts(self):
        extra = {f"f{i}": "x" for i in range(5)}
        res = self.post_multipart(self.catalog_text(), RED, extra=extra)
        self.assertIn(res.status_code, (400, 413))
        self.assertIn(res.get_json()["error"]["code"], ("BROCHURE_PDF_INVALID_FORM", "BROCHURE_PDF_REQUEST_TOO_LARGE"))


class CoverSlotTests(CoverBase):
    def test_busy_and_slot_release_after_image_failure(self):
        held = [pdf_download._slots.acquire(blocking=False) for _ in range(2)]
        try:
            self.assertError(self.post_multipart(self.catalog_text(), RED), 429, "BROCHURE_PDF_BUSY")
        finally:
            for _ in held:
                pdf_download._slots.release()
        for _ in range(3):  # 이미지 검증 실패가 슬롯을 새게 하면 세 번째부터 429
            self.assertError(self.post_multipart(self.catalog_text(), png_bytes(size=(10, 10))), 400,
                             "BROCHURE_PDF_COVER_INVALID")
        self.assertSlotsFree()

    def test_image_decode_happens_inside_slot(self):
        observed = []
        real = pdf_download.validate_cover

        def spy(data):
            free = pdf_download._slots.acquire(blocking=False)
            if free:
                pdf_download._slots.release()
            other = pdf_download._slots.acquire(blocking=False)
            observed.append(other)
            if other:
                pdf_download._slots.release()
            return real(data)
        held = pdf_download._slots.acquire(blocking=False)  # 1개를 미리 잡아 두면 검증 중에는 남은 자리가 없어야 함
        try:
            with mock.patch.object(pdf_download, "validate_cover", spy):
                self.assertEqual(self.post_multipart(self.catalog_text(), RED).status_code, 200)
        finally:
            pdf_download._slots.release()
        self.assertTrue(held)
        self.assertEqual(observed, [False])
        self.assertSlotsFree()


if __name__ == "__main__":
    unittest.main()
