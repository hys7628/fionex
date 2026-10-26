"""일반 PDF 텍스트 추출 작업. service.py가 별도 프로세스(multiprocessing spawn)에서 run()을 실행합니다.

- 시간 제한·프로세스 종료는 service.py가 담당합니다. 이 모듈은 Flask를 import하지 않습니다.
- PDF 내용을 명령·스크립트로 실행하지 않고 pypdf로 텍스트만 읽습니다.
- 업로드 내용·추출 문구를 디스크·로그에 남기지 않습니다(pypdf 경고 출력도 끔).
"""
import io
import logging
import warnings


def _normalize(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def extract(data, max_pages):
    """PDF bytes → 페이지별 텍스트.

    성공: {"status": "ok", "page_count": int, "pages": [str 또는 None]}  (None = 해당 페이지 추출 실패)
    실패: {"status": "error", "code": str}
    """
    from pypdf import PdfReader

    # pypdf 경고에 문서 일부가 섞여 서버 콘솔에 남지 않도록 출력하지 않습니다.
    logging.getLogger("pypdf").setLevel(logging.CRITICAL + 1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return _extract(PdfReader, data, max_pages)


def _extract(PdfReader, data, max_pages):
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            return {"status": "error", "code": "PDF_ENCRYPTED"}
        page_count = len(reader.pages)
    except Exception:
        # 손상된 PDF는 pypdf 예외 외에도 다양한 예외를 낼 수 있어 모두 손상으로 처리합니다.
        return {"status": "error", "code": "PDF_DAMAGED"}

    if page_count == 0:
        return {"status": "error", "code": "PDF_NO_PAGES"}
    if page_count > max_pages:
        return {"status": "error", "code": "PDF_TOO_MANY_PAGES"}

    pages = []
    for index in range(page_count):
        try:
            pages.append(_normalize(reader.pages[index].extract_text() or ""))
        except Exception:
            pages.append(None)
    return {"status": "ok", "page_count": page_count, "pages": pages}


def run(in_conn, out_conn, max_pages):
    """프로세스 진입점. in_conn으로 PDF bytes를 받고 out_conn으로 결과 dict를 보냅니다."""
    try:
        result = extract(in_conn.recv_bytes(), max_pages)
    except Exception:
        result = {"status": "error", "code": "EXTRACT_FAILED"}
    try:
        out_conn.send(result)
    except OSError:
        pass  # 시간 초과로 부모가 연결을 닫은 경우. 부모가 이 프로세스를 종료합니다.
    finally:
        in_conn.close()
        out_conn.close()
