"""홈 일일 브리핑 PDF 테스트. 외부 요청이 없습니다(service 함수를 가상 데이터로 바꿈).

실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_home -v

뉴스·환율·전시회 값은 모두 가상(fixture)이며 실제 사용자 데이터가 아닙니다.
PDF 글자·링크·쪽 수는 requirements의 pypdf로 추출해 확인합니다. 눈으로 본 배치는 검증 기록을 참고하세요.
"""
import sys
import unittest
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from unittest import mock

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402
from features.home import buyer_time, report, service  # noqa: E402

HOLIDAYS = {
    2026: {"source": "brasilapi", "fetched_at": "2026-10-25T09:00:00+09:00",
           "holidays": [{"date": "2026-11-02", "name": "Finados"}, {"date": "2026-11-15", "name": "Proclamação da República"}]},
    2027: {"source": "brasilapi", "fetched_at": "2026-10-25T09:00:00+09:00", "holidays": [{"date": "2027-01-01", "name": "Confraternização mundial"}]},
}


def holidays(year):
    return HOLIDAYS.get(year, {"source": "none", "fetched_at": None, "holidays": []})


def fx_ok():
    base = {"fetched_at": "2026-10-25T09:00:00+09:00"}
    return {
        "usd_krw": dict(base, pair="USD/KRW", source="koreaexim", source_name="한국수출입은행 매매기준율", status="ok",
                        rate=1405.2, date="2026-10-23", previous={"rate": 1400.9, "date": "2026-10-22"}, change_pct=0.31),
        "usd_brl": dict(base, pair="USD/BRL", source="bcb_ptax", source_name="Banco Central do Brasil PTAX 매도", status="ok",
                        rate=5.0377, date="2026-10-23", previous={"rate": 5.0383, "date": "2026-10-22"}, change_pct=-0.01),
        "brl_krw": {"rate": 278.9368, "derived": True, "method": "USD/KRW ÷ USD/BRL",
                    "usd_krw_date": "2026-10-23", "usd_brl_date": "2026-10-23"},
    }


def news_item(i, origin="google", summary=None, title=None):
    item = {"id": f"n{i}", "title": title or f"TEST Indústria têxtil amplia Produção em São Paulo nº {i}",
            "url": f"https://example.com/news/{i}?a=1&b=2", "media": "TEST Jornal", "media_domain": "example.com",
            "published_at": f"2026-10-{24 - i % 3:02d}T1{i % 10}:00:00+00:00", "origin": origin, "lang": "pt-BR"}
    if origin == "kotra":
        item.update(lang="ko", published_at="2026-07-27", media="KOTRA 해외시장뉴스 · 상파울루무역관", media_domain="dream.kotra.or.kr")
    if summary:
        item["summary_ko"] = summary
    return item


def news_ok():
    items = [news_item(1, summary="상파울루 섬유업계, 생산 확대"), news_item(2, "abit", summary="ABIT, 수출 지원 프로그램 발표"),
             news_item(3, "kotra", title="TEST 브라질 섬유 시장 동향 <특집> & 전망"), news_item(4), news_item(5), news_item(6),
             news_item(7, title="TEST " + "Confecções brasileiras apostam em recuperação das vendas " * 4), news_item(8), news_item(9), news_item(10)]
    media = {k: {"status": "ok", "fetched_at": "2026-10-25T09:00:00+09:00", "count": 3, "stale": False,
                 "collected": 4, "after_filter": 3} for k in ("kotra", "google", "abit")}
    return {"items": items, "media": media, "summary": {"pending": 0}}


def fairs_ok(limit=3):
    def fair(name, start, end, d_day, verified):
        return {"name": name, "start": start, "end": end, "d_day": d_day, "status": "upcoming", "city": "Americana/SP",
                "venue": "TEST Venue", "focus": "TEST", "note": None, "url": "https://example.com/" + name, "source": "TEST 출처",
                "verified": verified, "checked_at": "2026-10-25"}
    return {"fairs": [fair("Inspiramais", "2027-01-26", "2027-01-27", "D-93", False),
                      fair("Tecnotêxtil Brasil 2027", "2027-04-27", "2027-04-30", "D-184", True),
                      fair("Febratex Summit 2027", "2027-08-24", "2027-08-26", "D-303", True)][:limit],
            "data_checked_at": "2026-10-25", "total_upcoming": 3, "invalid_count": 0}


NOW = datetime(2026, 10, 26, 1, 0, tzinfo=timezone.utc)  # 서울 10/26(월) 10:00, 상파울루 10/25(일) 22:00


class ReportTestBase(unittest.TestCase):
    def setUp(self):
        patches = {"get_holidays": holidays, "get_fx": fx_ok, "get_news": news_ok, "get_upcoming_fairs": fairs_ok}
        for name, fn in patches.items():
            p = mock.patch.object(service, name, side_effect=fn)
            self.mocks = getattr(self, "mocks", {})
            self.mocks[name] = p.start()
            self.addCleanup(p.stop)


class BuyerTimeTests(unittest.TestCase):
    def at(self, iso, city="America/Sao_Paulo"):
        return buyer_time.buyer_time(city, datetime.fromisoformat(iso), holidays)

    def test_cases_match_screen_rules(self):
        b = self.at("2026-10-26T01:00:00+00:00")
        self.assertEqual((b["status"], buyer_time.format_day_time(b["local"]), buyer_time.format_day_time(b["seoul"])),
                         ("주말", "10/25(일) 22:00", "10/26(월) 10:00"))
        self.assertEqual(buyer_time.format_day_time(b["next_start"]["seoul"]), "10/26(월) 21:00")
        m = self.at("2026-10-26T01:00:00+00:00", "America/Manaus")
        self.assertEqual((buyer_time.format_day_time(m["local"]), buyer_time.format_day_time(m["next_start"]["seoul"])),
                         ("10/25(일) 21:00", "10/26(월) 22:00"))
        self.assertEqual(self.at("2026-10-27T13:00:00+00:00")["status"], "업무시간")
        self.assertIsNone(self.at("2026-10-27T13:00:00+00:00")["next_start"])
        self.assertEqual(self.at("2026-10-27T12:00:00+00:00")["status"], "업무시간")       # 09:00
        self.assertEqual(self.at("2026-10-27T20:59:00+00:00")["status"], "업무시간")       # 17:59
        b18 = self.at("2026-10-27T21:00:00+00:00")                                         # 18:00
        self.assertEqual((b18["status"], buyer_time.format_day_time(b18["next_start"]["seoul"])), ("업무시간 외", "10/28(수) 21:00"))
        b8 = self.at("2026-10-27T11:00:00+00:00")                                          # 08:00
        self.assertEqual(buyer_time.format_day_time(b8["next_start"]["seoul"]), "10/27(화) 21:00")
        h = self.at("2026-11-02T13:00:00+00:00")
        self.assertEqual((h["status"], buyer_time.format_day_time(h["next_start"]["seoul"])), ("공휴일", "11/3(화) 21:00"))
        y = self.at("2026-12-31T22:00:00+00:00")
        self.assertEqual(buyer_time.format_day_time(y["next_start"]["seoul"]), "1/4(월) 21:00")
        self.assertTrue(y["next_start"]["holidays_known"])

    def test_holidays_within_7_days(self):
        b = self.at("2026-10-26T01:00:00+00:00")  # 상파울루 10/25 → 11/2는 8일 후라 제외
        self.assertEqual(b["holidays"], [])
        c = self.at("2026-10-27T13:00:00+00:00")  # 10/27 → 11/2는 6일 후
        self.assertEqual([(h["name"], h["days"], h["weekend"]) for h in c["holidays"]], [("Finados", 6, False)])

    def test_unknown_holidays(self):
        b = buyer_time.buyer_time("America/Sao_Paulo", datetime.fromisoformat("2026-11-02T13:00:00+00:00"),
                                  lambda year: {"source": "none", "fetched_at": None, "holidays": []})
        self.assertEqual(b["status"], "업무시간")  # 공휴일 없이 판단
        self.assertEqual(b["holiday_info"][2026]["source"], "none")


class CollectTests(ReportTestBase):
    def test_collect_normal(self):
        data = report.collect("America/Sao_Paulo", NOW)
        self.assertEqual(data["failures"], [])
        self.assertEqual(len(data["news"]["items"]), report.NEWS_LIMIT)
        self.assertEqual(data["news"]["total"], 10)
        self.mocks["get_upcoming_fairs"].assert_called_once_with(report.FAIRS_LIMIT)
        self.mocks["get_news"].assert_called_once_with()  # 새로고침(refresh) 없이 캐시 정책 그대로
        self.mocks["get_fx"].assert_called_once_with()

    def test_partial_failures(self):
        self.mocks["get_fx"].side_effect = RuntimeError("fx down")
        self.mocks["get_news"].side_effect = RuntimeError("news down")
        self.mocks["get_upcoming_fairs"].side_effect = service.FairsDataError()
        data = report.collect("America/Sao_Paulo", NOW)
        self.assertEqual(data["failures"], ["환율 전체", "뉴스 전체", "전시회 일정 자료"])
        self.assertIsNone(data["fx"])
        pdf = report.render(data)
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_source_level_failures_listed(self):
        fx = fx_ok()
        fx["usd_krw"].update(status="not_configured", rate=None, date=None, previous=None, change_pct=None,
                             error={"code": "key_missing", "message": "TEST 키 없음", "retryable": False})
        fx["brl_krw"] = None
        news = news_ok()
        news["media"]["kotra"].update(status="not_configured", error={"code": "key_missing", "message": "TEST KOTRA 키 없음", "retryable": False})
        self.mocks["get_fx"].side_effect = lambda: fx
        self.mocks["get_news"].side_effect = lambda: news
        data = report.collect("America/Sao_Paulo", NOW)
        self.assertEqual(data["failures"], ["환율 USD/KRW(TEST 키 없음)", "뉴스 KOTRA(TEST KOTRA 키 없음)"])
        self.assertTrue(report.render(data).startswith(b"%PDF"))

    def test_build_daily_filename_and_memory_only(self):
        before = set(ROOT.rglob("*.pdf"))
        pdf, filename = report.build_daily("America/Manaus", NOW)
        self.assertTrue(pdf.startswith(b"%PDF") and pdf.rstrip().endswith(b"%%EOF"))
        self.assertGreater(len(pdf), 1000)
        self.assertEqual(filename, "fionex_daily_briefing_20261026_1000.pdf")  # 서울 시각
        self.assertEqual(set(ROOT.rglob("*.pdf")), before)  # 프로젝트 폴더에 파일을 만들지 않음


class PdfLayoutTests(ReportTestBase):
    def pdf(self, data=None):
        reader = PdfReader(BytesIO(report.render(data or report.collect("America/Sao_Paulo", NOW))))
        text = "\n".join(page.extract_text() for page in reader.pages)
        links = [a.get_object()["/A"]["/URI"] for page in reader.pages for a in page.get("/Annots", [])
                 if a.get_object().get("/Subtype") == "/Link"]
        return reader, text, links

    def test_news_title_links_without_url_text_within_two_pages(self):
        reader, text, links = self.pdf()
        self.assertLessEqual(len(reader.pages), 2)
        news_links = {u for u in links if "/news/" in u}  # 여러 줄 제목은 줄마다 같은 링크 영역이 생김
        self.assertEqual(len(news_links), report.NEWS_LIMIT)  # 뉴스 제목마다 링크
        self.assertIn("https://example.com/news/1?a=1&b=2", links)
        self.assertNotIn("https://", text)  # 긴 URL 문자열은 본문에 없음
        self.assertIn("example.com", text)  # 짧은 도메인만

    def test_page_numbers_n_of_total(self):
        reader, text, _ = self.pdf()
        total = len(reader.pages)
        for n, page in enumerate(reader.pages, 1):
            self.assertIn(f"{n} / {total}", page.extract_text())

    def test_derived_date_cell(self):
        self.assertEqual(report.derived_date_text("2026-10-23", "2026-10-23"), "2026-10-23 (두 환율 동일)")
        self.assertEqual(report.derived_date_text("2026-10-23", "2026-10-24"), "KRW 10-23 / BRL 10-24")
        self.assertEqual(report.derived_date_text("2026-12-31", "2027-01-02"), "KRW 2026-12-31 / BRL 2027-01-02")
        _, text, _ = self.pdf()
        self.assertIn("2026-10-23 (두 환율 동일)", text)

    def test_notes_show_source_counts(self):
        news = news_ok()
        news["media"]["kotra"].update(collected=0, after_filter=0)
        news["items"] = [i for i in news["items"] if i["origin"] != "kotra"]
        news["media"]["google"].update(collected=53, after_filter=13)
        self.mocks["get_news"].side_effect = lambda: news
        data = report.collect("America/Sao_Paulo", NOW)
        self.assertEqual(data["news"]["selected"].get("kotra", 0), 0)  # 가짜 기사 없음
        _, text, _ = self.pdf(data)
        self.assertIn("수집 0건 / 필터 후 0건 / 브리핑 선정 0건", text)
        self.assertIn("수집 53건 / 필터 후 13건", text)

    def test_kotra_minimum_in_briefing(self):
        news = news_ok()
        kotra = news_item(11, "kotra", title="TEST 브라질 원사 시장")  # 가장 오래된 기사
        news["items"] = [i for i in news["items"] if i["origin"] != "kotra"] + [kotra]
        self.mocks["get_news"].side_effect = lambda: news
        data = report.collect("America/Sao_Paulo", NOW)
        self.assertEqual(len(data["news"]["items"]), report.NEWS_LIMIT)
        self.assertIn(kotra, data["news"]["items"])
        self.assertEqual(data["news"]["selected"]["kotra"], 1)


class RouteTests(ReportTestBase):
    def test_route(self):
        client = app.test_client()
        res = client.get("/api/home/report/daily.pdf?city=America/Manaus")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "application/pdf")
        self.assertRegex(res.headers["Content-Disposition"], r'^attachment; filename="fionex_daily_briefing_\d{8}_\d{4}\.pdf"$')
        self.assertEqual(res.headers["Cache-Control"], "no-store")
        self.assertTrue(res.data.startswith(b"%PDF"))
        self.assertEqual(client.get("/api/home/report/daily.pdf").status_code, 200)  # 기본 상파울루
        for q in ("?city=sao_paulo", "?city=", "?city=Asia/Seoul"):
            bad = client.get("/api/home/report/daily.pdf" + q)
            self.assertEqual(bad.status_code, 400, q)
            self.assertEqual(bad.get_json()["error"]["code"], "invalid_city")

    def test_engine_failure(self):
        with mock.patch.object(report, "render", side_effect=RuntimeError("engine")):
            res = app.test_client().get("/api/home/report/daily.pdf")
        self.assertEqual(res.status_code, 500)
        self.assertEqual(res.get_json()["error"]["code"], "report_failed")


if __name__ == "__main__":
    unittest.main()
