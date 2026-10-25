"""홍보 스튜디오 PDF 요청 검증(service.parse_pdf_request)·생성(pdf_builder)·라우트 테스트. 외부 API를 호출하지 않습니다.

실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_promotion_studio -v
"""
import io
import json
import sys
import unittest
from pathlib import Path

from PIL import Image
from pypdf import PdfReader
from werkzeug.datastructures import FileStorage, MultiDict

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from features.promotion_studio import pdf_builder, service  # noqa: E402

API = "/api/promotion-studio/pdf"


def storyboard(durations=(10, 10, 10), **overrides):
    data = {
        "title_pt": "Regen T2T: do têxtil ao têxtil",
        "title_ko": "리젠 T2T 가상 제목",
        "scenes": [{
            "number": i + 1, "start_seconds": 0, "end_seconds": 0, "duration_seconds": d,
            "visual_pt": f"Cena {i + 1} ação", "visual_ko": f"장면 {i + 1} 화면",
            "camera_pt": "Plano médio", "camera_ko": "중간 샷",
            "subtitle_pt": "", "subtitle_ko": "",
            "narration_pt": f"Narração {i + 1}", "narration_ko": f"내레이션 {i + 1}",
        } for i, d in enumerate(durations)],
        "review_notes": ["장면 2 수치 근거 확인 필요(가상)"],
        "notices": [], "model": "test", "prompt_version": "storyboard_generate_v1",
        "timing": {"total_seconds": sum(durations), "expected_seconds": 30, "ok": sum(durations) == 30},
        "conditions": {
            "audience": "바이어용", "audience_code": "buyer",
            "purposes": ["제품 소개", "전시회 홍보"], "purpose_codes": ["product_intro", "other"],
            "purpose_other": "전시회 홍보",
            "duration": 30, "scene_count": len(durations), "aspect_ratio": "9:16",
        },
    }
    data.update(overrides)
    return data


def png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (40, 20), (0, 90, 200)).save(buf, format="PNG")
    return buf.getvalue()


def request_parts(data=None, edition="bilingual", logo=None):
    form = MultiDict({"storyboard": json.dumps(data or storyboard(), ensure_ascii=False), "edition": edition})
    files = MultiDict()
    if logo is not None:
        files.add("logo", FileStorage(stream=io.BytesIO(logo[1]), filename=logo[0]))
    return form, files


def pdf_text(data):
    reader = PdfReader(io.BytesIO(data))
    return reader, [page.extract_text() for page in reader.pages]


class ParsePdfRequestTest(unittest.TestCase):
    def assert_code(self, code, *args, **kwargs):
        with self.assertRaises(service.PdfRequestError) as ctx:
            service.parse_pdf_request(*request_parts(*args, **kwargs))
        self.assertEqual(ctx.exception.code, code)

    def test_valid(self):
        board, edition, logo = service.parse_pdf_request(*request_parts())
        self.assertEqual(edition, "bilingual")
        self.assertEqual(len(board.scenes), 3)
        self.assertIsNone(logo)

    def test_edition_required(self):
        self.assert_code("PDF_INVALID_EDITION", edition="docx")

    def test_broken_json(self):
        form = MultiDict({"storyboard": "{not json", "edition": "pt"})
        with self.assertRaises(service.PdfRequestError):
            service.parse_pdf_request(form, MultiDict())

    def test_timing_mismatch_blocked(self):
        self.assert_code("PDF_TIMING_MISMATCH", storyboard((10, 10, 5)))

    def test_scene_count_and_codes_checked(self):
        bad = storyboard()
        bad["conditions"]["scene_count"] = 4
        self.assert_code("PDF_INVALID_STORYBOARD", bad)
        bad = storyboard()
        bad["conditions"]["purpose_codes"] = ["product_intro", "unknown"]
        self.assert_code("PDF_INVALID_STORYBOARD", bad)
        self.assert_code("PDF_INVALID_STORYBOARD", storyboard((15, 15)))  # 장면 3개 미만

    def test_text_length_limit(self):
        bad = storyboard()
        bad["scenes"][0]["visual_pt"] = "x" * 2001
        self.assert_code("PDF_INVALID_STORYBOARD", bad)

    def test_logo_signature_checked(self):
        self.assert_code("PDF_INVALID_LOGO", logo=("logo.png", b"not a png at all"))
        _, _, logo = service.parse_pdf_request(*request_parts(logo=("logo.png", png_bytes())))
        self.assertTrue(logo.startswith(b"\x89PNG"))


class BuildPdfTest(unittest.TestCase):
    def build(self, data=None, edition="bilingual", logo=None):
        board, _, _ = service.parse_pdf_request(*request_parts(data))
        return pdf_builder.build_pdf(board, edition, logo)

    def test_pages_cover_scenes_review(self):
        reader, pages = pdf_text(self.build())
        self.assertEqual(len(reader.pages), 3 + 2)
        self.assertIn("Regen T2T: do têxtil ao têxtil", pages[0])
        self.assertIn("리젠 T2T 가상 제목", pages[0])
        self.assertIn("전시회 홍보", pages[0])
        self.assertIn("Cena 2", pages[2])
        self.assertIn("0:10–0:20", pages[2])
        self.assertIn("내레이션 2", pages[2])
        self.assertIn("수치 근거 확인 필요", pages[-1])

    def test_portuguese_edition_has_no_korean_review_text(self):
        _, pages = pdf_text(self.build(edition="pt"))
        self.assertIn("Narração 1", pages[1])
        self.assertNotIn("내레이션 1", pages[1])
        self.assertNotIn("리젠 T2T 가상 제목", pages[0])

    def test_unsupported_characters_replaced_and_reported(self):
        data = storyboard()
        data["scenes"][1]["narration_ko"] = "탄소 배출이 적은 विकल्प입니다"
        _, pages = pdf_text(self.build(data))
        self.assertNotIn("विकल्प", pages[2])
        self.assertIn("□", pages[2])
        self.assertIn("장면 2", pages[-1])

    def test_long_text_stays_on_one_page(self):
        data = storyboard()
        data["scenes"][0]["visual_pt"] = "Texto longo de teste. " * 70
        data["scenes"][0]["visual_ko"] = "긴 가상 문장입니다. " * 70
        reader, _ = pdf_text(self.build(data))
        self.assertEqual(len(reader.pages), 5)

    def test_logo_embedded(self):
        reader, _ = pdf_text(self.build(logo=png_bytes()))
        self.assertTrue(reader.pages[0].images)

    def test_broken_logo_raises(self):
        board, _, _ = service.parse_pdf_request(*request_parts())
        with self.assertRaises(pdf_builder.LogoImageError):
            pdf_builder.build_pdf(board, "pt", b"\x89PNG\r\n\x1a\n" + b"\x00" * 30)


class PdfRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import create_app
        cls.client = create_app().test_client()

    def post(self, data):
        return self.client.post(API, data=data, content_type="multipart/form-data")

    def test_download(self):
        res = self.post({"storyboard": json.dumps(storyboard()), "edition": "pt",
                         "logo": (io.BytesIO(png_bytes()), "logo.png")})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "application/pdf")
        self.assertIn("attachment", res.headers["Content-Disposition"])
        self.assertTrue(res.data.startswith(b"%PDF"))

    def test_errors_are_json(self):
        res = self.post({"storyboard": json.dumps(storyboard((10, 10, 5))), "edition": "pt"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()["error"]["code"], "PDF_TIMING_MISMATCH")
        bad_logo = b"\x89PNG\r\n\x1a\n" + b"\x00" * 30
        res = self.post({"storyboard": json.dumps(storyboard()), "edition": "pt",
                         "logo": (io.BytesIO(bad_logo), "logo.png")})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()["error"]["code"], "PDF_INVALID_LOGO")

    def test_panel_has_pdf_controls(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn('disabled aria-describedby="promotion_studio-pdf-hint" data-ps-pdf>', html)
        self.assertIn('<option value="pt">포르투갈어 전용본</option>', html)


if __name__ == "__main__":
    unittest.main()
