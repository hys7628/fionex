# PDF 글꼴 (시장 분석 PDF 출력용)

| 파일 | 내용 |
|---|---|
| NotoSansKR-Regular.ttf | Noto Sans KR 굵기 400 정적 인스턴스 |
| NotoSansKR-Bold.ttf | Noto Sans KR 굵기 700 정적 인스턴스 |
| OFL.txt | SIL Open Font License 1.1 원문 (글꼴과 함께 배포해야 함) |

- 원본: Google Fonts 저장소 `ofl/notosanskr/NotoSansKR[wght].ttf` (가변 글꼴), 2026-10-25 다운로드
  https://github.com/google/fonts/tree/main/ofl/notosanskr
- ReportLab이 가변 글꼴을 직접 다루지 못해 fontTools 4.60.1 `varLib.instancer`로 wght=400·700 정적 글꼴을 만들었다.
  fontTools는 변환 작업에만 썼고 프로젝트 의존성이 아니다.
- 확인: 한글, 포르투갈어 악센트(ã ç é ê ô õ á í ó ú à), 따옴표·대시·가운뎃점 글리프 포함.
- 라이선스: SIL OFL 1.1. 상업적 사용·문서 포함 가능. 글꼴 파일을 단독 판매하지 않으며 OFL.txt를 함께 둔다.
  변환본은 OFL상 수정본(Modified Version)이며 예약 글꼴 이름 조항은 OFL.txt를 따른다.
