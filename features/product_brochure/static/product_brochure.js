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

    function createRunner(deps, options) {
      let seq = 0;
      let busy = false;

      async function run(input) {
        if (busy) return "busy";
        if (deps.blocked && deps.blocked()) return "blocked";
        if (!options.validate(input)) return "invalid";
        if (deps.needsConfirm() && !deps.confirm(options.confirmMessage)) return "cancelled";
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

    function inputSignature(fields) {
      return JSON.stringify(fields.map(function (f) {
        return [f.key, f.value, !!f.confirmed, !!f.virtual, originOf(f)];
      }));
    }

    // "확인 내용 적용" 시점의 독립 복사본. 원래 항목 객체와 참조를 공유하지 않습니다.
    function createSnapshot(fields, source, version) {
      return {
        source: source,
        version: version,
        signature: inputSignature(fields),
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
      if (!requiredOk) {
        out.reason = "required";
        out.message = "제품명과 제품 설명에 값을 입력하고 \"사용자 확인\"을 체크한 뒤 다시 적용하세요.";
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

    // 서버 엄격 스키마: 8개 key 각각 {key, value, confirmed, virtual, origin}
    function buildGeneratePayload(snapshot) {
      return {
        fields: FIELD_KEYS.map(function (k) {
          const f = snapshotField(snapshot, k);
          return { key: k, value: f.value, confirmed: f.confirmed, virtual: f.virtual, origin: f.origin };
        }),
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
      if (!validKeys(d.used_keys, FIELD_KEYS)) return null;
      if (!REQUIRED_KEYS.every(function (k) { return d.used_keys.indexOf(k) >= 0; })) return null;
      if (!Array.isArray(d.excluded) || !d.excluded.every(function (e) {
        return isObj(e) && FIELD_KEYS.indexOf(e.key) >= 0 && (e.reason === "empty" || e.reason === "unconfirmed");
      })) return null;
      const p = d.pages;
      if (!isObj(p) || !isObj(p.cover) || !isObj(p.intro) || p.cover.page !== 1 || p.intro.page !== 2) return null;
      if (!validCopy(p.cover.product_name, ["product_name"]) || !validCopy(p.cover.tagline, d.used_keys)) return null;
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
        return { ok: false, kind: "server_error", code: known ? code : null,
          message: known ? GENERATE_ERROR_MESSAGES[code] : "생성 요청을 처리하지 못했습니다(HTTP " + res.status + "). 다시 시도하세요." };
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
    };

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

    return {
      ANALYZE_URL: ANALYZE_URL, MAX_FILE_BYTES: MAX_FILE_BYTES, REPLACE_MESSAGE: REPLACE_MESSAGE,
      GROUPS: GROUPS, EXAMPLE_FIELDS: EXAMPLE_FIELDS, FIELD_KEYS: FIELD_KEYS,
      createFields: createFields, createFieldsFromAnalysis: createFieldsFromAnalysis, validateAnalysis: validateAnalysis,
      setValue: setValue, setConfirmed: setConfirmed, setVirtual: setVirtual,
      isDirty: isDirty, summarize: summarize, validateFile: validateFile, formatSize: formatSize,
      interpretResponse: interpretResponse, createAnalyzer: createAnalyzer,
      GENERATE_URL: GENERATE_URL, MAX_VALUE_CHARS: MAX_VALUE_CHARS, FIELD_LABEL: FIELD_LABEL, REGENERATE_MESSAGE: REGENERATE_MESSAGE,
      originOf: originOf, inputSignature: inputSignature, createSnapshot: createSnapshot,
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

  let fields = null;          // 현재 검토 중인 항목(브라우저 메모리)
  let fieldsSource = null;    // "example" | "analysis"
  let fieldsVersion = 0;      // 파일 교체·새 분석·예시 불러오기마다 증가(이전 적용·결과 재사용 방지)
  let applied = null;         // "확인 내용 적용" 시점의 요약
  let snapshot = null;        // "확인 내용 적용" 시점의 생성 입력 스냅샷(독립 복사본)
  let generation = null;      // 마지막 성공한 생성 결과 { data, signature, version }
  let lastFile = null;        // 파일 교체 취소 시 되돌릴 이전 선택
  let busy = false;           // PDF 분석 중
  let generating = false;     // 카탈로그 생성 중

  function working() {
    return busy || generating;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text; // AI·사용자 문자열은 항상 텍스트로만 넣습니다.
    return node;
  }

  /* 작업 상태: 진행 중 요청·분석 결과·생성 초안(재요청 비용)은 보호, 예시는 수정했을 때만 보호.
     다운로드 기능이 없으므로 setResult는 쓰지 않습니다. 조건을 OR로 묶어 한 상태 변화로 보호가 꺼지지 않게 합니다. */
  function syncWork() {
    const protect = working() || !!generation ||
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
    reviewCard.setAttribute("aria-busy", locked ? "true" : "false");
    analyzeStatus.replaceChildren();
    if (busy) {
      analyzeStatus.append(el("span", "spinner"), document.createTextNode(" PDF를 분석하고 있습니다. 최대 몇 분 걸릴 수 있습니다."));
    } else if (generating) {
      analyzeStatus.textContent = "카탈로그 문구를 생성하는 중에는 파일을 바꾸거나 분석할 수 없습니다.";
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
      currentSignature: fields ? Review.inputSignature(fields) : null, busy: working(),
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
    resultOpenBtn.disabled = !generation || generating;
    resultStatus.replaceChildren();
    if (!generation) {
      resultStatus.textContent = "아직 생성 결과가 없습니다.";
      resultStatus.className = "field-hint";
      return;
    }
    const stale = Review.isResultStale(generation, generationContext());
    resultStatus.className = stale ? "field-error" : "field-hint";
    resultStatus.textContent = stale
      ? "마지막 생성 결과가 현재 입력과 다를 수 있습니다. 결과를 열어 볼 수 있지만, 현재 입력으로 만들려면 다시 적용·생성하세요."
      : "생성 결과(번역·내용 검토가 필요한 초안)를 \"생성 결과 보기\"로 확인할 수 있습니다.";
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

  function changed() {
    if (applied && snapshot && Review.inputSignature(fields) !== snapshot.signature) {
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
    blocked: function () { return generating; },
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
    blocked: function () { return busy; },
    canGenerate: function () { return Review.evaluateGeneration(generationContext()).ok; },
    needsConfirm: function () { return !!generation; },
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
      generation = { data: data, signature: snapshot.signature, version: snapshot.version };
      renderResult(data);
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
    snapshot = Review.createSnapshot(fields, fieldsSource, fieldsVersion);
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

  function createPreview(dialog, openBtn) {
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

    closeBtn.addEventListener("click", function () { dialog.close(); });
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
  const resultPreview = createPreview(resultDialog, resultOpenBtn);
  const resultStale = resultDialog.querySelector("[data-result-stale]");
  const resultFlags = resultDialog.querySelector("[data-result-flags]");
  const resultMeta = resultDialog.querySelector("[data-result-meta]");

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
        el("p", "catalog-term-label", item.label),
        // 짧은 값(수량·기간)은 큰 숫자 위계, 긴 조건 문장은 본문 크기로(넘침 방지, 글자를 과도하게 줄이지 않음)
        el("p", item.value.length <= 24 ? "catalog-term-value" : "catalog-term-value catalog-term-value-long", item.value));
    } else {
      node.append(el("dt", "", item.label), el("dd", "", item.value));
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

  function renderResult(data) {
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

    const flags = Review.describeReviewFlags(data);
    resultFlags.replaceChildren();
    if (flags.length) {
      const list = el("ul", "product_brochure-list");
      flags.forEach(function (f) { list.append(el("li", "", f.where + ": " + f.text)); });
      resultFlags.append(el("p", "notice-title", "검토 표시(점선 테두리 부분)"), list);
    }
    resultFlags.hidden = !flags.length;
    const excluded = data.excluded.map(function (e) {
      return Review.FIELD_LABEL[e.key] + (e.reason === "unconfirmed" ? "(미확인)" : "(빈 값)");
    });
    resultMeta.textContent = "응답 모델 " + data.model + " · 프롬프트 " + data.prompt_version +
      " · 사용 항목 " + data.used_keys.map(function (k) { return Review.FIELD_LABEL[k]; }).join(", ") +
      (excluded.length ? " · 제외 " + excluded.join(", ") : "");
  }

  resultOpenBtn.addEventListener("click", function () {
    if (!generation) return;
    resultStale.hidden = !Review.isResultStale(generation, generationContext());
    resultPreview.open();
  });
})();
