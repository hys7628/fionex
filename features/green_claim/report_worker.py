"""검수 결과 PDF 보고서 만들기. report_service가 별도 프로세스(multiprocessing spawn)에서 run()을 실행합니다.

- 시간 제한·프로세스 종료는 report_service.py가 담당합니다. 이 모듈은 Flask를 import하지 않으며 reportlab은 실행할 때만 불러옵니다.
- 입력은 report_service가 형식·일관성을 확인한 검수 결과입니다. 내용을 고치거나 기준 자료로 보충하지 않습니다.
- 모든 사용자·AI·기준 문자열은 ReportLab 문단 마크업으로 해석되지 않게 이스케이프합니다.
- 글꼴: 공통 Pretendard(static/fonts/pretendard/, OFL, common/config.py PDF_FONT_FILES). 한글·라틴·포르투갈어 악센트를 한 글꼴로 그립니다.
  글자마다 글리프가 있는 글꼴을 고르는 구조(latin → ko)는 유지하며 지금은 두 자리 모두 Pretendard입니다.
  글꼴에 없는 문자(이모지·제어문자 등)는 지우지 않고 [U+XXXX]로 대신 표시합니다.
- PDF는 메모리(BytesIO)에서 만들며 디스크에 쓰지 않습니다. 외부 이미지·글꼴·링크 대상을 가져오지 않고 스크립트·첨부를 넣지 않습니다.
- 디자인: 공통 PDF 디자인(common/pdf_theme.py) — 머리 'GREEN CLAIM REPORT'·로고(저장소 안 static/assets 이미지), 큰 제목,
  막대 구역 제목, 검수 결과 요약 숫자 카드, 민트 머리 표, 브랜드 꼬리. 글꼴은 위 GCLatin/GCKo(Pretendard)를 그대로 씁니다.
"""
import io
import json
import unicodedata
from datetime import datetime
from common.config import PDF_FONT_FILES

LATIN_FONTS = dict(PDF_FONT_FILES)
KO_FONTS = dict(PDF_FONT_FILES)
FONT_NAMES = {"latin": {"regular": "GCLatin", "bold": "GCLatin-Bold"}, "ko": {"regular": "GCKo", "bold": "GCKo-Bold"}}

TITLE = "그린 클레임 문구 검수 보고서"
SUBTITLE = "브라질 대상 홍보 문구 표현 위험 검토"
FOOTER = "표현 위험 스크리닝(적법성·사실·인증 보장 아님)"  # 꼬리 왼쪽 'FIONEX | WEAVE A BRIGHTER TOMORROW' 뒤에 붙는 안내
KICKER = "GREEN CLAIM REPORT"

ACTION_LABELS = {"revise_recommended": "수정 권고", "needs_review": "검토 필요", "judgment_withheld": "판단 보류"}
ACTION_ORDER = ("revise_recommended", "needs_review", "judgment_withheld")
# (글자색, 배경색). 색만으로 구분하지 않도록 항상 번호·조치 이름을 함께 씁니다.
TONES = {"revise_recommended": ("#9F1C14", "#FCE4E1"), "needs_review": ("#7A4E00", "#FBEFD3"),
         "judgment_withheld": ("#1C4F8F", "#E1ECFA")}
LANGUAGE_LABELS = {"ko": "한국어", "en": "영어", "pt-BR": "브라질 포르투갈어", "mixed": "여러 언어 혼합", "unknown": "언어 판단 보류"}
NATURE_LABELS = {"law": "법률", "advertising_self_regulation": "광고 자율규제"}
CHECK_LABELS = {
    "no_change_found": "대상 조항 전체를 비교해 변경을 발견하지 못함",
    "partial_checked": "부분 확인(일부 조항은 발췌 문장만 확인)",
    "change_detected": "원문 변경 감지 · 검토 전(기준에 반영 안 됨)",
    "failed": "확인 실패",
    "deferred": "조회 보류(이용 조건 등)",
    "baseline_missing": "비교 기준 부족",
    "not_checked": "확인 기록 없음",
    "not_checked_this_request": "이번 요청에서 확인하지 못함",
    "auto_check_off": "자동 확인 안 함(저장된 기준 사용)",
}
CHECK_MODE_LABELS = {"stored_only": "저장된 기준 사용 · 최신성 자동 확인 안 함"}
UPDATED_UNRECORDED = "업데이트 날짜 미기록"  # 화면(green_claim.js)과 같은 문장
INPUT_MODE_LABELS = {"text": "문구 직접 입력",
                     "file": "홍보물 파일에서 글자 추출·판독 후 사용자가 확인·수정한 문구"}
NO_ALTERNATIVE = "대체 예시를 제공하지 않았습니다."
PLACEHOLDER_STYLE = ('<font name="GCLatin" color="#3D3D3D" backColor="#E2E2E2">', "</font>")
FIXED_LIMITS = [
    "이 보고서는 제공된 CDC·CONAR 기준 범위에서 표현 위험을 AI로 검토한 결과입니다. 모든 오류·위험을 발견한다고 보장하지 않습니다.",
    "파일로 입력한 경우 검수 대상은 원본 파일이 아니라, 추출·판독한 뒤 사용자가 확인·수정한 문구입니다. 추출·판독 누락이나 오류가 있을 수 있습니다.",
    "원본 PDF·Word·이미지 파일을 자동으로 수정하지 않았습니다. 대체 예시는 참고용이며 원본에 적용된 문장이 아닙니다.",
    "이 보고서는 브라우저가 보관하던 마지막 검수 결과로 만들었습니다. 서버는 결과의 형식과 내부 일관성만 확인했으며, "
    "결과가 실제 AI 응답과 같다는 것을 증명하지 않습니다. PDF를 만들 때 AI 검수나 공식 출처 확인을 다시 하지 않았습니다.",
]


class _Fonts:
    """등록한 글꼴과 글자별 글리프 표(cmap)."""

    def __init__(self):
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        self.cmaps = {}
        for weight in ("regular", "bold"):
            for family, path in (("latin", LATIN_FONTS[weight]), ("ko", KO_FONTS[weight])):
                if not path.is_file():
                    raise FileNotFoundError("font")
                name = FONT_NAMES[family][weight]
                font = TTFont(name, str(path))
                pdfmetrics.registerFont(font)
                self.cmaps[name] = font.face.charToGlyph

    def pick(self, char, weight):
        code = ord(char)
        for family in ("latin", "ko"):
            name = FONT_NAMES[family][weight]
            if code in self.cmaps[name]:
                return name
        return None


def _escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _placeholder(char):
    return PLACEHOLDER_STYLE[0] + "[U+%04X]" % ord(char) + PLACEHOLDER_STYLE[1]


def _compose(text, fonts, weight):
    """결합 문자(예: e + U+0301)를 합성형이 글꼴에 있을 때만 화면 표시용으로 합칩니다(그 밖은 그대로)."""
    out = []
    for char in text:
        if out and unicodedata.combining(char):
            merged = unicodedata.normalize("NFC", out[-1] + char)
            if len(merged) == 1 and fonts.pick(merged, weight):
                out[-1] = merged
                continue
        out.append(char)
    return out


class Writer:
    """문자열 → ReportLab 문단 마크업(이스케이프·글꼴 전환·대체 표시). 문자열을 마크업으로 해석하지 않습니다."""

    def __init__(self, fonts):
        self.fonts = fonts

    def rich(self, text, bold=False, prev=None):
        """prev: 원문에서 바로 앞 글자(None 또는 줄바꿈이면 줄 시작). 연속 공백·줄 시작 공백은 줄바꿈 없는 공백으로 유지."""
        weight = "bold" if bold else "regular"
        base = FONT_NAMES["latin"][weight]
        parts, run_font, run = [], None, []

        def flush():
            if run:
                chunk = "".join(run)
                parts.append(chunk if run_font == base else f'<font name="{run_font}">{chunk}</font>')
                run.clear()

        last = prev
        for char in _compose(text, self.fonts, weight):
            if char == "\n":
                flush()
                parts.append("<br/>")
                last = "\n"
                continue
            if char == " ":
                char = " " if last not in (None, "\n", " ") else " "
                font = base
                piece = char
            elif unicodedata.category(char) in ("Cc", "Cf", "Co", "Cs", "Cn", "Zl", "Zp") or not self.fonts.pick(char, weight):
                flush()
                parts.append(_placeholder(char))
                last = char
                continue
            else:
                font = self.fonts.pick(char, weight)
                piece = _escape(char)
            if font != run_font:
                flush()
                run_font = font
            run.append(piece)
            last = " " if char == " " else char
        flush()
        return "".join(parts)


def _time(value):
    """ISO 8601(시간대 포함) → '2026-10-25 16:31:44 (한국 시간)'. 없으면 None(날짜를 만들지 않음)."""
    if not value:
        return None
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    offset = stamp.strftime("%z")
    offset = offset[:3] + ":" + offset[3:]
    return stamp.strftime("%Y-%m-%d %H:%M:%S") + (" (한국 시간)" if offset == "+09:00" else f" (UTC{offset})")


def build_pdf(payload):
    """검증한 보고서 입력 → PDF bytes."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    from common import pdf_theme as theme

    fonts = _Fonts()
    writer = Writer(fonts)
    review = payload["review"]
    items = review["items"]
    refs = review["criteria_refs"]
    criteria = review["criteria"]
    sources = {source["id"]: source for source in criteria["sources"]}

    def style(name, size=9.5, bold=False, color="#13233F", leading=None, space_before=0, space_after=3, **extra):
        return ParagraphStyle(name, fontName=FONT_NAMES["latin"]["bold" if bold else "regular"], fontSize=size,
                              leading=leading or size * 1.5, textColor=colors.HexColor(color), alignment=TA_LEFT,
                              spaceBefore=space_before, spaceAfter=space_after, splitLongWords=1,
                              bulletFontName=FONT_NAMES["latin"]["regular"], **extra)

    body = style("body")
    muted = style("muted", size=8.5, color="#54637A")
    label = style("label", size=8.5, bold=True, color="#54637A", space_before=4, space_after=1, keepWithNext=1)
    title = style("title", size=24, bold=True, leading=30, space_after=4)
    h2 = style("h2", size=10.5, bold=True, leading=15, space_before=8, space_after=3, keepWithNext=1, color="#1D6AD4")
    source_line = style("source", size=9.5, leading=15.5, space_after=0)
    box = style("box", size=8.5, color="#13233F", space_after=0)
    width = A4[0] - 36 * mm
    reg, bold_font = FONT_NAMES["latin"]["regular"], FONT_NAMES["latin"]["bold"]

    story = []

    def para(text, st=body, bold=False):
        story.append(Paragraph(writer.rich(text, bold=bold), st))

    def section(text, tag=None):
        story.append(theme.SectionTitle(text, tag, size=13, font=reg, font_bold=bold_font, space_before=14, space_after=6))

    def note(text, tone="info"):
        story.append(theme.note_box(Paragraph(writer.rich(text), box), width, tone))
        story.append(Spacer(1, 6))

    def field(name, value, empty=None):
        if value is None or value == "":
            if empty is None:
                return
            value = empty
        story.append(Paragraph(writer.rich(name, bold=True), label))
        para(value)

    def bullets(values, st=body):
        for value in values:
            story.append(Paragraph(writer.rich(value), st, bulletText="•"))

    # 1. 제목과 검수 범위
    para(TITLE, title, bold=True)
    para(SUBTITLE, style("subtitle", size=10.5, color="#33415A", leading=16, space_after=8))
    note("검수 범위: 브라질 대상 홍보 문구의 표현 위험을 저장된 CDC(소비자보호법)·CONAR(광고 자율규제) 기준으로 검토합니다. "
         "확인하지 않은 것: 수치·환경 성능의 사실성, 인증 보유·유효성, 적법성, 그림·색상·로고 등 디자인. "
         "이 보고서는 위법 여부 확정·사용 승인·친환경 점수가 아닙니다.")
    note("표시 안내: 원문 속 ▶R1 같은 번호는 보고서가 붙인 표시이며 원문 글자가 아닙니다. "
         "회색 바탕의 [U+XXXX]는 PDF 글꼴에 없는 원문 글자(이모지·제어문자 등)를 지우지 않고 코드 번호로 대신 표시한 것입니다. "
         "연속 공백과 줄바꿈은 원문대로 유지했습니다.", "mint")

    # 2. 전체 요약: 조치별 큰 숫자 카드 + 표
    section("1. 검수 결과 요약", "AI 표현 위험 스크리닝")
    summary = review["summary"]
    story.append(theme.stat_cards([
        (ACTION_LABELS[action], str(summary["by_action"][action]), colors.HexColor(TONES[action][0]), None) for action in ACTION_ORDER
    ], width, font=reg, font_bold=bold_font, value_size=26))
    story.append(Spacer(1, 8))
    field("검수 결과를 받은 시각", _time(payload["displayed_at"]) and
          _time(payload["displayed_at"]) + " · 이 컴퓨터 시계 기준, 서버 확인 아님", empty="기록 없음")
    field("보고서 생성 시각", _time(payload["generated_at"]) + " · 서버 시계 기준(검수 시각과 다름)")
    field("입력 방식", INPUT_MODE_LABELS[payload["input_mode"]])
    field("전체 항목 수", f"{summary['total']}개 (발견한 항목 수가 문구의 모든 위험을 뜻하지 않습니다)")
    rows = [[Paragraph(writer.rich(text, bold=True), muted) for text in ("조치", "개수", "항목 번호")]]
    for action in ACTION_ORDER:
        ids = summary["item_ids_by_action"][action]
        rows.append([Paragraph(f'<font color="{TONES[action][0]}">' + writer.rich(ACTION_LABELS[action], bold=True) + "</font>", body),
                     Paragraph(writer.rich(f"{summary['by_action'][action]}개"), body),
                     Paragraph(writer.rich(", ".join(ids) if ids else "없음"), body)])
    story.append(theme.data_table(rows, [32 * mm, 20 * mm, width - 52 * mm], zebra=False))
    story.append(Spacer(1, 4))
    if summary["no_items_message"]:
        story.append(theme.note_box(Paragraph(writer.rich(summary["no_items_message"] + " 항목이 없어도 안전하거나 적법하다는 뜻이 아니며, "
                                                          "그린워싱이 없다는 판정도 아닙니다.", bold=True), box), width, "warning"))
    field("AI 작성 요약", summary["model_summary_ko"])
    if review["model_limitations"]:
        story.append(Paragraph(writer.rich("AI가 보고한 이번 검토의 한계", bold=True), label))
        bullets(review["model_limitations"])

    # 3. 검수한 원문
    section("2. 검수한 원문", "검수 당시 사본")
    para("실제 검수에 사용한 문구입니다. 대상 구절은 배경색으로, 여러 항목이 겹치는 부분은 밑줄을 더해 표시했습니다.", muted)
    story.extend(_original_paragraphs(writer, review["text"], items, source_line))

    # 4. 항목별 검토
    section("3. 주요 검토 항목", "항목별 검토 의견")
    if not items:
        para("검토 항목이 없습니다. " + (summary["no_items_message"] or ""))
    for item in items:
        tone, soft = TONES[item["action"]]
        head = style("item_" + item["id"], size=10.5, bold=True, color=tone, backColor=colors.HexColor(soft),
                     borderPadding=4, space_before=10, space_after=4, keepWithNext=1)
        story.append(Paragraph(writer.rich(f"{item['id']} · {ACTION_LABELS[item['action']]}", bold=True), head))
        field(f"대상 구절 ({LANGUAGE_LABELS[item['quote_language']]}, 원문 위치 {item['start'] + 1}~{item['end']}번째 글자)", item["quote"])
        field("한국어 해석", item["interpretation_ko"])
        field("이유", item["reason_ko"])
        field("수정 방향", item["direction_ko"])
        story.append(Paragraph(writer.rich("대체 예시 (참고용 · 원본을 수정한 것이 아님 · 사람 확인 필요)", bold=True), label))
        alternative = item["alternative"]
        if alternative:
            if alternative["original_text"]:
                field(f"원문 언어 예시({LANGUAGE_LABELS[item['quote_language']]})", alternative["original_text"])
            if alternative["pt_br_text"]:
                field("브라질 포르투갈어 예시", alternative["pt_br_text"])
            field("예시의 한국어 해석", alternative["ko_interpretation"])
            if item["alternative_note_ko"]:
                para(item["alternative_note_ko"], muted)
        else:
            para(item["alternative_note_ko"] or NO_ALTERNATIVE)
            para("예시 대신 위 이유와 수정 방향을 참고해 주세요.", muted)
        field("관련 기준", ", ".join(item["criteria_ids"]) if item["criteria_ids"] else "연결된 기준 없음(판단 보류)")

    # 5. 근거와 출처
    section("4. 근거와 출처", "CDC · CONAR 저장 기준")
    para("원문 요구는 기준 원문이 정한 내용, 서비스 검토 해석은 이 서비스의 검토 관점이며 원문과 같은 효력이 없습니다. "
         "한국어 번역은 이해를 돕는 비공식 번역입니다.", muted)
    if not refs:
        para("이 결과에서 연결된 기준이 없습니다.")
    for criterion_id, ref in refs.items():
        source = sources[ref["source_id"]]
        para(f"{criterion_id} · {NATURE_LABELS[ref['legal_nature']]} · {ref['provisions']} · {ref['title_ko']}", h2, bold=True)
        field("자료", f"{source['title']} ({NATURE_LABELS[source['legal_nature']]})")
        field("원문 요구(원문이 정한 내용)", ref["requirement_ko"], empty="기준 자료에 따로 적힌 원문 요구 없음(아래 원문 발췌·번역 참고)")
        field("서비스 검토 해석(원문과 같은 효력 없음)", ref["review_guidance_ko"])
        field("적용 범위·해석 한계", ref["scope_limits_ko"])
        field("저장된 원문 발췌(포르투갈어)", ref["excerpt_pt"])
        field("한국어 번역(비공식)", ref["translation_ko"])
        field("자료 확보 시각", _time(ref["retrieved_at"]), empty="기록 없음")
        story.append(Paragraph(writer.rich("공식 출처", bold=True), label))
        story.append(Paragraph(f'<a href="{_escape(ref["official_url"])}" color="#1D4ED8"><u>'
                               + writer.rich(ref["official_url"]) + "</u></a>", body))
        if ref["usage_rights_status"] == "ai_use_permission_unconfirmed":
            para("이 자료의 AI 이용 허가는 확인되지 않았습니다(기준 자료 기록).", muted)

    para("검수 당시 기준과 확인 상태", h2, bold=True)
    field("사용 기준", f"기준 버전 {criteria['bundle_version']} · "
          + ("기본 기준" if criteria["active_version"] == "base" else f"활성화된 기준 {criteria['active_version'] or '기록 없음'}")
          + " · 검수 당시 저장된 기준(최신 개정 전체를 확인한 것이 아님). 보고서를 만들 때 기준을 다시 읽거나 바꾸지 않았습니다.")
    field("기준 자료 업데이트 날짜", criteria["criteria_updated_on"] or UPDATED_UNRECORDED)
    field("이번 검수의 공식 출처 확인", CHECK_MODE_LABELS[criteria["check_mode"]])
    for source in criteria["sources"]:
        story.append(Paragraph(writer.rich(f"{source['title']} ({NATURE_LABELS[source['legal_nature']]})", bold=True), label))
        lines = [
            "자료 확보 시각: " + (_time(source["retrieved_at"]) or "기록 없음"),
            "이번 검수의 확인: " + CHECK_LABELS.get(source["check_status"], "상태 기록 없음")
            + (" · 시도 " + _time(source["check_attempted_at"]) if source["check_attempted_at"] else ""),
            "마지막 성공 확인(이전 기록, 조항 비교 완료): " + (_time(source["check_last_success_at"]) or "기록 없음"),
        ]
        if source["check_reason"]:
            lines.append("이유: " + source["check_reason"])
        if source["previous_check_status"]:
            lines.append("이전 출처 확인 기록(이번 검수 아님): " + CHECK_LABELS.get(source["previous_check_status"], "상태 기록 없음")
                         + (" · " + _time(source["previous_check_attempted_at"]) if source["previous_check_attempted_at"] else ""))
        if source["usage_rights_status"] == "ai_use_permission_unconfirmed":
            lines.append("AI 이용 허가: 확인되지 않음")
        bullets(lines)
        story.append(Paragraph(f'<a href="{_escape(source["official_url"])}" color="#1D4ED8"><u>'
                               + writer.rich(source["official_url"]) + "</u></a>", muted))
    story.append(Paragraph(writer.rich("기준 확인 경고", bold=True), label))
    bullets(criteria["warnings"] or ["경고 없음"])
    story.append(Paragraph(writer.rich("공식 원문 변경이 감지됐지만 아직 기준에 반영하지 않은 항목", bold=True), label))
    if criteria["unresolved_changes"]:
        bullets([f"{change['source_id']} · 감지 {_time(change['detected_at']) or '시각 없음'} · 관련 기준 "
                 + (", ".join(change["criteria_ids"] or []) or "없음") for change in criteria["unresolved_changes"]])
    else:
        para("없음")

    # 6. 한계
    section("5. 검수 한계 및 유의사항")
    bullets(FIXED_LIMITS + review["notices"])

    # 7. 상세 정보
    section("6. 상세 정보")
    bullets([
        f"검수 모델: {review['model'] or '기록 없음'} · 서비스 프롬프트: {review['prompt_version']}",
        f"기준 묶음: {criteria['bundle_id']} (형식 {criteria['schema_version']}) · 버전 {criteria['bundle_version']}",
        f"기준 내용 해시: {criteria['content_hash']}",
        f"확인 방식 코드: {criteria['check_mode']} · 전체 확인 결과 코드: {criteria['check_overall'] or '없음'}",
        f"원문 글자 수: {review['char_count']}자(Unicode 코드 포인트, 공백·줄바꿈 포함) · 위치 단위: {review['position_unit']}",
    ], muted)

    generated = _time(payload["generated_at"]) or ""
    canvas_cls = theme.numbered_canvas(KICKER, generated[:10].replace("-", "."), 18 * mm, FOOTER)  # 머리·꼬리 전용 글꼴 이름

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=theme.CONTENT_TOP,
                            bottomMargin=theme.CONTENT_BOTTOM, title=TITLE, subject=SUBTITLE, author="", creator="fionex green_claim")
    doc.build(story, canvasmaker=canvas_cls)
    return buffer.getvalue()


def _original_paragraphs(writer, text, items, st):
    """원문을 항목 경계마다 나눠 조각을 한 번씩만 출력합니다(누락·중복 없음). 줄마다 문단 하나."""
    from reportlab.platypus import Paragraph

    cuts = sorted({0, len(text)} | {item["start"] for item in items} | {item["end"] for item in items})
    starts = {}
    for item in items:
        starts.setdefault(item["start"], []).append(item)
    lines = [[]]
    for start, end in zip(cuts, cuts[1:]):
        for item in starts.get(start, []):
            tone, _ = TONES[item["action"]]
            lines[-1].append(f'<font size="7.5" color="#FFFFFF" backColor="{tone}">'
                             + writer.rich("▶" + item["id"], bold=True) + "</font>")
        covering = [item for item in items if item["start"] <= start < item["end"]]
        for index, part in enumerate(text[start:end].split("\n")):
            if index:
                lines.append([])
            if not part:
                continue
            prev = None if index else (text[start - 1] if start > 0 else None)
            markup = writer.rich(part, prev=prev)
            if covering:
                action = min((item["action"] for item in covering), key=ACTION_ORDER.index)
                markup = f'<font backColor="{TONES[action][1]}">' + (f"<u>{markup}</u>" if len(covering) > 1 else markup) + "</font>"
            lines[-1].append(markup)
    return [Paragraph("".join(line) or " ", st) for line in lines]


def run(in_conn, out_conn, _options):
    """프로세스 진입점. in_conn으로 보고서 입력 JSON bytes를 받고 out_conn으로 결과 dict를 보냅니다."""
    try:
        payload = json.loads(in_conn.recv_bytes().decode("utf-8"))
        result = {"status": "ok", "pdf": build_pdf(payload)}
    except (ImportError, FileNotFoundError):
        result = {"status": "error", "code": "REPORT_DEPENDENCY_MISSING"}
    except Exception:
        result = {"status": "error", "code": "REPORT_FAILED"}
    try:
        out_conn.send(result)
    except OSError:
        pass  # 시간 초과로 부모가 연결을 닫은 경우. 부모가 이 프로세스를 종료합니다.
    finally:
        in_conn.close()
        out_conn.close()
