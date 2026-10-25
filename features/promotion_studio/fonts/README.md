# PDF 글꼴

홍보 스튜디오 PDF(pdf_builder.py)에 사용하는 글꼴입니다. 한국어와 포르투갈어 악센트 문자(ã, ç, é 등)를 모두 포함합니다.

| 파일 | 내용 |
|---|---|
| NotoSansKR-Regular.ttf | Noto Sans KR 가변 글꼴의 wght 400 고정 인스턴스 |
| NotoSansKR-Bold.ttf | 같은 글꼴의 wght 700 고정 인스턴스 |
| OFL.txt | 사용권 전문(SIL Open Font License 1.1) |

- 원본: Google Fonts 저장소 `ofl/notosanskr/NotoSansKR[wght].ttf` (https://github.com/google/fonts/tree/main/ofl/notosanskr), 2026-10-25 조회.
  원본 SHA-256 `194018e6b2b293a7964f037b25c0249ce1418bc9ab3c971060a03aa57861e252`
- 변환: fontTools 4.67.0 `varLib.instancer.instantiateVariableFont(font, {"wght": 400 또는 700}, updateFontNames=True)`로
  굵기만 고정했습니다. 글자 모양은 바꾸지 않았고, 글꼴 내부 이름은 굵기에 맞게(Regular/Bold) 갱신됐습니다.
  가변 글꼴을 요청마다 변환하면 PDF 1개에 약 15초가 걸려(2026-10-25 실측) 미리 변환한 파일을 둡니다.
- 사용권: OFL 1.1. 문서에 글꼴을 포함(임베딩)하는 것과 수정본 재배포가 허용되며, 글꼴 파일만 따로 판매할 수 없습니다. 재배포 시 OFL.txt를 함께 둡니다.
- 검토 결과: 나눔고딕(OFL)은 포르투갈어 악센트 문자가 없어 사용하지 않았습니다(2026-10-25 cmap 확인).
