# 결과물 경로

현재 기록 없음. 아래 항목을 실제 작업 후 추가하세요.

날짜 / 종류 / 경로 / 생성 도구 / 관련 실험 / 사용권·검토 상태

미실행·미확인은 그대로 표시하고 결과를 추정해 작성하지 않습니다.

---

## 2026-10-25 제품소개서 카탈로그 디자인 시안용 콘셉트 이미지 (사용자 제공 디자인 자산)
구분: 개발용 디자인 자산(사용자가 저장소에 직접 추가). 서비스 사용자의 업로드·생성 결과물이 아님.
공통 성격: ChatGPT에서 생성했다고 사용자가 전달한 고정 디자인 시안용 이미지. **실제 리젠 T2T 사진이나 검증된 제품 조직을 보여주는 자료가 아님.**
이미지 생성 모델명·생성 설정·프롬프트·사용권 조건: 전달받지 못함(미확인). Claude는 이미지를 생성·수정·재생성하지 않았고 원본을 덮어쓰지 않음.

| 날짜 | 종류 | 경로 | 형식·크기 | 생성 도구 | 사용 위치 | 관련 실험 | 사용권·검토 상태 |
|---|---|---|---|---|---|---|---|
| 2026-10-25 | 표지 콘셉트 이미지(아이보리 원단 곡선 + 딥그린 포인트, 세로) | features/product_brochure/static/images/catalog_cover_concept.png | PNG 1024×1536, 8-bit RGB, 2,938,036 bytes | ChatGPT(사용자 전달, 모델·설정 미확인) | 카탈로그 시안 1쪽 표지 전면, 4쪽 마무리 영역 부분 크롭 | 없음(서비스 프롬프트 실험 아님) | 사용권 조건 미확인. 시연용 시안에만 사용, 문서에 "Imagem conceitual gerada por IA — não representa o produto real." 표시. 사용자 시각 검토 전 |
| 2026-10-25 | 소재 콘셉트 이미지(실타래 + 원단 조직, 가로) | features/product_brochure/static/images/catalog_material_concept.png | PNG 1448×1086, 8-bit RGB, 2,987,376 bytes | ChatGPT(사용자 전달, 모델·설정 미확인) | 카탈로그 시안 2쪽 소개(크롭 없음), 3쪽 상세(원단 조직 부분 크롭, 같은 이미지의 확대로 표시) | 없음 | 위와 같음 |

- 형식·크기는 Claude가 `file` 명령과 파일 목록으로 직접 확인. 정적 URL 응답(200, image/png)은 테스트로 확인.
- 실제 제품 이미지로 바꿀 때는 출처·사용권을 확인한 뒤 같은 파일 역할(표지 세로 2:3, 소재 가로 4:3)로 교체하고 이 표에 새 행을 추가.

## 2026-10-26 카탈로그 PDF 글꼴(임시 위치)·개발 검증 PDF
| 날짜 | 자산 | 위치 | 형식·크기 | 출처 | 용도 | 사용권 |
|---|---|---|---|---|---|---|
| 2026-10-26 | Noto Sans KR 굵기 400 정적 글꼴 | features/product_brochure/fonts/NotoSansKR-Regular.ttf | TTF 6,224,868 bytes, sha256 a9d9ecdf…c435a5 | 팀 공용 글꼴(origin/feature/market_analysis의 features/market_analysis/fonts, 커밋 af0178d)과 git blob 동일(bf8ab2e0). 원본: Google Fonts ofl/notosanskr 가변 글꼴을 팀원이 fontTools로 정적 변환(해당 README 기록) | 카탈로그 PDF 본문 | SIL OFL 1.1, OFL.txt 동봉. 변환본은 OFL상 수정본 |
| 2026-10-26 | Noto Sans KR 굵기 700 정적 글꼴 | features/product_brochure/fonts/NotoSansKR-Bold.ttf | TTF 6,222,712 bytes, sha256 851b1f41…ccfb5ad | 위와 같음(blob c19a676e) | 제목·값 굵은 글자 | 위와 같음 |
| 2026-10-26 | OFL 라이선스 원문 | features/product_brochure/fonts/OFL.txt | 텍스트 | 위와 같음(blob 1c9f4328) | 글꼴과 함께 배포 | — |

- 임시 위치: 공통 글꼴 경로는 모든 기능 병합 후 별도 브랜치에서 정리(팀 합의). 코드 경로는 pdf_catalog.FONT_DIR 한곳만 바꾸면 됨. 다른 기능 폴더를 실행 시 참조하지 않음.
- 저장소에 같은 글꼴이 기능별로 중복됨(약 12 MB씩). 공통화 시 정리 대상.
- 글리프: 포르투갈어 악센트·— · & < > 포함을 Claude가 cmap으로 확인(이모지 등 없는 문자는 실패 처리).
- 이미지 2개는 기존 행(2026-10-25)과 같은 파일을 PDF에 JPEG(품질 88)로 다시 압축해 넣음. 원본 파일은 바꾸지 않음.
- 개발 검증 PDF(가상 데이터, 서비스 사용자 결과 아님)는 저장소 밖 세션 임시 폴더에 생성, Git 추적 대상 아님:
  C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Desktop-fionex\36d7c2bf-67d2-469c-9a14-643e83056de0\scratchpad\pdf_samples_v3\
  (pdf_samples·pdf_samples_v2는 이전 코드로 만든 파일. 삭제하지 않고 보존)
