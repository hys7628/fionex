# 그린 클레임 검수 보고서 PDF 글꼴

검수 결과 PDF(report_worker.py)에 넣는(임베딩) 글꼴입니다. 파일은 공식 배포본을 수정하지 않고 그대로 두었습니다.

| 파일 | 글꼴 | 버전 | 라이선스 | SHA-256 |
|---|---|---|---|---|
| NanumGothic-Regular.ttf | 나눔고딕 Regular (NanumGothic) | 3.020 (head fontRevision) | SIL OFL 1.1 (NanumGothic-OFL.txt) | 76f45ef4a6bcff344c837c95a7dcc26e017e38b5846d5ae0cdcb5b86be2e2d31 |
| NanumGothic-Bold.ttf | 나눔고딕 Bold (NanumGothicBold) | 3.020 | SIL OFL 1.1 | f96298f9fb18e364d2370f4c3ce948ac67a2b61af992d7234bc15c42b033c674 |
| NanumGothic-OFL.txt | 위 두 파일의 라이선스 원문 | - | - | eeacf16032901d0ed0456876ec77b8f0fda6b3fecec7d972f8543eb602e6c30f |

- 출처: Google Fonts 공식 저장소 https://github.com/google/fonts/tree/main/ofl/nanumgothic
  (내려받은 날 2026-10-26, 당시 main 커밋 e7db6ca603fd4862010383ff17ffd6cc4ffac1c0. 라이선스 파일은 같은 폴더의 OFL.txt를 이름만 바꿔 보관)
- 저작권: Copyright (c) 2010 NHN Corporation, 디자인 Sandoll Communications. 예약 글꼴 이름 Nanum 등(라이선스 파일 참고).
- OS/2 fsType 0(설치 가능 임베딩 허용). OFL은 다른 소프트웨어와 함께 재배포·문서 임베딩을 허용하며 글꼴만 따로 판매할 수 없습니다.
- 확인한 글리프: 한글 완성형 11,172자 전체, ASCII 전체. **Latin-1 악센트 문자(á·ã·ç·é 등)는 없음** → 라틴 문자는 ReportLab 패키지에 들어 있는 Bitstream Vera(Vera.ttf·VeraBd.ttf, 재배포 허용 라이선스, reportlab/fonts/bitstream-vera-license.txt)로 그립니다. Vera는 이 폴더에 복사하지 않습니다.
- 두 글꼴에 모두 없는 문자(이모지 등)는 보고서에서 `[U+XXXX]`로 대신 표시합니다(feature_spec.md "검수 결과 PDF 다운로드").

다른 컴퓨터: 저장소를 받고 `pip install -r requirements.txt`(reportlab 포함)만 하면 됩니다. Windows 시스템 글꼴 설치는 필요하지 않습니다.
