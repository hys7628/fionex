"""시장 분석 PDF 출력(A4 세로). 화면에 표시된 결과 dict를 그대로 받아 그립니다. 통계·AI를 다시 호출하지 않습니다.

- ReportLab 5.1.0 + Noto Sans KR(fonts/, OFL). 공통 PDF 입력 검사(common/pdf_utils.py, pypdf)와는 별개입니다.
- 모든 문자열은 XML 이스케이프 후 Paragraph에 넣습니다(기사 제목 등 외부 문자열의 마크업 해석 방지).
- 긴 한글·URL은 CJK 줄바꿈으로 칸 안에서 나눕니다. 긴 표는 머리글 행을 페이지마다 반복합니다.
- 사용 범위상 PDF 수록이 확인되지 않은 기사(pdf_text=False)는 제목·출처·게시일·링크만 넣습니다.
- 결과는 메모리 bytes로만 만들고 디스크에 쓰지 않습니다.
"""
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, PolyLine, Rect, String, Circle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from features.market_analysis.news_sources import safe_url

FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT, FONT_BOLD = "NotoSansKR", "NotoSansKR-Bold"
KST = timezone(timedelta(hours=9))

# 화면 디자인 토큰(static/css/tokens.css) 값 참고
C_TEXT = colors.HexColor("#17243b")
C_MUTED = colors.HexColor("#55657d")
C_BORDER = colors.HexColor("#dde4ee")
C_HEAD = colors.HexColor("#f6f8fb")
C_PRIMARY = colors.HexColor("#1f63d8")
C_PRIMARY_SOFT = colors.HexColor("#e7effd")
C_WARN = colors.HexColor("#8a5300")
C_WARN_SOFT = colors.HexColor("#fdf2df")

_registered = False


def _register_fonts():
    global _registered
    if not _registered:
        pdfmetrics.registerFont(TTFont(FONT, str(FONT_DIR / "NotoSansKR-Regular.ttf")))
        pdfmetrics.registerFont(TTFont(FONT_BOLD, str(FONT_DIR / "NotoSansKR-Bold.ttf")))
        _registered = True


def _styles():
    base = dict(fontName=FONT, textColor=C_TEXT, wordWrap="CJK", alignment=TA_LEFT)
    return {
        "title": ParagraphStyle("title", fontSize=17, leading=23, fontName=FONT_BOLD, **{k: v for k, v in base.items() if k != "fontName"}),
        "h2": ParagraphStyle("h2", fontSize=12.5, leading=17, spaceBefore=10, spaceAfter=4, fontName=FONT_BOLD,
                             **{k: v for k, v in base.items() if k != "fontName"}),
        "body": ParagraphStyle("body", fontSize=9, leading=13, **base),
        "small": ParagraphStyle("small", fontSize=7.5, leading=10.5, textColor=C_MUTED,
                                **{k: v for k, v in base.items() if k != "textColor"}),
        "cell": ParagraphStyle("cell", fontSize=7.8, leading=10.5, **base),
        "cell_num": ParagraphStyle("cell_num", fontSize=7.8, leading=10.5, alignment=2,
                                   **{k: v for k, v in base.items() if k != "alignment"}),
        "cell_head": ParagraphStyle("cell_head", fontSize=7.8, leading=10.5, fontName=FONT_BOLD, textColor=C_MUTED,
                                    **{k: v for k, v in base.items() if k not in ("fontName", "textColor")}),
        "notice": ParagraphStyle("notice", fontSize=8.3, leading=12, textColor=C_WARN, backColor=C_WARN_SOFT,
                                 borderPadding=(4, 6, 4, 6), spaceBefore=4, spaceAfter=6,
                                 **{k: v for k, v in base.items() if k != "textColor"}),
    }


def _p(text, style):
    return Paragraph(escape(str(text if text is not None else "")), style)


def _link(url, style, label=None):
    """http(s) 절대 주소만 링크로 만듭니다. 형식이 틀리면 링크 없이 안내 문구만 넣습니다."""
    url = safe_url(url)
    if not url:
        return _p("원문 주소 형식 오류(링크 미표시)", style)
    safe = escape(url, {'"': "&quot;"})
    return Paragraph('<a href="%s" color="#1a56bd">%s</a>' % (safe, escape(label or url)), style)


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


def _table(rows, widths, st, head_rows=1, num_cols=(), zebra=False, highlight=None):
    data = []
    for ri, row in enumerate(rows):
        cells = []
        for ci, v in enumerate(row):
            if hasattr(v, "wrap") or isinstance(v, list):  # 이미 만든 단락(들)
                cells.append(v)
            elif ri < head_rows:
                cells.append(_p(v, st["cell_head"]))
            else:
                cells.append(_p(v, st["cell_num"] if ci in num_cols else st["cell"]))
        data.append(cells)
    t = Table(data, colWidths=widths, repeatRows=head_rows)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, C_BORDER),
        ("BACKGROUND", (0, 0), (-1, head_rows - 1), C_HEAD),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for r in highlight or []:
        style.append(("BACKGROUND", (0, r), (-1, r), C_PRIMARY_SOFT))
    t.setStyle(TableStyle(style))
    return t


# ---------- 그래프 ----------
def _chart(monthly, metric, width, height=58 * mm):
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
        d.add(Line(left, y, left + pw, y, strokeColor=C_BORDER, strokeWidth=0.4))
        d.add(String(left - 3, y - 2.5, _axis(nice * i / 4, metric), fontName=FONT, fontSize=6, fillColor=C_MUTED, textAnchor="end"))
    n = max(1, len(monthly))
    step = pw / n
    every = max(1, -(-n // 8))
    segments, seg, dots = [], [], []  # 단가 선은 값이 없는 달에서 끊습니다
    for i, m in enumerate(monthly):
        cx = left + step * i + step / 2
        if i % every == 0:
            d.add(String(cx, bottom - 10, m["month"], fontName=FONT, fontSize=5.8, fillColor=C_MUTED, textAnchor="middle"))
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
            bw = max(1.2, step - 1.5)
            d.add(Rect(cx - bw / 2, bottom, bw, h, fillColor=C_PRIMARY, strokeColor=None))
    if seg:
        segments.append(seg)
    for s in segments:
        if len(s) >= 4:
            d.add(PolyLine(s, strokeColor=C_PRIMARY, strokeWidth=1.2))
    for x, y, flagged in dots:
        d.add(Circle(x, y, 2.6 if flagged else 1.4, fillColor=colors.white if flagged else C_PRIMARY,
                     strokeColor=C_WARN if flagged else C_PRIMARY, strokeWidth=1 if flagged else 0.4))
    d.add(Line(left, bottom, left + pw, bottom, strokeColor=C_MUTED, strokeWidth=0.6))
    return d


def _nice(v):
    if v <= 0:
        return 1
    import math
    p = 10 ** math.floor(math.log10(v))
    n = v / p
    return (1 if n <= 1 else 2 if n <= 2 else 2.5 if n <= 2.5 else 5 if n <= 5 else 10) * p


def _axis(v, metric):
    if metric == "fob":
        return ("%.1fM" % (v / 1e6)) if v >= 1e6 else ("%.0fK" % (v / 1e3) if v >= 1e3 else "%.0f" % v)
    if metric == "kg":
        return "{:,.0f}".format(v)
    return "%.2f" % v


# ---------- 본문 ----------
def build_pdf(payload):
    """payload: {"stats": analyze 결과, "news": news 결과 또는 None, "ai": ai 결과 또는 None} → PDF bytes."""
    _register_fonts()
    st = _styles()
    stats = payload["stats"]
    news = payload.get("news")
    ai = payload.get("ai")
    q, s, sup = stats["query"], stats["summary"], stats["suppliers"]
    src = (stats.get("sources") or [{}])[0]
    created = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title="브라질 시장 분석 %s %s" % (q["code"], q["to"]), author="fionex")
    W = doc.width
    story = []

    story.append(_p("브라질 시장 분석 보고서", st["title"]))
    story.append(_p("fionex · 생성 %s · 통계 출처 ComexStat(MDIC)" % created, st["small"]))
    story.append(Spacer(1, 6))

    countries = ", ".join(_country(c) for c in q.get("countries") or []) or "전체 국가"
    story.append(_table([
        ["항목", "내용"],
        ["대상 시장", "브라질 · 수입"],
        ["품목", "%s %s%s" % (q["code_system_label"], q["code"], (" · " + q["code_name"]) if q.get("code_name") else "")],
        ["기간", "%s ~ %s (%d개월)" % (q["from"], q["to"], q["months"])],
        ["비교 공급국", countries],
    ], [32 * mm, W - 32 * mm], st))
    story.append(_p("무역 통계는 해당 코드의 전체 시장이며 일반 원사·재생 원사·리젠 T2T를 구분하지 않습니다. T2T 수요나 시장 규모로 해석하지 마세요. "
                    "평균 수입단가는 FOB 기준이며 견적·판매가격·도착가격이 아닙니다. 공급국은 ComexStat 기준 원산지 국가입니다.", st["notice"]))
    for n in stats.get("notes") or []:
        story.append(_p("· " + n, st["small"]))

    # ① 핵심 수치
    story.append(_p("① 핵심 수치", st["h2"]))
    if not stats.get("has_data"):
        story.append(_p("조회 결과 없음: 이 조건에는 ComexStat 수입 기록이 없습니다(조회 실패나 0 확인이 아님).", st["body"]))
    else:
        pp = s["prior_period"]
        story.append(_table([
            ["지표", "값", "전년 동기 대비 (%s~%s)" % (pp["from"], pp["to"])],
            ["수입액 (FOB, USD)", usd(s["fob"]), yoy(s["yoy"]["fob"])],
            ["수입량 (t)", tons(s["kg"]), yoy(s["yoy"]["kg"])],
            ["평균 수입단가 (FOB, USD/kg)", price(s["unit_price"], s.get("unit_price_reason")), yoy(s["yoy"]["unit_price"])],
        ], [60 * mm, 50 * mm, W - 110 * mm], st, num_cols=(1, 2)))
        story.append(_p("증감률 = (현재 − 전년 동기) ÷ 전년 동기 × 100. 평균 수입단가 = FOB 합계 ÷ 순중량 합계.", st["small"]))

        # ② 월별 추세
        story.append(_p("② 시장 추세 (월별)", st["h2"]))
        for metric, label in (("fob", "수입액 월별 추이 (USD)"), ("kg", "수입량 월별 추이 (t)"), ("unit_price", "평균 수입단가(FOB) 월별 추이 (USD/kg)")):
            story.append(KeepTogether([_p(label, st["body"]), _chart(stats["monthly"], metric, W)]))
        story.append(_p("막대·점이 없는 달은 수입 기록이 없는 달입니다. 단가 그래프의 테두리 점은 '확인 필요'(중앙값의 ½ 미만 또는 2배 초과).", st["small"]))
        mrows = [["월", "수입액 (USD)", "전년 동월 대비", "수입량 (t)", "전년 동월 대비", "평균 수입단가 (USD/kg)", "전년 동월 대비"]]
        for m in stats["monthly"]:
            if not m["has_record"]:
                mrows.append([m["month"], "기록 없음", "", "", "", "", ""])
                continue
            flag = " · 확인 필요" if m.get("price_flag") else ""
            mrows.append([m["month"], usd(m["fob"]), yoy(m["yoy"]["fob"]), tons(m["kg"]), yoy(m["yoy"]["kg"]),
                          price(m["unit_price"], m.get("unit_price_reason")) + flag, yoy(m["yoy"]["unit_price"])])
        story.append(Spacer(1, 4))
        story.append(_table(mrows, [16 * mm, 27 * mm, 25 * mm, 22 * mm, 25 * mm, 32 * mm, W - 147 * mm], st, num_cols=(1, 2, 3, 4, 5, 6)))

        # ③ 공급국
        story.append(_p("③ 공급국 비교", st["h2"]))
        story.append(_p("수입액 기준 순위. 비중의 분모는 같은 품목·기간의 브라질 전체 수입액. 기간 내 공급국 %d개국." % sup["count"], st["small"]))
        k = sup.get("korea")
        story.append(_p("한국 현황: " + ("%d위 / %d개국 · 비중 %s · 수입액 USD %s · 수입량 %s t · 평균 수입단가 %s USD/kg" % (
            k["rank"], sup["count"], pct(k["share"]), usd(k["fob"]), tons(k["kg"]), price(k["unit_price"])) if k
            else "조회 기간에 한국(Coreia do Sul)의 수입 기록이 없습니다."), st["body"]))
        story.append(Spacer(1, 3))
        story.append(_supplier_table(sup["top"], W, st))
        if sup.get("selected"):
            story.append(_p("선택한 공급국 (비중은 전체 시장 기준)", st["body"]))
            story.append(_supplier_table(sup["selected"], W, st))

    # ④ AI 분석
    story.append(_p("④ AI 분석", st["h2"]))
    story.extend(_ai_section(ai, W, st))

    # ⑤ 근거 자료
    story.append(_p("⑤ 근거 자료", st["h2"]))
    story.append(_p("%s · %s" % (src.get("name", "ComexStat"), "지표: FOB 금액(USD), 순중량(kg)"), st["body"]))
    story.append(_link(src.get("url"), st["cell"]))
    story.append(_p("자료 갱신일 %s · 최신 제공 월 %s · 자료 받은 시각 %s" % (
        src.get("data_updated") or "확인 안 됨", src.get("latest_month") or "확인 안 됨", src.get("fetched_at") or "확인 안 됨"), st["small"]))
    story.extend(_news_section(news, W, st))

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont(FONT, 7)
        canvas.setFillColor(C_MUTED)
        canvas.drawString(16 * mm, 9 * mm, "fionex 시장 분석 · %s %s · %s~%s" % (q["code_system_label"], q["code"], q["from"], q["to"]))
        canvas.drawRightString(A4[0] - 16 * mm, 9 * mm, "%d쪽" % d.page)
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def _supplier_table(lst, W, st):
    rows = [["순위", "공급국", "수입액 (USD)", "비중", "수입량 (t)", "평균 수입단가 (USD/kg)", "수입액 전년 대비"]]
    hl = []
    for c in lst:
        if c.get("no_record"):
            rows.append(["—", _country(c["country"]), "조회 기간 수입 기록 없음", "", "", "", ""])
            continue
        if (c.get("country") or {}).get("code") == "190":
            hl.append(len(rows))
        flag = " · 확인 필요" if c.get("price_flag") else ""
        rows.append([str(c["rank"]), _country(c["country"]), usd(c["fob"]), pct(c["share"]), tons(c["kg"]),
                     price(c["unit_price"], c.get("unit_price_reason")) + flag, yoy(c["yoy"]["fob"])])
    return _table(rows, [11 * mm, 44 * mm, 27 * mm, 14 * mm, 22 * mm, 30 * mm, W - 148 * mm], st,
                  num_cols=(0, 2, 3, 4, 5, 6), highlight=hl)


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
    rows = [["구분", "핵심 내용", "영업·마케팅 시사점", "사실/추정/미확인", "출처·기준일"]]
    for r in ai.get("rows") or []:
        srcs = [_p("%s %s (%s)" % (x["id"], x.get("name", ""), x.get("date", "")), st["cell"]) for x in r.get("sources") or []] \
            or "출처 없음"
        status = r["status"] + ((" · 확인 필요: " + "; ".join(r["flags"])) if r.get("flags") else "")
        rows.append([r["section"], r["content"], r["implication"], status, srcs])
    if len(rows) == 1:
        out.append(_p("표에 남은 행이 없습니다(근거 부족).", st["body"]))
    else:
        out.append(_table(rows, [18 * mm, 52 * mm, 48 * mm, 24 * mm, W - 142 * mm], st))
    if ai.get("gaps"):
        out.append(_p("근거 부족으로 작성하지 않은 내용: " + "; ".join(ai["gaps"]), st["small"]))
    if ai.get("remaining_findings"):
        out.append(_p("자동 검사에서 남은 문제: " + "; ".join(ai["remaining_findings"]), st["small"]))
    usage = ai.get("usage") or {}
    out.append(_p("검토 기록 (프롬프트 %s / %s, 모델 %s, 호출 %s회)" % (
        (ai.get("prompt_versions") or {}).get("draft", "?"), (ai.get("prompt_versions") or {}).get("review", "?"),
        usage.get("model") or "?", usage.get("calls", "?")), st["body"]))
    rrows = [["회차", "확인한 항목", "수정 사항", "미해결", "완료"]]
    for r in ai.get("rounds") or []:
        rrows.append(["%d. %s" % (r["number"], r["title"]), "; ".join(r.get("checked") or []) or "-",
                      "; ".join(r.get("changes") or []) or "수정 없음", "; ".join(r.get("unresolved") or []) or "-",
                      "완료" if r.get("status") == "done" else "미완료"])
    for n in range(len(ai.get("rounds") or []) + 1, (ai.get("rounds_total") or 5) + 1):
        rrows.append(["%d회차" % n, "-", "-", "-", "미실행"])
    out.append(_table(rrows, [30 * mm, 50 * mm, 45 * mm, 38 * mm, W - 163 * mm], st))
    return out


def _news_section(news, W, st):
    out = []
    if not news:
        out.append(_p("뉴스·보고서는 수집하지 않았습니다.", st["small"]))
        return out
    # 출처별 연결 상태(화면과 같은 3열). 건수는 데이터(count)에만 남기고 표에는 넣지 않습니다.
    srows = [["출처", "상태", "안내"]]
    for s in news.get("sources") or []:
        srows.append([s["label"], s["status_text"], s.get("message") or s.get("usage_note") or ""])
    if len(srows) == 1:
        srows.append(["-", "-", "출처 상태 정보가 없습니다."])
    out.append(Spacer(1, 4))
    out.append(_table(srows, [36 * mm, 28 * mm, W - 64 * mm], st))
    w = news.get("window") or {}
    items, others = news.get("items") or [], news.get("other_items") or []
    out.append(_p("요청 수집 기간 %s~%s(최근 %s개월) · 섬유 업계 핵심 기사 %d건 / 중복 제거 후 후보 %d건 · 주제 기준 밖 수집 기사 %d건" % (
        w.get("from", "?"), w.get("to", "?"), w.get("months", "?"), len(items), news.get("candidates", 0), len(others)), st["small"]))
    for n in w.get("notes") or []:
        out.append(_p(n, st["notice"]))
    for s in news.get("sources") or []:
        if s.get("stale"):
            out.append(_p("%s: 새 조회 실패로 %s에 받은 이전 자료를 표시했습니다." % (s["label"], s.get("collected_at") or "?"), st["notice"]))
    if any(s.get("source") == "newsdata" and s.get("state") == "ok" for s in news.get("sources") or []):
        out.append(_p("일반 뉴스: Powered by NewsData.io (https://newsdata.io). 무료 플랜이라 최근 48시간 기사만 검색했고 본문은 받지 않았습니다. "
                      "언론사 설명은 PDF에 넣지 않고 제목·링크만 수록합니다. 기사 저작권은 각 언론사에 있습니다.", st["small"]))
    if any(it.get("source") == "gdelt" for it in items + others):
        out.append(_p("일반 뉴스 출처: The GDELT Project (https://www.gdeltproject.org/). 일반 뉴스는 제목·메타데이터만 확인했고 기사 본문은 확인하지 않았습니다. "
                      "GDELT 시각은 GDELT가 기사를 처음 발견한 시각이며 게시일이 아닙니다.", st["small"]))
    if any(it.get("title_ko") for it in items + others):
        out.append(_p("포르투갈어·스페인어 제목 아래의 'AI 번역'은 OpenAI 기계 번역이며 원문 제목이 기준입니다.", st["small"]))
    if items:
        out.append(_article_table(items, W, st))
    else:
        out.append(_p("섬유 업계 핵심 기사를 확보하지 못했습니다.", st["small"]))
    if others:
        out.append(_p("그 밖에 수집한 브라질 기사 (주제 기준 밖 · AI 분석에 쓰지 않음)", st["body"]))
        out.append(_article_table(others, W, st))
    return out


def _article_table(items, W, st):
    """기사 제목 | 원문 URL (화면과 같은 구성). 제목 칸에 ID·AI 번역 제목·출처·날짜를 함께 적습니다."""
    rows = [["기사 제목", "원문 URL"]]
    access = {"full_text": "원문 확보(본문 미수록)", "description": "제목·언론사 설명만 확인", "title_only": "제목·메타데이터만 확인"}
    for it in items:
        date = ("게시일 " + it["published"]) if it.get("published") else (
            ("GDELT 최초 발견 " + it["seen_at"]) if it.get("seen_at") else "날짜 미확인")
        meta = " · ".join(filter(None, [it.get("source_name"), date, access.get(it.get("access"), it.get("access")),
                                        "" if it.get("pdf_text") else "이용 범위 확인 필요"]))
        title = [_p("%s %s" % (it.get("id") or "", it["title"]), st["cell"])]
        if it.get("title_ko"):
            title.append(_p("AI 번역: " + it["title_ko"], st["cell"]))
        title.append(_p(meta, st["small"]))
        rows.append([title, _link(it.get("url"), st["small"])])
    return _table(rows, [110 * mm, W - 110 * mm], st)
