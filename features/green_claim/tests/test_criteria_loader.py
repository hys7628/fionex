"""검수 기준 자료 로더 검증. 외부 요청·OpenAI 호출 없음. 실행(저장소 루트):

    python -m unittest features.green_claim.tests.test_criteria_loader -v

오류 사례는 실제 기준 폴더를 임시 폴더로 복사해 바꾼 뒤 내부 함수(_load_from)로 확인합니다. 실제 기준 파일은 바꾸지 않습니다.
자료 구조·근거 대응 검증이며 법률 검토나 그린워싱 검수 품질 검증이 아닙니다.
"""
import hashlib
import json
import os
import shutil
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import create_app
from features.green_claim import criteria_loader as cl

MD_FILES = ("cdc_l8078_excerpt.md", "conar_excerpt.md", "review_criteria_ko.md", "source_register.md")


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RealBundleTest(unittest.TestCase):
    def test_loads_real_stored_criteria(self):
        r = cl.load_criteria()
        self.assertEqual(r["status"], "ready")
        self.assertEqual(r["counts"], {"criteria": 24, "law": 9, "advertising_self_regulation": 15})
        ids = [item["id"] for item in r["criteria"]]
        self.assertEqual(len(ids), len(set(ids)))
        for item in r["criteria"]:
            expected = ("SRC-CDC", "law") if item["id"].startswith("CDC-") else ("SRC-CONAR-WEB", "advertising_self_regulation")
            self.assertEqual((item["source_id"], item["legal_nature"]), expected, item["id"])
            self.assertIs(item["translation_official"], False)
            for name in cl.REQUIRED_TEXT_FIELDS:
                self.assertTrue(item[name].strip(), (item["id"], name))
        by_id = {item["id"]: item for item in r["criteria"]}
        self.assertIsNone(by_id["CDC-37"]["requirement_ko"])  # CDC 자료에는 "원문 요구" 칸이 없어 만들지 않음
        self.assertTrue(by_id["CONAR-U-2"]["requirement_ko"])
        self.assertIn("É proibida toda publicidade enganosa ou abusiva.", by_id["CDC-37"]["excerpt"]["text_pt"])
        self.assertIn("특정 범위에 한정된(pontuais)", by_id["CONAR-U-2"]["translation_ko"])  # 정정된 현재 번역
        self.assertNotIn("단발적", json.dumps(r, ensure_ascii=False))
        self.assertEqual(by_id["CDC-06"]["amendment_note_ko"], "III은 Lei nº 12.741/2012에 따른 문안.")

    def test_dates_versions_freshness_and_rights(self):
        r = cl.load_criteria()
        sources = {source["id"]: source for source in r["sources"]}
        self.assertEqual(sources["SRC-CDC"]["retrieved_at"], "2026-10-25T16:31:44+09:00")
        self.assertEqual(sources["SRC-CONAR-WEB"]["retrieved_at"], "2026-10-25T16:31:51+09:00")
        self.assertEqual(sources["SRC-CONAR-PDF"]["retrieved_at"], "2026-10-25T16:33:58+09:00")
        self.assertIsNone(sources["SRC-CDC"]["official_edition"])  # 공식 판 번호 없음
        self.assertEqual(sources["SRC-CONAR-PDF"]["official_edition"], "Edição 2025")
        self.assertIsNone(sources["SRC-CDC"]["dates"]["effective"])  # 정확한 시행 일자 기록 없음 → 채우지 않음
        self.assertEqual(sources["SRC-CONAR-PDF"]["dates"]["annex_u_amendment_approved"], "2025-11")
        self.assertEqual(sources["SRC-CDC"]["supporting_excerpt_ids"], ["CDC-118"])
        for source_id in ("SRC-CONAR-WEB", "SRC-CONAR-PDF"):
            self.assertEqual(sources[source_id]["usage_rights"]["status"], "ai_use_permission_unconfirmed")
        self.assertEqual(r["freshness"]["mode"], "stored_only")
        self.assertIsNone(r["freshness"]["rechecked_at"])
        bundle = r["bundle"]
        self.assertNotIn(bundle["bundle_created_at"], [source["retrieved_at"] for source in r["sources"]])
        self.assertIn("공식 자료 조회 시각", bundle["bundle_created_note"])
        self.assertIn("공식 법령·코드의 판·버전이 아님", bundle["bundle_version_note"])
        self.assertIn("최신성·법적 효력을 증명하지 않음", bundle["content_hash"]["note"])
        self.assertEqual(len(bundle["content_hash"]["value"]), 64)

    def test_independent_of_working_directory_and_returns_copies(self):
        before = os.getcwd()
        with tempfile.TemporaryDirectory() as other:
            os.chdir(other)
            try:
                first = cl.load_criteria()
            finally:
                os.chdir(before)
        first["criteria"][0]["translation_ko"] = "변경"
        first["sources"].clear()
        second = cl.load_criteria()
        self.assertNotEqual(second["criteria"][0]["translation_ko"], "변경")
        self.assertEqual(len(second["sources"]), 3)

    def test_existing_md_files_unchanged_and_no_network(self):
        before = {name: file_digest(cl.DATA_DIR / name) for name in MD_FILES}
        with mock.patch.object(socket, "socket", side_effect=AssertionError("외부 연결 금지")):
            cl.load_criteria()
        self.assertEqual({name: file_digest(cl.DATA_DIR / name) for name in MD_FILES}, before)

    def test_not_exposed_as_user_api(self):
        rules = [rule.rule for rule in create_app().url_map.iter_rules()]
        self.assertFalse([rule for rule in rules if "criteria" in rule])
        self.assertNotIn("criteria_loader", Path(cl.__file__).with_name("routes.py").read_text(encoding="utf-8"))


class BrokenBundleTest(unittest.TestCase):
    """임시 복사본에서만 자료를 바꿔 오류를 확인합니다."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "criteria"
        shutil.copytree(cl.DATA_DIR, self.dir)
        self.bundle = json.loads((self.dir / cl.BUNDLE_FILE).read_text(encoding="utf-8"))

    def tearDown(self):
        self._tmp.cleanup()

    def save(self, rehash=True):
        if rehash:
            self.bundle["content_hash"]["value"] = cl.bundle_hash(self.bundle)
        (self.dir / cl.BUNDLE_FILE).write_text(json.dumps(self.bundle, ensure_ascii=False), encoding="utf-8")

    def edit_md(self, name, old, new, update_hash=True):
        path = self.dir / name
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertIn(old, text)
        text = text.replace(old, new, 1)
        path.write_text(text, encoding="utf-8")
        if update_hash:
            for item in self.bundle["evidence_files"]:
                if item["file"] == name:
                    item["sha256"] = cl.text_sha256(text)
        self.save()

    def assertCode(self, code):
        with self.assertRaises(cl.CriteriaError) as ctx:
            cl._load_from(self.dir)
        self.assertEqual(ctx.exception.code, code, ctx.exception.detail)
        self.assertEqual(set(ctx.exception.to_dict()), {"code", "message"})
        self.assertNotIn(str(self.dir), ctx.exception.to_dict()["message"])
        return ctx.exception

    def test_copy_loads_before_changes(self):
        self.assertEqual(cl._load_from(self.dir)["status"], "ready")

    def test_file_json_and_schema(self):
        (self.dir / cl.BUNDLE_FILE).unlink()
        self.assertCode("CRITERIA_FILE_MISSING")
        (self.dir / cl.BUNDLE_FILE).write_text("{ broken", encoding="utf-8")
        self.assertCode("CRITERIA_INVALID_JSON")
        (self.dir / cl.BUNDLE_FILE).write_text("[]", encoding="utf-8")
        self.assertCode("CRITERIA_INVALID_JSON")
        for version in (2, 0, True, "1", None):
            with self.subTest(version=version):
                self.bundle["schema_version"] = version
                self.save()
                self.assertCode("CRITERIA_SCHEMA_UNSUPPORTED")

    def test_hash(self):
        self.bundle["criteria"][0]["title_ko"] += " "
        self.save(rehash=False)
        self.assertCode("CRITERIA_HASH_MISMATCH")
        self.bundle["content_hash"]["algorithm"] = "md5"
        self.save()
        self.assertCode("CRITERIA_SCHEMA_UNSUPPORTED")

    def test_invalid_fields(self):
        original = json.loads(json.dumps(self.bundle))
        cases = {
            "중복 ID": lambda b: b["criteria"].append(json.loads(json.dumps(b["criteria"][0]))),
            "필드 누락": lambda b: b["criteria"][3].pop("scope_limits_ko"),
            "잘못된 타입": lambda b: b["criteria"][3].__setitem__("title_ko", 7),
            "빈 문자열": lambda b: b["criteria"][3].__setitem__("review_guidance_ko", "  "),
            "빈 기준": lambda b: b.__setitem__("criteria", []),
            "공식 번역 표시": lambda b: b["criteria"][3].__setitem__("translation_official", True),
            "법률·자율규제 불일치": lambda b: b["criteria"][0].__setitem__("legal_nature", "advertising_self_regulation"),
            "알 수 없는 자료 ID": lambda b: b["criteria"][0].__setitem__("source_id", "SRC-NONE"),
            "최신성 상태 임의 변경": lambda b: b["freshness"].__setitem__("mode", "rechecked"),
            "자료 필드 누락": lambda b: b["sources"][0].pop("retrieved_at"),
            "자료 이름 경로 포함": lambda b: b["evidence_files"][0].__setitem__("file", "../secret.md"),
        }
        for name, change in cases.items():
            with self.subTest(name):
                self.bundle = json.loads(json.dumps(original))
                change(self.bundle)
                self.save()
                self.assertCode("CRITERIA_INVALID")

    def test_evidence_files_and_correspondence(self):
        original = json.loads(json.dumps(self.bundle))
        cases = {
            "발췌 문장 불일치": lambda b: b["criteria"][0]["excerpt"].__setitem__("text_pt", b["criteria"][0]["excerpt"]["text_pt"] + "x"),
            "조항 불일치": lambda b: b["criteria"][5].__setitem__("provisions", "Art. 99"),
            "번역 불일치": lambda b: b["criteria"][10].__setitem__("translation_ko", "다른 번역"),
            "검토 머리글 불일치": lambda b: b["criteria"][2]["review"].__setitem__("heading", "### CDC-29 다른 제목"),
            "조회 시각 불일치": lambda b: b["sources"][0].__setitem__("retrieved_at", "2026-10-25T16:31:45+09:00"),
            "기준 누락(구간 미대응)": lambda b: b["criteria"].pop(),
        }
        for name, change in cases.items():
            with self.subTest(name):
                self.bundle = json.loads(json.dumps(original))
                change(self.bundle)
                self.save()
                self.assertCode("CRITERIA_EVIDENCE_MISMATCH")
        self.bundle = json.loads(json.dumps(original))
        self.save()
        (self.dir / "conar_excerpt.md").unlink()
        self.assertCode("CRITERIA_EVIDENCE_MISSING")

    def test_md_changes_detected(self):
        self.edit_md("cdc_l8078_excerpt.md", "É proibida toda publicidade", "É permitida toda publicidade", update_hash=False)
        self.assertCode("CRITERIA_EVIDENCE_MISMATCH")  # 근거 파일 해시

    def test_md_changes_detected_even_with_updated_file_hash(self):
        self.edit_md("cdc_l8078_excerpt.md", "É proibida toda publicidade", "É permitida toda publicidade")
        self.assertCode("CRITERIA_EVIDENCE_MISMATCH")  # 기준의 발췌 문장과 다름

    def test_md_section_removed(self):
        self.edit_md("review_criteria_ko.md", "#### CONAR-U-8 비교", "#### 비교")
        self.assertCode("CRITERIA_EVIDENCE_MISSING")

    def test_logs_code_only(self):
        (self.dir / cl.BUNDLE_FILE).write_text("{ broken", encoding="utf-8")
        with mock.patch.object(cl.logger, "warning") as warn:
            with self.assertRaises(cl.CriteriaError):
                cl._load_from(self.dir)
        self.assertIn("CRITERIA_INVALID_JSON", str(warn.call_args))
        self.assertNotIn(str(self.dir), str(warn.call_args))


if __name__ == "__main__":
    unittest.main()
