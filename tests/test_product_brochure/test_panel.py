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


class RenderedPanel(unittest.TestCase):
    """GET / 결과에서 제품소개서 패널을 파싱하는 공통 준비(테스트 없음)."""

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


class PanelRenderTests(RenderedPanel):

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
        self.assertIn("최대 10 MiB·20쪽", self.text)
        self.assertIn("스캔 PDF", self.text)
        self.assertIn("판독 품질은 아직 확인하지 않았습니다", self.text)

    def test_analyze_disabled_until_valid_file(self):
        # 이전: "항상 비활성". 현재: 처음에는 비활성이고 유효한 PDF를 선택해야 JS가 활성화(자동 분석 없음)
        submit = self.find("button", type="submit")
        self.assertEqual(len(submit), 1)
        self.assertIn("disabled", submit[0])
        self.assertIn("data-analyze", submit[0])
        self.assertIn("10 MiB 이하의 PDF를 선택하면 분석할 수 있습니다.", self.text)
        alerts = [a for t, a in self.parser.elements if "data-analyze-error" in a]
        self.assertEqual(len(alerts), 1)
        self.assertIn("hidden", alerts[0])

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
        self.assertIn("aria-busy", sections[0])

    def test_source_notices_are_separate(self):
        example = [a for t, a in self.parser.elements if "data-source-example" in a]
        analysis = [a for t, a in self.parser.elements if "data-source-analysis" in a]
        self.assertEqual((len(example), len(analysis)), (1, 1))
        self.assertIn("hidden", example[0])
        self.assertIn("hidden", analysis[0])
        self.assertIn("PDF 분석(AI 추출) 결과입니다. 사용자 확인 전에는 확정 정보가 아닙니다.", self.text)
        self.assertIn("원문 대조 미실시", self.text)
        self.assertIn("원문 대조·사실 검증·인증 완료를 뜻하지 않습니다", self.text)

    def test_catalog_and_download_disabled(self):
        for label in ("카탈로그 생성", "PDF 다운로드"):
            self.assertIn(label, self.text)
        disabled = [a for t, a in self.parser.elements if t == "button" and "disabled" in a]
        # 처음 화면: PDF 분석·카탈로그 생성(조건 충족 전)·PDF 다운로드(생성 결과 없음)·생성 결과 보기(결과 없음)·AI 원문 되돌리기(수정 없음)
        # ·AI 표지 배경 생성(적용 스냅샷 없음)·기본 배경으로 복원(적용 이미지 없음)
        self.assertEqual(len(disabled), 7)
        for marker in ("data-analyze", "data-generate", "data-pdf-download", "data-result-open", "data-result-edit-restore",
                       "data-cover-generate", "data-cover-restore"):
            self.assertTrue(any(marker in a for a in disabled), marker)
        generate = [a for t, a in self.parser.elements if t == "button" and "data-generate" in a]
        self.assertEqual(len(generate), 1)
        self.assertIn("disabled", generate[0])

    def test_out_of_scope_inputs_absent(self):
        self.assertEqual(len(self.find("textarea")), 0)  # 이전 예시 입력(요청 사항) 제거
        self.assertNotIn("바이어", self.text)


class CatalogPreviewTests(RenderedPanel):
    """디자인 시안: 고정 예시 4쪽, 시연·가상 안내, 기존 상태와 분리."""

    def test_entry_point_and_dialog(self):
        opener = [a for t, a in self.parser.elements if t == "button" and "data-catalog-open" in a]
        self.assertEqual(len(opener), 1)
        self.assertEqual(opener[0]["type"], "button")
        self.assertNotIn("disabled", opener[0])
        self.assertIn("디자인 시안 보기", self.text)
        dialogs = [a for t, a in self.parser.elements if t == "dialog"]
        self.assertEqual(len(dialogs), 2)              # 고정 시안 + 생성 결과(분리)
        self.assertIn("data-catalog-dialog", dialogs[0])
        self.assertIn("data-result-dialog", dialogs[1])
        for d in dialogs:
            self.assertNotIn("open", d)                # 자동으로 열리지 않음
            self.assertIn("data-work-ignore", d)
        result_open = [a for t, a in self.parser.elements if t == "button" and "data-result-open" in a]
        self.assertEqual(len(result_open), 1)
        self.assertIn("disabled", result_open[0])      # 생성 결과가 생기기 전에는 비활성

    def test_result_dialog_has_no_sample_data(self):
        # 생성 결과 미리보기에는 시안의 예시 문구·더미 공급 조건이 없고 데이터 칸(slot)만 있음
        html = create_app().test_client().get("/").get_data(as_text=True)
        start = html.index("data-result-dialog")
        result = html[start:html.index("</dialog>", start)]
        for sample in ("500 kg", "1 kg", "30 dias", "Fibra de poliéster feita", "O regen T2T é",
                       "Informações técnicas a confirmar.", "Condições fictícias para demonstração.", "regen T2T<"):
            self.assertNotIn(sample, result)
        for name in ("product_name", "tagline", "paragraphs", "details", "details-empty", "supply", "supply-empty"):
            self.assertEqual(result.count(f'data-slot="{name}"'), 1, name)
        self.assertEqual(result.count('data-slot="unofficial"'), 4)
        self.assertEqual(len(re.split(r"<article ", result)) - 1, 4)
        self.assertIn("번역·내용 검토가 필요한 초안", result)
        self.assertIn("Imagem conceitual gerada por IA — não representa o produto real.", result)

    @classmethod
    def rendered_pages(cls):
        html = create_app().test_client().get("/").get_data(as_text=True)
        dialog = html[html.index("<dialog"):html.index("</dialog>")]
        return dialog, re.split(r"<article ", dialog)[1:]

    def test_four_pages_with_disclaimer_page_number_and_ai_image_notice(self):
        _, pages = self.rendered_pages()
        self.assertEqual(len(pages), 4)
        for n, page in enumerate(pages, start=1):
            self.assertIn(f'data-page="{n}" lang="pt-BR"', page)
            self.assertIn("Material demonstrativo — não é um catálogo oficial.", page)
            self.assertIn(f"{n} / 4", page)
            imgs = re.findall(r"<img\b[^>]*>", page)
            self.assertTrue(imgs)  # 모든 쪽에 콘셉트 이미지
            self.assertIn("Imagem conceitual gerada por IA — não representa o produto real.", page)
            for tag in imgs:
                src = re.search(r'src="([^"]+)"', tag).group(1)
                self.assertRegex(src, r"^/features/product_brochure/static/images/catalog_(cover|material)_concept\.png$")
                self.assertIn("conceitual", re.search(r'alt="([^"]+)"', tag).group(1))
            self.assertIn("catalog-figure-fallback", page)  # 로딩 실패 대체 안내

    def test_images_served_as_png(self):
        client = create_app().test_client()
        for name in ("catalog_cover_concept.png", "catalog_material_concept.png"):
            response = client.get("/features/product_brochure/static/images/" + name)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "image/png")
            self.assertTrue(response.get_data().startswith(b"\x89PNG\r\n\x1a\n"))
            response.close()

    def test_supply_terms_fictitious_and_no_invented_or_production_text_in_pages(self):
        dialog, pages = self.rendered_pages()
        terms = re.findall(r'<li class="catalog-term" data-term="(\w+)">(.*?)</li>', pages[3], re.S)
        self.assertEqual([k for k, _ in terms], ["moq", "sample", "lead_time"])
        for _, body in terms:
            self.assertIn("Condições fictícias para demonstração.", body)
        self.assertIn("Informações técnicas a confirmar.", pages[2])
        self.assertIsNone(re.search(r"%|\bdtex\b|\b\d+\s*D\b|GRS|OEKO|ISO\s*\d", pages[2]))  # 규격·인증·탄소 수치 없음
        doc = "".join(pages)
        # 제작 안내·점선 자리표시자·연락처는 문서 페이지 밖(시안 제작 메모)에만
        for production in ("Texto de exemplo", "Área exibida", "catalog-placeholder", "Área de contato"):
            self.assertNotIn(production, doc)
        self.assertIn("시안 제작 메모", dialog)
        for forbidden in (r"https?://", r"@", r"\+55", r"Hyosung", r"효성"):
            self.assertIsNone(re.search(forbidden, doc), forbidden)  # 외부 이미지·연락처·회사 표기 없음

    def test_page4_samples_and_commercial_terms_in_both_dialogs(self):
        html = create_app().test_client().get("/").get_data(as_text=True)
        self.assertEqual(html.count("Amostras e condições comerciais"), 2)  # 시안·결과 모두
        self.assertNotIn("Condições de fornecimento</h3>", html)
        self.assertEqual(html.count("Entre em contato para consultar a disponibilidade de amostras e as condições comerciais."), 2)
        for promise in ("Disponível mediante solicitação", "grátis", "gratuit", "envio imediato", "Solicite amostras"):
            self.assertNotIn(promise, html)  # 제공 가능·무료·즉시 발송 약속 없음

    def test_result_edit_ui_uses_plain_inputs(self):
        html = create_app().test_client().get("/").get_data(as_text=True)
        start = html.index("data-result-dialog")
        result = html[start:html.index("</dialog>", start)]
        for marker in ("data-result-edit-open", "data-result-edit-apply", "data-result-edit-cancel",
                       "data-result-edit-restore", "data-result-edit-fields", "data-result-user-edits"):
            self.assertIn(marker, result)
        design = html[html.index("<dialog"):html.index("</dialog>")]
        self.assertNotIn("data-result-edit", design)  # 고정 시안은 편집 대상 아님
        self.assertNotIn("contenteditable", html)
        self.assertNotIn("contentEditable", JS)
        self.assertNotIn("execCommand", JS)

    def test_edit_code_makes_no_requests_and_keeps_input_state(self):
        start = JS.index("/* 생성 결과 문구 편집")
        block = JS[start:JS.index('resultOpenBtn.addEventListener("click"', start)]
        for forbidden in ("fetch(", "postRequest", "generator.run", "analyzer.run", "snapshot =", "displayName =",
                          "setResult", "Storage", "innerHTML"):
            self.assertNotIn(forbidden, block)

    def test_pdf_download_wiring(self):
        start = JS.index("/* ---------- 카탈로그 PDF 다운로드 ----------")
        block = JS[start:]
        self.assertEqual(JS.count("downloadBlob("), 1)                 # 다운로드 호출은 성공 경로 한 곳
        self.assertEqual(JS.count("fetch("), 3)                        # 기존 postRequest + PDF 전용 sendPdf + 표지 sendCover
        self.assertIn("Review.PDF_URL", block)
        self.assertIn("const PDF_TIMEOUT_MS = 30000;", JS)
        self.assertIn("buildPdfPayload(Review.cloneData(generation.current))", block)  # 클릭 시점 적용본 스냅샷
        # downloadBlob(→markDownloadRequested) 뒤 이 탭의 보호 대상을 다시 반영
        after = block[block.index("downloadBlob("):]
        self.assertLess(after.index("recheckInputs(FEATURE_ID)"), after.index("onFailure"))
        self.assertLess(after.index("syncWork()"), after.index("onFailure"))
        for forbidden in ("setResult(", "innerHTML", "Storage", "generator.run", "analyzer.run", "generation.original",
                          "editing.values", "setInterval"):
            self.assertNotIn(forbidden, block)
        self.assertNotIn("setResult(", JS)

    def test_pdf_stale_confirm_uses_live_inputs(self):
        # 사용자 보고(2026-10-26) 회귀: 검토 입력 수정 → 재적용 없이 다운로드 → 이전 결과 확인
        # 판정은 클릭 시점에 현재 입력 서명으로 계산(캐시 없음)하고 생성 결과 미리보기 경고와 같은 함수를 씀
        self.assertIn("needsConfirm: function () { return !!generation && Review.isResultStale(generation, generationContext()); }", JS)
        ctx = JS[JS.index("function generationContext()"):JS.index("function syncGenerate()")]
        self.assertIn("currentSignature: currentSignature()", ctx)
        self.assertIn("return fields ? Review.inputSignature(fields, displayName) : null;", JS)
        # 항목 값·확인·가상 표시와 표시명·표시명 확인 변경이 모두 changed()로 상태를 갱신
        field = JS[JS.index("  function renderField(field)"):JS.index("  function renderSourceNotice")]
        self.assertIn("if (Review.setValue(field, input.value)) changed();", field)
        self.assertEqual(field.count("changed();"), 3)
        dn = JS[JS.index('displayNameInput.addEventListener("input"'):JS.index("  function changed()")]
        self.assertEqual(dn.count("changed();"), 2)
        # 결과 카드 안내·결과 대화상자 경고·PDF 안내·PDF 확인 모두 같은 판정
        self.assertEqual(JS.count("Review.isResultStale(generation, generationContext())"), 4)
        self.assertNotIn("isResultStale", JS[JS.index('pdfBtn.addEventListener("click"'):])  # 클릭 처리에서 따로 판정하지 않음

    def test_cover_markup_and_wiring(self):
        html = create_app().test_client().get("/").get_data(as_text=True)
        start = html.index("data-cover>")
        section = html[start:html.index("</section>", start)]
        for text in ("API 비용", "실제 제품 사진이 아닌 AI 콘셉트 이미지", "미니멀", "프리미엄", "부드러운 소재감",
                     "AI 표지 배경 생성", "표지에 적용", "후보 버리기", "기본 배경으로 복원",
                     "Imagem conceitual gerada por IA — não representa o produto real."):
            self.assertIn(text, section)
        self.assertIn("data-work-ignore", section[:section.index("data-cover-generate")])  # 분위기 선택만으로 작업 상태 없음
        self.assertIn("data-cover-candidate hidden", section)
        self.assertIn('data-cover-error role="alert" hidden', section)
        self.assertEqual(section.count('type="radio"'), 3)
        block = JS[JS.index("/* ---------- AI 표지 배경 ----------"):]
        # 클릭 시점 적용 스냅샷 + 분위기 3필드만, 210초 대기, 자동 적용 없음(후보만), PDF 차단
        self.assertIn("Review.buildCoverPayload(snapshot, selectedCoverMood())", block)
        self.assertIn("const COVER_TIMEOUT_MS = 210000;", JS)
        self.assertIn("candidate: { url: URL.createObjectURL(data.blob)", block)
        self.assertIn("applied: cover.applied,", block[block.index("onSuccess"):block.index("onFailure")])
        self.assertIn("coverApplied: !!cover.applied", JS)
        self.assertIn('resultDialog.querySelector(".catalog-cover-figure img")', block)  # 결과 1쪽 표지만
        self.assertNotIn("data-catalog-dialog", block)                                  # 고정 시안 미변경
        self.assertIn("Review.coverUrlsToRevoke(cover, next).forEach(function (url) { URL.revokeObjectURL(url); });", JS)
        self.assertEqual(JS.count("URL.revokeObjectURL("), 1)          # 해제는 상태 교체 한 곳에서만(AppShell 제외)
        for forbidden in ("localStorage", "sessionStorage", "indexedDB", "innerHTML", "setInterval"):
            self.assertNotIn(forbidden, block)
        self.assertIn("!!cover.candidate || !!cover.applied", JS[JS.index("function syncWork()"):])  # 이탈 보호
        # 문구 재생성 성공 처리에서 표지 이미지를 지우지 않음
        gen = JS[JS.index("const generator = Review.createGenerator"):JS.index("generateBtn.addEventListener")]
        self.assertNotIn("cover", gen.replace("coverBusy", ""))

    def test_result_revision_invalidates_download_mark(self):
        # 생성 성공·편집 적용·원문 복원·AI 표지 적용·기본 배경 복원마다 결과 버전 증가 → 이전 다운로드 요청 표시를 새 내용에 쓰지 않음
        self.assertEqual(JS.count("resultRevision++"), 5)
        for handler in ("coverApplyBtn.addEventListener", "coverRestoreBtn.addEventListener"):
            seg = JS[JS.index(handler):JS.index("\n  });", JS.index(handler))]
            self.assertIn("resultRevision++", seg)
            self.assertIn("working()", seg)
        self.assertIn("downloadedRevision === resultRevision", JS)
        self.assertIn("data.revision !== resultRevision", JS)
        for handler in ("editApplyBtn.addEventListener", "editRestoreBtn.addEventListener"):
            seg = JS[JS.index(handler):JS.index("});", JS.index(handler))]
            self.assertIn("working()", seg)                            # PDF 요청 중 잠금
            self.assertIn("resultRevision++", seg)

    def test_pdf_controls_markup(self):
        html = create_app().test_client().get("/").get_data(as_text=True)
        start = html.index('data-pdf-download')
        button = html[html.rindex("<button", 0, start):html.index("</button>", start)]
        self.assertIn("disabled", button)
        self.assertIn('aria-describedby="product_brochure-pdf-status"', button)
        self.assertIn('data-pdf-status role="status"', html)
        self.assertIn('data-pdf-error role="alert" hidden', html)
        self.assertNotIn("product_brochure-next-pending", html)       # "준비 중" 안내 제거
        # 생성 결과의 3·4쪽 항목명은 템플릿이 아닌 JS 고정값(CATALOG_ITEM_LABELS)으로 채움. 시안의 4쪽 항목명은 그대로
        self.assertIn("Pedido mínimo (MOQ)", html[:html.index("data-result-dialog")])
        self.assertIn('data-slot="supply"', html[html.index("data-result-dialog"):])
        self.assertEqual(JS.count("Review.CATALOG_ITEM_LABELS[item.key]"), 2)  # 3쪽 dt·4쪽 항목명
        self.assertNotIn("item.label", JS[JS.index("function infoItem"):JS.index("function renderInfoPage")])

    def test_preview_code_does_not_touch_review_state(self):
        # 미리보기 공통 블록과 디자인 시안 블록(생성 결과 블록 전까지)
        start = JS.index("/* ---------- 카탈로그 미리보기 공통")
        end = JS.index("/* ---------- 카탈로그 생성 결과 미리보기 ---------- */")
        block = JS[start:end]
        for forbidden in ("fields", "setDraft", "setResult", "downloadBlob", "fetch(", "Storage", "generation",
                          "clearReview", "showFields", "analyzer", "generator", "recheckInputs", "snapshot"):
            self.assertNotIn(forbidden, block)


class StaticRuleTests(unittest.TestCase):
    def test_only_known_requests_and_no_browser_storage(self):
        # 이전: "분석 API 1곳만" → "공통 요청 함수 1곳". 현재(PDF 다운로드 연결 후): 분석·생성은 공통 postRequest,
        # PDF는 응답을 Blob으로 받는 sendPdf 한 곳, AI 표지 배경은 PNG를 Blob으로 받는 sendCover 한 곳.
        # 사용자 파일 내용을 브라우저에서 읽거나 저장하지 않음
        self.assertEqual(len(re.findall(r"\bfetch\s*\(", JS)), 3)
        self.assertIn("fetch(url, {", JS)
        self.assertIn("fetch(Review.PDF_URL, {", JS)
        self.assertIn("fetch(Review.COVER_URL, {", JS)
        self.assertEqual(len(re.findall(r"pdfDownloader\.run\(", JS)), 1)   # 버튼 클릭 한 곳(자동 요청·재시도 없음)
        self.assertEqual(len(re.findall(r"coverGenerator\.run\(", JS)), 1)
        # 응답 서명 확인(PDF 앞 5바이트·PNG 앞 8바이트)만 arrayBuffer 허용. 다른 곳(업로드 파일)에서는 읽지 않음
        self.assertEqual(len(re.findall(r"\.arrayBuffer\s*\(", JS)), 2)
        self.assertIn("await blob.slice(0, 5).arrayBuffer()", JS[JS.index("async function sendPdf"):JS.index("async function sendCover")])
        self.assertIn("await blob.slice(0, 8).arrayBuffer()", JS[JS.index("async function sendCover"):])
        self.assertIn('ANALYZE_URL = "/api/product-brochure/analyze"', JS)
        self.assertIn('GENERATE_URL = "/api/product-brochure/generate"', JS)
        self.assertEqual(len(re.findall(r"postRequest\(Review\.(ANALYZE|GENERATE)_URL", JS)), 2)
        self.assertIn('method: "POST"', JS)
        self.assertEqual(len(re.findall(r'\.append\("source_file"', JS)), 1)
        # 생성 요청 본문은 적용 스냅샷으로 만든 JSON(Blob type이 Content-Type을 정함)
        self.assertIn('new Blob([JSON.stringify(Review.buildGeneratePayload(snap))], { type: "application/json" })', JS)
        # Content-Type 헤더를 직접 지정하지 않음(multipart 경계·JSON 타입은 본문에 맞춰 브라우저가 설정)
        self.assertIsNone(re.search(r"""["']?Content-Type["']?\s*:""", JS, re.I))
        for pattern in (r"XMLHttpRequest", r"sendBeacon", r"localStorage", r"sessionStorage", r"indexedDB",
                        r"FileReader", r"\.text\s*\(", r"setInterval"):
            self.assertIsNone(re.search(pattern, JS), pattern)
        # 분석·생성 요청은 각각 사용자 조작(submit·버튼 클릭) 한 곳에서만 시작(자동 실행·자동 재시도 없음)
        self.assertEqual(len(re.findall(r"analyzer\.run\(", JS)), 1)
        self.assertEqual(len(re.findall(r"generator\.run\(", JS)), 1)
        self.assertIn('generateBtn.addEventListener("click"', JS)
        self.assertNotIn("AppShell.onShow", JS)  # 탭 재진입 시 재요청·초기화 없음

    def test_no_html_injection_sinks(self):
        for pattern in (r"innerHTML", r"outerHTML", r"insertAdjacentHTML", r"document\.write"):
            self.assertIsNone(re.search(pattern, JS), pattern)

    def test_example_not_marked_as_result(self):
        # 결과 상태(setResult)를 만들지 않고 draft로만 보호(PDF 다운로드 연결 후에도 유지, 명세 §27).
        # downloadBlob은 PDF 다운로드 성공 경로에서만 사용(test_pdf_download_wiring)
        self.assertIsNone(re.search(r"setResult\s*\(", JS))
        self.assertEqual(JS.count("downloadBlob("), 1)
        self.assertIn("AppShell.work.setDraft(FEATURE_ID, protect)", JS)

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
