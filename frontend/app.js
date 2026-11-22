"use strict";

const state = { lang: "en", payload: null, images: [], previewErrors: [], samplePreview: false, pageIndex: 0, selected: null };
const fileInput = document.querySelector("#file-input");
const sampleButton = document.querySelector("#sample-button");
const statusNode = document.querySelector("#status");
const results = document.querySelector("#results");
const canvas = document.querySelector("#document-canvas");
const context = canvas.getContext("2d");
document.querySelector("#page-prev").addEventListener("click", () => selectPage(state.pageIndex - 1));
document.querySelector("#page-next").addEventListener("click", () => selectPage(state.pageIndex + 1));

document.querySelectorAll(".language").forEach((button) => button.addEventListener("click", () => {
  document.querySelector(".language.active")?.classList.remove("active");
  button.classList.add("active");
  state.lang = button.dataset.lang;
  if (state.payload) loadSample();
}));
sampleButton.addEventListener("click", loadSample);
fileInput.addEventListener("change", () => { if (fileInput.files[0]) uploadFile(fileInput.files[0]); });
document.querySelector("#copy-whatsapp").addEventListener("click", () => copyText(document.querySelector("#whatsapp-text").textContent));
canvas.addEventListener("click", onCanvasClick);
window.addEventListener("resize", drawCanvas);

async function checkServer() {
  try {
    const response = await fetch("/api/v1/health", { cache: "no-store" });
    if (!response.ok) throw new Error("health check failed");
    setStatus("KararKavach is connected. Upload an agreement or load the sample.");
  } catch {
    setStatus("KararKavach server is not running. Start it in the project terminal and keep that window open.", "error");
  }
}

async function loadSample() {
  setStatus("Loading the sample agreement…", "loading");
  try {
    const response = await fetch(`/api/v1/audit-sample?lang=${encodeURIComponent(state.lang)}`);
    if (!response.ok) throw new Error(await responseMessage(response));
    const payload = await response.json();
    loadPreviewImages(payload, () => render(payload, "Sample Trap Rental Agreement"), true);
  } catch (error) { setStatus(networkMessage(error), "error"); }
}

async function uploadFile(file) {
  setStatus("Reviewing your agreement…", "loading");
  const form = new FormData(); form.append("file", file);
  try {
    const response = await fetch(`/api/v1/audit?lang=${encodeURIComponent(state.lang)}`, { method: "POST", body: form });
    if (!response.ok) throw new Error(await responseMessage(response));
    const payload = await response.json();
    loadPreviewImages(payload, () => render(payload, file.name));
  } catch (error) { setStatus(networkMessage(error), "error"); }
}

function networkMessage(error) {
  if (error instanceof TypeError && /fetch/i.test(error.message)) {
    return "Could not reach KararKavach. Start the server and open this page from its address, then try again.";
  }
  return error.message || "The review could not be completed.";
}

async function responseMessage(response) {
  const fallback = `The server could not review this file (HTTP ${response.status}${response.statusText ? ` ${response.statusText}` : ""}). Please try another PDF or image.`;
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : fallback;
  } catch { return fallback; }
}

function render(payload, title) {
  state.payload = payload; state.pageIndex = 0; state.selected = null;
  results.hidden = false;
  document.querySelector("#document-title").textContent = title;
  updatePreviewPlaceholder();
  const audit = payload.audit;
  const score = Number(audit.safety_score ?? 0);
  document.querySelector("#score-value").textContent = score;
  const gauge = document.querySelector("#score-gauge");
  const color = audit.verdict === "GREEN" ? "#27845f" : audit.verdict === "YELLOW" ? "#c4821c" : "#bd443c";
  gauge.style.setProperty("--score", `${score * 3.6}deg`); gauge.style.setProperty("--gauge", color);
  document.querySelector("#verdict-label").textContent = `${audit.verdict} · ${audit.verdict === "GREEN" ? "Looks safer" : audit.verdict === "YELLOW" ? "Review carefully" : "Needs attention"}`;
  const explanations = new Map(payload.explanations.map((item) => [Number(item.clause_number), item]));
  const flagged = audit.clauses.filter((clause) => clause.verdict !== "GREEN");
  document.querySelector("#clause-count").textContent = `${flagged.length} flagged`;
  const list = document.querySelector("#clause-list"); list.replaceChildren();
  flagged.forEach((clause) => list.append(makeClauseCard(clause, explanations.get(Number(clause.clause_number)))));
  const message = payload.explanations[0]?.whatsapp_message || "No flagged clauses were found. You can still ask the other party to clarify any term that feels unclear.";
  document.querySelector("#whatsapp-text").textContent = message;
  document.querySelector("#copy-whatsapp").disabled = false;
  drawCanvas(); setStatus("Review ready. Your uploaded file was processed in memory.");
  updatePageIndicator();
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

function makeClauseCard(clause, explanation) {
  const card = document.createElement("article");
  card.className = `clause-card ${clause.verdict.toLowerCase()}`;
  card.id = `clause-${clause.clause_number}`;
  card.addEventListener("click", () => { if (clause.page) selectPage(clause.page - 1); });
  const top = document.createElement("div"); top.className = "clause-top";
  top.innerHTML = `<span class="clause-number">CLAUSE ${escapeHtml(clause.clause_number)}</span><span class="risk-pill">${escapeHtml(clause.verdict)} · ${escapeHtml(clause.score)}/100</span>`;
  card.append(top);
  appendField(card, "Original clause", clause.clause_text, "clause-text");
  const ruleText = clause.fired_rules.map((rule) => `${rule.description}${rule.legal_reference ? ` (${rule.legal_reference})` : ""}`).join(" · ") || "No specific statutory rule was returned.";
  appendField(card, "Rule to review", ruleText, "rule-line");
  appendField(card, "In plain language", explanation?.explanation || "A detailed explanation is not available for this clause.", "clause-text");
  if (explanation?.audio_url) {
    const audioWrap = document.createElement("div"); audioWrap.className = "audio-row";
    const audio = document.createElement("audio"); audio.controls = true; audio.preload = "none"; audio.src = explanation.audio_url; audio.setAttribute("aria-label", `Audio explanation for clause ${clause.clause_number}`); audioWrap.append(audio); card.append(audioWrap);
  }
  if (explanation?.audio_error) appendField(card, "Audio", explanation.audio_error, "rule-line");
  appendField(card, "Safer wording to suggest", explanation?.replacement_clause || "Ask for this term to be clarified in writing.", "clause-text replacement");
  const copy = document.createElement("button"); copy.className = "text-button"; copy.textContent = "Copy Safe Replacement Clause ↗";
  copy.addEventListener("click", () => copyText(explanation?.replacement_clause || "Ask for this term to be clarified in writing.")); card.append(copy);
  return card;
}

function appendField(card, label, value, className) {
  const heading = document.createElement("p"); heading.className = "field-label"; heading.textContent = label; card.append(heading);
  const text = document.createElement("p"); text.className = className; text.textContent = value; card.append(text);
}

function drawCanvas() {
  const page = state.payload?.ocr?.pages?.[state.pageIndex];
  if (!page) { canvas.width = 1; canvas.height = 1; return; }
  const currentImage = state.images[state.pageIndex];
  const width = page.width || currentImage?.naturalWidth || 1;
  const height = page.height || currentImage?.naturalHeight || 1;
  const dpr = window.devicePixelRatio || 1;
  const displayWidth = Math.max(1, canvas.parentElement.clientWidth);
  const scale = displayWidth / width;
  canvas.width = Math.round(displayWidth * dpr); canvas.height = Math.round(height * scale * dpr);
  canvas.style.width = `${displayWidth}px`; canvas.style.height = `${height * scale}px`;
  context.setTransform(dpr * scale, 0, 0, dpr * scale, 0, 0);
  context.fillStyle = "#fff"; context.fillRect(0, 0, width, height);
  if (currentImage) context.drawImage(currentImage, 0, 0, width, height);
  const explanations = new Map((state.payload.audit.clauses || []).map((item) => [Number(item.clause_number), item.verdict]));
  for (const clause of page.clauses || []) {
    const verdict = explanations.get(Number(clause.number)); if (!verdict) continue;
    const [, x, y, w, h] = clause.bbox;
    context.fillStyle = verdict === "RED" ? "rgba(207, 54, 48, .22)" : "rgba(230, 161, 43, .25)";
    context.strokeStyle = verdict === "RED" ? "#c83b35" : "#d79424";
    context.lineWidth = Math.max(3, width / 500); context.fillRect(x, y, w, h); context.strokeRect(x, y, w, h);
    context.fillStyle = context.strokeStyle; context.font = `bold ${Math.max(22, width / 55)}px sans-serif`; context.fillText(String(clause.number), x + 5, Math.max(24, y - 5));
  }
  const documentFinding = state.payload.audit.clauses.find((clause) => clause.clause_number === 0 && clause.verdict !== "GREEN");
  if (documentFinding) {
    context.fillStyle = documentFinding.verdict === "RED" ? "rgba(207, 54, 48, .16)" : "rgba(230, 161, 43, .18)";
    context.strokeStyle = documentFinding.verdict === "RED" ? "#c83b35" : "#d79424";
    context.lineWidth = Math.max(3, width / 500);
    context.fillRect(0, 0, width, Math.max(45, height * 0.06));
    context.strokeRect(0, 0, width, Math.max(45, height * 0.06));
  }
}

function onCanvasClick(event) {
  const page = state.payload?.ocr?.pages?.[state.pageIndex]; if (!page) return;
  const bounds = canvas.getBoundingClientRect();
  const x = (event.clientX - bounds.left) * page.width / bounds.width;
  const y = (event.clientY - bounds.top) * page.height / bounds.height;
  const match = [...(page.clauses || [])].reverse().find((clause) => {
    const [, left, top, width, height] = clause.bbox; return x >= left && x <= left + width && y >= top && y <= top + height;
  });
  if (!match || !document.querySelector(`#clause-${CSS.escape(String(match.number))}`)) return;
  document.querySelector(".clause-card.selected")?.classList.remove("selected");
  const card = document.querySelector(`#clause-${CSS.escape(String(match.number))}`); card.classList.add("selected");
  state.selected = match.number; card.scrollIntoView({ behavior: "smooth", block: "center" });
}

function loadPreviewImages(payload, done, isSample = false) {
  state.payload = payload;
  const pages = payload.ocr?.pages || [];
  state.images = pages.map(() => null);
  state.previewErrors = pages.map(() => false);
  state.samplePreview = isSample;
  ensurePreviewImage(0, done);
}

function ensurePreviewImage(index, done = () => {}) {
  const page = state.payload?.ocr?.pages?.[index];
  if (!page) { done(); return; }
  if (state.images[index]) { done(); return; }
  const source = page.preview || (state.samplePreview && index === 0 ? `/assets/sample_rental_agreement.png?v=5` : null);
  if (!source) { done(); return; }
  const preview = new Image();
  preview.decoding = "async";
  preview.onload = () => {
    state.images[index] = preview;
    state.previewErrors[index] = false;
    updatePreviewPlaceholder();
    done();
  };
  preview.onerror = () => {
    state.previewErrors[index] = true;
    updatePreviewPlaceholder();
    done();
  };
  preview.src = source;
}

function updatePreviewPlaceholder() {
  const placeholder = document.querySelector("#empty-canvas");
  const available = Boolean(state.images[state.pageIndex]);
  placeholder.hidden = available;
  if (state.previewErrors[state.pageIndex]) {
    placeholder.textContent = "This page preview could not be displayed. The text audit is still available.";
  } else {
    placeholder.textContent = "Your scanned agreement will appear here.";
  }
}

function selectPage(index) {
  const count = state.payload?.ocr?.pages?.length || 0;
  if (!count) return;
  state.pageIndex = Math.max(0, Math.min(count - 1, index));
  updatePageIndicator();
  updatePreviewPlaceholder();
  ensurePreviewImage(state.pageIndex, drawCanvas);
  drawCanvas();
}

function updatePageIndicator() {
  const count = state.payload?.ocr?.pages?.length || 1;
  document.querySelector("#page-indicator").textContent = `Page ${state.pageIndex + 1} of ${count}`;
  document.querySelector("#page-prev").disabled = state.pageIndex === 0;
  document.querySelector("#page-next").disabled = state.pageIndex >= count - 1;
}

async function copyText(text) {
  try { await navigator.clipboard.writeText(text); setStatus("Copied to clipboard."); }
  catch { setStatus("Clipboard access is unavailable in this browser.", "error"); }
}
function setStatus(message, type = "") { statusNode.textContent = message; statusNode.className = `status ${type}`; }
function escapeHtml(value) { return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]); }

if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
  navigator.serviceWorker.addEventListener("controllerchange", () => window.location.reload());
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}
checkServer();
