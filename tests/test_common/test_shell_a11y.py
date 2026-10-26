"""공통 shell·탭 화면의 접근성 구조(HTML) 확인. 브라우저 동작(초점 이동·낭독)은 검증하지 않습니다.

실제 키보드·초점 흐름은 브라우저로 확인합니다(docs/worklogs 검증 기록). 여기서는 회귀로 빠지기 쉬운 구조만 봅니다:
skip link·main·nav, 프로그램 초점 대상(tabindex=-1), 큰 결과 영역에 aria-live 없음, 짧은 상태 문장, 공통 helper 공개 여부.
실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_common -v
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402


def tag(html, marker):
    """marker(속성 문자열)가 들어 있는 첫 시작 태그 전체를 돌려줍니다."""
    match = re.search(r"<[a-z0-9]+[^>]*" + re.escape(marker) + r"[^>]*>", html)
    return match.group(0) if match else ""


class ShellA11yTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = create_app().test_client().get("/").get_data(as_text=True)

    def test_skip_link_main_and_nav(self):
        self.assertIn('<a class="skip-link" href="#main-content" data-skip-link>', self.html)
        self.assertEqual(self.html.count("<main "), 1)
        self.assertIn('id="main-content" tabindex="-1"', tag(self.html, 'id="main-content"'))
        self.assertIn('aria-label="주 메뉴"', self.html)

    def test_official_logo_in_sidebar_and_topbar(self):
        logos = re.findall(r'<img class="brand-logo"[^>]*>', self.html)
        self.assertEqual(len(logos), 2)  # 사이드바·작은 화면 상단바
        for img in logos:
            self.assertIn('src="/static/assets/fionex_logo.png"', img)
            self.assertIn('alt="FIONEX"', img)
            self.assertIn('width="2172" height="724"', img)  # 원본 비율(3:1) 자리 확보
        self.assertNotIn("brand-mark", self.html)
        self.assertTrue((ROOT / "static" / "assets" / "fionex_logo.png").is_file())

    def test_each_tab_has_one_h1_focus_target(self):
        for feature in ("home", "market_analysis", "product_brochure", "green_claim", "promotion_studio"):
            h1 = tag(self.html, 'id="title-%s"' % feature)
            self.assertTrue(h1.startswith("<h1"), feature)
            self.assertIn('tabindex="-1"', h1, feature)

    def test_market_result_focus_target_and_no_large_live_region(self):
        self.assertIn('tabindex="-1"', tag(self.html, 'id="market_analysis-result-title"'))
        self.assertIn('tabindex="-1"', tag(self.html, 'id="market_analysis-buyers-title"'))
        # 큰 결과·바이어 목록 전체를 낭독하지 않음. 완료는 짧은 status 문장으로
        self.assertNotIn("aria-live", tag(self.html, "data-ma-result"))
        self.assertNotIn("aria-live", tag(self.html, "data-ma-buyers"))
        self.assertIn('role="status"', tag(self.html, "data-ma-status"))

    def test_green_claim_results_title_focus_target(self):
        self.assertIn('tabindex="-1"', tag(self.html, 'id="green_claim-results-title"'))

    def test_unavailable_buttons_describe_pending(self):
        for feature in ("product_brochure", "promotion_studio"):
            buttons = re.findall(r'<button[^>]*aria-describedby="%s-pending"[^>]*>' % feature, self.html)
            self.assertEqual(len(buttons), 2, feature)
            self.assertTrue(all("disabled" in b for b in buttons), feature)

    def test_shell_exposes_focus_helpers(self):
        js = (ROOT / "static" / "js" / "app_shell.js").read_text(encoding="utf-8")
        self.assertIn("ui: { setButtonBusy: setButtonBusy, focusResult: focusResult }", js)
        self.assertIn("prefers-reduced-motion: reduce", js)


if __name__ == "__main__":
    unittest.main()
