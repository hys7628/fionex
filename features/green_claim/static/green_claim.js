// 그린 클레임 체크 탭 스크립트. 이 탭 패널 내부만 다룹니다. 공통 API 사용법: docs/design_system.md
// 현재 단계: 문구 직접 입력의 글자 수·입력 상태 안내. AI 검수·파일 추출·PDF는 아직 연결하지 않습니다.
(function () {
  "use strict";

  const FEATURE_ID = "green_claim";
  const MAX_CHARS = 20000;
  const MESSAGES = {
    empty: "검수할 문구를 입력해 주세요. 공백만으로는 검수할 수 없습니다.",
    over: "최대 20,000자를 넘었습니다. 초과한 만큼 줄여 주세요. 입력한 문구는 자동으로 자르지 않습니다.",
  };

  const panel = document.querySelector('[data-feature-panel="' + FEATURE_ID + '"]');
  if (!panel) return;

  const textarea = panel.querySelector("#green_claim-claims");
  const countEl = panel.querySelector("#green_claim-claims-count");
  const errorEl = panel.querySelector("#green_claim-claims-error");
  const liveEl = panel.querySelector("#green_claim-claims-live");
  if (!textarea || !countEl || !errorEl || !liveEl) return;

  const numberFormat = new Intl.NumberFormat("ko-KR");
  let composing = false;   // 한글 등 조합 입력 중에는 오류 표시를 바꾸지 않음
  let touched = false;     // 사용자가 입력한 적이 있는지(첫 화면에서 바로 오류를 띄우지 않음)
  let hadContent = false;  // 직전 확인 시점에 공백 아닌 글자가 있었는지
  let shownError = null;   // 현재 표시 중인 오류: "empty" | "over" | null

  // 글자 수: CRLF·CR을 LF로 바꾼 뒤 Unicode 코드 포인트 수(공백·줄바꿈 포함).
  // 화면에 보이는 글자 묶음(예: 결합 이모지)과 항상 같지는 않습니다.
  function normalize(text) {
    return text.replace(/\r\n?/g, "\n");
  }

  function inspect(text) {
    const normalized = normalize(text);
    const count = Array.from(normalized).length;
    let problem = null;
    if (normalized.trim() === "") problem = "empty";
    else if (count > MAX_CHARS) problem = "over";
    return { count: count, problem: problem };
  }

  function renderCount(count) {
    const over = count - MAX_CHARS;
    let text = numberFormat.format(count) + " / " + numberFormat.format(MAX_CHARS) + "자 (공백·줄바꿈 포함)";
    if (over > 0) text += " · " + numberFormat.format(over) + "자 초과";
    countEl.textContent = text;
    countEl.dataset.state = over > 0 ? "over" : "";
  }

  // 오류가 바뀔 때만 화면·알림 영역을 갱신합니다(타이핑마다 반복해 읽지 않도록).
  function setError(problem) {
    if (problem === shownError) return;
    shownError = problem;
    if (problem) {
      textarea.setAttribute("aria-invalid", "true");
      errorEl.textContent = MESSAGES[problem];
      errorEl.hidden = false;
      liveEl.textContent = MESSAGES[problem];
    } else {
      textarea.removeAttribute("aria-invalid");
      errorEl.textContent = "";
      errorEl.hidden = true;
      liveEl.textContent = "";
    }
  }

  // trigger: "input"(입력 중) | "blur"(입력칸을 떠남) | "init"(첫 확인)
  function refresh(trigger) {
    const result = inspect(textarea.value);
    renderCount(result.count);
    if (composing) return;

    let next = result.problem;
    if (next === "empty") {
      // 처음부터 공백을 입력하는 중에는 오류를 띄우지 않고, 내용을 모두 지웠거나 입력칸을 떠날 때 안내합니다.
      const show = touched && (trigger === "blur" || hadContent || shownError === "empty");
      if (!show) next = null;
    }
    setError(next);
    hadContent = result.problem !== "empty";
  }

  textarea.addEventListener("compositionstart", function () { composing = true; });
  textarea.addEventListener("compositionend", function () {
    composing = false;
    refresh("input");
  });
  textarea.addEventListener("input", function (event) {
    touched = true;
    if (event.isComposing) composing = true;
    refresh("input");
  });
  textarea.addEventListener("blur", function () {
    composing = false;
    refresh("blur");
  });

  // 브라우저가 이전 값을 채워 넣은 경우에도 글자 수를 맞춥니다. 오류는 사용자가 입력한 뒤부터 표시합니다.
  refresh("init");

  // 결과를 만들지 않으므로 AppShell.work.setResult는 호출하지 않습니다.
  // 입력 작성 상태와 이탈 경고는 공통 shell의 자동 감지가 처리합니다.
})();
