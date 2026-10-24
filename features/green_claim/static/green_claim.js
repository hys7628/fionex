// 그린 클레임 체크 탭 스크립트. 이 탭 패널 내부만 다룹니다. 공통 API 사용법: docs/design_system.md
(function () {
  "use strict";

  const FEATURE_ID = "green_claim";
  const panel = document.querySelector('[data-feature-panel="' + FEATURE_ID + '"]');
  if (!panel) return;

  // 기능 개발 단계에서 구현.
  // - 입력 변경은 공통 shell이 자동 감지합니다.
  // - 결과 생성 후 AppShell.work.setResult(FEATURE_ID, true)
  // - PDF Blob 다운로드는 AppShell.work.downloadBlob(FEATURE_ID, blob, "파일명.pdf")
  // - 탭을 다시 열 때 생성 API를 재호출하지 않습니다(결과 DOM이 그대로 유지됨).
})();
