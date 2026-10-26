"""검수 → 결과 → PDF 보고서 서버 통합 확인(모의). 외부 요청·OpenAI 호출 없음. 실행(저장소 루트):

    python -m unittest features.green_claim.tests.test_review_report_flow -v

실제 Flask 라우트(POST /api/green-claim/review → POST /api/green-claim/report)와 실제 review_service·report_service·
별도 프로세스 PDF 생성을 그대로 통과합니다. 외부 경계만 모의합니다: 공통 generate_structured 자리의 가짜 AI,
공식 기준 페이지 조회의 가짜 응답(test_review와 같은 FakeWeb, 실제 소켓 차단), 기준 확인 상태를 쓸 임시 data 폴더.
가짜 AI 결과는 실제 검수 품질·번역 검증이 아니며 문구는 모두 가상 문구입니다(실제 제품 성능 주장 아님).
"""
import functools
import io
import json
import logging
import re
import unittest
from pathlib import Path
from unittest import mock

from pypdf import PdfReader

from app import create_app
from common import errors
from features.green_claim import criteria_check as cc
from features.green_claim import criteria_loader as cl
from features.green_claim import report_service as rp
from features.green_claim import report_worker as rw
from features.green_claim import review_service as rs
from features.green_claim.tests.test_review import Base, FakeResult, FakeSchema, item, result_data

# 가상 사례 A(절대적·포괄적 표현, 포르투갈어+한국어). docs/worklogs/kim_minjeong 실제 1회 테스트 계획의 사례 A와 같은 문구
CASE_A = "Nosso fio é 100% sustentável e não causa nenhum impacto ambiental. 가장 친환경적인 원사입니다."
FAKE_ITEMS_A = [
    item("100% sustentável", action="revise_recommended", ids=("CDC-37", "CONAR-U-1"), language="pt-BR",
         alternative={"original_text": None, "pt_br_text": "Nosso fio é descrito neste texto",
                      "ko_interpretation": "이 글에서 설명하는 우리 원사"}),
    item("não causa nenhum impacto ambiental", action="needs_review", ids=("CONAR-U-1",), language="pt-BR"),
    item("가장 친환경적인", action="judgment_withheld", ids=(), language="ko", unavailable=None),
]
FRAGMENTS = ("Nosso fio", "nenhum impacto", "가장 친환경적인 원사", "descrito neste texto")  # 로그·파일에 남으면 안 되는 사용자·AI 문구


def squash(text):
    return re.sub(r"\s+", "", text)


def real_state_snapshot():
    """실제 data/criteria_state·criteria_work의 (상대 경로, 크기, 수정 시각). 파일 내용은 읽지 않고 바꾸지 않습니다."""
    snapshot = {}
    for name in ("criteria_state", "criteria_work"):
        base = cl.DATA_ROOT / name
        if base.exists():
            for p in base.rglob("*"):
                if p.is_file():
                    info = p.stat()
                    snapshot[str(p.relative_to(cl.DATA_ROOT))] = (info.st_size, info.st_mtime_ns)
    return snapshot


class ReviewReportFlowTest(Base):
    @classmethod
    def setUpClass(cls):
        cls.client = create_app().test_client()

    def setUp(self):
        super().setUp()  # 임시 data 폴더·실제 소켓 차단·가짜 공식 페이지(self.web)
        self.real_before = real_state_snapshot()
        self.ai_calls = []
        self.web_calls = []

        def generate(**kwargs):
            self.ai_calls.append(json.loads(kwargs["input_text"])["text_to_review"])
            if getattr(self, "ai_error", None):
                raise self.ai_error
            return FakeResult(result_data(FAKE_ITEMS_A))

        def opener(url, timeout):
            self.web_calls.append(url)
            return self.web(url, timeout)

        real = rs.run_review_request
        # 실제 라우트가 부르는 실제 검수 함수에 테스트 경계(임시 data 폴더·가짜 공식 페이지)만 넘김
        for patcher in (mock.patch.object(rs, "_load_ai", return_value=(generate, FakeSchema)),
                        mock.patch.object(rs, "run_review_request", functools.partial(real, root=self.root, opener=opener))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def review(self, text):
        return self.client.post("/api/green-claim/review", data=json.dumps({"text": text}), content_type="application/json")

    def report(self, review, mode="text"):
        body = {"review": review, "input_mode": mode, "displayed_at": "2026-10-26T10:00:05+09:00"}
        return self.client.post("/api/green-claim/report", data=json.dumps(body), content_type="application/json")

    def test_review_then_pdf_without_new_ai_or_criteria_calls(self):
        records = []
        handler = logging.Handler()
        handler.emit = records.append
        logging.getLogger().addHandler(handler)
        self.addCleanup(logging.getLogger().removeHandler, handler)

        res = self.review(CASE_A)
        self.assertEqual(res.status_code, 200, res.get_data(as_text=True)[:200])
        data = res.get_json()["data"]
        self.assertEqual((len(self.ai_calls), self.ai_calls[0]), (1, CASE_A))  # AI 1회, 재시도 없음
        web_after_review = len(self.web_calls)
        self.assertEqual(web_after_review, 2)  # CDC robots.txt·본문, CONAR 보류
        self.assertFalse(any("conar" in url for url in self.web_calls))
        self.assertEqual([it["id"] for it in data["items"]], ["R1", "R2", "R3"])

        # PDF: 기준 로드·공식 확인·AI를 다시 부르면 실패하도록 막은 상태에서 실제 라우트·별도 프로세스 생성
        with mock.patch.object(cl, "_load_active", side_effect=AssertionError("기준 재로드")), \
                mock.patch.object(cl, "load_criteria", side_effect=AssertionError("기준 재로드")), \
                mock.patch.object(cc, "check_sources", side_effect=AssertionError("공식 확인 재실행")):
            pdf_res = self.report(data)
        self.assertEqual(pdf_res.status_code, 200, pdf_res.get_data()[:200])
        self.assertEqual(pdf_res.mimetype, "application/pdf")
        self.assertEqual(pdf_res.headers["Content-Disposition"], 'attachment; filename="green_claim_review_report.pdf"')
        self.assertEqual((len(self.ai_calls), len(self.web_calls)), (1, web_after_review))

        # 화면에 쓰이는 검수 응답과 PDF의 원문·항목·기준 버전·해시 일치
        reader = PdfReader(io.BytesIO(pdf_res.data))
        flat = squash("\n".join(page.extract_text() or "" for page in reader.pages))
        flat = re.sub(re.escape(squash(rw.FOOTER)) + r"\d+/\d+", "", flat)
        criteria = data["criteria"]
        expected = [criteria["bundle_version"], criteria["content_hash"], "2026-10-2610:00:05(한국시간)"]
        expected += [it["id"] + "·" + it["action_label_ko"] for it in data["items"]] + [it["quote"] for it in data["items"]]
        expected += [f"{cid}·" for cid in data["criteria_refs"]]
        for value in expected:
            with self.subTest(value=value):
                self.assertIn(squash(value), flat)
        marked = "".join(("".join("▶" + it["id"] for it in data["items"] if it["start"] == i)) + ch
                         for i, ch in enumerate(data["text"]))
        self.assertIn(squash(marked), flat)  # 원문 사본: 번호 표시를 넣은 자리 외에는 원문 그대로

        # 결과를 바꿔 보내면 거부(보충·재생성 없음)
        tampered = json.loads(json.dumps(data))
        tampered["items"][0]["quote"] = "100% verde"
        bad = self.report(tampered)
        self.assertEqual((bad.status_code, bad.get_json()["error"]["code"]), (422, "REPORT_RESULT_INVALID"))
        self.assertEqual(len(self.ai_calls), 1)

        # 비저장: 로그·임시 data 폴더·저장소 기능 폴더에 사용자·AI 문구 없음
        logged = "\n".join(record.getMessage() for record in records)
        stored = b"".join(p.read_bytes() for p in Path(self.root).rglob("*") if p.is_file() and "brazil_claim_criteria" not in p.parts)
        for fragment in FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, logged)
                self.assertNotIn(fragment.encode("utf-8"), stored)
        # 실제 data 폴더는 이 테스트에서 쓰지 않음: 처음부터 비어 있다고 가정하지 않고 실행 전후 목록을 비교(내용은 읽지 않음)
        self.assertEqual(real_state_snapshot(), self.real_before)
        written = [p for p in Path(self.root).rglob("*") if p.is_file() and "brazil_claim_criteria" not in p.parts]
        self.assertTrue(any(p.name == "check_state.json" for p in written))  # 확인 상태는 임시 data 폴더에만 생김

    def test_ai_failure_returns_fixed_error_once(self):
        self.ai_error = errors.AITimeoutError()
        res = self.review(CASE_A)
        body = res.get_json()
        self.assertEqual((res.status_code, body["ok"], body["error"]["code"]), (504, False, "AI_TIMEOUT"))
        self.assertEqual(len(self.ai_calls), 1)  # 자동 재시도 없음
        self.assertNotIn("Nosso", res.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
