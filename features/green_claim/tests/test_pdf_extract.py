"""일반 PDF 텍스트 추출 검증. 외부 요청·OpenAI 호출 없음. 실행(저장소 루트):

    python -m unittest features.green_claim.tests.test_pdf_extract -v

테스트 PDF는 표준 라이브러리로 만든 가상 문서입니다(Helvetica, WinAnsi: 영어·포르투갈어).
한국어 PDF는 이 방식으로 만들기 어려워 브라우저 확인에서 별도로 검증합니다.
실제 추출은 별도 프로세스(spawn)로 실행되므로 일부 테스트는 몇 초 걸립니다.
"""
import io
import multiprocessing
import unittest
from unittest import mock

from pypdf import PdfReader, PdfWriter
from werkzeug.datastructures import FileStorage

from app import create_app
from features.green_claim import pdf_worker, service


def _pdf_string(text):
    raw = text.encode("cp1252")
    return b"(" + raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def make_pdf(pages, pad=0):
    """pages: 페이지별 줄 목록(list[str]) 또는 None(텍스트 없이 도형만 있는 페이지).
    pad: 참조되지 않는 패딩 스트림 길이(파일 크기 맞추기용)."""
    objects = []

    def add(body):
        objects.append(body)
        return len(objects)

    catalog = add(None)
    pages_obj = add(None)
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    kids = []
    for lines in pages:
        if lines is None:
            content = b"0.85 g 72 500 200 200 re f"
        else:
            content = b"BT /F1 11 Tf 14 TL 72 760 Td " + b" ".join(_pdf_string(line) + b" Tj T*" for line in lines) + b" ET"
        stream = add(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
        kids.append(add(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] "
                        b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>" % (pages_obj, font, stream)))
    objects[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_obj
    objects[pages_obj - 1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
        b" ".join(b"%d 0 R" % k for k in kids), len(kids))
    if pad:
        add(b"<< /Length %d >>\nstream\n" % pad + b" " * pad + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, catalog, xref)
    return bytes(out)


def make_pdf_of_size(target, pages):
    """패딩 길이를 조절해 정확히 target 바이트인 PDF를 만듭니다(xref 오프셋이 고정 폭이라 크기는 패딩에 비례)."""
    pad = 1
    for _ in range(5):
        data = make_pdf(pages, pad=pad)
        if len(data) == target:
            return data
        pad += target - len(data)
    raise AssertionError("크기 맞추기 실패")


def encrypt(data):
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
    writer.encrypt("", "owner", algorithm="RC4-128")  # 열기 암호 없이 권한 암호만 있는 PDF
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


PT = "Fabricado com resíduos têxteis reciclados. Ação, coração, não."
EN = "Made with recycled textile waste."


class BuildResultTest(unittest.TestCase):
    """build_result 단위 확인(모의 입력)."""

    def test_separator_counts_and_ranges(self):
        r = service.build_result({"status": "ok", "page_count": 3, "pages": ["ab", "   ", "cd"]})
        self.assertEqual(r["text"], "ab\n\ncd")
        self.assertEqual(r["char_count"], 6)
        self.assertEqual([p["status"] for p in r["pages"]], ["text", "no_text", "text"])
        self.assertEqual((r["pages"][0]["char_start"], r["pages"][0]["char_end"]), (0, 2))
        self.assertEqual((r["pages"][2]["char_start"], r["pages"][2]["char_end"]), (4, 6))
        self.assertEqual(r["pages_without_text"], [2])
        self.assertFalse(r["all_pages_have_text"])
        self.assertIn(service.NOTICE_MISSING, r["notices"])

    def test_char_limit_boundary_includes_separator(self):
        ok = service.build_result({"status": "ok", "page_count": 2, "pages": ["a" * 9999, "b" * 9999]})
        self.assertEqual(ok["char_count"], 20000)
        with self.assertRaises(service.ExtractError) as ctx:
            service.build_result({"status": "ok", "page_count": 2, "pages": ["a" * 10000, "b" * 9999]})
        self.assertEqual(ctx.exception.code, "TEXT_TOO_LONG")

    def test_code_points_not_utf16(self):
        r = service.build_result({"status": "ok", "page_count": 1, "pages": ["😀가"]})
        self.assertEqual(r["char_count"], 2)

    def test_page_error_and_all_errors(self):
        r = service.build_result({"status": "ok", "page_count": 2, "pages": [None, "ok"]})
        self.assertEqual(r["pages"][0]["status"], "error")
        self.assertEqual(r["pages_without_text"], [1])
        with self.assertRaises(service.ExtractError) as ctx:
            service.build_result({"status": "ok", "page_count": 2, "pages": [None, None]})
        self.assertEqual(ctx.exception.code, "EXTRACT_FAILED")
        with self.assertRaises(service.ExtractError) as ctx:
            service.build_result({"status": "ok", "page_count": 2, "pages": ["", " \n"]})
        self.assertEqual(ctx.exception.code, "PDF_NO_TEXT")

    def test_worker_error_code_passthrough(self):
        with self.assertRaises(service.ExtractError) as ctx:
            service.build_result({"status": "error", "code": "PDF_ENCRYPTED"})
        self.assertEqual(ctx.exception.code, "PDF_ENCRYPTED")
        with self.assertRaises(service.ExtractError) as ctx:
            service.build_result({"status": "error", "code": "UNKNOWN"})
        self.assertEqual(ctx.exception.code, "EXTRACT_FAILED")


class WorkerTest(unittest.TestCase):
    """pdf_worker.extract를 현재 프로세스에서 직접 확인(실제 pypdf)."""

    def test_order_and_languages(self):
        r = pdf_worker.extract(make_pdf([["Page one", EN], ["Page two", PT], ["Page three"]]), 20)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["page_count"], 3)
        self.assertIn("Page one", r["pages"][0])
        self.assertIn(EN, r["pages"][0])
        self.assertIn(PT, r["pages"][1])
        self.assertIn("Page three", r["pages"][2])

    def test_damaged_and_encrypted(self):
        good = make_pdf([["x"]])
        self.assertEqual(pdf_worker.extract(b"%PDF-1.4\n" + b"\x00garbage" * 50, 20)["code"], "PDF_DAMAGED")
        self.assertEqual(pdf_worker.extract(good[: len(good) // 3], 20)["status"] in ("error", "ok"), True)
        self.assertEqual(pdf_worker.extract(encrypt(good), 20)["code"], "PDF_ENCRYPTED")

    def test_page_limit(self):
        self.assertEqual(pdf_worker.extract(make_pdf([["p"]] * 20), 20)["page_count"], 20)
        self.assertEqual(pdf_worker.extract(make_pdf([["p"]] * 21), 20)["code"], "PDF_TOO_MANY_PAGES")

    def test_page_exception_marked(self):
        with mock.patch("pypdf.PageObject.extract_text", side_effect=RuntimeError("boom")):
            r = pdf_worker.extract(make_pdf([["a"], ["b"]]), 20)
        self.assertEqual(r["pages"], [None, None])


class ProcessTest(unittest.TestCase):
    """별도 프로세스 실행·시간 초과·정리(실제 spawn)."""

    def test_extract_pdf_real_process(self):
        r = service.extract_pdf("promo.PDF", make_pdf([["Hello", EN], None, [PT]]))
        self.assertEqual(r["page_count"], 3)
        self.assertEqual(r["pages_without_text"], [2])
        self.assertIn(PT, r["text"])
        start, end = r["pages"][2]["char_start"], r["pages"][2]["char_end"]
        self.assertIn(PT, r["text"][start:end])
        self.assertEqual(multiprocessing.active_children(), [])

    def test_timeout_terminates_process(self):
        with mock.patch.object(service.logger, "warning") as warn:
            with self.assertRaises(service.ExtractError) as ctx:
                service.extract_pdf("a.pdf", make_pdf([["x"]]), timeout=0.05)
        self.assertEqual(ctx.exception.code, "EXTRACT_TIMEOUT")
        warn.assert_called_once()
        self.assertNotIn("x", str(warn.call_args))  # 로그에 문서 내용 없음(code만)
        self.assertEqual(multiprocessing.active_children(), [])

    def test_busy_when_slots_taken(self):
        taken = [service._slots.acquire(blocking=False) for _ in range(service.MAX_CONCURRENT_EXTRACTIONS)]
        try:
            self.assertTrue(all(taken))
            with self.assertRaises(service.ExtractError) as ctx:
                service.run_worker(make_pdf([["x"]]))
            self.assertEqual(ctx.exception.code, "EXTRACT_BUSY")
        finally:
            for _ in taken:
                service._slots.release()

    def test_long_text_not_truncated(self):
        line = "Texto reciclado " * 6  # 96자
        pages = [[line] * 50 for _ in range(5)]  # 약 24,000자 이상
        with self.assertRaises(service.ExtractError) as ctx:
            service.extract_pdf("long.pdf", make_pdf(pages))
        self.assertEqual(ctx.exception.code, "TEXT_TOO_LONG")


class RouteTest(unittest.TestCase):
    """Flask 테스트 클라이언트로 요청·응답 확인."""

    @classmethod
    def setUpClass(cls):
        cls.client = create_app().test_client()

    def post(self, files=None, data=None, **kw):
        form = dict(data or {})
        for name, filename, content in files or []:
            form.setdefault(name, []).append(FileStorage(io.BytesIO(content), filename=filename))
        return self.client.post("/api/green-claim/extract", data=form, content_type="multipart/form-data", **kw)

    def assertError(self, resp, code, status):
        body = resp.get_json()
        self.assertEqual(resp.status_code, status, body)
        self.assertEqual(body["ok"], False)
        self.assertEqual(body["error"]["code"], code)
        self.assertEqual(set(body["error"]), {"code", "message"})
        for leak in ("Traceback", "\\", "site-packages", "pypdf", "Error("):
            self.assertNotIn(leak, body["error"]["message"])

    def test_success_shape(self):
        resp = self.post([("promo_file", "promo.pdf", make_pdf([["Linha um", PT], None]))])
        body = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(body["ok"])
        data = body["data"]
        self.assertEqual(set(data), {"text", "char_count", "page_count", "pages", "pages_without_text",
                                     "all_pages_have_text", "notices", "limits"})
        self.assertIn(PT, data["text"])
        self.assertEqual(data["page_count"], 2)
        self.assertEqual(data["pages_without_text"], [2])
        self.assertFalse(data["all_pages_have_text"])
        self.assertEqual(data["limits"]["max_bytes"], 10_000_000)

    def test_request_errors(self):
        self.assertError(self.client.post("/api/green-claim/extract", json={}), "REQUEST_INVALID", 400)
        self.assertError(self.post(data={"other": "x"}), "FILE_MISSING", 400)
        pdf = make_pdf([["x"]])
        self.assertError(self.post([("promo_file", "a.pdf", pdf), ("promo_file", "b.pdf", pdf)]), "FILE_MULTIPLE", 400)
        self.assertError(self.post([("promo_file", "a.pdf", b"")]), "FILE_EMPTY", 400)

    def test_type_checks(self):
        pdf = make_pdf([["x"]])
        self.assertError(self.post([("promo_file", "a.docx", pdf)]), "FILE_TYPE_UNSUPPORTED", 415)
        self.assertError(self.post([("promo_file", "a", pdf)]), "FILE_TYPE_UNSUPPORTED", 415)
        self.assertError(self.post([("promo_file", "fake.pdf", b"hello, this is text")]), "PDF_INVALID", 422)
        self.assertError(self.post([("promo_file", "d.pdf", b"%PDF-1.7\n" + b"\x00" * 300)]), "PDF_DAMAGED", 422)
        self.assertError(self.post([("promo_file", "e.pdf", encrypt(pdf))]), "PDF_ENCRYPTED", 422)
        self.assertError(self.post([("promo_file", "n.pdf", make_pdf([None, None]))]), "PDF_NO_TEXT", 422)
        self.assertError(self.post([("promo_file", "p.pdf", make_pdf([["p"]] * 21))]), "PDF_TOO_MANY_PAGES", 422)
        self.assertEqual(self.post([("promo_file", "p.pdf", make_pdf([["p"]] * 20))]).status_code, 200)

    def test_size_boundary_and_memory_stream(self):
        exact = make_pdf_of_size(10_000_000, [["Size boundary"]])
        self.assertEqual(len(exact), 10_000_000)
        # Werkzeug 기본 스풀링(임시 파일) 함수가 호출되면 실패하도록 막아 둠
        with mock.patch("werkzeug.formparser.default_stream_factory", side_effect=AssertionError("spooled")):
            resp = self.post([("promo_file", "big.pdf", exact)])
        self.assertEqual(resp.status_code, 200, resp.get_json())
        self.assertIn("Size boundary", resp.get_json()["data"]["text"])
        self.assertError(self.post([("promo_file", "big.pdf", exact + b"\n")]), "FILE_TOO_LARGE", 413)
        huge = exact + b" " * (70 * 1024)  # 요청 본문 상한 초과
        self.assertError(self.post([("promo_file", "huge.pdf", huge)]), "FILE_TOO_LARGE", 413)


if __name__ == "__main__":
    unittest.main()
