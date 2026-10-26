"""시장 분석 PDF 출력(A4 세로). 화면에 표시된 결과 dict를 그대로 받아 그립니다. 통계·AI를 다시 호출하지 않습니다.

- ReportLab 5.1.0 + 공통 Pretendard(static/fonts/pretendard/, OFL, common/config.py PDF_FONT_FILES). 공통 PDF 입력 검사(common/pdf_utils.py, pypdf)와는 별개입니다.
- 모든 문자열은 XML 이스케이프 후 Paragraph에 넣습니다(외부 문자열·AI 출력의 마크업 해석 방지).
- 긴 한글·URL은 CJK 줄바꿈으로 칸 안에서 나눕니다. 긴 표는 머리글 행을 페이지마다 반복합니다.
- 결과는 메모리 bytes로만 만들고 디스크에 쓰지 않습니다.
- 디자인: 공통 PDF 디자인(common/pdf_theme.py) — 머리 'MARKET REPORT'·로고, 큰 제목, 막대 구역 제목, 핵심 수치 카드, 민트 머리 표.
- 바이어 목록은 2026-10-27부터 이 보고서에 넣지 않습니다(화면 '바이어 목록' 탭·바이어별 AI 브리핑 PDF에서 확인).
"""
import io
import re
import urllib.parse
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, PolyLine, Rect, String, Circle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from common import pdf_theme as theme
from common.config import PDF_FONT_NAMES


FONT, FONT_BOLD = PDF_FONT_NAMES["regular"], PDF_FONT_NAMES["bold"]
KST = timezone(timedelta(hours=9))

# 화면 디자인 토큰(static/css/tokens.css) 값 — 공통 PDF 디자인과 같은 색
C_TEXT = theme.NAVY
C_MUTED = theme.MUTED
C_BORDER = theme.LINE
C_PRIMARY = theme.PRIMARY
C_AQUA = theme.AQUA
C_MINT = theme.MINT_TEXT
C_WARN = theme.WARNING
C_WARN_SOFT = theme.WARNING_SOFT
MARGIN = 16 * mm


def _register_fonts():
    theme.register_fonts()


def _h2(text, tag=None):
    return theme.SectionTitle(text, tag, size=12.5, space_before=12, space_after=6)


def _styles():
    base = dict(fontName=FONT, textColor=C_TEXT, wordWrap="CJK", alignment=TA_LEFT)
    t = theme.styles()
    return {
        "title": t["title"],
        "lead": t["lead"],
        "body": ParagraphStyle("body", fontSize=9.8, leading=15, **base),
        "small": ParagraphStyle("small", fontSize=8.2, leading=12, textColor=C_MUTED,
                                **{k: v for k, v in base.items() if k != "textColor"}),
        "cell": ParagraphStyle("cell", fontSize=8.6, leading=12.4, **base),
        "cell_num": ParagraphStyle("cell_num", fontSize=8.6, leading=12.4, alignment=2,
                                   **{k: v for k, v in base.items() if k != "alignment"}),
        "cell_head_num": ParagraphStyle("cell_head_num", fontSize=8.4, leading=12, fontName=FONT_BOLD, textColor=C_TEXT, alignment=2,
                                        **{k: v for k, v in base.items() if k not in ("fontName", "textColor", "alignment")}),
        "cell_muted": ParagraphStyle("cell_muted", fontSize=8.6, leading=12.4, textColor=C_MUTED,
                                     **{k: v for k, v in base.items() if k != "textColor"}),
        "cell_muted_num": ParagraphStyle("cell_muted_num", fontSize=8.6, leading=12.4, textColor=C_MUTED, alignment=2,
                                         **{k: v for k, v in base.items() if k not in ("textColor", "alignment")}),
        "cell_head": ParagraphStyle("cell_head", fontSize=8.4, leading=12, fontName=FONT_BOLD, textColor=C_TEXT,
                                    **{k: v for k, v in base.items() if k not in ("fontName", "textColor")}),
        "notice": ParagraphStyle("notice", fontSize=9, leading=13.6, textColor=C_WARN, backColor=C_WARN_SOFT,
                                 borderPadding=(5, 7, 5, 7), spaceBefore=6, spaceAfter=8,
                                 **{k: v for k, v in base.items() if k != "textColor"}),
    }


def snapshot_label(src):
    """스냅샷 대체 표시 문구(화면과 같음)."""
    return "MDIC 공개 원본 자료(기준: %s) 사용" % str(src.get("fetched_at") or "")[:10]


def _p(text, style):
    return Paragraph(escape(str(text if text is not None else "")), style)


def safe_url(value):
    """링크로 쓸 수 있는 http(s) 절대 주소면 그대로, 아니면 None."""
    url = str(value or "").strip()
    if not url or re.search(r"[\s\x00-\x1f\x7f<>\"']", url):
        return None
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        return None
    return url


def _link(url, style, label=None):
    """http(s) 절대 주소만 링크로 만듭니다. 형식이 틀리면 링크 없이 안내 문구만 넣습니다."""
    url = safe_url(url)
    if not url:
        return _p("원문 주소 형식 오류(링크 미표시)", style)
    safe = escape(url, {'"': "&quot;"})
    return Paragraph('<a href="%s" color="#1d6ad4">%s</a>' % (safe, escape(label or url)), style)


# ---------- 숫자 표시(화면과 같은 반올림) ----------
def usd(v):
    return "기록 없음" if v is None else "{:,}".format(int(round(v)))


def tons(kg):
    return "기록 없음" if kg is None else "{:,.1f}".format(kg / 1000)


def price(v, reason=None):
    return ("계산 불가" + (" (%s)" % reason if reason else "")) if v is None else "{:,.2f}".format(v)


def pct(v):
    return "계산 불가" if v is None else "{:,.1f}%".format(v)


def yoy(y):
    if not y or y.get("value") is None:
        return "계산 불가" + (" (%s)" % y.get("reason") if y and y.get("reason") else "")
    v = y["value"]
    return ("+" if v > 0 else "") + "{:,.1f}%".format(v)


def _country(c):
    if not c:
        return ""
    ko, pt = c.get("name_ko"), c.get("name_pt")
    return "%s (%s)" % (ko, pt) if ko and pt else (ko or pt or "")


# 표 색(2026-10-27 가독성 정리): 숫자가 잘 읽히도록 무채색 블루그레이 머리 + 얇은 선 + 아주 옅은 줄무늬.
T_HEAD_BG = colors.HexColor("#eef2f7")
T_HEAD_LINE = colors.HexColor("#9aa8bc")
T_LINE = colors.HexColor("#e3e8ef")
T_ZEBRA = colors.HexColor("#f8fafc")
T_HIGHLIGHT = colors.HexColor("#e8f1fd")  # 한국 행


def _table(rows, widths, st, head_rows=1, num_cols=(), zebra=False, highlight=None, muted_rows=(), valign="MIDDLE"):
    data = []
    for ri, row in enumerate(rows):
        cells = []
        for ci, v in enumerate(row):
            if hasattr(v, "wrap") or isinstance(v, list):  # 이미 만든 단락(들)
                cells.append(v)
            elif ri < head_rows:
                cells.append(_p(v, st["cell_head_num"] if ci in num_cols else st["cell_head"]))
            elif ri in muted_rows:
                cells.append(_p(v, st["cell_muted_num"] if ci in num_cols else st["cell_muted"]))
            else:
                cells.append(_p(v, st["cell_num"] if ci in num_cols else st["cell"]))
        data.append(cells)
    t = Table(data, colWidths=widths, repeatRows=head_rows)
    style = [
        ("VALIGN", (0, 0), (-1, -1), valign),  # 숫자 표는 가운데, 긴 문장 표(AI)는 위
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, head_rows), (-1, -1), 0.4, T_LINE),
    ]
    if head_rows:
        style += [("BACKGROUND", (0, 0), (-1, head_rows - 1), T_HEAD_BG),
                  ("LINEBELOW", (0, head_rows - 1), (-1, head_rows - 1), 0.9, T_HEAD_LINE)]
    if zebra or len(data) > 6:
        for r in range(head_rows + 1, len(data), 2):
            style.append(("BACKGROUND", (0, r), (-1, r), T_ZEBRA))
    for r in highlight or []:
        style.append(("BACKGROUND", (0, r), (-1, r), T_HIGHLIGHT))
        style.append(("LINEBEFORE", (0, r), (0, r), 2.2, C_PRIMARY))
    t.setStyle(TableStyle(style))
    return t


def yoy_cell(y):
    """표 칸용 전년 대비: 계산할 수 없으면 '—'(사유는 표 아래 각주 한 줄)."""
    return "—" if not y or y.get("value") is None else yoy(y)


# ---------- 그래프 ----------
def _chart(monthly, metric, width, height=62 * mm):
    """월별 단일 계열 그래프. fob·kg는 막대, unit_price는 선. 기록 없는 달은 비움."""
    def val(m):
        if not m.get("has_record"):
            return None
        if metric == "kg":
            return None if m.get("kg") is None else m["kg"] / 1000
        return m.get(metric)

    values = [val(m) for m in monthly]
    present = [v for v in values if v is not None]
    d = Drawing(width, height)
    left, bottom, top, right = 38, 22, 8, 6
    pw, ph = width - left - right, height - bottom - top
    vmax = max(present) if present else 1
    nice = _nice(vmax)
    for i in range(5):
        y = bottom + ph * i / 4
        d.add(Line(left, y, left + pw, y, strokeColor=C_BORDER, strokeWidth=0.4, strokeDashArray=[2, 2]))
        d.add(String(left - 3, y - 2.5, _axis(nice * i / 4, metric), fontName=FONT, fontSize=7, fillColor=C_MUTED, textAnchor="end"))
    n = max(1, len(monthly))
    step = pw / n
    every = max(1, -(-n // 8))
    segments, seg, dots = [], [], []  # 단가 선은 값이 없는 달에서 끊습니다
    for i, m in enumerate(monthly):
        cx = left + step * i + step / 2
        if i % every == 0:
            d.add(String(cx, bottom - 10, m["month"][2:].replace("-", "."), fontName=FONT, fontSize=7, fillColor=C_MUTED, textAnchor="middle"))
        v = values[i]
        if v is None:
            if seg:
                segments.append(seg)
                seg = []
            continue
        h = ph * v / nice
        if metric == "unit_price":
            seg += [cx, bottom + h]
            dots.append((cx, bottom + h, bool(m.get("price_flag"))))
        else:
            bw = max(1.2, step * 0.7)
            d.add(Rect(cx - bw / 2, bottom, bw, h, fillColor=C_AQUA if i == len(monthly) - 1 else C_PRIMARY, strokeColor=None))
    if seg:
        segments.append(seg)
    for s in segments:
        if len(s) >= 4:
            d.add(PolyLine(s, strokeColor=C_PRIMARY, strokeWidth=1.2))
    for x, y, flagged in dots:
        d.add(Circle(x, y, 2.6 if flagged else 1.4, fillColor=colors.white if flagged else C_PRIMARY,
                     strokeColor=C_WARN if flagged else C_PRIMARY, strokeWidth=1 if flagged else 0.4))
    if present:  # 월평균 점선(민트)
        avg = sum(present) / len(present)
        ya = bottom + ph * avg / nice
        d.add(Line(left, ya, left + pw, ya, strokeColor=C_MINT, strokeWidth=0.8, strokeDashArray=[4, 3]))
        d.add(String(left + 3, ya + 2.5, "월평균 " + _axis(avg, metric), fontName=FONT_BOLD, fontSize=6, fillColor=C_MINT))
    d.add(Line(left, bottom, left + pw, bottom, strokeColor=C_MUTED, strokeWidth=0.6))
    return d


def _nice(v):
    if v <= 0:
        return 1
    import math
    p = 10 ** math.floor(math.log10(v))
    n = v / p
    return (1 if n <= 1 else 2 if n <= 2 else 2.5 if n <= 2.5 else 5 if n <= 5 else 10) * p


def _short(v, unit):
    """눈금 값을 반올림 때문에 서로 같은 글자가 되지 않게 필요한 만큼만 소수를 남깁니다(예: 1,500 → 1.5K, 2,000 → 2K)."""
    s = "%.1f" % v
    return (s[:-2] if s.endswith(".0") else s) + unit


def _axis(v, metric):
    if metric == "fob":
        return _short(v / 1e6, "M") if v >= 1e6 else (_short(v / 1e3, "K") if v >= 1e3 else "%.0f" % v)
    if metric == "kg":
        return "{:,.0f}".format(v) if v >= 10 or float(v).is_integer() else ("%.2f" % v).rstrip("0").rstrip(".")
    return "%.2f" % v


# ---------- 본문 ----------
def build_pdf(payload):
    """payload: {"stats": analyze 결과, "ai": ai 결과 또는 None} → PDF bytes."""
    _register_fonts()
    st = _styles()
    stats = payload["stats"]
    ai = payload.get("ai")
    q, s, sup = stats["query"], stats["summary"], stats["suppliers"]
    src = (stats.get("sources") or [{}])[0]
    created = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=theme.CONTENT_TOP,
                            bottomMargin=theme.CONTENT_BOTTOM, title="브라질 시장 분석 %s %s" % (q["code"], q["to"]), author="fionex")
    W = doc.width
    story = []

    story.append(_p("브라질 시장 분석 보고서", st["title"]))
    story.append(_p("브라질 수입 통계(ComexStat)로 %s %s 품목의 수입 추세와 공급국 현황을 정리했습니다. 생성 %s." % (
        q["code_system_label"], q["code"], created), st["lead"]))

    countries = ", ".join(_country(c) for c in q.get("countries") or []) or "전체 국가"
    story.append(_table([
        ["항목", "내용"],
        ["대상 시장", "브라질 · 수입"],
        ["품목", "%s %s%s" % (q["code_system_label"], q["code"], (" · " + q["code_name"]) if q.get("code_name") else "")],
        ["기간", "%s ~ %s (%d개월)" % (q["from"], q["to"], q["months"])],
        ["비교 공급국", countries],
    ], [32 * mm, W - 32 * mm], st, zebra=False))
    story.append(_p("무역 통계는 해당 코드의 전체 시장이며 일반 원사·재생 원사·리젠 T2T를 구분하지 않습니다. T2T 수요나 시장 규모로 해석하지 마세요. "
                    "평균 수입단가는 FOB 기준이며 견적·판매가격·도착가격이 아닙니다. 공급국은 ComexStat 기준 원산지 국가입니다.", st["notice"]))
    if src.get("cache_status") == "snapshot":
        story.append(_p(snapshot_label(src), st["notice"]))
    for n in stats.get("notes") or []:
        story.append(_p("· " + n, st["small"]))

    # ① 핵심 수치
    story.append(_h2("① 핵심 수치", "ComexStat 집계"))
    if not stats.get("has_data"):
        story.append(_p("조회 결과 없음: 이 조건에는 ComexStat 수입 기록이 없습니다(조회 실패나 0 확인이 아님).", st["body"]))
    else:
        pp = s["prior_period"]
        story.append(theme.stat_cards([
            ("수입액 (FOB, USD)", usd(s["fob"]), C_PRIMARY, "전년 동기 대비 " + yoy(s["yoy"]["fob"])),
            ("수입량 (t)", tons(s["kg"]), C_PRIMARY, "전년 동기 대비 " + yoy(s["yoy"]["kg"])),
            ("평균 수입단가 (USD/kg)", price(s["unit_price"], s.get("unit_price_reason")), C_MINT, "전년 동기 대비 " + yoy(s["yoy"]["unit_price"])),
        ], W, value_size=15))
        story.append(Spacer(1, 6))
        story.append(_table([
            ["지표", "값", "전년 동기 대비 (%s~%s)" % (pp["from"], pp["to"])],
            ["수입액 (FOB, USD)", usd(s["fob"]), yoy(s["yoy"]["fob"])],
            ["수입량 (t)", tons(s["kg"]), yoy(s["yoy"]["kg"])],
            ["평균 수입단가 (FOB, USD/kg)", price(s["unit_price"], s.get("unit_price_reason")), yoy(s["yoy"]["unit_price"])],
        ], [60 * mm, 50 * mm, W - 110 * mm], st, num_cols=(1, 2)))
        story.append(_p("증감률 = (현재 − 전년 동기) ÷ 전년 동기 × 100. 평균 수입단가 = FOB 합계 ÷ 순중량 합계.", st["small"]))

        # ② 월별 추세
        story.append(_h2("② 시장 추세 (월별)", "ComexStat 월별 집계"))
        for metric, label in (("fob", "수입액 월별 추이 (USD)"), ("kg", "수입량 월별 추이 (t)"), ("unit_price", "평균 수입단가(FOB) 월별 추이 (USD/kg)")):
            story.append(KeepTogether([_p(label, st["cell_head"]), _chart(stats["monthly"], metric, W)]))
        story.append(_p("막대·점이 없는 달은 수입 기록이 없는 달입니다. 단가 그래프의 테두리 점은 '확인 필요'(중앙값의 ½ 미만 또는 2배 초과).", st["small"]))
        mrows = [["월", "수입액 (USD)", "전년 대비", "수입량 (t)", "전년 대비", "단가 (USD/kg)", "전년 대비"]]
        muted = []
        for m in stats["monthly"]:
            if not m["has_record"]:
                muted.append(len(mrows))
                mrows.append([m["month"], "기록 없음", "—", "—", "—", "—", "—"])
                continue
            flag = " ※" if m.get("price_flag") else ""
            mrows.append([m["month"], usd(m["fob"]), yoy_cell(m["yoy"]["fob"]), tons(m["kg"]), yoy_cell(m["yoy"]["kg"]),
                          price(m["unit_price"], m.get("unit_price_reason")) + flag, yoy_cell(m["yoy"]["unit_price"])])
        story.append(Spacer(1, 6))
        story.append(_p("월별 상세", st["cell_head"]))
        story.append(Spacer(1, 3))
        story.append(_table(mrows, [20 * mm, 32 * mm, 22 * mm, 27 * mm, 22 * mm, 30 * mm, W - 153 * mm], st,
                            num_cols=(1, 2, 3, 4, 5, 6), muted_rows=muted))
        story.append(_p("— : 기록이 없거나 전년 같은 달 기록이 없어 계산할 수 없음 · ※ : 단가 확인 필요(중앙값의 ½ 미만 또는 2배 초과) · "
                        "단가 = 평균 수입단가(FOB)", st["small"]))

        # ③ 공급국
        story.append(_h2("③ 공급국 비교", "수입액 기준 순위"))
        story.append(_p("수입액 기준 순위. 비중의 분모는 같은 품목·기간의 브라질 전체 수입액. 기간 내 공급국 %d개국." % sup["count"], st["small"]))
        k = sup.get("korea")
        story.append(theme.note_box(_p("한국 현황: " + ("%d위 / %d개국 · 비중 %s · 수입액 USD %s · 수입량 %s t · 평균 수입단가 %s USD/kg" % (
            k["rank"], sup["count"], pct(k["share"]), usd(k["fob"]), tons(k["kg"]), price(k["unit_price"])) if k
            else "조회 기간에 한국(Coreia do Sul)의 수입 기록이 없습니다."), st["body"]), W, "mint"))
        story.append(Spacer(1, 3))
        story.append(_supplier_table(sup["top"], W, st))
        if sup.get("selected"):
            story.append(Spacer(1, 8))
            story.append(_p("선택한 공급국 (비중은 전체 시장 기준)", st["cell_head"]))
            story.append(Spacer(1, 3))
            story.append(_supplier_table(sup["selected"], W, st))
        story.append(_p("— : 기록이 없거나 전년 같은 기간 기록이 없어 계산할 수 없음 · 파란 줄 = 한국 · 단가 = 평균 수입단가(FOB)", st["small"]))

    # ④ AI 분석
    story.append(_h2("④ AI 분석", "출처로 확인된 사실 행만"))
    story.extend(_ai_section(ai, W, st))

    # ⑤ 근거 자료
    story.append(_h2("⑤ 근거 자료"))
    story.append(_p("%s · %s" % (src.get("name", "ComexStat"), "지표: FOB 금액(USD), 순중량(kg)"), st["body"]))
    story.append(_link(src.get("url"), st["cell"]))
    story.append(_p("자료 갱신일 %s · 최신 제공 월 %s · 자료 받은 시각 %s" % (
        src.get("data_updated") or "확인 안 됨", src.get("latest_month") or "확인 안 됨", src.get("fetched_at") or "확인 안 됨"), st["small"]))
    if src.get("cache_status") == "snapshot":
        story.append(_p(snapshot_label(src) + " — ComexStat 조회에 실패해 MDIC가 공개한 원본 CSV를 미리 받아 요약한 시연용 자료로 만들었습니다. "
                        "실시간 조회 결과가 아닙니다.", st["notice"]))

    note = "%s %s · %s~%s" % (q["code_system_label"], q["code"], q["from"], q["to"])
    doc.build(story, canvasmaker=theme.numbered_canvas("MARKET REPORT", datetime.now(KST).strftime("%Y.%m.%d"), MARGIN, note))
    return buf.getvalue()


def _supplier_table(lst, W, st):
    rows = [["순위", "공급국", "수입액 (USD)", "비중", "수입량 (t)", "단가 (USD/kg)", "수입액 전년 대비"]]
    hl, muted = [], []
    for c in lst:
        if c.get("no_record"):
            muted.append(len(rows))
            rows.append(["—", _country(c["country"]), "기록 없음", "—", "—", "—", "—"])
            continue
        if (c.get("country") or {}).get("code") == "190":
            hl.append(len(rows))
        # 공급국 단가에는 '확인 필요'를 붙이지 않습니다(화면과 같음, 2026-10-26 담당자 지시). 월별 표의 표시는 유지.
        rows.append([str(c["rank"]), _country(c["country"]), usd(c["fob"]), pct(c["share"]), tons(c["kg"]),
                     price(c["unit_price"], c.get("unit_price_reason")), yoy_cell(c["yoy"]["fob"])])
    return _table(rows, [13 * mm, 50 * mm, 30 * mm, 15 * mm, 24 * mm, 22 * mm, W - 154 * mm], st,
                  num_cols=(0, 2, 3, 4, 5, 6), highlight=hl, muted_rows=muted)


def _ai_section(ai, W, st):
    out = []
    if not ai:
        out.append(_p("AI 분석을 실행하지 않았습니다. 위 수치는 모두 코드로 계산한 값입니다.", st["body"]))
        return out
    if not ai.get("has_draft", True):
        out.append(_p("AI 분석을 시작하지 못해 결과가 없습니다(%s). 위 수치는 모두 코드로 계산한 값입니다." % (
            (ai.get("error") or {}).get("message") or "사유 미확인"), st["notice"]))
        return out
    if not ai.get("complete"):
        err = ai.get("error") or {}
        out.append(_p("검토 미완료: 5차례 검토 중 %d회만 끝났습니다. %s 아래 표는 마지막으로 끝난 단계의 결과입니다." % (
            len(ai.get("rounds") or []), err.get("message") or ""), st["notice"]))
    rows = [["구분", "핵심 내용", "영업·마케팅 시사점", "판정", "출처·기준일"]]
    # 출처로 확인된 사실 행만 싣습니다(추정·미확인 행 삭제, 2026-10-26 담당자 지시).
    for r in [r for r in ai.get("rows") or [] if r.get("status") == "사실"]:
        srcs = [_p("%s %s (%s)" % (x["id"], x.get("name", ""), x.get("date", "")), st["cell"]) for x in r.get("sources") or []] \
            or "출처 없음"
        status = r["status"] + ((" · 확인 필요: " + "; ".join(r["flags"])) if r.get("flags") else "")
        rows.append([r["section"], r["content"], r["implication"], status, srcs])
    if len(rows) == 1:
        out.append(_p("표에 남은 행이 없습니다(근거 부족).", st["body"]))
    else:
        out.append(_table(rows, [20 * mm, 56 * mm, 48 * mm, 16 * mm, W - 140 * mm], st, valign="TOP"))
    if ai.get("gaps"):
        out.append(_p("근거 부족으로 작성하지 않은 내용: " + "; ".join(ai["gaps"]), st["small"]))
    if ai.get("remaining_findings"):
        out.append(_p("자동 검사에서 남은 문제: " + "; ".join(ai["remaining_findings"]), st["small"]))
    usage = ai.get("usage") or {}
    out.append(Spacer(1, 8))
    out.append(_p("검토 기록 (프롬프트 %s / %s, 모델 %s, 호출 %s회)" % (
        (ai.get("prompt_versions") or {}).get("draft", "?"), (ai.get("prompt_versions") or {}).get("review", "?"),
        usage.get("model") or "?", usage.get("calls", "?")), st["cell_head"]))
    out.append(Spacer(1, 3))
    rrows = [["회차", "확인한 항목", "수정 사항", "미해결", "완료"]]
    for r in ai.get("rounds") or []:
        rrows.append(["%d. %s" % (r["number"], r["title"]), "; ".join(r.get("checked") or []) or "-",
                      "; ".join(r.get("changes") or []) or "수정 없음", "; ".join(r.get("unresolved") or []) or "-",
                      "완료" if r.get("status") == "done" else "미완료"])
    for n in range(len(ai.get("rounds") or []) + 1, (ai.get("rounds_total") or 5) + 1):
        rrows.append(["%d회차" % n, "-", "-", "-", "미실행"])
    out.append(_table(rrows, [30 * mm, 50 * mm, 45 * mm, 38 * mm, W - 163 * mm], st, valign="TOP"))
    removed = ai.get("removed_rows") or []
    if removed:
        out.append(_p("출처로 확인되지 않아 표에서 뺀 항목 %d건: %s" % (
            len(removed), "; ".join("%s · %s" % (r.get("section", ""), r.get("content", "")) for r in removed)), st["small"]))
    return out


# ---------- 바이어별 AI 브리핑 PDF ----------
BRIEF_SECTIONS = (("overview", "회사 개요"), ("market_context", "시장 맥락"), ("approach_points", "접근 포인트"))


def _bullet(text, sources, style, mark="• "):
    ids = " ".join("[%s]" % s["id"] for s in sources)
    return Paragraph(escape(mark + text) + ((' <font color="#55657d" size="7">%s</font>' % escape(ids)) if ids else ""), style)


def build_briefing_pdf(b):
    """buyer_briefing.run 결과(서버 보관본) → PDF bytes. AI를 다시 부르지 않고 화면과 같은 내용만 그립니다."""
    _register_fonts()
    st = _styles()
    q_style = ParagraphStyle("q", parent=st["body"], fontName=FONT_BOLD, spaceBefore=5)
    a_style = ParagraphStyle("a", parent=st["body"], leftIndent=10, textColor=C_MUTED)
    c, m = b["company"], b["market"]
    created = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=theme.CONTENT_TOP,
                            bottomMargin=theme.CONTENT_BOTTOM, title="바이어 AI 브리핑 %s" % c["razao_social"], author="fionex")
    W = doc.width
    story = [_p("바이어 AI 브리핑", st["title"]),
             _p("%s에 대해 출처 있는 자료로 AI가 작성한 영업 준비 초안입니다. 연락 전 원문을 확인하세요." % c["razao_social"], st["lead"]),
             _p("PDF 생성 %s · 브리핑 생성 %s" % (created, b.get("generated_at") or "?"), st["small"]),
             Spacer(1, 4)]
    market = ("%s %s · %s~%s" % (m["query"]["code_system_label"], m["query"]["code"], m["query"]["from"], m["query"]["to"])
              if m.get("included") else (m.get("note") or "시장 통계 미포함"))
    fantasia = c.get("nome_fantasia")
    story.append(_table([
        ["항목", "내용"],
        ["회사명", c["razao_social"] + ((" · " + fantasia) if fantasia and fantasia != c["razao_social"] else "")],
        ["CNPJ", c["cnpj"]],
        ["지역", "%s, %s" % (c.get("municipio") or "", c.get("uf") or "")],
        ["업종", "%s (%s)" % (c.get("cnae_label") or "", c.get("cnae") or "")],
        ["우선순위 등급", "%s · %s" % (c.get("grade") or "—", c.get("grade_reason") or "")],
        ["시장 맥락", market],
    ], [32 * mm, W - 32 * mm], st, zebra=False))
    for n in b.get("notes") or []:
        story.append(_p(n, st["notice"]))
    used = {}
    for key, label in BRIEF_SECTIONS:
        story.append(_h2(label, "AI 초안"))
        items = b["sections"].get(key) or []
        if not items:
            story.append(_p("근거가 있는 내용이 없어 쓰지 않았습니다.", st["small"]))
        for it in items:
            used.update({s["id"]: s for s in it["sources"]})
            story.append(_bullet(it["text"], it["sources"], st["body"]))
    story.append(_h2("예상 질문", "AI 초안"))
    if not b.get("questions"):
        story.append(_p("근거가 있는 질문이 없어 쓰지 않았습니다.", st["small"]))
    for q in b.get("questions") or []:
        used.update({s["id"]: s for s in q["sources"]})
        story.append(KeepTogether([_p("Q. " + q["question"], q_style), _bullet(q["answer_direction"], q["sources"], a_style, "A. ")]))
    if b.get("gaps"):
        story.append(Spacer(1, 4))
        story.append(_p("근거 부족으로 쓰지 않은 내용: " + "; ".join(b["gaps"]), st["small"]))
    if b.get("removed"):
        story.append(_h2("코드 검사로 뺀 문장 %d개" % len(b["removed"])))
        for r in b["removed"]:
            story.append(_p("· %s · %s — %s" % (r["section"], r["text"], r["reason"]), st["small"]))
    story.append(_h2("출처"))
    for sid in sorted(used):
        src = used[sid]
        story.append(_p("%s · %s · %s" % (sid, src.get("name") or "", src.get("date") or ""), st["cell"]))
        story.append(_link(src.get("url"), st["small"]))
    u = b.get("usage") or {}
    story.append(Spacer(1, 4))
    story.append(_p("모델 %s · 호출 %s회 · 입력 %s / 출력 %s 토큰 · 프롬프트 %s" % (
        u.get("model") or "-", u.get("calls") or 0, u.get("input_tokens") or 0, u.get("output_tokens") or 0, b.get("prompt_version") or "-"), st["small"]))

    doc.build(story, canvasmaker=theme.numbered_canvas("BUYER BRIEFING", datetime.now(KST).strftime("%Y.%m.%d"), MARGIN,
                                                       "AI 초안(연락 전 원문 확인)"))
    return buf.getvalue()
