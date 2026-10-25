// 그린 클레임 체크 탭 스크립트. 이 탭 패널 내부만 다룹니다. 공통 API 사용법: docs/design_system.md
// 현재 단계: 문구 직접 입력 + 일반 PDF·Word(.docx) 글자 추출 + 사용자가 선택한 PDF·이미지(JPG·JPEG·PNG) AI 글자 판독·확인·수정.
// AI 그린워싱 검수·결과 PDF는 아직 연결하지 않습니다.
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
      busyText: " 글자를 추출하는 중입니다. 최대 30초 걸릴 수 있습니다.",
    },
    ocr: {
      url: "/api/green-claim/ocr",
      timeoutMs: 150000,
      failTitle: "AI 글자 판독에 실패했습니다",
      busyText: " AI가 글자를 판독하는 중입니다. 2분 넘게 걸릴 수 있습니다. "
        + "화면에서 취소해도 이미 보낸 요청의 처리·요금은 취소되지 않을 수 있습니다.",
    },
  };
  const OCR_HINT = "필요하면 아래 'AI 글자 판독'을 직접 선택할 수 있습니다(선택한 PDF가 OpenAI로 전송됩니다).";
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
    fileSection.setAttribute("aria-busy", busy ? "true" : "false");
    statusEl.replaceChildren();
    if (busy) {
      const spinner = document.createElement("span");
      spinner.className = "spinner";
      spinner.setAttribute("aria-hidden", "true");
      statusEl.append(spinner, REQUESTS[kind].busyText);
    }
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
    let text = "아래 문구는 바뀌지 않았습니다. 필요하면 다시 실행해 주세요.";
    // 브라우저 취소는 화면 대기만 멈춥니다. 서버·공급자에 이미 보낸 요청은 취소를 보장하지 않습니다.
    if (wasOcr) text += " 이미 보낸 AI 판독 요청의 처리·요금이 취소되었는지는 보장할 수 없습니다.";
    showMessage("info", title, text);
  }

  fileInput.addEventListener("change", function () {
    const canceled = busy;
    if (canceled) cancelExtraction("파일을 바꿔 이전 추출을 취소했습니다");
    clearPending();
    const file = fileInput.files[0];
    const problem = file ? checkFile(file) : "";
    setFileError(problem);
    const previous = appliedText !== null
      ? "새 파일로 추출·판독하기 전까지 아래 문구는 이전 파일에서 가져와 수정한 내용입니다." : "";
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
      + numberFormat.format(data.char_count) + "자를 아래 입력칸에 넣었습니다.";
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
      + numberFormat.format(data.char_count) + "자를 아래 입력칸에 넣었습니다.";
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
    let text = "출처: 일반 글자 추출(PDF 안의 텍스트 정보). 전체 " + data.page_count + "페이지 중 " + readPages
      + "페이지에서 텍스트를 읽었습니다. " + numberFormat.format(data.char_count) + "자를 아래 입력칸에 넣었습니다.";
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
      showMessage("warning", "이미지는 '글자 추출'을 지원하지 않습니다", IMAGE_HINT + " 아래 문구는 바뀌지 않았습니다.");
      return;
    }
    if (kind === "ocr" && kindOfFile === "docx") {
      clearPending();
      showMessage("warning", "Word는 'AI 글자 판독'을 지원하지 않습니다",
        "AI 글자 판독은 PDF·JPG·JPEG·PNG만 지원합니다. Word는 '글자 추출'을 사용해 주세요. 아래 문구는 바뀌지 않았습니다.");
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

  // 결과를 만들지 않으므로 AppShell.work.setResult는 호출하지 않습니다.
  // 입력 작성 상태와 이탈 경고는 공통 shell의 자동 감지가 처리합니다. 탭 재방문 시 추출을 다시 실행하지 않습니다.
})();
