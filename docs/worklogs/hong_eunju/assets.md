# 결과물 경로

아래 항목을 실제 작업 후 추가하세요.

날짜 / 종류 / 경로 / 생성 도구 / 관련 실험 / 사용권·검토 상태

미실행·미확인은 그대로 표시하고 결과를 추정해 작성하지 않습니다.

| 날짜 | 종류 | 경로 | 생성 도구 | 관련 작업 | 사용권·검토 상태 |
|---|---|---|---|---|---|
| 2026-10-25 | 폰트(PDF용) | features/home/fonts/NotoSansKR-Regular.ttf, NotoSansKR-Bold.ttf, OFL.txt, README.md | Google Fonts 공식 NotoSansKR[wght].ttf(v2.004)에서 fontTools 4.67.0 instancer로 wght 400·700 정적 인스턴스 추출 | DEV-HOME-008 일일 브리핑 PDF | SIL OFL 1.1(예약 이름 'Source'만, 'Noto Sans KR' 이름 사용). OFL.txt 동봉. sha256은 fonts/README.md |
| 2026-10-25 | 검증용 PDF·페이지 이미지 | 세션 임시 폴더(scratchpad)에만 생성, 저장소·worklog에 보관하지 않음 | report.py(가상 fixture 데이터 및 키 없는 테스트 서버 실제 공개 데이터) | DEV-HOME-008 검증 | 사용자 PDF 아님. 보관하지 않음 |
| 2026-10-26 | 로고(PNG) | static/assets/fionex_logo.png | 사용자 제공 원본 FIONEX_LOGO.png를 그대로 복사(변환·리사이즈 없음, 2172×724 RGBA, 870,173 bytes) | DEV-COMMON-006 공통 사이드바·상단바 로고 | 사용자(홍은주)가 공식 로고로 제공. 제작 출처·사용권 문서는 확인하지 못함(담당자 확인 필요) |
| 2026-10-26 | 웹 폰트(TTF) | static/fonts/brand/Brand New Hyosung Light.ttf, Medium.ttf, Bold.ttf | 사용자(홍은주)가 직접 넣은 파일 그대로 사용(변환·서브셋 없음, 각 약 1.3MB) | DEV-COMMON-007 웹 UI 브랜드 폰트 | Copyright (c) 2023 HYOSUNG CORPORATION. All rights reserved. 라이선스 문구 없음, fsType 4(미리보기·인쇄 임베딩). 웹 제공(파일 내려받기 가능) 허가 미확인 — 효성 브랜드 담당 확인 필요 |
| 2026-10-26 | 공통 글꼴(woff2·TTF) | static/fonts/pretendard/ (Pretendard-Regular·Medium·SemiBold·Bold.woff2, Pretendard-Regular·Bold.ttf, LICENSE.txt, README.md) | 사용자가 넣은 Pretendard 1.3.9 배포본(static/fonts/Pretendard-1.3.9/)에서 필요한 파일만 그대로 복사(변환 없음, 해시는 README.md) | DEV-COMMON-008 웹·모든 탭 PDF 글꼴 통일 | SIL OFL 1.1(예약 이름 Pretendard), LICENSE.txt 동봉, fsType 0. 웹 제공·PDF 임베딩 허용 |
| 2026-10-26 | 삭제(글꼴) | features/home/fonts, features/market_analysis/fonts(Noto Sans KR+OFL+README), features/green_claim/fonts(나눔고딕+OFL+README) | - | DEV-COMMON-008 | Pretendard 통일로 사용처 없음. Git 이력에 남음 |
| 2026-10-26 | 미사용(사용자 파일) | static/fonts/brand/ (Brand New Hyosung, DEV-COMMON-007), static/fonts/Pretendard-1.3.9/ (배포본 67MB) | 사용자 제공, 변경·삭제 안 함 | DEV-COMMON-008 | 코드 참조 없음. 커밋 제외 또는 삭제는 담당자 결정(Brand New Hyosung은 웹 사용권 미확인) |
