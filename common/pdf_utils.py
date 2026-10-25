"""PDF 입력 공통 검사. 메모리 bytes만 다루며 디스크에 쓰지 않습니다.

inspect_pdf(data) 검사 순서:
  bytes 타입 → 빈 파일 → 크기 상한 → PDF 서명 → pypdf 구조 파싱 → 암호화(해제 시도 없이 거부) → 페이지 수(0쪽·상한 초과)

- 서명만으로 유효한 PDF로 보지 않고 실제 구조를 파싱합니다.
- 본문 텍스트는 추출하지 않습니다. 텍스트 유무로 스캔 문서를 판정하지 않습니다.
- 일반적인 구조 검사이며 모든 악성·과도한 자원 사용 PDF를 차단하지는 못합니다.
- 오류는 common.errors의 고정 메시지로만 알립니다. 파서 예외 원문은 옮기지 않습니다.
"""
import io
import logging
from dataclasses import dataclass

from pypdf import PdfReader

from common import config
from common.errors import (
    AIInputError,
    PdfCorruptError,
    PdfEmptyError,
    PdfEncryptedError,
    PdfNoPagesError,
    PdfNotPdfError,
    PdfTooLargeError,
    PdfTooManyPagesError,
)

# pypdf는 손상 파일 복구 시 경고 로그에 파일 앞부분 바이트 등을 넣을 수 있습니다(예: "invalid pdf header: b'...'").
# 문서 내용이 로그에 남지 않도록 pypdf 로거의 출력을 전파하지 않습니다. pypdf를 쓰는 다른 코드의 로그에도 적용됩니다.
_pypdf_logger = logging.getLogger("pypdf")
_pypdf_logger.addHandler(logging.NullHandler())
_pypdf_logger.propagate = False

# PDF 사양상 헤더는 파일 앞부분에 있어야 합니다. 앞 1024바이트 안에서 "%PDF-"를 찾습니다.
_SIGNATURE = b"%PDF-"
_SIGNATURE_WINDOW = 1024


@dataclass(frozen=True)
class PdfInfo:
    size_bytes: int
    page_count: int


class _EncryptedPdf(Exception):
    pass


class _NoDecryptReader(PdfReader):
    """암호화된 PDF를 만나면 해제를 시도하지 않고 멈추는 리더.

    pypdf 6.21.2의 PdfReader는 암호화 PDF에 빈 비밀번호로 자동 해제를 시도합니다(_handle_encryption).
    requirements.txt에서 pypdf 버전을 고정하고, tests/test_common에서 해제가 시도되지 않음을 확인합니다.
    """

    def _handle_encryption(self, password):
        raise _EncryptedPdf()


def inspect_pdf(data, *, max_bytes=None, max_pages=None):
    """PDF bytes를 검사하고 PdfInfo(size_bytes, page_count)를 돌려줍니다.

    max_bytes·max_pages: 생략하면 config.PDF_MAX_BYTES(10 MiB)·config.PDF_MAX_PAGES(20).
    오류: PdfValidationError 하위 클래스(PDF_EMPTY, PDF_TOO_LARGE, PDF_NOT_PDF, PDF_CORRUPT,
          PDF_ENCRYPTED, PDF_NO_PAGES, PDF_TOO_MANY_PAGES). bytes가 아니면 AI_INVALID_INPUT.
    """
    max_bytes = config.PDF_MAX_BYTES if max_bytes is None else max_bytes
    max_pages = config.PDF_MAX_PAGES if max_pages is None else max_pages
    for limit in (max_bytes, max_pages):
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise AIInputError(message="PDF 검사 상한은 1 이상의 정수여야 합니다.")
    if not isinstance(data, bytes):
        raise AIInputError(message="PDF 데이터는 bytes여야 합니다.")
    if not data:
        raise PdfEmptyError()
    if len(data) > max_bytes:
        raise PdfTooLargeError()
    if _SIGNATURE not in data[:_SIGNATURE_WINDOW]:
        raise PdfNotPdfError()

    try:
        reader = _NoDecryptReader(io.BytesIO(data), strict=False)
        page_count = len(reader.pages)
    except _EncryptedPdf:
        raise PdfEncryptedError() from None
    except Exception:
        # 파서 예외 메시지에 문서 일부가 들어갈 수 있어 원 예외를 체인하지 않습니다.
        raise PdfCorruptError() from None

    if page_count == 0:
        raise PdfNoPagesError()
    if page_count > max_pages:
        raise PdfTooManyPagesError()
    return PdfInfo(size_bytes=len(data), page_count=page_count)
