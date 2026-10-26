"""시장 분석 PDF 출력(A4 세로). 화면에 표시된 결과 dict를 그대로 받아 그립니다. 통계·AI를 다시 호출하지 않습니다.

- ReportLab 5.1.0 + 공통 Pretendard(static/fonts/pretendard/, OFL, common/config.py PDF_FONT_FILES). 공통 PDF 입력 검사(common/pdf_utils.py, pypdf)와는 별개입니다.
- 모든 문자열은 XML 이스케이프 후 Paragraph에 넣습니다(외부 문자열·AI 출력의 마크업 해석 방지).
- 긴 한글·URL은 CJK 줄바꿈으로 칸 안에서 나눕니다. 긴 표는 머리글 행을 페이지마다 반복합니다.
- 결과는 메모리 bytes로만 만들고 디스크에 쓰지 않습니다.
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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from common.config import PDF_FONT_FILES, PDF_FONT_NAMES
from features.market_analysis import buyers


FONT, FONT_BOLD = PDF_FONT_NAMES["regular"], PDF_FONT_NAMES["bold"]
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
        pdfmetrics.registerFont(TTFont(FONT, str(PDF_FONT_FILES["regular"])))
        pdfmetrics.registerFont(TTFont(FONT_BOLD, str(PDF_FONT_FILES["bold"])))
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
    """payload: {"stats": analyze 결과, "ai": ai 결과 또는 None} → PDF bytes."""
    _register_fonts()
    st = _styles()
    stats = payload["stats"]
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

    # ⑥ 바이어 목록(화면과 같은 기준 자료 파일, 전체 목록)
    story.append(_p("⑥ 바이어 목록 (리젠 T2T 잠재 바이어)", st["h2"]))
    story.extend(_buyer_section(buyers.load(), W, st))

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont(FONT, 7)
        canvas.setFillColor(C_MUTED)
        canvas.drawString(16 * mm, 9 * mm, "fionex 시장 분석 · %s %s · %s~%s" % (q["code_system_label"], q["code"], q["from"], q["to"]))
        canvas.drawRightString(A4[0] - 16 * mm, 9 * mm, "%d쪽" % d.page)
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def _buyer_section(d, W, st):
    out = [_p(n, st["notice"]) for n in d["notes"]]
    if not d["ready"]:
        out.append(_p("기준 자료가 아직 없습니다(buyer_data_builder로 생성 후 표시).", st["body"]))
        return out
    lst = d["companies"]
    g = d["counts"].get("grades") or {}
    out.append(_p("전체 %d곳(A %d · B %d · C %d) · 재생·T2T 근거 %d곳 · 조건: 주 업종 대상 CNAE, 활성, 법인, 규모 '%s'. 우선순위 등급순. %s" % (
        len(lst), g.get("A", 0), g.get("B", 0), g.get("C", 0), d["counts"]["with_evidence"], d["filters"]["porte"], d.get("grade_note") or ""), st["small"]))
    for rule in d.get("grade_rules") or []:
        out.append(_p("· " + rule, st["small"]))
    rows = [["#", "회사명 · CNPJ", "등급 · 근거", "지역(주·시)", "업종(CNAE)", "대표 전화 · 회사 도메인", "재생·T2T 근거"]]
    for i, c in enumerate(lst, 1):
        name = [_p(c["razao_social"], st["cell"])] + ([_p(c["nome_fantasia"], st["small"])] if c.get("nome_fantasia") else []) + \
            [_p("CNPJ " + c["cnpj"], st["small"])]
        grade = [_p(c.get("grade") or "—", st["cell_head"]), _p(c.get("grade_reason") or "", st["small"])]
        contact = " / ".join(c["phones"] + (["도메인 " + c["domain"]] if c.get("domain") else [])) or "등록 없음"
        ev = [p for e in c["evidence"] for p in (_link(e.get("url"), st["cell"], e.get("title")), _p("확인 " + str(e.get("checked_at")), st["small"]))]
        rows.append([str(i), name, grade, "%s · %s" % (c.get("uf") or "", c.get("municipio") or ""),
                     "%s %s" % (c["cnae"], c.get("cnae_desc") or ""), contact, ev or "—"])
    out.append(_table(rows, [8 * mm, 38 * mm, 34 * mm, 22 * mm, 30 * mm, 30 * mm, W - 162 * mm], st, num_cols=(0,)))
    src = d["source"]
    out.append(_p("출처: %s · 자료 기준월 %s · 생성 %s" % (src["name"], src["reference_month"], src.get("generated_at")), st["small"]))
    out.append(_link(src["url"], st["cell"]))
    return out


def _supplier_table(lst, W, st):
    rows = [["순위", "공급국", "수입액 (USD)", "비중", "수입량 (t)", "평균 수입단가 (USD/kg)", "수입액 전년 대비"]]
    hl = []
    for c in lst:
        if c.get("no_record"):
            rows.append(["—", _country(c["country"]), "조회 기간 수입 기록 없음", "", "", "", ""])
            continue
        if (c.get("country") or {}).get("code") == "190":
            hl.append(len(rows))
        # 공급국 단가에는 '확인 필요'를 붙이지 않습니다(화면과 같음, 2026-10-26 담당자 지시). 월별 표의 표시는 유지.
        rows.append([str(c["rank"]), _country(c["country"]), usd(c["fob"]), pct(c["share"]), tons(c["kg"]),
                     price(c["unit_price"], c.get("unit_price_reason")), yoy(c["yoy"]["fob"])])
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
    # 출처로 확인된 사실 행만 싣습니다(추정·미확인 행 삭제, 2026-10-26 담당자 지시).
    for r in [r for r in ai.get("rows") or [] if r.get("status") == "사실"]:
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
    removed = ai.get("removed_rows") or []
    if removed:
        out.append(_p("출처로 확인되지 않아 표에서 뺀 항목 %d건: %s" % (
            len(removed), "; ".join("%s · %s" % (r.get("section", ""), r.get("content", "")) for r in removed)), st["small"]))
    return out
