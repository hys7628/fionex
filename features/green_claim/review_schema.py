"""그린워싱 문구 검수 결과 스키마(공통 generate_structured의 schema 인자).

pydantic이 필요하므로 검수 요청 때만 review_service가 불러옵니다. 모든 필드는 필수이며 값이 없으면 null입니다
(공통 연결의 strict JSON Schema 조건). 위치·개수·기준 링크는 모델이 아니라 서버가 정합니다.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Alternative(BaseModel):
    original_text: Optional[str] = Field(description="대상 구절과 같은 언어의 대체 문장 예시. 만들 수 없으면 null")
    pt_br_text: Optional[str] = Field(description="브라질 포르투갈어 대체 문장 예시. 만들 수 없으면 null")
    ko_interpretation: str = Field(description="대체 문장의 한국어 해석")


class ReviewItem(BaseModel):
    quote: str = Field(description="검토 대상 구절. 입력 문구에 있는 글자를 그대로 옮김")
    occurrence: int = Field(description="같은 구절이 입력에 여러 번 있으면 몇 번째인지(1부터). 한 번뿐이면 1")
    quote_language: Literal["ko", "en", "pt-BR", "mixed", "unknown"] = Field(description="구절 언어. 확실하지 않으면 unknown")
    interpretation_ko: str = Field(description="구절의 한국어 해석")
    action: Literal["revise_recommended", "needs_review", "judgment_withheld"] = Field(
        description="수정 권고 / 검토 필요 / 판단 보류")
    reason_ko: str = Field(description="한국어 이유(짧은 근거 설명)")
    direction_ko: str = Field(description="한국어 수정 방향")
    criteria_ids: list[str] = Field(description="관련 기준 ID(제공된 목록에 있는 것만). 관련 기준이 없으면 빈 목록")
    alternative: Optional[Alternative] = Field(description="대체 문장 예시. 근거 자료가 있어야 쓸 수 있으면 null")
    alternative_unavailable_reason_ko: Optional[str] = Field(description="alternative가 null인 이유. 있으면 null")


class ReviewResult(BaseModel):
    items: list[ReviewItem] = Field(description="검토 항목. 없으면 빈 목록")
    summary_ko: str = Field(description="전체 요약(한국어). 개수는 쓰지 않아도 됨")
    limitations: list[str] = Field(description="이번 검토의 한계. 없으면 빈 목록")
