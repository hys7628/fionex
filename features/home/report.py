"""홈 일일 브리핑 PDF. 버튼을 누른 시점의 홈 데이터를 모아 A4 PDF를 메모리에서 만듭니다(서버에 저장하지 않음).

- 데이터는 기존 service 함수와 그 캐시를 그대로 씁니다: 공휴일(get_holidays), 환율(get_fx), 뉴스(get_news),
  전시회(get_upcoming_fairs).
- 뉴스는 원문 제목 아래 한국어 번역(제목만 보고 옮긴 한 줄)을 붙입니다(2026-10-27). 화면 AI 요약과 같은 기능·캐시를 쓰며,
  PDF에 실을 상위 기사 중 아직 번역이 없는 Google·ABIT 포르투갈어 제목만 한 번 묶어 요청합니다(service.translate_titles).
  번역하지 못하면 원문 제목만 싣고 유의사항에 사유를 적습니다. KOTRA 기사는 한국어 제목이라 번역하지 않습니다.
- 영역별로 실패를 나눕니다. 실패한 영역은 "확인 불가"로 두고 마지막 유의사항에 목록으로 적습니다. 값을 채워 넣지 않습니다.
- 폰트: 공통 Pretendard(static/fonts/pretendard/, OFL, common/config.py PDF_FONT_FILES). 한글·포르투갈어 악센트 포함.
- 디자인: 공통 PDF 디자인(common/pdf_theme.py) — 머리 'DAILY BRIEFING'·로고, 큰 제목, 막대 구역 제목, 민트 머리 표, 브랜드 꼬리.
"""
import logging
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer

from common import pdf_theme as theme
from common.config import PDF_FONT_NAMES
from features.home.buyer_time import CITIES, DEFAULT_CITY, SEOUL, buyer_time, format_day, format_day_time, next_holiday_text

logger = logging.getLogger(__name__)

NEWS_LIMIT = 8
FAIRS_LIMIT = 3
FONT = PDF_FONT_NAMES["regular"]
FONT_BOLD = PDF_FONT_NAMES["bold"]
ORIGIN_LABELS = {"kotra": "KOTRA", "google": "Google News", "abit": "ABIT"}
SOURCE_NAMES = {"brasilapi": "BrasilAPI 국가 공휴일", "fallback": "대체 공휴일 자료", "none": "확인 불가"}

MARGIN = 18 * mm


# ---------- 데이터 모으기 ----------
def collect(city=DEFAULT_CITY, now=None):
    """PDF에 넣을 값과 실패 목록. 각 영역 값이 None이면 그 영역은 확인 불가입니다."""
    from features.home import service  # service가 이 모듈을 불러오므로 함수 안에서 가져옵니다.

    now = now or datetime.now(SEOUL)
    failures = []
    data = {"generated_at": now.astimezone(SEOUL), "city": city, "failures": failures}

    try:
        data["buyer"] = buyer_time(city, now, service.get_holidays)
        if any(v["source"] == "none" for v in data["buyer"]["holiday_info"].values()):
            failures.append("브라질 공휴일 정보(공휴일 없이 주말·업무시간만 판단)")
    except Exception:
        logger.exception("브리핑: 바이어 시간 계산 실패")
        data["buyer"] = None
        failures.append("바이어 시간")

    try:
        data["fx"] = service.get_fx()
        for key in ("usd_krw", "usd_brl"):
            info = data["fx"][key]
            if info["status"] != "ok":
                failures.append(f"환율 {info['pair']}({info['error']['message']})")
    except Exception:
        logger.exception("브리핑: 환율 조회 실패")
        data["fx"] = None
        failures.append("환율 전체")

    try:
        news = service.get_news()
        # 최신순 상위 8건. 필터를 통과한 KOTRA 기사가 있으면 최소 1건은 넣습니다(service.NEWS_SOURCE_MINIMUM).
        top, selected = service.select_top_news(news["items"], NEWS_LIMIT, service.NEWS_SOURCE_MINIMUM)
        data["news"] = {"items": top, "media": news["media"], "total": len(news["items"]), "selected": selected,
                        "translation": _translate(service, top)}
        logger.info("브리핑 뉴스 선정: %s", ", ".join(f"{k}={selected.get(k, 0)}" for k in ORIGIN_LABELS))
        for key, info in news["media"].items():
            if info["status"] != "ok":
                failures.append(f"뉴스 {ORIGIN_LABELS[key]}({info['error']['message']})")
    except Exception:
        logger.exception("브리핑: 뉴스 조회 실패")
        data["news"] = None
        failures.append("뉴스 전체")

    try:
        # 화면의 '전체' 보기와 같은 정책(브라질 최소 노출)으로 3건
        data["fairs"] = service.get_upcoming_fairs(FAIRS_LIMIT, min_brazil=service.FAIRS_MIN_BRAZIL_IN_ALL)
    except service.FairsDataError:
        data["fairs"] = None
        failures.append("전시회 일정 자료")
    except Exception:
        logger.exception("브리핑: 전시회 일정 읽기 실패")
        data["fairs"] = None
        failures.append("전시회 일정 자료")
    return data


def _translate(service, items):
    """상위 기사 제목 번역을 붙입니다(항목에 summary_ko). 반환 상태 문장(성공이면 None)."""
    try:
        result = service.translate_titles(items)
    except Exception:
        logger.exception("브리핑: 기사 제목 번역 실패")
        return "제목 번역을 만들지 못했습니다"
    for item in items:
        text = result.get("summaries", {}).get(item["id"])
        if text:
            item["summary_ko"] = text
    return None if result.get("status") == "ok" else (result.get("message") or "제목 번역을 만들지 못했습니다")


def build_daily(city=DEFAULT_CITY, now=None):
    """(PDF bytes, 파일명). PDF 엔진 오류만 예외로 올라갑니다."""
    data = collect(city, now)
    return render(data), "fionex_daily_briefing_" + data["generated_at"].strftime("%Y%m%d_%H%M") + ".pdf"


# ---------- PDF 만들기 ----------
def _register_fonts():
    theme.register_fonts()


def _styles():
    s = theme.styles()
    s["h2"] = None  # 구역 제목은 theme.SectionTitle
    s["item"] = ParagraphStyle("item", parent=s["body"], fontName=FONT_BOLD, fontSize=9.4, leading=13.5)
    s["head"] = s["label"]
    s["translation"] = ParagraphStyle("translation", parent=s["body"], fontSize=9.2, leading=13.6, spaceBefore=1, spaceAfter=1)
    s["num"] = ParagraphStyle("num", parent=s["body"], fontName=FONT_BOLD, fontSize=11, leading=14, textColor=theme.PRIMARY)
    return s


def _h2(text, tag=None):
    return theme.SectionTitle(text, tag, size=12, space_before=10, space_after=5)


def _p(text, style):
    return Paragraph(escape(text), style)


def _link(url, text, style):
    # 외부 문자열은 이스케이프한 뒤 넣습니다(ReportLab 문단은 간이 마크업을 해석함).
    return Paragraph(f'<a href="{escape(url, {chr(34): "&quot;"})}" color="#1d6ad4">{escape(text)}</a>', style)


def _table(rows, widths, header=True):
    if header:
        return theme.data_table(rows, widths)
    return theme.kv_table(rows, widths[0], sum(widths))


def render(data):
    _register_fonts()
    s = _styles()
    width = A4[0] - 2 * MARGIN
    story = []

    # 0. 머리말: 큰 제목 + 한 줄 소개 + 시각 표
    buyer = data.get("buyer")
    city_name = CITIES.get(data["city"], data["city"])
    story.append(_p("일일 브리핑", s["title"]))
    story.append(_p("브라질 바이어 현지 시간과 환율, 원단·원사·섬유 업계 소식, 다가오는 전시회를 한 번에 정리했습니다.", s["lead"]))
    head_rows = [
        [_p("생성 시각", s["head"]), _p(data["generated_at"].strftime("%Y-%m-%d %H:%M") + " KST", s["cell"])],
        [_p("서울 시각", s["head"]), _p(format_day_time(buyer["seoul"]) if buyer else "확인 불가", s["cell"])],
        [_p(f"브라질 시각({city_name})", s["head"]), _p(format_day_time(buyer["local"]) if buyer else "확인 불가", s["cell"])],
    ]
    story.append(_table(head_rows, (38 * mm, width - 38 * mm), header=False))

    story += _buyer_section(buyer, s, width)
    story += _fx_section(data.get("fx"), s, width)
    story += _news_section(data.get("news"), s, width)
    story += _fairs_section(data.get("fairs"), s, width)
    story += _notes_section(data, s)

    buf = BytesIO()
    canvas_cls = theme.numbered_canvas("DAILY BRIEFING", data["generated_at"].strftime("%Y.%m.%d"), MARGIN)
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=theme.CONTENT_TOP,
                            bottomMargin=theme.CONTENT_BOTTOM, title="fionex 일일 브리핑", author="fionex")
    doc.build(story, canvasmaker=canvas_cls)
    return buf.getvalue()


def _buyer_section(buyer, s, width):
    out = [_h2("바이어 시간", "현지 업무시간 기준")]
    if buyer is None:
        return out + [_p("확인 불가", s["body"])]
    if buyer["next_start"]:
        nxt = buyer["next_start"]
        next_text = f"{format_day_time(nxt['seoul'])} KST (현지 {format_day(nxt['local'].date())} 09:00)"
        if not nxt["holidays_known"]:
            next_text += " · 공휴일 미반영"
    else:
        next_text = "업무시간 중" if buyer["status"] == "업무시간" else "계산할 수 없음"
    # 다음 공휴일(화면과 같은 buyer_time.next_holiday_text). 7일 이내 공휴일은 같은 줄에 회신 영향과 함께 덧붙여 중복 행을 두지 않습니다.
    holiday_text = next_holiday_text(buyer.get("next_holiday"))
    within = [f"{format_day(h['date'])} {h['name']}" + (" (주말)" if h["weekend"] else " — 회신 지연 가능")
              for h in buyer["holidays"]]
    if within:
        holiday_text += " · 7일 이내: " + ", ".join(within)
    rows = [
        [_p("현재 상태", s["head"]), _p(buyer["status"], s["cell"])],
        [_p("다음 업무 시작", s["head"]), _p(next_text, s["cell"])],
        [_p("다음 공휴일", s["head"]), _p(holiday_text, s["cell"])],
    ]
    out.append(_table(rows, (38 * mm, width - 38 * mm), header=False))
    out.append(Spacer(1, 3))
    out.append(_p("기준: 현지 09:00~18:00 (가정, 확정되지 않은 업무시간) · 점심시간 미반영 · 브라질 국가 공휴일만 반영", s["small"]))
    return out


def _change_text(info):
    if info.get("change_pct") is None or not info.get("previous"):
        return "비교 데이터 없음"
    pct = info["change_pct"]
    direction = "▲ 상승" if pct > 0 else "▼ 하락" if pct < 0 else "– 변동 없음"
    return f"{direction} {abs(pct):.2f}% (직전 {info['previous']['date']})"


def _fx_section(fx, s, width):
    out = [_h2("환율", "USD 기준 고시 환율")]
    if fx is None:
        return out + [_p("확인 불가", s["body"])]
    rows = [[_p(h, s["head"]) for h in ("통화", "값", "고시일", "전일 대비", "출처")]]
    for key, quote, digits in (("usd_krw", "KRW", 2), ("usd_brl", "BRL", 4)):
        info = fx[key]
        if info["status"] == "ok":
            rows.append([_p(info["pair"], s["cell"]), _p(f"1 USD = {info['rate']:,.{digits}f} {quote}", s["cell"]),
                         _p(info["date"], s["cell"]), _p(_change_text(info), s["cell"]), _p(info["source_name"], s["cell"])])
        else:
            rows.append([_p(info["pair"], s["cell"]), _p("확인 불가", s["cell"]), _p("-", s["cell"]),
                         _p(info["error"]["message"], s["cell"]), _p(info["source_name"], s["cell"])])
    derived = fx.get("brl_krw")
    if derived:
        rows.append([_p("BRL/KRW", s["cell"]), _p(f"1 BRL = {derived['rate']:,.2f} KRW", s["cell"]),
                     _p(derived_date_text(derived["usd_krw_date"], derived["usd_brl_date"]), s["cell"]),
                     _p("-", s["cell"]), _p("USD 경유 계산값 · 공식 고시 환율 아님", s["cell"])])
    else:
        rows.append([_p("BRL/KRW", s["cell"]), _p("계산 불가", s["cell"]), _p("-", s["cell"]),
                     _p("USD/KRW와 USD/BRL이 모두 있어야 계산", s["cell"]), _p("USD 경유 계산값", s["cell"])])
    # 값·고시일·전일 대비가 보통 한 줄에 들어가는 너비(2026-10-25 글자 폭 측정).
    out.append(_table(rows, (21 * mm, 38 * mm, 42 * mm, 38 * mm, width - 139 * mm)))
    out.append(Spacer(1, 3))
    out.append(_p("BRL/KRW = USD/KRW ÷ USD/BRL (USD 경유 계산값). 주말·공휴일에는 최근 고시일 값입니다. 전망·해석 없음.", s["small"]))
    return out


def derived_date_text(krw_date, brl_date):
    """BRL/KRW 고시일 칸. 같으면 '2026-10-23 (두 환율 동일)', 다르면 'KRW 10-23 / BRL 10-24'(연도가 다르면 전체 날짜)."""
    if krw_date == brl_date:
        return f"{krw_date} (두 환율 동일)"
    if krw_date[:4] == brl_date[:4]:
        return f"KRW {krw_date[5:]} / BRL {brl_date[5:]}"
    return f"KRW {krw_date} / BRL {brl_date}"


def _news_date(value):
    if len(value) == 10:
        return value
    return format_day_time(datetime.fromisoformat(value).astimezone(SEOUL)) + " KST"


def _news_section(news, s, width):
    out = [_h2("최신 뉴스", "원문 제목 + 한국어 번역")]
    if news is None or not news["items"]:
        return out + [_p("뉴스를 불러오지 못했습니다" if news is None or all(
            m["status"] != "ok" for m in news["media"].values()) else "수집 기간 안에 해당하는 소식이 없습니다", s["body"])]
    out.append(_p(f"최신순 상위 {len(news['items'])}건(수집 {news['total']}건 중). 제목을 누르면 원문으로 이동합니다.", s["small"]))
    out.append(Spacer(1, 3))
    rows = []
    for index, item in enumerate(news["items"], 1):
        # 제목이 원문 링크입니다. 긴 주소(Google News 경유 URL)는 본문에 쓰지 않고 매체 도메인만 보입니다.
        block = [_link(item["url"], item["title"], s["item"])]
        if item.get("summary_ko") and item["origin"] in ("google", "abit"):
            block.append(Paragraph('<font color="#0a7262"><b>번역</b></font>  ' + escape(item["summary_ko"]), s["translation"]))
        media = item.get("media")
        domain = item.get("media_domain")
        if media and domain and domain not in media:
            media = f"{media}({domain})"
        # 매체·날짜 줄 끝에 주제 태그(최대 2개)를 붙입니다.
        meta = " · ".join(x for x in (ORIGIN_LABELS.get(item["origin"], item["origin"]), media or domain,
                                       _news_date(item["published_at"]), " · ".join(item.get("tags") or ())) if x)
        block.append(_p(meta, s["small"]))
        rows.append([_p(f"{index:02d}", s["num"]), block])
    out.append(theme.data_table(rows, (12 * mm, width - 12 * mm), head_rows=0))
    return out


def _fairs_section(fairs, s, width):
    out = [_h2("다가오는 전시회", "담당자 확인 자료")]
    if fairs is None:
        return out + [_p("일정 확인 불가", s["body"])]
    if not fairs["fairs"]:
        return out + [_p("확인된 예정 전시회가 없습니다", s["body"])]
    rows = [[_p(h, s["head"]) for h in ("행사", "기간", "D-day", "국가 · 도시 · 장소", "확인 상태 · 출처")]]
    for f in fairs["fairs"]:
        period = f["start"] if f["start"] == f["end"] else f"{f['start']} ~ {f['end']}"
        place = " · ".join(x for x in (f.get("country"), f.get("city"), f.get("venue")) if x) or "미확인"
        state = ("공식 사이트 확인" if f["verified"] else "확인 필요") + f" ({f['checked_at']} 확인)"
        rows.append([_p(f["name"], s["cell"]), _p(period, s["cell"]), _p(f["d_day"], s["cell"]), _p(place, s["cell"]),
                     [_p(state, s["cell"]), _link(f["url"], f["source"], s["cell"])]])
    out.append(_table(rows, (34 * mm, 30 * mm, 16 * mm, 42 * mm, width - 122 * mm)))
    return out


def _notes_section(data, s):
    out = [_h2("출처 및 유의사항")]
    lines = []
    buyer, fx, news, fairs = data.get("buyer"), data.get("fx"), data.get("news"), data.get("fairs")
    if buyer:
        for year, info in buyer["holiday_info"].items():
            when = f", 조회 {info['fetched_at'][:16].replace('T', ' ')}" if info.get("fetched_at") else ""
            lines.append(f"공휴일({year}): {SOURCE_NAMES.get(info['source'], info['source'])}{when}")
    if fx:
        for key in ("usd_krw", "usd_brl"):
            info = fx[key]
            lines.append(f"{info['pair']}: {info['source_name']}, 조회 {info['fetched_at'][:16].replace('T', ' ')}")
    if news:
        # 수집(응답에서 읽은 건수) → 필터 후(관련성) → 브리핑 선정(상위 8건 안). KOTRA 0건이 어느 단계인지 구분됩니다.
        for key, info in news["media"].items():
            if info.get("collected") is None:
                reason = info.get("error", {}).get("message")
                lines.append(f"뉴스 {ORIGIN_LABELS[key]}: 수집 기록 없음" + (f"({reason})" if reason else ""))
                continue
            lines.append(f"뉴스 {ORIGIN_LABELS[key]}: 수집 {info['collected']}건 / 필터 후 {info['after_filter']}건 / "
                         f"브리핑 선정 {news.get('selected', {}).get(key, 0)}건 · {info['fetched_at'][:16].replace('T', ' ')} 수집")
    if fairs:
        lines.append(f"전시회: 담당자 확인 정적 자료(자료 확인일 {fairs.get('data_checked_at') or '미확인'})")
    lines += [
        "업무시간 09:00~18:00은 가정값입니다.",
        "BRL/KRW는 USD/KRW ÷ USD/BRL로 계산한 USD 경유 값이며 공식 고시 환율이 아닙니다.",
        "뉴스 '번역'은 Google News·ABIT 포르투갈어 제목만 보고 AI가 옮긴 한국어 한 줄이며 기사 본문을 보지 않았습니다. 원문을 확인하세요. KOTRA 뉴스는 한국어 제목이라 번역하지 않습니다.",
    ]
    if news and news.get("translation"):
        lines.append("제목 번역: " + news["translation"] + " — 원문 제목만 실었습니다.")
    if fairs and any(not f["verified"] for f in fairs["fairs"]):
        lines.append("'확인 필요' 전시회는 공식 출처에서 일정이 다르게 표기되는 등 추가 확인이 필요합니다.")
    for line in lines:
        out.append(_p("· " + line, s["small"]))
    out.append(Spacer(1, 4))
    out.append(_p("수집 실패·확인 불가 항목", s["item"]))
    failures = data["failures"] or ["없음"]
    for line in failures:
        out.append(_p("· " + line, s["body"]))
    return out
