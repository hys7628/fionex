// 홈 탭 스크립트. 이 탭 패널 내부만 다룹니다. 공통 API 사용법: docs/design_system.md
(function () {
  "use strict";

  const FEATURE_ID = "home";
  const panel = document.querySelector('[data-feature-panel="' + FEATURE_ID + '"]');
  if (!panel) return;

  // 기능 개발 단계에서 구현.
  // - 입력 변경은 공통 shell이 자동 감지합니다.
  // - 결과 생성 후 AppShell.work.setResult(FEATURE_ID, true)
  // - PDF Blob 다운로드는 AppShell.work.downloadBlob(FEATURE_ID, blob, "파일명.pdf")
  // - 탭을 다시 열 때 생성 API를 재호출하지 않습니다(결과 DOM이 그대로 유지됨).

  /* ---------- 바이어 시간 ---------- */
  // 시각은 IANA 시간대 + Intl.DateTimeFormat으로 구합니다. 고정 시차를 쓰지 않습니다.
  // 업무시간 09:00~18:00은 확정되지 않은 가정값입니다(화면에 "가정"으로 표시).
  const SEOUL_TZ = "Asia/Seoul";
  const WORK_START_HOUR = 9;
  const WORK_END_HOUR = 18;
  const NEXT_START_SEARCH_DAYS = 31;
  const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];
  // 현지 시각의 색(tone) + 작은 글자(text) + 화면낭독용 이유(detail). 색만으로 구분하지 않습니다.
  const STATUS = {
    holiday: { text: "연락 어려움", detail: "공휴일", tone: "home-status-danger" },
    weekend: { text: "연락 어려움", detail: "주말", tone: "home-status-warning" },
    work: { text: "연락 가능", detail: "업무시간", tone: "home-status-success" },
    off: { text: "연락 어려움", detail: "업무시간 외", tone: "home-status-warning" },
  };

  const citySelect = panel.querySelector("#home-city");
  const el = {
    seoul: panel.querySelector("#home-seoul-time"),
    brazil: panel.querySelector("#home-brazil-time"),
    city: panel.querySelector("#home-brazil-city"),
    date: panel.querySelector("#home-brazil-date"),
    clock: panel.querySelector("#home-clock"),
    status: panel.querySelector("#home-status"),
    statusDetail: panel.querySelector("#home-status-detail"),
    nextRow: panel.querySelector("#home-next-row"),
    next: panel.querySelector("#home-next-start"),
    nextLocal: panel.querySelector("#home-next-local"),
    holiday: panel.querySelector("#home-holiday"),
    source: panel.querySelector("#home-holiday-source"),
  };

  // 같은 내용이면 DOM을 건드리지 않아 화면낭독기 반복 안내를 줄입니다.
  function setText(node, text) {
    if (node.textContent !== text) node.textContent = text;
  }

  function setClass(node, className) {
    if (node.className !== className) node.className = className;
  }

  /* 날짜 계산. day = {year, month, day}는 시간대와 무관한 달력 날짜입니다. */
  const formatters = new Map();

  function partsIn(instant, timeZone) {
    let fmt = formatters.get(timeZone);
    if (!fmt) {
      fmt = new Intl.DateTimeFormat("en-US", {
        timeZone: timeZone,
        year: "numeric", month: "numeric", day: "numeric",
        hour: "numeric", minute: "numeric", hourCycle: "h23",
      });
      formatters.set(timeZone, fmt);
    }
    const p = {};
    fmt.formatToParts(instant).forEach(function (part) {
      if (part.type !== "literal") p[part.type] = Number(part.value);
    });
    return { year: p.year, month: p.month, day: p.day, hour: p.hour % 24, minute: p.minute };
  }

  function addDays(day, n) {
    const d = new Date(Date.UTC(day.year, day.month - 1, day.day + n));
    return { year: d.getUTCFullYear(), month: d.getUTCMonth() + 1, day: d.getUTCDate() };
  }

  function weekday(day) {
    return new Date(Date.UTC(day.year, day.month - 1, day.day)).getUTCDay();
  }

  function isWeekend(day) {
    const w = weekday(day);
    return w === 0 || w === 6;
  }

  function dayKey(day) {
    return day.year + "-" + String(day.month).padStart(2, "0") + "-" + String(day.day).padStart(2, "0");
  }

  function pad2(n) {
    return String(n).padStart(2, "0");
  }

  // 10/25(일) 00:10
  function formatDayTime(p) {
    return p.month + "/" + p.day + "(" + WEEKDAYS[weekday(p)] + ") " + pad2(p.hour) + ":" + pad2(p.minute);
  }

  function formatDay(day) {
    return day.month + "/" + day.day + "(" + WEEKDAYS[weekday(day)] + ")";
  }

  // 현지 날짜·시각 → 실제 시점. 오프셋을 고정하지 않고, Intl로 후보 시점의 현지 시각을 확인해
  // 목표 시각과의 차이만큼 보정합니다(시간대 규칙·서머타임 변경 반영).
  function zonedTimeToInstant(day, hour, timeZone) {
    const target = Date.UTC(day.year, day.month - 1, day.day, hour, 0);
    let guess = target;
    for (let i = 0; i < 3; i++) {
      const p = partsIn(new Date(guess), timeZone);
      const diff = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute) - target;
      if (diff === 0) break;
      guess -= diff;
    }
    return new Date(guess);
  }

  /* 공휴일: 연도별로 서버(/api/home/holidays)에서 받아 페이지 메모리에만 둡니다. */
  // 연도 → { loading: true } | { source, fetchedAt, byDate: Map(날짜 → 이름) }
  const holidayYears = new Map();

  function ensureYear(year) {
    if (holidayYears.has(year)) return;
    holidayYears.set(year, { loading: true });
    fetch("/api/home/holidays?year=" + year)
      .then(function (res) { return res.json(); })
      .then(function (body) {
        if (!body.ok) throw new Error(body.error.message);
        const data = body.data;
        return {
          source: data.source,
          fetchedAt: data.fetched_at,
          byDate: new Map(data.holidays.map(function (h) { return [h.date, h.name]; })),
        };
      })
      .catch(function () {
        return { source: "none", fetchedAt: null, byDate: new Map() };
      })
      .then(function (entry) {
        holidayYears.set(year, entry);
        render();
      });
  }

  // 확인하지 못한 연도는 홈을 다시 열 때 재시도합니다.
  function forgetUnavailableYears() {
    holidayYears.forEach(function (entry, year) {
      if (entry.source === "none") holidayYears.delete(year);
    });
  }

  // { name: 공휴일 이름 또는 null, known: 그 연도 공휴일 자료를 확인했는지 }
  function lookupHoliday(day) {
    ensureYear(day.year);
    const entry = holidayYears.get(day.year);
    if (entry.loading || entry.source === "none") return { name: null, known: false };
    return { name: entry.byDate.get(dayKey(day)) || null, known: true };
  }

  function workStatus(day, hour) {
    if (lookupHoliday(day).name) return STATUS.holiday;
    if (isWeekend(day)) return STATUS.weekend;
    if (hour >= WORK_START_HOUR && hour < WORK_END_HOUR) return STATUS.work;
    return STATUS.off;
  }

  // 평일이며 국가 공휴일이 아닌 가장 가까운 날. 오늘 09:00 전이면 오늘부터 찾습니다.
  function nextWorkDay(today, hour) {
    let day = hour < WORK_START_HOUR ? today : addDays(today, 1);
    let allKnown = true;
    for (let i = 0; i < NEXT_START_SEARCH_DAYS; i++, day = addDays(day, 1)) {
      if (isWeekend(day)) continue;
      const holiday = lookupHoliday(day);
      if (!holiday.known) allKnown = false;
      if (!holiday.name) return { day: day, allKnown: allKnown };
    }
    return null;
  }

  // 다음 공휴일(PDF의 buyer_time.next_holiday와 같은 규칙): 기준 도시 현지 날짜 이후(오늘 포함) 가장 가까운 공휴일.
  // 올해 남은 공휴일이 없을 때만 다음 해 목록을 불러옵니다. 그 해 자료를 확인하지 못하면 추측하지 않습니다.
  // 반환 { day, name, days } | { loading: true } | null(확인 불가)
  function nextHoliday(today) {
    const todayKey = dayKey(today);
    for (let year = today.year; year <= today.year + 1; year++) {
      ensureYear(year);
      const entry = holidayYears.get(year);
      if (entry.loading) return { loading: true };
      if (entry.source === "none") return null;
      const key = Array.from(entry.byDate.keys()).filter(function (k) { return k >= todayKey; }).sort()[0];
      if (key) {
        const p = key.split("-").map(Number);
        const day = { year: p[0], month: p[1], day: p[2] };
        const days = Math.round((Date.UTC(p[0], p[1] - 1, p[2]) - Date.UTC(today.year, today.month - 1, today.day)) / 86400000);
        return { day: day, name: entry.byDate.get(key), days: days };
      }
    }
    return null;
  }

  // 11/2(월) Finados · D-8 / 오늘이면 D-DAY. 공휴일 이름은 BrasilAPI 원문 그대로(번역 없음).
  function nextHolidayText(holiday) {
    if (holiday === null) return "다음 공휴일 확인 불가";
    if (holiday.loading) return "확인 중";
    return formatDay(holiday.day) + " " + holiday.name + " · " + (holiday.days === 0 ? "D-DAY" : "D-" + holiday.days);
  }

  function renderSource(years) {
    const entries = years.map(function (y) { return holidayYears.get(y); });
    if (entries.some(function (e) { return e.loading; })) {
      setClass(el.source, "field-hint home-time-sub-line");
      setText(el.source, "공휴일 정보 확인 중");
    } else if (entries.some(function (e) { return e.source === "none"; })) {
      setClass(el.source, "notice notice-warning home-time-sub-line");
      setText(el.source, "공휴일 정보 확인 불가: 공휴일 없이 주말·업무시간만 판단합니다.");
    } else if (entries.some(function (e) { return e.source === "fallback"; })) {
      setClass(el.source, "notice notice-warning home-time-sub-line");
      setText(el.source, "공휴일 정보: 대체 자료 사용(BrasilAPI 조회 실패)");
    } else {
      const fetched = entries[0].fetchedAt ? " · " + formatDayTime(partsIn(new Date(entries[0].fetchedAt), SEOUL_TZ)) + " 조회" : "";
      // 출처 이름은 짧게(전체 안내는 출처 및 유의사항)
      setClass(el.source, "field-hint home-time-sub-line");
      setText(el.source, "BrasilAPI" + fetched);
    }
  }

  function render() {
    const now = new Date();
    const timeZone = citySelect.value;
    const local = partsIn(now, timeZone);
    const today = { year: local.year, month: local.month, day: local.day };

    setText(el.seoul, formatDayTime(partsIn(now, SEOUL_TZ)));
    setText(el.brazil, pad2(local.hour) + ":" + pad2(local.minute));
    setText(el.date, formatDay(today));
    setText(el.city, citySelect.selectedOptions[0].textContent);

    const status = workStatus(today, local.hour);
    if (holidayYears.get(today.year).loading) {
      setClass(el.clock, "home-clock");
      setText(el.status, "확인 중");
      setText(el.statusDetail, "");
    } else {
      setClass(el.clock, "home-clock " + status.tone);
      setText(el.status, status.text);
      setText(el.statusDetail, " (" + status.detail + ")");
    }

    if (status === STATUS.work) {
      el.nextRow.hidden = true;
    } else {
      const next = nextWorkDay(today, local.hour);
      if (next) {
        const start = zonedTimeToInstant(next.day, WORK_START_HOUR, timeZone);
        setText(el.next, formatDayTime(partsIn(start, SEOUL_TZ)) + " KST");
        setText(el.nextLocal, "현지 " + formatDay(next.day) + " " + pad2(WORK_START_HOUR) + ":00" +
          (next.allKnown ? "" : " · 공휴일 미반영"));
      } else {
        setText(el.next, "계산할 수 없음");
        setText(el.nextLocal, "");
      }
      el.nextRow.hidden = false;
    }

    setText(el.holiday, nextHolidayText(nextHoliday(today)));
    // 출처 줄은 올해 + (다음 공휴일·다음 업무일 계산으로 불러온 경우) 다음 해
    renderSource(holidayYears.has(today.year + 1) ? [today.year, today.year + 1] : [today.year]);
  }

  /* ---------- 업계 소식 ---------- */
  // 서버(/api/home/news)가 수집 경로별로 가져와 1시간 캐시합니다. 홈을 처음 열 때 한 번 요청하고,
  // 탭을 다시 열 때는 DOM이 유지되므로 다시 요청하지 않습니다. 외부 문자열은 textContent로만 넣습니다.
  const NEWS_ORIGINS = { kotra: "KOTRA", google: "Google News", abit: "ABIT" };
  const news = {
    body: panel.querySelector("#home-news-body"),
    sources: panel.querySelector("#home-news-sources"),
    notices: panel.querySelector("#home-news-notices"),
    loading: panel.querySelector("#home-news-loading"),
    summaryLoading: panel.querySelector("#home-news-summary-loading"),
    summaryStatus: panel.querySelector("#home-news-summary-status"),
    list: panel.querySelector("#home-news-list"),
    empty: panel.querySelector("#home-news-empty"),
    emptyText: panel.querySelector("#home-news-empty-text"),
    filter: panel.querySelector("#home-news-filter"),
    topics: panel.querySelector("#home-news-topics"),
    filterEmpty: panel.querySelector("#home-news-filter-empty"),
    moreRow: panel.querySelector("#home-news-more-row"),
    more: panel.querySelector("#home-news-more"),
  };
  // 매체·주제 필터는 이미 받은 목록을 화면에서만 거릅니다(추가 요청 없음).
  // Home 카드는 요약이라 4건만 보이고, '업계 소식 더 보기'는 같은 탭 안의 뉴스 상세 화면을 엽니다.
  const NEWS_PAGE_SIZE = 4;
  const newsView = { origin: "all", topic: "all" };
  // 마지막으로 받은 뉴스 목록·경로 상태(페이지 메모리에만). 카드와 상세 화면이 같이 씁니다.
  let newsItems = [];
  let newsMedia = null;
  // 주제 태그 순서(서버 service.NEWS_TOPIC_ORDER + "기타")와 같게 둡니다. 태그는 서버가 붙여 보냅니다.
  const NEWS_TOPICS = ["원사", "원단", "규제·무역", "리사이클·ESG", "패션·리테일", "기타"];
  let newsLoaded = false;
  let newsBusy = false;
  let summaryBusy = false;

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function formatKst(iso) {
    return formatDayTime(partsIn(new Date(iso), SEOUL_TZ));
  }

  // 날짜만 있는 항목(KOTRA)은 날짜만, 시각이 있으면 KST로 표시합니다.
  function formatNewsDate(value) {
    if (value.length === 10) {
      const p = value.split("-").map(Number);
      return formatDay({ year: p[0], month: p[1], day: p[2] });
    }
    return formatKst(value) + " KST";
  }

  function langLabel(lang) {
    if (!lang) return "";
    if (lang.indexOf("pt") === 0) return "포르투갈어";
    if (lang.indexOf("ko") === 0) return "한국어";
    return lang;
  }

  // 수집 경로 상태: ok 정상 / error 실패 / not_configured 설정 필요(KOTRA 인증키 없음)
  const SOURCE_STATES = {
    ok: { text: "정상", tone: "badge-success" },
    error: { text: "실패", tone: "badge-warning" },
    not_configured: { text: "설정 필요", tone: "badge-info" },
  };

  function renderNewsSources(media) {
    news.sources.replaceChildren.apply(news.sources, Object.keys(NEWS_ORIGINS).map(function (origin) {
      const info = media[origin];
      const state = SOURCE_STATES[info.status] || SOURCE_STATES.error;
      const li = make("li", "home-news-source");
      // 수집 → 필터 후 → 표시. KOTRA 0건이 응답 0건인지 필터 후 0건인지 화면에서 구분됩니다.
      const counts = info.collected == null ? info.count + "건"
        : "수집 " + info.collected + " · 필터 후 " + info.after_filter + " · 표시 " + info.count;
      li.append(
        make("span", "badge " + state.tone, NEWS_ORIGINS[origin] + " · " + state.text),
        make("span", "home-news-source-meta",
          info.fetched_at ? formatKst(info.fetched_at) + " 갱신 · " + counts : "수집 기록 없음"));
      return li;
    }));
  }

  // [전체 N] [KOTRA n] [Google News n] [ABIT n]. 건수는 주어진 목록 기준(경로 사이 중복 제외 후).
  // 실패·설정 필요 경로에는 ⚠와 화면낭독용 문구를 붙입니다. 재시도는 카드 안내의 버튼으로 합니다.
  function renderNewsFilter(items, media) {
    fillMediaTabs(news.filter, items, media, newsView.origin);
  }

  function fillMediaTabs(container, items, media, selected) {
    const counts = { all: items.length };
    items.forEach(function (item) { counts[item.origin] = (counts[item.origin] || 0) + 1; });
    const tabs = [{ key: "all", label: "전체" }].concat(Object.keys(NEWS_ORIGINS).map(function (origin) {
      return { key: origin, label: NEWS_ORIGINS[origin], status: media ? media[origin].status : "ok" };
    }));
    container.replaceChildren.apply(container, [make("span", "home-news-filter-label", "매체")].concat(tabs.map(function (tab) {
      const button = make("button", "home-news-tab");
      button.type = "button";
      button.dataset.newsFilter = tab.key;
      button.setAttribute("aria-pressed", String(selected === tab.key));
      button.append(make("span", "", tab.label), make("span", "home-news-tab-count", String(counts[tab.key] || 0)));
      if (tab.status && tab.status !== "ok") {
        const label = tab.status === "not_configured" ? "설정 필요" : "수집 실패";
        button.append(make("span", "home-news-tab-warn", "⚠"));
        button.lastChild.setAttribute("aria-hidden", "true");
        button.append(make("span", "visually-hidden", " (" + label + ")"));
        button.title = tab.label + " " + label;
      }
      return button;
    })));
    container.hidden = false;
  }

  // 주제 필터 [전체] [원사] … [기타]. 매체 필터와 함께 적용합니다(둘 다 맞는 기사만).
  function renderTopicFilter(items) {
    fillTopicTabs(news.topics, items, newsView.topic);
  }

  function fillTopicTabs(container, items, selected) {
    const counts = { all: items.length };
    items.forEach(function (item) {
      (item.tags || []).forEach(function (tag) { counts[tag] = (counts[tag] || 0) + 1; });
    });
    const keys = ["all"].concat(NEWS_TOPICS);
    container.replaceChildren.apply(container, [make("span", "home-news-filter-label", "주제")].concat(keys.map(function (key) {
      const button = make("button", "home-news-tab");
      button.type = "button";
      button.dataset.newsTopic = key;
      button.setAttribute("aria-pressed", String(selected === key));
      button.append(make("span", "", key === "all" ? "전체" : key), make("span", "home-news-tab-count", String(counts[key] || 0)));
      return button;
    })));
    container.hidden = false;
  }

  function matchesFilters(item, view) {
    return (view.origin === "all" || item.origin === view.origin) &&
      (view.topic === "all" || (item.tags || []).indexOf(view.topic) !== -1);
  }

  function applyNewsView() {
    const items = Array.prototype.slice.call(news.list.children);
    let matched = 0;
    items.forEach(function (li) {
      const match = (newsView.origin === "all" || li.dataset.origin === newsView.origin) &&
        (newsView.topic === "all" || li.dataset.tags.split("|").indexOf(newsView.topic) !== -1);
      li.hidden = !match || matched >= NEWS_PAGE_SIZE;
      if (match) matched += 1;
    });
    news.filterEmpty.hidden = items.length === 0 || matched > 0;
    // 상세 화면(전체 목록·검색)은 뉴스가 하나라도 있으면 열 수 있습니다.
    news.moreRow.hidden = items.length === 0;
    news.more.textContent = "업계 소식 더 보기 (전체 " + items.length + "건 · 검색)";
  }

  news.filter.addEventListener("click", function (event) {
    const button = event.target.closest("[data-news-filter]");
    if (!button) return;
    newsView.origin = button.dataset.newsFilter;
    news.filter.querySelectorAll("[data-news-filter]").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b === button));
    });
    applyNewsView();
  });

  news.topics.addEventListener("click", function (event) {
    const button = event.target.closest("[data-news-topic]");
    if (!button) return;
    newsView.topic = button.dataset.newsTopic;
    news.topics.querySelectorAll("[data-news-topic]").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b === button));
    });
    applyNewsView();
  });

  news.more.addEventListener("click", function () {
    openNewsDetail();
  });

  function renderNewsNotices(media) {
    news.notices.replaceChildren.apply(news.notices, Object.keys(NEWS_ORIGINS).filter(function (origin) {
      return media[origin].status !== "ok";
    }).map(function (origin) {
      const info = media[origin];
      const notConfigured = info.status === "not_configured";
      const notice = make("div", "notice " + (notConfigured ? "notice-info" : "notice-warning"));
      notice.append(make("p", "notice-title", NEWS_ORIGINS[origin] + (notConfigured ? " 설정 필요" : " 불러오기 실패")));
      notice.append(make("p", "", info.error.message +
        (info.stale ? " " + formatKst(info.fetched_at) + " 수집분을 계속 표시합니다." : "")));
      if (info.error.retryable) {
        const button = make("button", "btn btn-secondary", NEWS_ORIGINS[origin] + " 다시 시도");
        button.type = "button";
        button.dataset.newsRetry = origin;
        const row = make("div", "btn-row");
        row.append(button);
        notice.append(row);
      }
      return notice;
    }));
  }

  // 기사 하나: 제목(원문 링크) · AI 요약(있을 때) · 경로·주제 라벨·매체·날짜·언어. source가 있으면 작은 출처 구분 라벨.
  function newsItemNode(item, sourceLabel) {
    const li = make("li", "home-news-item");
    li.dataset.newsId = item.id;
    li.dataset.origin = item.origin;
    li.dataset.tags = (item.tags || []).join("|");
    const link = make("a", "home-news-link", item.title);
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    if (item.lang) link.lang = item.lang;
    link.append(make("span", "visually-hidden", " (새 탭에서 원문 열기)"));

    const meta = make("p", "home-news-meta");
    meta.append(make("span", "home-label", NEWS_ORIGINS[item.origin]));  // 분류 라벨은 회색(상태 색 아님)
    // 주제 태그(1~2개, 없으면 "기타")도 같은 회색 라벨. 화면낭독기에는 "주제"를 붙여 읽힙니다.
    (item.tags || []).forEach(function (tag) {
      const label = make("span", "home-label home-topic-label");
      label.append(make("span", "visually-hidden", "주제 "), document.createTextNode(tag));
      meta.append(label);
    });
    if (item.media) meta.append(make("span", "", item.media));
    const time = make("time", "", formatNewsDate(item.published_at));
    time.dateTime = item.published_at;
    meta.append(time);
    if (langLabel(item.lang)) meta.append(make("span", "", langLabel(item.lang)));

    if (sourceLabel) meta.prepend(make("span", "home-label home-search-label", sourceLabel));

    li.append(link);
    if (item.summary_ko) li.append(summaryNode(item.summary_ko));
    li.append(meta);
    return li;
  }

  function renderNewsList(items, media) {
    newsItems = items;
    newsMedia = media;
    news.list.replaceChildren.apply(news.list, items.map(function (item) { return newsItemNode(item); }));
    news.list.hidden = items.length === 0;
    news.empty.hidden = items.length > 0;
    renderNewsFilter(items, media);
    renderTopicFilter(items);
    applyNewsView();
    const allFailed = Object.keys(NEWS_ORIGINS).every(function (origin) { return media[origin].status !== "ok"; });
    news.emptyText.textContent = allFailed
      ? "모든 수집 경로에서 뉴스를 불러오지 못했습니다. 위 안내를 확인한 뒤 다시 시도하세요."
      : "수집 기간 안에 해당하는 소식이 없습니다.";
    if (!detail.view.hidden) renderDetail();
  }

  // 검증을 통과한 요약만 서버가 보내므로, 받은 항목에만 "AI 요약" 표시를 붙입니다.
  function summaryNode(text) {
    const p = make("p", "home-news-summary");
    p.append(make("span", "home-label", "AI 요약"));
    const body = make("span", "", text);
    body.lang = "ko";
    p.append(body);
    return p;
  }

  function applySummaries(summaries) {
    newsItems.forEach(function (item) {
      if (summaries[item.id]) item.summary_ko = summaries[item.id];
    });
    news.list.querySelectorAll(".home-news-item").forEach(function (li) {
      const text = summaries[li.dataset.newsId];
      if (!text || li.querySelector(".home-news-summary")) return;
      li.querySelector(".home-news-link").after(summaryNode(text));
    });
    if (!detail.view.hidden) renderDetail();
  }

  function setSummaryStatus(text) {
    news.summaryStatus.textContent = text;
    news.summaryStatus.hidden = !text;
  }

  // 목록을 먼저 보여 준 뒤 요약만 따로 요청합니다. 실패해도 목록은 그대로 둡니다.
  // 요약 요청 중 목록이 다시 그려지면(경로 재시도) 끝난 뒤 한 번 더 요청합니다.
  let summaryAgain = false;

  async function loadSummaries() {
    if (summaryBusy) {
      summaryAgain = true;
      return;
    }
    summaryBusy = true;
    summaryAgain = false;
    news.list.setAttribute("aria-busy", "true");
    news.summaryLoading.hidden = false;
    setSummaryStatus("");
    try {
      const res = await fetch("/api/home/news/summaries", { method: "POST" });
      const body = await res.json();
      if (!body.ok) throw new Error(body.error.message);
      applySummaries(body.data.summaries);
      setSummaryStatus(body.data.status === "ok" ? "" : body.data.message);
    } catch (err) {
      setSummaryStatus("AI 요약을 만들지 못했습니다. 원문 제목만 표시합니다.");
    } finally {
      summaryBusy = false;
      news.list.setAttribute("aria-busy", "false");
      news.summaryLoading.hidden = true;
    }
    if (summaryAgain) loadSummaries();
  }

  function setNewsBusy(value) {
    newsBusy = value;
    news.body.setAttribute("aria-busy", value ? "true" : "false");
    news.loading.hidden = !value;
    news.notices.querySelectorAll("[data-news-retry]").forEach(function (b) { b.disabled = value; });
  }

  // 서버 자체에 닿지 못한 경우. 이미 보이는 목록은 지우지 않습니다.
  function showNewsRequestError() {
    const old = news.notices.querySelector("#home-news-request-error");
    if (old) old.remove();
    const notice = make("div", "notice notice-danger");
    notice.id = "home-news-request-error";
    notice.setAttribute("role", "alert");
    notice.append(make("p", "notice-title", "업계 소식 불러오기 실패"));
    notice.append(make("p", "", "서버에서 뉴스 목록을 받지 못했습니다. 잠시 후 다시 시도하세요."));
    const button = make("button", "btn btn-secondary", "업계 소식 다시 시도");
    button.type = "button";
    button.dataset.newsRetry = "";
    const row = make("div", "btn-row");
    row.append(button);
    notice.append(row);
    news.notices.prepend(notice);
    if (!newsLoaded) {
      news.emptyText.textContent = "뉴스 목록을 받지 못했습니다.";
      news.empty.hidden = false;
    }
  }

  async function loadNews(refresh) {
    if (newsBusy) return;
    setNewsBusy(true);
    try {
      const res = await fetch("/api/home/news" + (refresh ? "?refresh=" + encodeURIComponent(refresh) : ""));
      const body = await res.json();
      if (!body.ok) throw new Error(body.error.message);
      renderNewsSources(body.data.media);
      renderNewsNotices(body.data.media);
      renderNewsList(body.data.items, body.data.media);
      newsLoaded = true;
      if (body.data.summary && body.data.summary.pending > 0) loadSummaries();
    } catch (err) {
      showNewsRequestError();
    } finally {
      setNewsBusy(false);
    }
  }

  // 재시도 버튼은 다시 그려지므로, 같은 경로가 또 실패하면 그 버튼으로, 아니면 목록으로 초점을 옮깁니다.
  news.notices.addEventListener("click", function (event) {
    const button = event.target.closest("[data-news-retry]");
    if (!button || button.disabled) return;
    const origin = button.dataset.newsRetry;
    loadNews(origin || null).then(function () {
      const again = news.notices.querySelector('[data-news-retry="' + origin + '"]');
      if (again) again.focus();
      else if (!news.list.hidden) news.list.focus();
    });
  });

  /* ---------- 업계 소식 상세(같은 탭 안의 화면) ---------- */
  // Home 카드의 '업계 소식 더 보기'로 열고 '← 홈으로'로 닫습니다(새 메뉴·주소 없음, 페이지 이동 없음).
  // 1) 받은 뉴스(newsItems)에서 먼저 검색(제목·매체·매체 도메인·주제 태그·수집 경로, AI 요약 제외).
  // 2) 결과가 없을 때만 'Google News에서 검색' 버튼 → /api/home/news/search(사용자가 누를 때만).
  // 검색어·결과는 이 페이지 메모리에만 둡니다(저장소·서버 저장 없음).
  const NEWS_SEARCH_MIN_LENGTH = 2;  // 서버 service.NEWS_SEARCH_MIN_LENGTH와 같은 값
  const detail = {
    view: panel.querySelector("#home-news-detail"),
    layout: panel.querySelector(".home-layout"),
    back: panel.querySelector("#home-news-back"),
    title: panel.querySelector("#home-news-detail-title"),
    form: panel.querySelector("#home-news-search"),
    query: panel.querySelector("#home-news-query"),
    filter: panel.querySelector("#home-detail-filter"),
    topics: panel.querySelector("#home-detail-topics"),
    count: panel.querySelector("#home-detail-count"),
    list: panel.querySelector("#home-detail-list"),
    empty: panel.querySelector("#home-detail-empty"),
    external: panel.querySelector("#home-detail-external"),
    externalText: panel.querySelector("#home-detail-external-text"),
    externalButton: panel.querySelector("#home-detail-external-button"),
    externalStatus: panel.querySelector("#home-detail-external-status"),
    externalList: panel.querySelector("#home-detail-search-list"),
  };
  const detailView = { origin: "all", topic: "all", query: "" };
  // 마지막 Google News 검색 {query, status: busy|ok|error, items, message}
  let externalSearch = null;

  // 판정용 정규화: 악센트 제거·소문자(têxtil = textil). 화면 글자는 바꾸지 않습니다.
  function plain(text) {
    return String(text || "").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  function normalizeQuery(value) {
    return String(value || "").replace(/"/g, " ").split(/\s+/).filter(Boolean).join(" ");
  }

  // 검색어 낱말이 모두 들어 있는 기사(AND). 대상: 제목·매체·매체 도메인·주제 태그·수집 경로 이름.
  function matchesQuery(item, query) {
    const haystack = plain([item.title, item.media, item.media_domain, (item.tags || []).join(" "), NEWS_ORIGINS[item.origin]].join(" "));
    return plain(query).split(" ").every(function (word) { return haystack.indexOf(word) !== -1; });
  }

  function renderDetail() {
    const query = detailView.query;
    const base = query ? newsItems.filter(function (item) { return matchesQuery(item, query); }) : newsItems;
    const shown = base.filter(function (item) { return matchesFilters(item, detailView); });
    fillMediaTabs(detail.filter, base, newsMedia, detailView.origin);
    fillTopicTabs(detail.topics, base, detailView.topic);
    detail.list.replaceChildren.apply(detail.list, shown.map(function (item) { return newsItemNode(item); }));
    detail.list.hidden = shown.length === 0;
    detail.count.textContent = query ? "검색 결과 " + shown.length + "건" : "전체 " + shown.length + "건";
    const noData = newsItems.length === 0;
    detail.empty.hidden = !(noData || (base.length > 0 && shown.length === 0));
    detail.empty.textContent = noData ? "불러온 소식이 없습니다." : "선택한 조건에 해당하는 뉴스가 없습니다.";
    renderExternal(query, base.length);
  }

  // 받은 뉴스에서 찾지 못했을 때만 Google News 검색 안내·버튼·결과를 보입니다.
  function renderExternal(query, baseCount) {
    const show = Boolean(query) && baseCount === 0;
    detail.external.hidden = !show;
    if (!show) return;
    const tooShort = query.length < NEWS_SEARCH_MIN_LENGTH;
    const current = externalSearch && externalSearch.query === query ? externalSearch : null;
    detail.externalText.textContent = "현재 수집된 뉴스에서 결과를 찾지 못했습니다." +
      (tooShort ? " Google News 검색은 두 글자 이상 입력하세요." : "");
    detail.externalButton.disabled = tooShort || (current && current.status === "busy");
    detail.externalButton.textContent = current && current.status === "error" ? "Google News에서 다시 검색" : "Google News에서 검색";
    detail.externalButton.hidden = Boolean(current && current.status === "ok");
    detail.external.setAttribute("aria-busy", current && current.status === "busy" ? "true" : "false");
    let status = "";
    if (current && current.status === "busy") status = "검색 중...";
    else if (current && current.status === "error") status = current.message;
    detail.externalStatus.textContent = status;
    detail.externalStatus.className = current && current.status === "error" ? "notice notice-warning" : "field-hint";
    detail.externalStatus.hidden = !status;

    const items = current && current.status === "ok" ? current.items.filter(function (item) { return matchesFilters(item, detailView); }) : [];
    detail.externalList.replaceChildren.apply(detail.externalList, items.map(function (item) { return newsItemNode(item, "Google News 검색"); }));
    detail.externalList.hidden = !(current && current.status === "ok");
    if (current && current.status === "ok") {
      detail.externalStatus.className = "field-hint";
      detail.externalStatus.textContent = "Google News 검색 결과 " + items.length + "건" +
        (current.items.length === 0 ? " · 섬유 관련 기사로 확인된 결과가 없습니다." : "");
      detail.externalStatus.hidden = false;
    }
  }

  async function searchGoogleNews() {
    const query = detailView.query;
    if (query.length < NEWS_SEARCH_MIN_LENGTH) return;
    if (externalSearch && externalSearch.query === query && externalSearch.status !== "error") return;  // 같은 검색어 중복 요청 방지
    externalSearch = { query: query, status: "busy", items: [], message: "" };
    renderDetail();
    try {
      const res = await fetch("/api/home/news/search?q=" + encodeURIComponent(query));
      const body = await res.json();
      if (!body.ok) throw new Error(body.error.message);
      if (externalSearch.query === query) externalSearch = { query: query, status: "ok", items: body.data.items, message: "" };
    } catch (err) {
      if (externalSearch.query === query) {
        externalSearch = { query: query, status: "error", items: [], message: "Google News 검색 결과를 가져오지 못했습니다." };
      }
    }
    if (!detail.view.hidden) {
      renderDetail();
      // 검색 중 비활성·성공 후 숨김으로 버튼 초점이 사라지므로 결과 건수 문장(실패 시 다시 검색 버튼)으로 이어 줍니다.
      const ok = externalSearch && externalSearch.query === query && externalSearch.status === "ok";
      AppShell.ui.focusResult(ok ? detail.externalStatus : detail.externalButton, { scroll: "nearest", from: [detail.external] });
    }
  }

  function openNewsDetail() {
    detail.layout.hidden = true;
    detail.view.hidden = false;
    renderDetail();
    detail.title.focus({ preventScroll: true });
    detail.view.scrollIntoView({ block: "start" });
  }

  function closeNewsDetail() {
    detail.view.hidden = true;
    detail.layout.hidden = false;
    news.more.focus({ preventScroll: true });
    panel.querySelector("#home-news").scrollIntoView({ block: "start" });
  }

  detail.back.addEventListener("click", closeNewsDetail);
  detail.query.addEventListener("input", function () {
    detailView.query = normalizeQuery(detail.query.value);
    renderDetail();
  });
  detail.form.addEventListener("submit", function (event) {
    event.preventDefault();
    detailView.query = normalizeQuery(detail.query.value);
    renderDetail();
  });
  detail.externalButton.addEventListener("click", searchGoogleNews);
  detail.filter.addEventListener("click", function (event) {
    const button = event.target.closest("[data-news-filter]");
    if (!button) return;
    detailView.origin = button.dataset.newsFilter;
    renderDetail();
  });
  detail.topics.addEventListener("click", function (event) {
    const button = event.target.closest("[data-news-topic]");
    if (!button) return;
    detailView.topic = button.dataset.newsTopic;
    renderDetail();
  });

  function ensureNews() {
    if (!newsLoaded && !newsBusy) loadNews(null);
  }

  /* ---------- 환율 ---------- */
  // 서버(/api/home/fx)가 소스별로 조회·캐시합니다. 홈을 처음 열 때 한 번 요청하고, 탭을 다시 열 때는 요청하지 않습니다.
  // 숫자는 서버가 돌려준 공식 고시값만 표시합니다. 값이 없으면 "확인 불가"로 두고 숫자를 채우지 않습니다.
  const fxEl = {
    body: panel.querySelector("#home-fx-body"),
    loading: panel.querySelector("#home-fx-loading"),
    list: panel.querySelector("#home-fx-list"),
    notices: panel.querySelector("#home-fx-notices"),
  };
  const FX_DIGITS = { usd_krw: 2, usd_brl: 4, brl_krw: 2 };
  let fxLoaded = false;
  let fxBusy = false;

  function formatRate(value, digits) {
    return new Intl.NumberFormat("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
  }

  // 방향은 기호와 낱말로 함께 표시합니다(색으로만 구분하지 않음).
  function fxChangeText(info) {
    if (info.change_pct === null || info.change_pct === undefined || !info.previous) return "전일 대비: 비교 데이터 없음";
    const pct = info.change_pct;
    const direction = pct > 0 ? "▲ 상승" : pct < 0 ? "▼ 하락" : "– 변동 없음";
    return direction + " " + Math.abs(pct).toFixed(2) + "%";
  }

  // Home 요약 타일: 통화쌍 → 큰 숫자(+작은 단위) → 전일 대비 → 가장 작은 회색 한 줄(월/일 고시 · 짧은 출처).
  // 전체 출처명·고시일·직전 고시일은 타일 title로 두고, 자세한 설명은 '출처 및 유의사항'에 있습니다.
  // 값이 없으면 숫자 자리에 "확인 불가"/"계산 불가"만 둡니다.
  const FX_SHORT_SOURCES = { koreaexim: "한국수출입은행", bcb_ptax: "BCB PTAX" };

  // 2026-10-23 → 10/23 (Home 표시용, API 값은 그대로)
  function shortFxDate(value) {
    const p = value.split("-");
    return Number(p[1]) + "/" + Number(p[2]);
  }
  function fxTile(pair, value, unit, line, meta) {
    const li = make("li", "home-fx-tile");
    li.append(make("p", "home-fx-pair", pair));
    const valueLine = make("p", "home-fx-value");
    valueLine.append(make("span", "home-fx-number" + (unit ? "" : " home-fx-number-none"), value));
    if (unit) valueLine.append(make("span", "home-fx-unit", unit));
    li.append(valueLine);
    li.append(make("p", "home-fx-line", line));
    li.append(make("p", "home-fx-source", meta));
    return li;
  }

  function fxSourceTile(name, quote, info) {
    if (info.status !== "ok") {
      return fxTile(info.pair, "확인 불가", "", info.error.message, info.source_name);
    }
    const tile = fxTile(info.pair, formatRate(info.rate, FX_DIGITS[name]), quote, fxChangeText(info),
      shortFxDate(info.date) + " 고시 · " + (FX_SHORT_SOURCES[info.source] || info.source_name));
    tile.title = info.date + " 고시 · " + info.source_name + (info.previous ? " · 전일 대비: 직전 고시일 " + info.previous.date + " 대비" : "");
    return tile;
  }

  function derivedDateText(derived) {
    if (derived.usd_krw_date === derived.usd_brl_date) return shortFxDate(derived.usd_krw_date) + " 고시";
    return "KRW " + shortFxDate(derived.usd_krw_date) + " · BRL " + shortFxDate(derived.usd_brl_date) + " 고시";
  }

  function renderFx(data) {
    const derived = data.brl_krw;
    fxEl.list.replaceChildren(
      fxSourceTile("usd_krw", "KRW", data.usd_krw),
      fxSourceTile("usd_brl", "BRL", data.usd_brl),
      derived
        ? fxTile("BRL/KRW", formatRate(derived.rate, FX_DIGITS.brl_krw), "KRW",
          "USD 경유", derivedDateText(derived))
        : fxTile("BRL/KRW", "계산 불가", "", "USD/KRW와 USD/BRL이 모두 있어야 계산", "USD 경유 계산값")
    );
    fxEl.list.hidden = false;

    fxEl.notices.replaceChildren.apply(fxEl.notices, ["usd_krw", "usd_brl"].filter(function (name) {
      return data[name].status !== "ok";
    }).map(function (name) {
      const info = data[name];
      const notConfigured = info.status === "not_configured";
      const notice = make("div", "notice " + (notConfigured ? "notice-info" : "notice-warning"));
      notice.append(make("p", "notice-title", info.pair + (notConfigured ? " 설정 필요" : " 확인 불가")));
      notice.append(make("p", "", info.error.message));
      if (info.error.retryable) {
        const button = make("button", "btn btn-secondary", info.pair + " 다시 시도");
        button.type = "button";
        button.dataset.fxRetry = name;
        const row = make("div", "btn-row");
        row.append(button);
        notice.append(row);
      }
      return notice;
    }));
  }

  function setFxBusy(value) {
    fxBusy = value;
    fxEl.body.setAttribute("aria-busy", value ? "true" : "false");
    fxEl.loading.hidden = !value;
    fxEl.notices.querySelectorAll("[data-fx-retry]").forEach(function (b) { b.disabled = value; });
  }

  // 서버 자체에 닿지 못한 경우. 이미 보이는 값은 그대로 둡니다.
  function showFxRequestError() {
    const old = fxEl.notices.querySelector("#home-fx-request-error");
    if (old) old.remove();
    const notice = make("div", "notice notice-danger");
    notice.id = "home-fx-request-error";
    notice.setAttribute("role", "alert");
    notice.append(make("p", "notice-title", "환율 불러오기 실패"));
    notice.append(make("p", "", "서버에서 환율을 받지 못했습니다. 잠시 후 다시 시도하세요."));
    const button = make("button", "btn btn-secondary", "환율 다시 시도");
    button.type = "button";
    button.dataset.fxRetry = "";
    const row = make("div", "btn-row");
    row.append(button);
    notice.append(row);
    fxEl.notices.prepend(notice);
  }

  async function loadFx(refresh) {
    if (fxBusy) return;
    setFxBusy(true);
    try {
      const res = await fetch("/api/home/fx" + (refresh ? "?refresh=" + encodeURIComponent(refresh) : ""));
      const body = await res.json();
      if (!body.ok) throw new Error(body.error.message);
      renderFx(body.data);
      fxLoaded = true;
    } catch (err) {
      showFxRequestError();
    } finally {
      setFxBusy(false);
    }
  }

  fxEl.notices.addEventListener("click", function (event) {
    const button = event.target.closest("[data-fx-retry]");
    if (!button || button.disabled) return;
    const name = button.dataset.fxRetry;
    loadFx(name || null).then(function () {
      const again = fxEl.notices.querySelector('[data-fx-retry="' + name + '"]');
      if (again) again.focus();
      else if (!fxEl.list.hidden) fxEl.list.focus();
    });
  });

  function ensureFx() {
    if (!fxLoaded && !fxBusy) loadFx(null);
  }

  /* ---------- 다가오는 전시회(브라질·중남미) ---------- */
  // 서버(/api/home/fairs)가 정적 자료에서 다가오는 행사를 날짜순으로 줍니다. 홈을 처음 열 때 한 번 요청하고,
  // 지역 필터·브라질 최소 노출은 받은 목록에서만 계산합니다(추가 요청 없음).
  const fairsEl = {
    body: panel.querySelector("#home-fairs-body"),
    loading: panel.querySelector("#home-fairs-loading"),
    list: panel.querySelector("#home-fairs-list"),
    empty: panel.querySelector("#home-fairs-empty"),
    notices: panel.querySelector("#home-fairs-notices"),
    hint: panel.querySelector("#home-fairs-hint"),
    foot: panel.querySelector("#home-fairs-foot"),
    filter: panel.querySelector("#home-fairs-filter"),
    filterEmpty: panel.querySelector("#home-fairs-filter-empty"),
  };
  const FAIR_REGIONS = { all: "전체", brazil: "브라질", latin_america: "중남미" };
  const FAIR_PAGE_SIZE = 3;
  // 가정값: '전체'에서 브라질 행사 최소 건수(있는 만큼만). 서버 fairs.MIN_BRAZIL_IN_ALL(PDF)과 같은 값입니다.
  const FAIR_MIN_BRAZIL_IN_ALL = 2;
  const fairsView = { region: "all", fairs: [] };
  // D-day 칸: 다가오는 행사는 기본 글자색, 오늘·진행 중만 상태 색
  const FAIR_DAY_TONES = { upcoming: "", today: " home-fair-dday-today", ongoing: " home-fair-dday-ongoing" };
  let fairsLoaded = false;
  let fairsBusy = false;

  function fairLine(label, value) {
    const p = make("p", "home-fair-line");
    p.append(make("span", "home-fair-label", label), make("span", "", value || "미확인"));
    return p;
  }

  // 2027-04-27 ~ 2027-04-30 → 2027.04.27–04.30 (해가 다르면 두 날짜 모두 전체)
  function fairPeriod(start, end) {
    const dot = function (value) { return value.replace(/-/g, "."); };
    if (start === end) return dot(start);
    if (start.slice(0, 4) === end.slice(0, 4)) return dot(start) + "–" + dot(end.slice(5));
    return dot(start) + "–" + dot(end);
  }

  function fairItem(fair) {
    const li = make("li", "home-fair-item");
    li.append(make("p", "home-fair-dday" + (FAIR_DAY_TONES[fair.status] || ""), fair.d_day));
    const main = make("div", "home-fair-main");
    main.append(make("p", "home-fair-name", fair.name));
    // D-day → 행사명 → 국가·도시 → 기간 순으로 읽힙니다.
    main.append(make("p", "home-fair-place", [fair.country, fair.city].filter(Boolean).join(" · ")));
    const when = make("p", "home-fair-when");
    const period = make("time", "", fairPeriod(fair.start, fair.end));
    period.dateTime = fair.start;
    when.append(period);
    main.append(when);
    // [확인 필요] [상세 정보]를 한 줄에. 펼치면 상세 내용이 그 아래에 나옵니다.
    const tags = make("div", "home-fair-tags");
    if (!fair.verified) tags.append(make("span", "badge badge-warning", "확인 필요"));

    // 장소·분야·확인 상태·메모·출처는 지우지 않고 접기 영역으로 옮깁니다.
    const details = make("details", "home-fair-details");
    details.append(make("summary", "", "상세 정보"));
    details.append(fairLine("기간", fair.start === fair.end ? fair.start : fair.start + " ~ " + fair.end));
    details.append(fairLine("장소", [fair.country, fair.city, fair.venue].filter(Boolean).join(" · ")));
    details.append(fairLine("분야", fair.focus));
    const check = make("p", "home-fair-line");
    check.append(make("span", "home-fair-label", "확인"),
      make("span", "", (fair.verified ? "공식 사이트 확인" : "확인 필요") + " · " + fair.checked_at + " 확인"));
    details.append(check);
    if (fair.note) details.append(make("p", "home-fair-note", fair.note));
    const link = make("a", "home-fair-link", "출처: " + fair.source);
    link.href = fair.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.append(make("span", "visually-hidden", " (새 탭에서 열기)"));
    details.append(link);
    tags.append(details);
    main.append(tags);
    li.append(main);
    return li;
  }

  // '전체': 브라질 행사를 앞에서부터 최소 건수만큼 먼저 넣고 나머지를 날짜순으로 채운 뒤 날짜순으로(서버 select_for_all과 같은 규칙).
  function selectForAll(fairs, limit, minBrazil) {
    const chosen = fairs.filter(function (f) { return f.region === "brazil"; }).slice(0, Math.min(minBrazil, limit));
    fairs.forEach(function (f) { if (chosen.length < limit && chosen.indexOf(f) === -1) chosen.push(f); });
    return chosen.sort(function (a, b) { return fairs.indexOf(a) - fairs.indexOf(b); });
  }

  function renderFairsFilter() {
    const counts = { all: fairsView.fairs.length };
    fairsView.fairs.forEach(function (f) { counts[f.region] = (counts[f.region] || 0) + 1; });
    fairsEl.filter.replaceChildren.apply(fairsEl.filter, Object.keys(FAIR_REGIONS).map(function (key) {
      const button = make("button", "home-news-tab");
      button.type = "button";
      button.dataset.fairsRegion = key;
      button.setAttribute("aria-pressed", String(fairsView.region === key));
      button.append(make("span", "", FAIR_REGIONS[key]), make("span", "home-news-tab-count", String(counts[key] || 0)));
      return button;
    }));
    fairsEl.filter.hidden = fairsView.fairs.length === 0;
  }

  function applyFairsView() {
    const all = fairsView.fairs;
    const shown = fairsView.region === "all"
      ? selectForAll(all, FAIR_PAGE_SIZE, FAIR_MIN_BRAZIL_IN_ALL)
      : all.filter(function (f) { return f.region === fairsView.region; }).slice(0, FAIR_PAGE_SIZE);
    fairsEl.list.replaceChildren.apply(fairsEl.list, shown.map(fairItem));
    fairsEl.list.hidden = shown.length === 0;
    fairsEl.empty.hidden = all.length > 0;
    fairsEl.filterEmpty.hidden = all.length === 0 || shown.length > 0;
  }

  fairsEl.filter.addEventListener("click", function (event) {
    const button = event.target.closest("[data-fairs-region]");
    if (!button) return;
    fairsView.region = button.dataset.fairsRegion;
    fairsEl.filter.querySelectorAll("[data-fairs-region]").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b === button));
    });
    applyFairsView();
  });

  function renderFairs(data) {
    fairsView.fairs = data.fairs;
    renderFairsFilter();
    applyFairsView();
    fairsEl.notices.replaceChildren();
    if (data.invalid_count > 0) {
      const notice = make("div", "notice notice-warning");
      notice.append(make("p", "notice-title", "일부 일정 제외"),
        make("p", "", "형식이 맞지 않거나 출처가 없는 항목 " + data.invalid_count + "건은 표시하지 않았습니다."));
      fairsEl.notices.append(notice);
    }
    if (data.data_checked_at) {
      fairsEl.foot.textContent = "자료 확인일 " + data.data_checked_at + " · 방문 전 출처에서 다시 확인하세요.";
      fairsEl.hint.textContent = "담당자가 출처를 확인해 넣은 자료입니다(자동 수집 아님, 자료 확인일 " + data.data_checked_at +
        "). 일정은 바뀔 수 있으니 방문 전 출처에서 다시 확인하세요. D-day는 서울 날짜 기준입니다.";
    }
  }

  function showFairsError() {
    fairsEl.list.hidden = true;
    fairsEl.empty.hidden = true;
    fairsEl.filter.hidden = true;
    fairsEl.filterEmpty.hidden = true;
    const notice = make("div", "notice notice-warning");
    notice.setAttribute("role", "status");
    notice.append(make("p", "notice-title", "일정 확인 불가"),
      make("p", "", "전시회 일정 자료를 확인할 수 없습니다. 다른 홈 기능은 그대로 사용할 수 있습니다."));
    const button = make("button", "btn btn-secondary", "전시회 일정 다시 시도");
    button.type = "button";
    button.dataset.fairsRetry = "";
    const row = make("div", "btn-row");
    row.append(button);
    notice.append(row);
    fairsEl.notices.replaceChildren(notice);
  }

  async function loadFairs() {
    if (fairsBusy) return;
    fairsBusy = true;
    fairsEl.body.setAttribute("aria-busy", "true");
    fairsEl.loading.hidden = false;
    fairsEl.notices.querySelectorAll("[data-fairs-retry]").forEach(function (b) { b.disabled = true; });
    try {
      const res = await fetch("/api/home/fairs?limit=20");  // 필터용으로 다가오는 행사 전체(최대 20)
      const body = await res.json();
      if (!body.ok) throw new Error(body.error.message);
      renderFairs(body.data);
      fairsLoaded = true;
    } catch (err) {
      showFairsError();
    } finally {
      fairsBusy = false;
      fairsEl.body.setAttribute("aria-busy", "false");
      fairsEl.loading.hidden = true;
    }
  }

  fairsEl.notices.addEventListener("click", function (event) {
    const button = event.target.closest("[data-fairs-retry]");
    if (!button || button.disabled) return;
    loadFairs().then(function () {
      const again = fairsEl.notices.querySelector("[data-fairs-retry]");
      if (again) again.focus();
      else if (!fairsEl.list.hidden) fairsEl.list.focus();
    });
  });

  function ensureFairs() {
    if (!fairsLoaded && !fairsBusy) loadFairs();
  }

  /* ---------- 일일 브리핑 PDF ---------- */
  // 서버가 그 시점의 홈 데이터로 PDF를 만들어 돌려줍니다. 기준 도시만 함께 보냅니다.
  // 다운로드는 fetch → Blob → AppShell.work.downloadBlob(페이지 이동 없음, 저장 성공 여부는 브라우저 몫).
  const reportEl = {
    body: panel.querySelector("#home-report-body"),
    button: panel.querySelector("#home-report-button"),
    status: panel.querySelector("#home-report-status"),
    notices: panel.querySelector("#home-report-notices"),
    city: panel.querySelector("#home-report-city"),
  };
  let reportBusy = false;
  // 성공 안내는 버튼 옆에 잠깐만 보여 줍니다. 오류 안내는 다시 누를 때까지 그대로 둡니다.
  const REPORT_STATUS_SECONDS = 4;
  let reportStatusTimer = null;

  function reportFilename(res) {
    const match = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") || "");
    return match ? match[1] : "fionex_daily_briefing.pdf";
  }

  function showReportError(message) {
    const notice = make("div", "notice notice-danger");
    notice.setAttribute("role", "alert");
    notice.append(make("p", "notice-title", "PDF를 만들지 못했습니다"),
      make("p", "", message + " 버튼을 다시 눌러 시도할 수 있습니다."));
    reportEl.notices.replaceChildren(notice);
  }

  async function downloadReport() {
    if (reportBusy) return;
    reportBusy = true;
    reportEl.button.disabled = true;
    AppShell.ui.setButtonBusy(reportEl.button, "PDF 준비 중...");
    reportEl.body.setAttribute("aria-busy", "true");
    clearTimeout(reportStatusTimer);
    reportEl.status.hidden = true;
    reportEl.notices.replaceChildren();
    try {
      const res = await fetch("/api/home/report/daily.pdf?city=" + encodeURIComponent(citySelect.value));
      if (!res.ok || (res.headers.get("Content-Type") || "").indexOf("application/pdf") !== 0) {
        let message = "서버에서 PDF를 받지 못했습니다.";
        try { message = (await res.json()).error.message || message; } catch (err) { /* JSON 아님 */ }
        const error = new Error(message);
        error.fromServer = true;
        throw error;
      }
      const blob = await res.blob();
      AppShell.work.downloadBlob(FEATURE_ID, blob, reportFilename(res));
      reportEl.status.textContent = "다운로드를 요청했습니다.";
      reportEl.status.hidden = false;
      reportStatusTimer = setTimeout(function () { reportEl.status.hidden = true; }, REPORT_STATUS_SECONDS * 1000);
    } catch (err) {
      // 네트워크 오류 원문(브라우저 영어 문구 등)은 보여 주지 않고 서버가 준 고정 문장만 씁니다.
      showReportError(err.fromServer ? err.message : "서버에 연결하지 못했습니다.");
    } finally {
      reportBusy = false;
      reportEl.button.disabled = false;
      AppShell.ui.setButtonBusy(reportEl.button, null);
      reportEl.body.setAttribute("aria-busy", "false");
    }
  }

  reportEl.button.addEventListener("click", downloadReport);
  citySelect.addEventListener("change", function () {
    setText(reportEl.city, citySelect.selectedOptions[0].textContent);
  });

  // 화면에 분 단위까지만 표시하므로 매 분 경계에 한 번 갱신합니다. 홈이 숨겨지면 멈춥니다.
  let timer = null;

  function tick() {
    render();
    clearTimeout(timer);
    timer = setTimeout(tick, 60000 - (Date.now() % 60000) + 50);
  }

  function stop() {
    clearTimeout(timer);
    timer = null;
  }

  citySelect.addEventListener("change", render);

  // 백그라운드 탭에서는 타이머가 지연될 수 있어 다시 보일 때 즉시 갱신합니다.
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden && timer !== null) tick();
  });

  AppShell.onShow(FEATURE_ID, function () {
    forgetUnavailableYears();
    tick();
    ensureFx();
    ensureNews();
    ensureFairs();
  });
  AppShell.onHide(FEATURE_ID, stop);
  if (AppShell.current() === FEATURE_ID) {
    tick();
    ensureFx();
    ensureNews();
    ensureFairs();
  }
})();
