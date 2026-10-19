/* Scam Shield frontend. Plain JS, no build step. */
(() => {
  "use strict";

  const SPEECH_LANG = { en: "en-IN", hi: "hi-IN", kn: "kn-IN" };
  const CUE_KEYS = ["police", "money", "otp", "secret", "app", "relative", "prize", "threat"];
  const $ = (id) => document.getElementById(id);

  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
  };

  let lang = ["en", "hi", "kn"].includes(store.get("lang")) ? store.get("lang") : "en";
  let lastResult = null;
  let lastMode = "message";
  const selectedCues = new Set();

  const t = (key) => key.split(".").reduce((o, k) => (o ? o[k] : undefined), I18N[lang]) ?? key;

  // ---------------- language ----------------
  function applyLang() {
    document.documentElement.lang = lang;
    document.title = t("appName");
    document.querySelectorAll("[data-t]").forEach((el) => { el.textContent = t(el.dataset.t); });
    document.querySelectorAll("[data-t-placeholder]").forEach((el) => { el.placeholder = t(el.dataset.tPlaceholder); });
    document.querySelectorAll("[data-lang]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
    renderCues();
    if (lastResult && !$("screen-verdict").hidden) renderVerdict(lastResult);
  }
  document.querySelectorAll("[data-lang]").forEach((b) =>
    b.addEventListener("click", () => { lang = b.dataset.lang; store.set("lang", lang); applyLang(); }));

  // ---------------- screens ----------------
  function show(name) {
    ["home", "coach", "wait", "verdict"].forEach((s) => { $("screen-" + s).hidden = s !== name; });
    window.scrollTo(0, 0);
  }
  document.querySelectorAll("[data-go]").forEach((b) => b.addEventListener("click", () => show(b.dataset.go)));

  function showError(id, msg) { const el = $(id); el.textContent = msg; el.hidden = !msg; }

  // ---------------- voice input ----------------
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognizer = null;
  let activeMic = null;

  function stopMic() {
    if (recognizer) { try { recognizer.stop(); } catch { /* already stopped */ } }
    if (activeMic) {
      activeMic.setAttribute("aria-pressed", "false");
      const label = activeMic.querySelector("span");
      if (label) label.textContent = t("speak");
    }
    recognizer = null; activeMic = null;
    $("mic-status").textContent = "";
  }

  document.querySelectorAll("[data-mic]").forEach((btn) => btn.addEventListener("click", () => {
    if (activeMic === btn) return stopMic();
    stopMic();
    const errId = btn.dataset.mic === "msg" ? "home-error" : "coach-error";
    if (!Recognition) return showError(errId, t("noVoice"));
    const target = $(btn.dataset.mic);
    const base = target.value ? target.value.trimEnd() + " " : "";
    recognizer = new Recognition();
    recognizer.lang = SPEECH_LANG[lang];
    recognizer.interimResults = true;
    recognizer.continuous = true;
    recognizer.onresult = (e) => {
      let text = "";
      for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript;
      target.value = base + text;
    };
    recognizer.onerror = (e) => {
      const msgKey = e.error === "not-allowed" ? "micDenied"
                   : e.error === "no-speech"   ? "micNoSpeech"
                   : "micError";
      stopMic();
      showError(errId, t(msgKey));
    };
    recognizer.onend = () => stopMic();
    activeMic = btn;
    btn.setAttribute("aria-pressed", "true");
    const label = btn.querySelector("span");
    if (label) label.textContent = t("listening");
    $("mic-status").textContent = t("listening");
    showError(errId, "");
    recognizer.start();
  }));

  // ---------------- live coach cues ----------------
  function renderCues() {
    const box = $("cues");
    box.innerHTML = "";
    CUE_KEYS.forEach((key) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "cue";
      b.textContent = t("cues." + key);
      b.setAttribute("aria-pressed", String(selectedCues.has(key)));
      b.addEventListener("click", () => {
        selectedCues.has(key) ? selectedCues.delete(key) : selectedCues.add(key);
        b.setAttribute("aria-pressed", String(selectedCues.has(key)));
        showError("coach-error", "");
      });
      box.appendChild(b);
    });
  }

  // ---------------- API ----------------
  async function post(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }

  async function analyse(body, errId, returnTo) {
    stopMic();
    lastMode = body.mode;
    show("wait");
    try {
      lastResult = await post("/analyse", body);
      renderVerdict(lastResult);
      show("verdict");
      $("verdict-band").focus();
    } catch {
      show(returnTo);
      showError(errId, t("errNet"));
    }
  }

  $("btn-check").addEventListener("click", () => {
    const text = $("msg").value.trim();
    if (!text) return showError("home-error", t("errEmpty"));
    showError("home-error", "");
    analyse({ text, lang, mode: "message", cues: [] }, "home-error", "home");
  });

  $("btn-call").addEventListener("click", () => { show("coach"); });

  $("btn-coach").addEventListener("click", () => {
    if (!selectedCues.size) return showError("coach-error", t("errCue"));
    analyse({ text: $("coach-msg").value.trim(), lang, mode: "live_coach", cues: [...selectedCues] },
      "coach-error", "coach");
  });

  // ---------------- verdict ----------------
  function renderVerdict(r) {
    const band = $("verdict-band");
    band.className = "verdict is-" + r.verdict;
    $("verdict-title").textContent = t("verdict." + r.verdict);

    const live = lastMode === "live_coach" && r.verdict !== "genuine";
    $("advice-now").hidden = !live;
    $("advice-now").textContent = live ? r.advice : "";
    $("advice-block").hidden = live || !r.advice;
    $("advice").textContent = r.advice || "";
    $("explanation").textContent = r.explanation || "";

    const flags = $("flags");
    flags.innerHTML = "";
    (r.red_flags || []).forEach((f) => { const li = document.createElement("li"); li.textContent = f; flags.appendChild(li); });
    $("flags-block").hidden = !(r.red_flags || []).length;

    $("offline-note").hidden = r.source !== "rules";
    $("btn-1930").hidden = r.verdict === "genuine";
    $("btn-alert").hidden = r.verdict === "genuine";

    // "Call my family" — only when verdict is worrying and a number is saved
    const savedPhone = store.get("familyPhone") || "";
    const showCall = r.verdict !== "genuine" && savedPhone;
    const callBtn = $("btn-call-family");
    if (showCall) {
      const dialNum = savedPhone.replace(/[^\d+]/g, "");
      callBtn.href = "tel:" + dialNum;
      callBtn.textContent = t("callFamily");
    }
    callBtn.hidden = !showCall;

    $("sent-text").textContent = r.redacted_text || "";
    $("report-block").hidden = true;
    showError("verdict-error", "");
  }

  $("btn-again").addEventListener("click", () => {
    $("msg").value = ""; $("coach-msg").value = "";
    selectedCues.clear(); renderCues();
    lastResult = null;
    window.speechSynthesis?.cancel();
    show("home");
    $("msg").focus();
  });

  $("btn-read").addEventListener("click", () => {
    if (!lastResult || !window.speechSynthesis) return;
    const r = lastResult;
    const parts = [t("verdict." + r.verdict), r.advice, r.explanation, ...(r.red_flags || [])].filter(Boolean);
    const u = new SpeechSynthesisUtterance(parts.join(". "));
    u.lang = SPEECH_LANG[lang];
    u.rate = 0.9;
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  });

  $("btn-report").addEventListener("click", async () => {
    const block = $("report-block");
    block.hidden = false;
    $("report-steps").textContent = t("checking");
    try {
      const r = await post("/report", { lang, scam_type: lastResult?.scam_type || null, summary: lastResult?.explanation || "" });
      $("report-steps").textContent = r.steps;
    } catch {
      $("report-steps").textContent = t("errNet");
    }
  });

  // ---------------- family alert (confirm first) ----------------
  $("btn-alert").addEventListener("click", () => {
    $("family-phone").value = store.get("familyPhone") || "";
    $("confirm").showModal();
  });
  $("confirm-no").addEventListener("click", () => $("confirm").close());
  // Prevent the form's native submit (no method="dialog") and route Enter to confirm-yes.
  $("confirm-form").addEventListener("submit", (e) => { e.preventDefault(); $("confirm-yes").click(); });

  $("confirm-yes").addEventListener("click", async () => {
    const btn = $("confirm-yes");
    const phone = $("family-phone").value.replace(/[^\d+]/g, "");
    if (phone) store.set("familyPhone", phone); // stays on this device; never sent to the server
    btn.disabled = true;
    const summary = (lastMode === "live_coach" ? t("alertSummaryCall") : t("alertSummaryScam")) +
      (lastResult?.explanation ? ". " + lastResult.explanation : "");
    try {
      const r = await post("/alert", { summary, lang, user_confirmed: true });
      const text = encodeURIComponent(r.message);
      const waNumber = phone.replace(/^\+/, "").replace(/^0/, "").replace(/^(\d{10})$/, "91$1");
      $("alert-text").textContent = r.message;
      $("send-wa").href = `https://wa.me/${waNumber}?text=${text}`;
      $("send-sms").href = `sms:${phone}?&body=${text}`;
      $("confirm").close();
      $("alert-ready").showModal();
    } catch {
      $("confirm").close();
      showError("verdict-error", t("errNet"));
    } finally {
      btn.disabled = false;
    }
  });
  $("ready-close").addEventListener("click", () => $("alert-ready").close());

  // ---------------- OCR (Tesseract.js, on-device) ----------------
  // Language map: UI lang -> Tesseract language code(s). The image never leaves the device.
  const OCR_LANG = { en: "eng", hi: "hin+eng", kn: "kan+eng" };

  function setOcrProgress(msg) {
    const el = $("ocr-progress");
    el.textContent = msg;
    el.hidden = !msg;
  }

  $("btn-ocr").addEventListener("click", () => {
    // Reset and open the file picker
    $("ocr-input").value = "";
    showError("home-error", "");
    setOcrProgress("");
    $("ocr-input").click();
  });

  $("ocr-input").addEventListener("change", async () => {
    const file = $("ocr-input").files[0];
    if (!file) return;

    // Guard: Tesseract.js must be loaded (CDN script at bottom of index.html)
    if (typeof Tesseract === "undefined") {
      showError("home-error", t("ocrError"));
      return;
    }

    setOcrProgress(t("ocrReading"));
    $("btn-ocr").disabled = true;

    try {
      const ocrLang = OCR_LANG[lang] || "eng";
      const { data: { text } } = await Tesseract.recognize(file, ocrLang, {
        // Suppress Tesseract's own verbose console output
        logger: () => {},
      });
      const cleaned = text.replace(/\r\n/g, "\n").trim();
      if (!cleaned) {
        setOcrProgress("");
        showError("home-error", t("ocrEmpty"));
        return;
      }
      $("msg").value = cleaned;
      setOcrProgress(t("ocrDone"));
      $("msg").focus();
    } catch {
      setOcrProgress("");
      showError("home-error", t("ocrError"));
    } finally {
      $("btn-ocr").disabled = false;
      // Clear the input so picking the same file again fires change
      $("ocr-input").value = "";
    }
  });

  // ---------------- share target (PWA Web Share Target) ----------------
  function applyShareParams() {
    const params = new URLSearchParams(window.location.search);
    const shareText = params.get("share_text") || "";
    const shareTitle = params.get("share_title") || "";
    const combined = [shareTitle, shareText].filter(Boolean).join("\n").trim();
    if (!combined) return;
    $("msg").value = combined;
    show("home");
    // Clear the URL params so a refresh doesn't re-fill the field.
    history.replaceState(null, "", "/");
  }

  // ---------------- family number setting ----------------
  (function initFamilySetting() {
    const input = $("setting-family-phone");
    const saved = $("family-setting-saved");
    // Pre-fill from storage
    input.value = store.get("familyPhone") || "";
    let saveTimer = null;
    function saveFamilyPhone() {
      const v = input.value.replace(/[^\d+\s\-()]/g, "").trim();
      input.value = v;
      if (v) store.set("familyPhone", v); else store.set("familyPhone", "");
      // Show "Saved." briefly
      saved.hidden = false;
      clearTimeout(saveTimer);
      saveTimer = setTimeout(() => { saved.hidden = true; }, 2000);
    }
    input.addEventListener("change", saveFamilyPhone);
    input.addEventListener("blur", saveFamilyPhone);
  })();

  // ---------------- start ----------------
  applyLang();
  applyShareParams();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
})();
