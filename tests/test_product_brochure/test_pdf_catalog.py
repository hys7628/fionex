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


def _regions(page):
    """쪽별 글자 영역(CSS px: 왼쪽, 위, 오른쪽, 아래). 기준선이 위·아래 사이이고 가로가 좌우 안에 있어야 함."""
    pc = pdf_catalog
    right = pc.PAD + pc.CONTENT_W
    footer = (pc.PAD, pc.CONTENT_BOTTOM, right, pc.PAGE_H - pc.FOOTER_BOTTOM)
    if page == 1:
        return [(pc.PAD, pc.PAD, pc.PAD + pc.COVER_TEXT_W, pc.COVER_TEXT_BOTTOM),
                (pc.PAD, pc.COVER_FIGURE_H, right, pc.CONTENT_BOTTOM), footer]
    if page == 2:
        return [(pc.PAD, pc.PAD, right, pc.CONTENT_BOTTOM), footer]
    if page == 3:
        return [(24, pc.DETAIL_FIGURE_H, 24 + 300, pc.CONTENT_BOTTOM),
                (pc.DETAIL_TEXT_X, pc.PAD, right, pc.CONTENT_BOTTOM), footer]
    col_w = (pc.CONTENT_W - pc.TERM_GAP * 2) / 3
    cards = [(pc.PAD + n * (col_w + pc.TERM_GAP) + pc.TERM_PAD_X, 170,
              pc.PAD + n * (col_w + pc.TERM_GAP) + col_w - pc.TERM_PAD_X, pc.CONTENT_BOTTOM) for n in range(3)]
    closing_x = pc.PAD + (pc.CONTENT_W - pc.GAP) * 6 / 11 + pc.GAP
    return [(pc.PAD, pc.PAD, right, 170),              # 머리말·제목
            (pc.PAD + 3 + 24, 170, right - 24, pc.CONTENT_BOTTOM)] + cards + [  # 빈 상태 상자·카드
           (closing_x, 170, right, pc.CONTENT_BOTTOM), footer]


class GeometryTests(unittest.TestCase):
    """내용 스트림에서 실제로 그려진 글자 줄의 가로 범위를 계산해(pdf_geometry) 쪽별 영역과 대조합니다.
    2026-10-26 후속 시각 검증(외부 전달)에서 발견된 가로 넘침의 회귀 테스트: 머리말 자간(Tc)이 같은 쪽 본문에 남아
    측정보다 넓게 그려졌음. 이 검사는 수정 전 코드에서 2쪽 최대 644~666pt(쪽 폭 595pt)로 실패했습니다."""

    def assertInsideRegions(self, data):
        import pdf_geometry
        pc = pdf_catalog
        runs = pdf_geometry.text_runs(build_pdf(data))
        self.assertTrue(runs)
        for page, x0, x1, y, chars, _size in runs:
            left, right, base = x0 / pc.PX, x1 / pc.PX, pc.PAGE_H - y / pc.PX
            ok = any(l - 0.5 <= left and right <= r + 0.5 and t <= base <= b + 0.5 for l, t, r, b in _regions(page))
            self.assertTrue(ok, f"{page}쪽 글자 줄이 영역 밖: x {left:.1f}~{right:.1f}px, 기준선 {base:.1f}px, {chars}자")

    def test_text_stays_inside_regions(self):
        for case in ("base", "edited", "empty_info", "virtual_all", "long_max", "max_paragraphs", "wide_words"):
            with self.subTest(case=case):
                self.assertInsideRegions(getattr(pdf_fixtures, case)())

    def test_kicker_spacing_does_not_leak(self):
        """머리말의 글자 간격은 q/Q 안에만 있고, 그 뒤 본문 줄의 실제 폭은 글꼴 측정 폭과 같아야 함."""
        import pdf_geometry
        from reportlab.pdfbase.pdfmetrics import stringWidth
        pdf = build_pdf(pdf_fixtures.base())
        text = pdf_fixtures.base()["intro"]["paragraphs"][0]["text"]
        runs = [r for r in pdf_geometry.text_runs(pdf) if r[0] == 2]
        size = pdf_catalog.FONT_PX["lg"] * pdf_catalog.PX
        body = [r for r in runs if abs(r[5] - size) < 0.01]  # 2쪽 본문 크기(lg) 줄만, 위에서부터
        body.sort(key=lambda r: -r[3])
        self.assertGreaterEqual(len(body), 2)
        consumed = 0
        for line in body:  # 줄마다 실제 그려진 폭 = 같은 글자의 글꼴 측정 폭(자간 누적 없음)
            chunk = text[consumed:consumed + line[4]]
            consumed += line[4] + 1  # 줄바꿈 자리의 공백
            expected = stringWidth(chunk, pdf_catalog.FONT_NAMES["regular"], size)
            self.assertAlmostEqual(line[2] - line[1], expected, delta=0.5, msg=chunk)
        stream = PdfReader(io.BytesIO(pdf)).pages[1].get_contents().get_data().decode("latin-1")
        depth, tc_outside = 0, []
        for token_line in stream.split("\n"):
            for part in token_line.split(" Tc")[:-1]:
                if depth == 0 and float(part.split()[-1]) != 0:
                    tc_outside.append(part.split()[-1])
            depth += token_line.split().count("q") - token_line.split().count("Q")
        self.assertEqual(tc_outside, [])

    def test_wide_words_wrap_without_loss(self):
        d = pdf_fixtures.wide_words()
        joined = "".join(flat(t).replace(" ", "") for t in pages_text(build_pdf(d)))
        for value in (d["cover"]["tagline"]["text"], d["details"]["items"][0]["value"], d["supply"]["items"][0]["value"]):
            self.assertIn(value.replace(" ", ""), joined)  # 줄바꿈만 생기고 글자는 빠지지 않음


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
