# Pretendard (fionex 공통 글꼴)

웹 화면 전체와 5개 탭의 PDF 출력에 쓰는 단일 글꼴입니다. 파일은 공식 배포본에서 골라 이름·내용을 바꾸지 않고 그대로 복사했습니다.
다른 글꼴(기능별 `fonts/` 폴더, 시스템 글꼴 설치)은 쓰지 않습니다.

| 파일 | 용도 | 굵기 | 원본 경로(Pretendard-1.3.9 배포본) | SHA-256 |
|---|---|---|---|---|
| Pretendard-Regular.woff2 | 웹 `@font-face` | 400 | web/static/woff2/ | fad853f7f47c6c8b103171e7193fa095708cdcd70850a71d93aa5379e8a61d63 |
| Pretendard-Medium.woff2 | 웹 `@font-face` | 500 | web/static/woff2/ | d03481330eeba0659ab5b87f25ceb504a35de377dd90a0d0aba2982eb2d05e2c |
| Pretendard-SemiBold.woff2 | 웹 `@font-face` | 600 | web/static/woff2/ | c863f76a7de5c1ddc1ed8b2fa794964530774592c4f31407a84e2a2ae93f17f0 |
| Pretendard-Bold.woff2 | 웹 `@font-face` | 700 | web/static/woff2/ | 4609c3356e536fafe38f4add0daeceb3d8595d3057bce13c428c33ddbd43d362 |
| Pretendard-Regular.ttf | PDF(ReportLab) 본문 | 400 | public/static/alternative/ | 6d0af5258997aec7354a6e340fc2325ba321c410ca48b3af858c8c3d6e92a324 |
| Pretendard-Bold.ttf | PDF(ReportLab) 제목·강조 | 700 | public/static/alternative/ | c16b88c670d23e83fa1170c954cbc4822d3b8dad3c3cde15d798a94b43d97985 |
| LICENSE.txt | SIL Open Font License 1.1 원문 | - | LICENSE.txt | b04538c9abec39a3db75108cf0af0fd9c77032fe8aa2cf38345b4d250e98e38e |

- 버전: Pretendard 1.3.9 (name 테이블 Version 1.309). 출처: https://github.com/orioncactus/pretendard (사용자가 배포본을 `static/fonts/Pretendard-1.3.9/`에 넣어 둠, 2026-10-26).
- 저작권: Copyright (c) 2021 Kil Hyung-jin, 예약 글꼴 이름 Pretendard. SIL OFL 1.1 — 재배포·웹 사용·문서(PDF) 임베딩 허용, 글꼴만 따로 판매 금지, LICENSE.txt를 함께 둡니다. OS/2 fsType 0(설치 가능 임베딩).
- 형식: PDF용은 TrueType 외곽선(glyf) TTF입니다. ReportLab은 CFF(.otf) 글꼴을 쓰지 못해 배포본의 `alternative/*.ttf`를 골랐습니다. 웹은 크기가 작은 woff2.
- 글리프(fontTools 확인): 한글 완성형 11,172자 전체, ASCII 전체, 포르투갈어 악센트(á ã â à ç é ê í ó õ ô ú ü, 대문자 포함), `· • – — … € ₩ ▲ ▼ ① ~ ⑥ ※` 포함. `ⓘ`는 없음(웹 도움말 버튼만 사용, 시스템 글꼴로 대체).
- 사용 위치: 웹 `static/css/common.css`의 `@font-face`, PDF는 `common/config.py`의 `PDF_FONT_FILES`(Home `features/home/report.py`, 시장 분석 `features/market_analysis/pdf_report.py`, 그린 클레임 `features/green_claim/report_worker.py`).
- 새 굵기가 필요하면 같은 배포본에서 같은 이름 규칙(`Pretendard-<굵기>.woff2|ttf`)으로 추가하고 이 표에 적습니다.
