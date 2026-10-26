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
