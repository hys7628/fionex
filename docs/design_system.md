# 공통 UI 기준

2026-10-24 공통 UI 적용, 2026-10-26 블루·아쿠아·민트 대시보드 톤으로 정리(홍은주, feature/common_setup). 참고 이미지: resources/design/dashboard_reference.png
이미지에서는 색감(흰 카드·옅은 블루그레이 배경·블루·아쿠아·민트 포인트·네이비 숫자), 카드 질감(얇은 테두리·은은한 그림자), 버튼, 상태 표현, 인터랙션 분위기만 참고했다. 배치는 복제하지 않는다.
이미지 속 이름·로고·슬로건·메뉴·수치·차트는 사용하지 않는다. 이미지를 배경으로 붙이지 않고 HTML/CSS로 구성한다.
서비스명은 `fionex`(2026-10-24 확정, common/config.py의 SERVICE_NAME). 화면과 브라우저 제목은 이 값을 사용한다.
로그인·프로필·계정 메뉴는 두지 않는다. 웹폰트 사용권이 미정이라 시스템 글꼴을 쓴다.

## 화면 구조
```
┌ 사이드바(248px) ┬ 본문 (최대 1440px, 좁으면 유동 폭) ─────────┐
│ fionex          │ ┌ 머리글: 탭 제목 · 짧은 설명 · 작업 상태 ┐ │
│ 홈              │ └─────────────────────────────────────────┘ │
│ 시장 분석       │ ┌ 입력 카드 ─────┐ ┌ 결과 카드 ──────────┐ │
│ 제품소개서      │ │                │ │ 빈 상태 안내        │ │
│ 그린 클레임 체크│ └────────────────┘ └─────────────────────┘ │
│ 홍보 스튜디오   │                                              │
└─────────────────┴──────────────────────────────────────────────┘
```
- templates/base.html: 사이드바, 탭별 `<section data-feature-panel="기능id">`, 공통 머리글. 각 탭 작업 영역은 `features/<기능>/templates/<기능>/panel.html`을 include.
- 메뉴 이름·탭 제목·설명은 각 `features/<기능>/routes.py`의 `FEATURE`에서 관리. 순서는 app.py `FEATURE_MODULES`.
- 반응형 기준: 960px 미만은 사이드바를 접고 상단 메뉴 버튼으로 연다. 1100px 이상에서 `.workspace`가 입력·결과 2열, 미만은 세로 배치.
- 미구현 기능은 빈 상태(`.empty-state`)로 안내한다. 실제 뉴스·통계·AI 결과를 꾸며 넣지 않는다.
- 기능이 없는 생성·다운로드 버튼은 `disabled`(점선·회색)로 두고 옆에 "준비 중" 안내를 붙인다.
- 현재 패널의 입력 항목은 공통 UI 확인용 예시다. 담당자가 feature_spec 확정 후 교체한다.

## CSS 파일 역할
| 파일 | 내용 | 규칙 |
|---|---|---|
| static/css/tokens.css | 색상·글꼴·간격·모서리·그림자·움직임·레이아웃 변수 | 디자인 값의 단일 원본. 값 변경은 공통 합의 후 |
| static/css/common.css | 기본 요소, 앱 shell, 머리글, 카드, 배치, 입력, 버튼, 표, 상태 안내, 움직임 | 전역 요소(body, button, input…) 기본값은 여기서만. 색 hex를 직접 쓰지 않고 토큰만 사용 |
| features/<기능>/static/<기능>.css | 해당 탭 내부 전용 스타일 | 선택자를 `.feature-<기능id>` 안으로 한정 |

탭 CSS 규칙
- 공통 클래스를 복제하지 말고 그대로 쓴다. 공통에 없는 것만 탭 CSS에 추가한다.
- `body`, `button`, `.btn`, `.card` 같은 전역·공통 선택자를 탭 CSS에서 덮어쓰지 않는다.
- 색·간격은 `var(--...)` 토큰만 사용한다. 새 색이 필요하면 tokens.css 추가를 공통 담당과 합의한다.
- 여러 탭에서 필요한 스타일은 common.css 추가를 제안한다.

```css
/* features/green_claim/static/green_claim.css */
.feature-green_claim .claim-list { display: flex; flex-direction: column; gap: var(--space-3); }
.feature-green_claim .claim-risk { color: var(--color-danger); }
```

## 팔레트와 분위기
밝고 깨끗한 B2B SaaS 대시보드. 흰 면 + 아주 옅은 블루그레이 배경, 블루(주요 동작)·아쿠아(보조 빛)·민트(친환경 강조) 포인트, 제목·숫자는 딥 네이비.
피한다: 진한 회색 배경, 강한 royal blue, 네온, 과한 그라데이션·glassmorphism, 카드마다 다른 모서리·그림자, 두꺼운 테두리, 모바일 앱처럼 둥근 UI.

| 역할 | 값 | 변수 |
|---|---|---|
| 페이지 배경 | #f3f6fa + 모서리 radial 빛(아쿠아 7%·블루 5%) | `--color-bg`, `--color-bg-gradient` |
| 면 | #ffffff / 옅은 면 #f6f8fb / hover #f0f5fb / 표 행 hover #f6f9fe | `--color-surface`, `--color-surface-muted`, `--color-surface-hover`, `--color-row-hover` |
| 띄운 면(elevated) | 흰 면 + 그림자 단계로 표현(별도 색 없음) | `--color-surface` + `--shadow-md`/`--shadow-lg` |
| 머리글 | 블루→아쿠아→민트 아주 옅은 그라데이션 | `--color-hero-gradient` |
| 블루 | #1d6ad4 (흰 글자 5.2:1), 누름 #1663c4, soft #eaf2fd, 글자 #1559b8 (6.7:1) | `--color-primary`, `-hover`, `-soft`, `-text` |
| 주 버튼 | #1d6ad4 → #1677c4 (끝 색도 흰 글자 4.7:1) | `--color-primary-gradient` |
| 아쿠아 | #22b8cf 장식 전용, soft #e5f6f9, 글자 #0c7a8a (5.0:1) | `--color-aqua`, `-soft`, `-text` |
| 민트 | #23b39b 장식 전용, soft #e6f6f2, 글자 #0a7262 | `--color-accent`, `-soft`, `-text` |
| 네이비 글자 | #13233f (15.7:1) | `--color-text` |
| 보조 글자 | #54637a (흰 6.1:1, 배경 5.6:1), placeholder #64738a | `--color-text-muted`, `--color-text-placeholder` |
| 선 | 카드·표 행 #e7ecf3 / 구분선 #e2e8f0 / 점선·보조 버튼 #c3cedc / 입력 #7b8aa1 (3.5:1) | `--color-border-subtle`, `--color-border`, `--color-border-strong`, `--color-border-control` |
| 상태 | info #1559b8 · success #0a7262 · warning #8f4b00 · danger #b42318, 각 `-soft` 배경·`-border` 테두리 (글자/soft 5:1 이상) | `--color-info/success/warning/danger` + `-soft`, `-border` |
| 분류 라벨 | 배경 #eef2f7, 글자 #47566e (6.6:1), 테두리 #dde4ee | `--color-neutral-soft`, `-text`, `-border` |
| 덮개 | 모바일 메뉴 뒤 rgba(19,35,63,.35) | `--color-overlay` |

대비 수치는 tokens.css 값으로 WCAG 공식 계산한 값이다. 그라데이션 배경 위 보조 글자는 5:1 이상. 아쿠아·민트 원색은 글자에 쓰지 않는다(`-text` 사용).

## 주요 토큰
| 분류 | 변수 |
|---|---|
| 간격 | `--space-1`(4px) ~ `--space-12`(48px) |
| 모서리 | `--radius-sm` 8(입력·안내·작은 요소) / `--radius-md` 10(버튼·메뉴·표 틀·빈 상태) / `--radius-lg` 16(카드·머리글) / `--radius-pill`(배지·상태 칩만) |
| 그림자 | `--shadow-sm`(머리글·보조 버튼), `--shadow-md`(카드), `--shadow-hover`(누를 수 있는 카드 hover), `--shadow-lg`(모바일 메뉴·팝오버), `--shadow-primary`/`-hover`(주 버튼) |
| 초점 | `--focus-ring`(흰 틈 + 블루 2px), `--focus-halo`(입력칸 옅은 블루 3px 링) |
| 글꼴 | `--font-sans`, `--font-size-xs` ~ `--font-size-2xl`, `--font-weight-regular/medium/semibold/bold` |
| 움직임 | `--transition-fast` 150ms, `--transition-base` 200ms, `--duration-enter` 220ms, `--ease-out` |

## 글자 위계
| 단계 | 크기·굵기 | 색 |
|---|---|---|
| 탭 제목 `.page-title` | 2xl(28px, 960px 미만 xl) · bold · 자간 -0.02em | `--color-text` |
| 카드 제목 `.card-title` | lg(18px) · bold | `--color-text` |
| 본문 | md(16px) · regular · 줄 간격 1.6 | `--color-text` |
| 설명·메타 `.card-description`, `.page-description` | sm(14px) | `--color-text-muted` |
| 입력 이름 `.field-label` | sm · bold | `--color-text` |
| 안내·표 머리 `.field-hint`, `.table th` | xs(12px) | `--color-text-muted` |
| 숫자 데이터 | 기능별 크기, `.num`/`.tabular-nums`(tabular-nums), 표 숫자 칸 medium | `--color-text` |

시간·환율·금액·KPI·D-day·퍼센트는 `font-variant-numeric: tabular-nums`로 자릿수를 맞추고 설명보다 크게·진하게 둔다.

## 공통 컴포넌트
| 용도 | 클래스 |
|---|---|
| 카드 | `.card` > `.card-header` > `.card-title`, `.card-description` |
| 배치 | `.workspace`(입력·결과 2열), `.grid`(카드 자동 열), `.stack`(세로 간격) |
| 입력 | `.field` > `.field-label` + `.input` / `.select` / `.textarea` / `.file-input` + `.field-hint` / `.field-error`, 필수 표시 `.field-required`, 묶음 `.fieldset` + `legend.field-label`, 선택지 `.choice` |
| 버튼 | `.btn` + `.btn-primary` / `.btn-secondary` / `.btn-ghost` / `.btn-icon`, 묶음 `.btn-row` |
| 표 | `.table-wrap` > `table.table` (`caption`에 출처·단위, 숫자 칸 `.num`) |
| 상태 | `.empty-state`(+`.empty-state-title`), `.notice.notice-info/-success/-warning/-danger`(+`.notice-title`), `.badge.badge-info/-success/-warning/-danger`, `.spinner` |
| 분류 라벨 | `.badge`(기본)·`.badge-neutral`(점 없음), `.tag`(작은 사각 라벨) |
| 숫자 | `.num`, `.tabular-nums` |
| 누를 수 있는 카드 | `.card.card-interactive` 또는 `a.card` |
| 접근성 | `.visually-hidden` |

### 컴포넌트 규칙 (2026-10-26)
- **카드**: 흰 면, 1px `--color-border-subtle`, `--radius-lg` 16px, `--shadow-md`, 안쪽 여백 24px(960px 미만 20px), 머리→본문 16px, 제목→설명 4px. 모든 카드에 움직임을 넣지 않는다. 누를 수 있는 카드만 `.card-interactive`로 hover 시 2px 상승·`--shadow-hover`·테두리 블루 tint.
- **머리글** `.page-header`: hero 그라데이션 + 옅은 테두리 + `--shadow-sm`, 여백 24px 32px(작은 화면 20px).
- **사이드바**: 흰 면 + 오른쪽 1px 옅은 선(그림자 없음). 메뉴 radius 10px, 기본 보조 글자색, hover `--color-surface-hover` + 아이콘 블루, 선택 `--color-primary-soft` 배경 + `--color-primary-text` 글자·아이콘 semibold. 폭 248px 유지.
- **버튼**: 높이 42px, radius 10px, 글자 sm bold.
  - primary: 블루 그라데이션 + 흰 글자 + `--shadow-primary`. hover는 색을 바꾸지 않고(대비 유지) 그림자 증가 + 1px 상승, 누름은 `--color-primary-hover`.
  - secondary: 흰 면 + `--color-border-strong` 테두리 + 블루 글자. hover 블루 테두리·soft 배경.
  - disabled: 점선 테두리 + 옅은 면 + 보조 글자(6.1:1, 읽힘), 그림자·이동 없음.
- **입력**: 높이 42px, radius 8px, 테두리 `--color-border-control`(3.5:1). hover 블루 테두리. 키보드 초점은 블루 테두리 + `--focus-halo` 링 + 투명 outline(고대비 모드에서 실제 선). 오류 `aria-invalid` 빨강 테두리(초점 시 빨강 옅은 링). disabled 옅은 면·보조 글자. placeholder `--color-text-placeholder`.
- **배지/라벨**: 상태(성공=민트그린, 주의=주황, 위험=빨강, 정보=블루)는 `.badge-*`(점 + soft 배경 + 얇은 테두리). Google·KOTRA·ABIT·AI 요약·원사·원단 같은 단순 분류는 `.badge-neutral`/`.tag`(블루그레이)를 쓰고 초록·주황·빨강을 쓰지 않는다.
- **안내** `.notice`: 옅은 tint 배경 + 1px 상태 테두리 + 왼쪽 3px 강조선, 여백 12px 16px, 제목은 상태 글자색·본문은 네이비. 아이콘 없이 제목 문장으로 뜻을 전달한다. 오류(`danger`)만 진한 tint를 쓰고 일반 안내는 옅게 둔다. 안의 버튼은 왼쪽 정렬.
- **표**: 틀 1px 옅은 선 + radius 10px, 머리 `--color-surface-muted`·xs 보조 글자, 행 구분 1px `--color-border-subtle`, 행 hover `--color-row-hover`, 숫자 칸 `.num` 오른쪽·tabular-nums·medium. 열 너비는 기능이 정한다.
- **빈 상태**: 점선 `--color-border-strong` + 옅은 면, radius 10px, 최소 높이 160px.
- **로딩**: `.spinner`(블루·아쿠아 테두리 회전) + 텍스트, 버튼 `disabled`, 영역 `aria-busy`.

### 움직임
- 대상: 버튼·카드·메뉴·필터 hover, 입력 초점, 상태 변화. 속성은 opacity·transform·background-color·border-color·box-shadow만, 150~220ms.
- 탭 진입: 패널이 보일 때 1회 opacity 0→1, translateY 5px→0, 220ms(`panel-enter`). 끝난 뒤 transform이 남지 않는다. 기능 코드는 애니메이션 종료를 기다리지 않는다.
- 계속 움직이는 장식은 만들지 않는다(로딩 `.spinner`만 예외).
- `prefers-reduced-motion: reduce`: 모든 transition·animation 0ms, 탭 진입 애니메이션 없음, hover 이동 없음.

### 성공·오류 안내 지속 시간
- 오류(`notice-danger`)는 자동으로 숨기지 않는다. 사용자가 다시 시도하거나 상태가 바뀔 때 기능 코드가 지운다.
- 다운로드 요청 같은 일회성 성공은 기능별로 처리한다(2026-10-26 기준: Home은 4초 뒤 숨김, 시장 분석은 버튼 옆 안내 문장, 그린 클레임은 다음 상태 변화 때 지움). 공통 자동 숨김은 두지 않는다. 판단 근거와 제안은 docs/worklogs/hong_eunju/prompt_log.md DEV-COMMON-002.

### 반응형
- 1200px 미만: 본문 여백 32px → 24px. 960px 미만: 사이드바 접힘(상단 메뉴 버튼), 본문 여백 16px, 카드·머리글 여백 20px, 탭 제목 xl. 1100px 이상: `.workspace` 2열.
- 공통 스타일은 390px에서 가로 스크롤이 생기지 않아야 한다. 넓은 표는 `.table-wrap` 안에서만 가로 스크롤한다.

```html
<div class="workspace">
  <form class="card" aria-labelledby="green_claim-input-title">
    <div class="card-header"><div>
      <h2 class="card-title" id="green_claim-input-title">검수 대상</h2>
      <p class="card-description">짧은 설명</p>
    </div></div>
    <div class="field">
      <label class="field-label" for="green_claim-claims">주장 문구<span class="field-required">필수</span></label>
      <textarea class="textarea" id="green_claim-claims" aria-describedby="green_claim-claims-hint"></textarea>
      <p class="field-hint" id="green_claim-claims-hint">한 줄에 하나씩</p>
    </div>
    <div class="btn-row"><button type="submit" class="btn btn-primary">검수 실행</button></div>
  </form>
  <section class="card" aria-labelledby="green_claim-result-title">
    <div class="card-header"><div><h2 class="card-title" id="green_claim-result-title">검수 결과</h2></div>
      <button type="button" class="btn btn-secondary" disabled>PDF 다운로드</button></div>
    <div class="empty-state"><p class="empty-state-title">아직 결과가 없습니다</p><p>안내 문장</p></div>
  </section>
</div>

<div class="notice notice-warning" role="alert">
  <p class="notice-title">확인 필요</p><p>근거 자료에서 확인되지 않은 항목이 있습니다.</p>
</div>

<div class="table-wrap"><table class="table">
  <caption>출처 · 단위 · 조회 시각</caption>
  <thead><tr><th scope="col">항목</th><th scope="col" class="num">값</th></tr></thead>
  <tbody>…</tbody>
</table></div>
```

## 접근성 기준
- 모든 입력에 보이는 `<label for>`를 둔다. 안내문은 `aria-describedby`로 연결한다. 오류는 `aria-invalid="true"` + `.field-error` 문장.
- id는 다른 탭과 겹치지 않게 `기능id-` 접두어를 붙인다(모든 패널이 한 페이지에 있음).
- 상태는 색상과 텍스트를 함께 표시한다. 색만으로 위험도·성공을 구분하지 않는다.
- 키보드 초점은 공통 `:focus-visible` 테두리(블루 2px)를 쓰고 `outline: none`으로 지우지 않는다. 입력칸은 블루 테두리 + `--focus-halo`(outline은 투명 2px로 남김).
- 공통 shell 제공: 본문 건너뛰기 링크, 탭 전환 시 탭 제목으로 초점 이동, 모바일 메뉴 열면 메뉴로 초점·뒤 화면 `inert`, Esc로 닫고 메뉴 버튼으로 초점 복귀.
- 비동기 처리 중에는 버튼을 `disabled`로 바꿔 중복 실행을 막고, 결과 영역에 `aria-busy="true"`와 `.spinner` + 텍스트를 표시한다.

## 공통 동작
- 탭 전환은 해시(`#market_analysis`) 변경으로 처리하며 페이지를 다시 불러오지 않는다. 비활성 패널은 `hidden`만 적용되어 입력값·선택 파일·결과 DOM이 그대로 유지된다.
- 탭 사이 데이터는 자동 전달하지 않는다. 사용자 작업을 localStorage·sessionStorage·IndexedDB·서버에 저장하지 않는다.
- 패널 안 폼의 기본 제출(페이지 이동)은 공통 shell이 막는다. 기능 코드는 submit 핸들러에서 `fetch`로 요청한다.
- 새로고침·페이지 종료 시 작성 중 입력 또는 미다운로드 결과가 있으면 `beforeunload`로 브라우저 기본 경고를 요청한다. 내부 탭 이동에는 경고하지 않는다. 새로고침 후 이전 작업은 복원하지 않는다(해시로 마지막 탭만 다시 열림).
- 브라우저 제한: 경고 문구는 브라우저 기본 문구이며 사용자 지정 불가. 페이지와 상호작용하기 전이거나 브라우저·환경 정책(모바일 탭 정리, 강제 종료 등)에 따라 경고가 표시되지 않을 수 있다. 다운로드 요청 후 실제 파일 저장 성공 여부는 페이지에서 확인할 수 없다.

## 작업 상태 API (window.AppShell)
입력 변경은 공통 shell이 자동 감지한다: 패널 안 input/textarea/select 값이 기본값과 다르거나 파일이 선택되면 "작성 중"으로 표시하고 종료 경고를 켠다.
감지에서 뺄 입력(예: 결과 필터, 보기 전환)은 그 요소나 감싸는 요소에 `data-work-ignore` 속성을 붙인다. 패널 전체를 빼려면 panel.html 최상위 요소에 붙이고 `setDraft`로 직접 알린다.

| 호출 | 용도 |
|---|---|
| `AppShell.work.setResult(id, true/false)` | 다운로드하지 않은 결과 생김 / 결과 삭제 |
| `AppShell.work.downloadBlob(id, blob, "파일명.pdf")` | Blob 다운로드 요청 + `markDownloadRequested` |
| `AppShell.work.markDownloadRequested(id)` | 다른 방식으로 다운로드를 요청한 뒤 호출. 해당 탭 입력·결과 경고를 해제하고, 이후 입력을 다시 수정하면 다시 경고 |
| `AppShell.work.setDraft(id, true/false)` | 자동 감지 밖의 작성 상태(예: 결과 편집기, 코드로 만든 목록) |
| `AppShell.work.recheckInputs(id)` | 코드로 입력값을 바꾼 뒤 자동 감지 재실행(코드 변경은 input 이벤트가 없음) |
| `AppShell.work.clear(id)` | 사용자가 '새로 시작'을 누른 경우 등 상태 모두 해제 |
| `AppShell.work.get(id)` | `{hasDraft, hasUndownloadedResult, downloadRequested}` |
| `AppShell.current()`, `AppShell.show(id)` | 현재 탭 / 탭 전환(데이터 전달 아님) |
| `AppShell.onShow(id, fn)`, `AppShell.onHide(id, fn)` | 등록 이후의 탭 표시·숨김 시 호출. 첫 화면 상태는 `AppShell.current()`로 확인 |

머리글 상태 표시: 작성 중 > 다운로드 요청됨 순. 작성 중이면 사이드바 메뉴에 점(+화면낭독용 텍스트)이 표시된다.
미다운로드 결과(`setResult`)는 머리글·사이드바에 표시하지 않고 새로고침·종료 경고에만 쓴다(2026-10-26 한윤수 요청으로 변경, 팀 공유 필요).
"다운로드 요청됨"은 요청 상태일 뿐 저장 성공을 뜻하지 않는다. 화면 문구에서도 저장 완료라고 표현하지 않는다.

```js
// features/product_brochure/static/product_brochure.js
(function () {
  "use strict";
  const FEATURE_ID = "product_brochure";
  const panel = document.querySelector('[data-feature-panel="' + FEATURE_ID + '"]');
  if (!panel) return;
  const form = panel.querySelector("form");
  const submit = form.querySelector('[type="submit"]');

  form.addEventListener("submit", async function () {   // 기본 제출은 공통 shell이 막음
    submit.disabled = true;                              // 중복 실행 방지
    try {
      const res = await fetch("/api/product-brochure/generate", { method: "POST", body: new FormData(form) });
      const body = await res.json();
      if (!body.ok) throw new Error(body.error.message);
      // 결과 DOM 갱신 … (탭을 다시 열어도 DOM이 유지되므로 API를 재호출하지 않음)
      AppShell.work.setResult(FEATURE_ID, true);
    } catch (err) {
      // 입력은 그대로 두고 .notice-danger로 안내, 재시도 가능
    } finally {
      submit.disabled = false;
    }
  });

  async function downloadPdf() {
    const res = await fetch("/api/product-brochure/pdf", { method: "POST", body: /* 결과 */ null });
    AppShell.work.downloadBlob(FEATURE_ID, await res.blob(), "brochure.pdf");
  }
})();
```
다운로드는 `fetch` → Blob → `downloadBlob`을 권장한다. `location.href`로 다운로드 주소에 이동하면 브라우저가 페이지 이탈로 보고 종료 경고를 띄울 수 있다.

## PDF
PDF 디자인은 화면 디자인과 별도 검증: 한글/포르투갈어 글꼴·페이지 나눔·이미지 품질. 화면 토큰 값을 참고할 수 있으나 PDF 도구는 미정.

## 금지
공통 디자인과 다른 독자 테마, 공통 CSS 복제, 탭 CSS의 전역 덮어쓰기, 꾸민 데이터 표시, 작동하지 않는 버튼을 활성 상태로 두기.
