"use strict";
/* gst-recon demo UI. No build step. All text from OCR or the model is untrusted: every insertion goes through esc(). */

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const rupee = (n) => (n < 0 ? "-" : "") + "\u20B9" + Math.abs(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const BUCKETS = ["eligible", "blocked", "deferred"];
const OCR_TABS = [["ocr", "Document text (OCR)"], ["register", "Purchase register"], ["gstr2b", "GSTR-2B"], ["bank", "Bank statement"]];

const S = {
  cases: [], caseId: null, detail: null, models: [], model: "base", constrained: true, mode: "live", speed: 1, kind: "e2e", focusDoc: null,
  health: { live: false }, runs: {}, running: false, ctrl: null, doc: null, ocrTab: "ocr", gt: true,
  expanded: new Set(), tableKey: null,
};
const runKey = (caseId = S.caseId, model = S.model, con = S.constrained, kind = S.kind) => `${caseId}|${kind}|${model}|${con ? 1 : 0}`;
const current = () => S.runs[runKey()] || null;

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
  return r.json();
}
const post = (path, body) => api(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });

/* ------------------------------------------------------------------ boot */
async function boot() {
  bindUi();
  await Promise.all([refreshHealth(), loadCases()]);
  await loadModels();
  S.mode = S.health.live ? "live" : "replay";
  syncControls();
  setInterval(refreshHealth, 8000);
  await selectCase(new URLSearchParams(location.search).get("case") || S.cases[0]?.id);
}

async function refreshHealth() {
  try { S.health = await api("/api/health"); } catch { S.health = { live: false }; }
  const el = $("srvStatus"), h = S.health;
  const rv = $("reconVer");
  rv.hidden = !h.reconciler;
  rv.textContent = h.reconciler ? `reconciler ${h.reconciler}` : "";
  el.className = "srv " + (h.live ? "up" : "down");
  el.querySelector("span").textContent = h.live
    ? `SGLang up${h.running != null ? ` \u00B7 ${h.running} running` : ""}`
    : `Offline \u00B7 ${h.recordings || 0} recorded runs`;
  document.querySelector('#modeSeg [data-mode="live"]').disabled = !h.live;
}

async function loadCases() {
  S.cases = await api("/api/cases");
  const sel = $("caseSel");
  sel.innerHTML = S.cases.map((c) => `<option value="${esc(c.id)}">${esc(c.id)} \u00B7 ${c.docs} docs \u00B7 ${esc(c.buyer)}</option>`).join("");
  if (S.caseId) sel.value = S.caseId;
}

async function loadModels() {
  const m = await api("/api/models");
  S.models = m.models;
  if (!S.models.some((x) => x.name === S.model)) S.model = (S.models.find((x) => x.adapter) || S.models[0]).name;
}

/* ------------------------------------------------------------------ controls */
function bindUi() {
  $("caseSel").onchange = (e) => selectCase(e.target.value);
  $("openDirBtn").onclick = () => { $("dirRow").hidden = !$("dirRow").hidden; $("dirInput").focus(); };
  $("dirGo").onclick = openDir;
  $("dirInput").onkeydown = (e) => e.key === "Enter" && openDir();
  $("modeSeg").onclick = (e) => { const b = e.target.closest("button"); if (b && !b.disabled) { S.mode = b.dataset.mode; syncControls(); } };
  $("speedSeg").onclick = (e) => { const b = e.target.closest("button"); if (b) { S.speed = +b.dataset.speed; syncControls(); } };
  $("conSeg").onclick = (e) => { const b = e.target.closest("button"); if (b) { S.constrained = b.dataset.con === "1"; syncControls(); showRun(); } };
  $("kindSeg").onclick = (e) => { const b = e.target.closest("button"); if (b && !b.disabled) { S.kind = b.dataset.kind; S.focusDoc = null; syncControls(); showRun(); } };
  $("callStrip").onclick = (e) => { const b = e.target.closest("button[data-doc]"); if (b) { S.focusDoc = b.dataset.doc; pickDoc(b.dataset.doc); showRun(); } };
  $("modelSeg").onclick = (e) => { const b = e.target.closest("button"); if (b) { S.model = b.dataset.model; syncControls(); showRun(); } };
  $("gtToggle").onchange = (e) => { S.gt = e.target.checked; renderView(current()); };
  $("runBtn").onclick = startRun;
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") $("lightbox").hidden = true;
    if ((e.key === "r" || e.key === "R") && !e.metaKey && !e.ctrlKey && !/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) startRun();
  });
  $("lightbox").onclick = () => ($("lightbox").hidden = true);
  $("scan").onclick = () => {
    const img = $("scan").querySelector("img");
    if (img) { $("lightbox").querySelector("img").src = img.src; $("lightbox").hidden = false; }
  };
  $("recon").addEventListener("click", (e) => {
    const tb = e.target.closest("tbody.row");
    if (!tb) return;
    const id = tb.dataset.id;
    S.expanded.has(id) ? S.expanded.delete(id) : S.expanded.add(id);
    pickDoc(id);
    renderView(current());
  });
}

async function openDir() {
  const msg = $("dirMsg");
  try {
    const r = await post("/api/cases/dir", { path: $("dirInput").value.trim() });
    msg.textContent = `added ${r.added} case${r.added === 1 ? "" : "s"}`;
    await loadCases();
  } catch (e) { msg.textContent = e.message; }
}

function syncControls() {
  const usable = S.models.filter((m) => !m.recorded_only || S.mode === "replay");
  if (!usable.some((m) => m.name === S.model) && usable.length) S.model = (usable.find((m) => m.adapter) || usable[0]).name;
  $("modelSeg").innerHTML = usable.map((m) =>
    `<button data-model="${esc(m.name)}" aria-pressed="${m.name === S.model}" title="${esc(m.name)}">${esc(m.label)}</button>`).join("");
  for (const b of $("kindSeg").children) b.setAttribute("aria-pressed", b.dataset.kind === S.kind);
  for (const b of $("modeSeg").children) b.setAttribute("aria-pressed", b.dataset.mode === S.mode);
  for (const b of $("speedSeg").children) b.setAttribute("aria-pressed", +b.dataset.speed === S.speed);
  for (const b of $("conSeg").children) b.setAttribute("aria-pressed", (b.dataset.con === "1") === S.constrained);
  $("speedField").hidden = S.mode !== "replay";
}

function setBusy(on) {
  S.running = on;
  document.body.classList.toggle("running", on);
  $("runBtn").classList.toggle("busy", on);
  $("runLabel").textContent = on ? "Stop" : "Run reconciliation";
  for (const id of ["caseSel", "openDirBtn"]) $(id).disabled = on;
  for (const b of document.querySelectorAll("#modelSeg button, #kindSeg button, #modeSeg button, #speedSeg button, #conSeg button")) b.disabled = on || (b.dataset.mode === "live" && !S.health.live);
}

/* ------------------------------------------------------------------ left panel: documents */
async function selectCase(id) {
  if (!id) return;
  S.caseId = id;
  $("caseSel").value = id;
  S.detail = await api(`/api/cases/${encodeURIComponent(id)}`);
  const d = S.detail, h = d.header;
  S.gt = d.has_truth ? $("gtToggle").checked : false;
  $("gtSwitch").hidden = !d.has_truth;
  $("caseMeta").textContent = `${h.Buyer || ""} \u00B7 ${(h["Return period"] || "").replace(/^\d+ /, "").replace(/[()]/g, "")} \u00B7 ${d.difficulty || "case"}`;
  S.expanded.clear();
  S.doc = (d.docs.find((x) => x.image) || d.docs[0] || {}).id;
  renderDocs();
  showRun();
}

function pickDoc(id) { S.doc = id; renderDocs(); }

function renderDocs(statusById = lastStatuses()) {
  const d = S.detail;
  if (!d) return;
  $("docTabs").innerHTML = d.docs.map((x) => {
    const st = statusById[x.id];
    return `<button role="tab" data-doc="${esc(x.id)}" aria-selected="${x.id === S.doc}">${esc(x.id)}<span class="kind ${x.image ? "scan" : ""}" title="${x.image ? "scanned image" : "email or WhatsApp text"}"></span>${st ? `<i class="${st}"></i>` : ""}</button>`;
  }).join("");
  for (const b of $("docTabs").children) b.onclick = () => { pickDoc(b.dataset.doc); };
  const doc = d.docs.find((x) => x.id === S.doc) || d.docs[0];
  const scan = $("scan");
  if (doc?.image) {
    scan.className = "scan";
    scan.innerHTML = `<img src="${esc(doc.image)}" alt="Scan of ${esc(doc.id)}"><span class="hint">click to enlarge</span>`;
  } else {
    scan.className = "scan none";
    scan.textContent = "No scan for this document: it arrived as email or WhatsApp text";
  }
  $("ocrTabs").innerHTML = OCR_TABS.filter(([k]) => k === "ocr" || sectionFor(k)).map(([k, label]) =>
    `<button role="tab" data-t="${k}" aria-selected="${k === S.ocrTab}">${esc(label)}</button>`).join("");
  for (const b of $("ocrTabs").children) b.onclick = () => { S.ocrTab = b.dataset.t; renderDocs(); };
  $("ocrText").textContent = S.ocrTab === "ocr" ? (doc?.text || "") : sectionFor(S.ocrTab) || "";
}

function sectionFor(tab) {
  const secs = S.detail?.sections || {};
  const keys = Object.keys(secs).filter((k) => ({ register: /REGISTER/i, gstr2b: /GSTR-2B/i, bank: /BANK/i }[tab]).test(k));
  return keys.map((k) => `=== ${k} ===\n${secs[k]}`).join("\n\n");
}

function lastStatuses() {
  const v = current()?.view;
  if (!v?.diff || !S.gt) return {};
  return Object.fromEntries(v.rows.filter((r) => r.ready.itc).map((r) => [r.doc_id, Object.keys(r.wrong).length ? "bad" : "ok"]));
}

/* ------------------------------------------------------------------ running */
async function startRun() {
  if (S.running) { S.ctrl?.abort(); return; }
  const ctrl = new AbortController();
  S.ctrl = ctrl;
  setBusy(true);
  S.focusDoc = null;
  let run = newRun(S.caseId, S.model, S.constrained, S.mode, S.speed, S.kind);
  S.runs[runKey()] = run;
  showRun();
  const ticker = setInterval(() => tick(run), 90);
  try {
    const res = await fetch("/api/run", { method: "POST", headers: { "content-type": "application/json" }, signal: ctrl.signal,
      body: JSON.stringify({ case_id: S.caseId, model: S.model, constrained: S.constrained, mode: S.mode, speed: S.speed, kind: S.kind }) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const reader = res.body.getReader(), dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl); buf = buf.slice(nl + 1);
        if (line) run = onEvent(run, JSON.parse(line));
      }
    }
  } catch (e) {
    if (e.name === "AbortError") run.aborted = true; else run.error = run.error || e.message;
  }
  clearInterval(ticker);
  run.done = true;
  setBusy(false);
  finishRun(run);
}

function newRun(caseId, model, constrained, mode, speed, kind) {
  return { caseId, model, constrained, mode, speed, kind, text: "", tokens: 0, stats: null, view: null, final: false, error: null,
    aborted: false, done: false, t0: performance.now(), tFirst: null, rev: 0, shownRev: -1, viewLen: -1, recordedAt: null,
    docs: {}, order: [], active: null, stage: "read", traces: null, problems: null, docRev: 0, viewDocRev: -1, autoOpened: false };
}

function onEvent(run, ev) {
  run.rev++;
  if (ev.type === "start") {
    const key = runKey(run.caseId, ev.model, ev.constrained, run.kind);
    if (key !== runKey(run.caseId, run.model, run.constrained, run.kind)) { // a replay can serve a different recorded run than asked for
      delete S.runs[runKey(run.caseId, run.model, run.constrained, run.kind)];
      Object.assign(run, { model: ev.model, constrained: ev.constrained });
      S.runs[key] = run;
      S.model = ev.model; S.constrained = ev.constrained;
      syncControls(); setBusy(true);
    }
    run.mode = ev.mode; run.recordedAt = ev.recorded_at;
    run.order = ev.docs || [];
    for (const id of run.order) run.docs[id] = { id, text: "", tokens: 0, state: "queued", stats: null, valid: null, tFirst: null };
    run.t0 = performance.now();
    showRun();
  } else if (ev.type === "doc_start") {
    run.active = ev.doc_id;
    Object.assign(run.docs[ev.doc_id], { state: "active", t0: performance.now() });
    if (!S.focusDoc) pickDoc(ev.doc_id);
  } else if (ev.type === "tok") {
    run.tFirst ??= performance.now(); run.tokens++;
    const d = ev.doc_id && run.docs[ev.doc_id];
    if (d) { d.tFirst ??= performance.now(); d.tokens++; d.text += ev.t; } else run.text += ev.t;
  } else if (ev.type === "doc_done") {
    const d = run.docs[ev.doc_id];
    Object.assign(d, { state: ev.valid.schema ? "ok" : "bad", stats: ev.stats, valid: ev.valid });
    run.docRev++;
  } else if (ev.type === "doc_error") {
    Object.assign(run.docs[ev.doc_id], { state: "bad", error: ev.message });
  } else if (ev.type === "reconciling") {
    run.stage = "reconcile"; run.active = null;
  } else if (ev.type === "assembled") {
    run.stage = "done"; run.text = ev.text; run.final = true; run.problems = ev.problems;
    const t = ev.trace;
    run.traces = Object.fromEntries(Object.entries(t.decisions).map(([id, d]) => [id, { ...d, link: t.links?.[id] }]));
  } else if (ev.type === "done") {
    run.stats = ev.stats;
  } else if (ev.type === "error") {
    run.error = ev.message;
  }
  return run;
}

const hybridRun = (run) => run?.kind === "hybrid";

function tick(run) {
  if (S.runs[runKey()] !== run) return;
  if (run.rev !== run.shownRev) { renderStream(run); renderStats(run); renderStrip(run); }
  if (hybridRun(run)) { if (!run.final && run.docRev !== run.viewDocRev) pumpPartial(run); }
  else if (run.text.length !== run.viewLen) pumpView(run);
}

function finishRun(run) {
  run.final = !run.aborted && !run.error;
  run.viewLen = -1;
  run.done = true;
  renderStream(run); renderStats(run); renderStrip(run);
  if (run.text) pumpView(run, true); else showRun();
}

// Hybrid, before the reconciler has run: rows from the documents the model has finished (extraction only, no ITC yet).
function pumpPartial(run) {
  run.viewDocRev = run.docRev;
  const rows = [];
  for (const id of run.order) {
    const d = run.docs[id];
    let j = null;
    if (d.state === "ok" || d.state === "bad") { try { j = JSON.parse(d.text); } catch { /* not JSON: no row */ } }
    if (!j) continue;
    rows.push({ doc_id: id, ready: { extraction: true, match: false, itc: false }, supplier: j.supplier_name, gstin: j.supplier_gstin,
      invoice_no: j.invoice_no, date: j.invoice_date, doc_type: j.doc_type, total: j.total, lines: (j.line_items || []).map((l) => l.description),
      in_books: false, in_2b: false, paid: false, vouchers: [], gstr2b: null, payments: [], flags: [], eligible: 0, blocked: 0, deferred: 0,
      heads: { eligible: {}, blocked: {}, deferred: {} }, reasons: [], wrong: {}, missing: false, trace: null });
  }
  run.view = { rows, headline: { eligible: 0, blocked: 0, deferred: 0 }, headline_final: false, truth_headline: null, diff: null, validity: null };
  renderView(run);
}

let viewBusy = false;
async function pumpView(run, force = false) {
  if (viewBusy && !force) return;
  viewBusy = true;
  try {
    for (let again = true; again;) {
      const len = run.text.length, final = run.final;
      run.viewLen = len;
      run.view = await post("/api/view", { case_id: run.caseId, text: run.text, final, traces: run.traces });
      again = run.text.length !== len || run.final !== final;
      if (S.runs[runKey()] === run) { renderView(run); renderDocs(); renderStats(run); openInteresting(run); }
    }
  } catch (e) { console.error(e); }
  viewBusy = false;
}

// After a hybrid run, open the invoices the reconciler blocked or deferred: that is the audit trail.
function openInteresting(run) {
  if (!hybridRun(run) || !run.done || run.autoOpened || !run.view) return;
  run.autoOpened = true;
  const hits = run.view.rows.filter((r) => r.blocked > 0 || r.deferred > 0).slice(0, 2);
  for (const r of hits) S.expanded.add(r.doc_id);
  if (hits.length) { pickDoc(hits[0].doc_id); renderView(run); }
}

/* ------------------------------------------------------------------ middle panel */
function showRun() {
  const run = current();
  const hy = S.kind === "hybrid";
  $("midTitle").innerHTML = hy ? "2 &middot; Model reads each doc" : "2 &middot; Model writes JSON";
  $("rightTitle").innerHTML = hy ? "3 &middot; Code reconciles" : "3 &middot; Reconciliation";
  renderStream(run); renderStats(run); renderStrip(run); renderView(run); renderDocs();
  for (const b of $("conSeg").children) b.setAttribute("aria-pressed", (b.dataset.con === "1") === S.constrained);
}

const TOKEN_RE = /("(?:\\.|[^"\\])*(?:"|$)(?:\s*:)?)|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|\b(true|false|null)\b|([{}\[\],:])/g;
function highlight(text) {
  let out = "", last = 0, m;
  TOKEN_RE.lastIndex = 0;
  while ((m = TOKEN_RE.exec(text))) {
    out += esc(text.slice(last, m.index));
    const cls = m[1] ? (/"\s*:$/.test(m[1]) ? "k" : "s") : m[2] ? "n" : m[3] ? "b" : "p";
    out += `<span class="${cls}">${esc(m[0])}</span>`;
    last = TOKEN_RE.lastIndex;
  }
  return out + esc(text.slice(last));
}
// Display-only line breaks for compact JSON; the stored text is untouched.
function layout(text) {
  return text.slice(0, 300).includes("\n") ? text : text.replace(/\},\s*\{/g, "},\n{").replace(/,?\s*"(matches|itc|itc_totals)":/g, ",\n\n\"$1\":").replace(/,\s*"line_items":/, ",\n\n\"line_items\":").replace(/\],\s*"taxable_value":/, "],\n\n\"taxable_value\":");
}

const focusId = (run) => (run.docs[S.focusDoc] ? S.focusDoc : run.active || run.order.findLast((id) => run.docs[id].text) || run.order[0]);

function renderStrip(run) {
  const el = $("callStrip");
  el.hidden = !hybridRun(run);
  if (!hybridRun(run)) return;
  const fid = focusId(run);
  const chips = run.order.map((id) => {
    const d = run.docs[id], tok = d.stats?.completion_tokens ?? d.tokens;
    const ic = d.state === "ok" ? "\u2713" : d.state === "bad" ? "\u2717" : "";
    return `<button data-doc="${esc(id)}" class="call ${d.state}${id === fid ? " focus" : ""}" title="${esc(d.error || `${tok} tokens`)}">${ic ? `<i>${ic}</i>` : ""}${esc(id)}<small>${d.state === "queued" ? "" : tok}</small></button>`;
  }).join("");
  const rs = run.stage, rms = run.stats?.reconcile_ms;
  const rec = `<span class="call rec ${rs}" title="Plain code, no model: matches the register, GSTR-2B and bank, then applies GST law">${rs === "done" ? "<i>\u2713</i>" : ""}Then: code reconciler, no model<small>${rs === "done" ? (rms != null ? `${rms} ms` : "done") : rs === "reconcile" ? "running" : "waiting"}</small></span>`;
  const sig = chips + rec;
  if (el.dataset.sig !== sig) { el.dataset.sig = sig; el.innerHTML = sig; }
}

function renderStream(run) {
  const pre = $("stream"), empty = $("streamEmpty"), badge = $("runBadge");
  if (!run) {
    pre.innerHTML = ""; badge.hidden = true;
    empty.innerHTML = `<b>Press Run</b>${S.constrained ? "Output is forced to match the JSON schema" : "Same prompt, schema in the prompt, no grammar"}`;
    return;
  }
  badge.hidden = false;
  const replay = run.mode === "replay";
  badge.className = "badge " + (replay ? "replay" : "live");
  badge.textContent = replay ? `Replay \u00B7 recorded${run.speed > 1 ? ` \u00B7 ${run.speed}x` : ""}` : "Live \u00B7 SGLang";
  badge.title = replay ? `Recorded ${run.recordedAt || ""} from a real run of ${run.model}. Not generated now.` : `Generating now with ${run.model}`;
  const hy = hybridRun(run), fid = hy ? focusId(run) : null, d = hy ? run.docs[fid] : null;
  const text = hy ? d?.text || "" : run.text;
  if (run.error && !text) {
    pre.innerHTML = ""; empty.innerHTML = `<b style="color:var(--bad)">${esc(run.error)}</b>${S.health.live ? "" : "Switch Source to Replay to use a recorded run."}`;
    return;
  }
  empty.innerHTML = text ? "" : `<b>${run.done ? "No output" : "Waiting for the first token"}</b>${run.done ? "" : "the request is queued on the GPU"}`;
  const stick = pre.scrollHeight - pre.scrollTop - pre.clientHeight < 48;
  const writing = hy ? d?.state === "active" : !run.done;
  const caret = writing && text ? '<span class="caret"></span>' : "";
  const head = hy && d ? `<span class="docline">${esc(fid)} \u00B7 ${d.state === "active" ? "being read now" : "read by the model"}</span>\n` : "";
  pre.innerHTML = head + highlight(layout(text)).replace(/^\s+/, "") + caret;
  if (stick || hy) pre.scrollTop = pre.scrollHeight;
  run.shownRev = run.rev;
}

function renderStats(run) {
  const el = $("stats");
  const st = run?.stats;
  const hy = hybridRun(run);
  const live = run && !st;
  const sec = run && run.tFirst ? (performance.now() - run.t0) / 1000 : 0;
  const act = hy ? run.docs[run.active] : null;
  const decode = (hy ? act?.tFirst : run?.tFirst) ? Math.max((performance.now() - (hy ? act.tFirst : run.tFirst)) / 1000, 0.001) : 0;
  const replayLive = live && run.mode === "replay";
  const n = hy ? act?.tokens : run?.tokens;
  const d0 = hy ? run?.docs[run.order[0]] : null;
  const first = d0?.stats ? d0.stats.ttft_s : d0?.tFirst && d0.t0 && !replayLive ? (d0.tFirst - d0.t0) / 1000 : null;
  const cells = [
    [hy ? "First token (doc 1)" : "Time to first token", st ? fmtSec(st.ttft_s) : first != null ? fmtSec(first) : run?.tFirst && !replayLive && !hy ? fmtSec((run.tFirst - run.t0) / 1000) : "-"],
    ["Tokens", run ? `${(st?.completion_tokens ?? run.tokens).toLocaleString("en-IN")}` : "-"],
    ["Tokens / sec", st ? (st.tps ? `${st.tps.toFixed(1)}` : "-") : live && !replayLive && n > 1 ? (n / decode).toFixed(1) : "-"],
    ["Total latency", st ? fmtSec(st.latency_s) : live && !replayLive && sec ? fmtSec(sec) : "-"],
  ];
  el.innerHTML = cells.map(([l, v]) => `<div class="stat${l === "Tokens" && st?.finish_reason === "length" ? " warn" : ""}"><span>${l}</span><b>${v}</b></div>`).join("");
  const val = $("validity");
  const v = run?.view?.validity;
  if (hy && run) {
    const ds = run.order.map((id) => run.docs[id]), fin = ds.filter((d) => d.valid), ok = fin.filter((d) => d.valid.schema).length;
    if (run.stage !== "done" || !st) {
      val.className = "validity";
      val.textContent = run.error ? "Run failed" : run.aborted ? "Stopped" : run.stage === "reconcile" ? "Code reconciler running..." : `Reading documents: ${fin.length} of ${run.order.length} done`;
    } else {
      val.className = "validity " + (ok === ds.length ? "ok" : "bad");
      val.innerHTML = ok === ds.length
        ? `<b>\u2713 ${ok} of ${ds.length} documents match the schema</b><small>${run.constrained ? "guaranteed by the grammar" : "no grammar: valid this time"}</small>`
        : `<b>\u2717 ${ds.length - ok} of ${ds.length} documents failed the schema</b><small>the reconciler reads them leniently</small>`;
    }
  } else if (v) {
    val.className = "validity " + (v.schema ? "ok" : "bad");
    val.innerHTML = v.schema
      ? `<b>\u2713 Valid JSON, matches the schema</b><small>${run.constrained ? "guaranteed by the grammar" : "no grammar: valid this time"}</small>`
      : `<b>\u2717 ${v.json ? "Valid JSON, wrong shape" : "Not valid JSON"}</b><small title="${esc(v.error)}">${esc(v.error)}</small>`;
    if (st?.finish_reason === "length") val.innerHTML += `<small>hit the token limit</small>`;
  } else {
    val.className = "validity";
    val.textContent = run?.aborted ? "Stopped" : run ? (run.error ? "Run failed" : "Checking the output as it streams...") : "Validity check appears when a run finishes";
  }
}
const fmtSec = (s) => (s == null ? "-" : s < 10 ? `${s.toFixed(2)}s` : `${s.toFixed(1)}s`);

/* ------------------------------------------------------------------ right panel */
function renderView(run) {
  const v = run?.view;
  const wrap = $("recon");
  const key = run ? runKey(run.caseId, run.model, run.constrained) : null;
  if (key !== S.tableKey) { for (const tb of [...wrap.querySelectorAll("tbody")]) tb.remove(); S.tableKey = key; }
  $("tableEmpty").innerHTML = v?.rows.length ? "" : `<b>The table fills in as the model finishes each invoice</b>one row per document`;
  renderHeadline(v, run);
  const gt = S.gt && v?.diff;
  $("diffBar").hidden = !gt;
  if (gt) {
    const d = v.diff, bad = d.exact < d.judged || d.wrong_cells;
    $("diffBar").className = "diffbar " + (bad ? "bad" : "ok");
    $("diffBar").innerHTML = bad
      ? `<b>\u2717 ${d.judged - d.exact} of ${d.judged} invoices differ from ground truth</b><span>${d.wrong_cells} cell${d.wrong_cells === 1 ? "" : "s"} highlighted \u00B7 ITC exact ${d.exact}/${d.judged}</span>`
      : `<b>\u2713 Every ITC amount matches ground truth to the rupee</b><span>ITC exact ${d.exact}/${d.judged}</span>`;
  }
  if (!v) return;
  const seen = new Set(), known = new Set(S.detail?.docs.map((d) => d.id));
  for (const r of v.rows.filter((x) => run?.final || known.has(x.doc_id))) { // a still-typing id like "D0" is not a row yet
    seen.add(r.doc_id);
    let tb = wrap.querySelector(`tbody[data-id="${CSS.escape(r.doc_id)}"]`);
    const html = rowHtml(r, gt);
    const sel = r.doc_id === S.doc;
    const sig = html + sel;
    if (!tb) {
      tb = document.createElement("tbody");
      tb.dataset.id = r.doc_id; tb.className = "row enter";
      wrap.appendChild(tb);
      if (run && !run.done) $("tableWrap").scrollTop = $("tableWrap").scrollHeight;
    }
    if (tb.dataset.sig !== sig) {
      tb.dataset.sig = sig; tb.innerHTML = html;
      tb.className = `row s-${dominant(r)}${sel ? " sel" : ""}${tb.classList.contains("enter") ? " enter" : ""}`;
    }
  }
  for (const tb of [...wrap.querySelectorAll("tbody")]) if (!seen.has(tb.dataset.id)) tb.remove(); // ids still being typed
}

function dominant(r) {
  if (!r.ready.itc) return "pending";
  return BUCKETS.reduce((a, b) => (Math.abs(r[b]) > Math.abs(r[a]) ? b : a), "eligible");
}

function renderHeadline(v, run) {
  const h = v?.headline, truth = S.gt && v?.diff && v.truth_headline;
  const final = v?.headline_final;
  $("headline").innerHTML = BUCKETS.map((b) => {
    const has = h && v.rows.some((r) => r.ready.itc) || final;
    const gtLine = truth ? (Math.abs(truth[b] - h[b]) <= 1 ? `<div class="gt ok">\u2713 ground truth ${rupee(truth[b])}</div>` : `<div class="gt bad">truth ${rupee(truth[b])}</div>`) : "";
    return `<div class="tile ${b}${has ? "" : " pending"}${has && !final && run && !run.done ? " live-total" : ""}"><div class="amt">${has ? rupee(h[b]) : "\u20B9 -"}</div><div class="lbl"><i></i>${b}</div>${final ? gtLine : ""}</div>`;
  }).join("");
}

function cell(r, key, inner, cls = "") {
  const w = S.gt && r.wrong[key] != null;
  return { cls: `${cls}${w ? " bad-cell" : ""}`, inner: inner + (w ? `<span class="exp">${esc(r.wrong[key])}</span>` : "") };
}

function amt(r, b) {
  if (!r.ready.itc) return `<span class="shim"></span>`;
  const n = r[b];
  return n === 0 ? "-" : rupee(n);
}

function pills(r) {
  return [["in_books", "Books"], ["in_2b", "2B"], ["paid", "Bank"]].map(([k, label]) => {
    const wrong = S.gt && r.wrong[k] != null;
    const state = !r.ready.match ? "pend" : r[k] ? "ok" : "no";
    const g = state === "ok" ? "\u2713 " : state === "no" ? "\u2717 " : "";
    return `<span class="pill ${state}${wrong ? " bad-cell" : ""}" title="${wrong ? `ground truth: ${esc(r.wrong[k])}` : ""}">${g}${label}</span>`;
  }).join("");
}

function rowHtml(r, gt) {
  const wrongAny = gt && Object.keys(r.wrong).length;
  const c = (k, inner, cls) => cell(r, k, inner, cls);
  const sup = c("supplier", `<span class="nm">${esc(r.supplier || (r.missing ? "Not produced by the model" : "..."))}</span>`);
  const tot = c("total", r.total != null ? rupee(r.total) : "-", "num amt-cell");
  const e = c("eligible", amt(r, "eligible"), `num amt-cell e ${r.eligible > 0 ? "pos" : r.eligible < 0 ? "neg" : "zero"}`);
  const b = c("blocked", amt(r, "blocked"), `num amt-cell b ${r.blocked ? "pos" : "zero"}`);
  const d = c("deferred", amt(r, "deferred"), `num amt-cell d ${r.deferred ? "pos" : "zero"}`);
  const inv = c("invoice_no", `${esc(r.invoice_no || "")}${r.date ? ` \u00B7 ${esc(r.date)}` : ""}${r.gstin ? ` \u00B7 ${esc(r.gstin)}` : ""}`);
  const reasons = !r.ready.itc ? (current()?.kind === "hybrid" && r.ready.extraction ? '<span class="reason" style="--c:var(--dim)">Read by the model, waiting for the code reconciler</span>' : '<span class="shim" style="width:150px"></span>')
    : r.reasons.length ? r.reasons.map((x) => `<span class="reason ${x.bucket}">${esc(x.text)}</span>`).join("") : '<span class="reason" style="--c:var(--dim)">No reason given</span>';
  const flagWrong = gt && r.wrong.flags != null, reasonWrong = gt && r.wrong.reasons != null;
  const flags = r.ready.match ? r.flags.map((f) => `<span class="chip ${f.severity}">${esc(f.label)}</span>`).join("") : "";
  const verdict = gt && r.ready.itc ? `<span class="verdict ${wrongAny ? "bad" : "ok"}">${wrongAny ? "differs from truth" : "matches truth"}</span>` : "";
  return `
  <tr class="main">
    <td><div class="inv"><span class="id">${esc(r.doc_id)}</span><span class="${sup.cls}">${sup.inner}</span></div>
        <div class="inv-sub ${r.doc_type === "credit_note" ? "credit" : ""} ${inv.cls}">${inv.inner}</div></td>
    <td class="${tot.cls}">${tot.inner}</td>
    <td><div class="pills">${pills(r)}</div></td>
    <td class="${e.cls}">${e.inner}</td><td class="${b.cls}">${b.inner}</td><td class="${d.cls}">${d.inner}</td>
  </tr>
  <tr class="why"><td colspan="6"><div class="whyline">
    ${flags}<span class="${reasonWrong ? "bad-cell" : ""}" style="display:contents">${reasons}</span>${verdict}
    ${flagWrong ? `<span class="exp reason-exp" style="margin-left:0">flags: ${esc(r.wrong.flags)}</span>` : ""}
    ${reasonWrong ? `<span class="exp reason-exp">${esc(r.wrong.reasons)}</span>` : ""}
  </div></td></tr>${S.expanded.has(r.doc_id) ? evidence(r) : ""}`;
}

const HEAD_NAMES = { igst: "IGST", cgst: "CGST", sgst: "SGST", cess: "Cess" };
const CATEGORY = { normal: "ordinary goods or services", food_beverage: "food and beverages", motor_vehicle: "motor vehicle", club_membership: "club membership", works_contract: "works contract" };
const PURPOSE = { business: "business use", further_supply: "resale or onward supply", passenger_transport: "passenger transport", driving_training: "driving training",
  factory_canteen: "factory canteen", staff_welfare: "staff welfare", own_construction: "own building work", personal: "personal use", gift: "gifts" };
const yes = (t) => `<span class="t-ok">${t}</span>`, no = (t) => `<span class="t-bad">${t}</span>`;

// The reconciler's audit trail for one invoice, in plain words. All facts come from the code's trace, none from the model's prose.
function traceHtml(r) {
  const t = r.trace, why = Object.fromEntries(r.reasons.map((x) => [x.code, x.text.replace(/^[A-Za-z ]+: /, "")]));
  const li = [];
  for (const l of t.lines || []) {
    li.push(`<li><b>${esc(l.description)}</b> was read as ${esc(CATEGORY[l.itc_category] || l.itc_category)}, for ${esc(PURPOSE[l.purpose] || l.purpose)}: ${l.block ? no(`blocked, ${esc(why[l.block] || l.block)}`) : yes("no blocking rule applies")}</li>`);
  }
  const g = t.gstr2b, ev = (x) => (x?.evidence?.length ? ` <small>(${esc(x.evidence.join(", "))})</small>` : "");
  if (!g || typeof g === "string") li.push(`<li>GSTR-2B: ${no("no entry matched this invoice, so the supplier has not reported it")}</li>`);
  else {
    const diffs = Object.keys(HEAD_NAMES).filter((h) => Math.abs((g[h]?.[0] ?? 0) - (g[h]?.[1] ?? 0)) > 1).map((h) => `${HEAD_NAMES[h]} ${rupee(g[h][0])} on the invoice vs ${rupee(g[h][1])} in 2B`);
    li.push(`<li>GSTR-2B: matched entry ${esc(t.link?.gstr2b?.doc_no || "")} filed in ${esc(g.period)}${ev(t.link?.gstr2b)}; ${g.period !== g.case_period ? no(`it is in another month (this return is ${esc(g.case_period)})`) : yes("filed for this month")}; ${g.ctin !== g.invoice_gstin ? no(`filed under GSTIN ${esc(g.ctin)}, invoice says ${esc(g.invoice_gstin)}`) : yes("same supplier GSTIN")}; ${diffs.length ? no(diffs.join("; ")) : yes("tax amounts agree")}</li>`);
  }
  const reg = t.register || [];
  li.push(`<li>Purchase register: ${reg.length ? reg.map((v, i) => `${yes(esc(v.voucher))} <small>taxable ${rupee(v.taxable)}${ev(t.link?.register?.[i])}</small>`).join(", ") : no("no voucher matched")}</li>`);
  const p = t.payment;
  if (p) li.push(`<li>Payment: ${p.days_since_invoice} days since the invoice, ${p.outstanding <= 0.5 ? yes("fully paid") : `${rupee(p.outstanding)} of ${rupee(p.total)} unpaid`}; ${p.unpaid_180d ? no("unpaid for over 180 days, credit must be reversed") : yes("not over the 180-day limit")}</li>`);
  return `<div class="trace-h">Why: decision trace from the code reconciler</div><ul class="trace">${li.join("")}</ul>`;
}

function evidence(r) {
  const heads = (b) => Object.entries(r.heads[b]).filter(([, n]) => n).map(([h, n]) => `${h.toUpperCase()} ${rupee(n)}`).join(", ") || "none";
  const kv = [["Supplier GSTIN", r.gstin], ["Invoice date", r.date], ["Line items", r.lines.join(", ")],
    ["Register voucher", r.vouchers.join(", ") || "none"], ["GSTR-2B entry", r.gstr2b ? r.gstr2b.join(" / ") : "none"], ["Bank reference", r.payments.join(", ") || "none"],
    ["Eligible tax", heads("eligible")], ["Blocked tax", heads("blocked")], ["Deferred tax", heads("deferred")]];
  return `<tr class="ev"><td colspan="6"><div class="grid2">${kv.map(([k, v]) => `<div>${esc(k)}: <b>${esc(v ?? "-")}</b></div>`).join("")}</div>${r.trace ? traceHtml(r) : ""}</td></tr>`;
}

boot();
