"""기준 묶음 생성·공식 출처 변경 확인·후보 교체 검증. 외부 요청·OpenAI 호출 없음. 실행(저장소 루트):

    python -m unittest features.green_claim.tests.test_criteria_update -v

모든 테스트는 기본 기준을 임시 data 폴더로 복사해 사용하고, HTTP는 가짜 응답으로 대신합니다(실제 소켓 생성 차단).
실제 기준 파일·확인 상태 파일은 만들거나 바꾸지 않습니다. 검토 기록(review.json)은 테스트용 가상 기록입니다.
"""
import hashlib
import html
import http.client
import io
import json
import multiprocessing
import os
import shutil
import socket
import ssl
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path
from unittest import mock

from features.green_claim import criteria_admin, criteria_build as cb, criteria_check as cc
from features.green_claim import criteria_loader as cl, criteria_store as cs

CDC_URL = "https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm"
CONAR_URL = "https://www.conar.org.br/codigos"
CDC_MARKER = "LEI Nº 8.078, DE 11 DE SETEMBRO DE 1990."
CONAR_MARKER = "Código Brasileiro de Autorregulamentação Publicitária"


def tree_digest(directory):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(directory).iterdir()) if p.is_file()}


class FakeResponse(io.BytesIO):
    def __init__(self, status, body=b"", content_type="text/html; charset=utf-8", headers=None):
        super().__init__(body)
        self.status = status
        self.headers = Message()
        if content_type:
            self.headers["Content-Type"] = content_type
        for key, value in (headers or {}).items():
            self.headers[key] = value


class FakeWeb:
    """URL → 응답 함수. 요청 기록을 남깁니다."""

    def __init__(self, routes):
        self.routes = routes
        self.requests = []

    def __call__(self, url, timeout):
        self.requests.append((url, timeout))
        handler = self.routes.get(url)
        if handler is None:
            return FakeResponse(404, b"", "text/plain")
        return handler() if callable(handler) else handler


def page(criteria, source_id, marker, replace=None, extra_menu="", drop=None, encoding="utf-8", edit=None):
    """저장 원문 발췌로 만든 가상 공식 페이지(메뉴 포함). replace=(옛 문장, 새 문장), drop=뺄 기준 ID,
    edit=본문 HTML을 바꾸는 함수. 마지막 조항 뒤에 다음 장·부속서 제목을 두어 조항 끝을 표시합니다."""
    paragraphs = []
    for item in criteria:
        if item["source_id"] != source_id or item["id"] == drop:
            continue
        for line in item["excerpt"]["text_pt"].split("\n"):
            if line:
                if source_id == "SRC-CONAR-WEB" and len(line) > 3 and line[1:3] == ". " and line[0] in "abcdefgh":
                    line = line[3:]  # 실제 웹은 HTML 목록이라 기호가 본문 텍스트에 없음
                paragraphs.append(f"<p>{html.escape(line, quote=False)}</p>")
    body = "".join(paragraphs)
    if replace:
        old = html.escape(replace[0], quote=False)
        assert old in body, replace[0]
        body = body.replace(old, html.escape(replace[1], quote=False), 1)
    if edit:
        body = edit(body)
    closing = "<p>TÍTULO II</p>" if source_id == "SRC-CDC" else '<p>ANEXO "V"</p>'
    text = (f"<html><head><title>T</title><style>p{{color:red}}</style><script>var x=1;</script></head><body>"
            f"<div class='menu'>Início | Legislação {extra_menu}</div><p><strong>{marker}</strong></p>{body}{closing}"
            f"<div class='footer'>Rodapé</div></body></html>")
    return text.encode(encoding)


def review_record(**overrides):
    record = {"reviewed_by": "테스트 검토자(가상)", "reviewed_at": "2026-10-26T10:00:00+09:00",
              "scope": "테스트용 가상 검토 기록", "translation_reviewed": True, "guidance_reviewed": True,
              "sources_rechecked": ["SRC-CDC"], "criteria_updated_on": "2026-10-26"}
    record.update(overrides)
    return record


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "data"
        self.root.mkdir()
        shutil.copytree(cl.DATA_DIR, self.root / cl.BASE_DIR_NAME)
        self.loaded = cl._load_active(self.root)
        # 가상 페이지는 저장 발췌만으로 만들어 실제 확보본의 발췌 밖 문장이 없으므로, 그 페이지 기준 비교 범위(모두 full)를 씁니다.
        # 실제 comparison_units.json(일부 partial)의 동작은 CoverageTest에서 따로 확인합니다.
        self.set_coverage()
        self.base_digest = tree_digest(self.root / cl.BASE_DIR_NAME)
        guard = mock.patch.object(socket, "socket", side_effect=AssertionError("실제 네트워크 사용 금지"))
        guard.start()
        self.addCleanup(guard.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def cdc_page(self, **kwargs):
        return page(self.loaded["criteria"], "SRC-CDC", CDC_MARKER, **kwargs)

    def set_coverage(self, overrides=None, remove=False):
        path = self.root / cl.BASE_DIR_NAME / cc.COVERAGE_FILE
        if remove:
            path.unlink()
            return
        coverage = {}
        for source_id, marker in (("SRC-CDC", CDC_MARKER), ("SRC-CONAR-WEB", CONAR_MARKER)):
            lines = cc.html_lines(page(self.loaded["criteria"], source_id, marker), "utf-8")
            criteria = [item for item in self.loaded["criteria"] if item["source_id"] == source_id]
            coverage.update(cc.measure_coverage(criteria, lines, cc.UNIT_RULES[source_id],
                                                cc.POLICIES[source_id]["strip_list_markers"]))
        for criterion_id, units in (overrides or {}).items():
            coverage[criterion_id].update(units)
        path.write_text(json.dumps({"schema_version": 1, "coverage": coverage}, ensure_ascii=False), encoding="utf-8")

    def web(self, cdc=None, robots=None, conar=None):
        routes = {"https://www.planalto.gov.br/robots.txt": robots or FakeResponse(404, b"", "text/plain"),
                  CDC_URL: cdc if cdc is not None else (lambda: FakeResponse(200, self.cdc_page()))}
        if conar is not None:
            routes["https://www.conar.org.br/robots.txt"] = FakeResponse(404, b"", "text/plain")
            routes[CONAR_URL] = conar
        return FakeWeb(routes)

    def check(self, web, **kwargs):
        return cc.check_sources(root=self.root, opener=web, now=kwargs.pop("now", "2026-10-26T09:00:00+09:00"), **kwargs)

    def source(self, result, source_id):
        return next(item for item in result["sources"] if item["source_id"] == source_id)

    def prepared(self, name="cand1", version="2026-10-26.2"):
        cs.prepare_candidate(name, root=self.root)
        cb.build_candidate(name, version, root=self.root, created_at="2026-10-26T09:30:00+09:00")
        return cb.candidate_directory(name, self.root)


class BuildTest(Base):
    def test_stable_output_and_same_content_as_active(self):
        directory = cb.candidate_directory("x", self.root)
        cs.prepare_candidate("x", root=self.root)
        first = cb.build_candidate("x", "2026-10-26.2", root=self.root, created_at="2026-10-26T01:00:00+09:00")
        bytes_one = (directory / cl.BUNDLE_FILE).read_bytes()
        second = cb.build_candidate("x", "2026-10-26.2", root=self.root, created_at="2026-10-27T05:00:00+09:00")
        self.assertEqual(first["bundle"]["content_hash"], second["bundle"]["content_hash"])
        self.assertNotEqual(first["bundle"]["bundle_created_at"], second["bundle"]["bundle_created_at"])
        bundle_two = json.loads((directory / cl.BUNDLE_FILE).read_text(encoding="utf-8"))
        bundle_one = json.loads(bytes_one.decode("utf-8"))
        bundle_one.pop("bundle_created_at"), bundle_two.pop("bundle_created_at")
        self.assertEqual(bundle_one, bundle_two)
        active = json.loads((self.root / cl.BASE_DIR_NAME / cl.BUNDLE_FILE).read_text(encoding="utf-8"))
        self.assertEqual((second["criteria"], second["sources"]), (active["criteria"], active["sources"]))
        self.assertEqual(second["bundle"]["schema_version"], 2)
        self.assertEqual(tree_digest(self.root / cl.BASE_DIR_NAME), self.base_digest)  # 활성(base) 기준 미변경

    def test_failures_leave_no_bundle(self):
        cases = {
            "md 누락": lambda d: (d / "conar_excerpt.md").unlink(),
            "검토 구간 누락": lambda d: (d / cl.REVIEW_FILE).write_text(
                (d / cl.REVIEW_FILE).read_text(encoding="utf-8").replace("#### CONAR-U-8 비교", "#### 비교"), encoding="utf-8"),
            "메타 손상": lambda d: (d / cl.SOURCES_META_FILE).write_text("{", encoding="utf-8"),
            "출처 행 누락": lambda d: (d / cl.REGISTER_FILE).write_text(
                (d / cl.REGISTER_FILE).read_text(encoding="utf-8").replace("| SRC-CDC |", "| SRC-XXX |"), encoding="utf-8"),
        }
        for index, (label, change) in enumerate(cases.items()):
            with self.subTest(label):
                name = f"bad{index}"
                directory = cs.prepare_candidate(name, root=self.root)
                change(directory)
                with self.assertRaises(cl.CriteriaError) as ctx:
                    cb.build_candidate(name, "v1", root=self.root)
                self.assertEqual(ctx.exception.code, "CRITERIA_BUILD_FAILED")
                self.assertFalse((directory / cl.BUNDLE_FILE).exists())

    def test_only_candidate_names(self):
        for name in ("../x", "a/b", "", "x.partial", "..", "C:\\x"):
            with self.subTest(name=name):
                with self.assertRaises(cl.CriteriaError) as ctx:
                    cb.build_candidate(name, "v1", root=self.root)
                self.assertEqual(ctx.exception.code, "CRITERIA_INVALID")
        with self.assertRaises(cl.CriteriaError):
            cb.build_candidate("missing", "v1", root=self.root)


class ActivationTest(Base):
    def test_review_required_and_activate_and_rollback(self):
        directory = self.prepared()
        with self.assertRaises(cl.CriteriaError) as ctx:
            cs.activate_candidate("cand1", root=self.root)
        self.assertEqual(ctx.exception.code, "CRITERIA_REVIEW_MISSING")
        for bad in (review_record(translation_reviewed=False), review_record(guidance_reviewed="yes"),
                    review_record(reviewed_by=" ")):
            (directory / cs.REVIEW_FILE).write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(cl.CriteriaError):
                cs.activate_candidate("cand1", root=self.root)
        self.assertIsNone(cl.read_pointer(self.root))
        self.assertEqual(cl._load_active(self.root)["active_version"], "base")

        (directory / cs.REVIEW_FILE).write_text(json.dumps(review_record(), ensure_ascii=False), encoding="utf-8")
        pointer = cs.activate_candidate("cand1", root=self.root)
        loaded = cl._load_active(self.root)
        self.assertEqual((pointer["previous"], loaded["active_version"]), ("base", pointer["active"]))
        self.assertTrue(pointer["active"].startswith("2026-10-26.2-"))
        self.assertEqual(loaded["bundle"]["schema_version"], 2)
        self.assertEqual(tree_digest(self.root / cl.BASE_DIR_NAME), self.base_digest)
        self.assertEqual(list((self.root / cl.VERSIONS_DIR_NAME).glob("*.partial")), [])
        with self.assertRaises(cl.CriteriaError) as ctx:
            cs.activate_candidate("cand1", root=self.root)
        self.assertEqual(ctx.exception.code, "CRITERIA_ACTIVATION_FAILED")  # 이미 활성

        back = cs.rollback(root=self.root)
        self.assertEqual((back["active"], cl._load_active(self.root)["active_version"]), ("base", "base"))
        again = cs.rollback(root=self.root)
        self.assertEqual(again["active"], pointer["active"])

    def test_reviewed_content_change_becomes_active_only_after_activation(self):
        directory = cs.prepare_candidate("cand2", root=self.root)
        review = directory / cl.REVIEW_FILE
        text = review.read_text(encoding="utf-8")
        old = "- 검토 활용: 수정 방향에"
        self.assertEqual(text.count(old), 1)
        review.write_text(text.replace(old, "- 검토 활용: (가상 검토 수정) 수정 방향에"), encoding="utf-8")
        cb.build_candidate("cand2", "2026-10-26.3", root=self.root)
        self.assertNotIn("(가상 검토 수정)", json.dumps(cl._load_active(self.root), ensure_ascii=False))
        (directory / cs.REVIEW_FILE).write_text(json.dumps(review_record(), ensure_ascii=False), encoding="utf-8")
        cs.activate_candidate("cand2", root=self.root)
        self.assertIn("(가상 검토 수정)", json.dumps(cl._load_active(self.root), ensure_ascii=False))

    def test_failed_activation_keeps_current(self):
        directory = self.prepared()
        (directory / cs.REVIEW_FILE).write_text(json.dumps(review_record(), ensure_ascii=False), encoding="utf-8")
        with mock.patch.object(cs.os, "rename", side_effect=OSError("disk")):
            with self.assertRaises(cl.CriteriaError) as ctx:
                cs.activate_candidate("cand1", root=self.root)
        self.assertEqual(ctx.exception.code, "CRITERIA_ACTIVATION_FAILED")
        self.assertIsNone(cl.read_pointer(self.root))
        self.assertEqual(list((self.root / cl.VERSIONS_DIR_NAME).glob("*")), [])  # 부분 폴더 남지 않음
        bundle = json.loads((directory / cl.BUNDLE_FILE).read_text(encoding="utf-8"))
        bundle["criteria"][0]["translation_ko"] = "조작"
        (directory / cl.BUNDLE_FILE).write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(cl.CriteriaError) as ctx:
            cs.activate_candidate("cand1", root=self.root)
        self.assertEqual(ctx.exception.code, "CRITERIA_HASH_MISMATCH")
        self.assertIsNone(cl.read_pointer(self.root))
        self.assertFalse((self.root / cl.STATE_DIR_NAME / cs.LOCK_FILE).exists())

    def test_pointer_problems_do_not_fall_back_silently(self):
        state = self.root / cl.STATE_DIR_NAME
        state.mkdir()
        for content in ("{", json.dumps({"active": "../brazil_claim_criteria"}), json.dumps({"active": "missing-1"}),
                        json.dumps({"x": 1})):
            with self.subTest(content=content):
                (state / cl.POINTER_FILE).write_text(content, encoding="utf-8")
                with self.assertRaises(cl.CriteriaError) as ctx:
                    cl._load_active(self.root)
                self.assertEqual(ctx.exception.code, "CRITERIA_POINTER_INVALID")
        result = cc.criteria_status(self.root)
        self.assertEqual((result["overall"], result["criteria_usable"]), ("not_ready", False))

    def test_no_criteria_at_all(self):
        shutil.rmtree(self.root / cl.BASE_DIR_NAME)
        web = self.web()
        result = self.check(web)
        self.assertEqual((result["overall"], result["criteria_usable"], web.requests), ("not_ready", False, []))


class LockTest(Base):
    def test_busy_stale_and_cleanup(self):
        with cs.criteria_lock(self.root):
            with self.assertRaises(cl.CriteriaError) as ctx:
                with cs.criteria_lock(self.root, wait=0.3):
                    pass
            self.assertEqual(ctx.exception.code, "CRITERIA_BUSY")
            web = self.web()
            with mock.patch.object(cs, "LOCK_WAIT_SECONDS", 0.3):
                result = cc.check_sources(root=self.root, opener=web)
            self.assertEqual((result["overall"], web.requests), ("busy", []))
        lock = self.root / cl.STATE_DIR_NAME / cs.LOCK_FILE
        self.assertFalse(lock.exists())
        lock.write_text(json.dumps({"pid": 1, "created": time.time() - 3600}), encoding="ascii")
        with cs.criteria_lock(self.root, wait=0.3):
            pass  # 오래된 잠금은 정리 후 획득
        self.assertFalse(lock.exists())
        with self.assertRaises(RuntimeError):
            with cs.criteria_lock(self.root):
                raise RuntimeError("작업 중 실패")
        self.assertFalse(lock.exists())

    def test_concurrent_activation_and_check(self):
        directory = self.prepared()
        (directory / cs.REVIEW_FILE).write_text(json.dumps(review_record(), ensure_ascii=False), encoding="utf-8")
        outcomes = []
        barrier = threading.Barrier(2)

        def activate():
            barrier.wait()
            try:
                outcomes.append(("activate", cs.activate_candidate("cand1", root=self.root)["active"]))
            except cl.CriteriaError as err:
                outcomes.append(("activate", err.code))

        def check():
            barrier.wait()
            outcomes.append(("check", self.check(self.web())["overall"]))

        threads = [threading.Thread(target=activate), threading.Thread(target=check)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(30)
        self.assertEqual(len(outcomes), 2)
        loaded = cl._load_active(self.root)
        self.assertTrue(loaded["active_version"].startswith("2026-10-26.2-"))  # 확인은 잠금 대기 후 진행(또는 busy)
        self.assertFalse((self.root / cl.STATE_DIR_NAME / cs.LOCK_FILE).exists())
        self.assertEqual(list((self.root / cl.VERSIONS_DIR_NAME).glob("*.partial")), [])


class CheckTest(Base):
    def test_no_change_and_deferred_sources(self):
        web = self.web()
        before = tree_digest(self.root / cl.BASE_DIR_NAME)
        result = self.check(web)
        cdc = self.source(result, "SRC-CDC")
        self.assertEqual((cdc["status"], cdc["success"], cdc["requests_used"]), ("no_change_found", True, 2))
        self.assertEqual(len(cdc["checked_criteria"]), 9)
        self.assertEqual(cdc["last_success_at"], "2026-10-26T09:00:00+09:00")
        conar = self.source(result, "SRC-CONAR-WEB")
        self.assertEqual((conar["status"], conar["reason_code"]), ("deferred", "terms_permission_unconfirmed"))
        self.assertEqual(len(conar["unchecked_criteria"]), 15)
        self.assertEqual(self.source(result, "SRC-CONAR-PDF")["status"], "deferred")
        self.assertEqual((result["overall"], result["criteria_usable"]), ("partial", True))  # 일부 출처만 확인 → 완료 아님
        self.assertEqual(result["active"]["sources_retrieved_at"]["SRC-CDC"], "2026-10-25T16:31:44+09:00")
        self.assertEqual(result["active"]["active_version"], "base")
        self.assertTrue(any("최신성은 알 수 없습니다" in warning for warning in result["warnings"]))
        self.assertEqual([url for url, _ in web.requests], ["https://www.planalto.gov.br/robots.txt", CDC_URL])
        self.assertEqual(tree_digest(self.root / cl.BASE_DIR_NAME), before)  # 변경 없음이면 기준 파일 재작성 없음
        status = cc.criteria_status(self.root)
        self.assertEqual((status["network_checked"], self.source(status, "SRC-CDC")["status"]), (False, "no_change_found"))

    def test_menu_and_format_changes_are_not_changes(self):
        body = self.cdc_page(extra_menu="<b>Novo item</b> " * 20).replace(b"<p>", b"<p style='font-size:9px'>  \n")
        result = self.check(self.web(cdc=FakeResponse(200, body)))
        self.assertEqual(self.source(result, "SRC-CDC")["status"], "no_change_found")

    def test_clause_change_detected_recorded_not_applied(self):
        changed = self.cdc_page(replace=("É proibida toda publicidade enganosa ou abusiva.",
                                         "É proibida toda publicidade enganosa, abusiva ou TESTE-NOVO."))
        result = self.check(self.web(cdc=FakeResponse(200, changed)))
        cdc = self.source(result, "SRC-CDC")
        self.assertEqual((cdc["status"], cdc["changed_criteria"]), ("change_detected", ["CDC-37"]))
        self.assertEqual((result["overall"], result["criteria_usable"]), ("change_pending_review", True))
        self.assertEqual(len(result["unresolved_changes"]), 1)
        detail = self.root / cb.WORK_DIR_NAME / cc.DETECTED_DIR_NAME / result["unresolved_changes"][0]["detail_file"]
        recorded = json.loads(detail.read_text(encoding="utf-8"))
        self.assertIn("abusiva ou TESTE-NOVO", recorded["page_text"])
        self.assertEqual(tree_digest(self.root / cl.BASE_DIR_NAME), self.base_digest)  # 자동 반영 없음
        self.assertNotIn("TESTE-NOVO", json.dumps(cl._load_active(self.root), ensure_ascii=False))
        again = self.check(self.web(cdc=FakeResponse(200, changed)), now="2026-10-26T10:00:00+09:00")
        self.assertEqual(len(again["unresolved_changes"]), 1)  # 같은 내용은 중복 기록 안 함
        ok = self.check(self.web(), now="2026-10-26T11:00:00+09:00")
        self.assertEqual(ok["overall"], "change_pending_review")  # 검토·반영 전까지 미반영 경고 유지
        directory = self.prepared()
        (directory / cs.REVIEW_FILE).write_text(json.dumps(review_record(), ensure_ascii=False), encoding="utf-8")
        cs.activate_candidate("cand1", root=self.root)
        self.assertEqual(cc.criteria_status(self.root)["unresolved_changes"], [])

    def test_missing_clause_and_extraction_failure(self):
        result = self.check(self.web(cdc=FakeResponse(200, self.cdc_page(drop="CDC-38"))))
        cdc = self.source(result, "SRC-CDC")
        self.assertEqual((cdc["status"], cdc["comparison"]["CDC-38"]["result"]), ("change_detected", "missing"))
        empty_articles = f"<html><body><p>{CDC_MARKER}</p><p>Página em manutenção</p></body></html>".encode()
        result = self.check(self.web(cdc=FakeResponse(200, empty_articles)))
        self.assertEqual((self.source(result, "SRC-CDC")["status"], self.source(result, "SRC-CDC")["reason_code"]),
                         ("failed", "extraction_failed"))

    def test_bad_responses_are_failures_not_no_change(self):
        login = b"<html><body><form>Login</form><p>Acesso restrito</p></body></html>"
        bad_utf8 = b"<html><body>\xff\xfe\xfa</body></html>"
        cases = {
            "http_error": FakeResponse(500, b"<html>erro</html>"),
            "page_unrecognized": FakeResponse(200, login),
            "page_unrecognized ": FakeResponse(200, b""),
            "not_html": FakeResponse(200, b"%PDF-1.7", "application/pdf"),
            "decode_error": FakeResponse(200, bad_utf8, "text/html; charset=utf-8"),
        }
        self.check(self.web(), now="2026-10-26T08:00:00+09:00")  # 이전 성공 기록
        for code, response in cases.items():
            with self.subTest(code):
                result = self.check(self.web(cdc=response))
                cdc = self.source(result, "SRC-CDC")
                self.assertEqual((cdc["status"], cdc["reason_code"], cdc["success"]), ("failed", code.strip(), False))
                self.assertEqual(cdc["last_success_at"], "2026-10-26T08:00:00+09:00")  # 마지막 성공 시각 유지
                self.assertTrue(result["criteria_usable"])
                self.assertIn("기존 기준", " ".join(result["warnings"]))

    def test_server_closed_is_distinguished_and_kept_failed(self):
        # 2026-10-26 실제 진단: robots.txt 요청에 Planalto가 HTTP 응답 없이 연결을 끊음(http.client.RemoteDisconnected).
        # 연결 실패(network_error)와 구분하되 실패 그대로 처리하고, 마지막 성공 시각·기존 기준 사용을 유지하는지 확인(가상 응답).
        def closed():
            raise http.client.RemoteDisconnected("Remote end closed connection without response")

        def closed_wrapped():
            raise urllib.error.URLError(http.client.RemoteDisconnected("closed"))

        def refused():
            raise ConnectionRefusedError(10061, "refused")

        self.check(self.web(), now="2026-10-26T08:00:00+09:00")  # 이전 성공 기록
        cases = [
            ("robots closed", {"robots": closed}, "server_closed", "robots", 1),
            ("robots closed (URLError)", {"robots": closed_wrapped}, "server_closed", "robots", 1),
            ("page closed", {"cdc": closed}, "server_closed", "page", 2),
            ("robots refused", {"robots": refused}, "network_error", "robots", 1),
        ]
        for name, routes, code, step, requests in cases:
            with self.subTest(name):
                web = self.web(**routes)
                result = self.check(web, now="2026-10-26T13:54:36+09:00")
                cdc = self.source(result, "SRC-CDC")
                self.assertEqual((cdc["status"], cdc["reason_code"], cdc["success"], cdc["failed_step"]), ("failed", code, False, step))
                self.assertEqual((cdc["requests_used"], len(web.requests)), (requests, requests))  # robots 실패 시 페이지 요청 없음
                self.assertEqual(cdc["last_success_at"], "2026-10-26T08:00:00+09:00")  # 실제 성공 없이 갱신하지 않음
                self.assertTrue(result["criteria_usable"])
                self.assertIn("기존 기준", " ".join(result["warnings"]))
                state = cs.read_check_state(self.root)["sources"]["SRC-CDC"]
                self.assertEqual((state["last_reason_code"], state["last_failed_step"]), (code, step))
        ok = self.source(self.check(self.web(), now="2026-10-26T15:00:00+09:00"), "SRC-CDC")
        self.assertEqual((ok["status"], ok.get("failed_step")), ("no_change_found", None))
        self.assertIsNone(cs.read_check_state(self.root)["sources"]["SRC-CDC"]["last_failed_step"])

    def test_windows_1252_page_without_charset(self):
        body = self.cdc_page(encoding="windows-1252")
        result = self.check(self.web(cdc=FakeResponse(200, body, "text/html")))
        self.assertEqual(self.source(result, "SRC-CDC")["status"], "no_change_found")

    def test_network_limits(self):
        def timeout():
            raise socket.timeout("slow")

        big_header = FakeResponse(200, b"x", headers={"Content-Length": str(cc.MAX_DOWNLOAD_BYTES + 1)})
        big_body = FakeResponse(200, b"<html>" + b"a" * cc.MAX_DOWNLOAD_BYTES)
        cases = {"timeout": timeout, "too_large": big_header, "too_large ": big_body}
        for code, response in cases.items():
            with self.subTest(code):
                result = self.check(self.web(cdc=response))
                self.assertEqual(self.source(result, "SRC-CDC")["reason_code"], code.strip())
        # 같은 호스트 리다이렉트도 요청 수에 포함: robots + 리다이렉트 + 본문 = 3 > 2
        redirect = FakeResponse(301, b"", headers={"Location": "/ccivil_03/leis/L8078compilado.htm"})
        web = self.web(cdc=redirect)
        web.routes["https://www.planalto.gov.br/ccivil_03/leis/L8078compilado.htm"] = lambda: FakeResponse(200, self.cdc_page())
        result = self.check(web)
        self.assertEqual((self.source(result, "SRC-CDC")["reason_code"], len(web.requests)), ("too_many_requests", 2))
        no_robots = {key: dict(value) for key, value in cc.POLICIES.items()}
        no_robots["SRC-CDC"]["check_robots"] = False
        web = self.web(cdc=redirect)
        web.routes["https://www.planalto.gov.br/ccivil_03/leis/L8078compilado.htm"] = lambda: FakeResponse(200, self.cdc_page())
        result = self.check(web, policies=no_robots)
        self.assertEqual(self.source(result, "SRC-CDC")["status"], "no_change_found")
        for location in ("https://evil.example/l8078.htm", "http://www.planalto.gov.br/x.htm"):
            with self.subTest(location=location):
                web = self.web(cdc=FakeResponse(302, b"", headers={"Location": location}))
                result = self.check(web, policies=no_robots)
                self.assertEqual(self.source(result, "SRC-CDC")["reason_code"], "redirect_refused")
                self.assertNotIn(location, [url for url, _ in web.requests])
        ticks = iter(range(0, 1000, 31))
        result = self.check(self.web(), clock=lambda: next(ticks))
        self.assertIn(self.source(result, "SRC-CDC")["reason_code"], ("deadline", "timeout"))
        web = self.web()
        self.check(web)
        self.assertTrue(all(timeout_value <= cc.REQUEST_TIMEOUT_SECONDS for _, timeout_value in web.requests))

    def test_robots(self):
        disallow = FakeResponse(200, b"User-agent: *\nDisallow: /ccivil_03/\n", "text/plain")
        web = self.web(robots=disallow)
        result = self.check(web)
        cdc = self.source(result, "SRC-CDC")
        self.assertEqual((cdc["status"], cdc["reason_code"], len(web.requests)), ("deferred", "robots_disallowed", 1))
        result = self.check(self.web(robots=FakeResponse(503, b"", "text/plain")))
        self.assertEqual(self.source(result, "SRC-CDC")["reason_code"], "robots_unavailable")

    def test_partial_success_and_baseline_missing(self):
        policies = {key: dict(value) for key, value in cc.POLICIES.items()}
        policies["SRC-CONAR-WEB"]["auto_fetch"] = True   # 내부 테스트 경계에서만(가짜 응답)
        policies["SRC-CONAR-PDF"] = dict(policies["SRC-CDC"], host="conar.wpenginepowered.com")
        conar_ok = FakeResponse(200, page(self.loaded["criteria"], "SRC-CONAR-WEB", CONAR_MARKER))
        result = self.check(self.web(conar=conar_ok), policies=policies)
        self.assertEqual(self.source(result, "SRC-CONAR-WEB")["status"], "no_change_found")
        self.assertEqual(self.source(result, "SRC-CONAR-PDF")["status"], "baseline_missing")  # 저장 발췌 없음
        self.assertEqual(result["overall"], "partial")
        result = self.check(self.web(conar=FakeResponse(500, b"")), policies=policies)
        self.assertEqual((self.source(result, "SRC-CDC")["status"], self.source(result, "SRC-CONAR-WEB")["status"]),
                         ("no_change_found", "failed"))
        self.assertEqual(result["overall"], "partial")
        wrong_host = {"SRC-CDC": dict(cc.POLICIES["SRC-CDC"], host="www.example.org")}
        result = self.check(self.web(), policies=wrong_host)
        self.assertEqual(self.source(result, "SRC-CDC")["reason_code"], "url_not_allowed")

    def test_status_before_any_check_and_tls_default(self):
        status = cc.criteria_status(self.root)
        self.assertEqual({item["source_id"]: item["status"] for item in status["sources"]},
                         {"SRC-CDC": "not_checked", "SRC-CONAR-WEB": "deferred", "SRC-CONAR-PDF": "deferred"})
        self.assertEqual((status["overall"], status["criteria_usable"]), ("partial", True))
        captured = {}

        class Opener:
            def open(self, request, timeout):
                captured["timeout"] = timeout
                return FakeResponse(200, b"")

        def build_opener(*handlers):
            captured["handlers"] = handlers
            return Opener()

        with mock.patch.object(urllib.request, "build_opener", build_opener):
            cc.default_open(CDC_URL, 10)
        https = next(h for h in captured["handlers"] if isinstance(h, urllib.request.HTTPSHandler))
        context = https._context
        self.assertEqual((context.verify_mode, context.check_hostname), (ssl.CERT_REQUIRED, True))
        self.assertTrue(any(isinstance(h, type) and issubclass(h, urllib.request.HTTPRedirectHandler)
                            for h in captured["handlers"]))


class ClauseComparisonTest(Base):
    """조항 전체 비교: 기존 문장을 남긴 채 추가·조건·숫자·부정어·삭제·순서 변경을 잡는지, 서식만 바뀐 것은 무시하는지."""

    def cdc(self, **kwargs):
        result = self.check(self.web(cdc=FakeResponse(200, self.cdc_page(**kwargs))))
        return self.source(result, "SRC-CDC")

    def lines_of(self, criterion_id):
        item = next(item for item in self.loaded["criteria"] if item["id"] == criterion_id)
        return [line for line in item["excerpt"]["text_pt"].split("\n") if line]

    def test_additions_keeping_existing_sentences(self):
        art37 = self.lines_of("CDC-37")
        cases = {
            "중간에 문단 추가": dict(edit=lambda b: b.replace(f"<p>{html.escape(art37[2], quote=False)}",
                                                     f"<p>§ 1°-A Parágrafo inserido de teste.</p><p>{html.escape(art37[2], quote=False)}", 1)),
            "끝에 문단 추가": dict(replace=("§ 4° (Vetado).", "§ 4° (Vetado).\n§ 5° Parágrafo final de teste.")),
            "같은 줄 끝에 문장 추가": dict(replace=("cabe a quem as patrocina.",
                                            "cabe a quem as patrocina. Aplica-se também a anúncios digitais.")),
            "예외·조건 추가": dict(replace=("É proibida toda publicidade enganosa ou abusiva.",
                                       "É proibida toda publicidade enganosa ou abusiva, salvo autorização expressa.")),
            "숫자 변경": dict(replace=("Lei nº 11.989, de 2009", "Lei nº 11.989, de 2010")),
            "부정어 추가": dict(replace=("É proibida toda publicidade", "Não é proibida toda publicidade")),
            "문장 삭제": dict(replace=(art37[3], "")),
            "순서 변경": dict(edit=lambda b: b.replace(html.escape(art37[1], quote=False), "@@1@@", 1)
                                       .replace(html.escape(art37[2], quote=False), html.escape(art37[1], quote=False), 1)
                                       .replace("@@1@@", html.escape(art37[2], quote=False), 1)),
        }
        expected = {"같은 줄 끝에 문장 추가": ["CDC-38"], "숫자 변경": ["CDC-30-31"]}
        for label, kwargs in cases.items():
            with self.subTest(label):
                if "replace" in kwargs and "\n" in kwargs["replace"][1]:
                    old, new = kwargs.pop("replace")
                    kwargs["edit"] = lambda b, o=old, n=new: b.replace(
                        html.escape(o, quote=False) + "</p>",
                        "</p><p>".join(html.escape(part, quote=False) for part in n.split("\n")) + "</p>", 1)
                cdc = self.cdc(**kwargs)
                self.assertEqual((cdc["status"], cdc["changed_criteria"]),
                                 ("change_detected", expected.get(label, ["CDC-37"])), cdc.get("comparison", {}).get("CDC-37"))
                self.assertNotIn(cdc["changed_criteria"][0], cdc["checked_criteria"])

    def test_menu_html_whitespace_only(self):
        def reformat(body):
            body = body.replace(" enganosa ou abusiva.", "  enganosa<br/>ou&nbsp;abusiva.", 1)
            return body.replace("<p>", "<p class='x'>\n   ").replace("</p>", "  </p>\n")
        cdc = self.cdc(edit=reformat, extra_menu="<nav><a href='#'>Novo menu</a></nav>")
        self.assertEqual((cdc["status"], cdc["changed_criteria"], len(cdc["checked_criteria"])), ("no_change_found", [], 9))

    def test_boundary_not_identified_is_not_no_change(self):
        # 같은 번호로 시작하는 줄이 하나 더 생기면 조항 시작을 하나로 정할 수 없음
        duplicate = self.cdc(edit=lambda b: b + "<p>Art. 37. Nota que repete o número do artigo.</p>")
        self.assertEqual((duplicate["status"], duplicate["unverifiable_criteria"]), ("partial_checked", ["CDC-37"]))
        self.assertNotIn("CDC-37", duplicate["checked_criteria"])
        policies = {key: dict(value) for key, value in cc.POLICIES.items()}
        policies["SRC-CONAR-WEB"]["auto_fetch"] = True  # 내부 테스트 경계(가짜 응답)
        no_scope = page(self.loaded["criteria"], "SRC-CONAR-WEB", CONAR_MARKER,
                        edit=lambda b: b.replace("ANEXO \"U\"", "ANEXO-U-SEM-TITULO", 1))
        result = self.check(self.web(conar=FakeResponse(200, no_scope)), policies=policies)
        conar = self.source(result, "SRC-CONAR-WEB")
        self.assertNotEqual(conar["status"], "no_change_found")
        self.assertIn("CONAR-U-2", conar["unverifiable_criteria"])  # 부속서 U 범위를 못 찾아 항목 경계 식별 불가
        self.assertIn("CONAR-36B", conar["checked_criteria"])


class CoverageTest(Base):
    """발췌가 조항 일부만 담은 경우와 비교 범위 정보가 없는 경우: 조항 전체 변경 없음으로 표시하지 않음."""

    def test_partial_unit(self):
        self.set_coverage({"CDC-06": {"Art. 6": "partial"}})
        extra = lambda b: b.replace("São direitos básicos do consumidor:</p>",
                                    "São direitos básicos do consumidor:</p><p>XIV - inciso de teste fora do excerto;</p>", 1)
        result = self.check(self.web(cdc=FakeResponse(200, self.cdc_page(edit=extra))))
        cdc = self.source(result, "SRC-CDC")
        self.assertEqual((cdc["status"], cdc["partially_checked_criteria"]), ("partial_checked", ["CDC-06"]))
        self.assertNotIn("CDC-06", cdc["checked_criteria"])
        self.assertEqual(result["overall"], "partial")
        self.assertTrue(any("부분" in warning for warning in result["warnings"]))
        changed_line = self.check(self.web(cdc=FakeResponse(200, self.cdc_page(
            edit=extra, replace=("a proteção contra a publicidade enganosa", "a proteção contra a publicidade")))))
        self.assertEqual(self.source(changed_line, "SRC-CDC")["changed_criteria"], ["CDC-06"])
        vanished = self.check(self.web())  # 확보 당시 있던 발췌 밖 문장(가정)이 없어짐 → 변경
        self.assertEqual(self.source(vanished, "SRC-CDC")["changed_criteria"], ["CDC-06"])

    def test_missing_coverage_file_means_partial_only(self):
        self.set_coverage(remove=True)
        result = self.check(self.web())
        cdc = self.source(result, "SRC-CDC")
        self.assertEqual((cdc["status"], cdc["checked_criteria"]), ("partial_checked", []))
        self.assertEqual(len(cdc["partially_checked_criteria"]), 9)
        self.assertTrue(any("comparison_units.json" in warning for warning in result["warnings"]))

    def test_real_comparison_units_match_active_criteria(self):
        data = json.loads((cl.DATA_DIR / cc.COVERAGE_FILE).read_text(encoding="utf-8"))
        loaded = cl.load_criteria()
        partial = set()
        for item in loaded["criteria"]:
            source_id = item["source_id"]
            labels = [label for label, *_ in cc.excerpt_units(item["excerpt"]["text_pt"], cc.UNIT_RULES[source_id],
                                                               cc.POLICIES[source_id]["strip_list_markers"])]
            self.assertEqual(sorted(data["coverage"][item["id"]]), sorted(labels), item["id"])
            partial |= {(item["id"], label) for label, value in data["coverage"][item["id"]].items() if value != "full"}
        self.assertEqual(partial, {("CDC-02-03", "Art. 3"), ("CDC-06", "Art. 6"), ("CDC-60", "Art. 60"),
                                   ("CONAR-27", "Artigo 27"), ("CONAR-U-PRE", "_context")})
        # 원문 텍스트를 담지 않음: 값은 범위 표시뿐
        self.assertTrue(all(value in cc.COVERAGE_VALUES for units in data["coverage"].values() for value in units.values()))


class AdminTest(unittest.TestCase):
    def test_cli_rejects_paths_and_reports_errors(self):
        with mock.patch("builtins.print") as printed:
            self.assertEqual(criteria_admin.main(["build", "../escape", "--version", "v1"]), 1)
        output = printed.call_args[0][0]
        self.assertIn("CRITERIA_INVALID", output)
        self.assertNotIn(str(cl.DATA_ROOT), output)

    def test_status_reads_real_data_without_writing(self):
        before = tree_digest(cl.DATA_DIR)
        state_existed = (cl.DATA_ROOT / cl.STATE_DIR_NAME / cs.CHECK_STATE_FILE).exists()
        with mock.patch.object(socket, "socket", side_effect=AssertionError("네트워크 금지")), \
                mock.patch("builtins.print") as printed:
            self.assertEqual(criteria_admin.main(["status"]), 0)
        result = json.loads(printed.call_args[0][0])
        self.assertTrue(result["criteria_usable"])
        self.assertEqual(result["active"]["active_version"], "base")
        self.assertEqual(tree_digest(cl.DATA_DIR), before)
        self.assertEqual((cl.DATA_ROOT / cl.STATE_DIR_NAME / cs.CHECK_STATE_FILE).exists(), state_existed)
        self.assertEqual(multiprocessing.active_children(), [])


if __name__ == "__main__":
    unittest.main()
