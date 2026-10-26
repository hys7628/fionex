"""제품소개서 화면 상태 로직(review_logic_check.js)을 Node로 실행합니다.

Node가 없으면 건너뜁니다(Node는 프로젝트 의존성이 아님). 브라우저 동작 확인이 아닙니다.
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = HERE / "review_logic_check.js"
JS = ROOT / "features" / "product_brochure" / "static" / "product_brochure.js"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from features.product_brochure import generation  # noqa: E402

# 화면 로직으로 분석 결과 항목을 만들고 일부를 수정·확인·적용한 뒤 생성 요청 본문을 출력(가상 데이터)
PAYLOAD_SCRIPT = r"""
const R = require(process.argv[1]);
const field = (key, o) => Object.assign({ key, value: null, status: "not_found", ai_status: "not_found", evidence: [],
  marked_virtual: false, note: null, server_notes: [], confirmed: false }, o || {});
const body = { ok: true, data: { extraction_status: "unconfirmed", prompt_version: "v", source: { size_bytes: 1, page_count: 1 },
  model: "m", multiple_products: false, review_notes: [], fields: [
    field("product_name", { value: "리젠 T2T (regen T2T)", status: "found" }),
    field("description", { value: "설명(가상)", status: "unclear" }),
    field("yarn_spec"), field("carbon_reduction"), field("certification"),
    field("moq", { value: "500 kg", status: "found", marked_virtual: true }),
    field("sample", { value: "1 kg", status: "found", marked_virtual: true }),
    field("lead_time", { value: "30일", status: "found", marked_virtual: true }) ] } };
const fs = R.createFieldsFromAnalysis(R.validateAnalysis(body));
const get = (k) => fs.find((f) => f.key === k);
R.setValue(get("description"), "수정한 설명(가상)");
R.setValue(get("yarn_spec"), "75D/36F");
["product_name", "description", "yarn_spec", "moq"].forEach((k) => R.setConfirmed(get(k), true));
const suggestion = R.suggestDisplayName(get("product_name").value);  // 화면 제안값을 사용자가 확인했다고 가정
const displayName = { value: suggestion.value, confirmed: true };
process.stdout.write(JSON.stringify(R.buildGeneratePayload(R.createSnapshot(fs, "analysis", 1, displayName))));
"""


# 생성 응답 형태의 가상 데이터를 화면 로직으로 편집·적용한 뒤 PDF 요청 본문과 화면 고정값을 출력
PDF_PAYLOAD_SCRIPT = r"""
const R = require(process.argv[1]);
const copy = (text, keys, virtual) => ({ text, source_keys: keys, virtual, origins: {}, review_flags: ["claim_term"] });
const info = (key, value, virtual) => ({ key, label: "AI rótulo " + key, value, source_keys: [key], virtual,
  origin: "extracted", review_flags: [], fictitious_notice: virtual ? "Condições fictícias para demonstração." : undefined });
const data = { status: "draft_needs_review", language: "pt-BR", prompt_version: "v", model: "m",
  display_name: { value: "Fibra Exemplo D1", confirmed: true },
  notices: { unofficial: "u", fictitious: "f" },
  pages: {
    cover: { page: 1, product_name: copy("Fibra Exemplo D1", ["product_name"], false), tagline: copy("Original.", ["description"], false) },
    intro: { page: 2, paragraphs: [copy("Parágrafo original.", ["description"], true)] },
    details: { page: 3, items: [info("yarn_spec", "75D/36F", false), info("carbon_reduction", "Dado fictício.", true)], empty: false, empty_message: null },
    supply: { page: 4, items: [info("moq", "500 kg", true), info("lead_time", "30 dias", true)], empty: false, empty_message: null },
  }, used_keys: [], excluded: [], input_meta: {} };
const original = R.cloneData(data);
const values = R.editValues(original);
values.display_name = "Fio Ação & Têxtil";
values.tagline = "Texto aplicado <editado> & ação.";
values["supply:moq"] = "800 kg";
const current = R.applyEdits(original, R.cloneData(original), values).data;
process.stdout.write(JSON.stringify({ payload: R.buildPdfPayload(current), labels: R.CATALOG_ITEM_LABELS,
  filename: R.PDF_FILENAME, maxBytes: R.MAX_PDF_REQUEST_BYTES }));
"""


class PdfCrossTests(unittest.TestCase):
    """화면 JS가 만든 PDF 요청 본문을 실제 서버 계약(parse_catalog·라우트)으로 확인합니다(OpenAI 호출 없음)."""

    @classmethod
    def setUpClass(cls):
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("node 없음")
        result = subprocess.run([node, "-e", PDF_PAYLOAD_SCRIPT, str(JS)], capture_output=True, text=True,
                                encoding="utf-8", timeout=60)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        cls.out = json.loads(result.stdout)

    def test_payload_accepted_by_parse_catalog(self):
        from features.product_brochure import pdf_catalog, pdf_download
        catalog = pdf_download.parse_request(self.out["payload"])
        parsed = pdf_catalog.parse_catalog(catalog)
        self.assertEqual(parsed["product_name"], {"text": "Fio Ação & Têxtil", "virtual": False})
        self.assertEqual(parsed["tagline"]["text"], "Texto aplicado <editado> & ação.")   # 적용본 사용
        self.assertEqual(parsed["paragraphs"], [{"text": "Parágrafo original.", "virtual": True}])
        self.assertEqual([(i["key"], i["value"], i["virtual"]) for i in parsed["supply"]],
                         [("moq", "800 kg", True), ("lead_time", "30 dias", True)])
        self.assertEqual([(i["key"], i["virtual"]) for i in parsed["details"]],
                         [("yarn_spec", False), ("carbon_reduction", True)])
        self.assertNotIn("AI rótulo", json.dumps(self.out["payload"], ensure_ascii=False))  # AI 라벨 미전송

    def test_payload_downloads_through_route(self):
        import io
        from pypdf import PdfReader
        from app import create_app
        client = create_app().test_client()
        res = client.post("/api/product-brochure/pdf", json=self.out["payload"])
        self.addCleanup(res.close)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "application/pdf")
        texts = " ".join(" ".join(p.extract_text().split()) for p in PdfReader(io.BytesIO(res.get_data())).pages)
        self.assertIn("Fio Ação & Têxtil", texts)
        self.assertIn("800 kg", texts)
        self.assertIn("Condições fictícias para demonstração.", texts)

    def test_screen_constants_match_server(self):
        from features.product_brochure import pdf_catalog, pdf_download
        self.assertEqual(self.out["labels"], pdf_catalog.ITEM_LABELS)          # 화면·PDF 항목명 일치
        self.assertEqual(self.out["filename"], pdf_download.DOWNLOAD_NAME)
        self.assertEqual(self.out["maxBytes"], pdf_download.MAX_REQUEST_BYTES)


class ReviewLogicTests(unittest.TestCase):
    def node(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node 없음")
        return node

    def test_node_logic_checks(self):
        result = subprocess.run([self.node(), str(SCRIPT)], capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("checks passed", result.stdout)

    def test_screen_payload_accepted_by_server_schema(self):
        # 화면 JS가 만든 요청 본문을 서버 generation.parse_request(엄격 스키마)가 그대로 받는지
        result = subprocess.run([self.node(), "-e", PAYLOAD_SCRIPT, str(JS)], capture_output=True, text=True,
                                encoding="utf-8", timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        by_key, display_name = generation.parse_request(payload)
        self.assertEqual(display_name, "regen T2T")                         # 화면 제안 → 서버 표시명
        self.assertEqual(by_key["product_name"].value, "리젠 T2T (regen T2T)")  # 원본 제품명 보존
        used, excluded = generation.select_inputs(by_key)
        self.assertEqual(used, ["product_name", "description", "yarn_spec", "moq"])
        self.assertEqual({e["key"]: e["reason"] for e in excluded},
                         {"carbon_reduction": "empty", "certification": "empty", "sample": "unconfirmed", "lead_time": "unconfirmed"})
        self.assertEqual(by_key["description"].origin, "user_modified")
        self.assertEqual(by_key["yarn_spec"].origin, "user_added")
        self.assertEqual(by_key["product_name"].origin, "extracted")
        self.assertIs(by_key["moq"].virtual, True)


if __name__ == "__main__":
    unittest.main()
