"""홈 일일 브리핑 PDF. 버튼을 누른 시점의 홈 데이터를 모아 A4 PDF를 메모리에서 만듭니다(서버에 저장하지 않음).

- 데이터는 기존 service 함수와 그 캐시를 그대로 씁니다: 공휴일(get_holidays), 환율(get_fx), 뉴스(get_news),
  전시회(get_upcoming_fairs). 뉴스 AI 요약은 이미 만든 요약만 씁니다(PDF 때문에 OpenAI를 부르지 않음).
- 영역별로 실패를 나눕니다. 실패한 영역은 "확인 불가"로 두고 마지막 유의사항에 목록으로 적습니다. 값을 채워 넣지 않습니다.
- 폰트: features/home/fonts/Noto Sans KR(OFL). 한글·포르투갈어 악센트 포함.
"""
import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from features.home.buyer_time import CITIES, DEFAULT_CITY, SEOUL, buyer_time, format_day, format_day_time

logger = logging.getLogger(__name__)

NEWS_LIMIT = 8
FAIRS_LIMIT = 3
FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT = "NotoSansKR"
FONT_BOLD = "NotoSansKR-Bold"
ORIGIN_LABELS = {"kotra": "KOTRA", "google": "Google News", "abit": "ABIT"}
SOURCE_NAMES = {"brasilapi": "BrasilAPI 국가 공휴일", "fallback": "대체 공휴일 자료", "none": "확인 불가"}

# 흑백 출력에서도 구분되도록 색은 보조로만 씁니다.
INK = colors.HexColor("#17243b")
MUTED = colors.HexColor("#55657d")
LINE = colors.HexColor("#b9c5d6")
SHADE = colors.HexColor("#eef3fa")
LINK = colors.HexColor("#1a56bd")


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
        data["news"] = {"items": news["items"][:NEWS_LIMIT], "media": news["media"], "total": len(news["items"])}
        for key, info in news["media"].items():
            if info["status"] != "ok":
                failures.append(f"뉴스 {ORIGIN_LABELS[key]}({info['error']['message']})")
    except Exception:
        logger.exception("브리핑: 뉴스 조회 실패")
        data["news"] = None
        failures.append("뉴스 전체")

    try:
        data["fairs"] = service.get_upcoming_fairs(FAIRS_LIMIT)
    except service.FairsDataError:
        data["fairs"] = None
        failures.append("전시회 일정 자료")
    except Exception:
        logger.exception("브리핑: 전시회 일정 읽기 실패")
        data["fairs"] = None
        failures.append("전시회 일정 자료")
    return data


def build_daily(city=DEFAULT_CITY, now=None):
    """(PDF bytes, 파일명). PDF 엔진 오류만 예외로 올라갑니다."""
    data = collect(city, now)
    return render(data), "fionex_daily_briefing_" + data["generated_at"].strftime("%Y%m%d_%H%M") + ".pdf"


# ---------- PDF 만들기 ----------
_fonts_ready = False


def _register_fonts():
    global _fonts_ready
    if not _fonts_ready:
        pdfmetrics.registerFont(TTFont(FONT, str(FONT_DIR / "NotoSansKR-Regular.ttf")))
        pdfmetrics.registerFont(TTFont(FONT_BOLD, str(FONT_DIR / "NotoSansKR-Bold.ttf")))
        _fonts_ready = True


def _styles():
    base = ParagraphStyle("body", fontName=FONT, fontSize=9.5, leading=14, textColor=INK, alignment=TA_LEFT)
    return {
        "body": base,
        "small": ParagraphStyle("small", parent=base, fontSize=8, leading=11.5, textColor=MUTED),
        "title": ParagraphStyle("title", parent=base, fontName=FONT_BOLD, fontSize=18, leading=24, spaceAfter=2),
        "h2": ParagraphStyle("h2", parent=base, fontName=FONT_BOLD, fontSize=12.5, leading=17, spaceBefore=10, spaceAfter=5),
        "item": ParagraphStyle("item", parent=base, fontName=FONT_BOLD, fontSize=9.5, leading=13.5),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8.8, leading=12.5),
        "head": ParagraphStyle("head", parent=base, fontName=FONT_BOLD, fontSize=8.8, leading=12.5),
    }


def _p(text, style):
    return Paragraph(escape(text), style)


def _link(url, text, style):
    # 외부 문자열은 이스케이프한 뒤 넣습니다(ReportLab 문단은 간이 마크업을 해석함).
    return Paragraph(f'<a href="{escape(url, {chr(34): "&quot;"})}" color="#1a56bd">{escape(text)}</a>', style)


def _table(rows, widths, header=True):
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), SHADE), ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK)]
    table.setStyle(TableStyle(style))
    return table


def render(data):
    _register_fonts()
    s = _styles()
    width = A4[0] - 36 * mm
    story = []

    # 0. 머리말
    buyer = data.get("buyer")
    city_name = CITIES.get(data["city"], data["city"])
    story.append(_p("fionex 일일 브리핑", s["title"]))
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
    generated = data["generated_at"].strftime("%Y-%m-%d %H:%M KST")

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 10 * mm, f"fionex 일일 브리핑 · {generated} 생성")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{doc.page}쪽")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=18 * mm, title="fionex 일일 브리핑", author="fionex")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def _buyer_section(buyer, s, width):
    out = [_p("1. 바이어 시간", s["h2"])]
    if buyer is None:
        return out + [_p("확인 불가", s["body"])]
    if buyer["next_start"]:
        nxt = buyer["next_start"]
        next_text = f"{format_day_time(nxt['seoul'])} KST (현지 {format_day(nxt['local'].date())} 09:00)"
        if not nxt["holidays_known"]:
            next_text += " · 공휴일 미반영"
    else:
        next_text = "업무시간 중" if buyer["status"] == "업무시간" else "계산할 수 없음"
    if buyer["holidays"]:
        holiday_text = ", ".join(
            f"{format_day(h['date'])} {h['name']}" + (" (주말)" if h["weekend"] else " — 회신 지연 가능") for h in buyer["holidays"])
    elif any(v["source"] == "none" for v in buyer["holiday_info"].values()):
        holiday_text = "공휴일 정보 확인 불가"
    else:
        holiday_text = "7일 이내 국가 공휴일 없음"
    rows = [
        [_p("현재 상태", s["head"]), _p(buyer["status"], s["cell"])],
        [_p("다음 업무 시작", s["head"]), _p(next_text, s["cell"])],
        [_p("7일 이내 공휴일", s["head"]), _p(holiday_text, s["cell"])],
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
    out = [_p("2. 환율", s["h2"])]
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
                     _p(f"USD/KRW {derived['usd_krw_date']}\nUSD/BRL {derived['usd_brl_date']}".replace("\n", " · "), s["cell"]),
                     _p("-", s["cell"]), _p("USD 경유 계산값 · 공식 고시 환율 아님", s["cell"])])
    else:
        rows.append([_p("BRL/KRW", s["cell"]), _p("계산 불가", s["cell"]), _p("-", s["cell"]),
                     _p("USD/KRW와 USD/BRL이 모두 있어야 계산", s["cell"]), _p("USD 경유 계산값", s["cell"])])
    out.append(_table(rows, (18 * mm, 38 * mm, 30 * mm, 42 * mm, width - 128 * mm)))
    out.append(Spacer(1, 3))
    out.append(_p("BRL/KRW = USD/KRW ÷ USD/BRL (USD 경유 계산값). 주말·공휴일에는 최근 고시일 값입니다. 전망·해석 없음.", s["small"]))
    return out


def _news_date(value):
    if len(value) == 10:
        return value
    return format_day_time(datetime.fromisoformat(value).astimezone(SEOUL)) + " KST"


def _news_section(news, s, width):
    out = [_p("3. 최신 뉴스", s["h2"])]
    if news is None or not news["items"]:
        return out + [_p("뉴스를 불러오지 못했습니다" if news is None or all(
            m["status"] != "ok" for m in news["media"].values()) else "수집 기간 안에 해당하는 소식이 없습니다", s["body"])]
    out.append(_p(f"최신순 상위 {len(news['items'])}건(수집 {news['total']}건 중). 원문 제목 그대로 표시합니다.", s["small"]))
    for index, item in enumerate(news["items"], 1):
        block = [_link(item["url"], f"{index}. {item['title']}", s["item"])]
        if item.get("summary_ko") and item["origin"] in ("google", "abit"):
            block.append(_p("[AI 요약] " + item["summary_ko"], s["body"]))
        meta = " · ".join(x for x in (ORIGIN_LABELS.get(item["origin"], item["origin"]), item.get("media"),
                                       _news_date(item["published_at"])) if x)
        block.append(_p(meta, s["small"]))
        block.append(_link(item["url"], item["url"], s["small"]))
        block.append(Spacer(1, 5))
        out.append(KeepTogether(block))
    return out


def _fairs_section(fairs, s, width):
    out = [_p("4. 다가오는 전시회", s["h2"])]
    if fairs is None:
        return out + [_p("일정 확인 불가", s["body"])]
    if not fairs["fairs"]:
        return out + [_p("확인된 예정 전시회가 없습니다", s["body"])]
    rows = [[_p(h, s["head"]) for h in ("행사", "기간", "D-day", "도시 · 장소", "확인 상태 · 출처")]]
    for f in fairs["fairs"]:
        period = f["start"] if f["start"] == f["end"] else f"{f['start']} ~ {f['end']}"
        place = " · ".join(x for x in (f.get("city"), f.get("venue")) if x) or "미확인"
        state = ("공식 사이트 확인" if f["verified"] else "확인 필요") + f" ({f['checked_at']} 확인)"
        rows.append([_p(f["name"], s["cell"]), _p(period, s["cell"]), _p(f["d_day"], s["cell"]), _p(place, s["cell"]),
                     [_p(state, s["cell"]), _link(f["url"], f["source"], s["cell"])]])
    out.append(_table(rows, (34 * mm, 30 * mm, 16 * mm, 42 * mm, width - 122 * mm)))
    return out


def _notes_section(data, s):
    out = [_p("5. 출처 및 유의사항", s["h2"])]
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
        for key, info in news["media"].items():
            when = f"수집 {info['fetched_at'][:16].replace('T', ' ')}" if info.get("fetched_at") else "수집 기록 없음"
            lines.append(f"뉴스 {ORIGIN_LABELS[key]}: {when}")
    if fairs:
        lines.append(f"전시회: 담당자 확인 정적 자료(자료 확인일 {fairs.get('data_checked_at') or '미확인'})")
    lines += [
        "업무시간 09:00~18:00은 가정값입니다.",
        "BRL/KRW는 USD/KRW ÷ USD/BRL로 계산한 USD 경유 값이며 공식 고시 환율이 아닙니다.",
        "[AI 요약]은 Google News·ABIT 포르투갈어 제목만 보고 만든 한국어 한 줄이며 기사 본문을 보지 않았습니다. 원문을 확인하세요. KOTRA 뉴스는 요약하지 않습니다.",
    ]
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
