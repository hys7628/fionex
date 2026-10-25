// 그린 클레임 체크 탭 스크립트. 이 탭 패널 내부만 다룹니다. 공통 API 사용법: docs/design_system.md
// 현재 단계: 문구 직접 입력 + 일반 PDF·Word(.docx) 글자 추출·확인·수정. AI 검수·스캔 PDF OCR·결과 PDF는 아직 연결하지 않습니다.
(function () {
  "use strict";

  const FEATURE_ID = "green_claim";
  const MAX_CHARS = 20000;
  const MAX_FILE_BYTES = 10000000;
  const EXTRACT_URL = "/api/green-claim/extract";
  const CLIENT_TIMEOUT_MS = 45000; // 서버 추출 제한(30초) + 업로드·응답 여유
  const MESSAGES = {
    empty: "검수할 문구를 입력해 주세요. 공백만으로는 검수할 수 없습니다.",
    over: "최대 20,000자를 넘었습니다. 초과한 만큼 줄여 주세요. 입력한 문구는 자동으로 자르지 않습니다.",
  };

  const panel = document.querySelector('[data-feature-panel="' + FEATURE_ID + '"]');
  if (!panel) return;
  const byId = function (id) { return panel.querySelector("#" + id); };
  const numberFormat = new Intl.NumberFormat("ko-KR");

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

  // 입력칸 하나의 글자 수·입력 상태 안내. prefix: textarea id(같은 접두어의 -count/-error/-live 요소 사용)
  function createTextField(prefix) {
    const textarea = byId(prefix);
    const countEl = byId(prefix + "-count");
    const errorEl = byId(prefix + "-error");
    const liveEl = byId(prefix + "-live");
    if (!textarea || !countEl || !errorEl || !liveEl) return null;

    let composing = false;   // 한글 등 조합 입력 중에는 오류 표시를 바꾸지 않음
    let touched = false;     // 입력한 적이 있는지(첫 화면에서 바로 오류를 띄우지 않음)
    let hadContent = false;  // 직전 확인 시점에 공백 아닌 글자가 있었는지
    let shownError = null;   // 현재 표시 중인 오류: "empty" | "over" | null

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

    return {
      textarea: textarea,
      // 코드로 문구를 넣은 뒤 글자 수·입력 상태와 공통 작성 상태를 다시 계산합니다(코드 변경은 input 이벤트가 없음).
      setValue: function (text) {
        textarea.value = text;
        touched = true;
        composing = false;
        refresh("input");
        AppShell.work.recheckInputs(FEATURE_ID);
      },
    };
  }

  const textField = createTextField("green_claim-claims");
  const extractedField = createTextField("green_claim-extracted");
  if (!textField || !extractedField) return;

  /* ---------- 입력 방식 전환: 각 방식의 문구는 페이지 메모리에 그대로 둡니다 ---------- */
  const modeRadios = Array.from(panel.querySelectorAll('input[name="input_mode"]'));
  const modePanels = Array.from(panel.querySelectorAll("[data-mode-panel]"));

  function showMode(mode) {
    modePanels.forEach(function (el) { el.hidden = el.dataset.modePanel !== mode; });
  }
  modeRadios.forEach(function (radio) {
    radio.addEventListener("change", function () {
      if (!radio.checked) return;
      // 처리 중 입력 방식을 바꾸면 진행 중 추출을 취소하고 그 응답을 반영하지 않습니다(문구는 그대로).
      if (busy) cancelExtraction("입력 방식을 바꿔 진행 중인 추출을 취소했습니다");
      showMode(radio.value);
    });
  });
  const checkedMode = modeRadios.find(function (r) { return r.checked; });
  showMode(checkedMode ? checkedMode.value : "text");

  /* ---------- 일반 PDF·Word(.docx) 글자 추출 ---------- */
  const fileSection = byId("green_claim-file-section");
  const fileInput = byId("green_claim-file");
  const fileError = byId("green_claim-file-error");
  const extractButton = byId("green_claim-extract");
  const statusEl = byId("green_claim-extract-status");
  const messageEl = byId("green_claim-extract-message");
  const replaceBox = byId("green_claim-replace");
  const replaceApply = byId("green_claim-replace-apply");
  const replaceKeep = byId("green_claim-replace-keep");
  const summaryBox = byId("green_claim-extract-summary");
  const summaryTitle = byId("green_claim-extract-summary-title");
  const summaryText = byId("green_claim-extract-summary-text");
  const noticeList = byId("green_claim-extract-notices");
  const detectedBox = byId("green_claim-extract-detected-box");
  const detectedList = byId("green_claim-extract-detected");
  const pagesLabel = byId("green_claim-extract-pages-label");
  const pageList = byId("green_claim-extract-pages");
  const editedNote = byId("green_claim-extracted-edited");

  let requestSeq = 0;        // 가장 최근 추출 요청 번호. 이전 번호의 응답은 반영하지 않습니다.
  let controller = null;     // 진행 중 요청 취소용
  let busy = false;
  let pendingResult = null;  // 교체 확인을 기다리는 새 추출 결과
  let appliedText = null;    // 마지막으로 입력칸에 반영한 추출 문구(수정 여부 판단용)

  function setFileError(message) {
    fileError.textContent = message || "";
    fileError.hidden = !message;
    if (message) fileInput.setAttribute("aria-invalid", "true");
    else fileInput.removeAttribute("aria-invalid");
  }

  // type: "danger" | "warning" | "info". 문구는 textContent로만 넣습니다.
  function showMessage(type, title, text) {
    messageEl.replaceChildren();
    if (!title) return;
    const box = document.createElement("div");
    box.className = "notice notice-" + type;
    box.setAttribute("role", type === "danger" ? "alert" : "status");
    const t = document.createElement("p");
    t.className = "notice-title";
    t.textContent = title;
    box.appendChild(t);
    if (text) {
      const p = document.createElement("p");
      p.textContent = text;
      box.appendChild(p);
    }
    messageEl.appendChild(box);
  }

  function setBusy(value) {
    busy = value;
    extractButton.disabled = value;
    fileSection.setAttribute("aria-busy", value ? "true" : "false");
    statusEl.replaceChildren();
    if (value) {
      const spinner = document.createElement("span");
      spinner.className = "spinner";
      spinner.setAttribute("aria-hidden", "true");
      statusEl.append(spinner, " 글자를 추출하는 중입니다. 최대 30초 걸릴 수 있습니다.");
    }
  }

  function clearPending() {
    pendingResult = null;
    replaceBox.hidden = true;
  }

  function checkFile(file) {
    if (!file) return "PDF 또는 Word(.docx) 파일을 선택해 주세요.";
    if (file.size === 0) return "빈 파일입니다. 내용이 있는 파일을 선택해 주세요.";
    if (file.size > MAX_FILE_BYTES) return "파일이 10,000,000바이트(약 10MB)를 넘습니다. 문서를 나누거나 용량을 줄여 주세요.";
    const name = file.name.toLowerCase();
    if (!name.endsWith(".pdf") && !name.endsWith(".docx")) {
      return "현재는 일반 PDF(.pdf)와 Word(.docx) 파일만 지원합니다. .doc·.docm 등 다른 형식과 이미지 파일은 지원하지 않습니다.";
    }
    return "";
  }

  // 진행 중 요청을 취소하고 그 응답은 반영하지 않습니다(요청 번호를 올림). 기존 문구는 지우지 않습니다.
  function cancelExtraction(title) {
    requestSeq += 1;
    if (controller) controller.abort();
    setBusy(false);
    clearPending();
    showMessage("info", title, "아래 문구는 바뀌지 않았습니다. 필요하면 '글자 추출'을 다시 눌러 주세요.");
  }

  fileInput.addEventListener("change", function () {
    const canceled = busy;
    if (canceled) cancelExtraction("파일을 바꿔 이전 추출을 취소했습니다");
    clearPending();
    const file = fileInput.files[0];
    const problem = file ? checkFile(file) : "";
    setFileError(problem);
    if (canceled) {
      // 취소 안내를 유지합니다.
    } else if (file && !problem && appliedText !== null) {
      showMessage("info", "새 파일을 선택했습니다", "글자 추출을 실행해 확인하기 전까지 아래 문구는 이전 파일에서 추출·수정한 내용입니다.");
    } else {
      showMessage(null);
    }
  });

  function addItem(list, text) {
    const li = document.createElement("li");
    li.textContent = text;
    list.appendChild(li);
  }

  function charRange(start, end) {
    return numberFormat.format(start + 1) + "~" + numberFormat.format(end) + "번째 글자";
  }

  // 요약은 텍스트로만 만듭니다. PDF는 페이지 기준, Word는 본문 블록(문단·표·행) 기준입니다.
  function renderSummary(data) {
    summaryTitle.textContent = "글자 추출 완료 (AI 검수는 아직 실행되지 않음)";
    noticeList.replaceChildren();
    data.notices.forEach(function (notice) { addItem(noticeList, notice); });
    detectedList.replaceChildren();
    pageList.replaceChildren();
    if (data.format === "docx") renderDocxSummary(data);
    else renderPdfSummary(data);
    detectedBox.hidden = detectedList.children.length === 0;
    summaryBox.hidden = false;
  }

  function renderDocxSummary(data) {
    summaryBox.className = "notice " + (data.detected_unsupported.length ? "notice-warning" : "notice-info");
    let text = "Word 본문 블록 " + data.block_count + "개(문단 " + data.paragraph_count + "개·표 " + data.table_count
      + "개) 중 " + data.blocks.length + "개 블록에서 텍스트를 읽었습니다. "
      + numberFormat.format(data.char_count) + "자를 아래 입력칸에 넣었습니다.";
    if (data.empty_block_count) text += " 내용이 없는 블록 " + data.empty_block_count + "개는 넣지 않았습니다.";
    summaryText.textContent = text;
    data.detected_unsupported.forEach(function (item) { addItem(detectedList, item.label); });
    pagesLabel.textContent = "블록별 추출 범위";
    data.blocks.forEach(function (block) {
      const name = block.type === "table" ? "표 " + block.number : "문단 " + block.number;
      addItem(pageList, "블록 " + block.block + " · " + name + ": " + charRange(block.char_start, block.char_end));
      (block.rows || []).forEach(function (row) {
        addItem(pageList, "블록 " + block.block + " · " + name + " · " + row.row + "행: "
          + charRange(row.char_start, row.char_end));
      });
    });
  }

  function renderPdfSummary(data) {
    const readPages = data.page_count - data.pages_without_text.length;
    summaryBox.className = "notice " + (data.all_pages_have_text ? "notice-info" : "notice-warning");
    let text = "전체 " + data.page_count + "페이지 중 " + readPages + "페이지에서 텍스트를 읽었습니다. "
      + numberFormat.format(data.char_count) + "자를 아래 입력칸에 넣었습니다.";
    if (data.pages_without_text.length) {
      text += " 텍스트를 추출하지 못한 페이지: " + data.pages_without_text.join(", ") + ".";
    }
    summaryText.textContent = text;
    pagesLabel.textContent = "페이지별 추출 범위";
    data.pages.forEach(function (page) {
      const li = document.createElement("li");
      if (page.status === "text") {
        li.textContent = page.page + "페이지: " + numberFormat.format(page.char_start + 1) + "~"
          + numberFormat.format(page.char_end) + "번째 글자";
      } else if (page.status === "no_text") {
        li.textContent = page.page + "페이지: 추출된 텍스트 없음";
      } else {
        li.textContent = page.page + "페이지: 추출 실패";
      }
      pageList.appendChild(li);
    });
  }

  function applyResult(data) {
    clearPending();
    extractedField.setValue(data.text);
    appliedText = extractedField.textarea.value;
    editedNote.hidden = true;
    renderSummary(data);
  }

  function handleSuccess(data) {
    const current = extractedField.textarea.value;
    // 이미 추출·수정한 문구가 있으면 사용자가 교체를 선택했을 때만 바꿉니다.
    if (current.trim() !== "" && normalize(current) !== normalize(data.text)) {
      pendingResult = data;
      replaceBox.hidden = false;
      showMessage("warning", "새 추출 결과가 준비되었습니다", "아래에서 새 결과로 바꿀지 선택해 주세요. 선택하기 전까지 입력칸의 문구는 바뀌지 않습니다.");
      replaceApply.focus();
      return;
    }
    showMessage(null);
    applyResult(data);
  }

  replaceApply.addEventListener("click", function () {
    if (!pendingResult) return;
    const data = pendingResult;
    showMessage(null);
    applyResult(data);
    extractedField.textarea.focus();
  });
  replaceKeep.addEventListener("click", function () {
    clearPending();
    showMessage("info", "기존 문구를 유지했습니다", "새로 추출한 결과는 반영하지 않았습니다.");
    extractedField.textarea.focus();
  });

  extractedField.textarea.addEventListener("input", function () {
    editedNote.hidden = appliedText === null || extractedField.textarea.value === appliedText;
  });

  extractButton.addEventListener("click", async function () {
    if (busy) return; // 중복 실행 방지
    const file = fileInput.files[0];
    const problem = checkFile(file);
    setFileError(problem);
    if (problem) {
      fileInput.focus();
      return;
    }
    clearPending();
    showMessage(null);

    const seq = ++requestSeq;
    controller = new AbortController();
    const localController = controller;
    let timedOut = false;
    const timer = setTimeout(function () { timedOut = true; localController.abort(); }, CLIENT_TIMEOUT_MS);
    setBusy(true);

    const formData = new FormData();
    formData.append("promo_file", file, file.name);
    try {
      const res = await fetch(EXTRACT_URL, { method: "POST", body: formData, signal: localController.signal });
      let body = null;
      try { body = await res.json(); } catch (err) { body = null; }
      if (seq !== requestSeq) return; // 오래된 응답
      if (!body || typeof body.ok !== "boolean") {
        showMessage("danger", "글자 추출에 실패했습니다", "서버 응답을 읽지 못했습니다. 다시 시도해 주세요.");
      } else if (!body.ok) {
        showMessage("danger", "글자 추출에 실패했습니다", body.error.message);
      } else {
        handleSuccess(body.data);
      }
    } catch (err) {
      if (seq !== requestSeq) return;
      if (timedOut) {
        showMessage("danger", "글자 추출에 실패했습니다", "응답이 너무 오래 걸려 기다림을 멈췄습니다. 다시 시도해 주세요.");
      } else {
        showMessage("danger", "글자 추출에 실패했습니다", "서버에 연결하지 못했습니다. 다시 시도해 주세요.");
      }
    } finally {
      clearTimeout(timer);
      if (seq === requestSeq) {
        setBusy(false);
        controller = null;
      }
    }
  });

  // 결과를 만들지 않으므로 AppShell.work.setResult는 호출하지 않습니다.
  // 입력 작성 상태와 이탈 경고는 공통 shell의 자동 감지가 처리합니다. 탭 재방문 시 추출을 다시 실행하지 않습니다.
})();
