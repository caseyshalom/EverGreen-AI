/* EcoGuardian — Social Features (5 fitur dampak sosial) */

// ── Load & render semua fitur sosial ─────────────────────────────────────────

async function loadSocialFeatures() {
  const city = (lastResult && lastResult.city) || localStorage.getItem("eco_last_city") || "Jakarta";
  const countryCode = (lastResult && lastResult.metrics && lastResult.metrics.country) || "ID";

  const infoEl = document.getElementById("socialCityInfo");
  if (infoEl) infoEl.textContent = `Memuat data sosial untuk ${city}...`;

  try {
    const res = await fetch(`/api/social-features/${encodeURIComponent(city)}?country_code=${countryCode}`);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();

    if (infoEl) infoEl.textContent = `Data sosial untuk ${data.city} — AQI: ${data.metrics.aqi} | Suhu: ${data.metrics.temperature}°C`;

    renderCHI(data.chi, data.social_data);
    renderVulnerabilityHeatmap(data.vulnerability_dimensions);
    renderSocialTimeline(data.social_impact);
    renderRadarChart(data.radar_groups);
    renderCommunityActions(data.community_actions, data.city);

  } catch (e) {
    if (infoEl) infoEl.textContent = "Gagal memuat data: " + e.message;
    console.error("Social features error:", e);
  }
}

// ── 1. Community Health Index ─────────────────────────────────────────────────

function renderCHI(chi, socialData) {
  const el = document.getElementById("chi-content");
  const badge = document.getElementById("chi-badge");
  if (!el) return;

  const score = chi.score;
  const color = chi.color;

  // Update hero stats
  const heroScore = document.getElementById("chi-hero-score");
  const heroLabel = document.getElementById("chi-hero-label");
  if (heroScore) heroScore.textContent = score;
  if (heroLabel) heroLabel.textContent = chi.label;

  if (badge) {
    badge.textContent = chi.label;
    badge.className = "sc-badge " + (score >= 80 ? "badge-green" : score >= 60 ? "badge-teal" : score >= 40 ? "badge-amber" : "badge-red");
  }

  const components = [
    { name: "Kualitas Udara", pct: Math.max(0, Math.min(100, Math.round(100 - (parseFloat(socialData.poverty_rate || 0) / 3)))), icon: "🌫️", weight: "35%" },
    { name: "Akses Air Bersih", pct: Math.round(socialData.clean_water_access || 0), icon: "💧", weight: "25%" },
    { name: "Sanitasi Dasar", pct: Math.round(socialData.basic_sanitation || 0), icon: "🚿", weight: "25%" },
    { name: "Bebas Kemiskinan", pct: Math.max(0, Math.min(100, Math.round(100 - (socialData.poverty_rate || 0) * 3))), icon: "💰", weight: "15%" },
  ];

  el.innerHTML = `
    <div style="display:flex;align-items:center;gap:20px;margin-bottom:16px;flex-wrap:wrap">
      <div style="text-align:center">
        <div style="font-size:2.5rem;font-weight:800;color:${color}">${score}</div>
        <div style="font-size:0.72rem;color:var(--text3);font-weight:600">/100</div>
        <div style="font-size:0.78rem;color:${color};font-weight:700;margin-top:2px">${chi.label}</div>
      </div>
      <div style="flex:1;min-width:200px">
        ${components.map(c => {
          const barColor = c.pct >= 70 ? "var(--green)" : c.pct >= 40 ? "var(--amber)" : "var(--red)";
          return `<div style="margin-bottom:8px">
            <div style="display:flex;justify-content:space-between;font-size:0.72rem;margin-bottom:3px">
              <span style="color:var(--text2)">${c.icon} ${c.name}</span>
              <span style="color:var(--text3)">${c.pct}% <span style="opacity:.6">(bobot ${c.weight})</span></span>
            </div>
            <div style="background:var(--border);border-radius:4px;height:7px;overflow:hidden">
              <div style="background:${barColor};width:${c.pct}%;height:100%;border-radius:4px;transition:width 1.2s ease"></div>
            </div>
          </div>`;
        }).join("")}
      </div>
    </div>
    <div style="font-size:0.75rem;color:var(--text3);padding:8px 12px;background:var(--surface2);border-radius:8px;border:1px solid var(--border)">
      ℹ️ Community Health Index menggabungkan kualitas udara, akses air bersih, sanitasi, dan tingkat kemiskinan. Sumber: WAQI + World Bank.
    </div>`;
}

// ── 2. Vulnerability Heatmap ──────────────────────────────────────────────────

function renderVulnerabilityHeatmap(dimensions) {
  const el = document.getElementById("vulnerability-heatmap-content");
  if (!el || !dimensions) return;

  const levelConfig = {
    rendah:  { color: "#22c55e", bg: "#dcfce7", label: "Rendah" },
    sedang:  { color: "#f59e0b", bg: "#fef3c7", label: "Sedang" },
    tinggi:  { color: "#ef4444", bg: "#fee2e2", label: "Tinggi" },
    kritis:  { color: "#dc2626", bg: "#fecaca", label: "Kritis" },
  };

  el.innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;margin-bottom:12px">
      ${dimensions.map(d => {
        const cfg = levelConfig[d.level] || levelConfig.sedang;
        return `<div style="background:${cfg.bg};border:1.5px solid ${cfg.color}33;border-radius:10px;padding:12px;text-align:center">
          <div style="font-size:1.4rem;margin-bottom:4px">${d.icon}</div>
          <div style="font-size:0.72rem;font-weight:700;color:#1a1a1a;margin-bottom:4px">${d.name}</div>
          <div style="font-size:1.2rem;font-weight:800;color:${cfg.color}">${d.value}${d.unit}</div>
          <div style="font-size:0.65rem;color:${cfg.color};font-weight:600;margin-top:4px;text-transform:uppercase">${cfg.label}</div>
          <div style="font-size:0.65rem;color:#555;margin-top:3px">${d.desc}</div>
        </div>`;
      }).join("")}
    </div>
    <div style="font-size:0.72rem;color:#555;display:flex;gap:12px;flex-wrap:wrap">
      ${Object.entries(levelConfig).map(([k, v]) =>
        `<span style="display:flex;align-items:center;gap:4px">
          <span style="width:10px;height:10px;border-radius:2px;background:${v.color};display:inline-block"></span>
          <span style="color:#333">${v.label}</span>
        </span>`
      ).join("")}
      <span style="margin-left:auto;opacity:.7;color:#555">Sumber: World Bank + WAQI</span>
    </div>`;
}

// ── 3. Social Impact Timeline ─────────────────────────────────────────────────

function renderSocialTimeline(impact) {
  const el = document.getElementById("social-timeline-content");
  if (!el || !impact) return;

  // Update hero stat
  const heroAffected = document.getElementById("social-hero-affected");
  if (heroAffected) {
    const n = impact.affected_people;
    heroAffected.textContent = n >= 1000000 ? (n/1000000).toFixed(1)+"jt" : n >= 1000 ? (n/1000).toFixed(0)+"rb" : n;
  }

  const riskColors = { rendah: "#22c55e", sedang: "#f59e0b", tinggi: "#ef4444", kritis: "#dc2626" };
  const riskColor = riskColors[impact.risk_level] || "#f59e0b";

  const formatNum = n => n >= 1000000 ? (n/1000000).toFixed(1) + " juta" : n >= 1000 ? (n/1000).toFixed(0) + " ribu" : n.toString();

  el.innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;margin-bottom:14px">
      <div style="background:var(--surface2);border:1px solid var(--border2);border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:1.6rem;margin-bottom:4px">👥</div>
        <div style="font-size:1.3rem;font-weight:800;color:${riskColor}">${formatNum(impact.affected_people)}</div>
        <div style="font-size:0.7rem;color:var(--text3);margin-top:2px">Warga Terdampak</div>
        <div style="font-size:0.65rem;color:var(--text3)">(${impact.affected_pct}% populasi)</div>
      </div>
      <div style="background:var(--surface2);border:1px solid var(--border2);border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:1.6rem;margin-bottom:4px">📅</div>
        <div style="font-size:1.3rem;font-weight:800;color:var(--amber)">${formatNum(impact.work_days_lost)}</div>
        <div style="font-size:0.7rem;color:var(--text3);margin-top:2px">Hari Kerja Hilang</div>
        <div style="font-size:0.65rem;color:var(--text3)">Estimasi per tahun</div>
      </div>
      <div style="background:var(--surface2);border:1px solid var(--border2);border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:1.6rem;margin-bottom:4px">🏥</div>
        <div style="font-size:1.3rem;font-weight:800;color:var(--red)">Rp ${impact.health_cost_billion_idr}M</div>
        <div style="font-size:0.7rem;color:var(--text3);margin-top:2px">Estimasi Biaya Kesehatan</div>
        <div style="font-size:0.65rem;color:var(--text3)">Miliar rupiah/tahun</div>
      </div>
      <div style="background:var(--surface2);border:1px solid var(--border2);border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:1.6rem;margin-bottom:4px">🏙️</div>
        <div style="font-size:1.3rem;font-weight:800;color:var(--blue)">${impact.population_million}jt</div>
        <div style="font-size:0.7rem;color:var(--text3);margin-top:2px">Populasi Kota</div>
        <div style="font-size:0.65rem;color:var(--text3)">AQI: ${impact.aqi} | PM2.5: ${impact.pm25}</div>
      </div>
    </div>
    <div style="background:var(--amber-l);border:1px solid #fcd34d;border-radius:8px;padding:10px 14px;font-size:0.75rem;color:var(--text2)">
      ⚠️ <strong>Catatan metodologi:</strong> ${impact.note}
    </div>`;
}

// ── 4. Radar Chart Kelompok Rentan ────────────────────────────────────────────

function renderRadarChart(groups) {
  const contentEl = document.getElementById("radar-chart-content");
  const svgEl = document.getElementById("radarSvg");
  if (!contentEl || !groups || groups.length === 0) return;

  const n = groups.length;
  const cx = 200, cy = 170, r = 120;
  const levels = 5;

  // Hitung titik polygon
  function getPoint(i, score) {
    const angle = (Math.PI * 2 * i / n) - Math.PI / 2;
    const radius = (score / 100) * r;
    return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
  }

  function getAxisPoint(i, radius) {
    const angle = (Math.PI * 2 * i / n) - Math.PI / 2;
    return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
  }

  // Grid circles
  let gridLines = "";
  for (let l = 1; l <= levels; l++) {
    const pts = Array.from({length: n}, (_, i) => getAxisPoint(i, r * l / levels));
    const d = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ") + "Z";
    gridLines += `<path d="${d}" fill="none" stroke="var(--border2)" stroke-width="1" opacity="0.6"/>`;
  }

  // Axis lines
  let axisLines = "";
  for (let i = 0; i < n; i++) {
    const p = getAxisPoint(i, r);
    axisLines += `<line x1="${cx}" y1="${cy}" x2="${p.x.toFixed(1)}" y2="${p.y.toFixed(1)}" stroke="var(--border2)" stroke-width="1" opacity="0.5"/>`;
  }

  // Data polygon
  const dataPoints = groups.map((g, i) => getPoint(i, g.score));
  const dataPath = dataPoints.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ") + "Z";

  // Labels
  let labels = "";
  for (let i = 0; i < n; i++) {
    const p = getAxisPoint(i, r + 22);
    const g = groups[i];
    const scoreColor = g.score >= 70 ? "#ef4444" : g.score >= 40 ? "#f59e0b" : "#22c55e";
    labels += `<text x="${p.x.toFixed(1)}" y="${p.y.toFixed(1)}" text-anchor="middle" dominant-baseline="middle"
      font-size="11" fill="var(--text2)" font-family="DM Sans, sans-serif">
      <tspan x="${p.x.toFixed(1)}" dy="-6">${g.icon} ${g.name.split(" ")[0]}</tspan>
      <tspan x="${p.x.toFixed(1)}" dy="14" font-weight="700" fill="${scoreColor}">${g.score}</tspan>
    </text>`;
  }

  // Dots
  let dots = "";
  dataPoints.forEach((p, i) => {
    const score = groups[i].score;
    const dotColor = score >= 70 ? "#ef4444" : score >= 40 ? "#f59e0b" : "#22c55e";
    dots += `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="4" fill="${dotColor}" stroke="white" stroke-width="1.5"/>`;
  });

  const svgContent = `
    ${gridLines}
    ${axisLines}
    <path d="${dataPath}" fill="rgba(239,68,68,0.15)" stroke="#ef4444" stroke-width="2" stroke-linejoin="round"/>
    ${dots}
    ${labels}`;

  // Render SVG
  if (svgEl) {
    svgEl.innerHTML = svgContent;
    svgEl.style.display = "block";
  }

  // Render legend cards
  contentEl.innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px;margin-bottom:14px">
      ${groups.map(g => {
        const scoreColor = g.score >= 70 ? "#ef4444" : g.score >= 40 ? "#f59e0b" : "#22c55e";
        const scoreBg = g.score >= 70 ? "#fee2e2" : g.score >= 40 ? "#fef3c7" : "#dcfce7";
        const label = g.score >= 70 ? "Sangat Rentan" : g.score >= 40 ? "Rentan" : "Aman";
        return `<div style="background:${scoreBg};border:1px solid ${scoreColor}33;border-radius:8px;padding:10px;text-align:center">
          <div style="font-size:1.2rem">${g.icon}</div>
          <div style="font-size:0.68rem;font-weight:700;color:#1a1a1a;margin:3px 0">${g.name}</div>
          <div style="font-size:1.1rem;font-weight:800;color:${scoreColor}">${g.score}<span style="font-size:0.65rem">/100</span></div>
          <div style="font-size:0.62rem;color:${scoreColor};font-weight:600">${label}</div>
        </div>`;
      }).join("")}
    </div>`;
}

// ── 5. Community Action Recommendations ──────────────────────────────────────

function renderCommunityActions(actions, city) {
  const el = document.getElementById("community-actions-content");
  if (!el || !actions) return;

  const actorConfig = {
    "Warga & Keluarga":    { icon: "🏠", color: "var(--green-d)",  bg: "var(--green-l)",  border: "var(--green-m)" },
    "RT/RW & Komunitas":   { icon: "🏘️", color: "var(--teal)",     bg: "var(--teal-l)",   border: "#5eead4" },
    "Sekolah & Kampus":    { icon: "🏫", color: "var(--blue)",     bg: "var(--blue-l)",   border: "#93c5fd" },
    "Puskesmas & Klinik":  { icon: "🏥", color: "#7c3aed",         bg: "#f5f3ff",         border: "#c4b5fd" },
    "Pemerintah Daerah":   { icon: "🏛️", color: "var(--amber)",    bg: "var(--amber-l)",  border: "#fcd34d" },
  };

  el.innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px">
      ${Object.entries(actions).map(([actor, actionList]) => {
        const cfg = actorConfig[actor] || { icon: "👤", color: "var(--text2)", bg: "var(--surface2)", border: "var(--border2)" };
        return `<div style="background:${cfg.bg};border:1.5px solid ${cfg.border};border-radius:10px;padding:14px">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
            <span style="font-size:1.2rem">${cfg.icon}</span>
            <span style="font-size:0.78rem;font-weight:700;color:${cfg.color}">${actor}</span>
          </div>
          <ul style="margin:0;padding-left:16px;list-style:none">
            ${actionList.map(a => `<li style="font-size:0.78rem;color:var(--text2);margin-bottom:6px;line-height:1.5;padding-left:0;display:flex;gap:6px;align-items:flex-start">
              <span style="color:${cfg.color};flex-shrink:0;margin-top:2px">→</span>
              <span>${a}</span>
            </li>`).join("")}
          </ul>
        </div>`;
      }).join("")}
    </div>
    <div style="margin-top:12px;font-size:0.72rem;color:var(--text3);text-align:right">
      Rekomendasi berbasis kondisi lingkungan ${city} saat ini
    </div>`;
}

// Auto-load dipanggil dari showPage di app.js
