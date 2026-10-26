"""검수 결과 PDF 보고서 검증(모의). 외부 요청·OpenAI 호출 없음. 실행(저장소 루트):

    python -m unittest features.green_claim.tests.test_report -v

검수 결과는 test_review의 가짜 AI·가짜 공식 페이지로 review_service.run_review_request를 실제로 실행해 만듭니다(계약 일치 확인).
가짜 결과로 만든 보고서는 실제 AI 검수 결과가 아닙니다. 문구는 모두 가상 문구입니다.
생성한 PDF는 pypdf로 다시 열어 쪽 수·텍스트·링크·글꼴을 확인합니다(레이아웃의 눈 확인은 별도).
"""
import copy
import io
import json
import multiprocessing
import os
import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from pypdf import PdfReader

from app import create_app
from features.green_claim import criteria_check as cc
from features.green_claim import criteria_loader as cl
from features.green_claim import report_service as rp
from features.green_claim import report_worker as rw
from features.green_claim import review_service as rs
from features.green_claim.criteria_build import KST
from features.green_claim.tests.test_review import BAD_R1_A, BAD_R1_B, BAD_R2, FAILURE_TEXT, Base, item, result_data

GENERATED = datetime(2026, 10, 26, 11, 0, 0, tzinfo=KST)
DISPLAYED = "2026-10-26T10:00:05+09:00"
SECRET = "SEGREDO-TESTE-7781"
LONG_URL = "https://example.com/" + "a" * 1800
TEXT = ("🌱 Produto 100% sustentável e ecológico.\n"
        "Our yarn is eco-friendly <b>bold</b> & <script>alert(1)</script>.\n"
        "\n"
        "  리젠은  친환경 원사입니다. 친환경\n"
        "Cafe\u0301 natural · " + LONG_URL + " " + SECRET)
ITEMS = [
    item("100% sustentável", action="revise_recommended", ids=("CDC-37",), language="pt-BR",
         # 대체 예시는 입력에 있는 사실만 다시 쓴 문장(새 특성·평가를 넣으면 서버가 지움, test_review 참고)
         alternative={"original_text": None, "pt_br_text": "Produto têxtil descrito no texto", "ko_interpretation": "본문에서 설명한 섬유 제품"}),
    item("sustentável e ecológico", action="needs_review", ids=("CONAR-36",), language="pt-BR"),
    item("eco-friendly <b>bold</b> & <script>alert(1)</script>", action="judgment_withheld", ids=(), language="en", unavailable=None),
    item("친환경", occurrence=2, ids=("CDC-37", "CDC-38"), language="ko",
         # 한국어 예시와 해석이 같으면 서버가 해석을 null로 정리(중복 제거)
         alternative={"original_text": "리젠 원사입니다", "pt_br_text": "É o fio Regen",
                      "ko_interpretation": "리젠 원사입니다"}),
]


def payload(review, mode="text", displayed=DISPLAYED, **extra):
    data = {"review": review, "input_mode": mode, "displayed_at": displayed}
    data.update(extra)
    return json.dumps(data).encode("utf-8")  # \uXXXX 이스케이프(짝 없는 서로게이트 검사용 값도 보낼 수 있음)


def pdf_text(pdf):
    reader = PdfReader(io.BytesIO(pdf))
    return reader, "\n".join(page.extract_text() or "" for page in reader.pages)


def squash(text):
    return re.sub(r"\s+", "", text)


def without_footer(flat):
    """쪽 넘김 위치에 끼어드는 바닥글(안내·쪽 번호)을 빼고 본문만 남깁니다."""
    return re.sub(re.escape(squash(rw.FOOTER)) + r"\d+/\d+", "", flat)


class ReportBase(Base):
    def review(self, text=TEXT, items=ITEMS, **kwargs):
        result, _ = self.run_review(text=text, data=result_data(items), **kwargs)
        return result

    def build_inprocess(self, raw):
        """검증은 실제 경로, PDF 생성은 같은 프로세스에서(빠른 확인용). 별도 프로세스 경로는 ProcessTest."""
        data = rp.parse_request(raw)
        return rw.build_pdf({**data, "generated_at": GENERATED.isoformat()})

    def assert_result_invalid(self, review):
        with self.assertRaises(rp.ExtractError) as ctx:
            rp.parse_request(payload(review))
        self.assertEqual(ctx.exception.code, "REPORT_RESULT_INVALID")


class ContractTest(ReportBase):
    def test_real_review_outputs_pass(self):
        variants = {
            "mixed": self.review(),
            "empty": self.review(items=[]),
            "withheld_only": self.review(text="Eco 🌱", items=[item("Eco", action="judgment_withheld", ids=(), language="en", unavailable=None)]),
        }
        with mock.patch.object(rs, "run_criteria_check",
                               side_effect=lambda root, now, opener=None: (cc.criteria_status(root), "status_only_busy")):
            variants["busy"] = self.review()
        for name, review in variants.items():
            with self.subTest(name=name):
                self.assertEqual(set(review), rp.TOP_KEYS)
                data = rp.parse_request(payload(review, mode="file", displayed=None))
                self.assertEqual(data["review"], review)  # 값을 바꾸지 않음
        self.assertEqual(variants["busy"]["criteria"]["sources"][0]["check_status"], rp.NOT_CHECKED_THIS_REQUEST)


class ValidationTest(ReportBase):
    def test_request_shape(self):
        review = self.review()
        cases = [
            (b"{", "REPORT_JSON_INVALID"), (b"\xff", "REPORT_JSON_INVALID"),
            (b"[" * 100_000 + b"]" * 100_000, "REPORT_JSON_INVALID"),  # 과도한 중첩
            (b"[]", "REPORT_FIELDS_INVALID"), (b"{}", "REPORT_FIELDS_INVALID"),
            (payload(review, extra_key=1), "REPORT_FIELDS_INVALID"),
            (payload(review, mode="upload"), "REPORT_FIELDS_INVALID"),
            (payload(review, displayed="2026-10-26 10:00"), "REPORT_FIELDS_INVALID"),
            (payload(review, displayed="2026-13-40T10:00:00+09:00"), "REPORT_FIELDS_INVALID"),
            (payload("not a review"), "REPORT_RESULT_INVALID"),
        ]
        for raw, code in cases:
            with self.subTest(code=code, raw=raw[:40]):
                with self.assertRaises(rp.ExtractError) as ctx:
                    rp.parse_request(raw)
                self.assertEqual(ctx.exception.code, code)

    def test_mutations_rejected(self):
        base = self.review()

        def mutated(change):
            review = copy.deepcopy(base)
            change(review)
            return review

        first = lambda r: r["items"][0]  # noqa: E731
        cases = {
            "missing top key": lambda r: r.pop("limits"),
            "extra top key": lambda r: r.update(signature="x"),
            "extra item key": lambda r: first(r).update(score=1),
            "id order": lambda r: first(r).update(id="R9"),
            "quote mismatch": lambda r: first(r).update(quote="100% sustentavel"),
            "start out of range": lambda r: first(r).update(start=99_999),
            "start bool": lambda r: first(r).update(start=True),
            "occurrence mismatch": lambda r: r["items"][3].update(occurrence=1),
            "occurrences count": lambda r: first(r).update(occurrences_in_text=2),
            "action label": lambda r: first(r).update(action_label_ko="안전"),
            "unknown action": lambda r: first(r).update(action="approved"),
            "judgment without criteria": lambda r: first(r).update(criteria_ids=[]),
            "duplicate criteria id": lambda r: first(r).update(criteria_ids=["CDC-37", "CDC-37"]),
            "ref missing": lambda r: r["criteria_refs"].pop("CDC-38"),
            "ref extra": lambda r: r["criteria_refs"].update(EXTRA=r["criteria_refs"]["CDC-37"]),
            "ref javascript url": lambda r: r["criteria_refs"]["CDC-37"].update(official_url="javascript:alert(1)"),
            "ref url differs from source": lambda r: r["criteria_refs"]["CDC-37"].update(official_url="https://evil.example/"),
            "ref retrieved_at differs": lambda r: r["criteria_refs"]["CDC-37"].update(retrieved_at="2020-01-01T00:00:00+09:00"),
            "translation official": lambda r: r["criteria_refs"]["CDC-37"].update(translation_official=True),
            "excerpt too long": lambda r: r["criteria_refs"]["CDC-37"].update(excerpt_pt="x" * 20_001),
            "summary total": lambda r: r["summary"].update(total=9),
            "summary by_action": lambda r: r["summary"]["by_action"].update(needs_review=0),
            "no items message with items": lambda r: r["summary"].update(no_items_message="검토 대상 표현이 발견되지 않았습니다."),
            "char_count": lambda r: r.update(char_count=1),
            "carriage return": lambda r: r.update(text=r["text"].replace("\n", "\r", 1)),
            "position unit": lambda r: r.update(position_unit="utf16"),
            "lone surrogate": lambda r: first(r).update(reason_ko="\ud800"),
            "empty reason": lambda r: first(r).update(reason_ko="  "),
            "content hash": lambda r: r["criteria"].update(content_hash="not-a-hash"),
            "check mode": lambda r: r["criteria"].update(check_mode="skipped"),
            "not checked with time": lambda r: r["criteria"].update(check_mode="status_only_error"),
            "source url scheme": lambda r: r["criteria"]["sources"][0].update(official_url="ftp://x.example/a"),
            "alternative empty": lambda r: first(r).update(alternative={"original_text": None, "pt_br_text": None, "ko_interpretation": "x"}),
            "pt-BR item with original-language sentence": lambda r: first(r)["alternative"].update(original_text="Outra frase"),
            "notices empty": lambda r: r.update(notices=[]),
            "limits bool": lambda r: r["limits"].update(max_chars=True),
        }
        for name, change in cases.items():
            with self.subTest(name=name):
                self.assert_result_invalid(mutated(change))

    def test_size_limits(self):
        text = "a" * 20_000
        review = self.review(text=text, items=[item("a" * 1_000, action="judgment_withheld", ids=(), unavailable=None)])
        rp.parse_request(payload(review))  # 경계값 통과
        too_long = copy.deepcopy(review)
        too_long["text"] += "a"
        too_long["char_count"] += 1
        self.assert_result_invalid(too_long)
        many = copy.deepcopy(review)
        many["items"] = many["items"] * 51
        self.assert_result_invalid(many)


class PdfContentTest(ReportBase):
    def test_content_fonts_and_safety(self):
        review = self.review()
        with mock.patch.object(cl, "_load_active", side_effect=AssertionError("기준을 다시 읽지 않음")), \
                mock.patch.object(cl, "load_criteria", side_effect=AssertionError("기준을 다시 읽지 않음")), \
                mock.patch.object(cc, "check_sources", side_effect=AssertionError("공식 확인을 다시 하지 않음")), \
                mock.patch.object(rs, "_load_ai", side_effect=AssertionError("AI를 다시 부르지 않음")):
            pdf = self.build_inprocess(payload(review, mode="file"))
        reader, text = pdf_text(pdf)
        flat = squash(text)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreaterEqual(len(reader.pages), 2)
        for expected in ("그린클레임문구검수보고서", "브라질대상홍보문구표현위험검토", "사실성", "인증보유", "적법성", "디자인",
                         "수정권고", "검토필요", "판단보류", "sustentável", "Produtotêxtildescritonotexto", "ÉofioRegen",
                         "[U+1F331]", "<b>bold</b>&<script>alert(1)</script>", "대체예시(참고용·원본을수정한것이아님",
                         "홍보물파일에서글자추출·판독후사용자가확인·수정한문구", "2026-10-2610:00:05(한국시간)·이컴퓨터시계기준",
                         "2026-10-2611:00:00(한국시간)·서버시계기준", "법률", "광고자율규제", "한국어번역(비공식)",
                         review["criteria"]["content_hash"], "Café", f"1/{len(reader.pages)}"):
            with self.subTest(expected=expected):
                self.assertIn(squash(expected), flat)
        self.assertNotIn("최신기준", flat)
        # 원문 사본: 번호 표시를 넣은 순서 그대로 원문 글자가 빠짐·중복 없이 이어짐(공백은 줄바꿈 차이 때문에 제외)
        expected_original = []
        starts = {}
        for it in review["items"]:
            starts.setdefault(it["start"], []).append(it["id"])
        for index, char in enumerate(review["text"]):
            expected_original.extend("▶" + item_id for item_id in starts.get(index, []))
            if char == "\U0001F331":
                expected_original.append("[U+1F331]")
            elif char == "\u0301":
                continue  # 화면 표시용으로 e + U+0301 → é 합성(Café)
            elif char == "e" and review["text"][index + 1:index + 2] == "\u0301":
                expected_original.append("é")
            else:
                expected_original.append(char)
        self.assertIn(squash("".join(expected_original)), without_footer(flat))
        self.assertNotIn("\x7f", text)  # 글머리표 등 글꼴에 없는 글자로 그려진 흔적 없음
        # 링크는 http/https만, 스크립트·첨부·실행 동작 없음, 외부 자료 참조 없음
        uris = [annot.get_object()["/A"]["/URI"] for page in reader.pages for annot in page.get("/Annots", []) or []
                if "/A" in annot.get_object()]
        self.assertTrue(uris and all(uri.startswith("https://") for uri in uris), uris)
        for token in (b"/JavaScript", b"/JS ", b"/EmbeddedFile", b"/Launch", b"/SubmitForm", b"/ImportData"):
            self.assertNotIn(token, pdf)
        fonts = set()
        for page in reader.pages:
            for font in page["/Resources"]["/Font"].values():
                fonts.add(str(font.get_object()["/BaseFont"]))
        self.assertTrue(any("NanumGothic" in name for name in fonts) and any("Vera" in name for name in fonts), fonts)

    def test_no_items_and_criteria_kept(self):
        review = self.review(items=[])
        review["criteria"]["bundle_version"] = "2026-10-26.1-당시"
        pdf = self.build_inprocess(payload(review, displayed=None))
        _, text = pdf_text(pdf)
        flat = squash(text)
        for expected in ("검토 대상 표현이 발견되지 않았습니다.", "안전하거나 적법하다는 뜻이 아니며", "기준 버전 2026-10-26.1-당시",
                         "검수 결과를 받은 시각", "기록 없음", "문구 직접 입력"):
            with self.subTest(expected=expected):
                self.assertIn(squash(expected), flat)


    def test_observed_failure_case_screen_and_pdf_match(self):
        """관측 실패 사례: 서버가 예시를 지운 결과가 PDF에도 같게 반영(이유·수정 방향 표시, 문제 문장 없음)."""
        bad = [
            item("100% sustentável, totalmente ecológico e não causa nenhum impacto ambiental", action="revise_recommended",
                 language="pt-BR", direction="범위·근거를 밝히고 절대 표현을 빼세요.",
                 alternative={"original_text": BAD_R1_A, "pt_br_text": BAD_R1_B, "ko_interpretation": "입증 가능한 특성이 있는 원단"}),
            item("É a opção mais verde do mercado", language="pt-BR", direction="비교 대상과 기준을 밝히세요.",
                 alternative={"original_text": BAD_R2, "pt_br_text": BAD_R2, "ko_interpretation": "입증되어야 하는 특성이 있는 선택지"}),
        ]
        review = self.review(text=FAILURE_TEXT, items=bad)
        self.assertTrue(all(entry["alternative"] is None for entry in review["items"]))  # 화면이 받는 값
        _, text = pdf_text(self.build_inprocess(payload(review)))
        flat = squash(text)
        for expected in ("범위·근거를밝히고절대표현을빼세요.", "비교대상과기준을밝히세요.", "예시대신위이유와수정방향을참고해주세요.",
                         squash(review["items"][0]["alternative_note_ko"])):
            with self.subTest(expected=expected):
                self.assertIn(squash(expected), flat)
        for sentence in (BAD_R1_A, BAD_R1_B, BAD_R2):
            self.assertNotIn(squash(sentence), flat)
        self.assertNotIn("원문언어예시", flat)

    def test_long_multi_page_report(self):
        text = ("Linha com acentuação: ção ã õ é ú. 한국어 문장입니다. " * 450)[:20_000]
        quote = "acentuação"
        count = len(rs._occurrences(text, quote))
        items = [item(quote, occurrence=n, action=("revise_recommended", "needs_review", "judgment_withheld")[n % 3],
                      ids=() if n % 3 == 2 else ("CDC-37",), reason="이유 " * 650, direction="방향 " * 650, language="pt-BR",
                      unavailable=None if n % 3 == 2 else "근거가 필요함")
                 for n in range(1, min(count, 50) + 1)]
        review = self.review(text=text, items=items)
        started = datetime.now()
        pdf = self.build_inprocess(payload(review))
        seconds = (datetime.now() - started).total_seconds()
        reader, flat = pdf_text(pdf)
        self.assertEqual((len(review["items"]), review["char_count"]), (50, 20_000))
        self.assertGreater(len(reader.pages), 20)
        self.assertIn("R50", flat)
        self.assertLess(len(pdf), rp.MAX_PDF_BYTES)
        print(f"\n[긴 보고서] 항목 50, 원문 20,000자, {len(reader.pages)}쪽, {len(pdf):,}바이트, 같은 프로세스 생성 {seconds:.1f}초")


class RouteTest(ReportBase):
    @classmethod
    def setUpClass(cls):
        cls.client = create_app().test_client()

    def test_success_headers_and_errors(self):
        review = self.review()
        with mock.patch.object(rp, "run_report_worker",
                               side_effect=lambda data, timeout=30: {"status": "ok", "pdf": rw.build_pdf(json.loads(data))}):
            res = self.client.post("/api/green-claim/report", data=payload(review), content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "application/pdf")
        self.assertEqual(res.headers["Content-Disposition"], 'attachment; filename="green_claim_review_report.pdf"')
        self.assertEqual(res.headers["Cache-Control"], "no-store")
        self.assertEqual(res.headers["X-Content-Type-Options"], "nosniff")
        self.assertTrue(res.data.startswith(b"%PDF-"))
        cases = [
            (b"text", "text/plain", 400, "REPORT_JSON_INVALID"),
            (b"{", "application/json", 400, "REPORT_JSON_INVALID"),
            (b" " * (rp.MAX_REQUEST_BYTES + 1), "application/json", 413, "REPORT_REQUEST_TOO_LARGE"),
            (payload({"text": SECRET}), "application/json", 422, "REPORT_RESULT_INVALID"),
        ]
        for raw, kind, status, code in cases:
            with self.subTest(code=code):
                res = self.client.post("/api/green-claim/report", data=raw, content_type=kind)
                body = res.get_json()
                self.assertEqual((res.status_code, body["ok"], body["error"]["code"]), (status, False, code))
                self.assertNotIn(SECRET, res.get_data(as_text=True))
        with mock.patch.object(rp, "build_report", side_effect=RuntimeError("C:\\secret\\path " + SECRET)):
            res = self.client.post("/api/green-claim/report", data=payload(review), content_type="application/json")
        self.assertEqual((res.status_code, res.get_json()["error"]["code"]), (500, "REPORT_FAILED"))
        self.assertNotIn("secret", res.get_data(as_text=True))


class ProcessTest(ReportBase):
    """실제 별도 프로세스(spawn): 성공·시간 초과·예외·동시 실행에서 자식 프로세스가 남지 않는지."""

    def test_spawn_success_timeout_busy_and_cleanup(self):
        review = self.review()
        raw = payload(review)
        with self.assertLogs("features.green_claim", level="WARNING") as logs:
            started = datetime.now()
            pdf = rp.build_report(raw, now=GENERATED)
            seconds = (datetime.now() - started).total_seconds()
            self.assertTrue(pdf.startswith(b"%PDF-"))
            self.assertEqual(multiprocessing.active_children(), [])
            with self.assertRaises(rp.ExtractError) as ctx:
                rp.build_report(raw, timeout=0.001)
            self.assertEqual(ctx.exception.code, "REPORT_TIMEOUT")
            self.assertEqual(multiprocessing.active_children(), [])
            rp._slots.acquire()
            try:
                with self.assertRaises(rp.ExtractError) as ctx:
                    rp.build_report(raw)
                self.assertEqual(ctx.exception.code, "REPORT_BUSY")
            finally:
                rp._slots.release()
            with self.assertRaises(rp.ExtractError):
                rp.parse_request(payload({"text": SECRET}))
        joined = "\n".join(logs.output)
        self.assertNotIn(SECRET, joined)
        self.assertNotIn("sustentável", joined)
        self.assertTrue(all("code=" in line for line in logs.output), logs.output)
        print(f"\n[별도 프로세스] 기본 보고서 생성 {seconds:.1f}초(프로세스 시작 포함)")

    def test_worker_errors(self):
        sent = []

        def run_with(raw):
            sent.clear()
            in_conn = mock.Mock(recv_bytes=mock.Mock(return_value=raw))
            out_conn = mock.Mock(send=sent.append)
            rw.run(in_conn, out_conn, None)
            return sent[0]

        job = json.dumps({**json.loads(payload(self.review())), "generated_at": GENERATED.isoformat()}).encode("utf-8")
        with mock.patch.object(rw, "build_pdf", side_effect=RuntimeError("C:\\secret " + SECRET)):
            self.assertEqual(run_with(job), {"status": "error", "code": "REPORT_FAILED"})
        with mock.patch.dict(rw.KO_FONTS, {"regular": Path(tempfile.gettempdir()) / "no_such_font.ttf"}):
            self.assertEqual(run_with(job), {"status": "error", "code": "REPORT_DEPENDENCY_MISSING"})
        self.assertEqual(run_with(job)["status"], "ok")
        for bad in ({"status": "error", "code": "SOMETHING"}, {"status": "ok", "pdf": b"not pdf"}, "x"):
            with self.subTest(bad=bad):
                with mock.patch.object(rp, "run_report_worker", return_value=bad):
                    with self.assertRaises(rp.ExtractError) as ctx:
                        rp.build_report(payload(self.review()))
                    self.assertEqual(ctx.exception.code, "REPORT_FAILED")
        with mock.patch.object(rp, "run_report_worker", return_value={"status": "ok", "pdf": b"%PDF-" + b"0" * rp.MAX_PDF_BYTES}):
            with self.assertRaises(rp.ExtractError) as ctx:
                rp.build_report(payload(self.review()))
            self.assertEqual(ctx.exception.code, "REPORT_OUTPUT_TOO_LARGE")

    def test_no_files_written(self):
        review = self.review()
        root = Path(__file__).resolve().parents[1]
        before = {p for p in root.rglob("*") if "__pycache__" not in p.parts}
        temp_before = set(os.listdir(tempfile.gettempdir()))
        self.build_inprocess(payload(review))
        after = {p for p in root.rglob("*") if "__pycache__" not in p.parts}
        self.assertEqual(after, before)
        new_temp = set(os.listdir(tempfile.gettempdir())) - temp_before
        self.assertFalse([name for name in new_temp if name.lower().endswith(".pdf")], new_temp)


if __name__ == "__main__":
    unittest.main()
