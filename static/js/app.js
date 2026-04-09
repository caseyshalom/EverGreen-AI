/* EcoGuardian AI — app.js */

// Raw output penuh dari backend — diisi saat renderResult dipanggil
const _agentRaw = { monitor: "", predict: "", social: "", ethics: "" };

// Strip markdown dan potong teks di akhir kalimat
function clean(text, maxLen = 200) {
  if (!text) return "";
  let t = text
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/#{1,6}\s/g, "")
    .replace(/\n+/g, " ")
    .trim();
  if (t.length <= maxLen) return t;
  const cut = t.slice(0, maxLen);
  const lastDot = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("! "), cut.lastIndexOf("? "));
  return lastDot > maxLen * 0.5 ? cut.slice(0, lastDot + 1) : cut.slice(0, cut.lastIndexOf(" ")) + "…";
}

// Ambil semua string dari object agent sebagai teks penuh
function extractFullText(obj) {
  if (!obj) return "";
  if (typeof obj === "string") return obj;
  return Object.values(obj)
    .filter(v => typeof v === "string" && v.length > 3)
    .join("\n\n");
}

// ── Insight Renderers ────────────────────────────────────────────────────

function renderMonitorInsight(m) {
  const el = document.getElementById("monitorInsight");
  if (!el) return;
  const status    = clean(m.status_udara || m.status || "", 80);
  const ringkasan = clean(m.ringkasan || m.raw || m.summary || "", 220);
  const recs      = m.rekomendasi || m.rekomendasi_segera || [];
  el.innerHTML = [
    status    ? `<div style="margin-bottom:4px"><strong>Status:</strong> ${status}</div>` : "",
    ringkasan ? `<div style="margin-bottom:6px;line-height:1.6;color:var(--text2)">${ringkasan}</div>` : "",
    recs.length ? `<div style="display:flex;flex-wrap:wrap;gap:4px">${recs.slice(0,2).map(r=>`<span class="ic-tag">${clean(r,80)}</span>`).join("")}</div>` : "",
  ].join("") || "—";
}

function renderPredictInsight(p) {
  const el = document.getElementById("predictInsight");
  if (!el) return;
  const banjir   = clean(p.risiko_banjir || "", 30);
  const polusi   = clean(p.risiko_polusi || "", 30);
  const prediksi = clean(p.prediksi || p.raw || "", 220);
  const saran    = p.saran || [];
  const riskColor = (v) => v === "tinggi" ? "var(--red)" : v === "sedang" ? "var(--amber)" : "var(--green-d)";
  el.innerHTML = [
    banjir  ? `<div style="margin-bottom:3px">🌊 Banjir: <strong style="color:${riskColor(banjir)}">${banjir}</strong></div>` : "",
    polusi  ? `<div style="margin-bottom:6px">💨 Polusi: <strong style="color:${riskColor(polusi)}">${polusi}</strong></div>` : "",
    prediksi ? `<div style="margin-bottom:6px;line-height:1.6;color:var(--text2)">${prediksi}</div>` : "",
    saran.length ? `<div style="display:flex;flex-wrap:wrap;gap:4px">${saran.slice(0,2).map(s=>`<span class="ic-tag">${clean(s,80)}</span>`).join("")}</div>` : "",
  ].join("") || "—";
}

function renderSocialInsight(s) {
  const el = document.getElementById("socialInsight");
  if (!el) return;
  const skor     = s.skor_kerentanan_sosial;
  const level    = clean(s.kerentanan_sosial || "", 40);
  const kelompok = s.kelompok_rentan || s.kelompok_paling_terdampak || [];
  const dampak   = clean(s.dampak || s.raw || "", 220);
  el.innerHTML = [
    skor !== undefined
      ? `<div style="margin-bottom:4px">Kerentanan: <strong style="color:var(--amber)">${skor}/100</strong></div>`
      : level ? `<div style="margin-bottom:4px">Kerentanan: <strong>${level}</strong></div>` : "",
    dampak ? `<div style="margin-bottom:6px;line-height:1.6;color:var(--text2)">${dampak}</div>` : "",
    kelompok.length ? `<div style="display:flex;flex-wrap:wrap;gap:4px">${kelompok.slice(0,3).map(k=>`<span class="ic-tag">${clean(k,50)}</span>`).join("")}</div>` : "",
  ].join("") || "—";
}

function renderEthicsInsight(e) {
  const el = document.getElementById("ethicsInsight");
  if (!el) return;
  const skor    = e.skor_etika || e.ethics_score;
  const catatan = clean(e.catatan_etika || e.catatan || e.raw || "", 220);
  const temuan  = e.temuan || e.findings || [];
  const color   = skor >= 80 ? "var(--green-d)" : skor >= 60 ? "var(--amber)" : "var(--red)";
  el.innerHTML = [
    skor !== undefined ? `<div style="margin-bottom:4px">Skor Etika: <strong style="color:${color}">${skor}/100</strong></div>` : "",
    temuan.length ? `<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px">${temuan.slice(0,3).map(t=>`<span class="ic-tag">${clean(t,60)}</span>`).join("")}</div>` : "",
    catatan ? `<div style="line-height:1.6;color:var(--text2)">${catatan}</div>` : "",
  ].join("") || "—";
}

// ── Rencana Aksi Terstruktur ─────────────────────────────────────────────

function renderAksiTerstruktur(actions, city) {
  const list = document.getElementById("aksiList");
  const sub  = document.getElementById("aksiSub");
  const cnt  = document.getElementById("aksiCount");
  if (!list || !actions || actions.length === 0) return;

  const prioConfig = {
    tinggi:  { color: "badge-red",   icon: "🔴", label: "Tinggi" },
    sedang:  { color: "badge-amber", icon: "🟡", label: "Sedang" },
    rendah:  { color: "badge-green", icon: "🟢", label: "Rendah" },
  };

  if (sub) sub.textContent = `Rencana aksi untuk ${city} — klik ✓ untuk tandai selesai`;
  if (cnt) cnt.textContent = actions.length + " Aksi";

  list.innerHTML = actions.map((a, i) => {
    const prio = prioConfig[a.prioritas] || prioConfig.sedang;
    return `
    <div class="aksi-item" id="aksi-${i}">
      <div class="aksi-num" style="background:var(--green-l);color:var(--green-d)">${i + 1}</div>
      <div class="aksi-content">
        <div class="aksi-title">${clean(a.aksi, 120)}</div>
        <div class="aksi-desc" style="margin-top:4px;color:var(--text3);font-size:0.75rem">
          📊 ${clean(a.dampak, 80)}
        </div>
        <div class="aksi-meta">
          <span class="aksi-tag ${prio.color}">${prio.icon} ${prio.label}</span>
          <span class="aksi-tag badge-blue">👤 ${clean(a.pelaku, 40)}</span>
        </div>
      </div>
      <div class="aksi-check" id="check-${i}" onclick="toggleAksi(${i})" title="Tandai selesai"></div>
    </div>`;
  }).join("");

  if (typeof updateKemajuanAksi === "function") updateKemajuanAksi();
}

// ── Download Laporan ─────────────────────────────────────────────────────

function renderNotifications(notifications, reportFile, city) {
  let panel = document.getElementById("notifPanel");
  if (!panel) {
    const sources = document.getElementById("responseSources");
    if (!sources) return;
    panel = document.createElement("div");
    panel.id = "notifPanel";
    panel.style.cssText = "margin-top:12px";
    sources.parentNode.insertBefore(panel, sources.nextSibling);
  }
  if (!reportFile) { panel.innerHTML = ""; return; }
  panel.innerHTML = `
    <a href="/api/download-report?file=${encodeURIComponent(reportFile)}"
       download
       style="display:inline-flex;align-items:center;gap:6px;padding:8px 16px;
              background:var(--green-l);color:var(--green-d);border:1.5px solid var(--green-m);
              border-radius:8px;font-size:0.8rem;font-weight:600;text-decoration:none;transition:all 0.2s"
       onmouseover="this.style.background='var(--green-m)'"
       onmouseout="this.style.background='var(--green-l)'">
      📄 Unduh Laporan ${city}
    </a>`;
}

// ── Agent Detail Modal ───────────────────────────────────────────────────

const _agentConfig = {
  monitor: { title: "Monitor Agent",  color: "var(--teal)",  emoji: "🌫️" },
  predict: { title: "Predict Agent",  color: "var(--amber)", emoji: "📈" },
  social:  { title: "Social Agent",   color: "var(--blue)",  emoji: "👥" },
  ethics:  { title: "Ethics Auditor", color: "var(--green)", emoji: "🛡️" },
};

// Dipanggil dari renderResult di index.html — simpan raw data sebelum diproses
function storeAgentRaw(data) {
  _agentRaw.monitor = extractFullText(data.monitor);
  _agentRaw.predict = extractFullText(data.predict);
  _agentRaw.social  = extractFullText(data.social);
  _agentRaw.ethics  = extractFullText(data.ethics);
}

function openAgentModal(key) {
  const cfg  = _agentConfig[key];
  // Ambil dari raw data, fallback ke teks yang tampil di card
  const raw  = _agentRaw[key];
  const card = document.getElementById(key === "ethics" ? "ethicsInsight" : key + "Insight");
  const text = raw || (card ? card.innerText : "") || "Data belum tersedia.";

  // Strip markdown untuk tampilan modal
  const cleaned = text
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/#{1,6}\s/g, "")
    .trim();

  document.getElementById("modalTitle").textContent = cfg.emoji + " " + cfg.title;
  document.getElementById("modalDot").style.background = cfg.color;
  document.getElementById("modalBody").textContent = cleaned;
  document.getElementById("agentModal").classList.add("open");
}

function closeAgentModal(e) {
  if (e.target.id === "agentModal") {
    document.getElementById("agentModal").classList.remove("open");
  }
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") document.getElementById("agentModal")?.classList.remove("open");
});

// ── Fix updateKemajuan & aksiTotal ──────────────────────────────────────

// Patch renderAksiTerstruktur agar sync aksiTotal setelah render
const _origRenderAksiTerstruktur = renderAksiTerstruktur;
renderAksiTerstruktur = function(actions, city) {
  _origRenderAksiTerstruktur(actions, city);
  if (typeof aksiTotal !== "undefined") {
    aksiTotal = actions ? actions.length : 0;
    aksiChecked = 0;
    if (typeof updateKemajuanAksi === "function") updateKemajuanAksi();
  }
};

// Inject skor sosial ke data sebelum updateKemajuan dipanggil
// Dipanggil dari storeAgentRaw yang sudah ada di atas
const _origStoreAgentRaw = storeAgentRaw;
storeAgentRaw = function(data) {
  _origStoreAgentRaw(data);
  // Ekstrak skor sosial dari teks jika belum ada
  if (data.social && data.social.skor_kerentanan_sosial === undefined) {
    const raw = data.social.dampak || data.social.raw || "";
    const match = raw.match(/[Ss]kor[^\d]*(\d{1,3})|(\d{1,3})\s*\/\s*100/);
    data.social.skor_kerentanan_sosial = match ? parseInt(match[1] || match[2]) : 0;
  }
};
