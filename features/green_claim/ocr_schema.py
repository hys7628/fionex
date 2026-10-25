"""스캔 PDF AI 글자 판독 결과 스키마(공통 generate_structured_from_pdf의 schema 인자).

pydantic이 필요하므로 판독 요청 때만 ocr_service가 불러옵니다(앱 시작·일반 추출에는 필요 없음).
모든 필드는 필수입니다(공통 연결의 strict JSON Schema 조건).
"""
from pydantic import BaseModel, Field


class OcrPage(BaseModel):
    page: int = Field(description="PDF의 물리적 페이지 번호(1부터). 인쇄된 쪽 번호가 아님")
    text: str = Field(description="이 페이지에서 보이는 글자를 원문 그대로 옮긴 텍스트. 읽을 수 없는 곳은 [판독 불가]")
    uncertain: list[str] = Field(description="판독 불가·불확실한 구간의 위치와 이유. 없으면 빈 목록")


class OcrResult(BaseModel):
    pages: list[OcrPage] = Field(description="1부터 마지막 페이지까지 모든 페이지를 한 번씩")
    limitations: list[str] = Field(description="문서 전체의 판독 한계. 정확도 수치를 만들지 않음. 없으면 빈 목록")
