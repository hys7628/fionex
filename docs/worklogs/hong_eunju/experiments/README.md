# 실험 증거
공개·가상 입력으로 실제 실행한 실험 JSON을 저장할 자리. 자동 수집 기능 미구현.

| 파일 | 실험 | 입력 | 실행 |
|---|---|---|---|
| news_summary_2026_10_25_163947.json | SPE-HOME-NEWS-001 뉴스 요약 v1/v2 비교 | 가상 제목 10건 + Google News 공개 제목 20건(본문 없음) | tests/test_home/run_news_summary_experiment.py --live --real 20 |
