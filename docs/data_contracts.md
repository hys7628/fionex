# 공통 연결 규칙 (초안)

탭 사이 데이터 자동 전달 없음. 각 탭 입력·결과를 별도 메모리 상태로 관리.
향후 API 접두어: /api/home, /api/market-analysis, /api/product-brochure, /api/green-claim, /api/promotion-studio.
각 엔드포인트와 필드·타입·상한·오류는 구현 전 담당 feature_spec.md에 작성.
권장 성공 응답: {"ok": true, "data": {...}}
권장 실패 응답: {"ok": false, "error": {"code": "...", "message": "..."}}
PDF 응답은 파일 바이너리와 다운로드 헤더 사용. 서버 경로나 키를 오류에 노출하지 않음.
통계는 값·단위·기간·품목코드·출처·조회시각을 함께 전달.
AI 출력에는 근거·미확인 항목을 포함하고 JSON 파싱/필수 필드 검증을 수행.
검수 결과는 제공 근거 범위의 스크리닝이며 법적 적합성 보장이 아님.
