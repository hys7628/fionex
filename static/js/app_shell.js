/*
 * 공통 shell: 탭 전환(페이지 새로고침 없음), 작은 화면 메뉴, 탭별 작업 상태 표시.
 * - 탭 패널은 DOM에 그대로 두고 hidden만 바꿉니다. 입력값·선택 파일·결과 DOM이 유지됩니다.
 * - 탭 사이 데이터는 전달하지 않습니다.
 * 기능 코드용 공개 API는 window.AppShell 입니다. 사용법: docs/design_system.md
 */
(function () {
  "use strict";

  const shell = document.querySelector("[data-app-shell]");
  if (!shell) return;

  const serviceName = shell.dataset.serviceName || "";
  const main = document.getElementById("main-content");
  const topbar = shell.querySelector(".topbar");
  const backdrop = shell.querySelector("[data-sidebar-backdrop]");
  const menuToggle = shell.querySelector("[data-menu-toggle]");
  const menuClose = shell.querySelector("[data-menu-close]");
  const smallScreen = window.matchMedia("(max-width: 959.98px)");

  const panels = new Map();
  shell.querySelectorAll("[data-feature-panel]").forEach(function (panel) {
    panels.set(panel.dataset.featurePanel, panel);
  });
  const links = Array.from(shell.querySelectorAll("[data-tab-link]"));
  const firstId = panels.keys().next().value;
  const handlers = { show: {}, hide: {} };
  let currentId = null;

  function known(id) {
    if (panels.has(id)) return true;
    console.warn("[AppShell] 알 수 없는 기능 id:", id);
    return false;
  }

  function runHandlers(type, id) {
    (handlers[type][id] || []).forEach(function (fn) {
      try { fn(panels.get(id)); } catch (err) { console.error(err); }
    });
  }

  /* ---------- 탭 전환 ---------- */
  function showTab(id, options) {
    const focus = options && options.focus;
    if (id !== currentId) {
      const prevId = currentId;
      panels.forEach(function (panel, pid) { panel.hidden = pid !== id; });
      links.forEach(function (link) {
        if (link.dataset.tabLink === id) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
      });
      document.title = panels.get(id).dataset.featureTitle + " · " + serviceName;
      currentId = id;
      if (prevId) runHandlers("hide", prevId);
      runHandlers("show", id);
    }
    if (focus) {
      window.scrollTo(0, 0);
      const title = panels.get(id).querySelector(".page-title");
      if (title) title.focus({ preventScroll: true });
    }
  }

  function idFromHash() {
    const id = decodeURIComponent(window.location.hash.slice(1));
    return panels.has(id) ? id : null;
  }

  // 메뉴는 일반 해시 링크(#market_analysis)입니다. 해시 변경은 페이지를 다시 불러오지 않습니다.
  window.addEventListener("hashchange", function () {
    const id = idFromHash();
    if (id) showTab(id, { focus: true });
  });

  links.forEach(function (link) {
    link.addEventListener("click", function () {
      // 이미 열린 탭을 다시 누르면 hashchange가 없으므로 여기서 초점만 옮깁니다.
      if (link.dataset.tabLink === currentId) showTab(currentId, { focus: true });
      closeMenu(false);
    });
  });

  const skipLink = document.querySelector("[data-skip-link]");
  if (skipLink) {
    skipLink.addEventListener("click", function (event) {
      event.preventDefault(); // 해시를 바꾸지 않아 현재 탭이 유지됩니다.
      main.focus();
    });
  }

  /* ---------- 작은 화면 메뉴 ---------- */
  function setBehindInert(value) {
    [main, topbar].forEach(function (el) {
      if (value) el.setAttribute("inert", "");
      else el.removeAttribute("inert");
    });
  }

  function openMenu() {
    shell.classList.add("is-menu-open");
    backdrop.hidden = false;
    menuToggle.setAttribute("aria-expanded", "true");
    setBehindInert(true);
    const active = links.find(function (link) { return link.dataset.tabLink === currentId; });
    (active || links[0]).focus();
  }

  function closeMenu(returnFocus) {
    if (!shell.classList.contains("is-menu-open")) return;
    shell.classList.remove("is-menu-open");
    backdrop.hidden = true;
    menuToggle.setAttribute("aria-expanded", "false");
    setBehindInert(false);
    if (returnFocus) menuToggle.focus();
  }

  menuToggle.addEventListener("click", openMenu);
  menuClose.addEventListener("click", function () { closeMenu(true); });
  backdrop.addEventListener("click", function () { closeMenu(true); });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeMenu(true);
  });
  smallScreen.addEventListener("change", function () { closeMenu(false); });

  /* ---------- 작업 상태 ---------- */
  // 패널 안 입력 요소가 기본값과 다르면 "작성 중"으로 봅니다.
  function panelHasInput(panel) {
    return Array.from(panel.querySelectorAll("input, textarea, select")).some(function (el) {
      if (el.disabled || el.closest("[data-work-ignore]")) return false;
      if (el.tagName === "SELECT") {
        return Array.from(el.options).some(function (o) { return o.selected !== o.defaultSelected; });
      }
      switch (el.type) {
        case "file": return el.files.length > 0;
        case "checkbox":
        case "radio": return el.checked !== el.defaultChecked;
        case "button":
        case "submit":
        case "reset":
        case "hidden": return false;
        default: return el.value !== el.defaultValue;
      }
    });
  }

  function recheckInputs(id) {
    const hasInput = panelHasInput(panels.get(id));
    const patch = { inputs: hasInput };
    if (hasInput) patch.downloadRequested = false;
    LeaveGuard.update(id, patch);
  }

  panels.forEach(function (panel, id) {
    panel.addEventListener("input", function () { recheckInputs(id); });
    panel.addEventListener("change", function () { recheckInputs(id); });
    // reset 이벤트는 값이 되돌려지기 전에 발생합니다.
    panel.addEventListener("reset", function () { setTimeout(function () { recheckInputs(id); }, 0); });
    // 폼 기본 제출은 페이지를 다시 불러와 모든 탭 상태를 잃게 하므로 막습니다.
    // 기능 코드는 자체 submit 핸들러에서 fetch로 요청합니다.
    panel.addEventListener("submit", function (event) { event.preventDefault(); });
  });

  function renderStatus(id, snap) {
    const chip = shell.querySelector('[data-work-status="' + id + '"]');
    const navStatus = shell.querySelector('[data-nav-status="' + id + '"]');
    let text = "";
    let tone = "";
    let navText = "";
    // 다운로드하지 않은 결과는 머리글·사이드바에 표시하지 않고 이탈 경고(LeaveGuard)만 유지합니다(2026-10-26 한윤수 요청, 공통 변경).
    if (snap.hasDraft) {
      text = "작성 중인 입력 있음"; tone = "info"; navText = "작성 중";
    } else if (snap.downloadRequested) {
      text = "다운로드 요청됨 · 저장 여부는 브라우저에서 확인"; tone = "success";
    }
    chip.textContent = text;
    chip.dataset.tone = tone;
    chip.hidden = !text;
    navStatus.querySelector("[data-nav-status-text]").textContent = navText ? "(" + navText + ")" : "";
    navStatus.hidden = !navText;
  }

  LeaveGuard.subscribe(renderStatus);

  const work = {
    // 자동 감지 외 작성 중 상태(예: 결과 편집기)를 알립니다.
    setDraft: function (id, value) {
      if (known(id)) LeaveGuard.update(id, { draft: !!value, downloadRequested: false });
    },
    // 다운로드하지 않은 결과가 생기면 true, 결과를 지우면 false.
    setResult: function (id, value) {
      if (known(id)) LeaveGuard.update(id, { result: !!value, downloadRequested: false });
    },
    // 다운로드를 요청했음을 알립니다. 실제 저장 성공 여부는 확인할 수 없습니다.
    // 입력·결과 경고를 해제하고, 이후 입력을 다시 수정하면 다시 경고합니다.
    markDownloadRequested: function (id) {
      if (known(id)) LeaveGuard.update(id, { inputs: false, draft: false, result: false, downloadRequested: true });
    },
    // Blob(예: fetch로 받은 PDF)을 내려받기 요청하고 markDownloadRequested를 호출합니다.
    downloadBlob: function (id, blob, filename) {
      if (!known(id)) return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
      work.markDownloadRequested(id);
    },
    // 코드로 입력값을 바꾼 뒤 자동 감지를 다시 실행합니다(코드 변경은 input 이벤트가 없음).
    recheckInputs: function (id) {
      if (known(id)) recheckInputs(id);
    },
    // 탭 작업 상태를 모두 해제합니다(예: 사용자가 '새로 시작'을 누른 경우).
    clear: function (id) {
      if (known(id)) LeaveGuard.update(id, { inputs: false, draft: false, result: false, downloadRequested: false });
    },
    get: function (id) {
      return known(id) ? LeaveGuard.get(id) : null;
    },
  };

  /* ---------- 작업 중 버튼·결과 초점 ---------- */
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const busyFocus = new WeakSet();  // 작업을 시작할 때 초점이 있던 버튼

  function focusLost() {
    return !document.activeElement || document.activeElement === document.body;
  }

  // 숨겨진 탭·화면 안이거나 문서에서 빠진 요소에는 초점을 옮기지 않습니다(탭 이동 중 끝난 작업이 초점을 뺏지 않게).
  function canFocus(el) {
    return !!el && el.isConnected && !el.closest("[hidden]") && !el.closest("[inert]");
  }

  // 실행·다운로드 버튼을 '작업 중' 모양으로 바꿉니다(문구 교체 + aria-busy, 회전 표시는 common.css).
  // label이 없으면 원래 문구로 되돌립니다. disabled는 바꾸지 않습니다: 다시 누를 수 있는 시점(중복 실행 방지)은 기능 코드가 정합니다.
  // 초점이 있던 버튼을 disabled로 바꾸면 브라우저가 초점을 body로 옮기므로(focus fixup), 되돌릴 때 초점이 여전히
  // 비어 있고 버튼을 다시 누를 수 있으면 그 버튼으로 초점을 돌려 줍니다. 기능 코드가 결과·오류 칸으로 초점을 옮겼으면 그대로 둡니다.
  function setButtonBusy(button, label) {
    if (!button) return;
    if (label) {
      if (!("idleLabel" in button.dataset)) button.dataset.idleLabel = button.textContent;
      if (document.activeElement === button) busyFocus.add(button);
      button.textContent = label;
      button.setAttribute("aria-busy", "true");
    } else if ("idleLabel" in button.dataset) {
      button.textContent = button.dataset.idleLabel;
      delete button.dataset.idleLabel;
      button.removeAttribute("aria-busy");
      if (busyFocus.has(button)) {
        busyFocus.delete(button);
        // disabled 복원이 이 호출 뒤에 오는 기능도 있어 다음 차례에 확인합니다.
        setTimeout(function () {
          if (focusLost() && canFocus(button) && !button.disabled) button.focus({ preventScroll: true });
        }, 0);
      }
    }
  }

  // 사용자가 실행한 작업의 결과 시작점(제목·영역)으로 초점을 옮깁니다. 자동 로딩·성공 안내에는 쓰지 않습니다.
  // tabindex가 없는 대상에는 tabindex="-1"을 붙여 Tab 순서에는 넣지 않습니다.
  // options.scroll: "start" | "nearest" | false(기본 "nearest"). reduced-motion이면 부드러운 스크롤을 쓰지 않습니다.
  // options.from: 요소 배열. 지금 초점이 body(사라짐)이거나 이 요소들 안에 있을 때만 옮깁니다(사용자가 다른 곳으로 옮겼으면 그대로).
  // 옮겼으면 true를 돌려줍니다.
  function focusResult(target, options) {
    const opts = options || {};
    const el = typeof target === "string" ? document.querySelector(target) : target;
    if (!canFocus(el)) return false;
    const from = (opts.from || []).filter(Boolean);
    const current = document.activeElement;
    if (!focusLost() && from.length && !from.some(function (f) { return f === current || f.contains(current); })) return false;
    if (!el.matches("a[href], button, input, select, textarea, [tabindex]")) el.setAttribute("tabindex", "-1");
    el.focus({ preventScroll: true });
    const block = opts.scroll === undefined ? "nearest" : opts.scroll;
    if (block) el.scrollIntoView({ behavior: reducedMotion.matches ? "auto" : "smooth", block: block });
    return document.activeElement === el;
  }

  window.AppShell = {
    current: function () { return currentId; },
    show: function (id) { if (known(id)) window.location.hash = id; },
    onShow: function (id, fn) { if (known(id)) (handlers.show[id] = handlers.show[id] || []).push(fn); },
    onHide: function (id, fn) { if (known(id)) (handlers.hide[id] = handlers.hide[id] || []).push(fn); },
    work: work,
    ui: { setButtonBusy: setButtonBusy, focusResult: focusResult },
  };

  showTab(idFromHash() || firstId);
})();
