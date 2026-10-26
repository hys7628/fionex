// 제품소개서 탭 스크립트. 이 탭 패널 내부만 다룹니다. 공통 API 사용법: docs/design_system.md
// 범위: 한국어 PDF 선택 → 분석 요청(POST /api/product-brochure/analyze) → 결과 확인·수정. 개발용 예시도 유지합니다.
(function () {
  "use strict";

  /* ---------- 상태 로직(DOM 없음) ---------- */
  // 항목 상태는 서로 독립된 값으로 둡니다. 미제공과 가상은 동시에 성립할 수 있습니다.
  //   provided: 자료가 값을 제공했는지(예시: 값 있음, AI 분석: found이면서 값 있음). 사용자가 바꿀 수 없습니다.
  //   status: AI 분석 항목만 found/unclear/not_found(예시는 null).
  //   virtual: 시연용 가상 정보인지. 자료가 가상으로 표시한 값은 해제할 수 없습니다.
  //   confirmed: 사용자가 검토했다고 표시했는지. 사실 검증·원문 대조·인증 완료가 아닙니다.
  //   userAdded: 자료 값이 없던 항목에 사용자가 입력함. userModified: 자료 값을 사용자가 바꿈.
  const Review = (function () {
    const ANALYZE_URL = "/api/product-brochure/analyze";
    const MAX_FILE_BYTES = 10 * 1024 * 1024; // 서버 공통 설정 PDF_MAX_BYTES와 같은 값
    const STATUSES = ["found", "unclear", "not_found"];

    const GROUPS = [
      { key: "basic", label: "기본 정보" },
      { key: "spec", label: "기술 사양" },
      { key: "certification", label: "인증 정보" },
      { key: "supply", label: "공급 조건" },
    ];

    // 개발용 예시. 업로드한 PDF의 분석 결과가 아니며 근거 위치·원문 발췌가 없습니다.
    const EXAMPLE_FIELDS = [
      { key: "product_name", group: "basic", label: "제품명", value: "리젠 T2T", provided: true, virtual: false },
      { key: "description", group: "basic", label: "제품 설명", value: "폐의류를 재활용하는 폴리에스터 섬유", provided: true, virtual: false, multiline: true },
      { key: "yarn_spec", group: "spec", label: "원사 규격", value: "", provided: false, virtual: false },
      { key: "carbon_reduction", group: "spec", label: "탄소 저감률", value: "", provided: false, virtual: false },
      { key: "certification", group: "certification", label: "인증", value: "", provided: false, virtual: false },
      { key: "moq", group: "supply", label: "MOQ", value: "500 kg", provided: true, virtual: true },
      { key: "sample", group: "supply", label: "샘플", value: "1 kg", provided: true, virtual: true },
      { key: "lead_time", group: "supply", label: "납기", value: "30일", provided: true, virtual: true },
    ];
    const FIELD_KEYS = EXAMPLE_FIELDS.map(function (d) { return d.key; });

    function baseField(def) {
      return {
        key: def.key, group: def.group, label: def.label, multiline: !!def.multiline,
        status: null, aiStatus: null, evidence: [], note: null, serverNotes: [], candidates: null,
        confirmed: false, userAdded: false, userModified: false,
      };
    }

    function createFields(defs) {
      return defs.map(function (d) {
        const f = baseField(d);
        f.source = "example";
        f.sourceValue = d.value;
        f.sourceVirtual = !!d.virtual;
        f.provided = !!d.provided;
        f.value = d.value;
        f.virtual = !!d.virtual;
        return f;
      });
    }

    function isStr(v) { return typeof v === "string"; }
    function isStrOrNull(v) { return v === null || typeof v === "string"; }
    function isObj(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }
    function isCount(v) { return typeof v === "number" && Number.isInteger(v) && v >= 0; }

    function validField(f) {
      if (!isObj(f) || FIELD_KEYS.indexOf(f.key) < 0 || STATUSES.indexOf(f.status) < 0) return false;
      if (!isStrOrNull(f.value) || !isStrOrNull(f.note) || typeof f.marked_virtual !== "boolean") return false;
      if (f.confirmed !== false) return false;
      if (!Array.isArray(f.server_notes) || !f.server_notes.every(isStr)) return false;
      if (f.candidates !== undefined && (!Array.isArray(f.candidates) || !f.candidates.every(isStrOrNull))) return false;
      if (!Array.isArray(f.evidence)) return false;
      return f.evidence.every(function (e) {
        return isObj(e) && (e.page === null || Number.isInteger(e.page)) && isStrOrNull(e.quote) &&
          typeof e.page_in_range === "boolean" && isStr(e.check);
      });
    }

    // 성공 응답 본문 전체를 먼저 검사합니다. 하나라도 어긋나면 결과를 쓰지 않습니다(부분 덮어쓰기 없음).
    function validateAnalysis(body) {
      if (!isObj(body) || body.ok !== true || !isObj(body.data)) return null;
      const d = body.data;
      if (d.extraction_status !== "unconfirmed" || !isStr(d.model) || typeof d.multiple_products !== "boolean") return null;
      if (!isObj(d.source) || !isCount(d.source.size_bytes) || !isCount(d.source.page_count)) return null;
      if (!Array.isArray(d.review_notes) || !d.review_notes.every(function (n) {
        return isObj(n) && (n.source === "server" || n.source === "ai") && isStr(n.message);
      })) return null;
      if (!Array.isArray(d.fields) || d.fields.length !== FIELD_KEYS.length || !d.fields.every(validField)) return null;
      const keys = d.fields.map(function (f) { return f.key; });
      const unique = keys.filter(function (k, i) { return keys.indexOf(k) === i; });
      if (unique.length !== FIELD_KEYS.length) return null; // 중복 key
      return d;
    }

    // 검사를 통과한 분석 data → 화면 항목. 확인은 항상 해제 상태로 시작합니다.
    function createFieldsFromAnalysis(data) {
      return EXAMPLE_FIELDS.map(function (def) {
        const r = data.fields.filter(function (x) { return x.key === def.key; })[0];
        const f = baseField(def);
        const hasCandidates = Array.isArray(r.candidates) && r.candidates.length > 1;
        // 후보가 여럿이면 하나를 확정값처럼 채우지 않습니다.
        const value = hasCandidates ? "" : (r.value || "");
        f.source = "analysis";
        f.status = r.status;
        f.aiStatus = r.ai_status === undefined ? null : r.ai_status;
        f.sourceValue = value;
        f.value = value;
        f.provided = r.status === "found" && value.trim() !== "";
        f.sourceVirtual = r.marked_virtual;
        f.virtual = r.marked_virtual;
        f.evidence = r.evidence.map(function (e) {
          return { page: e.page, quote: e.quote, pageInRange: e.page_in_range };
        });
        f.note = r.note;
        f.serverNotes = r.server_notes.slice();
        f.candidates = hasCandidates ? r.candidates.slice() : null;
        return f;
      });
    }

    function setValue(field, value) {
      const text = String(value);
      if (text === field.value) return false;
      field.value = text;
      field.confirmed = false; // 값을 바꾸면 확인을 해제합니다.
      const hadSourceValue = field.sourceValue !== "";
      // unclear처럼 자료 값이 있던 항목의 수정은 "사용자 추가"가 아니라 "사용자 수정"입니다.
      field.userAdded = !hadSourceValue && text.trim() !== "";
      field.userModified = hadSourceValue && text !== field.sourceValue;
      return true;
    }

    function setConfirmed(field, value) {
      field.confirmed = !!value;
    }

    function setVirtual(field, value) {
      if (field.sourceVirtual) return false; // 자료가 가상으로 표시한 값은 실제 정보로 바꿀 수 없습니다.
      field.virtual = !!value;
      return true;
    }

    function isDirty(fields) {
      return fields.some(function (f) {
        return f.value !== f.sourceValue || f.confirmed || f.virtual !== f.sourceVirtual;
      });
    }

    function summarize(fields) {
      return {
        total: fields.length,
        confirmed: fields.filter(function (f) { return f.confirmed; }).length,
        notProvided: fields.filter(function (f) { return !f.provided && !f.userAdded; }).length,
        userAdded: fields.filter(function (f) { return f.userAdded; }).length,
        userModified: fields.filter(function (f) { return f.userModified; }).length,
        virtual: fields.filter(function (f) { return f.virtual; }).length,
        unclear: fields.filter(function (f) { return f.status === "unclear"; }).length,
      };
    }

    // 브라우저가 알려준 MIME은 쓰지 않습니다. 화면 1차 확인(선택·확장자·빈 파일·크기)만 합니다.
    function validateFile(file) {
      if (!file) return { ok: false, code: "none", message: "PDF 파일을 선택하지 않았습니다." };
      if (!/\.pdf$/i.test(file.name || "")) {
        return { ok: false, code: "extension", message: "PDF가 아닌 확장자입니다. 확장자가 .pdf인 파일을 선택하세요." };
      }
      if (file.size === 0) return { ok: false, code: "empty", message: "빈 파일입니다(0 bytes). 내용이 있는 PDF를 선택하세요." };
      if (file.size > MAX_FILE_BYTES) {
        return { ok: false, code: "too_large", message: "파일이 10 MiB를 넘습니다. 10 MiB 이하의 PDF를 선택하세요." };
      }
      return {
        ok: true, code: "selected",
        message: "파일을 선택했습니다. 실제 PDF 형식·손상·암호화·페이지 수는 분석 요청 시 서버에서 확인합니다.",
      };
    }

    function formatSize(bytes) {
      if (bytes < 1024) return bytes + " bytes";
      if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB (" + bytes.toLocaleString("ko-KR") + " bytes)";
      return (bytes / (1024 * 1024)).toFixed(1) + " MB (" + bytes.toLocaleString("ko-KR") + " bytes)";
    }

    // 서버 JSON 오류의 message는 공통 오류 계약의 고정 문장입니다. 형식이 맞을 때만 보여 줍니다.
    const SAFE_CODE = /^(PDF|AI|UPLOAD)_[A-Z_]{2,40}$/;

    // res: { networkError, aborted } 또는 { status, json }(JSON이 아니면 json undefined)
    function interpretResponse(res) {
      if (!res || res.networkError) {
        return { ok: false, kind: res && res.aborted ? "timeout" : "network",
          message: res && res.aborted
            ? "서버 응답이 오래 걸려 요청을 중단했습니다. 잠시 후 다시 시도하세요."
            : "서버에 연결하지 못했습니다. 네트워크 상태를 확인한 뒤 다시 시도하세요." };
      }
      if (res.status === 413) {
        return { ok: false, kind: "too_large", message: "파일 또는 요청 크기가 허용 범위(PDF 10 MiB)를 넘습니다." };
      }
      const body = res.json;
      if (body === undefined) {
        return { ok: false, kind: "not_json",
          message: "서버 응답을 해석하지 못했습니다(HTTP " + res.status + "). 잠시 후 다시 시도하세요." };
      }
      if (isObj(body) && body.ok === false) {
        const err = isObj(body.error) ? body.error : {};
        const safe = isStr(err.code) && SAFE_CODE.test(err.code) && isStr(err.message) && err.message.length <= 200;
        return { ok: false, kind: "server_error", code: safe ? err.code : null,
          message: safe ? err.message : "분석 요청을 처리하지 못했습니다(HTTP " + res.status + "). 다시 시도하세요." };
      }
      const data = res.status >= 200 && res.status < 300 ? validateAnalysis(body) : null;
      if (!data) {
        return { ok: false, kind: "invalid_response", message: "분석 응답 형식이 올바르지 않아 결과를 표시하지 않았습니다. 다시 시도하세요." };
      }
      return { ok: true, data: data };
    }

    // 요청 실행기. 중복 요청을 막고, 요청 번호로 오래된 응답을 무시합니다. 자동 재시도는 없습니다.
    //   deps.send(input) → Promise<res>, deps.needsConfirm() → bool, deps.confirm(msg) → bool,
    //   deps.onBusy(bool), deps.onSuccess(data), deps.onFailure(result)
    //   선택: deps.blocked() → bool(다른 요청 진행 중이면 시작하지 않음)
    //   runner 옵션: validate(input) → bool, interpret(res), confirmMessage
    const REPLACE_MESSAGE = "PDF 분석 결과로 현재 확인·수정한 내용을 교체합니다. 분석에 성공한 뒤에만 교체됩니다. 계속할까요?";
    const REGENERATE_MESSAGE = "새 카탈로그 문구로 기존 생성 결과를 교체합니다. 생성에 성공한 뒤에만 교체됩니다. 계속할까요?";
    const REGENERATE_EDITED_MESSAGE = "새 카탈로그 문구로 기존 생성 결과와 직접 수정한 문구(편집 중인 내용 포함)를 모두 교체합니다. " +
      "생성에 성공한 뒤에만 교체됩니다. 계속할까요?";

    function createRunner(deps, options) {
      let seq = 0;
      let busy = false;

      async function run(input) {
        if (busy) return "busy";
        if (deps.blocked && deps.blocked()) return "blocked";
        if (!options.validate(input)) return "invalid";
        const confirmMessage = deps.confirmMessage ? deps.confirmMessage() : options.confirmMessage;
        if (deps.needsConfirm() && !deps.confirm(confirmMessage)) return "cancelled";
        const id = ++seq;
        busy = true;
        deps.onBusy(true);
        try {
          let res;
          try {
            res = await deps.send(input);
          } catch (e) {
            res = { networkError: true };
          }
          if (id !== seq) return "stale";
          const out = options.interpret(res);
          if (out.ok) deps.onSuccess(out.data);
          else deps.onFailure(out);
          return out.ok ? "success" : "failure";
        } finally {
          if (id === seq) {
            busy = false;
            deps.onBusy(false);
          }
        }
      }

      // 진행 중 요청의 응답을 무시하도록 만듭니다(현재 화면에서는 사용하지 않는 방어 경로).
      function invalidate() {
        seq++;
        if (busy) {
          busy = false;
          deps.onBusy(false);
        }
      }

      return { run: run, invalidate: invalidate, isBusy: function () { return busy; } };
    }

    function createAnalyzer(deps) {
      return createRunner(deps, {
        validate: function (file) { return validateFile(file).ok; },
        interpret: interpretResponse,
        confirmMessage: REPLACE_MESSAGE,
      });
    }

    /* ----- 카탈로그 문구 생성(서버 계약: features/product_brochure/generation.py, 명세 §21) ----- */
    const GENERATE_URL = "/api/product-brochure/generate";
    const REQUIRED_KEYS = ["product_name", "description"];
    const DETAIL_KEYS = ["yarn_spec", "certification", "carbon_reduction"];
    const SUPPLY_KEYS = ["moq", "sample", "lead_time"];
    const ORIGINS = ["extracted", "user_modified", "user_added"];
    // 서버 generation.MAX_VALUE_CHARS와 같은 값. 넘는 값은 자르지 않고 생성을 막습니다.
    const MAX_VALUE_CHARS = {
      product_name: 120, description: 1500,
      yarn_spec: 300, certification: 300, carbon_reduction: 300,
      moq: 200, sample: 200, lead_time: 200,
    };
    const FIELD_LABEL = {};
    EXAMPLE_FIELDS.forEach(function (d) { FIELD_LABEL[d.key] = d.label; });

    // 화면 상태 → 서버 origin. 사용자 추가 항목은 다시 고쳐도 user_added로 남습니다(sourceValue가 없으므로).
    function originOf(field) {
      if (field.userAdded) return "user_added";
      if (field.userModified) return "user_modified";
      return "extracted";
    }

    /* ----- 카탈로그 표시명(원본 제품명과 분리, 명세 §23) ----- */
    const MAX_DISPLAY_NAME_CHARS = 80; // 서버 generation.MAX_DISPLAY_NAME_CHARS와 같은 값
    // 한글 음절·자모(호환 자모·확장 A/B·반각 포함). 서버 generation.HANGUL과 같은 범위
    const HANGUL = /[ᄀ-ᇿ㄰-㆏ꥠ-꥿가-힣ힰ-퟿ﾠ-ￜ]/;
    const CONTROL = /[\u0000-\u001f\u007f]/;
    const LATIN_RUN = /[A-Za-zÀ-ɏ0-9][A-Za-zÀ-ɏ0-9 .,'&+\/\-®™]*/g;

    function latinRuns(text) {
      return (text.match(LATIN_RUN) || []).map(function (s) { return s.trim(); }).filter(function (s) {
        return /[A-Za-zÀ-ɏ]/.test(s);
      });
    }

    function tokens(text) {
      return text.toLowerCase().split(/[^a-zÀ-ɏ0-9]+/).filter(Boolean);
    }

    // 원본 제품명에서 카탈로그 표시명 후보를 제안합니다. 명확할 때만 값을 채우고, 애매하면 비워 둡니다.
    //   - 한글이 없으면 원본 그대로
    //   - 한글 + 괄호 안 라틴 문자 표기가 하나이고, 괄호 밖 라틴 단어가 모두 그 표기에 포함되면 그 표기
    //   - 그 밖(한글만, 후보 여러 개, 괄호 밖 단어 불일치)은 제안하지 않음(공식 영문명을 만들지 않음)
    function suggestDisplayName(productName) {
      const name = String(productName || "").trim();
      if (!name) return { value: "", reason: "empty", candidates: [] };
      if (!HANGUL.test(name)) return { value: name, reason: "latin_only", candidates: [name] };
      const groups = (name.match(/\(([^()]*)\)/g) || []).map(function (g) { return g.slice(1, -1).trim(); });
      const latinGroups = groups.filter(function (g) { return g && !HANGUL.test(g) && /[A-Za-zÀ-ɏ]/.test(g); });
      const outside = name.replace(/\([^()]*\)/g, " ");
      const candidates = latinRuns(outside).concat(latinGroups).filter(function (c, i, all) {
        return all.map(function (x) { return x.toLowerCase(); }).indexOf(c.toLowerCase()) === i;
      });
      if (latinGroups.length === 1) {
        const groupTokens = tokens(latinGroups[0]);
        const outsideTokens = tokens(latinRuns(outside).join(" "));
        if (outsideTokens.every(function (t) { return groupTokens.indexOf(t) >= 0; })) {
          return { value: latinGroups[0], reason: "paren_latin", candidates: candidates };
        }
      }
      return { value: "", reason: candidates.length ? "ambiguous" : "none", candidates: candidates };
    }

    function validateDisplayName(value) {
      const v = String(value || "").trim();
      if (!v) return { ok: false, reason: "empty", message: "카탈로그 표시명을 입력하세요." };
      if (v.length > MAX_DISPLAY_NAME_CHARS) {
        return { ok: false, reason: "too_long", message: "카탈로그 표시명은 " + MAX_DISPLAY_NAME_CHARS + "자 이하로 입력하세요." };
      }
      if (HANGUL.test(v)) return { ok: false, reason: "hangul", message: "카탈로그 표시명에는 한글을 쓸 수 없습니다. 원문의 라틴 문자 표기를 입력하세요." };
      if (CONTROL.test(v)) return { ok: false, reason: "control", message: "카탈로그 표시명에 쓸 수 없는 문자가 있습니다." };
      return { ok: true, reason: null, message: "" };
    }

    function inputSignature(fields, displayName) {
      const dn = displayName || { value: "", confirmed: false };
      return JSON.stringify({
        fields: fields.map(function (f) { return [f.key, f.value, !!f.confirmed, !!f.virtual, originOf(f)]; }),
        display_name: [String(dn.value), !!dn.confirmed],
      });
    }

    // "확인 내용 적용" 시점의 독립 복사본. 원래 항목 객체와 참조를 공유하지 않습니다.
    function createSnapshot(fields, source, version, displayName) {
      const dn = displayName || { value: "", confirmed: false };
      return {
        source: source,
        version: version,
        signature: inputSignature(fields, dn),
        displayName: { value: String(dn.value), confirmed: !!dn.confirmed },
        fields: fields.map(function (f) {
          return { key: f.key, value: String(f.value), confirmed: !!f.confirmed, virtual: !!f.virtual, origin: originOf(f) };
        }),
      };
    }

    function snapshotField(snapshot, key) {
      return snapshot.fields.filter(function (f) { return f.key === key; })[0];
    }

    // 생성 가능 여부와 포함·제외 항목(서버 select_inputs와 같은 기준)
    function evaluateGeneration(ctx) {
      const out = { ok: false, reason: null, message: "", included: [], excluded: [], tooLong: [] };
      if (ctx.source !== "analysis") {
        out.reason = ctx.source === "example" ? "example" : "no_analysis";
        out.message = ctx.source === "example"
          ? "개발용 예시로는 생성하지 않습니다. 실제 PDF 분석 결과를 검토·적용한 뒤 생성할 수 있습니다."
          : "PDF 분석 결과를 검토하고 \"확인 내용 적용\"을 누르면 생성할 수 있습니다.";
        return out;
      }
      if (!ctx.snapshot || ctx.snapshot.source !== "analysis" || ctx.snapshot.version !== ctx.version) {
        out.reason = "not_applied";
        out.message = "\"확인 내용 적용\"을 눌러 생성에 쓸 항목을 확정하세요.";
        return out;
      }
      if (ctx.snapshot.signature !== ctx.currentSignature) {
        out.reason = "reapply";
        out.message = "적용 이후 값이나 확인 상태가 바뀌었습니다. 다시 \"확인 내용 적용\"을 누르세요.";
        return out;
      }
      ctx.snapshot.fields.forEach(function (f) {
        if (f.value.length > MAX_VALUE_CHARS[f.key]) out.tooLong.push(f.key);
        if (!f.value.trim()) out.excluded.push({ key: f.key, reason: "empty" });
        else if (!f.confirmed) out.excluded.push({ key: f.key, reason: "unconfirmed" });
        else out.included.push(f.key);
      });
      const requiredOk = REQUIRED_KEYS.every(function (k) { return out.included.indexOf(k) >= 0; });
      const dn = ctx.snapshot.displayName || { value: "", confirmed: false };
      const dnCheck = validateDisplayName(dn.value);
      if (!requiredOk) {
        out.reason = "required";
        out.message = "제품명과 제품 설명에 값을 입력하고 \"사용자 확인\"을 체크한 뒤 다시 적용하세요.";
      } else if (!dnCheck.ok || !dn.confirmed) {
        out.reason = "display_name";
        out.message = (dnCheck.ok ? "카탈로그 표시명을 확인(체크)하세요." : dnCheck.message) + " 그 뒤 다시 적용하세요.";
      } else if (out.tooLong.length) {
        out.reason = "too_long";
        out.message = "허용 길이를 넘는 항목이 있습니다: " + out.tooLong.map(function (k) {
          return FIELD_LABEL[k] + "(" + MAX_VALUE_CHARS[k] + "자)";
        }).join(", ") + ". 값을 줄인 뒤 다시 적용하세요.";
      } else if (ctx.busy) {
        out.reason = "busy";
        out.message = "다른 요청을 처리하는 중입니다.";
      } else {
        out.ok = true;
      }
      return out;
    }

    // 서버 엄격 스키마: 8개 key 각각 {key, value, confirmed, virtual, origin} + display_name {value, confirmed}
    function buildGeneratePayload(snapshot) {
      return {
        fields: FIELD_KEYS.map(function (k) {
          const f = snapshotField(snapshot, k);
          return { key: k, value: f.value, confirmed: f.confirmed, virtual: f.virtual, origin: f.origin };
        }),
        display_name: { value: snapshot.displayName.value.trim(), confirmed: snapshot.displayName.confirmed },
      };
    }

    function validKeys(keys, allowed) {
      return Array.isArray(keys) && keys.length > 0 && keys.every(function (k) { return allowed.indexOf(k) >= 0; });
    }

    function validCopy(c, used) {
      return isObj(c) && isStr(c.text) && c.text.trim() !== "" && validKeys(c.source_keys, used) &&
        typeof c.virtual === "boolean" && isObj(c.origins) && Array.isArray(c.review_flags) && c.review_flags.every(isStr) &&
        (c.fictitious_notice === undefined || isStr(c.fictitious_notice));
    }

    function validInfoPage(p, pageNo, pageKeys, used) {
      if (!isObj(p) || p.page !== pageNo || !Array.isArray(p.items) || typeof p.empty !== "boolean") return false;
      if (p.empty !== (p.items.length === 0)) return false;
      if (p.empty ? !isStr(p.empty_message) : p.empty_message !== null) return false;
      const keys = p.items.map(function (i) { return isObj(i) ? i.key : null; });
      if (keys.some(function (k, n) { return keys.indexOf(k) !== n; })) return false; // 중복
      return p.items.every(function (i) {
        return isObj(i) && pageKeys.indexOf(i.key) >= 0 && used.indexOf(i.key) >= 0 &&
          isStr(i.label) && i.label.trim() !== "" && isStr(i.value) && i.value.trim() !== "" &&
          Array.isArray(i.source_keys) && i.source_keys.length === 1 && i.source_keys[0] === i.key &&
          typeof i.virtual === "boolean" && ORIGINS.indexOf(i.origin) >= 0 &&
          Array.isArray(i.review_flags) && i.review_flags.every(isStr) &&
          (i.fictitious_notice === undefined || isStr(i.fictitious_notice));
      });
    }

    // 생성 성공 응답 전체 검사. 하나라도 어긋나면 null(부분 반영 없음)
    function validateGeneration(body) {
      if (!isObj(body) || body.ok !== true || !isObj(body.data)) return null;
      const d = body.data;
      if (d.status !== "draft_needs_review" || d.language !== "pt-BR" || !isStr(d.prompt_version) || !isStr(d.model)) return null;
      if (!isObj(d.notices) || !isStr(d.notices.unofficial) || !isStr(d.notices.fictitious)) return null;
      if (!isObj(d.display_name) || d.display_name.confirmed !== true || !validateDisplayName(d.display_name.value).ok) return null;
      if (!validKeys(d.used_keys, FIELD_KEYS)) return null;
      if (!REQUIRED_KEYS.every(function (k) { return d.used_keys.indexOf(k) >= 0; })) return null;
      if (!Array.isArray(d.excluded) || !d.excluded.every(function (e) {
        return isObj(e) && FIELD_KEYS.indexOf(e.key) >= 0 && (e.reason === "empty" || e.reason === "unconfirmed");
      })) return null;
      const p = d.pages;
      if (!isObj(p) || !isObj(p.cover) || !isObj(p.intro) || p.cover.page !== 1 || p.intro.page !== 2) return null;
      if (!validCopy(p.cover.product_name, ["product_name"]) || !validCopy(p.cover.tagline, d.used_keys)) return null;
      if (p.cover.product_name.text !== d.display_name.value) return null; // 표지 제품명 = 확인한 표시명
      if (!Array.isArray(p.intro.paragraphs) || p.intro.paragraphs.length < 1 || p.intro.paragraphs.length > 2 ||
          !p.intro.paragraphs.every(function (c) { return validCopy(c, d.used_keys); })) return null;
      if (!validInfoPage(p.details, 3, DETAIL_KEYS, d.used_keys) || !validInfoPage(p.supply, 4, SUPPLY_KEYS, d.used_keys)) return null;
      return d;
    }

    // 알려진 오류 코드 → 안전한 한국어 안내(서버 메시지·공급자 원문은 표시하지 않음)
    const GENERATE_ERROR_MESSAGES = {
      GENERATE_REQUIRED_MISSING: "제품명과 제품 설명을 입력하고 사용자 확인한 뒤 다시 적용하세요.",
      GENERATE_FIELD_TOO_LONG: "허용 길이를 넘는 항목이 있습니다. 값을 줄인 뒤 다시 적용하세요.",
      GENERATE_INVALID_INPUT: "생성 요청 형식이 올바르지 않습니다. 다시 적용한 뒤 시도하세요.",
      GENERATE_DUPLICATE_KEY: "생성 요청 형식이 올바르지 않습니다(항목 중복).",
      GENERATE_MISSING_KEY: "생성 요청 형식이 올바르지 않습니다(항목 누락).",
      GENERATE_INVALID_JSON: "생성 요청 형식이 올바르지 않습니다.",
      GENERATE_REQUEST_TOO_LARGE: "생성 요청 크기가 허용 범위를 넘습니다. 긴 항목을 줄인 뒤 다시 적용하세요.",
      GENERATE_OUTPUT_INVALID: "생성된 문구가 형식·범위 검증을 통과하지 못했습니다. 다시 시도하세요.",
      GENERATE_OUTPUT_LANGUAGE: "생성된 카탈로그 문구에 한국어가 남아 있어 결과를 표시하지 않았습니다. 다시 시도하세요.",
      GENERATE_DISPLAY_NAME_REQUIRED: "카탈로그 표시명을 입력하고 확인한 뒤 다시 적용하세요.",
      GENERATE_DISPLAY_NAME_INVALID: "카탈로그 표시명 형식이 올바르지 않습니다(한글·제어 문자 불가, 80자 이하). 고친 뒤 다시 적용하세요.",
      AI_CONFIG_MISSING: "AI 기능 설정이 준비되지 않았습니다. 관리자에게 문의하세요.",
      AI_AUTH_FAILED: "AI 서비스 인증에 실패했습니다. 관리자에게 문의하세요.",
      AI_PERMISSION_DENIED: "AI 서비스 사용 권한이 없습니다. 관리자에게 문의하세요.",
      AI_MODEL_UNAVAILABLE: "설정된 AI 모델을 사용할 수 없습니다. 관리자에게 문의하세요.",
      AI_RATE_LIMITED: "AI 호출 한도에 도달했습니다. 잠시 후 다시 시도하세요.",
      AI_CONNECTION_FAILED: "AI 서비스에 연결하지 못했습니다. 잠시 후 다시 시도하세요.",
      AI_TIMEOUT: "AI 응답 시간이 초과되었습니다. 잠시 후 다시 시도하세요.",
      AI_PROVIDER_ERROR: "AI 서비스에서 오류가 발생했습니다. 잠시 후 다시 시도하세요.",
      AI_BAD_REQUEST: "AI 서비스가 요청을 처리하지 못했습니다. 관리자에게 문의하세요.",
      AI_REFUSED: "AI가 요청을 처리하지 않았습니다. 입력 내용을 확인한 뒤 다시 시도하세요.",
      AI_INCOMPLETE: "AI 응답이 완료되지 않았습니다. 다시 시도하세요.",
      AI_OUTPUT_INVALID: "AI 응답을 결과 형식으로 해석하지 못했습니다. 다시 시도하세요.",
    };

    // 한글 잔존 오류 메시지에서 서버가 만든 위치 표기만 꺼냅니다. 알려진 형식이 아닌 조각은 버립니다(문서 내용 미표시).
    function languageErrorPlaces(message) {
      if (!isStr(message) || message.indexOf("위치: ") < 0) return [];
      const labels = EXAMPLE_FIELDS.map(function (d) { return d.label; });
      return message.slice(message.indexOf("위치: ") + 4).split(", ").filter(function (p) {
        if (p === "1쪽 소개 문구" || p === "2쪽 소개 문단 1" || p === "2쪽 소개 문단 2") return true;
        const m = /^([34]쪽) (.+) (항목명|값)$/.exec(p);
        return !!m && labels.indexOf(m[2]) >= 0;
      });
    }

    function interpretGenerateResponse(res) {
      if (!res || res.networkError) {
        return { ok: false, kind: res && res.aborted ? "timeout" : "network",
          message: res && res.aborted
            ? "응답이 오래 걸려 화면에서 기다리기를 중단했습니다. 서버의 처리·과금이 취소되었다는 뜻은 아닙니다. 잠시 후 다시 시도하세요."
            : "서버에 연결하지 못했습니다. 네트워크 상태를 확인한 뒤 다시 시도하세요." };
      }
      if (res.status === 413) {
        return { ok: false, kind: "too_large", message: GENERATE_ERROR_MESSAGES.GENERATE_REQUEST_TOO_LARGE };
      }
      const body = res.json;
      if (body === undefined) {
        return { ok: false, kind: "not_json",
          message: "서버 응답을 해석하지 못했습니다(HTTP " + res.status + "). 잠시 후 다시 시도하세요." };
      }
      if (isObj(body) && body.ok === false) {
        const code = isObj(body.error) && isStr(body.error.code) ? body.error.code : null;
        const known = code && Object.prototype.hasOwnProperty.call(GENERATE_ERROR_MESSAGES, code);
        let message = known ? GENERATE_ERROR_MESSAGES[code] : "생성 요청을 처리하지 못했습니다(HTTP " + res.status + "). 다시 시도하세요.";
        if (code === "GENERATE_OUTPUT_LANGUAGE") {
          const places = languageErrorPlaces(body.error.message);
          if (places.length) message += " 위치: " + places.join(", ");
        }
        return { ok: false, kind: "server_error", code: known ? code : null, message: message };
      }
      const data = res.status >= 200 && res.status < 300 ? validateGeneration(body) : null;
      if (!data) {
        return { ok: false, kind: "invalid_response", message: "생성 응답 형식이 올바르지 않아 결과를 표시하지 않았습니다. 다시 시도하세요." };
      }
      return { ok: true, data: data };
    }

    function createGenerator(deps) {
      return createRunner(deps, {
        validate: function (snapshot) { return !!snapshot && deps.canGenerate(snapshot); },
        interpret: interpretGenerateResponse,
        confirmMessage: REGENERATE_MESSAGE,
      });
    }

    // 생성 결과가 현재 입력과 다를 수 있는지(생성 당시 스냅샷 기준)
    function isResultStale(result, ctx) {
      if (!result) return false;
      return ctx.version !== result.version || ctx.currentSignature !== result.signature;
    }

    const FLAG_TEXT = {
      new_number: "입력에 없는 숫자가 있습니다",
      number_not_preserved: "입력의 수치가 그대로 보이지 않습니다",
      claim_term: "근거 확인이 필요한 평가 표현이 있습니다",
      repeated_text: "표지 소개 문구와 거의 같은 내용이 반복됩니다",
    };

    /* ----- 생성 결과 문구 편집(브라우저 메모리만, API 호출 없음) ----- */
    // 서버 generation.py 출력 상한과 같은 값. 넘는 값은 자르지 않고 적용을 막습니다.
    const OUTPUT_LIMITS = { tagline: 140, paragraph: 600, detail: 300, supply: 200 };
    const EDIT_CONTROL = /[\u0000-\u0009\u000b-\u001f\u007f]/; // 줄바꿈(\n) 외 제어 문자

    function cloneData(data) {
      return JSON.parse(JSON.stringify(data));
    }

    // 편집 가능한 칸: 1쪽 표시명·소개, 2쪽 문단, 3·4쪽 값. 라벨·제목·고정 안내·메타데이터는 제외
    function editableEntries(data) {
      const p = data.pages;
      const out = [
        { id: "display_name", where: "1쪽 카탈로그 표시명", value: data.display_name.value, limit: MAX_DISPLAY_NAME_CHARS, multiline: false },
        { id: "tagline", where: "1쪽 소개 문구", value: p.cover.tagline.text, limit: OUTPUT_LIMITS.tagline, multiline: true },
      ];
      p.intro.paragraphs.forEach(function (c, n) {
        out.push({ id: "paragraph:" + n, where: "2쪽 소개 문단 " + (n + 1), value: c.text, limit: OUTPUT_LIMITS.paragraph, multiline: true });
      });
      p.details.items.forEach(function (i) {
        out.push({ id: "detail:" + i.key, where: "3쪽 " + FIELD_LABEL[i.key] + " 값", value: i.value, limit: OUTPUT_LIMITS.detail, multiline: true });
      });
      p.supply.items.forEach(function (i) {
        out.push({ id: "supply:" + i.key, where: "4쪽 " + FIELD_LABEL[i.key] + " 값", value: i.value, limit: OUTPUT_LIMITS.supply, multiline: true });
      });
      return out;
    }

    function editValues(data) {
      const values = {};
      editableEntries(data).forEach(function (e) { values[e.id] = e.value; });
      return values;
    }

    // 위치별 검사. 하나라도 틀리면 적용하지 않습니다(부분 적용 없음).
    function validateEdits(data, values) {
      const errors = [];
      editableEntries(data).forEach(function (e) {
        const raw = values[e.id];
        const add = function (message) { errors.push({ id: e.id, where: e.where, message: message }); };
        if (typeof raw !== "string") return add("값을 읽을 수 없습니다.");
        const v = raw.trim();
        if (!v) return add("비어 있습니다.");
        if (v.length > e.limit) return add(e.limit + "자를 넘습니다(현재 " + v.length + "자). 직접 줄여 주세요.");
        if (HANGUL.test(v)) return add("한글이 남아 있습니다. 카탈로그 문구는 pt-BR로 입력하세요.");
        if (EDIT_CONTROL.test(v)) return add("쓸 수 없는 문자가 있습니다.");
      });
      return { ok: errors.length === 0, errors: errors };
    }

    // 검증을 통과한 값으로 새 편집본을 만듭니다. 텍스트·값만 바꾸고 source_keys·origin·virtual·review_flags·안내는 보존.
    // 표지 표시명은 display_name.value와 cover.product_name.text를 함께 바꿔 일관성을 유지합니다.
    function applyEdits(original, current, values) {
      const check = validateEdits(current, values);
      if (!check.ok) return { ok: false, errors: check.errors };
      const next = cloneData(current);
      const v = function (id) { return values[id].trim(); };
      next.display_name.value = v("display_name");
      next.pages.cover.product_name.text = v("display_name");
      next.pages.cover.tagline.text = v("tagline");
      next.pages.intro.paragraphs.forEach(function (c, n) { c.text = v("paragraph:" + n); });
      next.pages.details.items.forEach(function (i) { i.value = v("detail:" + i.key); });
      next.pages.supply.items.forEach(function (i) { i.value = v("supply:" + i.key); });
      return { ok: true, data: next, editedIds: editedIds(original, next) };
    }

    // AI 원본과 값이 다른 칸(사용자 수정 · 재검토 필요)
    function editedIds(original, data) {
      const base = editValues(original);
      return editableEntries(data).filter(function (e) { return base[e.id] !== e.value; }).map(function (e) { return e.id; });
    }

    function isEditDirty(data, values) {
      const base = editValues(data);
      return Object.keys(base).some(function (id) { return values[id] !== base[id]; });
    }

    function describeUserEdits(data, ids) {
      return editableEntries(data).filter(function (e) { return ids.indexOf(e.id) >= 0; }).map(function (e) { return e.where; });
    }

    // review_flags → 사람이 찾을 수 있는 위치·항목 이름·설명 목록
    function describeReviewFlags(data) {
      const out = [];
      function add(where, flags) {
        flags.forEach(function (f) { out.push({ where: where, flag: f, text: FLAG_TEXT[f] || "검토가 필요합니다" }); });
      }
      add("1쪽 소개 문구", data.pages.cover.tagline.review_flags);
      data.pages.intro.paragraphs.forEach(function (c, n) { add("2쪽 소개 문단 " + (n + 1), c.review_flags); });
      data.pages.details.items.forEach(function (i) { add("3쪽 " + FIELD_LABEL[i.key], i.review_flags); });
      data.pages.supply.items.forEach(function (i) { add("4쪽 " + FIELD_LABEL[i.key], i.review_flags); });
      return out;
    }

    /* ----- 카탈로그 PDF 다운로드(서버 계약: features/product_brochure/pdf_download.py·pdf_catalog.parse_catalog, 명세 §26·§27) ----- */
    const PDF_URL = "/api/product-brochure/pdf";
    const PDF_FILENAME = "fionex_catalog_pt-BR.pdf";    // 서버 pdf_download.DOWNLOAD_NAME과 같은 고정 이름
    const MAX_PDF_REQUEST_BYTES = 32 * 1024;             // 서버 pdf_download.MAX_REQUEST_BYTES와 같은 값
    // 3·4쪽 항목명: 서버 pdf_catalog.ITEM_LABELS와 같은 고정 pt-BR 표시명(화면·PDF 일치, AI 라벨 미사용)
    const CATALOG_ITEM_LABELS = {
      yarn_spec: "Especificação do fio",
      certification: "Certificações",
      carbon_reduction: "Redução de carbono",
      moq: "Pedido mínimo (MOQ)",
      sample: "Amostra",
      lead_time: "Prazo de entrega",
    };
    const PDF_STALE_MESSAGE = "이 결과는 현재 입력과 다를 수 있습니다. 현재 미리보기 내용으로 PDF를 다운로드할까요?";
    const PDF_EDIT_PENDING_MESSAGE = "문구를 적용하거나 편집을 취소한 뒤 다운로드하세요.";

    // 적용된 편집본(generation.current)에서 parse_catalog가 받는 필드만 명시적으로 복사합니다.
    // AI 원본·편집 중 임시 값·항목명·근거·검토 표시·출처 메타데이터는 넣지 않습니다. virtual은 불리언으로 보존.
    function buildPdfPayload(current) {
      const p = current.pages;
      const text = function (c) { return { text: c.text, virtual: c.virtual === true }; };
      const item = function (i) { return { key: i.key, value: i.value, virtual: i.virtual === true }; };
      return {
        catalog: {
          language: "pt-BR",
          cover: { product_name: text(p.cover.product_name), tagline: text(p.cover.tagline) },
          intro: { paragraphs: p.intro.paragraphs.map(text) },
          details: { items: p.details.items.map(item) },
          supply: { items: p.supply.items.map(item) },
        },
      };
    }

    function utf8Bytes(str) {
      return new TextEncoder().encode(str).length;
    }

    // 다운로드 가능 조건. ctx: { hasResult, editDirty, busy, bodyBytes, coverApplied }
    // coverApplied: 사용자가 적용한 AI 표지 배경이 있으면 PDF가 미리보기와 달라지므로 막음(PDF 반영은 후속 작업)
    function evaluatePdfDownload(ctx) {
      if (!ctx.hasResult) return { ok: false, reason: "no_result", message: "카탈로그를 생성한 뒤 PDF를 다운로드할 수 있습니다(디자인 시안은 대상이 아님)." };
      if (ctx.busy) return { ok: false, reason: "busy", message: "다른 요청이 진행 중입니다. 끝난 뒤 다운로드하세요." };
      if (ctx.coverApplied) return { ok: false, reason: "cover_applied", message: COVER_PDF_BLOCK_MESSAGE };
      if (ctx.editDirty) return { ok: false, reason: "edit_pending", message: PDF_EDIT_PENDING_MESSAGE };
      if (ctx.bodyBytes > MAX_PDF_REQUEST_BYTES) {
        return { ok: false, reason: "too_large", message: "PDF 요청 크기가 허용 범위(32 KiB)를 넘습니다. 긴 문구를 줄여 적용한 뒤 다시 시도하세요." };
      }
      return { ok: true, reason: null, message: "" };
    }

    // 알려진 오류 코드 → 고정 한국어 안내(서버 메시지·HTML은 표시하지 않음).
    // 넘침 오류 응답에는 구조화된 위치 정보가 없으므로(code·message만) 위치를 추측하지 않습니다.
    const PDF_ERROR_MESSAGES = {
      BROCHURE_PDF_INVALID_JSON: "PDF 요청 형식이 올바르지 않습니다. 다시 시도하세요.",
      BROCHURE_PDF_INVALID_INPUT: "PDF로 만들 수 없는 문구가 있습니다(빈 값·길이·한글·쓸 수 없는 문자). 문구를 확인한 뒤 다시 시도하세요.",
      BROCHURE_PDF_REQUEST_TOO_LARGE: "PDF 요청 크기가 허용 범위(32 KiB)를 넘습니다. 긴 문구를 줄여 적용한 뒤 다시 시도하세요.",
      BROCHURE_PDF_BUSY: "PDF를 만드는 요청이 많습니다. 잠시 후 다시 시도하세요.",
      BROCHURE_PDF_LAYOUT_OVERFLOW: "PDF 페이지의 정해진 영역에 들어가지 않는 문구가 있습니다. 긴 문구를 줄여 적용한 뒤 다시 시도하세요.",
      BROCHURE_PDF_GLYPH_MISSING: "PDF 글꼴로 표시할 수 없는 문자(이모지 등)가 있습니다. 해당 문자를 지운 뒤 다시 시도하세요.",
      BROCHURE_PDF_ASSET_UNAVAILABLE: "PDF에 필요한 이미지·글꼴을 불러오지 못했습니다. 관리자에게 문의하세요.",
      BROCHURE_PDF_RENDER_FAILED: "카탈로그 PDF를 만들지 못했습니다. 잠시 후 다시 시도하세요.",
    };

    // res: { networkError, aborted } 또는 { status, contentType, json, size, head }(head: 본문 앞 5바이트 문자열)
    function interpretPdfResponse(res) {
      if (!res || res.networkError) {
        return { ok: false, kind: res && res.aborted ? "timeout" : "network",
          message: res && res.aborted
            ? "PDF 응답이 30초 안에 오지 않아 화면에서 기다리기를 중단했습니다. 서버의 PDF 생성이 멈췄다는 뜻은 아닙니다. 잠시 후 다시 시도하세요."
            : "서버에 연결하지 못했습니다. 네트워크 상태를 확인한 뒤 다시 시도하세요." };
      }
      const type = (res.contentType || "").split(";")[0].trim().toLowerCase();
      if (res.status === 200 && type === "application/pdf") {
        if (!(res.size > 0) || res.head !== "%PDF-") {
          return { ok: false, kind: "invalid_response", message: "받은 파일이 올바른 PDF가 아니어서 다운로드하지 않았습니다. 다시 시도하세요." };
        }
        return { ok: true, data: null };
      }
      if (res.status === 413) return { ok: false, kind: "server_error", code: "BROCHURE_PDF_REQUEST_TOO_LARGE",
        message: PDF_ERROR_MESSAGES.BROCHURE_PDF_REQUEST_TOO_LARGE };
      const body = res.json;
      if (isObj(body) && body.ok === false) {
        const code = isObj(body.error) && isStr(body.error.code) ? body.error.code : null;
        const known = code && Object.prototype.hasOwnProperty.call(PDF_ERROR_MESSAGES, code);
        return { ok: false, kind: "server_error", code: known ? code : null,
          message: known ? PDF_ERROR_MESSAGES[code] : "PDF 요청을 처리하지 못했습니다(HTTP " + res.status + "). 다시 시도하세요." };
      }
      return { ok: false, kind: res.status === 200 ? "invalid_response" : "not_json",
        message: res.status === 200
          ? "받은 응답이 PDF가 아니어서 다운로드하지 않았습니다. 다시 시도하세요."
          : "서버 응답을 해석하지 못했습니다(HTTP " + res.status + "). 잠시 후 다시 시도하세요." };
    }

    // input: { body: JSON 문자열, revision: 요청 당시 결과 버전 }. 공통 실행기(중복 방지·오래된 응답 무시·재시도 없음)
    function createPdfDownloader(deps) {
      return createRunner(deps, {
        validate: function (input) {
          return !!input && isStr(input.body) && utf8Bytes(input.body) <= MAX_PDF_REQUEST_BYTES;
        },
        interpret: function (res) {
          const out = interpretPdfResponse(res);
          if (out.ok) out.data = { blob: res.blob, revision: res.revision };
          return out;
        },
        confirmMessage: PDF_STALE_MESSAGE,
      });
    }

    /* ----- AI 표지 배경(서버 계약: features/product_brochure/cover_image.py, 명세 §28·§29) ----- */
    const COVER_URL = "/api/product-brochure/cover-image";
    const COVER_MOODS = { minimal: "미니멀", premium: "프리미엄", soft_texture: "부드러운 소재감" };
    const COVER_WIDTH = 1024;
    const COVER_HEIGHT = 1536;
    const MAX_COVER_BYTES = 16 * 1024 * 1024;  // 공통 config.IMAGE_MAX_BYTES와 같은 값
    const PNG_SIGNATURE = "\u0089PNG\r\n\u001a\n";
    const COVER_STALE_APPLY_MESSAGE = "이 후보는 지금과 다른 제품 정보(표시명·설명)로 생성됐습니다. 그래도 표지에 적용할까요?";
    const COVER_PDF_BLOCK_MESSAGE = "AI 표지 배경의 PDF 반영은 연결 준비 중입니다. 기본 배경으로 복원하면 다운로드할 수 있습니다.";

    // 생성 조건은 카탈로그 생성과 같은 판정(분석 결과·적용 스냅샷·현재 입력 일치·제품명/설명/표시명 확인)을 재사용
    function evaluateCover(ctx) {
      return evaluateGeneration(ctx);
    }

    // 표지 생성 입력의 제품 정보 서명(분위기 제외). 이미지가 어떤 정보로 만들어졌는지 비교할 때 사용
    function coverInfoSignature(displayName, description) {
      return JSON.stringify([String(displayName), String(description)]);
    }

    // 적용 스냅샷에서 서버가 받는 3개 필드만(클릭 시점 독립 복사본)
    function buildCoverPayload(snapshot, mood) {
      const desc = snapshotField(snapshot, "description");
      return { display_name: String(snapshot.displayName.value).trim(), description: String(desc.value).trim(), mood: mood };
    }

    const COVER_ERROR_MESSAGES = {
      COVER_IMAGE_INVALID_JSON: "표지 배경 요청 형식이 올바르지 않습니다. 다시 시도하세요.",
      COVER_IMAGE_INVALID_INPUT: "표지 배경 생성에 쓸 표시명·제품 설명·분위기 형식이 올바르지 않습니다. 확인한 뒤 다시 적용하세요.",
      COVER_IMAGE_REQUEST_TOO_LARGE: "표지 배경 요청 크기가 허용 범위를 넘습니다. 제품 설명을 줄여 다시 적용하세요.",
      AI_CONFIG_MISSING: "AI 이미지 기능 설정이 준비되지 않았습니다. 관리자에게 문의하세요.",
      AI_AUTH_FAILED: "AI 서비스 인증에 실패했습니다. 관리자에게 문의하세요.",
      AI_PERMISSION_DENIED: "AI 이미지 생성 권한이 없습니다. 관리자에게 문의하세요.",
      AI_MODEL_UNAVAILABLE: "설정된 AI 이미지 모델을 사용할 수 없습니다. 관리자에게 문의하세요.",
      AI_RATE_LIMITED: "AI 호출 한도에 도달했습니다. 잠시 후 다시 시도하세요.",
      AI_CONNECTION_FAILED: "AI 서비스에 연결하지 못했습니다. 잠시 후 다시 시도하세요.",
      AI_TIMEOUT: "AI 이미지 응답 시간이 초과되었습니다. 잠시 후 다시 시도하세요.",
      AI_PROVIDER_ERROR: "AI 서비스에서 오류가 발생했습니다. 잠시 후 다시 시도하세요.",
      AI_BAD_REQUEST: "AI 서비스가 이미지 요청을 처리하지 못했습니다. 입력을 확인하거나 관리자에게 문의하세요.",
      AI_REFUSED: "AI가 이미지 요청을 처리하지 않았습니다. 제품 설명을 확인한 뒤 다시 시도하세요.",
      AI_IMAGE_EMPTY: "AI가 이미지를 돌려주지 않았습니다. 다시 시도하세요.",
      AI_IMAGE_DECODE_FAILED: "생성된 이미지를 해석하지 못했습니다. 다시 시도하세요.",
      AI_IMAGE_INVALID: "생성된 이미지 형식·크기가 올바르지 않아 사용하지 않았습니다. 다시 시도하세요.",
      AI_UNKNOWN_ERROR: "표지 배경을 만들지 못했습니다. 잠시 후 다시 시도하세요.",
    };

    // res: { networkError, aborted } 또는 { status, contentType, json, size, head, decoded, width, height, tooLarge }
    function interpretCoverResponse(res) {
      if (!res || res.networkError) {
        return { ok: false, kind: res && res.aborted ? "timeout" : "network",
          message: res && res.aborted
            ? "응답이 210초 안에 오지 않아 화면에서 기다리기를 중단했습니다. 서버·AI 서비스의 작업이 멈췄거나 과금되지 않았다는 뜻은 아닙니다."
            : "서버에 연결하지 못했습니다. 네트워크 상태를 확인한 뒤 다시 시도하세요." };
      }
      const type = (res.contentType || "").split(";")[0].trim().toLowerCase();
      if (res.status === 200 && type === "image/png") {
        if (res.tooLarge || res.size > MAX_COVER_BYTES) {
          return { ok: false, kind: "invalid_response", message: "받은 이미지가 허용 크기(16 MiB)를 넘어 사용하지 않았습니다." };
        }
        if (!(res.size > 0) || res.head !== PNG_SIGNATURE || !res.decoded) {
          return { ok: false, kind: "invalid_response", message: "받은 파일이 올바른 PNG 이미지가 아니어서 사용하지 않았습니다." };
        }
        if (res.width !== COVER_WIDTH || res.height !== COVER_HEIGHT) {
          return { ok: false, kind: "invalid_response", message: "받은 이미지 크기가 세로형 1024×1536이 아니어서 사용하지 않았습니다." };
        }
        return { ok: true, data: null };
      }
      if (res.status === 413) {
        return { ok: false, kind: "server_error", code: "COVER_IMAGE_REQUEST_TOO_LARGE", message: COVER_ERROR_MESSAGES.COVER_IMAGE_REQUEST_TOO_LARGE };
      }
      const body = res.json;
      if (isObj(body) && body.ok === false) {
        const code = isObj(body.error) && isStr(body.error.code) ? body.error.code : null;
        const known = code && Object.prototype.hasOwnProperty.call(COVER_ERROR_MESSAGES, code);
        return { ok: false, kind: "server_error", code: known ? code : null,
          message: known ? COVER_ERROR_MESSAGES[code] : "표지 배경 요청을 처리하지 못했습니다(HTTP " + res.status + "). 다시 시도하세요." };
      }
      return { ok: false, kind: res.status === 200 ? "invalid_response" : "not_json",
        message: res.status === 200
          ? "받은 응답이 PNG 이미지가 아니어서 사용하지 않았습니다. 다시 시도하세요."
          : "서버 응답을 해석하지 못했습니다(HTTP " + res.status + "). 잠시 후 다시 시도하세요." };
    }

    // input: { payload: {display_name, description, mood}, infoSignature }. 공통 실행기(중복 방지·오래된 응답 무시·재시도 없음)
    function createCoverGenerator(deps) {
      return createRunner(deps, {
        validate: function (input) {
          const p = input && input.payload;
          return isObj(p) && Object.keys(p).sort().join(",") === "description,display_name,mood" &&
            isStr(p.display_name) && !!p.display_name && isStr(p.description) && !!p.description &&
            Object.prototype.hasOwnProperty.call(COVER_MOODS, p.mood);
        },
        interpret: function (res) {
          const out = interpretCoverResponse(res);
          if (out.ok) out.data = { blob: res.blob, payload: res.payload, infoSignature: res.infoSignature };
          return out;
        },
        confirmMessage: "",
      });
    }

    // 표지 이미지 상태 전이에서 더 이상 아무 곳(후보·적용)도 참조하지 않는 object URL만 해제 대상으로 돌려줍니다.
    // 후보와 적용 이미지가 같은 항목(같은 URL)을 가리킬 수 있으므로 사용 중인 URL은 해제하지 않습니다.
    function coverUrlsToRevoke(prev, next) {
      const urls = function (s) { return [s.candidate, s.applied].filter(Boolean).map(function (e) { return e.url; }); };
      const keep = urls(next);
      return urls(prev).filter(function (u, i, all) { return keep.indexOf(u) < 0 && all.indexOf(u) === i; });
    }

    return {
      COVER_URL: COVER_URL, COVER_MOODS: COVER_MOODS, COVER_WIDTH: COVER_WIDTH, COVER_HEIGHT: COVER_HEIGHT,
      MAX_COVER_BYTES: MAX_COVER_BYTES, PNG_SIGNATURE: PNG_SIGNATURE, COVER_STALE_APPLY_MESSAGE: COVER_STALE_APPLY_MESSAGE,
      COVER_PDF_BLOCK_MESSAGE: COVER_PDF_BLOCK_MESSAGE, COVER_ERROR_MESSAGES: COVER_ERROR_MESSAGES,
      evaluateCover: evaluateCover, coverInfoSignature: coverInfoSignature, buildCoverPayload: buildCoverPayload,
      interpretCoverResponse: interpretCoverResponse, createCoverGenerator: createCoverGenerator, coverUrlsToRevoke: coverUrlsToRevoke,
      PDF_URL: PDF_URL, PDF_FILENAME: PDF_FILENAME, MAX_PDF_REQUEST_BYTES: MAX_PDF_REQUEST_BYTES,
      CATALOG_ITEM_LABELS: CATALOG_ITEM_LABELS, PDF_STALE_MESSAGE: PDF_STALE_MESSAGE, PDF_EDIT_PENDING_MESSAGE: PDF_EDIT_PENDING_MESSAGE,
      PDF_ERROR_MESSAGES: PDF_ERROR_MESSAGES, buildPdfPayload: buildPdfPayload, utf8Bytes: utf8Bytes,
      evaluatePdfDownload: evaluatePdfDownload, interpretPdfResponse: interpretPdfResponse, createPdfDownloader: createPdfDownloader,
      ANALYZE_URL: ANALYZE_URL, MAX_FILE_BYTES: MAX_FILE_BYTES, REPLACE_MESSAGE: REPLACE_MESSAGE,
      GROUPS: GROUPS, EXAMPLE_FIELDS: EXAMPLE_FIELDS, FIELD_KEYS: FIELD_KEYS,
      createFields: createFields, createFieldsFromAnalysis: createFieldsFromAnalysis, validateAnalysis: validateAnalysis,
      setValue: setValue, setConfirmed: setConfirmed, setVirtual: setVirtual,
      isDirty: isDirty, summarize: summarize, validateFile: validateFile, formatSize: formatSize,
      interpretResponse: interpretResponse, createAnalyzer: createAnalyzer,
      GENERATE_URL: GENERATE_URL, MAX_VALUE_CHARS: MAX_VALUE_CHARS, FIELD_LABEL: FIELD_LABEL, REGENERATE_MESSAGE: REGENERATE_MESSAGE,
      originOf: originOf, inputSignature: inputSignature, createSnapshot: createSnapshot,
      suggestDisplayName: suggestDisplayName, validateDisplayName: validateDisplayName,
      REGENERATE_EDITED_MESSAGE: REGENERATE_EDITED_MESSAGE, OUTPUT_LIMITS: OUTPUT_LIMITS,
      cloneData: cloneData, editableEntries: editableEntries, editValues: editValues, validateEdits: validateEdits,
      applyEdits: applyEdits, editedIds: editedIds, isEditDirty: isEditDirty, describeUserEdits: describeUserEdits,
      MAX_DISPLAY_NAME_CHARS: MAX_DISPLAY_NAME_CHARS,
      evaluateGeneration: evaluateGeneration, buildGeneratePayload: buildGeneratePayload,
      validateGeneration: validateGeneration, interpretGenerateResponse: interpretGenerateResponse,
      createGenerator: createGenerator, isResultStale: isResultStale, describeReviewFlags: describeReviewFlags,
    };
  })();

  // 개발용 로직 점검(Node)에서 불러올 때는 DOM 연결을 건너뜁니다.
  if (typeof module === "object" && module.exports) {
    module.exports = Review;
    return;
  }

  /* ---------- 화면 연결 ---------- */
  const FEATURE_ID = "product_brochure";
  // 화면에서 기다리는 최대 시간. 서버 공통 timeout(PDF 120초, 텍스트 60초)보다 길게 둡니다.
  // 중단해도 서버 처리·과금이 취소된다는 보장은 없습니다.
  const REQUEST_TIMEOUT_MS = 180000;
  const GENERATE_TIMEOUT_MS = 120000;
  // PDF 응답 대기 상한. 화면에서 기다리기를 멈출 뿐 서버의 렌더링 종료를 보장하지 않습니다.
  const PDF_TIMEOUT_MS = 30000;
  const panel = document.querySelector('[data-feature-panel="' + FEATURE_ID + '"]');
  if (!panel) return;

  const form = panel.querySelector("form");
  const fileInput = panel.querySelector("#product_brochure-file");
  const fileStatus = panel.querySelector("[data-file-status]");
  const fileInfo = panel.querySelector("[data-file-info]");
  const fileName = panel.querySelector("[data-file-name]");
  const fileSize = panel.querySelector("[data-file-size]");
  const analyzeBtn = panel.querySelector("[data-analyze]");
  const analyzeStatus = panel.querySelector("[data-analyze-status]");
  const analyzeError = panel.querySelector("[data-analyze-error]");
  const loadExampleBtn = panel.querySelector("[data-load-example]");
  const reviewCard = panel.querySelector("[data-review-card]");
  const reviewEmpty = panel.querySelector("[data-review-empty]");
  const review = panel.querySelector("[data-review]");
  const exampleNotice = panel.querySelector("[data-source-example]");
  const analysisNotice = panel.querySelector("[data-source-analysis]");
  const analysisMeta = panel.querySelector("[data-analysis-meta]");
  const reviewNotes = panel.querySelector("[data-review-notes]");
  const groupsRoot = panel.querySelector("[data-review-groups]");
  const applyBtn = panel.querySelector("[data-apply]");
  const applyStatus = panel.querySelector("[data-apply-status]");
  const generateBtn = panel.querySelector("[data-generate]");
  const generateStatus = panel.querySelector("[data-generate-status]");
  const generateError = panel.querySelector("[data-generate-error]");
  const resultOpenBtn = panel.querySelector("[data-result-open]");
  const resultStatus = panel.querySelector("[data-result-status]");
  const pdfBtn = panel.querySelector("[data-pdf-download]");
  const pdfStatus = panel.querySelector("[data-pdf-status]");
  const pdfError = panel.querySelector("[data-pdf-error]");
  const coverGenerateBtn = panel.querySelector("[data-cover-generate]");
  const coverRestoreBtn = panel.querySelector("[data-cover-restore]");
  const coverMoods = panel.querySelector("[data-cover-moods]");
  const coverStatus = panel.querySelector("[data-cover-status]");
  const coverAppliedStatus = panel.querySelector("[data-cover-applied-status]");
  const coverError = panel.querySelector("[data-cover-error]");
  const coverCandidateBox = panel.querySelector("[data-cover-candidate]");
  const coverCandidateImg = panel.querySelector("[data-cover-candidate-img]");
  const coverCandidateTitle = panel.querySelector("[data-cover-candidate-title]");
  const coverCandidateTagline = panel.querySelector("[data-cover-candidate-tagline]");
  const coverCandidateMeta = panel.querySelector("[data-cover-candidate-meta]");
  const coverCandidateStale = panel.querySelector("[data-cover-candidate-stale]");
  const coverApplyBtn = panel.querySelector("[data-cover-apply]");
  const coverApplyHint = panel.querySelector("[data-cover-apply-hint]");
  const coverDiscardBtn = panel.querySelector("[data-cover-discard]");
  const displayNameBox = panel.querySelector("[data-display-name]");
  const displayNameInput = panel.querySelector("#product_brochure-display-name");
  const displayNameConfirm = panel.querySelector("#product_brochure-display-name-confirm");
  const displayNameHint = panel.querySelector("[data-display-name-hint]");

  let fields = null;          // 현재 검토 중인 항목(브라우저 메모리)
  let fieldsSource = null;    // "example" | "analysis"
  let fieldsVersion = 0;      // 파일 교체·새 분석·예시 불러오기마다 증가(이전 적용·결과 재사용 방지)
  let applied = null;         // "확인 내용 적용" 시점의 요약
  let snapshot = null;        // "확인 내용 적용" 시점의 생성 입력 스냅샷(독립 복사본)
  // 마지막 성공한 생성 결과 { original: AI 원본, current: 미리보기 적용본, editedIds, signature, version }
  // original·current는 서로 독립 복사본. 편집은 current만 바꾸고 입력 스냅샷·표시명 상태는 건드리지 않습니다.
  let generation = null;
  let editing = null;         // 문구 편집 중 임시 값 { values: {칸 id: 문자열} }(적용 전)
  let lastFile = null;        // 파일 교체 취소 시 되돌릴 이전 선택
  let busy = false;           // PDF 분석 중
  let generating = false;     // 카탈로그 생성 중
  let pdfBusy = false;        // 카탈로그 PDF 요청 중
  // 미리보기 적용본(generation.current)이 바뀔 때마다 증가: 생성 성공·편집 적용·원문 복원.
  // 다운로드 요청 표시는 요청 당시 버전에만 연결합니다(이후 수정본에 그대로 적용하지 않음).
  let resultRevision = 0;
  let downloadedRevision = null;
  // AI 표지 배경(브라우저 메모리만). 항목 { url(object URL), payload(요청 3개 필드), infoSignature, mood }
  // candidate: 마지막으로 성공한 생성 후보, applied: 사용자가 "표지에 적용"한 이미지. 둘이 같은 항목일 수 있음
  let coverBusy = false;      // 표지 배경 생성 요청 중
  let cover = { candidate: null, applied: null };
  const COVER_TIMEOUT_MS = 210000; // 서버 공통 이미지 timeout(180초)보다 길게. 중단해도 공급자 작업 중단·미과금 보장 없음
  // 카탈로그 표시명(원본 제품명과 별도). edited: 사용자가 직접 고쳤으면 제품명 수정 시 제안값으로 덮지 않음
  let displayName = { value: "", confirmed: false, edited: false, suggestion: null };

  function currentSignature() {
    return fields ? Review.inputSignature(fields, displayName) : null;
  }

  function working() {
    return busy || generating || pdfBusy || coverBusy;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text; // AI·사용자 문자열은 항상 텍스트로만 넣습니다.
    return node;
  }

  /* 작업 상태: 진행 중 요청·분석 결과·생성 초안(재요청 비용)은 보호, 예시는 수정했을 때만 보호.
     setResult는 쓰지 않습니다(PDF 다운로드 뒤에도 생성 결과·편집본이 남으므로 setDraft 보호를 유지).
     조건을 OR로 묶어 한 상태 변화로 보호가 꺼지지 않게 합니다. */
  function syncWork() {
    const protect = working() || !!generation || !!editing || !!cover.candidate || !!cover.applied ||
      (!!fields && (fieldsSource === "analysis" || Review.isDirty(fields)));
    AppShell.work.setDraft(FEATURE_ID, protect);
  }

  /* 파일 선택 */
  function currentFile() {
    return fileInput.files[0] || null;
  }

  function renderFile(file) {
    const result = Review.validateFile(file);
    fileStatus.textContent = result.message;
    fileStatus.className = result.ok || result.code === "none" ? "field-hint" : "field-error";
    if (result.ok || result.code === "none") fileInput.removeAttribute("aria-invalid");
    else fileInput.setAttribute("aria-invalid", "true");
    if (file) {
      fileName.textContent = file.name;
      fileSize.textContent = Review.formatSize(file.size);
      fileInfo.hidden = false;
    } else {
      fileInfo.hidden = true;
    }
    syncControls();
  }

  function restoreFile(file) {
    const dt = new DataTransfer();
    if (file) dt.items.add(file);
    fileInput.files = dt.files;
  }

  fileInput.addEventListener("change", function () {
    const file = currentFile();
    // 새 파일을 고르면 기존 검토 내용을 새 PDF의 결과로 보지 않고 정리합니다.
    if (file && file !== lastFile && fields) {
      if (Review.isDirty(fields) &&
          !window.confirm("새 PDF를 선택하면 현재 확인·수정한 내용이 초기화됩니다. 계속할까요?")) {
        restoreFile(lastFile); // 공통 shell의 입력 감지는 이 뒤에 실행되어 되돌린 상태를 반영합니다.
        return;
      }
      clearReview();
    }
    lastFile = file;
    hideError();
    renderFile(file);
  });

  /* 조작 가능 상태: 분석·생성 중에는 입력을 바꾸는 조작을 모두 잠급니다 */
  function syncControls() {
    const valid = Review.validateFile(currentFile()).ok;
    const locked = working();
    analyzeBtn.disabled = locked || !valid;
    fileInput.disabled = locked;
    loadExampleBtn.disabled = locked;
    applyBtn.disabled = locked;
    groupsRoot.querySelectorAll("fieldset").forEach(function (fs) { fs.disabled = locked; });
    displayNameInput.disabled = locked;
    displayNameConfirm.disabled = locked;
    reviewCard.setAttribute("aria-busy", locked ? "true" : "false");
    analyzeStatus.replaceChildren();
    if (busy) {
      analyzeStatus.append(el("span", "spinner"), document.createTextNode(" PDF를 분석하고 있습니다. 최대 몇 분 걸릴 수 있습니다."));
    } else if (generating) {
      analyzeStatus.textContent = "카탈로그 문구를 생성하는 중에는 파일을 바꾸거나 분석할 수 없습니다.";
    } else if (pdfBusy) {
      analyzeStatus.textContent = "PDF를 만드는 중에는 파일을 바꾸거나 분석할 수 없습니다.";
    } else if (coverBusy) {
      analyzeStatus.textContent = "AI 표지 배경을 만드는 중에는 파일을 바꾸거나 분석할 수 없습니다.";
    } else {
      analyzeStatus.textContent = valid
        ? "분석을 요청하면 PDF가 서버로 전송되어 OpenAI API로 분석됩니다."
        : "10 MiB 이하의 PDF를 선택하면 분석할 수 있습니다.";
    }
    syncGenerate();
  }

  /* 카탈로그 생성 버튼·안내 */
  function generationContext() {
    return {
      source: fieldsSource, snapshot: snapshot, version: fieldsVersion,
      currentSignature: currentSignature(), busy: working(),
    };
  }

  function syncGenerate() {
    const ev = Review.evaluateGeneration(generationContext());
    generateBtn.disabled = !ev.ok;
    generateStatus.replaceChildren();
    if (generating) {
      generateStatus.append(el("span", "spinner"), document.createTextNode(" 카탈로그 문구를 생성하고 있습니다."));
    } else if (!ev.ok) {
      generateStatus.textContent = ev.message;
    } else {
      const names = function (list) { return list.map(function (x) { return Review.FIELD_LABEL[x.key || x]; }).join(", "); };
      generateStatus.textContent = "포함: " + names(ev.included) +
        (ev.excluded.length ? " · 제외(미확인·빈 값): " + names(ev.excluded) : "") +
        ". 사용자 확인은 공식 사양·사실 검증을 뜻하지 않습니다.";
    }
    syncResultStatus();
  }

  function syncResultStatus() {
    resultOpenBtn.disabled = !generation || working(); // PDF·표지 요청 중에는 편집·원문 복원을 열지 않음
    syncPdf();
    syncCover();
    resultStatus.replaceChildren();
    if (!generation) {
      resultStatus.textContent = "아직 생성 결과가 없습니다.";
      resultStatus.className = "field-hint";
      return;
    }
    const stale = Review.isResultStale(generation, generationContext());
    resultStatus.className = stale ? "field-error" : "field-hint";
    // 입력 변경 경고(stale)와 출력 문구 수정은 별개로 안내합니다. 출력 수정으로 입력 경고를 없애지 않습니다.
    resultStatus.textContent = (stale
      ? "마지막 생성 결과가 현재 입력과 다를 수 있습니다. 결과를 열어 볼 수 있지만, 현재 입력으로 만들려면 다시 적용·생성하세요."
      : "생성 결과(번역·내용 검토가 필요한 초안)를 \"생성 결과 보기\"로 확인할 수 있습니다.") +
      (generation.editedIds.length ? " 직접 수정한 문구가 있습니다(재검토 필요)." : "") +
      (editing ? " 적용하지 않은 편집 내용이 있습니다." : "");
  }

  function showGenerateError(out) {
    generateError.replaceChildren(
      el("p", "notice-title", "카탈로그 문구 생성에 실패했습니다"),
      el("p", "", out.message),
      el("p", "", "적용한 항목과 기존 생성 결과는 그대로 남아 있습니다. 다시 시도할 수 있습니다."));
    generateError.hidden = false;
  }

  function hideGenerateError() {
    generateError.hidden = true;
    generateError.replaceChildren();
  }

  /* PDF 다운로드 버튼·안내 */
  function pdfEvaluation() {
    const body = generation ? JSON.stringify(Review.buildPdfPayload(generation.current)) : "";
    return Review.evaluatePdfDownload({
      hasResult: !!generation, editDirty: editDirty(), busy: working(), bodyBytes: Review.utf8Bytes(body),
      coverApplied: !!cover.applied, // 적용한 AI 표지 배경은 아직 PDF에 전달하지 않으므로 다운로드를 막음
    });
  }

  function syncPdf() {
    const ev = pdfEvaluation();
    pdfBtn.disabled = !ev.ok;
    pdfBtn.setAttribute("aria-busy", pdfBusy ? "true" : "false");
    pdfStatus.replaceChildren();
    if (pdfBusy) {
      pdfStatus.append(el("span", "spinner"), document.createTextNode(" PDF 만드는 중…"));
    } else if (!ev.ok) {
      pdfStatus.textContent = ev.message;
    } else if (downloadedRevision === resultRevision) {
      pdfStatus.textContent = "다운로드 요청됨 · 저장 여부는 브라우저에서 확인하세요. 문구를 수정·복원하거나 다시 생성하면 새로 다운로드해야 합니다.";
    } else {
      pdfStatus.textContent = "현재 미리보기에 적용된 문구로 A4 4쪽 PDF를 만듭니다. AI 검토 표시·사용자 수정 문구가 검토 완료되었다는 뜻은 아닙니다." +
        (Review.isResultStale(generation, generationContext()) ? " 이 결과는 현재 입력과 다를 수 있습니다(다운로드 전에 확인)." : "");
    }
  }

  function showPdfError(out) {
    pdfError.replaceChildren(
      el("p", "notice-title", "PDF를 다운로드하지 못했습니다"),
      el("p", "", out.message),
      el("p", "", "입력·생성 결과·적용된 문구는 그대로 남아 있습니다. 다시 시도할 수 있습니다."));
    pdfError.hidden = false;
  }

  function hidePdfError() {
    pdfError.hidden = true;
    pdfError.replaceChildren();
  }

  /* AI 표지 배경 버튼·안내 */
  function selectedCoverMood() {
    const checked = coverMoods.querySelector("input:checked");
    return checked ? checked.value : "minimal";
  }

  // 현재 입력(검토 화면의 제품 설명·표시명)의 정보 서명. 이미지가 이전 정보로 생성됐는지 비교할 때 사용
  function currentCoverInfo() {
    if (!fields) return null;
    const desc = fields.filter(function (f) { return f.key === "description"; })[0];
    return Review.coverInfoSignature(String(displayName.value).trim(), desc ? String(desc.value).trim() : "");
  }

  function coverStale(entry) {
    return !!entry && entry.infoSignature !== currentCoverInfo();
  }

  function syncCover() {
    const ev = Review.evaluateCover(generationContext());
    coverGenerateBtn.disabled = !ev.ok;
    coverGenerateBtn.setAttribute("aria-busy", coverBusy ? "true" : "false");
    coverMoods.disabled = working();
    coverStatus.replaceChildren();
    if (coverBusy) {
      coverStatus.append(el("span", "spinner"), document.createTextNode(" AI 표지 배경을 만드는 중… (최대 3분 30초)"));
    } else if (!ev.ok) {
      coverStatus.textContent = ev.message;
    } else {
      coverStatus.textContent = "생성할 때마다 API 비용이 발생합니다. 결과는 후보로만 표시되며 표지에 자동 적용되지 않습니다.";
    }
    coverRestoreBtn.disabled = !cover.applied || working();
    coverAppliedStatus.textContent = cover.applied
      ? "생성 결과 미리보기 1쪽 표지에 AI 배경 적용됨(분위기: " + Review.COVER_MOODS[cover.applied.mood] + ")." +
        (coverStale(cover.applied) ? " 지금과 다른 제품 정보(표시명·설명)로 생성된 이미지입니다." : "")
      : "표지는 기본 콘셉트 배경을 사용합니다.";

    const c = cover.candidate;
    coverCandidateBox.hidden = !c;
    if (!c) {
      coverCandidateImg.removeAttribute("src"); // 해제한 object URL을 숨은 요소가 계속 가리키지 않게
      return;
    }
    if (coverCandidateImg.getAttribute("src") !== c.url) coverCandidateImg.src = c.url;
    coverCandidateImg.alt = "AI 표지 배경 후보(분위기: " + Review.COVER_MOODS[c.mood] + ", 실제 제품 사진 아님)";
    // 실제 표지와 같은 글자: 생성 결과가 있으면 그 표시명·소개, 없으면 요청에 쓴 표시명만
    coverCandidateTitle.textContent = generation ? generation.current.pages.cover.product_name.text : c.payload.display_name;
    coverCandidateTagline.textContent = generation ? generation.current.pages.cover.tagline.text : "";
    coverCandidateMeta.textContent = "분위기: " + Review.COVER_MOODS[c.mood] + " · 1024×1536 · AI 콘셉트 이미지(실제 제품 사진 아님)";
    coverCandidateStale.hidden = !coverStale(c);
    coverCandidateStale.textContent = "이 후보는 지금과 다른 제품 정보(표시명·설명)로 생성됐습니다.";
    const isApplied = c === cover.applied;
    coverApplyBtn.disabled = !generation || isApplied || working();
    coverDiscardBtn.disabled = working();
    coverApplyHint.textContent = !generation
      ? "카탈로그 생성 결과가 있어야 표지에 적용할 수 있습니다. 후보는 미리 볼 수 있습니다."
      : isApplied ? "이 후보가 표지에 적용되어 있습니다." : "적용하면 생성 결과 미리보기 1쪽 표지 배경만 바뀝니다(문구·2~4쪽 이미지는 그대로).";
  }

  // 상태 교체: 이전 상태에서 더 이상 쓰지 않는 object URL만 해제(후보·적용이 같은 URL이면 유지)
  function setCover(next) {
    Review.coverUrlsToRevoke(cover, next).forEach(function (url) { URL.revokeObjectURL(url); });
    cover = next;
    syncCover();
    syncPdf();
    syncWork();
  }

  function showCoverError(out) {
    coverError.replaceChildren(
      el("p", "notice-title", "AI 표지 배경을 만들지 못했습니다"),
      el("p", "", out.message),
      el("p", "", "기존 후보·적용한 표지와 카탈로그 문구는 그대로 남아 있습니다. 다시 시도할 수 있습니다(시도할 때마다 비용 발생)."));
    coverError.hidden = false;
  }

  function hideCoverError() {
    coverError.hidden = true;
    coverError.replaceChildren();
  }

  function showError(out) {
    analyzeError.replaceChildren(
      el("p", "notice-title", "PDF 분석에 실패했습니다"),
      el("p", "", out.message),
      el("p", "", "선택한 파일과 기존 검토 내용은 그대로 남아 있습니다. 다시 시도할 수 있습니다."));
    analyzeError.hidden = false;
  }

  function hideError() {
    analyzeError.hidden = true;
    analyzeError.replaceChildren();
  }

  /* 검토 영역 */
  function badge(text, tone) {
    return el("span", "badge" + (tone ? " badge-" + tone : ""), text);
  }

  const STATUS_BADGE = {
    found: ["문서에서 추출", "info"],
    unclear: ["확인 필요", "warning"],
    not_found: ["문서에서 찾지 못함", ""],
  };

  function renderBadges(field, root) {
    root.replaceChildren();
    if (field.status) {
      const s = STATUS_BADGE[field.status];
      root.append(badge(s[0], s[1]));
    } else {
      root.append(field.provided ? badge("제공됨", "info") : badge("미제공", "warning"));
    }
    if (field.virtual) root.append(badge("가상 정보", "warning"));
    if (field.userAdded) root.append(badge("사용자 추가 정보", "info"));
    if (field.userModified) root.append(badge("사용자 수정", "info"));
    root.append(field.confirmed ? badge("사용자 확인", "success") : badge("미확인"));
  }

  // 항목별로 다른 안내만 표시합니다. 공통 설명은 검토 영역 상단에 있습니다.
  function hintText(field) {
    if (field.userAdded) return "사용자 입력 값입니다. 문서 근거가 아닙니다.";
    if (field.candidates) return "AI가 서로 다른 값을 반환했습니다. 아래 후보를 확인하고 값을 직접 입력하세요.";
    if (field.status === "not_found") return "문서에서 찾지 못한 항목입니다. 입력하면 사용자 추가 정보로 구분됩니다.";
    if (field.status === "unclear") return "AI가 확실히 읽지 못했거나 근거가 부족합니다. 근거와 원문을 확인하세요.";
    if (!field.status && !field.provided) return "미제공 항목입니다. 입력하면 사용자 추가 정보로 구분됩니다.";
    return "";
  }

  function renderDetails(field) {
    const box = el("div", "product_brochure-details");
    if (field.candidates) {
      const list = el("ul", "product_brochure-list");
      field.candidates.forEach(function (c) { list.append(el("li", "", c === null ? "(값 없음)" : c)); });
      box.append(el("p", "product_brochure-detail-title", "후보 값(확정 아님)"), list);
    }
    if (field.evidence.length) {
      const list = el("ul", "product_brochure-list");
      field.evidence.forEach(function (e) {
        const item = el("li");
        item.append(el("span", "product_brochure-page", e.page === null ? "페이지 없음" : "p." + e.page));
        if (!e.pageInRange) item.append(document.createTextNode(" "), badge("범위 밖 페이지", "danger"));
        item.append(document.createTextNode(" "), el("q", "", e.quote === null ? "(발췌 없음)" : e.quote));
        list.append(item);
      });
      box.append(el("p", "product_brochure-detail-title", "AI 제시 근거"), list);
    }
    if (field.note) box.append(el("p", "field-hint", "AI 설명: " + field.note));
    field.serverNotes.forEach(function (n) { box.append(el("p", "field-hint", "서버 검토: " + n)); });
    return box.childNodes.length ? box : null;
  }

  function renderField(field) {
    const id = FEATURE_ID + "-field-" + field.key;
    const wrap = el("div", "field product_brochure-item" + (field.multiline ? " product_brochure-item-wide" : ""));
    const label = el("label", "field-label", field.label);
    label.htmlFor = id;
    const input = field.multiline ? el("textarea", "textarea") : el("input", "input");
    if (!field.multiline) input.type = "text";
    input.id = id;
    input.value = field.value;
    input.placeholder = field.provided ? "" : (field.status === "not_found" ? "문서에서 찾지 못함" : "미제공");
    const badges = el("div", "product_brochure-badges");
    badges.setAttribute("aria-live", "polite");
    const hint = el("p", "field-hint");
    hint.id = id + "-hint";

    const choices = el("div", "product_brochure-choices");
    const confirmBox = el("input");
    confirmBox.type = "checkbox";
    confirmBox.id = FEATURE_ID + "-confirm-" + field.key;
    const confirmLabel = el("label", "choice");
    confirmLabel.append(confirmBox, document.createTextNode("사용자 확인"));
    const virtualBox = el("input");
    virtualBox.type = "checkbox";
    virtualBox.id = FEATURE_ID + "-virtual-" + field.key;
    virtualBox.disabled = field.sourceVirtual;
    const virtualLabel = el("label", "choice");
    virtualLabel.append(virtualBox, document.createTextNode("가상 정보"));
    choices.append(confirmLabel, virtualLabel);

    function sync() {
      confirmBox.checked = field.confirmed;
      virtualBox.checked = field.virtual;
      const text = hintText(field);
      hint.textContent = text;
      hint.hidden = !text;
      if (text) input.setAttribute("aria-describedby", hint.id);
      else input.removeAttribute("aria-describedby");
      renderBadges(field, badges);
    }

    input.addEventListener("input", function () {
      if (Review.setValue(field, input.value)) changed();
      sync();
    });
    confirmBox.addEventListener("change", function () {
      Review.setConfirmed(field, confirmBox.checked);
      changed();
      sync();
    });
    virtualBox.addEventListener("change", function () {
      Review.setVirtual(field, virtualBox.checked);
      changed();
      sync();
    });

    sync();
    wrap.append(label, badges, input, hint);
    const details = renderDetails(field);
    if (details) wrap.append(details);
    wrap.append(choices);
    return wrap;
  }

  function renderSourceNotice(meta) {
    exampleNotice.hidden = fieldsSource !== "example";
    analysisNotice.hidden = fieldsSource !== "analysis";
    reviewNotes.replaceChildren();
    reviewNotes.hidden = true;
    if (fieldsSource !== "analysis" || !meta) return;
    analysisMeta.textContent = "PDF " + meta.source.page_count + "쪽 · " + Review.formatSize(meta.source.size_bytes) +
      " · 응답 모델 " + meta.model;
    const notes = meta.review_notes.slice();
    if (notes.length || meta.multiple_products) {
      const list = el("ul", "product_brochure-list");
      if (meta.multiple_products) list.append(el("li", "", "복수 제품이 있을 수 있습니다. 각 값이 대상 제품의 정보인지 확인하세요."));
      notes.forEach(function (n) { list.append(el("li", "", (n.source === "ai" ? "AI: " : "서버: ") + n.message)); });
      reviewNotes.append(el("p", "notice-title", "검토 필요 사항"), list);
      reviewNotes.hidden = false;
    }
  }

  function renderReview(meta) {
    groupsRoot.replaceChildren();
    Review.GROUPS.forEach(function (g) {
      const groupFields = fields.filter(function (f) { return f.group === g.key; });
      if (!groupFields.length) return;
      const fieldset = el("fieldset", "fieldset product_brochure-group");
      fieldset.append(el("legend", "field-label", g.label));
      // 공통 .grid: 검토 카드의 실제 폭이 충분할 때만 2열, 좁으면 1열
      const items = el("div", "grid product_brochure-items");
      groupFields.forEach(function (f) { items.append(renderField(f)); });
      fieldset.append(items);
      groupsRoot.append(fieldset);
    });
    renderSourceNotice(meta);
    reviewEmpty.hidden = true;
    review.hidden = false;
  }

  /* 카탈로그 표시명 입력: 원본 제품명을 바꾸지 않고 카탈로그 표지에만 쓰는 값 */
  function renderDisplayName() {
    displayNameBox.hidden = fieldsSource !== "analysis";
    displayNameInput.value = displayName.value;
    displayNameConfirm.checked = displayName.confirmed;
    const check = Review.validateDisplayName(displayName.value);
    const s = displayName.suggestion;
    let hint;
    if (displayName.value.trim() && !check.ok) hint = check.message;
    else if (displayName.edited) hint = "직접 입력한 표시명입니다. 원문 표기와 맞는지 확인한 뒤 체크하세요.";
    else if (s && s.value) hint = "원본 제품명의 라틴 문자 표기(\"" + s.value + "\")를 제안했습니다. 확인하거나 고친 뒤 체크하세요.";
    else if (s && s.candidates.length) hint = "원본 제품명에서 표시명을 하나로 정할 수 없습니다(후보: " + s.candidates.join(" / ") + "). 원문 표기를 직접 입력하세요.";
    else hint = "원본 제품명에 라틴 문자 표기가 없습니다. 원문의 표기를 직접 입력하세요(공식 영문명을 임의로 만들지 마세요).";
    displayNameHint.textContent = hint;
    displayNameHint.className = displayName.value.trim() && !check.ok ? "field-error" : "field-hint";
    if (displayName.value.trim() && !check.ok) displayNameInput.setAttribute("aria-invalid", "true");
    else displayNameInput.removeAttribute("aria-invalid");
  }

  function productNameValue() {
    const f = fields && fields.filter(function (x) { return x.key === "product_name"; })[0];
    return f ? f.value : "";
  }

  function resetDisplayName() {
    const s = Review.suggestDisplayName(productNameValue());
    displayName = { value: s.value, confirmed: false, edited: false, suggestion: s };
    renderDisplayName();
  }

  function resuggestDisplayName() {
    // 사용자가 직접 고치지 않았다면 제품명 수정에 맞춰 제안값을 다시 계산합니다(확인은 해제).
    if (displayName.edited || fieldsSource !== "analysis") return;
    const s = Review.suggestDisplayName(productNameValue());
    if (s.value !== displayName.value) displayName.confirmed = false;
    displayName.value = s.value;
    displayName.suggestion = s;
    renderDisplayName();
  }

  displayNameInput.addEventListener("input", function () {
    if (displayNameInput.value === displayName.value) return;
    displayName.value = displayNameInput.value;
    displayName.edited = true;
    displayName.confirmed = false; // 값을 바꾸면 확인 해제
    renderDisplayName();
    changed();
  });

  displayNameConfirm.addEventListener("change", function () {
    if (displayNameConfirm.checked && !Review.validateDisplayName(displayName.value).ok) {
      displayNameConfirm.checked = false; // 유효하지 않은 표시명은 확인할 수 없음
      renderDisplayName();
      return;
    }
    displayName.confirmed = displayNameConfirm.checked;
    changed();
  });

  function changed() {
    resuggestDisplayName();
    if (applied && snapshot && currentSignature() !== snapshot.signature) {
      applyStatus.className = "notice notice-warning";
      applyStatus.replaceChildren(
        el("p", "notice-title", "다시 적용 필요: 적용 이후 수정된 내용이 있습니다"),
        el("p", "", "다시 \"확인 내용 적용\"을 누르면 현재 검토 상태가 반영됩니다. 그 전에는 카탈로그를 생성할 수 없습니다."));
    }
    syncGenerate();
    syncWork();
  }

  function resetApplied() {
    applied = null;
    snapshot = null;
    applyStatus.hidden = true;
    applyStatus.replaceChildren();
  }

  function clearReview() {
    fields = null;
    fieldsSource = null;
    fieldsVersion++; // 이전 적용·생성 결과를 새 입력으로 재사용하지 않음(생성 결과는 지우지 않고 "다를 수 있음" 표시)
    resetApplied();
    resetDisplayName();
    groupsRoot.replaceChildren();
    review.hidden = true;
    reviewEmpty.hidden = false;
    syncGenerate();
    syncWork();
  }

  function showFields(newFields, source, meta) {
    // 검사를 마친 결과로 한 번에 교체합니다.
    fields = newFields;
    fieldsSource = source;
    fieldsVersion++;
    resetApplied();
    resetDisplayName(); // 새 분석·예시마다 표시명 제안을 다시 계산(이전 확인 재사용 없음)
    renderReview(meta);
    syncControls();
    syncWork();
  }

  loadExampleBtn.addEventListener("click", function () {
    if (working()) return;
    if (fields && Review.isDirty(fields) &&
        !window.confirm("개발용 예시를 다시 불러오면 현재 확인·수정한 내용이 사라집니다. 계속할까요?")) {
      return;
    }
    // 선택한 PDF는 읽지 않습니다. 고정 예시로만 화면을 채웁니다.
    hideError();
    showFields(Review.createFields(Review.EXAMPLE_FIELDS), "example", null);
  });

  /* 서버 요청(분석·생성 공통). Content-Type은 본문(FormData·Blob)에 맞춰 브라우저가 정합니다. */
  async function postRequest(url, body, timeoutMs) {
    const controller = new AbortController();
    const timer = setTimeout(function () { controller.abort(); }, timeoutMs);
    try {
      const res = await fetch(url, {
        method: "POST", body: body, signal: controller.signal, headers: { Accept: "application/json" },
      });
      let json;
      if ((res.headers.get("content-type") || "").indexOf("application/json") >= 0) {
        try { json = await res.json(); } catch (e) { json = undefined; }
      }
      return { status: res.status, json: json }; // JSON이 아닌 본문(HTML 등)은 읽거나 표시하지 않음
    } catch (e) {
      return { networkError: true, aborted: !!e && e.name === "AbortError" };
    } finally {
      clearTimeout(timer);
    }
  }

  /* 분석 요청 */
  function sendAnalysis(file) {
    const body = new FormData();
    body.append("source_file", file, "document.pdf"); // 원본 파일명 대신 고정 이름
    return postRequest(Review.ANALYZE_URL, body, REQUEST_TIMEOUT_MS);
  }

  const analyzer = Review.createAnalyzer({
    send: sendAnalysis,
    blocked: function () { return generating || pdfBusy || coverBusy; },
    needsConfirm: function () { return !!fields && Review.isDirty(fields); },
    confirm: function (msg) { return window.confirm(msg); },
    onBusy: function (value) {
      busy = value;
      if (value) hideError();
      syncControls();
      if (!value) AppShell.work.recheckInputs(FEATURE_ID); // 비활성 중 건너뛴 파일 입력 감지를 다시 반영
      syncWork();
    },
    onSuccess: function (data) {
      hideError();
      showFields(Review.createFieldsFromAnalysis(data), "analysis", data);
    },
    onFailure: function (out) {
      showError(out); // 기존 파일·검토 내용·작업 상태는 그대로 둡니다
    },
  });

  form.addEventListener("submit", function () {
    // 기본 제출은 공통 shell이 막습니다. 분석은 사용자가 버튼을 누를 때만 요청합니다(교체 확인 취소 시 요청 없음).
    analyzer.run(currentFile());
  });

  /* 카탈로그 생성 요청: 적용 스냅샷의 8개 항목만 JSON으로 보냅니다(PDF·근거 발췌 재전송 없음) */
  function sendGeneration(snap) {
    const body = new Blob([JSON.stringify(Review.buildGeneratePayload(snap))], { type: "application/json" });
    return postRequest(Review.GENERATE_URL, body, GENERATE_TIMEOUT_MS);
  }

  const generator = Review.createGenerator({
    send: sendGeneration,
    blocked: function () { return busy || pdfBusy || coverBusy; },
    canGenerate: function () { return Review.evaluateGeneration(generationContext()).ok; },
    needsConfirm: function () { return !!generation; },
    // 직접 수정한 문구나 편집 중 내용이 있으면 대체된다는 점을 따로 알립니다.
    confirmMessage: function () {
      return generation && (generation.editedIds.length || editing) ? Review.REGENERATE_EDITED_MESSAGE : Review.REGENERATE_MESSAGE;
    },
    confirm: function (msg) { return window.confirm(msg); },
    onBusy: function (value) {
      generating = value;
      if (value) hideGenerateError();
      syncControls();
      if (!value) AppShell.work.recheckInputs(FEATURE_ID);
      syncWork();
    },
    onSuccess: function (data) {
      // 검사를 통과한 결과로 한 번에 교체하고, 생성 당시 입력 스냅샷과 연결합니다.
      // 성공했을 때만 새 원본으로 교체하고 이전 편집본·편집 중 값은 버립니다(확인은 요청 전에 받음).
      generation = {
        original: Review.cloneData(data), current: Review.cloneData(data), editedIds: [],
        signature: snapshot.signature, version: snapshot.version,
      };
      editing = null;
      resultRevision++;
      renderResult();
      hideGenerateError();
      syncResultStatus();
      syncWork();
    },
    onFailure: function (out) {
      showGenerateError(out); // 적용값·기존 생성 결과는 그대로 둡니다
    },
  });

  generateBtn.addEventListener("click", function () {
    generator.run(snapshot);
  });

  applyBtn.addEventListener("click", function () {
    if (!fields || working()) return;
    // 브라우저 메모리의 검토 상태만 갱신합니다. 서버 전송·저장·카탈로그 생성은 하지 않습니다.
    applied = Review.summarize(fields);
    snapshot = Review.createSnapshot(fields, fieldsSource, fieldsVersion, displayName);
    const title = fieldsSource === "analysis"
      ? "AI 추출 결과의 검토 상태를 이 화면에 반영했습니다"
      : "개발용 예시의 검토 상태를 이 화면에 반영했습니다";
    const scope = fieldsSource === "analysis"
      ? "원문 대조나 사실 검증을 한 것이 아니며 저장·전송하지 않았습니다. "
      : "실제 PDF 분석 결과가 아니며 저장·전송하지 않았습니다. ";
    applyStatus.className = "notice notice-info";
    applyStatus.replaceChildren(
      el("p", "notice-title", title),
      el("p", "", scope + "확인 " + applied.confirmed + "/" + applied.total +
        " · 확인 필요 " + applied.unclear + " · 미제공 " + applied.notProvided + " · 사용자 추가 " + applied.userAdded +
        " · 사용자 수정 " + applied.userModified + " · 가상 정보 " + applied.virtual + "."));
    applyStatus.hidden = false;
    syncGenerate();
  });

  syncControls();

  /* ---------- 카탈로그 미리보기 공통(배율·넘침 검사·이미지) ---------- */
  // 대화상자 하나를 A4 미리보기로 다룹니다. 검토 항목·작업 상태를 읽거나 바꾸지 않습니다.
  const CATALOG_PAGE_WIDTH = 794; // A4 세로 210mm @96dpi

  // options.beforeClose(): 닫기 버튼·Esc 전에 호출, false면 닫지 않음. 탭 숨김으로 닫힐 때는 호출하지 않음(편집 임시 값 보존).
  function createPreview(dialog, openBtn, options) {
    const beforeClose = options && options.beforeClose;
    const closeBtn = dialog.querySelector("[data-catalog-close]");
    const zoomBtn = dialog.querySelector("[data-catalog-zoom]");
    const scroller = dialog.querySelector("[data-catalog-scroller]");
    const pages = dialog.querySelector("[data-catalog-pages]");
    const overflowNote = dialog.querySelector("[data-catalog-overflow]");
    const title = dialog.querySelector("[data-catalog-title]");
    let actualSize = false;
    let observer = null;

    function layout() {
      const style = getComputedStyle(scroller);
      const available = scroller.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
      const gap = parseFloat(getComputedStyle(pages).columnGap) || 0;
      let cols = 1;
      let scale = 1;
      if (!actualSize) {
        // 화면 맞춤: 넓으면 2쪽씩, 좁으면 1쪽. 컨테이너 폭에 맞춰 축소하고 확대하지는 않음
        cols = available >= CATALOG_PAGE_WIDTH * 1.2 + gap ? 2 : 1;
        scale = Math.max(0.2, Math.min(1, (available - gap * (cols - 1)) / (cols * CATALOG_PAGE_WIDTH)));
      }
      pages.style.setProperty("--catalog-scale", String(scale));
      pages.style.setProperty("--catalog-cols", String(cols));
    }

    function checkOverflow() {
      // 페이지 상자(축소 전 레이아웃 크기)를 넘는 내용이 있으면 해당 쪽을 알립니다. 넘침을 숨기지 않습니다.
      if (!dialog.open) return;
      const over = Array.from(pages.querySelectorAll(".catalog-page")).filter(function (page) {
        return page.scrollHeight > page.clientHeight + 1 || page.scrollWidth > page.clientWidth + 1;
      }).map(function (page) { return page.dataset.page + "쪽"; });
      overflowNote.textContent = over.length
        ? over.join(", ") + " 내용이 페이지 영역을 넘습니다. 레이아웃 조정이 필요하며 PDF 출력 준비가 된 상태가 아닙니다."
        : "";
      overflowNote.hidden = !over.length;
    }

    function relayout() {
      layout();
      checkOverflow();
    }

    // 콘셉트 이미지: 로딩 실패 시 깨진 아이콘 대신 대체 안내, 로드·실패 후 넘침 검사를 다시 실행
    const images = Array.from(pages.querySelectorAll("img"));
    function markMissing(img) {
      const figure = img.closest(".catalog-figure");
      if (figure) figure.classList.add("catalog-figure-missing");
    }
    images.forEach(function (img) {
      img.addEventListener("load", checkOverflow);
      img.addEventListener("error", function () { markMissing(img); checkOverflow(); });
    });

    function setZoom(actual) {
      actualSize = actual;
      zoomBtn.setAttribute("aria-pressed", actual ? "true" : "false");
      zoomBtn.textContent = actual ? "화면 맞춤" : "실제 크기(100%)";
      relayout();
    }

    function open() {
      actualSize = false;
      dialog.showModal(); // 모달: 뒤 화면 조작 차단, Esc로 닫힘
      setZoom(false);
      images.forEach(function (img) {
        if (img.complete && img.naturalWidth === 0 && img.getAttribute("src")) markMissing(img);
      });
      if (window.ResizeObserver) {
        observer = new ResizeObserver(relayout);
        observer.observe(scroller);
      }
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(checkOverflow);
      scroller.scrollTop = 0;
      title.focus();
    }

    closeBtn.addEventListener("click", function () {
      if (beforeClose && !beforeClose()) return;
      dialog.close();
    });
    dialog.addEventListener("cancel", function (event) { // Esc
      if (beforeClose && !beforeClose()) event.preventDefault();
    });
    zoomBtn.addEventListener("click", function () { setZoom(!actualSize); });
    dialog.addEventListener("close", function () {
      if (observer) observer.disconnect();
      observer = null;
      openBtn.focus(); // 연 버튼으로 초점 복귀
    });
    // 해시 변경 등으로 탭이 숨겨지면 닫습니다(검토 상태는 그대로).
    AppShell.onHide(FEATURE_ID, function () {
      if (dialog.open) dialog.close();
    });

    return { open: open, checkOverflow: checkOverflow };
  }

  /* ---------- 카탈로그 디자인 시안(고정 예시) ---------- */
  // 고정 예시만 보여 줍니다. 생성 결과·검토 항목·작업 상태를 읽거나 바꾸지 않습니다. 서버 요청·브라우저 저장소 사용 없음.
  const catalogOpenBtn = panel.querySelector("[data-catalog-open]");
  const designPreview = createPreview(panel.querySelector("[data-catalog-dialog]"), catalogOpenBtn);
  catalogOpenBtn.addEventListener("click", function () { designPreview.open(); });

  /* ---------- 카탈로그 생성 결과 미리보기 ---------- */
  // 마지막 성공한 생성 결과만 표시합니다. 시안 대화상자와 DOM을 공유하지 않으며 AI 문자열은 textContent로만 넣습니다.
  const resultDialog = panel.querySelector("[data-result-dialog]");
  const resultPreview = createPreview(resultDialog, resultOpenBtn, { beforeClose: confirmLeaveEdit });
  const resultStale = resultDialog.querySelector("[data-result-stale]");
  const resultFlags = resultDialog.querySelector("[data-result-flags]");
  const resultMeta = resultDialog.querySelector("[data-result-meta]");
  const resultUserEdits = resultDialog.querySelector("[data-result-user-edits]");
  const editOpenBtn = resultDialog.querySelector("[data-result-edit-open]");
  const editSection = resultDialog.querySelector("[data-result-edit]");
  const editFields = resultDialog.querySelector("[data-result-edit-fields]");
  const editErrors = resultDialog.querySelector("[data-result-edit-errors]");
  const editApplyBtn = resultDialog.querySelector("[data-result-edit-apply]");
  const editCancelBtn = resultDialog.querySelector("[data-result-edit-cancel]");
  const editRestoreBtn = resultDialog.querySelector("[data-result-edit-restore]");

  function slot(name) {
    return resultDialog.querySelector('[data-slot="' + name + '"]');
  }

  function slots(name) {
    return Array.from(resultDialog.querySelectorAll('[data-slot="' + name + '"]'));
  }

  // 문구 + (가상이면) 서버 고정 가상 안내 + (검토 표시가 있으면) 표시
  function copyBlock(tag, className, copy) {
    const wrap = el("div", "catalog-copy" + (copy.review_flags.length ? " catalog-flagged" : ""));
    wrap.append(el(tag, className, copy.text));
    if (copy.fictitious_notice) wrap.append(el("p", "catalog-fictitious", copy.fictitious_notice));
    return wrap;
  }

  function infoItem(tag, item, isSupply) {
    const node = el(tag, (isSupply ? "catalog-term" : "catalog-spec") + (item.review_flags.length ? " catalog-flagged" : ""));
    node.dataset.key = item.key;
    if (isSupply) {
      node.append(
        el("p", "catalog-term-label", Review.CATALOG_ITEM_LABELS[item.key]), // PDF와 같은 고정 항목명(AI 라벨 미사용)
        // 짧은 값(수량·기간)은 큰 숫자 위계, 긴 조건 문장은 본문 크기로(넘침 방지, 글자를 과도하게 줄이지 않음)
        el("p", item.value.length <= 24 ? "catalog-term-value" : "catalog-term-value catalog-term-value-long", item.value));
    } else {
      node.append(el("dt", "", Review.CATALOG_ITEM_LABELS[item.key]), el("dd", "", item.value));
    }
    if (item.fictitious_notice) node.append(el(isSupply ? "p" : "dd", "catalog-fictitious", item.fictitious_notice));
    return node;
  }

  function renderInfoPage(page, listName, emptyName, isSupply) {
    const list = slot(listName);
    const empty = slot(emptyName);
    list.replaceChildren();
    page.items.forEach(function (item) { list.append(infoItem(isSupply ? "li" : "div", item, isSupply)); });
    list.hidden = page.empty;
    // 서버 빈 상태 안내(내용을 늘리지 않고 고정 템플릿에 표시)
    empty.replaceChildren();
    if (page.empty) empty.append(el("p", "catalog-status-title", page.empty_message));
    empty.hidden = !page.empty;
  }

  // 미리보기는 항상 적용본(current)을 그립니다. 사용자 수정 위치는 카탈로그 밖 안내에만 표시합니다.
  function renderResult() {
    const data = generation.current;
    const pages = data.pages;
    slot("product_name").textContent = pages.cover.product_name.text;
    slot("tagline").replaceChildren(copyBlock("p", "catalog-lead", pages.cover.tagline));
    slot("paragraphs").replaceChildren.apply(slot("paragraphs"), pages.intro.paragraphs.map(function (c) {
      return copyBlock("p", "catalog-lead", c);
    }));
    // 긴 소개 문단이면 2쪽 이미지 높이를 줄이고 본문 크기 글자로(문장을 자르지 않음)
    resultDialog.querySelector(".catalog-result-intro").classList.toggle("catalog-result-intro-long",
      pages.intro.paragraphs.reduce(function (n, c) { return n + c.text.length; }, 0) > 400);
    renderInfoPage(pages.details, "details", "details-empty", false);
    renderInfoPage(pages.supply, "supply", "supply-empty", true);
    slots("unofficial").forEach(function (node) { node.textContent = data.notices.unofficial; });
    applyCoverToResult(); // 적용한 AI 표지 배경(있으면) 또는 기본 배경

    // AI 생성 당시 서버 검토 표시(review_flags). 사용자가 문구를 고쳐도 자동으로 해제하지 않습니다.
    const flags = Review.describeReviewFlags(data);
    resultFlags.replaceChildren();
    if (flags.length) {
      const list = el("ul", "product_brochure-list");
      flags.forEach(function (f) { list.append(el("li", "", f.where + ": " + f.text)); });
      resultFlags.append(el("p", "notice-title", "AI 생성 검토 표시(점선 테두리 부분)"), list);
    }
    resultFlags.hidden = !flags.length;

    // 사용자 수정 · 재검토 필요(원래 검토 표시와 별도). 수정이 사실·번역 검증 완료를 뜻하지 않습니다.
    const edited = Review.describeUserEdits(data, generation.editedIds);
    resultUserEdits.replaceChildren();
    if (edited.length) {
      const list = el("ul", "product_brochure-list");
      edited.forEach(function (where) { list.append(el("li", "", where + ": 사용자 수정 · 재검토 필요")); });
      resultUserEdits.append(
        el("p", "notice-title", "사용자가 수정한 문구(재검토 필요)"), list,
        el("p", "", "사용자 수정은 사실·번역 검증 완료가 아닙니다. 연결된 출처 항목(source_keys)은 생성 당시 기준이며 수정한 문구의 정확성을 보장하지 않습니다."));
    }
    resultUserEdits.hidden = !edited.length;
    editRestoreBtn.disabled = !generation.editedIds.length && !(editing && Review.editedIds(generation.original, editingPreview()).length);
    const excluded = data.excluded.map(function (e) {
      return Review.FIELD_LABEL[e.key] + (e.reason === "unconfirmed" ? "(미확인)" : "(빈 값)");
    });
    resultMeta.textContent = "응답 모델 " + data.model + " · 프롬프트 " + data.prompt_version +
      " · 사용 항목 " + data.used_keys.map(function (k) { return Review.FIELD_LABEL[k]; }).join(", ") +
      (excluded.length ? " · 제외 " + excluded.join(", ") : "");
  }

  /* 생성 결과 문구 편집: 입력 칸(input/textarea)만 사용, API 호출 없음 */
  function editingPreview() {
    // 편집 중 값이 형식상 적용 가능할 때만 비교용 데이터를 만들고, 아니면 현재 적용본을 기준으로 봅니다.
    const r = Review.applyEdits(generation.original, generation.current, editing.values);
    return r.ok ? r.data : generation.current;
  }

  function renderEditForm(errors) {
    const byId = {};
    (errors || []).forEach(function (e) { byId[e.id] = e.message; });
    editFields.replaceChildren();
    Review.editableEntries(generation.current).forEach(function (entry, n) {
      const id = FEATURE_ID + "-edit-" + n;
      const wrap = el("div", "field");
      const label = el("label", "field-label", entry.where);
      label.htmlFor = id;
      const input = entry.multiline ? el("textarea", "textarea") : el("input", "input");
      if (!entry.multiline) input.type = "text";
      input.id = id;
      input.value = editing.values[entry.id]; // 텍스트로만 표시(HTML 해석 없음). maxlength로 자르지 않음
      const hint = el("p", "field-hint", "최대 " + entry.limit + "자 · 한국어 불가");
      hint.id = id + "-hint";
      const describedBy = [hint.id];
      wrap.append(label, input, hint);
      if (byId[entry.id]) {
        const err = el("p", "field-error", byId[entry.id]);
        err.id = id + "-error";
        describedBy.push(err.id);
        input.setAttribute("aria-invalid", "true");
        wrap.append(err);
      }
      input.setAttribute("aria-describedby", describedBy.join(" "));
      input.addEventListener("input", function () {
        editing.values[entry.id] = input.value;
        syncWork();
        syncPdf(); // 미적용 편집이 있으면 다운로드 불가
      });
      editFields.append(wrap);
    });
    editErrors.replaceChildren();
    if (errors && errors.length) {
      const list = el("ul", "product_brochure-list");
      errors.forEach(function (e) { list.append(el("li", "", e.where + ": " + e.message)); });
      editErrors.append(el("p", "notice-title", "적용하지 않았습니다. 아래 위치를 고쳐 주세요."), list);
    }
    editErrors.hidden = !(errors && errors.length);
  }

  function showEditSection(focusFirst) {
    editSection.hidden = false;
    editOpenBtn.hidden = true;
    renderEditForm();
    if (focusFirst) {
      const first = editFields.querySelector("input, textarea");
      if (first) first.focus();
    }
  }

  function endEdit() {
    editing = null;
    editSection.hidden = true;
    editOpenBtn.hidden = false;
    editFields.replaceChildren();
    editErrors.hidden = true;
    syncWork();
    syncPdf();
  }

  function editDirty() {
    return !!editing && Review.isEditDirty(generation.current, editing.values);
  }

  // 닫기·Esc·편집 취소: 바뀐 값이 있으면 버릴지 확인, 취소하면 편집 상태 유지
  function confirmLeaveEdit() {
    if (!editing) return true;
    if (editDirty() && !window.confirm("편집 중인 변경을 버리고 닫을까요? 미리보기에 적용된 문구는 그대로 남습니다.")) return false;
    endEdit();
    return true;
  }

  editOpenBtn.addEventListener("click", function () {
    if (!generation || working()) return;
    if (!editing) editing = { values: Review.editValues(generation.current) };
    showEditSection(true);
    syncWork();
    syncPdf();
  });

  editCancelBtn.addEventListener("click", function () {
    if (confirmLeaveEdit()) editOpenBtn.focus();
  });

  editApplyBtn.addEventListener("click", function () {
    if (!generation || !editing || working()) return;
    const r = Review.applyEdits(generation.original, generation.current, editing.values);
    if (!r.ok) {
      renderEditForm(r.errors); // 하나라도 틀리면 아무것도 반영하지 않음
      const firstBad = editFields.querySelector('[aria-invalid="true"]');
      if (firstBad) firstBad.focus();
      return;
    }
    // 검증을 통과하면 한 번에 반영. 입력 스냅샷·표시명 상태·메타데이터는 바꾸지 않음
    generation.current = r.data;
    generation.editedIds = r.editedIds;
    resultRevision++; // 이전 다운로드 요청 표시를 수정본에 적용하지 않음
    endEdit();
    renderResult();
    resultPreview.checkOverflow();
    syncResultStatus();
    editOpenBtn.focus();
  });

  editRestoreBtn.addEventListener("click", function () {
    if (!generation || working()) return;
    if (!window.confirm("마지막으로 생성된 AI 원문으로 되돌릴까요? 직접 수정한 문구가 모두 사라집니다.")) return;
    generation.current = Review.cloneData(generation.original);
    generation.editedIds = [];
    resultRevision++;
    if (editing) {
      editing.values = Review.editValues(generation.current);
      renderEditForm();
    }
    renderResult();
    resultPreview.checkOverflow();
    syncResultStatus();
    syncWork();
  });

  resultOpenBtn.addEventListener("click", function () {
    if (!generation) return;
    resultStale.hidden = !Review.isResultStale(generation, generationContext());
    renderResult();
    if (editing) showEditSection(false); // 탭 이동 등으로 닫혔던 편집 임시 값 복원
    else { editSection.hidden = true; editOpenBtn.hidden = false; }
    resultPreview.open();
  });

  /* ---------- 카탈로그 PDF 다운로드 ----------
     클릭 시점의 적용본에서 허용 필드만 뽑아 JSON으로 보냅니다(AI 원본·편집 중 값·항목명·근거 미포함, OpenAI 호출 없음).
     자동 요청·자동 재시도 없음. 실패·취소·시간 초과 시 입력·생성 원본·적용본·편집 상태를 바꾸지 않습니다. */
  async function sendPdf(input) {
    const controller = new AbortController();
    const timer = setTimeout(function () { controller.abort(); }, PDF_TIMEOUT_MS);
    try {
      const res = await fetch(Review.PDF_URL, {
        method: "POST", body: new Blob([input.body], { type: "application/json" }), signal: controller.signal,
        headers: { Accept: "application/pdf, application/json" },
      });
      const contentType = res.headers.get("content-type") || "";
      const out = { status: res.status, contentType: contentType, revision: input.revision };
      if (contentType.toLowerCase().indexOf("application/pdf") === 0) {
        const blob = await res.blob(); // 본문 수신까지 같은 시간 상한 안에서 기다림
        out.blob = blob;
        out.size = blob.size;
        out.head = String.fromCharCode.apply(null, new Uint8Array(await blob.slice(0, 5).arrayBuffer()));
      } else if (contentType.indexOf("application/json") >= 0) {
        try { out.json = await res.json(); } catch (e) { out.json = undefined; }
      } // 그 밖의 본문(HTML 등)은 읽거나 표시하지 않음
      return out;
    } catch (e) {
      return { networkError: true, aborted: !!e && e.name === "AbortError" };
    } finally {
      clearTimeout(timer);
    }
  }

  const pdfDownloader = Review.createPdfDownloader({
    send: sendPdf,
    blocked: function () { return busy || generating || coverBusy; },
    needsConfirm: function () { return !!generation && Review.isResultStale(generation, generationContext()); },
    confirm: function (msg) { return window.confirm(msg); },
    onBusy: function (value) {
      pdfBusy = value;
      if (value) hidePdfError();
      syncControls();
      if (!value) AppShell.work.recheckInputs(FEATURE_ID);
      syncWork();
    },
    onSuccess: function (data) {
      // 요청 뒤 미리보기 내용이 바뀌었다면(방어 경로) 이전 PDF를 내려받거나 다운로드 표시를 갱신하지 않습니다.
      if (!generation || data.revision !== resultRevision) {
        showPdfError({ message: "요청한 뒤 미리보기 내용이 바뀌어 이전 PDF를 다운로드하지 않았습니다. 다시 다운로드하세요." });
        return;
      }
      hidePdfError();
      AppShell.work.downloadBlob(FEATURE_ID, data.blob, Review.PDF_FILENAME);
      downloadedRevision = data.revision;
      // downloadBlob → markDownloadRequested가 이 탭의 inputs·draft·result를 모두 해제하므로,
      // 남아 있는 생성 결과·편집본·분석 결과·파일 선택 보호를 다시 반영합니다(다른 탭 상태는 건드리지 않음).
      AppShell.work.recheckInputs(FEATURE_ID);
      syncWork();
      syncPdf();
    },
    onFailure: function (out) {
      showPdfError(out);
    },
  });

  pdfBtn.addEventListener("click", function () {
    const ev = pdfEvaluation();
    if (!ev.ok) { syncPdf(); return; } // 미생성·미적용 편집·진행 중·크기 초과·AI 표지 적용 중: 요청하지 않음
    pdfDownloader.run({
      body: JSON.stringify(Review.buildPdfPayload(Review.cloneData(generation.current))), // 클릭 시점 독립 스냅샷
      revision: resultRevision,
    });
  });

  /* ---------- AI 표지 배경 ----------
     버튼 클릭 때만 적용 스냅샷의 표시명·설명과 분위기 3개 필드를 보냅니다(자동 호출·재시도 없음).
     성공한 PNG는 후보로만 표시하고, 사용자가 "표지에 적용"해야 생성 결과 미리보기 1쪽 표지에 반영합니다.
     Blob·object URL은 브라우저 메모리에만 두고 저장소·서버에 저장하지 않습니다. PDF 반영은 후속 작업. */
  const resultCoverImg = resultDialog.querySelector(".catalog-cover-figure img");
  const DEFAULT_COVER_SRC = resultCoverImg.getAttribute("src");
  const DEFAULT_COVER_ALT = resultCoverImg.getAttribute("alt");

  // 생성 결과 미리보기 1쪽 표지에만 반영(고정 시안·2~4쪽 이미지는 그대로). AI 이미지 안내 문구는 템플릿에 항상 있음
  function applyCoverToResult() {
    const src = cover.applied ? cover.applied.url : DEFAULT_COVER_SRC;
    if (resultCoverImg.getAttribute("src") !== src) {
      resultCoverImg.closest(".catalog-figure").classList.remove("catalog-figure-missing");
      resultCoverImg.src = src;
    }
    resultCoverImg.alt = cover.applied
      ? "Imagem de fundo da capa gerada por IA (conceitual, não é o produto real)"
      : DEFAULT_COVER_ALT;
  }

  async function sendCover(input) {
    const controller = new AbortController();
    const timer = setTimeout(function () { controller.abort(); }, COVER_TIMEOUT_MS);
    try {
      const res = await fetch(Review.COVER_URL, {
        method: "POST", body: new Blob([JSON.stringify(input.payload)], { type: "application/json" }),
        signal: controller.signal, headers: { Accept: "image/png, application/json" },
      });
      const contentType = res.headers.get("content-type") || "";
      const out = { status: res.status, contentType: contentType, payload: input.payload, infoSignature: input.infoSignature };
      if (contentType.toLowerCase().indexOf("image/png") === 0) {
        const declared = Number(res.headers.get("content-length"));
        if (declared > Review.MAX_COVER_BYTES) { // 상한을 넘으면 본문을 읽지 않음
          controller.abort();
          out.tooLarge = true;
          return out;
        }
        const blob = await res.blob(); // 본문 수신까지 같은 시간 상한 안에서 기다림
        out.blob = blob;
        out.size = blob.size;
        if (blob.size > 0 && blob.size <= Review.MAX_COVER_BYTES) {
          out.head = String.fromCharCode.apply(null, new Uint8Array(await blob.slice(0, 8).arrayBuffer()));
          try { // 브라우저가 실제로 디코딩할 수 있는지와 해상도 확인
            const bitmap = await createImageBitmap(blob);
            out.decoded = true;
            out.width = bitmap.width;
            out.height = bitmap.height;
            bitmap.close();
          } catch (e) {
            out.decoded = false;
          }
        }
      } else if (contentType.indexOf("application/json") >= 0) {
        try { out.json = await res.json(); } catch (e) { out.json = undefined; }
      } // 그 밖의 본문(HTML 등)은 읽거나 표시하지 않음
      return out;
    } catch (e) {
      return { networkError: true, aborted: !!e && e.name === "AbortError" };
    } finally {
      clearTimeout(timer);
    }
  }

  const coverGenerator = Review.createCoverGenerator({
    send: sendCover,
    blocked: function () { return busy || generating || pdfBusy; },
    needsConfirm: function () { return false; },
    confirm: function () { return true; },
    onBusy: function (value) {
      coverBusy = value;
      if (value) hideCoverError();
      syncControls();
      if (!value) AppShell.work.recheckInputs(FEATURE_ID);
      syncWork();
    },
    onSuccess: function (data) {
      // 검사를 통과한 이미지만 후보로. 표지는 자동으로 바꾸지 않음(적용 이미지 유지)
      hideCoverError();
      setCover({
        candidate: { url: URL.createObjectURL(data.blob), payload: data.payload, infoSignature: data.infoSignature, mood: data.payload.mood },
        applied: cover.applied,
      });
    },
    onFailure: function (out) {
      showCoverError(out); // 기존 후보·적용 이미지·문구는 그대로
    },
  });

  coverGenerateBtn.addEventListener("click", function () {
    if (!Review.evaluateCover(generationContext()).ok) { syncCover(); return; }
    const payload = Review.buildCoverPayload(snapshot, selectedCoverMood()); // 클릭 시점 적용 스냅샷 복사
    coverGenerator.run({ payload: payload, infoSignature: Review.coverInfoSignature(payload.display_name, payload.description) });
  });

  coverApplyBtn.addEventListener("click", function () {
    const c = cover.candidate;
    if (!c || !generation || c === cover.applied || working()) return;
    if (coverStale(c) && !window.confirm(Review.COVER_STALE_APPLY_MESSAGE)) return; // 취소하면 그대로
    setCover({ candidate: c, applied: c }); // 같은 항목(같은 URL)을 후보·적용이 함께 참조
    resultRevision++; // 이전 "다운로드 요청됨" 표시 무효화
    applyCoverToResult();
    syncPdf();
  });

  coverDiscardBtn.addEventListener("click", function () {
    const c = cover.candidate;
    if (!c || working()) return;
    if (c !== cover.applied && !window.confirm("이 후보를 버릴까요? 다시 보려면 새로 생성해야 합니다(비용 발생).")) return;
    setCover({ candidate: null, applied: cover.applied }); // 적용 이미지는 유지(같은 URL이면 해제하지 않음)
  });

  coverRestoreBtn.addEventListener("click", function () {
    if (!cover.applied || working()) return;
    if (cover.applied !== cover.candidate &&
        !window.confirm("적용한 AI 표지 배경을 해제하고 기본 배경으로 되돌릴까요? 이 이미지는 후보로 남아 있지 않아 다시 쓰려면 새로 생성해야 합니다.")) return;
    setCover({ candidate: cover.candidate, applied: null }); // 문구·분석값·후보는 그대로
    resultRevision++;
    applyCoverToResult();
    syncPdf();
  });
})();
