"use strict";

const $ = (id) => document.getElementById(id);
let PAGES = [];          // [{id, name}]
let EMOJI = [""];        // ротация эмодзи (синхронно с сервером)
let activeTab = 0;       // индекс выбранной страницы в превью

// --- утилиты ---------------------------------------------------------
function selectedPages() {
  return PAGES.filter((p) => {
    const el = document.querySelector(`.page-chip input[value="${p.id}"]`);
    return el && el.checked;
  });
}

// та же логика, что fbposter.poster.vary_text (для живого превью)
function varyText(message, pageName, index) {
  const text = message.replaceAll("{page}", pageName);
  const emoji = EMOJI[index % EMOJI.length] || "";
  return (text + " " + emoji).trimEnd();
}

function toast(msg, kind) {
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast " + (kind || "");
}

// --- загрузка статуса/страниц ---------------------------------------
async function loadStatus() {
  const r = await fetch("/api/status").then((r) => r.json());
  EMOJI = r.emoji && r.emoji.length ? r.emoji : [""];
  const pill = $("statusPill");
  if (r.connected && r.pages.length) {
    PAGES = r.pages;
    pill.textContent = `● подключено: ${r.pages.length}`;
    pill.className = "pill pill--on";
  } else {
    PAGES = [];
    pill.textContent = "● не подключено";
    pill.className = "pill pill--off";
  }
  renderPages();
  renderPreview();
}

function renderPages() {
  const box = $("pages");
  if (!PAGES.length) {
    box.innerHTML = '<div class="empty">Нет подключённых страниц. Нажми «Подключить страницы».</div>';
    return;
  }
  box.innerHTML = PAGES.map((p) => `
    <label class="page-chip">
      <input type="checkbox" value="${p.id}" checked> ${p.name}
    </label>`).join("");
  box.querySelectorAll("input").forEach((i) =>
    i.addEventListener("change", () => { activeTab = 0; renderPreview(); }));
}

// --- превью ----------------------------------------------------------
function renderPreview() {
  const sel = selectedPages();
  const tabs = $("tabs");
  if (!sel.length) {
    tabs.innerHTML = "";
    $("fbName").textContent = "—";
    $("avatar").textContent = "F";
    $("fbText").textContent = "Выбери хотя бы одну страницу слева.";
    $("fbImageWrap").hidden = true;
    return;
  }
  if (activeTab >= sel.length) activeTab = 0;

  tabs.innerHTML = sel.map((p, i) =>
    `<button class="tab ${i === activeTab ? "active" : ""}" data-i="${i}">${p.name}</button>`).join("");
  tabs.querySelectorAll(".tab").forEach((b) =>
    b.addEventListener("click", () => { activeTab = +b.dataset.i; renderPreview(); }));

  const page = sel[activeTab];
  const vary = $("vary").checked;
  const raw = $("text").value;
  const finalText = vary ? varyText(raw, page.name, activeTab) : raw.replaceAll("{page}", page.name);

  $("fbName").textContent = page.name;
  $("avatar").textContent = (page.name.trim()[0] || "F").toUpperCase();
  $("fbText").textContent = finalText;

  const img = $("image").value.trim();
  if (img) { $("fbImage").src = img; $("fbImageWrap").hidden = false; }
  else { $("fbImageWrap").hidden = true; }
}

// --- действия --------------------------------------------------------
function payload(dryRun) {
  return {
    text: $("text").value,
    image: $("image").value.trim(),
    link: $("link").value.trim(),
    at: $("at").value,
    vary: $("vary").checked,
    dry_run: !!dryRun,
    delay_min: +$("delayMin").value,
    delay_max: +$("delayMax").value,
    pages: selectedPages().map((p) => p.id),
  };
}

function showResults(results) {
  $("results").innerHTML = results.map((r) => `
    <div class="res ${r.ok ? "ok" : "fail"}">
      <span class="tag">${r.ok ? "OK" : "FAIL"}</span>
      <span><b>${r.page}</b></span>
      <span class="detail">${r.detail}</span>
    </div>`).join("");
}

async function doPublish(dryRun) {
  const sel = selectedPages();
  if (!sel.length) return toast("Выбери хотя бы одну страницу", "err");
  if (!$("text").value.trim()) return toast("Введи текст вакансии", "err");

  const btn = dryRun ? $("previewBtn") : $("publishBtn");
  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = dryRun ? "Проверяю..." : "Публикую...";
  toast(dryRun ? "" : "Отправляю на страницы (с паузами)...", "");

  try {
    const r = await fetch("/api/publish", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload(dryRun)),
    });
    const data = await r.json();
    if (!r.ok) { toast(data.error || "Ошибка", "err"); return; }
    showResults(data.results);
    const okCount = data.results.filter((x) => x.ok).length;
    if (dryRun) toast(`Предпросмотр готов: ${okCount} стр. Публикации не было.`, "ok");
    else toast(`Готово: ${okCount}/${data.results.length} опубликовано.`, "ok");
  } catch (e) {
    toast("Сеть/сервер недоступны: " + e.message, "err");
  } finally {
    btn.disabled = false; btn.textContent = label;
  }
}

async function connect() {
  const btn = $("connectBtn");
  btn.disabled = true;
  const label = btn.textContent;
  btn.textContent = "Открываю браузер...";
  toast("Открылся вход в Facebook. Войди и нажми «Разрешить»...", "");
  try {
    const r = await fetch("/api/login", { method: "POST" }).then((r) => r.json());
    if (r.ok) {
      toast(`Подключено страниц: ${r.count}.`, "ok");
      await loadStatus();
    } else {
      toast("Вход не удался: " + (r.error || ""), "err");
    }
  } catch (e) {
    toast("Ошибка: " + e.message, "err");
  } finally {
    btn.disabled = false; btn.textContent = label;
  }
}

// --- события ---------------------------------------------------------
["text", "image", "vary"].forEach((id) =>
  $(id).addEventListener("input", renderPreview));
$("selAll").addEventListener("click", (e) => { e.preventDefault();
  document.querySelectorAll(".page-chip input").forEach((i) => i.checked = true); renderPreview(); });
$("selNone").addEventListener("click", (e) => { e.preventDefault();
  document.querySelectorAll(".page-chip input").forEach((i) => i.checked = false); renderPreview(); });
$("previewBtn").addEventListener("click", () => doPublish(true));
$("publishBtn").addEventListener("click", () => doPublish(false));
$("connectBtn").addEventListener("click", connect);

loadStatus();
