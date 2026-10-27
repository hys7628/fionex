// 그린 클레임 체크 탭 스크립트. 이 탭 패널 내부만 다룹니다. 공통 API 사용법: docs/design_system.md
// 현재 단계: 문구 직접 입력 + 일반 PDF·Word(.docx) 글자 추출 + 사용자가 선택한 PDF·이미지(JPG·JPEG·PNG) AI 글자 판독·확인·수정
// + 그린워싱 표현 위험 검수 실행·결과 표시(feature_spec.md "검수 실행·결과 화면"). 결과 PDF는 아직 연결하지 않습니다.
(function () {
  "use strict";

  const FEATURE_ID = "green_claim";
  const MAX_CHARS = 20000;
  const MAX_FILE_BYTES = 10000000;
  // 일반 추출(서버 30초)과 AI 판독(공통 PDF 호출 120초)은 다른 요청입니다. 브라우저 대기 시간은 서버 제한 + 여유.
  const REQUESTS = {
    extract: {
      url: "/api/green-claim/extract",
      timeoutMs: 45000,
      failTitle: "글자 추출에 실패했습니다",
      busyText: "글자를 추출하는 중입니다. 최대 30초 걸릴 수 있습니다.",
    },
    ocr: {
      url: "/api/green-claim/ocr",
      timeoutMs: 150000,
      failTitle: "AI 글자 판독에 실패했습니다",
      busyText: "AI가 글자를 판독하는 중입니다. 2분 넘게 걸릴 수 있습니다. "
        + "화면에서 취소해도 이미 보낸 요청의 처리·요금은 취소되지 않을 수 있습니다.",
    },
  };
  const OCR_HINT = "필요하면 'AI 글자 판독'을 직접 선택할 수 있습니다(선택한 PDF가 OpenAI로 전송됩니다).";
  const IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png"];
  const IMAGE_HINT = "이미지는 '글자 추출'로 읽을 수 없습니다. 필요하면 'AI 글자 판독'을 직접 눌러 주세요"
    + "(이미지가 OpenAI로 전송되며 요금이 발생할 수 있습니다).";
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
      // 검수 실행을 막았을 때 입력칸에도 빈 입력·초과 안내를 바로 표시합니다(입력칸을 떠날 때와 같은 기준).
      showProblem: function () {
        touched = true;
        composing = false;
        refresh("blur");
      },
    };
  }

  const textField = createTextField("green_claim-claims");
  const extractedField = createTextField("green_claim-extracted");
  if (!textField || !extractedField) return;

  // 단계 화면 연결(아래 "단계 화면"에서 만듦). 처리 상태가 바뀔 때 단계 이동 버튼만 다시 계산합니다.
  let stepNav = null;

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
      reviewInputChanged("mode");
    });
  });
  const checkedMode = modeRadios.find(function (r) { return r.checked; });
  showMode(checkedMode ? checkedMode.value : "text");

  /* ---------- 일반 PDF·Word(.docx) 글자 추출, PDF AI 글자 판독 ---------- */
  const fileSection = byId("green_claim-file-section");
  const fileInput = byId("green_claim-file");
  const fileError = byId("green_claim-file-error");
  const extractButton = byId("green_claim-extract");
  const ocrButton = byId("green_claim-ocr");
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
  const detectedTitle = byId("green_claim-extract-detected-title");
  const detectedList = byId("green_claim-extract-detected");
  const pagesLabel = byId("green_claim-extract-pages-label");
  const pageList = byId("green_claim-extract-pages");
  const editedNote = byId("green_claim-extracted-edited");

  let requestSeq = 0;        // 가장 최근 추출 요청 번호. 이전 번호의 응답은 반영하지 않습니다.
  let controller = null;     // 진행 중 요청 취소용
  let busy = false;
  let busyKind = null;       // 진행 중 요청 종류("extract" | "ocr")
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

  // kind: 진행 중 요청 종류("extract" | "ocr"), 끝나면 null. 처리 중에는 두 버튼 모두 비활성(중복 실행 방지).
  function setBusy(kind) {
    busy = !!kind;
    busyKind = kind;
    extractButton.disabled = busy;
    ocrButton.disabled = busy;
    // 누른 버튼만 '작업 중' 문구·회전 표시(공통 AppShell.ui), 옆 상태 문장은 소요 시간 안내
    AppShell.ui.setButtonBusy(extractButton, kind === "extract" ? "글자 추출 중..." : null);
    AppShell.ui.setButtonBusy(ocrButton, kind === "ocr" ? "AI 판독 중..." : null);
    fileSection.setAttribute("aria-busy", busy ? "true" : "false");
    statusEl.textContent = busy ? REQUESTS[kind].busyText : "";
    if (stepNav) stepNav.update();
  }

  function clearPending() {
    pendingResult = null;
    replaceBox.hidden = true;
  }

  // 확장자 구분은 화면 안내용입니다. 실제 형식은 서버가 파일 내용으로 다시 확인합니다.
  function fileKind(file) {
    const name = file.name.toLowerCase();
    if (name.endsWith(".pdf")) return "pdf";
    if (name.endsWith(".docx")) return "docx";
    if (IMAGE_EXTENSIONS.some(function (ext) { return name.endsWith(ext); })) return "image";
    return null;
  }

  function checkFile(file) {
    if (!file) return "PDF·Word(.docx)·이미지(JPG·PNG) 파일을 선택해 주세요.";
    if (file.size === 0) return "빈 파일입니다. 내용이 있는 파일을 선택해 주세요.";
    if (file.size > MAX_FILE_BYTES) return "파일이 10,000,000바이트(약 10MB)를 넘습니다. 문서를 나누거나 용량을 줄여 주세요.";
    if (!fileKind(file)) {
      return "지원하지 않는 파일 형식입니다. PDF(.pdf)·Word(.docx)·JPG·JPEG·PNG 파일만 올릴 수 있습니다. "
        + ".doc·.docm·GIF·WebP·HEIC 등은 지원하지 않습니다.";
    }
    return "";
  }

  // 진행 중 요청을 취소하고 그 응답은 반영하지 않습니다(요청 번호를 올림). 기존 문구는 지우지 않습니다.
  function cancelExtraction(title) {
    const wasOcr = busyKind === "ocr";
    requestSeq += 1;
    if (controller) controller.abort();
    setBusy(null);
    clearPending();
    let text = "입력칸의 문구는 바뀌지 않았습니다. 필요하면 다시 실행해 주세요.";
    // 브라우저 취소는 화면 대기만 멈춥니다. 서버·공급자에 이미 보낸 요청은 취소를 보장하지 않습니다.
    if (wasOcr) text += " 이미 보낸 AI 판독 요청의 처리·요금이 취소되었는지는 보장할 수 없습니다.";
    showMessage("info", title, text);
  }

  fileInput.addEventListener("change", function () {
    const canceled = busy;
    if (canceled) cancelExtraction("파일을 바꿔 이전 추출을 취소했습니다");
    clearPending();
    reviewInputChanged("file");
    const file = fileInput.files[0];
    const problem = file ? checkFile(file) : "";
    setFileError(problem);
    const previous = appliedText !== null
      ? "새 파일로 추출·판독하기 전까지 입력칸의 문구는 이전 파일에서 가져와 수정한 내용입니다." : "";
    if (canceled) {
      // 취소 안내를 유지합니다.
    } else if (file && !problem && fileKind(file) === "image") {
      // 이미지 선택만으로는 요청하지 않습니다. 사용할 수 있는 버튼만 안내합니다.
      showMessage("info", "이미지 파일을 선택했습니다", (IMAGE_HINT + " " + previous).trim());
    } else if (file && !problem && previous) {
      showMessage("info", "새 파일을 선택했습니다", previous);
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

  // 요약은 텍스트로만 만듭니다. 출처(일반 추출 / AI 판독)를 구분하고,
  // PDF는 페이지 기준, Word는 본문 블록(문단·표·행) 기준입니다.
  function renderSummary(data) {
    summaryTitle.textContent = data.source === "ai_ocr"
      ? "AI 글자 판독 완료 (원본과 비교·수정 필요 · 그린워싱 검수 아님)"
      : "글자 추출 완료 (AI 검수는 아직 실행되지 않음)";
    noticeList.replaceChildren();
    data.notices.forEach(function (notice) { addItem(noticeList, notice); });
    detectedList.replaceChildren();
    pageList.replaceChildren();
    if (data.source === "ai_ocr" && data.format === "image") renderImageOcrSummary(data);
    else if (data.source === "ai_ocr") renderOcrSummary(data);
    else if (data.format === "docx") renderDocxSummary(data);
    else renderPdfSummary(data);
    detectedBox.hidden = detectedList.children.length === 0;
    summaryBox.hidden = false;
  }

  function renderOcrSummary(data) {
    summaryBox.className = "notice notice-warning";
    let text = "출처: AI 판독(모델 " + data.model + "). 서버가 확인한 전체 " + data.page_count + "페이지의 판독 결과 "
      + numberFormat.format(data.char_count) + "자를 추출 문구 입력칸에 넣었습니다.";
    if (data.pages_without_text.length) {
      text += " 글자가 없다고 보고된 페이지: " + data.pages_without_text.join(", ") + ".";
    }
    if (data.unreadable_mark_count) text += " [판독 불가] 표시 " + data.unreadable_mark_count + "곳.";
    summaryText.textContent = text;
    detectedTitle.textContent = "모델이 보고한 판독 불가·불확실 구간과 한계(측정한 정확도가 아님):";
    data.pages.forEach(function (page) {
      page.uncertain.forEach(function (note) { addItem(detectedList, page.page + "페이지: " + note); });
    });
    data.model_limitations.forEach(function (note) { addItem(detectedList, "문서 전체: " + note); });
    pagesLabel.textContent = "페이지별 판독 범위";
    data.pages.forEach(function (page) {
      addItem(pageList, page.page + "페이지: " + (page.status === "text"
        ? charRange(page.char_start, page.char_end) : "판독된 글자 없음"));
    });
  }

  function pixelSize(width, height) {
    return numberFormat.format(width) + "×" + numberFormat.format(height) + "픽셀";
  }

  // 이미지 판독: 원본 이미지와 판독용 사본 정보만 표시합니다(서버가 내부적으로 쓴 PDF·페이지 수는 표시하지 않음).
  function renderImageOcrSummary(data) {
    const image = data.image;
    summaryBox.className = "notice notice-warning";
    let text = "출처: AI 판독(모델 " + data.model + "). 원본 이미지(" + image.format.toUpperCase() + ", "
      + pixelSize(image.width, image.height) + ")의 판독용 사본에서 판독한 "
      + numberFormat.format(data.char_count) + "자를 추출 문구 입력칸에 넣었습니다.";
    if (image.sent_width !== image.width || image.sent_height !== image.height) {
      text += " 방향을 맞춘 사본 크기: " + pixelSize(image.sent_width, image.sent_height) + ".";
    }
    if (data.unreadable_mark_count) text += " [판독 불가] 표시 " + data.unreadable_mark_count + "곳.";
    summaryText.textContent = text;
    detectedTitle.textContent = "모델이 보고한 판독 불가·불확실 구간과 한계(측정한 정확도가 아님):";
    data.uncertain.forEach(function (note) { addItem(detectedList, "구간: " + note); });
    data.model_limitations.forEach(function (note) { addItem(detectedList, "이미지 전체: " + note); });
    pagesLabel.textContent = "판독 범위";
    addItem(pageList, "이미지 1장 전체: " + charRange(0, data.char_count));
  }

  function renderDocxSummary(data) {
    summaryBox.className = "notice " + (data.detected_unsupported.length ? "notice-warning" : "notice-info");
    detectedTitle.textContent = "이 문서에서 감지한 미지원 요소(추출하지 않음):";
    let text = "출처: Word 본문 추출. Word 본문 블록 " + data.block_count + "개(문단 " + data.paragraph_count + "개·표 " + data.table_count
      + "개) 중 " + data.blocks.length + "개 블록에서 텍스트를 읽었습니다. "
      + numberFormat.format(data.char_count) + "자를 추출 문구 입력칸에 넣었습니다.";
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
    let text = "출처: 일반 글자 추출(PDF 안의 텍스트 정보). 전체 " + data.page_count + "페이지 중 " + readPages
      + "페이지에서 텍스트를 읽었습니다. " + numberFormat.format(data.char_count) + "자를 추출 문구 입력칸에 넣었습니다.";
    if (data.pages_without_text.length) {
      text += " 텍스트를 추출하지 못한 페이지: " + data.pages_without_text.join(", ") + ".";
    }
    // 텍스트가 나와도 이미지 속 문구는 빠질 수 있으므로 AI 판독을 직접 선택할 수 있다고 알립니다(자동 호출 없음).
    text += " " + OCR_HINT;
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
    reviewInputChanged("extracted");  // 새 추출·판독 문구로 바꾸면 이전 검수 결과는 현재 입력의 결과가 아님
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

  // kind: "extract"(일반 글자 추출) | "ocr"(AI 글자 판독). 사용자가 버튼을 눌렀을 때만 호출합니다.
  async function runRequest(kind) {
    if (busy) return; // 중복 실행 방지
    const config = REQUESTS[kind];
    const file = fileInput.files[0];
    const problem = checkFile(file);
    setFileError(problem);
    if (problem) {
      fileInput.focus();
      return;
    }
    // 파일은 정상이지만 이 버튼이 지원하지 않는 형식이면 요청하지 않고 다른 버튼을 안내합니다.
    const kindOfFile = fileKind(file);
    if (kind === "extract" && kindOfFile === "image") {
      clearPending();
      showMessage("warning", "이미지는 '글자 추출'을 지원하지 않습니다", IMAGE_HINT + " 입력칸의 문구는 바뀌지 않았습니다.");
      return;
    }
    if (kind === "ocr" && kindOfFile === "docx") {
      clearPending();
      showMessage("warning", "Word는 'AI 글자 판독'을 지원하지 않습니다",
        "AI 글자 판독은 PDF·JPG·JPEG·PNG만 지원합니다. Word는 '글자 추출'을 사용해 주세요. 입력칸의 문구는 바뀌지 않았습니다.");
      return;
    }
    clearPending();
    showMessage(null);

    const seq = ++requestSeq;
    controller = new AbortController();
    const localController = controller;
    let timedOut = false;
    const timer = setTimeout(function () { timedOut = true; localController.abort(); }, config.timeoutMs);
    setBusy(kind);

    const formData = new FormData();
    formData.append("promo_file", file, file.name);
    try {
      const res = await fetch(config.url, { method: "POST", body: formData, signal: localController.signal });
      let body = null;
      try { body = await res.json(); } catch (err) { body = null; }
      if (seq !== requestSeq) return; // 오래된 응답
      if (!body || typeof body.ok !== "boolean") {
        showMessage("danger", config.failTitle, "서버 응답을 읽지 못했습니다. 다시 시도해 주세요.");
      } else if (!body.ok) {
        // 일반 추출에서 텍스트가 없으면 AI 판독을 직접 선택할 수 있다고 안내합니다(자동 호출하지 않음).
        const extra = kind === "extract" && body.error.code === "PDF_NO_TEXT" ? " " + OCR_HINT : "";
        showMessage("danger", config.failTitle, body.error.message + extra);
      } else {
        handleSuccess(body.data);
      }
    } catch (err) {
      if (seq !== requestSeq) return;
      let text = timedOut ? "응답이 너무 오래 걸려 기다림을 멈췄습니다. 다시 시도해 주세요."
        : "서버에 연결하지 못했습니다. 다시 시도해 주세요.";
      if (kind === "ocr") text += " 이미 보낸 AI 판독 요청의 처리·요금이 취소되었는지는 보장할 수 없습니다.";
      showMessage("danger", config.failTitle, text);
    } finally {
      clearTimeout(timer);
      if (seq === requestSeq) {
        setBusy(null);
        controller = null;
      }
    }
  }

  extractButton.addEventListener("click", function () { runRequest("extract"); });
  ocrButton.addEventListener("click", function () { runRequest("ocr"); });

  /* ---------- 그린워싱 표현 위험 검수 실행·결과 ---------- */
  // 공통 텍스트 AI timeout 60초 + 여유(처음 값은 기준 확인 30초 포함. 2026-10-26부터 자동 확인은 없으나 대기 제한은 그대로, feature_spec.md "저장 기준 검수")
  const REVIEW_URL = "/api/green-claim/review";
  const REVIEW_TIMEOUT_MS = 100000;
  const REVIEW_BUSY_TEXT = "검수 중입니다. 저장된 기준으로 AI가 검토하며 최대 100초 걸릴 수 있습니다. "
    + "화면에서 기다림을 멈춰도 이미 보낸 요청의 처리·요금은 취소되지 않을 수 있습니다.";
  const ACTION_LABELS = { revise_recommended: "수정 권고", needs_review: "검토 필요", judgment_withheld: "판단 보류" };
  const ACTION_TONES = { revise_recommended: "danger", needs_review: "warning", judgment_withheld: "info" };
  const LANGUAGE_LABELS = { ko: "한국어", en: "영어", "pt-BR": "브라질 포르투갈어", mixed: "여러 언어 혼합", unknown: "언어 판단 보류" };
  const NATURE_LABELS = { law: "법률", advertising_self_regulation: "광고 자율규제" };
  const CHECK_LABELS = {
    no_change_found: "대상 조항 전체를 비교해 변경을 발견하지 못함",
    partial_checked: "부분 확인(일부 조항은 발췌 문장만 확인)",
    change_detected: "원문 변경 감지 · 검토 전(기준에 반영 안 됨)",
    failed: "확인 실패",
    deferred: "조회 보류(이용 조건 등)",
    baseline_missing: "비교 기준 부족",
    not_checked: "확인 기록 없음",
    not_checked_this_request: "이번 요청에서 확인하지 못함",
    auto_check_off: "자동 확인 안 함(저장된 기준 사용)",
  };
  const UPDATED_UNRECORDED = "업데이트 날짜 미기록";  // PDF(report_worker.py)와 같은 문장
  const CHECK_MODE_LABELS = { stored_only: "저장된 기준 사용 · 최신성 자동 확인 안 함" };

  const reviewButton = byId("green_claim-review");
  const reviewStatusEl = byId("green_claim-review-status");
  const reviewMessageEl = byId("green_claim-review-message");
  const sourceBox = byId("green_claim-review-source-box");
  const sourceEl = byId("green_claim-review-source");
  const sourceErrorEl = byId("green_claim-review-source-error");
  const resultCard = byId("green_claim-result-card");
  const emptyEl = byId("green_claim-review-empty");
  const staleEl = byId("green_claim-review-stale");
  const resultEl = byId("green_claim-review-result");
  const resultLabelEl = byId("green_claim-review-result-label");
  const reviewSummaryEl = byId("green_claim-review-summary");
  const itemsEl = byId("green_claim-review-items");
  const criteriaEl = byId("green_claim-review-criteria");

  // 검수 결과 PDF: 서버 생성 최대 30초 + 여유(feature_spec.md "검수 결과 PDF 다운로드")
  const REPORT_URL = "/api/green-claim/report";
  const REPORT_TIMEOUT_MS = 45000;
  const REPORT_FILENAME = "green_claim_review_report.pdf";
  const pdfButton = byId("green_claim-pdf");
  const pdfHint = byId("green_claim-pdf-pending");
  const pdfMessageEl = byId("green_claim-pdf-message");

  let reviewSeq = 0;            // 가장 최근 검수 요청 번호. 다른 번호의 응답은 반영하지 않습니다.
  let reviewController = null;
  let reviewRunning = null;     // 진행 중 요청 정보 {seq, mode, text}
  let reviewResult = null;      // 마지막 성공 결과 {data, mode, at, displayedAt}
  let reviewStale = false;      // 마지막 성공 결과가 현재 입력의 결과가 아닌지(한 번 true면 되돌리지 않음)
  let pdfSeq = 0;               // 가장 최근 PDF 요청 번호. 다른 번호의 응답은 반영하지 않습니다.
  let pdfController = null;
  let pdfRunning = false;

  function currentMode() {
    const checked = modeRadios.find(function (r) { return r.checked; });
    return checked ? checked.value : "text";
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function showReviewMessage(type, title, text) {
    reviewMessageEl.replaceChildren();
    if (!title) return;
    const box = el("div", "notice notice-" + type);
    box.setAttribute("role", type === "danger" ? "alert" : "status");
    box.append(el("p", "notice-title", title));
    if (text) box.append(el("p", null, text));
    reviewMessageEl.append(box);
  }

  function setReviewBusy(on) {
    reviewButton.disabled = on || pdfRunning;
    AppShell.ui.setButtonBusy(reviewButton, on ? "검수 중..." : null);
    resultCard.setAttribute("aria-busy", on ? "true" : "false");
    reviewStatusEl.textContent = on ? REVIEW_BUSY_TEXT : "";
    updatePdfState();
  }

  function showPdfMessage(type, title, text) {
    pdfMessageEl.replaceChildren();
    if (!title) return;
    const box = el("div", "notice notice-" + type);
    box.setAttribute("role", type === "danger" ? "alert" : "status");
    box.append(el("p", "notice-title", title));
    if (text) box.append(el("p", null, text));
    pdfMessageEl.append(box);
  }

  // PDF 버튼은 현재 입력에 대한 유효 결과가 있고 검수·다운로드가 진행 중이 아닐 때만 활성
  function updatePdfState() {
    const valid = !!reviewResult && !reviewStale;
    pdfButton.disabled = !valid || !!reviewRunning || pdfRunning;
    AppShell.ui.setButtonBusy(pdfButton, pdfRunning ? "PDF 준비 중..." : null);
    pdfHint.replaceChildren();
    if (pdfRunning) {
      pdfHint.textContent = "PDF 보고서를 만드는 중입니다. 최대 30초 걸릴 수 있습니다.";
    } else if (!reviewResult) {
      pdfHint.textContent = "검수 결과가 있을 때 내려받을 수 있습니다.";
    } else if (reviewStale) {
      pdfHint.textContent = "입력이 바뀌어 다시 검수해야 내려받을 수 있습니다.";
    } else if (reviewRunning) {
      pdfHint.textContent = "검수 중에는 내려받을 수 없습니다.";
    } else {
      pdfHint.textContent = "현재 결과를 PDF 보고서로 내려받습니다(다시 검수하지 않음).";
    }
    if (stepNav) stepNav.update();  // 검수·PDF 처리 상태가 바뀔 때마다 단계 이동 가능 여부 갱신
  }

  // 결과 유효 여부를 화면·공통 작업 상태에 반영합니다. 다운로드 요청 상태는 PDF 다운로드 때만 AppShell이 바꿉니다.
  function syncResultState() {
    const valid = !!reviewResult && !reviewStale;
    staleEl.hidden = !(reviewResult && reviewStale);
    resultLabelEl.textContent = !reviewResult ? ""
      : (reviewStale ? "이전 문구의 결과 · " : "현재 입력에 대한 결과 · ") + "검수 시각 " + reviewResult.at
        + " · " + (reviewResult.mode === "file" ? "파일 추출·판독 문구" : "직접 입력 문구");
    resultLabelEl.dataset.state = reviewStale ? "stale" : "valid";
    AppShell.work.setResult(FEATURE_ID, valid);
    showPdfMessage(null);  // 이전 결과에 대한 다운로드 안내를 새 상태에 남기지 않음
    updatePdfState();
  }

  function cancelPdf(title) {
    pdfSeq += 1;
    if (pdfController) pdfController.abort();
    pdfController = null;
    pdfRunning = false;
    reviewButton.disabled = !!reviewRunning;
    updatePdfState();
    showPdfMessage("info", title, "파일 저장을 요청하지 않았습니다. 다시 검수한 뒤 내려받아 주세요.");
  }

  function cancelReview(title) {
    reviewSeq += 1;
    if (reviewController) reviewController.abort();
    reviewController = null;
    reviewRunning = null;
    setReviewBusy(false);
    showReviewMessage("info", title, "입력 문구는 그대로입니다. 필요하면 다시 '검수 실행'을 눌러 주세요. "
      + "이미 보낸 검수 요청의 처리·요금이 취소되었는지는 보장할 수 없습니다.");
  }

  // 검수 입력이 바뀜. kind: "text" | "extracted" | "mode" | "file"
  function reviewInputChanged(kind) {
    const affects = function (mode) {
      if (kind === "mode") return true;
      if (kind === "text") return mode === "text";
      return mode === "file";  // extracted·file
    };
    if (reviewRunning && affects(reviewRunning.mode)) {
      cancelReview("입력이 바뀌어 진행 중인 검수를 취소했습니다");
    }
    if (reviewResult && !reviewStale && affects(reviewResult.mode)) {
      reviewStale = true;
      syncResultState();
      // 다운로드 중 결과가 무효가 되면 늦은 응답으로 파일 저장을 요청하지 않음
      if (pdfRunning) cancelPdf("입력이 바뀌어 PDF 다운로드를 취소했습니다");
    }
  }

  textField.textarea.addEventListener("input", function () { reviewInputChanged("text"); });
  extractedField.textarea.addEventListener("input", function () { reviewInputChanged("extracted"); });

  /* ----- 원문 강조: 서버 위치는 Unicode 코드 포인트(Array.from 기준) ----- */
  function validSpan(item, chars) {
    return Number.isInteger(item.start) && Number.isInteger(item.end) && item.start >= 0
      && item.start < item.end && item.end <= chars.length
      && chars.slice(item.start, item.end).join("") === item.quote;
  }

  function focusTarget(target) {
    if (!target) return;
    target.scrollIntoView({ block: "center" });
    target.focus();
  }

  function renderSource(data) {
    const chars = Array.from(data.text);
    const good = [];
    const bad = [];
    data.items.forEach(function (item) { (validSpan(item, chars) ? good : bad).push(item); });
    sourceErrorEl.replaceChildren();
    if (bad.length) {
      const box = el("div", "notice notice-danger");
      box.setAttribute("role", "alert");
      box.append(el("p", "notice-title", "결과 위치 표시 오류"),
        el("p", null, "다음 항목은 원문 위치가 맞지 않아 원문에 강조하지 않았습니다: "
          + bad.map(function (item) { return item.id; }).join(", ") + ". 항목 내용은 오른쪽 결과에서 확인할 수 있습니다."));
      sourceErrorEl.append(box);
    }
    // 모든 시작·끝 위치로 원문을 나눠 조각마다 한 번만 출력합니다(겹치는 구간도 중복·누락 없음).
    const cuts = new Set([0, chars.length]);
    good.forEach(function (item) { cuts.add(item.start); cuts.add(item.end); });
    const points = Array.from(cuts).sort(function (a, b) { return a - b; });
    const starts = {};
    good.forEach(function (item) { (starts[item.start] = starts[item.start] || []).push(item); });
    sourceEl.replaceChildren();
    for (let i = 0; i < points.length - 1; i++) {
      const from = points[i];
      (starts[from] || []).forEach(function (item) {
        const mark = el("button", "green-claim-mark-label", item.id);
        mark.type = "button";
        mark.id = "green_claim-mark-" + item.id;
        mark.dataset.tone = ACTION_TONES[item.action] || "info";
        mark.setAttribute("aria-label", item.id + " " + (ACTION_LABELS[item.action] || "") + " 결과 항목으로 이동");
        mark.addEventListener("click", function () { focusTarget(byId("green_claim-item-" + item.id)); });
        sourceEl.append(mark);
      });
      const piece = chars.slice(from, points[i + 1]).join("");
      const covering = good.filter(function (item) { return item.start <= from && from < item.end; });
      if (!covering.length) {
        sourceEl.append(document.createTextNode(piece));
      } else {
        const mark = el("mark", "green-claim-mark", piece);
        mark.dataset.tone = ACTION_TONES[covering[0].action] || "info";
        mark.dataset.overlap = covering.length > 1 ? "true" : "false";
        mark.title = covering.map(function (item) { return item.id; }).join("·");
        sourceEl.append(mark);
      }
    }
  }

  /* ----- 결과 항목 ----- */
  function safeUrl(value) {
    try {
      const url = new URL(value);
      return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
    } catch (err) {
      return null;
    }
  }

  function field(parent, label, text, className) {
    if (text === undefined || text === null || text === "") return;
    const block = el("div", "green-claim-field" + (className ? " " + className : ""));
    block.append(el("p", "green-claim-field-label", label), el("p", "green-claim-field-text", text));
    parent.append(block);
  }

  function sourceKind(ref) {
    const org = ref.source_id && ref.source_id.indexOf("SRC-CONAR") === 0 ? "CONAR" : ref.source_id === "SRC-CDC" ? "CDC" : "";
    return (org ? org + " " : "") + (NATURE_LABELS[ref.legal_nature] || "구분 미확인");
  }

  function formatTime(value) {
    return value ? value.replace("T", " ").replace("+09:00", " (한국 시간)") : null;
  }

  function renderCriterion(id, ref) {
    const box = el("details", "green-claim-criterion");
    const summary = el("summary", null, ref
      ? sourceKind(ref) + " · " + ref.provisions + " · " + ref.title_ko + " (" + id + ")"
      : id + " · 기준 정보를 찾지 못함");
    box.append(summary);
    if (!ref) return box;
    field(box, "원문 요구(원문이 정한 내용)", ref.requirement_ko);
    field(box, "서비스 검토 해석(우리 서비스의 검토 관점, 원문과 같은 효력 없음)", ref.review_guidance_ko);
    field(box, "적용 범위·해석 한계", ref.scope_limits_ko);
    field(box, "저장된 원문 발췌(포르투갈어)", ref.excerpt_pt, "green-claim-pre");
    field(box, "한국어 번역(이해를 돕는 비공식 번역" + (ref.translation_official === false ? "" : ", 공식 여부 미확인") + ")",
      ref.translation_ko, "green-claim-pre");
    field(box, "자료 확보 시각", formatTime(ref.retrieved_at));
    const href = safeUrl(ref.official_url);
    const linkLine = el("p", "green-claim-field-text");
    if (href) {
      const a = el("a", null, "공식 출처 열기(새 창)");
      a.href = href;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      linkLine.append(a);
    } else {
      linkLine.textContent = "공식 출처 주소 형식이 안전하지 않아 링크를 표시하지 않았습니다.";
    }
    box.append(linkLine);
    if (ref.usage_rights_status === "ai_use_permission_unconfirmed") {
      box.append(el("p", "field-hint", "이 자료의 AI 이용 허가는 확인되지 않았습니다(기준 자료 기록)."));
    }
    return box;
  }

  function renderAlternative(parent, item) {
    const box = el("div", "green-claim-alternative");
    box.append(el("p", "green-claim-field-label", "대체 예시 (적용 승인 아님 · 사람 확인 필요)"));
    const alt = item.alternative;
    if (alt && (alt.original_text || alt.pt_br_text)) {
      if (alt.original_text) {
        field(box, "원문 언어 예시(" + (LANGUAGE_LABELS[item.quote_language] || "언어 미확인") + ")", alt.original_text);
      }
      if (alt.pt_br_text) field(box, "브라질 포르투갈어 예시", alt.pt_br_text);
      if (alt.ko_interpretation) field(box, "한국어 해석", alt.ko_interpretation);
    } else {
      box.append(el("p", "green-claim-field-text", item.alternative_note_ko || "대체 예시를 제공하지 않았습니다."));
    }
    if (alt && item.alternative_note_ko) box.append(el("p", "field-hint", item.alternative_note_ko));
    parent.append(box);
  }

  function renderItem(item, refs, chars) {
    const li = el("li", "green-claim-item");
    li.id = "green_claim-item-" + item.id;
    li.tabIndex = -1;
    li.dataset.tone = ACTION_TONES[item.action] || "info";
    const head = el("div", "green-claim-item-head");
    head.append(el("span", "green-claim-item-id", item.id));
    const badge = el("span", "badge badge-" + (ACTION_TONES[item.action] || "info"), ACTION_LABELS[item.action] || "조치 미확인");
    head.append(badge);
    if (validSpan(item, chars)) {
      const back = el("button", "btn btn-ghost green-claim-item-back", "원문 위치 보기");
      back.type = "button";
      back.setAttribute("aria-label", item.id + " 원문 위치 보기");
      back.addEventListener("click", function () { focusTarget(byId("green_claim-mark-" + item.id)); });
      head.append(back);
    } else {
      head.append(el("span", "field-hint", "원문 위치 표시 오류"));
    }
    li.append(head);
    field(li, "대상 구절 (" + (LANGUAGE_LABELS[item.quote_language] || "언어 미확인") + ")", item.quote, "green-claim-quote");
    field(li, "한국어 해석", item.interpretation_ko);
    field(li, "이유", item.reason_ko);
    field(li, "수정 방향", item.direction_ko);
    renderAlternative(li, item);
    const criteriaBox = el("div", "green-claim-field");
    criteriaBox.append(el("p", "green-claim-field-label", "관련 기준"));
    if (item.criteria_ids && item.criteria_ids.length) {
      item.criteria_ids.forEach(function (id) { criteriaBox.append(renderCriterion(id, refs[id])); });
    } else {
      criteriaBox.append(el("p", "green-claim-field-text", "연결된 기준 없음(판단 보류)"));
    }
    li.append(criteriaBox);
    return li;
  }

  function jumpButton(id) {
    const button = el("button", "btn btn-ghost green-claim-jump", id);
    button.type = "button";
    button.setAttribute("aria-label", id + " 결과 항목으로 이동");
    button.addEventListener("click", function () { focusTarget(byId("green_claim-item-" + id)); });
    return button;
  }

  // 추출 요약 renderSummary와 이름이 겹치면 같은 함수 범위에서 뒤 선언이 덮어쓰므로 이름을 구분합니다.
  function renderReviewSummary(data) {
    const s = data.summary;
    reviewSummaryEl.replaceChildren();
    const counts = el("p", "green-claim-summary-counts", "전체 " + numberFormat.format(s.total) + "개 항목");
    reviewSummaryEl.append(counts);
    const list = el("ul", "green-claim-summary-list");
    Object.keys(ACTION_LABELS).forEach(function (action) {
      const li = el("li", null);
      li.append(el("span", "badge badge-" + ACTION_TONES[action], ACTION_LABELS[action]),
        document.createTextNode(" " + numberFormat.format((s.by_action || {})[action] || 0) + "개 "));
      ((s.item_ids_by_action || {})[action] || []).forEach(function (id) { li.append(jumpButton(id)); });
      list.append(li);
    });
    reviewSummaryEl.append(list);
    if (s.no_items_message) {
      const none = el("div", "notice notice-info");
      none.append(el("p", "notice-title", s.no_items_message),
        el("p", null, "항목이 없어도 안전하거나 적법하다는 뜻이 아닙니다."));
      reviewSummaryEl.append(none);
    }
    field(reviewSummaryEl, "AI 작성 요약", s.model_summary_ko);
    // AI 보고 한계·판단 한계는 내용 그대로 접어 두는 상자 하나로(ⓘ 아이콘 + 펼쳐보기). 항목 0개 안내는 위에 그대로 보임
    const limits = el("details", "green-claim-limits");
    const limitsSummary = el("summary", null);
    limitsSummary.append(helpIcon(), document.createTextNode("판단 한계와 확인하지 않은 범위 보기"));
    limits.append(limitsSummary);
    if (data.model_limitations && data.model_limitations.length) {
      const box = el("div", "green-claim-field");
      box.append(el("p", "green-claim-field-label", "AI가 보고한 이번 검토의 한계"));
      const ul = el("ul", "green-claim-notice-list");
      data.model_limitations.forEach(function (text) { ul.append(el("li", null, text)); });
      box.append(ul);
      limits.append(box);
    }
    const notices = el("ul", "green-claim-notice-list");
    (data.notices || []).forEach(function (text) { notices.append(el("li", null, text)); });
    const noticeBox = el("div", "green-claim-field");
    noticeBox.append(el("p", "green-claim-field-label", "판단 한계와 확인하지 않은 범위"), notices);
    limits.append(noticeBox);
    reviewSummaryEl.append(limits);
  }

  // 도움말 버튼과 같은 "i" 아이콘(장식). 패널의 SVG를 복제해 모양을 한곳에서만 관리
  function helpIcon() {
    const source = panel.querySelector(".green-claim-help-icon");
    const icon = source ? source.cloneNode(true) : el("span", null);
    icon.setAttribute("aria-hidden", "true");
    return icon;
  }

  function renderCriteriaStatus(data) {
    const c = data.criteria;
    criteriaEl.replaceChildren();
    field(criteriaEl, "사용 기준", "기준 버전 " + c.bundle_version + " · "
      + (c.active_version === "base" ? "기본 기준" : "활성화된 기준 " + c.active_version)
      + " · " + (CHECK_MODE_LABELS[c.check_mode] || "저장된 기준 사용") + "(최신 개정 전체를 확인한 것이 아님)");
    field(criteriaEl, "기준 자료 업데이트 날짜", c.criteria_updated_on || UPDATED_UNRECORDED);
    field(criteriaEl, "검수 모델", (data.model || "모델 정보 없음") + " · 서비스 프롬프트 " + data.prompt_version);
    if (c.warnings && c.warnings.length) {
      const warn = el("div", "notice notice-warning");
      warn.append(el("p", "notice-title", "기준 확인 경고"));
      const ul = el("ul", "green-claim-notice-list");
      c.warnings.forEach(function (text) { ul.append(el("li", null, text)); });
      warn.append(ul);
      criteriaEl.append(warn);
    }
    if (c.unresolved_changes && c.unresolved_changes.length) {
      const box = el("div", "notice notice-warning");
      box.append(el("p", "notice-title", "공식 원문 변경이 감지됐지만 아직 기준에 반영하지 않았습니다"));
      const ul = el("ul", "green-claim-notice-list");
      c.unresolved_changes.forEach(function (change) {
        ul.append(el("li", null, change.source_id + " · 감지 " + (formatTime(change.detected_at) || "시각 없음")
          + " · 관련 기준 " + ((change.criteria_ids || []).join(", ") || "없음")));
      });
      box.append(ul);
      criteriaEl.append(box);
    }
    const list = el("ul", "green-claim-source-list");
    (c.sources || []).forEach(function (source) {
      const li = el("li", "green-claim-source");
      li.append(el("p", "green-claim-field-label", source.title + " (" + (NATURE_LABELS[source.legal_nature] || "구분 미확인") + ")"));
      const lines = [
        "자료 확보 시각: " + (formatTime(source.retrieved_at) || "기록 없음"),
        "이번 검수의 확인: " + (CHECK_LABELS[source.check_status] || "알 수 없는 상태")
          + (source.check_attempted_at ? " · 시도 " + formatTime(source.check_attempted_at) : ""),
        "마지막 성공 확인(이전 기록, 조항 비교 완료): " + (formatTime(source.check_last_success_at) || "기록 없음"),
      ];
      if (source.check_reason) lines.push("이유: " + source.check_reason);
      if (source.previous_check_status) {
        lines.push("이전 출처 확인 기록(이번 검수 아님): " + (CHECK_LABELS[source.previous_check_status] || "알 수 없는 상태")
          + (source.previous_check_attempted_at ? " · " + formatTime(source.previous_check_attempted_at) : ""));
      }
      if (source.usage_rights_status === "ai_use_permission_unconfirmed") lines.push("AI 이용 허가: 확인되지 않음");
      lines.forEach(function (text) { li.append(el("p", "green-claim-field-text", text)); });
      list.append(li);
    });
    criteriaEl.append(list);
    const details = el("details", "green-claim-pages");
    details.append(el("summary", null, "기준 상세 정보"));
    [
      "기준 묶음: " + c.bundle_id + " (형식 " + c.schema_version + ")",
      "내용 해시: " + c.content_hash,
      "확인 방식: " + (CHECK_MODE_LABELS[c.check_mode] || c.check_mode),
      "기준 상태 확인 결과: " + (c.check_overall || "없음"),
    ].forEach(function (text) { details.append(el("p", "green-claim-field-text", text)); });
    criteriaEl.append(details);
  }

  function looksLikeResult(data) {
    return data && typeof data.text === "string" && Array.isArray(data.items) && data.summary && data.criteria
      && typeof data.criteria_refs === "object";
  }

  function renderReview(data) {
    const chars = Array.from(data.text);
    renderSource(data);
    renderReviewSummary(data);
    itemsEl.replaceChildren();
    data.items.forEach(function (item) { itemsEl.append(renderItem(item, data.criteria_refs || {}, chars)); });
    renderCriteriaStatus(data);
    emptyEl.hidden = true;
    resultEl.hidden = false;
    sourceBox.hidden = false;
  }

  const pad = function (n) { return String(n).padStart(2, "0"); };

  function nowLabel(d) {
    return pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
  }

  // 이 컴퓨터 시계·시간대 기준 ISO 8601(예: 2026-10-26T10:00:05+09:00). PDF에는 "서버 확인 아님"으로 표시됩니다.
  function localIso(d) {
    const offset = -d.getTimezoneOffset();
    const abs = Math.abs(offset);
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + "T" + nowLabel(d)
      + (offset >= 0 ? "+" : "-") + pad(Math.floor(abs / 60)) + ":" + pad(abs % 60);
  }

  async function runReview() {
    if (reviewRunning) return;  // 중복 실행 방지
    const mode = currentMode();
    if (mode === "file" && busy) {
      showReviewMessage("warning", "글자 추출·판독이 끝난 뒤 검수해 주세요", "진행 중인 작업이 끝나면 문구를 확인한 뒤 다시 눌러 주세요.");
      return;
    }
    const inputField = mode === "file" ? extractedField : textField;
    const text = normalize(inputField.textarea.value);
    const check = inspect(text);
    if (check.problem) {
      inputField.showProblem();  // 입력칸 오류 안내 갱신(문구는 그대로)
      showReviewMessage("warning", "검수를 실행하지 않았습니다", MESSAGES[check.problem]);
      inputField.textarea.focus();
      return;
    }
    const seq = ++reviewSeq;
    reviewRunning = { seq: seq, mode: mode, text: text };
    reviewController = new AbortController();
    const localController = reviewController;
    let timedOut = false;
    const timer = setTimeout(function () { timedOut = true; localController.abort(); }, REVIEW_TIMEOUT_MS);
    showReviewMessage(null);
    setReviewBusy(true);
    try {
      const res = await fetch(REVIEW_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text }),
        signal: localController.signal,
      });
      let body = null;
      try { body = await res.json(); } catch (err) { body = null; }
      if (seq !== reviewSeq) return;  // 취소됐거나 오래된 응답
      const previous = reviewResult && !reviewStale ? " 아래 결과는 이전에 성공한 검수 결과입니다(검수 시각 " + reviewResult.at + ")." : "";
      if (!body || typeof body.ok !== "boolean") {
        showReviewMessage("danger", "검수에 실패했습니다", "서버 응답을 읽지 못했습니다. 입력 문구는 그대로이며 다시 실행할 수 있습니다." + previous);
      } else if (!body.ok) {
        showReviewMessage("danger", "검수에 실패했습니다", body.error.message + " 입력 문구는 그대로이며 다시 실행할 수 있습니다." + previous);
      } else if (!looksLikeResult(body.data)) {
        showReviewMessage("danger", "결과 표시 오류", "검수 결과 형식을 표시할 수 없습니다. 다시 실행해 주세요." + previous);
      } else {
        const received = new Date();
        reviewResult = { data: body.data, mode: mode, at: nowLabel(received), displayedAt: localIso(received) };
        reviewStale = false;
        renderReview(body.data);
        syncResultState();
        showReviewMessage("success", "검수를 마쳤습니다", "결과는 표현 위험 스크리닝이며 적법성·사실·인증을 보장하지 않습니다.");
        if (stepNav) stepNav.showResults();  // 검수 성공 후에만 결과 단계로 이동(화면 전환만)
      }
    } catch (err) {
      if (seq !== reviewSeq) return;
      const previous = reviewResult && !reviewStale ? " 아래 결과는 이전에 성공한 검수 결과입니다(검수 시각 " + reviewResult.at + ")." : "";
      showReviewMessage("danger", "검수에 실패했습니다",
        (timedOut ? "응답이 100초 안에 오지 않아 기다림을 멈췄습니다." : "서버에 연결하지 못했습니다.")
        + " 이미 보낸 요청의 처리·요금이 취소되었는지는 보장할 수 없습니다. 입력 문구는 그대로이며 다시 실행할 수 있습니다." + previous);
    } finally {
      clearTimeout(timer);
      if (seq === reviewSeq) {
        reviewRunning = null;
        reviewController = null;
        setReviewBusy(false);
      }
    }
  }

  reviewButton.addEventListener("click", runReview);

  /* ---------- 검수 결과 PDF 다운로드: 화면에 있는 마지막 유효 결과를 보냄(검수 API를 다시 부르지 않음) ---------- */
  async function startsWithPdf(blob) {
    const head = new Uint8Array(await blob.slice(0, 5).arrayBuffer());
    return blob.size > 0 && String.fromCharCode.apply(null, Array.from(head)) === "%PDF-";
  }

  async function downloadPdf() {
    if (pdfRunning || reviewRunning || !reviewResult || reviewStale) return;  // 중복 실행·무효 결과 차단
    const target = reviewResult;
    const seq = ++pdfSeq;
    pdfController = new AbortController();
    const localController = pdfController;
    let timedOut = false;
    const timer = setTimeout(function () { timedOut = true; localController.abort(); }, REPORT_TIMEOUT_MS);
    pdfRunning = true;
    reviewButton.disabled = true;
    showPdfMessage(null);
    updatePdfState();
    const retry = " 검수 결과와 입력은 그대로이며 다시 시도할 수 있습니다.";
    try {
      const res = await fetch(REPORT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ review: target.data, input_mode: target.mode, displayed_at: target.displayedAt }),
        signal: localController.signal,
      });
      const type = res.headers.get("Content-Type") || "";
      if (res.ok && type.indexOf("application/pdf") === 0) {
        const blob = await res.blob();
        const isPdf = await startsWithPdf(blob);
        if (seq !== pdfSeq || reviewResult !== target || reviewStale) return;  // 취소됐거나 그사이 결과가 바뀜
        if (!isPdf) {
          showPdfMessage("danger", "PDF 다운로드에 실패했습니다", "받은 파일이 PDF 형식이 아닙니다." + retry);
          return;
        }
        // 브라우저에 저장을 요청한 시점까지만 확인할 수 있습니다(실제 저장 완료는 확인 불가).
        AppShell.work.downloadBlob(FEATURE_ID, blob, REPORT_FILENAME);
        showPdfMessage("success", "브라우저에 PDF 다운로드를 요청했습니다",
          "실제 저장 여부는 브라우저의 다운로드 목록에서 확인해 주세요. 검수 결과는 화면에 그대로 있습니다.");
      } else {
        let body = null;
        try { body = await res.json(); } catch (err) { body = null; }
        if (seq !== pdfSeq) return;
        const message = body && body.ok === false && body.error ? body.error.message : "서버 응답을 읽지 못했습니다.";
        showPdfMessage("danger", "PDF 다운로드에 실패했습니다", message + retry);
      }
    } catch (err) {
      if (seq !== pdfSeq) return;
      showPdfMessage("danger", "PDF 다운로드에 실패했습니다",
        (timedOut ? "응답이 45초 안에 오지 않아 기다림을 멈췄습니다." : "서버에 연결하지 못했습니다.") + retry);
    } finally {
      clearTimeout(timer);
      if (seq === pdfSeq) {
        pdfRunning = false;
        pdfController = null;
        reviewButton.disabled = !!reviewRunning;
        updatePdfState();
      }
    }
  }

  pdfButton.addEventListener("click", downloadPdf);
  updatePdfState();

  /* ---------- 단계 화면(자료 입력 → 문구 확인 → 검수 결과): 표시 전환만 합니다 ---------- */
  // 요청을 만들지 않고 입력·결과·다운로드 상태를 바꾸지 않습니다. 입력칸·파일칸은 하나씩이며 단계 자리 사이로 옮깁니다.
  // 처리 중(추출·판독·검수·PDF)에는 단계 이동을 막아 기존 취소·늦은 응답 보호와 겹치지 않게 합니다.
  stepNav = (function () {
    const STEP_NAMES = { 1: "자료 입력", 2: "문구 확인", 3: "검수 결과" };
    const stages = Array.from(panel.querySelectorAll("[data-step-panel]"));
    const navButtons = Array.from(panel.querySelectorAll("[data-step-go]"));
    const slot = function (name) { return panel.querySelector('[data-slot="' + name + '"]'); };
    const claimsField = byId("green_claim-claims-field");
    const fileField = byId("green_claim-file-field");
    const nextButton = byId("green_claim-step1-next");
    const backButtons = [byId("green_claim-step2-back"), byId("green_claim-step3-back")];
    const kindHint = byId("green_claim-file-kind-hint");
    const liveEl = byId("green_claim-step-live");
    const titles = { 1: byId("green_claim-input-title"), 2: byId("green_claim-confirm-title"), 3: byId("green_claim-results-title") };
    const KIND_HINTS = {
      pdf: "PDF: 텍스트가 든 일반 PDF는 '글자 추출'(외부 전송 없음), 스캔 PDF는 'AI 글자 판독'을 사용하세요.",
      docx: "Word: '글자 추출'만 지원합니다('AI 글자 판독'은 Word를 지원하지 않음).",
      image: "이미지: 'AI 글자 판독'만 지원합니다('글자 추출'로 읽을 수 없음).",
    };
    let current = 1;
    let reached = 1;

    function processing() { return busy || !!reviewRunning || pdfRunning; }

    // 입력칸·파일칸을 현재 단계 자리로 옮김(같은 요소라 값·선택 파일·글자 수·오류가 그대로 유지)
    function place(step) {
      const at = step === 1 ? "1" : "2";
      slot("text-" + at).append(claimsField);
      slot("file-" + at).append(fileField);
    }

    // 1단계 '다음' 조건: 기존 입력 검사를 그대로 씁니다(오류 표시도 기존 함수).
    function inputReady() {
      if (currentMode() === "text") {
        if (!inspect(textField.textarea.value).problem) return true;
        textField.showProblem();
        textField.textarea.focus();
        return false;
      }
      const file = fileInput.files[0];
      if (!file && extractedField.textarea.value.trim() !== "") return true;  // 이미 가져온 추출 문구가 있음
      const problem = checkFile(file);
      setFileError(problem);
      if (!problem) return true;
      fileInput.focus();
      return false;
    }

    function update() {
      const locked = processing();
      navButtons.forEach(function (button) {
        const n = Number(button.dataset.stepGo);
        const state = n === current ? "current"
          : n === 3 ? (reviewResult ? (reviewStale ? "stale" : "done") : "locked")
          : n === 2 ? (reviewResult && !reviewStale ? "done" : (reached >= 2 ? "visited" : "todo"))
          : (reached >= 2 ? "done" : "todo");
        const labels = { current: "현재 단계", done: "완료", visited: "진행 중", stale: "이전 문구의 결과", locked: "검수 후 열림", todo: "" };
        button.dataset.state = state;
        button.querySelector("[data-step-state]").textContent = labels[state] ? "(" + labels[state] + ")" : "";
        button.disabled = locked || n === current || (n === 3 && !reviewResult);
        if (n === current) button.setAttribute("aria-current", "step");
        else button.removeAttribute("aria-current");
      });
      nextButton.disabled = locked;
      backButtons.forEach(function (button) { button.disabled = locked; });
      const file = fileInput.files[0];
      kindHint.textContent = file && fileKind(file) ? KIND_HINTS[fileKind(file)] : "파일을 선택해 주세요.";
    }

    // force: 검수 성공 직후(아직 처리 중 표시가 남은 순간)에도 결과 단계로 옮김
    function go(step, force) {
      if (step === current || (!force && processing())) return;
      if (step === 3 && !reviewResult) return;
      if (step === 2 && current === 1 && !inputReady()) return;
      current = step;
      reached = Math.max(reached, step);
      place(step);
      stages.forEach(function (stage) { stage.hidden = Number(stage.dataset.stepPanel) !== step; });
      update();
      liveEl.textContent = step + "단계 " + STEP_NAMES[step] + " 화면입니다.";
      titles[step].focus({ preventScroll: true });
      titles[step].scrollIntoView({ block: "nearest" });
    }

    navButtons.forEach(function (button) {
      button.addEventListener("click", function () { go(Number(button.dataset.stepGo)); });
    });
    nextButton.addEventListener("click", function () { go(2); });
    backButtons[0].addEventListener("click", function () { go(1); });
    backButtons[1].addEventListener("click", function () { go(2); });
    fileInput.addEventListener("change", update);
    modeRadios.forEach(function (radio) { radio.addEventListener("change", update); });

    place(1);
    update();
    return { update: update, showResults: function () { go(3, true); }, current: function () { return current; } };
  })();
  stepNav.update();

  /* ---------- ⓘ 도움말: 클릭·키보드·초점·마우스·터치, Escape·바깥 클릭·닫기 버튼으로 닫음 ---------- */
  // 화면 안에 보이도록 fixed 위치를 계산합니다(카드 overflow에 잘리지 않음). 상태·요청과 무관합니다.
  (function () {
    const helps = Array.from(panel.querySelectorAll(".green-claim-help"));
    let open = null;  // {help, button, pop, pinned}
    let refocusing = false;  // 닫으며 버튼으로 초점을 돌릴 때 focusin으로 다시 열리지 않게

    function position(entry) {
      const rect = entry.button.getBoundingClientRect();
      const width = Math.min(360, window.innerWidth - 32);
      entry.pop.style.width = width + "px";
      const height = entry.pop.offsetHeight;
      const left = Math.min(Math.max(16, rect.left + rect.width / 2 - width / 2), window.innerWidth - 16 - width);
      let top = rect.bottom + 8;
      if (top + height > window.innerHeight - 8 && rect.top - 8 - height >= 8) top = rect.top - 8 - height;
      entry.pop.style.left = left + "px";
      entry.pop.style.top = Math.max(8, top) + "px";
    }

    function close(returnFocus) {
      if (!open) return;
      const entry = open;
      open = null;
      entry.pop.hidden = true;
      entry.button.setAttribute("aria-expanded", "false");
      if (returnFocus) {
        refocusing = true;
        entry.button.focus();
        refocusing = false;
      }
    }

    function show(entry, pinned) {
      if (open && open.help !== entry.help) close(false);
      entry.pinned = pinned || (open && open.help === entry.help && open.pinned) || false;
      open = entry;
      entry.pop.hidden = false;
      entry.button.setAttribute("aria-expanded", "true");
      position(entry);
    }

    helps.forEach(function (help) {
      const entry = { help: help, button: help.querySelector(".green-claim-help-button"), pop: help.querySelector(".green-claim-popover") };
      let leaveTimer = null;
      entry.button.addEventListener("click", function () {
        if (open && open.help === help && open.pinned) close(false);
        else show(entry, true);  // 마우스로 열려 있던 것도 누르면 고정
      });
      entry.pop.querySelector(".green-claim-popover-close").addEventListener("click", function () { close(true); });
      help.addEventListener("pointerenter", function (event) {
        if (event.pointerType !== "mouse") return;
        clearTimeout(leaveTimer);
        if (!open || open.help !== help) show(entry, false);
      });
      help.addEventListener("pointerleave", function (event) {
        if (event.pointerType !== "mouse") return;
        leaveTimer = setTimeout(function () { if (open && open.help === help && !open.pinned) close(false); }, 250);
      });
      help.addEventListener("focusin", function () { if (!refocusing && (!open || open.help !== help)) show(entry, false); });
      help.addEventListener("focusout", function (event) {
        if (open && open.help === help && !help.contains(event.relatedTarget)) close(false);
      });
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && open) close(true);
    });
    document.addEventListener("pointerdown", function (event) {
      if (open && !open.help.contains(event.target)) close(false);
    });
    window.addEventListener("resize", function () { if (open) position(open); });
    window.addEventListener("scroll", function () { if (open) position(open); }, true);
    AppShell.onHide(FEATURE_ID, function () { close(false); });
  })();

  // 입력 작성 상태와 이탈 경고는 공통 shell의 자동 감지와 setResult가 처리합니다(중복 구현 없음).
  // 탭 재방문 시 추출·판독·검수를 다시 실행하지 않고 결과를 무효화하지 않습니다.
})();
