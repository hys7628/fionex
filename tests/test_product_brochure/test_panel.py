"""제품소개서 첫 화면(PDF 선택 + 결과 확인·수정) 렌더링·정적 규칙 검사.

브라우저 동작(파일 선택, 탭 이동, 확인 대화상자)은 검사하지 않습니다.
실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_product_brochure -v
"""
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402

FEATURE_DIR = ROOT / "features" / "product_brochure"
JS = (FEATURE_DIR / "static" / "product_brochure.js").read_text(encoding="utf-8")
CSS = (FEATURE_DIR / "static" / "product_brochure.css").read_text(encoding="utf-8")


class PanelParser(HTMLParser):
    """data-feature-panel="product_brochure" 영역의 요소와 텍스트를 모읍니다."""

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.elements = []
        self.text = []
        self.panels = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "data-feature-panel" in attrs:
            self.panels.append(attrs["data-feature-panel"])
        if self.depth == 0 and attrs.get("data-feature-panel") == "product_brochure":
            self.depth = 1
            return
        if self.depth:
            self.elements.append((tag, attrs))
            if tag not in ("input", "br", "img", "meta", "link"):
                self.depth += 1

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.text.append(data)


class PanelRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        response = create_app().test_client().get("/")
        cls.status = response.status_code
        cls.parser = PanelParser()
        cls.parser.feed(response.get_data(as_text=True))
        cls.text = " ".join(" ".join(cls.parser.text).split())

    def find(self, tag, **attrs):
        return [a for t, a in self.parser.elements
                if t == tag and all(a.get(k.replace("_", "-")) == v for k, v in attrs.items())]

    def test_home_renders_with_all_panels(self):
        self.assertEqual(self.status, 200)
        self.assertEqual(self.parser.panels,
                         ["home", "market_analysis", "product_brochure", "green_claim", "promotion_studio"])

    def test_single_pdf_input(self):
        files = self.find("input", type="file")
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["id"], "product_brochure-file")
        self.assertNotIn("multiple", files[0])
        self.assertIn(".pdf", files[0]["accept"])
        self.assertIn("스캔 PDF도 향후 분석 대상", self.text)
        self.assertIn("용량·페이지 상한은 아직 정하지 않았습니다", self.text)

    def test_analyze_disabled_with_pending_notice(self):
        submit = self.find("button", type="submit")
        self.assertEqual(len(submit), 1)
        self.assertIn("disabled", submit[0])
        self.assertIn("PDF 분석 연결 준비 중", self.text)

    def test_example_button_is_plain_button(self):
        btn = [a for t, a in self.parser.elements if t == "button" and "data-load-example" in a]
        self.assertEqual(len(btn), 1)
        self.assertEqual(btn[0]["type"], "button")
        self.assertNotIn("disabled", btn[0])

    def test_review_hidden_until_example_and_marked(self):
        review = [a for t, a in self.parser.elements if "data-review" in a]
        self.assertEqual(len(review), 1)
        self.assertIn("hidden", review[0])
        self.assertIn("개발용 예시입니다. 업로드한 PDF의 분석 결과가 아닙니다.", self.text)
        sections = [a for t, a in self.parser.elements if t == "section" and "data-work-ignore" in a]
        self.assertEqual(len(sections), 1)

    def test_catalog_and_download_disabled(self):
        for label in ("카탈로그 생성", "PDF 다운로드"):
            self.assertIn(label, self.text)
        disabled = [a for t, a in self.parser.elements if t == "button" and "disabled" in a]
        self.assertEqual(len(disabled), 3)  # PDF 분석, 카탈로그 생성, PDF 다운로드

    def test_out_of_scope_inputs_absent(self):
        self.assertEqual(len(self.find("textarea")), 0)  # 이전 예시 입력(요청 사항) 제거
        self.assertNotIn("바이어", self.text)


class StaticRuleTests(unittest.TestCase):
    def test_no_network_or_browser_storage(self):
        for pattern in (r"\bfetch\s*\(", r"XMLHttpRequest", r"sendBeacon", r"localStorage", r"sessionStorage",
                        r"indexedDB", r"FileReader", r"\.arrayBuffer\s*\(", r"\.text\s*\("):
            self.assertIsNone(re.search(pattern, JS), pattern)

    def test_no_html_injection_sinks(self):
        for pattern in (r"innerHTML", r"outerHTML", r"insertAdjacentHTML", r"document\.write"):
            self.assertIsNone(re.search(pattern, JS), pattern)

    def test_example_not_marked_as_result(self):
        self.assertNotIn("setResult", JS)
        self.assertNotIn("downloadBlob", JS)
        self.assertIn("setDraft", JS)

    def test_example_values_and_virtual_flags(self):
        for text in ('"리젠 T2T"', '"폐의류를 재활용하는 폴리에스터 섬유"', '"500 kg"', '"1 kg"', '"30일"'):
            self.assertIn(text, JS)
        for key in ("moq", "sample", "lead_time"):
            self.assertRegex(JS, r'key: "%s".*provided: true, virtual: true' % key)
        for key in ("yarn_spec", "carbon_reduction", "certification"):
            self.assertRegex(JS, r'key: "%s".*value: "", provided: false' % key)

    def test_css_scoped_to_feature(self):
        body = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
        selectors = [s.strip() for block in re.findall(r"([^{}]+)\{", body) for s in block.split(",")]
        self.assertTrue(selectors)
        for selector in selectors:
            self.assertTrue(selector.startswith(".feature-product_brochure "), selector)


if __name__ == "__main__":
    unittest.main()
