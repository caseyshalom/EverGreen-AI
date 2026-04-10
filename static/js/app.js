/* EcoGuardian AI — main.js (inline + overrides) */

let sessionId = localStorage.getItem("eco_session") || "";
let isLoading = false;
let analysisCount = 0;
let aksiChecked = 0;
let aksiTotal = 0;
let lastResult = null;

const pageMeta = {
  ringkasan: [
    "Ringkasan Dashboard",
    "Gambaran umum kondisi lingkungan dan sosial",
  ],
  pemantauan: [
    "Pemantauan Data Real-Time",
    "Data lingkungan langsung dari API terpercaya",
  ],
  analisis: [
    "Analisis Dampak",
    "Jalankan analisis multi-agent AI untuk wilayah pilihan",
  ],
  aksi: [
    "Rencana Aksi",
    "Rekomendasi tindakan konkret berdasarkan analisis",
  ],
  etika: [
    "Audit Etika & Transparansi",
    "Standar etika, keadilan, dan kualitas sistem AI",
  ],
  kemajuan: [
    "Lacak Kemajuan",
    "Monitor perkembangan analisis dan aksi yang dilakukan",
  ],
};

function showPage(name, btn) {
  document
    .querySelectorAll(".page")
    .forEach((p) => p.classList.remove("active"));
  document
    .querySelectorAll(".nav-item")
    .forEach((n) => n.classList.remove("active"));
  document.getElementById("page-" + name).classList.add("active");
  if (btn) btn.classList.add("active");
  const meta = pageMeta[name] || ["", ""];
  document.getElementById("pageTitle").textContent = meta[0];
  document.getElementById("pageSub").textContent = meta[1];
}

function setQuery(el, text) {
  document
    .querySelectorAll(".q-tag")
    .forEach((t) => t.classList.remove("active"));
  el.classList.add("active");
  document.getElementById("queryInput").value = text;
}

function showNotif(msg) {
  const n = document.getElementById("notif");
  document.getElementById("notifText").textContent = msg;
  n.classList.add("show");
  setTimeout(() => n.classList.remove("show"), 2500);
}

function setCityQuick(name) {
  document.getElementById("cityInput").value = name;
  document
    .querySelectorAll("#cityQuickBtns .q-tag")
    .forEach((b) => b.classList.remove("active"));
  event.target.classList.add("active");
}

async function runAnalysis() {
  if (isLoading) return;
  const query = document.getElementById("queryInput").value.trim();
  const city = (
    document.getElementById("cityInput").value || "Jakarta"
  ).trim();
  // Auto-detect country from city name (basic heuristic)
  const countryMap = {
    singapore: "SG",
    "kuala lumpur": "MY",
    bangkok: "TH",
    tokyo: "JP",
    manila: "PH",
  };
  const country = countryMap[city.toLowerCase()] || "ID";

  if (!query) {
    document.getElementById("queryInput").style.borderColor =
      "var(--red)";
    setTimeout(
      () =>
        (document.getElementById("queryInput").style.borderColor = ""),
      1500
    );
    showNotif("Masukkan pertanyaan analisis terlebih dahulu");
    return;
  }
  if (!city) {
    document.getElementById("cityInput").style.borderColor = "var(--red)";
    setTimeout(
      () => (document.getElementById("cityInput").style.borderColor = ""),
      1500
    );
    showNotif("Masukkan nama wilayah terlebih dahulu");
    return;
  }

  isLoading = true;
  document.getElementById("analyzeBtn").disabled = true;
  document.getElementById("btnText").textContent = "Menganalisis...";
  document.getElementById("loadingPanel").style.display = "block";
  document.getElementById("resultPanel").style.display = "none";

  const steps = ["step1", "step2", "step3", "step4"];
  const labels = [
    "Mengambil data lingkungan...",
    "Menganalisis tren & risiko...",
    "Menilai dampak sosial...",
    "Menyusun laporan...",
  ];
  steps.forEach((s, i) => {
    setTimeout(() => {
      steps.slice(0, i).forEach((prev) => {
        document.getElementById(prev).className = "step-card done";
        document
          .getElementById(prev)
          .querySelector(".step-status").textContent = "Selesai ✓";
      });
      const el = document.getElementById(s);
      el.className = "step-card running";
      el.querySelector(".step-status").textContent = labels[i];
    }, i * 2200);
  });

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        city,
        country_code: country,
        session_id: sessionId,
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.session_id) {
      sessionId = data.session_id;
      localStorage.setItem("eco_session", sessionId);
    }

    steps.forEach((s) => {
      document.getElementById(s).className = "step-card done";
      document
        .getElementById(s)
        .querySelector(".step-status").textContent = "Selesai ✓";
    });

    setTimeout(() => {
      document.getElementById("loadingPanel").style.display = "none";
      renderResult(data);
      analysisCount++;
      document.getElementById("heroAnalysisCount").textContent =
        analysisCount;
      document.getElementById("navBadge").style.display = "inline";
      showNotif(
        "Analisis selesai! " + data.city + " · Risiko " + data.risk_level
      );
    }, 500);
  } catch (err) {
    document.getElementById("loadingPanel").style.display = "none";
    document.getElementById("resultPanel").style.display = "block";
    document.getElementById("responseText").textContent =
      "Error: " +
      err.message +
      "\n\nPastikan API keys sudah dikonfigurasi di file .env dan server berjalan.";
    document.getElementById("resultPanel").style.display = "block";
    showNotif("Terjadi kesalahan: " + err.message);
  } finally {
    isLoading = false;
    document.getElementById("analyzeBtn").disabled = false;
    document.getElementById("btnText").textContent =
      "Jalankan Analisis Multi-Agent";
  }
}

function renderResult(data) {
  lastResult = data;
  const m = data.metrics || {};

  // Result header
  document.getElementById("resultCity").textContent =
    data.city + ", " + (data.metrics?.country || "");
  document.getElementById("resultTime").textContent =
    new Date().toLocaleDateString("id-ID", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    });

  const riskEl = document.getElementById("riskBadge");
  const riskMap = {
    rendah: "badge-green",
    sedang: "badge-amber",
    tinggi: "badge-red",
    kritis: "badge-red",
  };
  riskEl.className =
    "risk-badge " + (riskMap[data.risk_level] || "badge-amber");
  riskEl.textContent = "Risiko " + (data.risk_level || "Sedang");

  document.getElementById("responseText").textContent =
    data.response || "—";

  // Metrics
  const aqi = m.aqi;
  const temp = m.temperature;
  const pm25 = m.pm25;
  const hum = m.humidity;
  document.getElementById("r-aqi").textContent =
    aqi !== "N/A" ? aqi : "—";
  document.getElementById("r-aqi-lbl").textContent = getAqiLabel(aqi);
  document.getElementById("r-temp").textContent =
    temp !== "N/A" ? temp + "°C" : "—";
  document.getElementById("r-weather").textContent =
    m.weather_desc || "—";
  document.getElementById("r-pm25").textContent =
    pm25 !== "N/A" ? pm25 : "—";
  document.getElementById("r-humidity").textContent =
    hum !== "N/A" ? hum + "%" : "—";

  // Update summary page metrics
  document.getElementById("s-aqi").textContent =
    aqi !== "N/A" ? aqi : "—";
  document.getElementById("s-aqi-lbl").textContent = getAqiLabel(aqi);
  document.getElementById("s-temp").textContent =
    temp !== "N/A" ? temp + "°C" : "—";
  document.getElementById("s-temp-lbl").textContent =
    m.weather_desc || "°C";
  document.getElementById("s-risk").textContent = capitalize(
    data.risk_level || "—"
  );
  document.getElementById("s-risk-lbl").textContent =
    "Level risiko lingkungan";
  const socialScore = data.social?.skor_kerentanan_sosial;
  document.getElementById("s-social").textContent =
    socialScore !== undefined ? socialScore : "—";

  const badgeEl = document.getElementById("s-aqi-badge");
  const aqiNum = parseInt(aqi);
  if (!isNaN(aqiNum)) {
    if (aqiNum <= 50) {
      badgeEl.className = "sc-badge badge-green";
      badgeEl.textContent = "Baik";
    } else if (aqiNum <= 100) {
      badgeEl.className = "sc-badge badge-amber";
      badgeEl.textContent = "Sedang";
    } else {
      badgeEl.className = "sc-badge badge-red";
      badgeEl.textContent = "Tidak Sehat";
    }
  }
  const riskBadgeEl = document.getElementById("s-risk-badge");
  const riskColorMap = {
    rendah: "badge-green",
    sedang: "badge-amber",
    tinggi: "badge-red",
    kritis: "badge-red",
  };
  riskBadgeEl.className =
    "sc-badge " + (riskColorMap[data.risk_level] || "badge-amber");
  riskBadgeEl.textContent = capitalize(data.risk_level || "—");

  // Monitor metrics
  document.getElementById("m-aqi").textContent =
    aqi !== "N/A" ? aqi : "—";
  document.getElementById("m-aqi-desc").textContent = getAqiLabel(aqi);
  document.getElementById("m-pm25").textContent =
    pm25 !== "N/A" ? pm25 + " μg/m³" : "—";
  document.getElementById("m-temp").textContent =
    temp !== "N/A" ? temp + "°C" : "—";
  document.getElementById("m-temp-desc").textContent =
    m.weather_desc || "—";
  document.getElementById("m-humidity").textContent =
    hum !== "N/A" ? hum + "%" : "—";
  document.getElementById("m-wind").textContent =
    m.wind_speed !== "N/A" ? m.wind_speed + " m/s" : "—";
  document.getElementById("m-pollutant").textContent =
    m.dominant_pollutant || "—";

  // Progress bars pemantauan
  const aqiPct = !isNaN(aqiNum) ? Math.min((aqiNum / 300) * 100, 100) : 0;
  const pm25Num = parseFloat(pm25);
  const pm25Pct = !isNaN(pm25Num)
    ? Math.min((pm25Num / 75) * 100, 100)
    : 0;
  const tempNum = parseFloat(temp);
  const tempPct = !isNaN(tempNum)
    ? Math.min(((tempNum - 15) / 25) * 100, 100)
    : 0;
  const humNum = parseFloat(hum);
  const humPct = !isNaN(humNum) ? humNum : 0;
  document.getElementById("m-aqi-bar").style.width = aqiPct + "%";
  document.getElementById("m-aqi-bar").className =
    "progress-fill " +
    (aqiPct < 33
      ? "fill-green"
      : aqiPct < 66
      ? "fill-amber"
      : "fill-red");
  document.getElementById("m-pm25-bar").style.width = pm25Pct + "%";
  document.getElementById("m-temp-bar").style.width =
    Math.max(0, tempPct) + "%";
  document.getElementById("m-humidity-bar").style.width = humPct + "%";

  // Simpan raw data untuk modal detail
  storeAgentRaw(data);

  // Agent insights
  renderMonitorInsight(data.monitor || {});
  renderPredictInsight(data.predict || {});
  renderSocialInsight(data.social || {});
  renderEthicsInsight(data.ethics || {});

  // Sources / referensi resmi
  if (data.sources && data.sources.length > 0) {
    const sourcesEl = document.getElementById("responseSources");
    sourcesEl.innerHTML = data.sources.map(s =>
      `<a class="src-tag src-link" href="${s.url}" target="_blank" title="${s.desc}">${s.name}</a>`
    ).join("");
    renderSourcesPanel(data.sources);
  }

  // Forecast
  if (data.forecast && data.forecast.length > 0) {
    renderForecast(data.forecast, data.city);
  }

  // Rencana aksi
  if (data.actions && data.actions.length > 0) {
    renderAksiTerstruktur(data.actions, data.city);
  } else {
    renderAksi(data.monitor || {}, data.predict || {}, data.social || {}, data.city);
  }

  // Notifikasi & download
  renderNotifications(data.notifications || {}, data.report_file || "", data.city);

  // Inject skor sosial jika belum ada (dari teks agen)
  if (data.social && data.social.skor_kerentanan_sosial === undefined) {
    const rawSoc = data.social.dampak || data.social.raw || "";
    const mSoc = rawSoc.match(/[Ss]kor[^\d]*(\d{1,3})|(\d{1,3})\s*\/\s*100/);
    data.social.skor_kerentanan_sosial = mSoc ? parseInt(mSoc[1] || mSoc[2]) : 0;
  }

  // Kemajuan
  updateKemajuan(data);

  // History di ringkasan
  renderHistory(data);

  document.getElementById("resultPanel").style.display = "block";

  // Peta
  if (data.coordinates && data.coordinates.lat && data.coordinates.lon) {
    showMapForLocation(
      data.coordinates.lat,
      data.coordinates.lon,
      data.city,
      data.risk_level,
      data.metrics
    );
  }
  // Groq panel
  if (data.groq && Object.keys(data.groq).length > 0) {
    renderGroqPanel(data.groq);
  }
  // Sources panel
  if (data.sources && data.sources.length > 0) {
    renderSourcesPanel(data.sources);
  }
  // Update response-sources chips
  if (data.sources) {
    const srcDiv = document.querySelector(".response-sources");
    if (srcDiv) {
      srcDiv.innerHTML = data.sources
        .map(
          (s) =>
            `<span class="src-tag" title="${s.type}">${
              s.name.split(" (")[0]
            }</span>`
        )
        .join("");
    }
  }
}

// ── MAP ──────────────────────────────────────────────────────────────
let ecoMap = null,
  ecoMarker = null;
function initMap() {
  if (ecoMap) return;
  ecoMap = L.map("ecoMap").setView([-6.2, 106.8], 10);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution:
      '© <a href="https://openstreetmap.org">OpenStreetMap</a>',
    maxZoom: 18,
  }).addTo(ecoMap);
}
function showMapForLocation(lat, lon, cityName, riskLevel, metrics) {
  const panel = document.getElementById("mapPanel");
  if (!panel) return;
  panel.style.display = "block";
  initMap();
  ecoMap.setView([lat, lon], 11);
  if (ecoMarker) {
    ecoMarker.remove();
    ecoMarker = null;
  }
  const riskColors = {
    rendah: "#22c55e",
    sedang: "#f59e0b",
    tinggi: "#ef4444",
    kritis: "#7c3aed",
  };
  const color = riskColors[riskLevel] || "#6b7280";
  const icon = L.divIcon({
    className: "",
    html: `<div style="background:${color};width:42px;height:42px;border-radius:50%;border:3px solid white;box-shadow:0 2px 10px rgba(0,0,0,.3);display:flex;align-items:center;justify-content:center;font-size:18px;">🌿</div>`,
    iconSize: [42, 42],
    iconAnchor: [21, 21],
  });
  const aqi = metrics?.aqi ?? "N/A";
  const temp = metrics?.temperature ?? "N/A";
  const hum = metrics?.humidity ?? "N/A";
  const comfort = metrics?.groq_comfort_index ?? null;
  ecoMarker = L.marker([lat, lon], { icon }).addTo(ecoMap);
  ecoMarker
    .bindPopup(
      `
    <div style="font-family:sans-serif;min-width:190px;padding:4px 0">
      <b style="font-size:13px">📍 ${cityName}</b><br/>
      <span style="color:${color};font-weight:700;font-size:11px;text-transform:uppercase">● Risiko: ${riskLevel}</span>
      <hr style="margin:6px 0;border-color:#e5e7eb"/>
      <table style="font-size:11px;width:100%;border-collapse:collapse">
        <tr><td style="padding:2px 0;color:#6b7280">💨 AQI</td><td style="font-weight:600">${aqi}</td></tr>
        <tr><td style="padding:2px 0;color:#6b7280">🌡️ Suhu</td><td style="font-weight:600">${temp}°C</td></tr>
        <tr><td style="padding:2px 0;color:#6b7280">💧 Kelembaban</td><td style="font-weight:600">${hum}%</td></tr>
        ${
          comfort !== null
            ? `<tr><td style="padding:2px 0;color:#6b7280">😊 Kenyamanan</td><td style="font-weight:600">${comfort}/100</td></tr>`
            : ""
        }
      </table>
    </div>`
    )
    .openPopup();
  // Fix map render in initially hidden container
  setTimeout(() => ecoMap.invalidateSize(), 150);
  // Update subtitle
  document.getElementById(
    "mapSubtitle"
  ).textContent = `${cityName} · ${lat.toFixed(4)}°, ${lon.toFixed(4)}°`;
  const rb = document.getElementById("mapRiskBadge");
  const riskBadgeMap = {
    rendah: "badge-green",
    sedang: "badge-amber",
    tinggi: "badge-red",
    kritis: "badge-red",
  };
  rb.className = "sc-badge " + (riskBadgeMap[riskLevel] || "badge-amber");
  rb.textContent = "Risiko " + riskLevel;
}

// ── GROQ PANEL ───────────────────────────────────────────────────────
function renderGroqPanel(groq) {
  const panel = document.getElementById("groqPanel");
  if (!panel) return;
  const ci = groq.indeks_kenyamanan ?? null;
  const ciColor = ci >= 70 ? "#16a34a" : ci >= 40 ? "#d97706" : "#dc2626";
  const ciBorder =
    ci >= 70 ? "#22c55e" : ci >= 40 ? "#f59e0b" : "#ef4444";
  let html = "";
  if (ci !== null) {
    html += `<div style="display:flex;align-items:center;gap:10px;grid-column:1/-1">
      <div class="comfort-ring" style="color:${ciColor};border-color:${ciBorder}">${ci}</div>
      <div><div style="font-size:0.75rem;font-weight:600;color:var(--text)">Indeks Kenyamanan</div>
      <div style="font-size:0.7rem;color:var(--text3)">${
        ci >= 70 ? "Nyaman" : "Kurang nyaman untuk aktivitas luar"
      }</div></div>
    </div>`;
  }
  if (groq.risiko_cuaca_ekstrem)
    html += `<div><span style="font-size:0.68rem;color:var(--text3)">Risiko Cuaca Ekstrem</span><br/><strong>${groq.risiko_cuaca_ekstrem}</strong></div>`;
  if (groq.trend_suhu || groq.risiko_angin_kencang)
    html += `<div><span style="font-size:0.68rem;color:var(--text3)">Angin Kencang</span><br/><strong>${
      groq.risiko_angin_kencang || "—"
    }</strong></div>`;
  if (groq.saran_aktivitas_luar)
    html += `<div style="grid-column:1/-1"><span style="font-size:0.68rem;color:var(--text3)">Saran Aktivitas Luar</span><br/>${groq.saran_aktivitas_luar}</div>`;
  if (groq.analisis_kondisi_saat_ini)
    html += `<div style="grid-column:1/-1"><span style="font-size:0.68rem;color:var(--text3)">Kondisi Saat Ini</span><br/>${groq.analisis_kondisi_saat_ini}</div>`;
  if (groq.peringatan_khusus)
    html += `<div class="groq-warn">⚠️ <strong>Peringatan:</strong> ${groq.peringatan_khusus}</div>`;
  document.getElementById("groqBody").innerHTML =
    html || '<div style="color:var(--text3)">Tidak ada data Groq</div>';
  panel.style.display = "block";
}

// ── SOURCES PANEL ────────────────────────────────────────────────────
function renderSourcesPanel(sources) {
  const grid = document.getElementById("sourcesGrid");
  const panel = document.getElementById("sourcesPanel");
  if (!grid || !panel) return;
  const typeIcons = {
    "Cuaca Resmi Indonesia": "🏛️",
    "Kualitas Udara": "💨",
    "Cuaca Real-time": "⛅",
    "Prakiraan 7 Hari": "📅",
    "Sensor Udara": "🔬",
    "Data Sosial": "👥",
    Geocoding: "🗺️",
    "Analisis AI Cuaca": "🤖",
  };
  grid.innerHTML = sources
    .map((s) => {
      const isBMKG = s.name.includes("BMKG");
      const isUnavail = s.name.includes("tidak tersedia");
      return `<a href="${s.url}" target="_blank" rel="noopener"
      class="src-pill${isBMKG && !isUnavail ? " bmkg" : ""}"
      title="${s.type}${
        isUnavail ? " — tidak tersedia untuk wilayah ini" : ""
      }"
      style="${isUnavail ? "opacity:0.5;" : ""}">
      ${typeIcons[s.type] || "🔗"} ${s.name.replace(
        " (tidak tersedia untuk wilayah ini)",
        ""
      )}
    </a>`;
    })
    .join("");
  panel.style.display = "block";
}

function renderMonitorInsight(m) {
  const temuan = (m.temuan_utama || []).slice(0, 3);
  const recs = (m.rekomendasi_segera || []).slice(0, 2);
  let html = "";
  if (m.ringkasan)
    html += `<div style="margin-bottom:8px">${m.ringkasan}</div>`;
  if (temuan.length)
    html +=
      '<div class="ic-tags">' +
      temuan.map((t) => `<span class="ic-tag">${t}</span>`).join("") +
      "</div>";
  if (recs.length)
    html +=
      '<div style="margin-top:8px;font-weight:600;font-size:0.72rem;color:var(--text)">Aksi Segera:</div><div class="ic-tags">' +
      recs.map((r) => `<span class="ic-tag">${r}</span>`).join("") +
      "</div>";
  document.getElementById("monitorInsight").innerHTML = html || "—";
}

function renderPredictInsight(p) {
  let html = "";
  if (p.skor_risiko_iklim !== undefined)
    html += `<div style="margin-bottom:6px">Skor Risiko Iklim: <strong style="font-family:var(--mono);font-size:1rem;color:var(--amber)">${p.skor_risiko_iklim}/100</strong></div>`;
  if (p.risiko_banjir)
    html += `<div>Banjir: <strong>${p.risiko_banjir}</strong></div>`;
  if (p.risiko_kekeringan)
    html += `<div>Kekeringan: <strong>${p.risiko_kekeringan}</strong></div>`;
  if (p.prediksi_mingguan)
    html += `<div style="margin-top:8px">${p.prediksi_mingguan}</div>`;
  document.getElementById("predictInsight").innerHTML = html || "—";
}

function renderSocialInsight(s) {
  let html = "";
  if (s.skor_kerentanan_sosial !== undefined)
    html += `<div style="margin-bottom:6px">Kerentanan Sosial: <strong style="font-family:var(--mono);font-size:1rem;color:var(--blue)">${s.skor_kerentanan_sosial}/100</strong></div>`;
  const k = (s.kelompok_paling_terdampak || s.kelompok_rentan || []).slice(0, 3);
  if (k.length)
    html += '<div class="ic-tags">' + k.map((x) => `<span class="ic-tag">${x}</span>`).join("") + "</div>";
  const dampak = s.ringkasan_sosial || s.dampak || s.raw || "";
  if (dampak) html += `<div style="margin-top:8px">${dampak.slice(0,300)}</div>`;
  document.getElementById("socialInsight").innerHTML = html || "—";
}

function renderEthicsInsight(e) {
  const el = document.getElementById("ethicsInsight");
  if (!el) return;
  let html = "";
  const skor = e.skor_etika || e.ethics_score;
  const catatan = e.catatan_etika || e.catatan || e.raw || "";
  const temuan = e.temuan || e.findings || [];
  if (skor !== undefined)
    html += `<div style="margin-bottom:6px">Skor Etika: <strong style="font-family:var(--mono);font-size:1rem;color:var(--green-d)">${skor}/100</strong></div>`;
  if (temuan.length)
    html += '<div class="ic-tags" style="margin-bottom:6px">' + temuan.slice(0,3).map((t) => `<span class="ic-tag">${t}</span>`).join("") + "</div>";
  if (catatan) html += `<div style="font-size:0.78rem;color:var(--text2)">${catatan.slice(0,300)}</div>`;
  el.innerHTML = html || "—";
}

function renderForecast(days, city) {
  document.getElementById("forecast-city-label").textContent =
    city + " — 5 hari ke depan";
  const icons = ["☀️", "🌤️", "⛅", "🌧️", "⛈️", "🌫️", "🌡️"];
  const grid = document.getElementById("forecastGrid");
  grid.innerHTML = days
    .slice(0, 5)
    .map((d, i) => {
      const dt = new Date(d.date);
      const label =
        i === 0
          ? "Hari Ini"
          : dt.toLocaleDateString("id-ID", { weekday: "short" });
      const rain = parseFloat(d.precipitation) || 0;
      const icon = rain > 10 ? "🌧️" : rain > 3 ? "🌤️" : "☀️";
      return `<div class="fc-day${
        i === 0 ? " today" : ""
      }" onclick="showNotif('${label}: ${d.temp_max}°/${
        d.temp_min
      }° · ${rain}mm hujan')">
<div class="fc-date">${label}</div>
<div class="fc-icon">${icon}</div>
<div class="fc-max">${d.temp_max ?? "—"}°</div>
<div class="fc-min">${d.temp_min ?? "—"}°</div>
<div class="fc-rain">${rain}mm</div>
    </div>`;
    })
    .join("");
}

function renderAksi(monitor, predict, social, city) {
  const recs = [
    ...(monitor.rekomendasi_segera || []),
    ...(social.rekomendasi_inklusif || []),
    ...(predict.hari_terbaik_aktivitas_luar
      ? ["Aktivitas luar: " + predict.hari_terbaik_aktivitas_luar]
      : []),
    ...(social.program_prioritas || []),
  ].slice(0, 8);

  if (recs.length === 0) return;
  aksiTotal = recs.length;
  aksiChecked = 0;

  const colors = [
    "badge-red",
    "badge-amber",
    "badge-teal",
    "badge-blue",
    "badge-green",
  ];
  const tags = [
    "Kritis",
    "Prioritas",
    "Sosial",
    "Lingkungan",
    "Jangka Panjang",
  ];

  document.getElementById(
    "aksiSub"
  ).textContent = `Berdasarkan analisis ${city} — klik untuk menandai selesai`;
  document.getElementById("aksiCount").textContent =
    recs.length + " Aksi";

  document.getElementById("aksiList").innerHTML = recs
    .map(
      (rec, i) => `
    <div class="aksi-item" id="aksi-${i}">
<div class="aksi-num" style="background:var(--green-l);color:var(--green-d)">${
  i + 1
}</div>
<div class="aksi-content">
  <div class="aksi-title">${rec}</div>
  <div class="aksi-meta">
    <span class="aksi-tag ${colors[i % colors.length]}">${
        tags[i % tags.length]
      }</span>
  </div>
</div>
<div class="aksi-check" id="check-${i}" onclick="toggleAksi(${i})"></div>
    </div>
  `
    )
    .join("");

  updateKemajuanAksi();
}

function toggleAksi(i) {
  const el = document.getElementById("check-" + i);
  const item = document.getElementById("aksi-" + i);
  if (el.classList.contains("checked")) {
    el.classList.remove("checked");
    el.textContent = "";
    item.style.opacity = "1";
    aksiChecked = Math.max(0, aksiChecked - 1);
  } else {
    el.classList.add("checked");
    el.textContent = "✓";
    item.style.opacity = "0.6";
    aksiChecked++;
  }
  updateKemajuanAksi();
  showNotif(
    "Rencana aksi " +
      (el.classList.contains("checked") ? "selesai!" : "dibatalkan")
  );
}

function updateKemajuanAksi() {
  const pct =
    aksiTotal > 0 ? Math.round((aksiChecked / aksiTotal) * 100) : 0;
  document.getElementById("kj-aksi-pct").textContent = pct + "%";
  document.getElementById("kj-aksi-fill").style.width = pct + "%";
  document.getElementById("kj-aksi-meta").textContent =
    aksiChecked + " dari " + aksiTotal + " aksi selesai.";
}

function updateKemajuan(data) {
  const m = data.metrics || {};
  const aqi = parseInt(m.aqi) || 0;
  const aqiScore = aqi > 0 ? Math.max(0, 100 - Math.round(aqi / 3)) : 0;
  document.getElementById("kj-aqi-pct").textContent = aqiScore + "%";
  document.getElementById("kj-aqi-fill").style.width = aqiScore + "%";
  document.getElementById(
    "kj-aqi-meta"
  ).textContent = `AQI ${aqi} — ${getAqiLabel(
    aqi
  )}. Semakin rendah AQI, semakin baik.`;

  const riskScore =
    { rendah: 80, sedang: 50, tinggi: 25, kritis: 10 }[data.risk_level] ||
    50;
  document.getElementById("kj-risk-pct").textContent =
    100 - riskScore + "%";
  document.getElementById("kj-risk-fill").style.width =
    100 - riskScore + "%";
  document.getElementById(
    "kj-risk-meta"
  ).textContent = `Tingkat risiko: ${data.risk_level}. Skor semakin tinggi berarti risiko semakin besar.`;

  const soc = data.social?.skor_kerentanan_sosial || 0;
  document.getElementById("kj-social-pct").textContent = soc + "%";
  document.getElementById("kj-social-fill").style.width = soc + "%";
  document.getElementById(
    "kj-social-meta"
  ).textContent = `Skor kerentanan sosial ${soc}/100. Semakin tinggi berarti semakin rentan.`;

  document.getElementById("kj-total-pct").textContent = analysisCount + 1;
  document.getElementById("kj-total-fill").style.width =
    Math.min((analysisCount + 1) * 10, 100) + "%";
  document.getElementById("kj-total-meta").textContent =
    analysisCount +
    1 +
    " analisis dilakukan. Kota terakhir: " +
    data.city;
}

function renderHistory(data) {
  const container = document.getElementById("historyCards");
  const existing = container.querySelectorAll(".history-entry");
  const riskColorMap = {
    rendah: "badge-green",
    sedang: "badge-amber",
    tinggi: "badge-red",
    kritis: "badge-red",
  };
  const card = document.createElement("div");
  card.className = "history-entry";
  card.style.cssText =
    "padding:14px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius-sm);margin-bottom:8px;cursor:pointer;transition:all 0.15s;";
  card.onmouseover = () => (card.style.borderColor = "var(--border2)");
  card.onmouseout = () => (card.style.borderColor = "var(--border)");
  card.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
<div style="font-size:0.82rem;font-weight:600;color:var(--text)">${
  data.city
}</div>
<span class="sc-badge ${
  riskColorMap[data.risk_level] || "badge-amber"
}" style="margin:0">Risiko ${data.risk_level}</span>
    </div>
    <div style="font-size:0.75rem;color:var(--text2);margin-bottom:2px">${document
.getElementById("queryInput")
.value.slice(0, 80)}...</div>
    <div style="font-size:0.68rem;color:var(--text3);font-family:var(--mono)">${new Date().toLocaleString(
"id-ID"
    )}</div>
  `;
  if (container.querySelector(".empty-state")) container.innerHTML = "";
  container.prepend(card);
}

function getAqiLabel(aqi) {
  const n = parseInt(aqi);
  if (isNaN(n)) return "Belum ada data";
  if (n <= 50) return "Baik";
  if (n <= 100) return "Sedang";
  if (n <= 150) return "Tidak Sehat (Sensitif)";
  if (n <= 200) return "Tidak Sehat";
  if (n <= 300) return "Sangat Tidak Sehat";
  return "Berbahaya";
}

function capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "—";
}

// Health check
fetch("/api/health")
  .then((r) => {
    if (r.ok) showNotif("EcoGuardian AI siap digunakan");
  })
  .catch(() => {});


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

// Simpan aksi lengkap untuk modal
let _aksiData = [];

function renderAksiTerstruktur(actions, city) {
  const list = document.getElementById("aksiList");
  const sub  = document.getElementById("aksiSub");
  const cnt  = document.getElementById("aksiCount");
  if (!list || !actions || actions.length === 0) return;

  _aksiData = actions;

  const prioConfig = {
    tinggi:  { color: "badge-red",   icon: "🔴", label: "Tinggi" },
    sedang:  { color: "badge-amber", icon: "🟡", label: "Sedang" },
    rendah:  { color: "badge-green", icon: "🟢", label: "Rendah" },
  };

  if (sub) sub.textContent = `Rencana aksi untuk ${city} — klik untuk detail, ✓ untuk tandai selesai`;
  if (cnt) cnt.textContent = actions.length + " Aksi";

  list.innerHTML = actions.map((a, i) => {
    const prio = prioConfig[a.prioritas] || prioConfig.sedang;
    // Tampilkan aksi singkat — potong di akhir kata
    const aksiShort = a.aksi.length > 80
      ? a.aksi.slice(0, 80).replace(/\s\S+$/, '') + '…'
      : a.aksi;
    return `
    <div class="aksi-item" id="aksi-${i}" onclick="openAksiModal(${i})" style="cursor:pointer">
      <div class="aksi-num" style="background:var(--green-l);color:var(--green-d)">${i + 1}</div>
      <div class="aksi-content">
        <div class="aksi-title">${aksiShort}</div>
        <div class="aksi-meta" style="margin-top:6px">
          <span class="aksi-tag ${prio.color}">${prio.icon} ${prio.label}</span>
          <span class="aksi-tag badge-blue">👤 ${a.pelaku.length > 30 ? a.pelaku.slice(0,30)+'…' : a.pelaku}</span>
        </div>
        <div style="font-size:0.68rem;color:var(--text3);margin-top:4px">🔍 Klik untuk detail lengkap</div>
      </div>
      <div class="aksi-check" id="check-${i}" onclick="event.stopPropagation();toggleAksi(${i})" title="Tandai selesai"></div>
    </div>`;
  }).join("");

  if (typeof updateKemajuanAksi === "function") updateKemajuanAksi();
}

function openAksiModal(i) {
  const a = _aksiData[i];
  if (!a) return;
  const prioLabel = { tinggi: "🔴 Tinggi", sedang: "🟡 Sedang", rendah: "🟢 Rendah" }[a.prioritas] || "🟡 Sedang";
  document.getElementById("modalTitle").textContent = `Rencana Aksi ${i + 1}`;
  document.getElementById("modalDot").style.background = a.prioritas === "tinggi" ? "var(--red)" : a.prioritas === "rendah" ? "var(--green-d)" : "var(--amber)";
  document.getElementById("modalBody").innerHTML = `
    <div style="margin-bottom:12px">
      <div style="font-size:0.7rem;color:#7a967a;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">Prioritas</div>
      <div style="font-weight:600">${prioLabel}</div>
    </div>
    <div style="margin-bottom:12px">
      <div style="font-size:0.7rem;color:#7a967a;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">Pelaku</div>
      <div style="font-weight:600">👤 ${a.pelaku}</div>
    </div>
    <div style="margin-bottom:12px">
      <div style="font-size:0.7rem;color:#7a967a;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">Rencana Aksi</div>
      <div style="line-height:1.7">${a.aksi}</div>
    </div>
    <div style="padding-top:12px;border-top:1px solid #e2e8e2">
      <div style="font-size:0.7rem;color:#7a967a;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">Dampak yang Diharapkan</div>
      <div style="line-height:1.7;color:#4a6a4a">📊 ${a.dampak}</div>
    </div>
  `;
  const modal = document.getElementById("agentModal");
  modal.style.display = "flex";
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
  const raw  = _agentRaw[key];
  const card = document.getElementById(key === "ethics" ? "ethicsInsight" : key + "Insight");
  const text = raw || (card ? card.innerText : "") || "Data belum tersedia.";
  const cleaned = text
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/#{1,6}\s/g, "")
    .trim();
  document.getElementById("modalTitle").textContent = cfg.emoji + " " + cfg.title;
  document.getElementById("modalDot").style.background = cfg.color;
  document.getElementById("modalBody").textContent = cleaned;
  const modal = document.getElementById("agentModal");
  modal.style.display = "flex";
}

function closeAgentModal(e) {
  if (e.target.id === "agentModal") {
    document.getElementById("agentModal").style.display = "none";
  }
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    const m = document.getElementById("agentModal");
    if (m) m.style.display = "none";
  }
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

// ── Landing Page Functions ───────────────────────────────────────────────

// Particle canvas — daun melayang + partikel cahaya
document.addEventListener("DOMContentLoaded", function() {
  const canvas = document.getElementById('lgCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  function resize() {
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  // Particle types: leaf emoji + light dots
  const leaves = ['🍃','🌿','🍀','🌱'];
  const particles = [];

  for (let i = 0; i < 28; i++) {
    particles.push({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      size: Math.random() * 14 + 8,
      speedX: (Math.random() - 0.5) * 0.6,
      speedY: -(Math.random() * 0.4 + 0.2),
      rot: Math.random() * 360,
      rotSpeed: (Math.random() - 0.5) * 1.2,
      opacity: Math.random() * 0.4 + 0.15,
      type: 'leaf',
      emoji: leaves[Math.floor(Math.random() * leaves.length)],
    });
  }
  // Light dots
  for (let i = 0; i < 40; i++) {
    particles.push({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      size: Math.random() * 2.5 + 0.5,
      speedX: (Math.random() - 0.5) * 0.3,
      speedY: -(Math.random() * 0.2 + 0.05),
      opacity: Math.random() * 0.5 + 0.1,
      opacityDir: Math.random() > 0.5 ? 1 : -1,
      type: 'dot',
    });
  }

  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    particles.forEach(p => {
      p.x += p.speedX;
      p.y += p.speedY;
      if (p.type === 'leaf') {
        p.rot += p.rotSpeed;
        p.x += Math.sin(p.y * 0.01) * 0.4;
        if (p.y < -30) { p.y = canvas.height + 20; p.x = Math.random() * canvas.width; }
        if (p.x < -30) p.x = canvas.width + 20;
        if (p.x > canvas.width + 30) p.x = -20;
        ctx.save();
        ctx.globalAlpha = p.opacity;
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot * Math.PI / 180);
        ctx.font = p.size + 'px serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(p.emoji, 0, 0);
        ctx.restore();
      } else {
        p.opacity += p.opacityDir * 0.005;
        if (p.opacity > 0.7 || p.opacity < 0.05) p.opacityDir *= -1;
        if (p.y < -5) { p.y = canvas.height + 5; p.x = Math.random() * canvas.width; }
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(168,240,198,${p.opacity})`;
        ctx.fill();
      }
    });
    requestAnimationFrame(animate);
  }
  animate();
});

function enterDashboard() {
  const landing = document.getElementById('eco-landing');
  const dash    = document.getElementById('eco-dashboard');
  if (!landing || !dash) return;
  landing.classList.add('hide');
  setTimeout(() => {
    landing.style.display = 'none';
    dash.style.display = 'block';
    document.querySelectorAll('.kpi, .stat-card').forEach((c, i) => {
      setTimeout(() => c.classList.add('on'), 80 + i * 100);
    });
  }, 1000);
}

// ── Dark / Light Mode ────────────────────────────────────────────────────

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const btn = document.getElementById("themeToggle");
  if (btn) btn.textContent = theme === "dark" ? "☀️" : "🌙";
  localStorage.setItem("eco_theme", theme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  applyTheme(current === "dark" ? "light" : "dark");
}

// Apply saved theme on load
document.addEventListener("DOMContentLoaded", function() {
  const saved = localStorage.getItem("eco_theme") || "light";
  applyTheme(saved);
});
