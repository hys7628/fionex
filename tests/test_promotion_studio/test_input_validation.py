"""홍보 스튜디오 입력 검증(service.validate_input)과 패널 렌더링 테스트. 외부 API를 호출하지 않습니다.

실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_promotion_studio -v

파일은 테스트 안에서 만든 가상 bytes이며 실제 사용자 자료를 쓰지 않습니다.
"""
import io
import sys
import unittest
from pathlib import Path

from werkzeug.datastructures import FileStorage, MultiDict

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from features.promotion_studio import service  # noqa: E402
from features.promotion_studio.service import LIMITS, MB  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 24
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 16


def valid_form(**overrides):
    data = {
        "audience": "buyer",
        "description": "리젠 T2T 가상 테스트 설명",
        "purposes": ["product_intro"],
        "cta": "",
        "tone": "professional",
        "duration": "30",
        "scene_count": "6",
        "aspect_ratio": "16:9",
        "image_style": "photo",
        "max_wait_seconds": "180",
    }
    data.update(overrides)
    form = MultiDict()
    for key, value in data.items():
        for v in value if isinstance(value, list) else [value]:
            form.add(key, v)
    return form


def file(name, content=b"x"):
    return FileStorage(stream=io.BytesIO(content), filename=name)


class SizedStream(io.RawIOBase):
    """실제 메모리를 쓰지 않고 지정 크기처럼 동작하는 스트림(용량 경계 검사용)."""

    def __init__(self, size, head=b"x"):
        self._size = size
        self._head = head
        self._pos = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self._pos

    def seek(self, offset, whence=io.SEEK_SET):
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self._pos, io.SEEK_END: self._size}[whence]
        self._pos = base + offset
        return self._pos

    def read(self, n=-1):
        chunk = self._head[self._pos:self._pos + n] if n >= 0 else self._head[self._pos:]
        self._pos += len(chunk)
        return chunk


def sized_file(name, size, head=b"x"):
    return FileStorage(stream=SizedStream(size, head), filename=name)


def files(**fields):
    md = MultiDict()
    for key, items in fields.items():
        for item in items:
            md.add(key, item)
    return md


def fields_of(errors):
    return [e["field"] for e in errors]


class RequiredFieldsTest(unittest.TestCase):
    def test_valid_minimal_input(self):
        cleaned, errors = service.validate_input(valid_form(), files())
        self.assertEqual(errors, [])
        self.assertEqual(cleaned["duration"], 30)
        self.assertEqual(cleaned["scene_count"], 6)
        self.assertEqual(cleaned["cta"], "")
        self.assertIsNone(cleaned["logo"])
        self.assertIsNone(cleaned["logo_scope"])

    def test_missing_required_choices(self):
        form = valid_form()
        for key in ("audience", "description", "purposes", "tone", "duration",
                    "scene_count", "aspect_ratio", "image_style", "max_wait_seconds"):
            form.poplist(key)
        _, errors = service.validate_input(form, files())
        self.assertEqual(
            set(fields_of(errors)),
            {"audience", "description", "purposes", "tone", "duration",
             "scene_count", "aspect_ratio", "image_style", "max_wait_seconds"})

    def test_whitespace_description_is_missing(self):
        _, errors = service.validate_input(valid_form(description="   \n "), files())
        self.assertEqual(fields_of(errors), ["description"])

    def test_invalid_choice_values(self):
        form = valid_form(audience="admin", tone="loud", aspect_ratio="21:9", image_style="x", duration="45")
        _, errors = service.validate_input(form, files())
        self.assertEqual(set(fields_of(errors)), {"audience", "tone", "aspect_ratio", "image_style", "duration"})


class LengthLimitTest(unittest.TestCase):
    def test_description_boundary(self):
        n = LIMITS["description_max_chars"]
        self.assertEqual(service.validate_input(valid_form(description="가" * n), files())[1], [])
        _, errors = service.validate_input(valid_form(description="가" * (n + 1)), files())
        self.assertEqual(fields_of(errors), ["description"])

    def test_cta_boundary(self):
        n = LIMITS["cta_max_chars"]
        self.assertEqual(service.validate_input(valid_form(cta="a" * n), files())[1], [])
        self.assertEqual(fields_of(service.validate_input(valid_form(cta="a" * (n + 1)), files())[1]), ["cta"])

    def test_other_text_required_and_limited(self):
        n = LIMITS["other_max_chars"]
        form = valid_form(purposes=["other"], tone="other", image_style="other")
        _, errors = service.validate_input(form, files())
        self.assertEqual(set(fields_of(errors)), {"purpose_other", "tone_other", "image_style_other"})
        form = valid_form(purposes=["other"], purpose_other="b" * n, tone="other", tone_other="c" * (n + 1),
                          image_style="other", image_style_other="수채화")
        cleaned, errors = service.validate_input(form, files())
        self.assertEqual(fields_of(errors), ["tone_other"])
        self.assertEqual(cleaned["image_style_other"], "수채화")

    def test_other_text_ignored_when_not_selected(self):
        cleaned, errors = service.validate_input(valid_form(tone_other="무시"), files())
        self.assertEqual(errors, [])
        self.assertEqual(cleaned["tone_other"], "")


class ChoiceRangeTest(unittest.TestCase):
    def test_purpose_count(self):
        self.assertEqual(service.validate_input(valid_form(purposes=["product_intro", "eco_value"]), files())[1], [])
        _, errors = service.validate_input(
            valid_form(purposes=["product_intro", "eco_value", "partnership"]), files())
        self.assertEqual(fields_of(errors), ["purposes"])

    def test_duplicate_purpose_counted_once(self):
        cleaned, errors = service.validate_input(valid_form(purposes=["eco_value", "eco_value"]), files())
        self.assertEqual(errors, [])
        self.assertEqual(cleaned["purposes"], ["eco_value"])

    def test_scene_count_boundaries(self):
        for value, ok in (("2", False), ("3", True), ("15", True), ("16", False), ("6.5", False), ("", False)):
            with self.subTest(value=value):
                errors = service.validate_input(valid_form(scene_count=value), files())[1]
                self.assertEqual(errors == [], ok)

    def test_all_durations(self):
        for value in ("15", "30", "60", "90"):
            self.assertEqual(service.validate_input(valid_form(duration=value), files())[1], [])

    def test_wait_boundaries(self):
        lo, hi = LIMITS["wait_min_seconds"], LIMITS["wait_max_seconds"]
        for value, ok in ((lo - 1, False), (lo, True), (hi, True), (hi + 1, False), ("12.5", False), ("abc", False)):
            with self.subTest(value=value):
                errors = service.validate_input(valid_form(max_wait_seconds=str(value)), files())[1]
                self.assertEqual(errors == [], ok)


class FileTest(unittest.TestCase):
    def test_all_document_extensions(self):
        docs = [file(f"a{e}") for e in service.DOC_EXTENSIONS[:3]]
        self.assertEqual(service.validate_input(valid_form(), files(documents=docs))[1], [])
        docs = [file(f"b{e.upper()}") for e in service.DOC_EXTENSIONS[3:]]
        self.assertEqual(service.validate_input(valid_form(), files(documents=docs))[1], [])

    def test_document_count_and_type(self):
        docs = [file("a.pdf"), file("b.pdf"), file("c.pdf"), file("d.pdf")]
        self.assertEqual(fields_of(service.validate_input(valid_form(), files(documents=docs))[1]), ["documents"])
        _, errors = service.validate_input(valid_form(), files(documents=[file("a.doc")]))
        self.assertEqual(fields_of(errors), ["documents"])

    def test_empty_file_rejected(self):
        _, errors = service.validate_input(valid_form(), files(documents=[file("a.txt", b"")]))
        self.assertIn("빈 파일", errors[0]["message"])

    def test_document_size_boundaries(self):
        limit = LIMITS["doc_max_file_bytes"]
        ok = [sized_file("a.pdf", limit)]
        self.assertEqual(service.validate_input(valid_form(), files(documents=ok))[1], [])
        over = [sized_file("a.pdf", limit + 1)]
        self.assertEqual(fields_of(service.validate_input(valid_form(), files(documents=over))[1]), ["documents"])

    def test_document_total(self):
        limit = LIMITS["doc_max_file_bytes"]
        docs = [sized_file(f"{i}.pdf", limit) for i in range(3)]  # 합계 60MB = 상한
        self.assertEqual(service.validate_input(valid_form(), files(documents=docs))[1], [])

    def test_image_types_and_signature(self):
        photos = [file("a.png", PNG), file("b.jpg", JPG), file("c.jpeg", JPG), file("d.webp", WEBP)]
        self.assertEqual(service.validate_input(valid_form(), files(photos=photos))[1], [])
        _, errors = service.validate_input(valid_form(), files(photos=[file("fake.png", JPG)]))
        self.assertIn("내용이 맞지 않습니다", errors[0]["message"])
        _, errors = service.validate_input(valid_form(), files(photos=[file("a.gif", b"GIF89a")]))
        self.assertEqual(fields_of(errors), ["photos"])

    def test_photo_count_and_size(self):
        self.assertEqual(service.validate_input(valid_form(), files(photos=[file(f"{i}.png", PNG) for i in range(5)]))[1], [])
        _, errors = service.validate_input(valid_form(), files(photos=[file(f"{i}.png", PNG) for i in range(6)]))
        self.assertEqual(fields_of(errors), ["photos"])
        big = sized_file("big.png", LIMITS["image_max_file_bytes"] + 1, PNG)
        self.assertEqual(fields_of(service.validate_input(valid_form(), files(photos=[big]))[1]), ["photos"])

    def test_images_total_with_logo(self):
        each = LIMITS["image_max_file_bytes"]
        photos = [sized_file(f"{i}.png", each, PNG) for i in range(5)]
        logo = [sized_file("logo.png", each, PNG)]
        _, errors = service.validate_input(valid_form(logo_scope="pdf_only"), files(photos=photos, logo=logo))
        self.assertEqual(errors, [])  # 5×10MB + 10MB = 60MB 상한과 같음

    def test_logo_requires_scope(self):
        logo = [file("logo.png", PNG)]
        _, errors = service.validate_input(valid_form(), files(logo=logo))
        self.assertEqual(fields_of(errors), ["logo_scope"])
        cleaned, errors = service.validate_input(valid_form(logo_scope="image_and_pdf"), files(logo=logo))
        self.assertEqual(errors, [])
        self.assertEqual(cleaned["logo_scope"], "image_and_pdf")
        self.assertEqual(cleaned["logo"]["filename"], "logo.png")

    def test_logo_scope_ignored_without_logo(self):
        cleaned, errors = service.validate_input(valid_form(logo_scope="pdf_only"), files())
        self.assertEqual(errors, [])
        self.assertIsNone(cleaned["logo_scope"])

    def test_two_logos_rejected(self):
        _, errors = service.validate_input(
            valid_form(logo_scope="pdf_only"), files(logo=[file("a.png", PNG), file("b.png", PNG)]))
        self.assertEqual(fields_of(errors), ["logo"])

    def test_empty_file_field_ignored(self):
        # 파일을 고르지 않은 input도 빈 이름의 FileStorage로 전송됩니다.
        _, errors = service.validate_input(valid_form(), files(documents=[FileStorage(stream=io.BytesIO(b""), filename="")]))
        self.assertEqual(errors, [])

    def test_error_message_has_no_content(self):
        _, errors = service.validate_input(valid_form(), files(documents=[file("a.exe", b"SECRET-CONTENT")]))
        self.assertNotIn("SECRET", errors[0]["message"])


class PanelRenderTest(unittest.TestCase):
    """패널이 service의 제한값·기본값으로 렌더링되는지 확인합니다."""

    @classmethod
    def setUpClass(cls):
        from app import create_app
        cls.html = create_app().test_client().get("/").get_data(as_text=True)

    def test_limits_rendered(self):
        self.assertIn(f'maxlength="{LIMITS["description_max_chars"]}"', self.html)
        self.assertIn(f'maxlength="{LIMITS["cta_max_chars"]}"', self.html)
        self.assertIn("data-ps-limits=", self.html)
        self.assertIn('accept=".pdf,.docx,.pptx,.hwp,.xlsx,.txt"', self.html)

    def test_defaults_rendered(self):
        self.assertIn('value="30" checked', self.html)
        self.assertIn('<option value="6" selected>', self.html)
        self.assertIn('value="16:9" checked', self.html)
        self.assertIn('value="photo" checked', self.html)
        self.assertIn('value="180"', self.html)

    def test_generate_button_enabled(self):
        self.assertIn('<button type="submit" class="btn btn-primary" aria-describedby="promotion_studio-generate-hint" data-ps-submit>', self.html)


if __name__ == "__main__":
    unittest.main()
