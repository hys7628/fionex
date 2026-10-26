# 홈 PDF 폰트

홈 일일 브리핑 PDF(features/home/report.py)에 쓰는 폰트입니다. 화면 CSS에는 쓰지 않습니다.

| 파일 | 내용 |
|---|---|
| NotoSansKR-Regular.ttf | Noto Sans KR 굵기 400 정적 폰트 |
| NotoSansKR-Bold.ttf | Noto Sans KR 굵기 700 정적 폰트 |
| OFL.txt | SIL Open Font License 1.1 전문(원본 저장소 파일) |

- 출처: Google Fonts 공식 저장소 `ofl/notosanskr/NotoSansKR[wght].ttf` (Version 2.004), https://github.com/google/fonts/tree/main/ofl/notosanskr , 2026-10-25 내려받음.
  원본 sha256 `194018e6b2b293a7964f037b25c0249ce1418bc9ab3c971060a03aa57861e252`.
- 변환: 가변 폰트에서 fontTools 4.67.0 `varLib.instancer.instantiateVariableFont(font, {"wght": 400|700}, updateFontNames=True)`로 정적 인스턴스를 만들었습니다(글리프 추가·삭제 없음).
  - Regular sha256 `397503f7be57a432e0f0a5f25906de63cee5d04662bd6f135770642bac45ff63`
  - Bold sha256 `6db474d026dc4bc4e9860d17a142113c24cf06e82c294a3f8b3f3ac980779989`
- 사용권: SIL Open Font License 1.1. 예약 폰트 이름은 'Source'뿐이며(OFL.txt 첫 줄), 이 파일들은 'Noto Sans KR' 이름을 씁니다. 재배포 시 OFL.txt를 함께 둡니다.
- 선택 이유: 한글과 포르투갈어 악센트(ç ã é ô õ 등)·▲▼·– 를 모두 포함(2026-10-25 확인). Nanum Gothic은 포르투갈어 악센트가 없고, 맑은 고딕은 재배포 불가.
- 다른 탭에서도 쓰게 되면 팀 합의 후 공통 위치로 옮깁니다.
