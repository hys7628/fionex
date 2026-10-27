"""홍보 스튜디오 장면 이미지 생성(service.generate_scene_image)·PDF 장면 이미지 포함 테스트.

공통 AI 호출(service.generate_image_from_references)을 가짜 함수로 바꿔 외부 API를 호출하지 않습니다.
실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_promotion_studio -v
"""
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image
from pypdf import PdfReader
from werkzeug.datastructures import FileStorage, MultiDict

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.ai_client import GeneratedImage, ImageUsage, ReferenceImageResult  # noqa: E402
from common.errors import AIConfigError  # noqa: E402
from features.promotion_studio import service  # noqa: E402
from test_pdf_download import storyboard  # noqa: E402


def png(w=40, h=30, color=(0, 90, 200)):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


def scene_form(**overrides):
    data = {"visual_pt": "Close no fio regen", "camera_pt": "Plano fechado", "aspect_ratio": "16:9",
            "image_style_code": "photo", "image_style": "실사형"}
    data.update(overrides)
    return MultiDict({"scene": json.dumps(data, ensure_ascii=False)})


def photo_files(*items):
    files = MultiDict()
    for name, data in items:
        files.add("photos", FileStorage(stream=io.BytesIO(data), filename=name))
    return files


def fake_result(usage=True):
    image = GeneratedImage(data=png(1536, 1024), mime_type="image/png", width=1536, height=1024, model="test-image")
    u = ImageUsage(input_tokens=1200, output_tokens=1000, total_tokens=2200, input_image_tokens=1100, input_text_tokens=100)
    return ReferenceImageResult(image=image, usage=u if usage else None)


class GenerateSceneImageTest(unittest.TestCase):
    def test_photo_required_before_ai_call(self):
        with mock.patch.object(service, "generate_image_from_references") as call:
            with self.assertRaises(service.PdfRequestError) as ctx:
                service.generate_scene_image(scene_form(), MultiDict())
        call.assert_not_called()
        self.assertEqual(ctx.exception.code, "SCENE_IMAGE_PHOTO_REQUIRED")

    def test_fake_photo_rejected(self):
        with mock.patch.object(service, "generate_image_from_references") as call:
            with self.assertRaises(service.PdfRequestError):
                service.generate_scene_image(scene_form(), photo_files(("p.png", b"not png")))
        call.assert_not_called()

    def test_all_photos_sent_as_references(self):
        photos = (("a.png", png()), ("b.png", png(color=(200, 0, 0))))
        with mock.patch.object(service, "generate_image_from_references", return_value=fake_result()) as call:
            data = service.generate_scene_image(scene_form(), photo_files(*photos))
        kwargs = call.call_args.kwargs
        self.assertEqual(kwargs["reference_images"], [photos[0][1], photos[1][1]])
        self.assertEqual(kwargs["size"], "1536x1024")
        self.assertEqual(kwargs["quality"], service.SCENE_IMAGE_QUALITY)
        self.assertIn("Close no fio regen", kwargs["prompt"])
        self.assertIn("photorealistic", kwargs["prompt"])
        self.assertIn("reference images", kwargs["prompt"])
        self.assertEqual(data["reference_count"], 2)
        self.assertEqual(data["width"], 1536)
        # (1100×8 + 100×5 + 1000×30) / 1,000,000
        self.assertAlmostEqual(data["estimated_cost_usd"], 0.0393, places=4)

    def test_size_and_style_mapping(self):
        with mock.patch.object(service, "generate_image_from_references", return_value=fake_result(usage=False)) as call:
            data = service.generate_scene_image(
                scene_form(aspect_ratio="4:5", image_style_code="other", image_style="수채화풍"),
                photo_files(("a.png", png())))
        kwargs = call.call_args.kwargs
        self.assertEqual(kwargs["size"], "1024x1536")
        self.assertIn("central 4:5 area", kwargs["prompt"])
        self.assertIn("수채화풍", kwargs["prompt"])
        self.assertIsNone(data["estimated_cost_usd"])

    def test_invalid_scene_json(self):
        with self.assertRaises(service.PdfRequestError):
            service.generate_scene_image(MultiDict({"scene": "{"}), photo_files(("a.png", png())))
        with self.assertRaises(service.PdfRequestError):
            service.generate_scene_image(scene_form(aspect_ratio="2:1"), photo_files(("a.png", png())))


class SceneImageRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import create_app
        cls.client = create_app().test_client()

    def post(self, data):
        return self.client.post("/api/promotion-studio/scene-image", data=data, content_type="multipart/form-data")

    def test_success_and_errors(self):
        form = {"scene": scene_form()["scene"], "photos": (io.BytesIO(png()), "a.png")}
        with mock.patch.object(service, "generate_image_from_references", return_value=fake_result()):
            res = self.post(form)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["data"]["image_base64"])

        res = self.post({"scene": scene_form()["scene"]})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()["error"]["code"], "SCENE_IMAGE_PHOTO_REQUIRED")

        form = {"scene": scene_form()["scene"], "photos": (io.BytesIO(png()), "a.png")}
        with mock.patch.object(service, "generate_image_from_references", side_effect=AIConfigError()):
            res = self.post(form)
        self.assertEqual(res.status_code, 503)

    def test_panel_has_image_controls(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn("data-ps-image-start disabled", html)
        self.assertIn("data-ps-image-info=", html)


class PdfSceneImageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import create_app
        cls.client = create_app().test_client()

    def post(self, images):
        data = MultiDict([("storyboard", json.dumps(storyboard())), ("edition", "pt")])
        for name, content in images:
            data.add("scene_images", (io.BytesIO(content), name))
        return self.client.post("/api/promotion-studio/pdf", data=data, content_type="multipart/form-data")

    def test_images_embedded_on_matching_pages(self):
        res = self.post([("scene_image_1.png", png(150, 100)), ("scene_image_3.png", png(150, 100))])
        self.assertEqual(res.status_code, 200)
        reader = PdfReader(io.BytesIO(res.data))
        # 쪽마다 공통 머리의 FIONEX 로고 1개가 있으므로 그보다 많으면 장면 이미지가 있는 쪽
        self.assertEqual([len(reader.pages[i].images) > 1 for i in (1, 2, 3)], [True, False, True])
        self.assertIn("Imagem gerada por IA", reader.pages[1].extract_text())
        self.assertIn("Imagem não gerada", reader.pages[2].extract_text())

    def test_invalid_scene_images_rejected(self):
        for images in ([("scene_image_9.png", png())], [("photo.png", png())], [("scene_image_1.png", b"GIF89a....")],
                       [("scene_image_1.png", png()), ("scene_image_1.png", png())]):
            res = self.post(images)
            self.assertEqual(res.status_code, 400, images[0][0])
            self.assertEqual(res.get_json()["error"]["code"], "PDF_INVALID_SCENE_IMAGE")


class PdfPhotoFallbackTest(unittest.TestCase):
    """PDF 다운로드 때 '첨부 사진 그대로 넣기'와 AI 이미지 실패 장면 대체."""

    @classmethod
    def setUpClass(cls):
        from app import create_app
        cls.client = create_app().test_client()

    def post(self, use_photos="1", photos=(), scene_images=()):
        data = MultiDict([("storyboard", json.dumps(storyboard())), ("edition", "bilingual"), ("use_photos", use_photos)])
        for name, content in photos:
            data.add("photos", (io.BytesIO(content), name))
        for name, content in scene_images:
            data.add("scene_images", (io.BytesIO(content), name))
        return self.client.post("/api/promotion-studio/pdf", data=data, content_type="multipart/form-data")

    def test_photos_fill_every_scene(self):
        res = self.post(photos=[("a.png", png(80, 60)), ("b.jpg", self.jpeg())])
        self.assertEqual(res.status_code, 200)
        reader = PdfReader(io.BytesIO(res.data))
        self.assertTrue(all(len(reader.pages[i].images) > 1 for i in (1, 2, 3)))  # 공통 머리 로고 1개 + 사진
        self.assertIn("첨부한 제품 사진(AI 생성 아님)", reader.pages[1].extract_text())
        self.assertNotIn("이미지 미생성", "".join(p.extract_text() for p in reader.pages))

    def test_ai_images_first_then_photos(self):
        res = self.post(photos=[("a.png", png())], scene_images=[("scene_image_2.png", png(150, 100))])
        reader = PdfReader(io.BytesIO(res.data))
        self.assertIn("첨부한 제품 사진", reader.pages[1].extract_text())
        self.assertIn("AI 생성 이미지", reader.pages[2].extract_text())
        self.assertIn("첨부한 제품 사진", reader.pages[3].extract_text())

    def test_use_photos_requires_photo_and_off_by_default(self):
        res = self.post(photos=[])
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()["error"]["code"], "PDF_INVALID_PHOTO")
        res = self.post(use_photos="0", photos=[("a.png", png())])
        self.assertIn("이미지 미생성", PdfReader(io.BytesIO(res.data)).pages[1].extract_text())

    @staticmethod
    def jpeg():
        buf = io.BytesIO()
        Image.new("RGB", (60, 80), (200, 120, 0)).save(buf, format="JPEG")
        return buf.getvalue()


if __name__ == "__main__":
    unittest.main()
