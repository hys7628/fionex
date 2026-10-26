"""카탈로그 PDF 렌더러(pdf_catalog) 검증. 고정 가상 데이터(pdf_fixtures)만 쓰며 PDF를 디스크에 저장하지 않습니다.
텍스트 추출·페이지 수·자원 검사는 시각 검증을 대신하지 않습니다(육안 확인은 make_pdf_samples.py로 만든 PDF를 사람이 엶)."""
import io
import logging
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pypdf import PdfReader

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdf_fixtures  # noqa: E402

from features.product_brochure import generation, pdf_catalog  # noqa: E402
from features.product_brochure.pdf_catalog import (  # noqa: E402
    CatalogPdfAssetError, CatalogPdfGlyphError, CatalogPdfInputError, CatalogPdfOverflowError, build_pdf,
)

ROOT = Path(__file__).resolve().parents[2]


def pages_text(pdf):
    return [p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages]


def flat(text):
    return " ".join(text.split())


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = build_pdf(pdf_fixtures.base())

    def test_exactly_four_a4_portrait_pages(self):
        self.assertTrue(self.base.startswith(b"%PDF-"))
        reader = PdfReader(io.BytesIO(self.base))
        self.assertEqual(len(reader.pages), 4)
        for p in reader.pages:
            self.assertAlmostEqual(float(p.mediabox.width), 595.28, places=1)
            self.assertAlmostEqual(float(p.mediabox.height), 841.89, places=1)

    def test_selectable_text_and_fixed_notices_on_every_page(self):
        texts = [flat(t) for t in pages_text(self.base)]
        for n, t in enumerate(texts, start=1):
            self.assertIn(generation.NOTICE_UNOFFICIAL, t)
            self.assertIn(f"{n} / 4", t)
            self.assertIn("Imagem conceitual gerada por IA", t)  # AI 콘셉트 이미지 안내
        self.assertIn("Fibra Exemplo D1", texts[0])
        self.assertIn("Sobre o material", texts[1])
        self.assertIn("Detalhes do produto", texts[2])
        self.assertIn("Amostras e condições comerciais", texts[3])
        self.assertIn(pdf_catalog.CLOSING_BODY, texts[3])
        self.assertIn("Pedido mínimo (MOQ)", texts[3])  # 항목명은 서버 상수

    def test_images_and_fonts_are_fixed_embedded_assets(self):
        reader = PdfReader(io.BytesIO(self.base))
        refs, widths = set(), []
        for p in reader.pages:
            res = p["/Resources"]
            for xo in res["/XObject"].values():
                refs.add(xo.idnum)
                widths.append(int(xo.get_object()["/Width"]))
            fonts = {f.get_object()["/BaseFont"] for f in res["/Font"].values()}
            self.assertTrue(fonts)
            self.assertTrue(all("PBCatalogSans" in f or "AAAAAA" in f or "+" in f for f in fonts), fonts)
            self.assertFalse(any("Helvetica" in f for f in fonts))
        self.assertEqual(widths, [1024, 1448, 1448, 1024])  # 표지·소개·상세(크롭)·마무리(크롭)
        self.assertEqual(len(refs), 2)                      # 이미지 2개를 한 번씩만 포함
        self.assertLess(len(self.base), 3 * 1024 * 1024)

    def test_edited_values_are_used_literally_without_markup(self):
        texts = [flat(t) for t in pages_text(build_pdf(pdf_fixtures.edited()))]
        self.assertIn("Fio Ação & Têxtil <Demo>", texts[0])
        self.assertIn("& <marcação> não interpretada.", texts[0])
        self.assertIn("símbolos & < > \" '.", texts[1])
        self.assertIn("Segunda linha após quebra manual.", texts[1])
        self.assertIn("800 kg por pedido (editado)", texts[3])
        joined = " ".join(texts)
        for mock_text in ("regen T2T", "Fibra de poliéster feita a partir", "O regen T2T"):
            self.assertNotIn(mock_text, joined)  # 고정 시안 문구 미혼입
        self.assertIsNone(generation.HANGUL.search(joined))

    def test_markup_like_input_is_not_interpreted(self):
        d = pdf_fixtures.base()
        d["cover"]["tagline"]["text"] = '<b>negrito</b> <font color="red">x</font> <img src="file:///etc/passwd"/>'
        pdf = build_pdf(d)
        self.assertIn('<b>negrito</b> <font color="red">x</font>', flat(pages_text(pdf)[0]))
        self.assertEqual(len(PdfReader(io.BytesIO(pdf)).pages[0]["/Resources"]["/XObject"]), 1)

    def test_empty_details_and_supply_use_server_empty_messages(self):
        texts = [flat(t) for t in pages_text(build_pdf(pdf_fixtures.empty_info()))]
        self.assertIn(generation.EMPTY_DETAILS, texts[2])
        self.assertIn(generation.EMPTY_SUPPLY, texts[3])
        self.assertIn(pdf_catalog.CLOSING_BODY, texts[3])
        self.assertNotIn("Pedido mínimo", texts[3])
        self.assertNotIn(generation.NOTICE_FICTITIOUS, texts[3])

    def test_virtual_notices_follow_each_item(self):
        texts = [flat(t) for t in pages_text(build_pdf(pdf_fixtures.virtual_all()))]
        self.assertEqual(texts[0].count(generation.NOTICE_FICTITIOUS_CONTENT), 2)  # 표시명·소개 문구
        self.assertEqual(texts[1].count(generation.NOTICE_FICTITIOUS_CONTENT), 1)
        self.assertEqual(texts[2].count(generation.NOTICE_FICTITIOUS), 3)
        self.assertEqual(texts[3].count(generation.NOTICE_FICTITIOUS), 3)
        base = [flat(t) for t in pages_text(self.base)]
        self.assertNotIn(generation.NOTICE_FICTITIOUS_CONTENT, base[0] + base[1])
        self.assertEqual(base[2].count(generation.NOTICE_FICTITIOUS), 1)  # 가상 표시된 탄소 저감만

    def test_long_values_within_limits_fit(self):
        for case in ("long_max", "max_paragraphs"):
            with self.subTest(case=case):
                self.assertEqual(len(PdfReader(io.BytesIO(build_pdf(getattr(pdf_fixtures, case)()))).pages), 4)

    def test_short_value_with_wide_word_falls_back_to_long_style(self):
        d = pdf_fixtures.base()
        d["supply"]["items"][0]["value"] = "1.000.000.000 kg"  # 24자 이하지만 큰 글자로는 칸을 넘는 한 단어
        self.assertIn("1.000.000.000 kg", flat(pages_text(build_pdf(d))[3]))


class OverflowTests(unittest.TestCase):
    def assertOverflow(self, data, page):
        with self.assertRaises(CatalogPdfOverflowError) as ctx:
            build_pdf(data)
        self.assertEqual(ctx.exception.page, page)
        self.assertEqual(ctx.exception.http_status, 422)
        self.assertIn(f"{page}쪽", ctx.exception.message)

    def test_details_overflow_page3(self):
        self.assertOverflow(pdf_fixtures.overflow_details(), 3)

    def test_wide_title_word_overflow_page1(self):
        self.assertOverflow(pdf_fixtures.overflow_title(), 1)

    def test_page4_closing_space_check(self):
        # 상한(200자) 공급 조건 3개도 실제로는 마무리 영역이 남아 통과합니다(long_max). 검사 자체는 최소 높이를 올려 확인
        d = pdf_fixtures.long_max()
        build_pdf(d)
        with mock.patch.object(pdf_catalog, "CLOSING_MIN_H", 800):
            self.assertOverflow(d, 4)

    def test_overflow_message_has_no_user_text(self):
        d = pdf_fixtures.overflow_title()
        with self.assertRaises(CatalogPdfOverflowError) as ctx:
            build_pdf(d)
        self.assertNotIn(d["cover"]["product_name"]["text"], ctx.exception.message)


class InputValidationTests(unittest.TestCase):
    def assertInvalid(self, mutate, exc=CatalogPdfInputError):
        d = pdf_fixtures.base()
        mutate(d)
        with self.assertRaises(exc):
            pdf_catalog.parse_catalog(d)

    def test_limits_match_generation_and_edit(self):
        cases = [(("cover", "product_name"), 80), (("cover", "tagline"), 140)]
        for path, limit in cases:
            d = pdf_fixtures.base()
            d[path[0]][path[1]]["text"] = "a" * limit
            pdf_catalog.parse_catalog(d)
            d[path[0]][path[1]]["text"] = "a" * (limit + 1)
            with self.assertRaises(CatalogPdfInputError):
                pdf_catalog.parse_catalog(d)
        for section, limit in (("details", 300), ("supply", 200)):
            d = pdf_fixtures.base()
            d[section]["items"][0]["value"] = "a" * (limit + 1)
            with self.assertRaises(CatalogPdfInputError):
                pdf_catalog.parse_catalog(d)
        self.assertInvalid(lambda d: d["intro"]["paragraphs"][0].update(text="a" * 601))

    def test_text_rules(self):
        self.assertInvalid(lambda d: d["cover"]["tagline"].update(text="   "))
        self.assertInvalid(lambda d: d["cover"]["tagline"].update(text="리젠 fio"))
        self.assertInvalid(lambda d: d["cover"]["tagline"].update(text="ㅎ"))
        self.assertInvalid(lambda d: d["cover"]["tagline"].update(text="a\tb"))
        self.assertInvalid(lambda d: d["cover"]["product_name"].update(text="Nome\nquebrado"))
        d = pdf_fixtures.base()
        d["cover"]["tagline"]["text"] = "  Ação\nlinha 2  "
        self.assertEqual(pdf_catalog.parse_catalog(d)["tagline"]["text"], "Ação\nlinha 2")  # 앞뒤 공백만 정리

    def test_structure_rules(self):
        self.assertInvalid(lambda d: d["details"]["items"].append({"key": "moq", "value": "x", "virtual": False}))
        self.assertInvalid(lambda d: d["supply"]["items"].append(dict(d["supply"]["items"][0])))
        self.assertInvalid(lambda d: d["supply"]["items"][0].update(key="contact"))
        self.assertInvalid(lambda d: d["supply"]["items"][0].update(label="Rótulo livre"))  # 라벨 입력 불가
        self.assertInvalid(lambda d: d["cover"]["tagline"].update(virtual="false"))
        self.assertInvalid(lambda d: d["intro"].update(paragraphs=[]))
        self.assertInvalid(lambda d: d["intro"].update(paragraphs=[d["intro"]["paragraphs"][0]] * 3))
        self.assertInvalid(lambda d: d.update(language="ko"))
        for extra in ("html", "image_url", "font_path", "color", "notice"):
            self.assertInvalid(lambda d, k=extra: d.update({k: "x"}))
        with self.assertRaises(CatalogPdfInputError):
            pdf_catalog.parse_catalog([])

    def test_items_sorted_by_page_order_without_changes(self):
        d = pdf_fixtures.base()
        d["supply"]["items"].reverse()
        out = pdf_catalog.parse_catalog(d)
        self.assertEqual([i["key"] for i in out["supply"]], ["moq", "sample", "lead_time"])
        self.assertEqual([i["value"] for i in out["supply"]], ["500 kg", "1 kg", "30 dias"])

    def test_missing_glyph_fails(self):
        d = pdf_fixtures.base()
        d["cover"]["tagline"]["text"] = "Texto com emoji \U0001F600"
        with self.assertRaises(CatalogPdfGlyphError):
            build_pdf(d)


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def images_with(self, role, path):
        files = dict(pdf_catalog.IMAGE_FILES)
        files[role] = path
        return mock.patch.object(pdf_catalog, "IMAGE_FILES", files)

    def test_missing_image(self):
        with self.images_with("cover", self.dir / "none.png"), self.assertRaises(CatalogPdfAssetError):
            build_pdf(pdf_fixtures.base())

    def test_corrupt_image(self):
        bad = self.dir / "bad.png"
        data = pdf_catalog.IMAGE_FILES["material"].read_bytes()
        bad.write_bytes(data[:len(data) // 3])  # 잘린 PNG
        with self.images_with("material", bad), self.assertRaises(CatalogPdfAssetError):
            build_pdf(pdf_fixtures.base())

    def test_wrong_size_image(self):
        from PIL import Image
        other = self.dir / "other.png"
        Image.new("RGB", (10, 10)).save(other)
        with self.images_with("cover", other), self.assertRaises(CatalogPdfAssetError):
            build_pdf(pdf_fixtures.base())

    def test_missing_or_corrupt_font(self):
        bad = self.dir / "bad.ttf"
        bad.write_bytes(b"not a font")
        for path in (self.dir / "none.ttf", bad):
            with self.subTest(path=path.name), \
                    mock.patch.object(pdf_catalog, "FONT_FILES", {"regular": path, "bold": path}), \
                    mock.patch.object(pdf_catalog, "FONT_NAMES", {"regular": "PBTestBad", "bold": "PBTestBad-Bold"}), \
                    mock.patch.object(pdf_catalog, "_registered", {}), \
                    self.assertRaises(CatalogPdfAssetError):
                build_pdf(pdf_fixtures.base())

    def test_asset_problem_does_not_block_app_start(self):
        from app import create_app
        with self.images_with("cover", self.dir / "none.png"), \
                mock.patch.object(pdf_catalog, "FONT_FILES", {"regular": self.dir / "x.ttf", "bold": self.dir / "x.ttf"}):
            self.assertEqual(create_app().test_client().get("/").status_code, 200)

    def test_asset_paths_are_fixed_project_files(self):
        for path in list(pdf_catalog.IMAGE_FILES.values()) + list(pdf_catalog.FONT_FILES.values()):
            self.assertTrue(path.is_file(), path)
            self.assertIn(Path(__file__).resolve().parents[2] / "features" / "product_brochure", path.parents)
        self.assertTrue((pdf_catalog.FONT_DIR / "OFL.txt").is_file())


class IsolationTests(unittest.TestCase):
    def test_no_ai_network_or_logging(self):
        def forbid(*a, **k):
            raise AssertionError("PDF 생성 중 AI·네트워크 호출 금지")
        with mock.patch.object(generation, "generate_structured", forbid), \
                mock.patch.object(socket.socket, "connect", forbid), \
                self.assertNoLogs(level=logging.DEBUG):
            build_pdf(pdf_fixtures.edited())
            with self.assertRaises(CatalogPdfOverflowError):
                build_pdf(pdf_fixtures.overflow_details())

    def test_source_has_no_ai_disk_write_or_route(self):
        import ast
        tree = ast.parse((ROOT / "features" / "product_brochure" / "pdf_catalog.py").read_text(encoding="utf-8"))
        used = set()
        for node in ast.walk(tree):  # 주석·문서 문자열이 아닌 실제 import·이름·속성만
            if isinstance(node, ast.Import):
                used.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                used.add(node.module or "")
                used.update(a.name for a in node.names)
            elif isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                used.add(node.attr)
        joined = " ".join(used)
        for forbidden in ("ai_client", "generate_structured", "openai", "httpx", "requests", "urllib", "socket",
                          "logging", "logger", "write_bytes", "write_text", "tempfile", "pdf_utils", "inspect_pdf"):
            self.assertNotIn(forbidden, joined)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        self.assertNotIn("open", names)  # 내장 open(파일 쓰기) 없음. 이미지는 PIL Image.open으로 읽기만
        self.assertNotIn("pdf_catalog", (ROOT / "features" / "product_brochure" / "routes.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
