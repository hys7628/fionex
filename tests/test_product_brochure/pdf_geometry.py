"""PDF 내용 스트림을 해석해 실제로 그려진 글자 줄의 가로 범위를 계산합니다(렌더러의 자체 측정과 독립).

그래픽 상태(q/Q·cm)와 텍스트 상태(Tc 글자 간격·Tw 단어 간격·Tz 가로 배율·Tf 글꼴/크기·TL 줄 간격)를 PDF 규칙대로 따라가며,
Tj/TJ/'/" 마다 글꼴의 /Widths로 폭을 계산합니다. Tc 등은 BT/ET로 초기화되지 않고 q/Q로만 복원된다는 PDF 규칙을 반영합니다.
ReportLab 단순 글꼴(1바이트 코드 + /Widths)만 지원합니다. 시각 검증을 대신하지 않습니다.
"""
import io

from pypdf import PdfReader
from pypdf.generic import ContentStream


def _mul(m, n):
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (a * a2 + b * c2, a * b2 + b * d2, c * a2 + d * c2, c * b2 + d * d2,
            e * a2 + f * c2 + e2, e * b2 + f * d2 + f2)


def _point(m, x, y):
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


IDENTITY = (1, 0, 0, 1, 0, 0)


def _raw(data):
    """문자열 피연산자의 원래 바이트(글꼴 코드)."""
    if hasattr(data, "original_bytes"):
        return bytes(data.original_bytes)
    return bytes(data) if isinstance(data, bytes) else data.encode("latin-1")


def _widths(page):
    out = {}
    for name, ref in page["/Resources"]["/Font"].items():
        font = ref.get_object()
        first = int(font["/FirstChar"])
        out[name] = {first + i: float(w) for i, w in enumerate(font["/Widths"])}
    return out


def text_runs(pdf):
    """[(쪽 번호, x 시작, x 끝, 기준선 y, 문자 수, 글꼴 크기)] 단위 pt."""
    runs = []
    for number, page in enumerate(PdfReader(io.BytesIO(pdf)).pages, start=1):
        widths = _widths(page)
        gs = {"ctm": IDENTITY, "Tc": 0.0, "Tw": 0.0, "Tz": 100.0, "font": None, "size": 0.0, "TL": 0.0}
        stack = []
        tm = tlm = IDENTITY
        ops = ContentStream(page.get_contents(), page.pdf).operations

        def show(data):
            nonlocal tm
            data = _raw(data)
            x0, y0 = _point(_mul(tm, gs["ctm"]), 0, 0)
            advance = 0.0
            for code in data:
                w = widths[gs["font"]][code] / 1000 * gs["size"] + gs["Tc"] + (gs["Tw"] if code == 32 else 0)
                advance += w * gs["Tz"] / 100
            tm = _mul((1, 0, 0, 1, advance, 0), tm)
            x1, _ = _point(_mul(tm, gs["ctm"]), 0, 0)
            runs.append((number, min(x0, x1), max(x0, x1), y0, len(data), gs["size"]))

        def next_line():
            nonlocal tm, tlm
            tlm = _mul((1, 0, 0, 1, 0, -gs["TL"]), tlm)
            tm = tlm

        for operands, op in ops:
            op = op.decode("latin-1") if isinstance(op, bytes) else op
            if op == "q":
                stack.append(dict(gs))
            elif op == "Q":
                gs = stack.pop()
            elif op == "cm":
                gs["ctm"] = _mul(tuple(float(v) for v in operands), gs["ctm"])
            elif op == "BT":
                tm = tlm = IDENTITY
            elif op == "Tf":
                gs["font"], gs["size"] = operands[0], float(operands[1])
            elif op in ("Tc", "Tw", "Tz", "TL"):
                gs[op] = float(operands[0])
            elif op == "Tm":
                tm = tlm = tuple(float(v) for v in operands)
            elif op in ("Td", "TD"):
                if op == "TD":
                    gs["TL"] = -float(operands[1])
                tlm = _mul((1, 0, 0, 1, float(operands[0]), float(operands[1])), tlm)
                tm = tlm
            elif op == "T*":
                next_line()
            elif op == "Tj":
                show(operands[0])
            elif op == "'":
                next_line()
                show(operands[0])
            elif op == '"':
                gs["Tw"], gs["Tc"] = float(operands[0]), float(operands[1])
                next_line()
                show(operands[2])
            elif op == "TJ":
                for part in operands[0]:
                    if isinstance(part, (bytes, str)):
                        show(part)
                    else:
                        tm = _mul((1, 0, 0, 1, -float(part) / 1000 * gs["size"] * gs["Tz"] / 100, 0), tm)
    return runs
