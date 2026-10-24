/*
 * 탭별 작업 상태 저장소 + 새로고침·페이지 종료 경고.
 * - 상태는 현재 페이지 메모리에만 둡니다. localStorage/sessionStorage/IndexedDB/서버에 쓰지 않습니다.
 * - 보호할 상태가 있을 때만 beforeunload를 연결하고, 없으면 해제합니다.
 * - 경고 표시 여부와 문구는 브라우저가 결정합니다(사용자 조작 전이거나 브라우저 정책에 따라 생략될 수 있음).
 * 기능 코드는 이 파일을 직접 쓰지 말고 AppShell.work(app_shell.js)를 사용합니다.
 */
(function () {
  "use strict";

  const states = {};
  const listeners = [];
  let guardAttached = false;

  function emptyState() {
    // inputs: 패널 입력 자동 감지, draft: 기능이 직접 알린 작성 중 상태,
    // result: 다운로드하지 않은 결과, downloadRequested: 다운로드 요청(저장 성공 확인 아님)
    return { inputs: false, draft: false, result: false, downloadRequested: false };
  }

  function stateOf(id) {
    if (!states[id]) states[id] = emptyState();
    return states[id];
  }

  function snapshot(id) {
    const s = stateOf(id);
    return {
      hasDraft: s.inputs || s.draft,
      hasUndownloadedResult: s.result,
      downloadRequested: s.downloadRequested,
    };
  }

  function onBeforeUnload(event) {
    event.preventDefault();
    event.returnValue = ""; // 구형 브라우저 호환. 사용자 지정 문구는 표시되지 않습니다.
  }

  function isGuarded() {
    return Object.keys(states).some(function (id) {
      const s = states[id];
      return s.inputs || s.draft || s.result;
    });
  }

  function syncGuard() {
    const needed = isGuarded();
    if (needed && !guardAttached) {
      window.addEventListener("beforeunload", onBeforeUnload);
      guardAttached = true;
    } else if (!needed && guardAttached) {
      window.removeEventListener("beforeunload", onBeforeUnload);
      guardAttached = false;
    }
  }

  function update(id, patch) {
    Object.assign(stateOf(id), patch);
    syncGuard();
    const snap = snapshot(id);
    listeners.forEach(function (fn) { fn(id, snap); });
  }

  window.LeaveGuard = {
    update: update,
    get: snapshot,
    isGuarded: isGuarded,
    subscribe: function (fn) { listeners.push(fn); },
  };
})();
