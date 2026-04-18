"""
EcoGuardian - Agent Orchestrator (CrewAI)
Pipeline: Monitor -> Predict -> Social -> Ethics -> Report
Fitur:
- Jawaban relevan dengan pertanyaan user
- Rencana aksi terstruktur (prioritas, pelaku, dampak)
- Ethical guardrails
- Reasoning transparency
- Rate limit safe (delay antar task + dual model)
"""

import json
import os
import re
import time
import asyncio
from crewai import Agent, Task, Crew, Process
from crewai import LLM

from memory.db import save_message, save_analysis, get_analysis_history

# Import Supabase wrappers dengan fallback ke SQLite
try:
    from memory.supabase_db import (
        save_message as _save_message,
        save_analysis as _save_analysis,
        get_analysis_history as _get_history,
    )
except Exception:
    _save_message = save_message
    _save_analysis = save_analysis
    _get_history = get_analysis_history
from tools.env_tools import (
    get_air_quality, get_weather, get_forecast,
    get_social_data, get_city_coordinates, get_earthquake_data
)
from tools.notification_tools import generate_report_text, save_report_file

# ---------------------------------------------------------------------------
# Sumber referensi resmi per negara
# ---------------------------------------------------------------------------

OFFICIAL_SOURCES = {
    "ID": [
        {"name": "BMKG", "url": "https://www.bmkg.go.id", "desc": "Badan Meteorologi, Klimatologi, dan Geofisika"},
        {"name": "KLHK", "url": "https://www.menlhk.go.id", "desc": "Kementerian Lingkungan Hidup dan Kehutanan"},
        {"name": "ISPU KLHK", "url": "https://iku.menlhk.go.id", "desc": "Indeks Standar Pencemar Udara resmi Indonesia"},
        {"name": "BPS Indonesia", "url": "https://www.bps.go.id", "desc": "Badan Pusat Statistik"},
        {"name": "BNPB", "url": "https://www.bnpb.go.id", "desc": "Badan Nasional Penanggulangan Bencana"},
    ],
    "SG": [
        {"name": "NEA Singapore", "url": "https://www.nea.gov.sg", "desc": "National Environment Agency"},
        {"name": "MSS Singapore", "url": "https://www.weather.gov.sg", "desc": "Meteorological Service Singapore"},
    ],
    "MY": [
        {"name": "JMM Malaysia", "url": "https://www.met.gov.my", "desc": "Jabatan Meteorologi Malaysia"},
        {"name": "DOE Malaysia", "url": "https://www.doe.gov.my", "desc": "Department of Environment Malaysia"},
    ],
    "TH": [
        {"name": "TMD Thailand", "url": "https://www.tmd.go.th", "desc": "Thai Meteorological Department"},
        {"name": "PCD Thailand", "url": "https://www.pcd.go.th", "desc": "Pollution Control Department"},
    ],
    "JP": [
        {"name": "JMA Japan", "url": "https://www.jma.go.jp", "desc": "Japan Meteorological Agency"},
        {"name": "MOE Japan", "url": "https://www.env.go.jp", "desc": "Ministry of the Environment Japan"},
    ],
}

GLOBAL_SOURCES = [
    {"name": "WAQI", "url": "https://aqicn.org", "desc": "World Air Quality Index"},
    {"name": "Open-Meteo", "url": "https://open-meteo.com", "desc": "Free Weather API"},
    {"name": "World Bank Data", "url": "https://data.worldbank.org", "desc": "Data sosial & ekonomi global"},
    {"name": "WHO Air Quality", "url": "https://www.who.int/health-topics/air-pollution", "desc": "Panduan kualitas udara WHO"},
]

def get_official_sources(country_code: str) -> list:
    return OFFICIAL_SOURCES.get(country_code.upper(), []) + GLOBAL_SOURCES


def compute_ikl(metrics: dict, social: dict, risk_level: str) -> dict:
    """
    Indeks Kesehatan Lingkungan (IKL) — skor 0-100 gabungan semua metrik.
    Semakin tinggi = semakin sehat.
    """
    scores = []

    # AQI score (0-100, makin rendah AQI makin bagus)
    aqi = metrics.get("aqi", "N/A")
    try:
        aqi_val = float(aqi)
        aqi_score = max(0, 100 - (aqi_val / 3))
        scores.append(("Kualitas Udara", round(aqi_score), 0.35))
    except (ValueError, TypeError):
        pass

    # Risk level score
    risk_scores = {"rendah": 90, "sedang": 60, "tinggi": 30, "kritis": 10}
    scores.append(("Tingkat Risiko", risk_scores.get(risk_level, 60), 0.25))

    # Social vulnerability (makin rendah kerentanan makin bagus)
    soc_score = social.get("skor_kerentanan_sosial", 50)
    try:
        social_ikl = max(0, 100 - float(soc_score))
        scores.append(("Kesejahteraan Sosial", round(social_ikl), 0.25))
    except (ValueError, TypeError):
        scores.append(("Kesejahteraan Sosial", 50, 0.25))

    # Temperature comfort (optimal 20-28°C)
    temp = metrics.get("temperature", "N/A")
    try:
        t = float(temp)
        temp_score = max(0, 100 - abs(t - 24) * 5)
        scores.append(("Kenyamanan Suhu", round(temp_score), 0.15))
    except (ValueError, TypeError):
        pass

    if not scores:
        return {"score": 50, "label": "Sedang", "components": []}

    total_weight = sum(w for _, _, w in scores)
    ikl = sum(s * w for _, s, w in scores) / total_weight
    ikl = round(ikl)

    label = "Sangat Baik" if ikl >= 80 else "Baik" if ikl >= 60 else "Sedang" if ikl >= 40 else "Buruk" if ikl >= 20 else "Kritis"
    color = "#22c55e" if ikl >= 80 else "#16a34a" if ikl >= 60 else "#f59e0b" if ikl >= 40 else "#ef4444"

    return {
        "score": ikl,
        "label": label,
        "color": color,
        "components": [{"name": n, "score": s} for n, s, _ in scores],
    }


# ---------------------------------------------------------------------------
# Fetch semua data lingkungan
# ---------------------------------------------------------------------------

async def fetch_all_env_data(city: str, country_code: str) -> dict:
    coords = await get_city_coordinates(city)
    tasks = [get_air_quality(city), get_weather(city), get_social_data(country_code), get_earthquake_data()]
    if coords:
        tasks.append(get_forecast(coords["lat"], coords["lon"]))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {
        "air_quality": results[0] if not isinstance(results[0], Exception) else {"status": "error"},
        "weather":     results[1] if not isinstance(results[1], Exception) else {"status": "error"},
        "social":      results[2] if not isinstance(results[2], Exception) else {"status": "error"},
        "earthquake":  results[3] if not isinstance(results[3], Exception) else {"status": "error"},
        "forecast":    results[4] if len(results) > 4 and not isinstance(results[4], Exception) else {"status": "error"},
        "coords":      coords or {},
    }


# ---------------------------------------------------------------------------
# Parse rencana aksi dari teks laporan
# ---------------------------------------------------------------------------

def parse_action_plan(text: str) -> list:
    """Ekstrak rencana aksi dari teks laporan. Support berbagai format output LLM."""
    import re as _re
    actions = []

    def norm_prio(p: str) -> str:
        p = p.strip().lower()
        if p in ("1", "tinggi", "high"): return "tinggi"
        if p in ("2", "sedang", "medium", "moderate"): return "sedang"
        if p in ("3", "rendah", "low"): return "rendah"
        return p if p in ("tinggi", "sedang", "rendah") else "sedang"

    # Hapus baris instruksi template yang ikut ke output
    clean_lines = []
    for line in text.split("\n"):
        s = line.strip()
        if _re.match(r'^["\']?3 aksi fokus', s, _re.IGNORECASE): continue
        if _re.match(r'^\[PRIORITAS:x\]', s, _re.IGNORECASE): continue
        if _re.match(r'^Buat TEPAT 3 aksi', s, _re.IGNORECASE): continue
        if _re.match(r'^OUTPUT HANYA', s, _re.IGNORECASE): continue
        clean_lines.append(line)
    text = "\n".join(clean_lines)

    # Format 1: [PRIORITAS: x] [PELAKU: x] [AKSI: x] [DAMPAK: x]
    pattern1 = r'\[PRIORITAS:\s*([^\]]+)\]\s*\[PELAKU:\s*([^\]]+)\]\s*\[AKSI:\s*([^\]]+)\]\s*\[DAMPAK:\s*([^\]]+)\]'
    for m in _re.findall(pattern1, text, _re.IGNORECASE):
        actions.append({
            "prioritas": norm_prio(m[0]),
            "pelaku": m[1].strip(),
            "aksi": m[2].strip(),
            "dampak": m[3].strip(),
        })
    if actions:
        return actions[:6]

    # Format 2: satu baris tanpa kurung siku
    pattern2 = r'PRIORITAS:\s*(\S+)\s+PELAKU:\s*(.+?)\s+AKSI:\s*(.+?)\s+DAMPAK:\s*(.+?)(?=PRIORITAS:|$)'
    for m in _re.findall(pattern2, text, _re.IGNORECASE | _re.DOTALL):
        actions.append({
            "prioritas": norm_prio(m[0]),
            "pelaku": _re.sub(r'\s+', ' ', m[1]).strip().rstrip('*'),
            "aksi": _re.sub(r'\s+', ' ', m[2]).strip().rstrip('*'),
            "dampak": _re.sub(r'\s+', ' ', m[3]).strip().rstrip('*'),
        })
    if actions:
        return actions[:6]

    # Format 3: multi-line
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        prio_match = _re.match(r'PRIORITAS:\s*(\S+)', line, _re.IGNORECASE)
        if prio_match:
            prio = norm_prio(prio_match.group(1))
            pelaku = aksi = dampak = ""
            for j in range(i+1, min(i+8, len(lines))):
                l = lines[j].strip()
                if _re.match(r'^PRIORITAS:', l, _re.IGNORECASE): break
                pm = _re.match(r'PELAKU:\s*(.+)', l, _re.IGNORECASE)
                am = _re.match(r'AKSI:\s*(.+)', l, _re.IGNORECASE)
                dm = _re.match(r'DAMPAK:\s*(.+)', l, _re.IGNORECASE)
                if pm: pelaku = pm.group(1).strip()
                if am: aksi = am.group(1).strip()
                if dm: dampak = dm.group(1).strip()
            if aksi:
                actions.append({
                    "prioritas": prio,
                    "pelaku": pelaku or "Pemerintah & Masyarakat",
                    "aksi": aksi,
                    "dampak": dampak or "Peningkatan kondisi lingkungan",
                })
        i += 1
    if actions:
        return actions[:6]

    # Format 4: baris bernomor
    in_aksi = False
    for line in lines:
        line = line.strip()
        if _re.search(r'rencana aksi|action plan', line, _re.IGNORECASE):
            in_aksi = True
            continue
        if in_aksi and _re.match(r'^[\d\-\*\•]+[\.\)]\s+.{10,}', line):
            prio = "sedang"
            if any(w in line.lower() for w in ["segera", "kritis", "darurat", "tinggi"]):
                prio = "tinggi"
            elif any(w in line.lower() for w in ["jangka panjang", "rendah", "opsional"]):
                prio = "rendah"
            clean_line = _re.sub(r'^[\d\-\*\•]+[\.\)]\s+', '', line)
            clean_line = _re.sub(r'\*\*', '', clean_line).strip()
            actions.append({
                "prioritas": prio,
                "pelaku": "Pemerintah & Masyarakat",
                "aksi": clean_line,
                "dampak": "Peningkatan kondisi lingkungan dan sosial",
            })

    return actions[:6]


# ---------------------------------------------------------------------------
# CrewAI Crew Builder
# ---------------------------------------------------------------------------

def _detect_focus(query: str) -> str:
    """Deteksi fokus utama dari query user."""
    q = query.lower()
    if any(w in q for w in ["rekomendasi aksi", "rencana aksi", "aksi konkret", "langkah pencegahan", "solusi", "tindakan"]):
        return "aksi"
    if any(w in q for w in ["cuaca", "hujan", "suhu", "angin", "prakiraan", "prediksi", "iklim", "banjir", "kekeringan"]):
        return "cuaca"
    if any(w in q for w in ["udara", "aqi", "pm2.5", "polusi", "polutan", "asap", "kualitas udara"]):
        return "kualitas_udara"
    if any(w in q for w in ["sosial", "masyarakat", "rentan", "miskin", "kemiskinan", "sanitasi", "kelompok"]):
        return "sosial"
    return "lengkap"


def build_crew(env_data: dict, user_query: str, city: str):
    fast_llm = LLM(
        model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
        api_key=os.getenv("GROQ_API_KEY", ""),
        temperature=0.1,
        timeout=60,
        max_retries=2,
    )
    report_llm = LLM(
        model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
        api_key=os.getenv("GROQ_API_KEY", ""),
        temperature=0.15,
        timeout=60,
        max_retries=2,
    )

    aq      = env_data.get("air_quality", {})
    weather = env_data.get("weather", {})
    social  = env_data.get("social", {}).get("data", {})

    def fmt(key: str) -> str:
        val = social.get(key, {}).get("value")
        if val is None:
            return "N/A"
        try:
            return str(round(float(val)))
        except Exception:
            return str(val)

    forecast_days = env_data.get("forecast", {}).get("forecast", [])[:7]
    eq = env_data.get("earthquake", {})
    focus = _detect_focus(user_query)

    # ── Context injection kaya ─────────────────────────────────────────────
    aqi_val   = aq.get("aqi", "N/A")
    pm25_val  = aq.get("pm25", "N/A")
    temp_val  = weather.get("temperature", "N/A")
    hum_val   = weather.get("humidity", "N/A")
    wind_val  = weather.get("wind_speed", "N/A")
    desc_val  = weather.get("description", "N/A")
    pollutant = aq.get("dominant_pollutant", "N/A")

    try:
        aqi_num = float(aqi_val)
        if aqi_num <= 50:
            aqi_status = f"BAIK ({aqi_num:.0f} — dalam batas aman WHO <50)"
        elif aqi_num <= 100:
            aqi_status = f"SEDANG ({aqi_num:.0f} — {aqi_num-50:.0f} poin di atas zona baik)"
        elif aqi_num <= 150:
            aqi_status = f"TIDAK SEHAT ({aqi_num:.0f} — {aqi_num-100:.0f} poin di atas batas ISPU 100)"
        elif aqi_num <= 200:
            aqi_status = f"SANGAT TIDAK SEHAT ({aqi_num:.0f} — darurat kelompok sensitif)"
        else:
            aqi_status = f"BERBAHAYA ({aqi_num:.0f} — darurat kesehatan publik)"
    except (ValueError, TypeError):
        aqi_status = "DATA TIDAK TERSEDIA dari WAQI"

    try:
        pm25_num = float(pm25_val)
        pm25_status = (
            f"{pm25_num}μg/m³ — AMAN" if pm25_num <= 25
            else f"{pm25_num}μg/m³ — MELEBIHI batas WHO 25μg/m³ sebesar {pm25_num-25:.1f}μg/m³ ({((pm25_num/25)-1)*100:.0f}% di atas batas)"
        )
    except (ValueError, TypeError):
        pm25_status = "DATA TIDAK TERSEDIA"

    fc_summary = ""
    if forecast_days:
        rains = [float(d.get("precipitation") or 0) for d in forecast_days]
        max_rain = max(rains)
        fc_summary = (
            f"Prakiraan 3 hari: curah hujan maks {max_rain:.1f}mm/hari "
            f"({'RISIKO BANJIR TINGGI' if max_rain >= 50 else 'WASPADA' if max_rain >= 20 else 'NORMAL'}), "
            f"suhu {forecast_days[0].get('temp_min','?')}-{forecast_days[0].get('temp_max','?')}°C"
        )

    STANDARDS = (
        "Standar: WHO AQI<50 baik, ISPU 51-100 sedang, 101-199 tidak sehat | "
        "PM2.5<25μg/m³ aman | Banjir>50mm/hari"
    )

    DATA_CONTEXT = (
        f"DATA {city.upper()}: AQI={aqi_status} | PM2.5={pm25_status} | "
        f"Polutan={pollutant} | Suhu={temp_val}°C | Kelembaban={hum_val}% | "
        f"Angin={wind_val}m/s | Cuaca={desc_val} | {fc_summary} | "
        f"Gempa BMKG: M{eq.get('magnitude','N/A')} {eq.get('tanggal','N/A')} {eq.get('wilayah','N/A')} | "
        f"{STANDARDS}"
    )

    SOCIAL_CONTEXT = (
        f"Sosial {city.upper()}: Kemiskinan={fmt('poverty_rate')}% | "
        f"Air bersih={fmt('clean_water_access')}% | Sanitasi={fmt('basic_sanitation')}%"
    )

    # ── Agents dengan persona kuat ─────────────────────────────────────────

    monitor_agent = Agent(
        role="Dr. Rina — Ilmuwan Lingkungan Senior KLHK",
        goal="Analisis kualitas udara dan cuaca berbasis data nyata. Bandingkan dengan standar WHO/ISPU. Jelaskan MENGAPA.",
        backstory="Ilmuwan KLHK 20 tahun. Selalu sebut angka spesifik, bandingkan standar, jelaskan kausalitas. Tidak pernah klaim tanpa data.",
        llm=fast_llm, verbose=False, allow_delegation=False,
    )
    predict_agent = Agent(
        role="Prof. Budi — Ahli Klimatologi BMKG",
        goal="Prediksi risiko iklim dengan probabilitas jelas. Proyeksi 3-7 hari dari data prakiraan.",
        backstory="Klimatologi BMKG spesialis banjir dan polusi. Selalu sebut probabilitas, mekanisme kausal, timeline spesifik.",
        llm=fast_llm, verbose=False, allow_delegation=False,
    )
    social_agent = Agent(
        role="Dr. Siti — Sosiolog Keadilan Lingkungan",
        goal="Analisis dampak pada kelompok rentan. Hitung skor kerentanan 0-100 berbasis World Bank.",
        backstory="Sosiolog pakar keadilan lingkungan. Identifikasi kelompok rentan dengan angka, hubungkan data sosial-ekonomi dengan risiko.",
        llm=fast_llm, verbose=False, allow_delegation=False,
    )
    ethics_agent = Agent(
        role="Ir. Hasan — Auditor Etika AI",
        goal="Validasi output agen: bias, klaim tanpa data, transparansi, keadilan. Skor etika 0-100.",
        backstory="Auditor etika AI prinsip FAT. Verifikasi klaim dengan data, tandai ⚠️ jika tidak berdasar, pastikan rekomendasi realistis.",
        llm=fast_llm, verbose=False, allow_delegation=False,
    )
    report_agent = Agent(
        role="Dr. Arif — Analis Kebijakan Lingkungan",
        goal="Laporan komprehensif menjawab pertanyaan user langsung dengan reasoning eksplisit dan rencana aksi terukur.",
        backstory="Analis kebijakan lingkungan. Jawab pertanyaan langsung, reasoning step-by-step, angka spesifik, aksi realistis.",
        llm=report_llm, verbose=False, allow_delegation=False,
    )

    # ── Tasks dengan Chain-of-Thought & Few-Shot ──────────────────────────

    task_monitor = Task(
        description=(
            f"Pertanyaan: '{user_query[:80]}'\n{DATA_CONTEXT}\n\n"
            "Analisis CoT:\n1.OBSERVASI(angka) 2.INTERPRETASI(standar WHO/ISPU) "
            "3.KAUSALITAS(mengapa) 4.RELEVANSI(jawab pertanyaan) 5.REKOMENDASI(2 aksi)\n"
            "Jika data tidak tersedia, nyatakan eksplisit."
        ),
        expected_output="Analisis 5 langkah CoT dengan angka spesifik dan 2 rekomendasi.",
        agent=monitor_agent,
        callback=lambda _: time.sleep(2),
    )

    task_predict = Task(
        description=(
            f"Pertanyaan: '{user_query[:80]}'\n{DATA_CONTEXT}\n\n"
            f"Prakiraan 7 hari: {json.dumps([{k:v for k,v in d.items() if k in ['date','temp_max','temp_min','precipitation','wind_max']} for d in forecast_days], ensure_ascii=False) if forecast_days else 'N/A'}\n\n"
            "Jika pertanyaan menyebut '7 hari', WAJIB uraikan per periode (hari 1-2, 3-4, 5-7).\n"
            "Format: TREN 7 HARI:[uraian] | RISIKO:[nama] PROBABILITAS:[%] TIMEFRAME:[kapan] | "
            "MEKANISME:[kausal] | MITIGASI 1:[aksi-timeline] | MITIGASI 2:[aksi-timeline]"
        ),
        expected_output="Tren 7 hari, risiko+probabilitas, mekanisme, 2 mitigasi.",
        agent=predict_agent,
        context=[task_monitor],
        callback=lambda _: time.sleep(2),
    )

    task_social = Task(
        description=(
            f"Pertanyaan: '{user_query[:80]}'\n{DATA_CONTEXT}\n{SOCIAL_CONTEXT}\n\n"
            "Hitung skor kerentanan 0-100 (kemiskinan 30%+air bersih 25%+sanitasi 25%+AQI 20%).\n"
            "Format: SKOR KERENTANAN SOSIAL:[n]/100 | KELOMPOK RENTAN:[list] | "
            "KAITAN:[kausal] | REKOMENDASI:[2 solusi inklusif]"
        ),
        expected_output="Skor kerentanan, kelompok rentan, kaitan kausal, 2 rekomendasi.",
        agent=social_agent,
        context=[task_monitor],
        callback=lambda _: time.sleep(2),
    )

    task_ethics = Task(
        description=(
            f"Audit etika analisis {city}: '{user_query[:60]}'\n"
            "Nilai 4 dimensi (masing-masing 0-25): Validitas|Transparansi|Keadilan|Akurasi\n"
            "Format: SKOR ETIKA:[total]/100 | ✅/⚠️ Validitas:[temuan] | "
            "✅/⚠️ Transparansi:[temuan] | ✅/⚠️ Keadilan:[temuan] | CATATAN:[keterbatasan]"
        ),
        expected_output="Skor etika 0-100 dengan 4 temuan dan catatan keterbatasan.",
        agent=ethics_agent,
        context=[task_monitor, task_predict, task_social],
        callback=lambda _: time.sleep(2),
    )

    FOCUS_INSTRUCTIONS = {
        "kualitas_udara": (
            "OUTPUT HANYA section ini (jangan tulis section lain):\n"
            "1. KONDISI SAAT INI\n"
            "Fokus HANYA pada AQI, PM2.5, polutan dominan, dan dampaknya pada kesehatan.\n"
            "Gunakan angka spesifik dan bandingkan dengan standar WHO/ISPU.\n\n"
            "5. RENCANA AKSI\n"
            "3 aksi fokus pengurangan polusi udara.\n"
            "[PRIORITAS:x] [PELAKU:x] [AKSI:x] [DAMPAK:x]\n\n"
            "Baris terakhir: RISK_LEVEL: rendah/sedang/tinggi/kritis"
        ),
        "cuaca": (
            "OUTPUT HANYA section ini (jangan tulis section lain):\n"
            "2. PREDIKSI RISIKO\n"
            "Uraikan prakiraan cuaca 7 hari per periode (hari 1-2, hari 3-4, hari 5-7).\n"
            "Sebutkan suhu, curah hujan, angin per periode. Identifikasi hari paling berisiko.\n"
            "Format: TREN 7 HARI: [uraian] | RISIKO: [nama] PROBABILITAS: [%] | MITIGASI: [aksi]\n\n"
            "5. RENCANA AKSI\n"
            "3 aksi fokus mitigasi cuaca/banjir.\n"
            "[PRIORITAS:x] [PELAKU:x] [AKSI:x] [DAMPAK:x]\n\n"
            "Baris terakhir: RISK_LEVEL: rendah/sedang/tinggi/kritis"
        ),
        "sosial": (
            "OUTPUT HANYA section ini (jangan tulis section lain):\n"
            "3. DAMPAK SOSIAL\n"
            "Hitung skor kerentanan 0-100. Identifikasi kelompok rentan dengan estimasi jumlah.\n"
            "Hubungkan data kemiskinan/sanitasi/air bersih dengan risiko lingkungan.\n"
            "Format: SKOR KERENTANAN: [n]/100 | KELOMPOK: [list] | KAITAN: [kausal]\n\n"
            "5. RENCANA AKSI\n"
            "3 aksi fokus sosial dan inklusif.\n"
            "[PRIORITAS:x] [PELAKU:x] [AKSI:x] [DAMPAK:x]\n\n"
            "Baris terakhir: RISK_LEVEL: rendah/sedang/tinggi/kritis"
        ),
        "aksi": (
            "OUTPUT HANYA section ini (jangan tulis section lain):\n"
            "5. RENCANA AKSI\n"
            "Buat TEPAT 3 aksi konkret berbasis data yang tersedia.\n"
            "Setiap aksi WAJIB format:\n"
            "[PRIORITAS: tinggi/sedang/rendah] [PELAKU: siapa spesifik] [AKSI: tindakan detail] [DAMPAK: angka terukur]\n"
            "Sertakan alasan berbasis data untuk setiap aksi.\n\n"
            "Baris terakhir: RISK_LEVEL: rendah/sedang/tinggi/kritis"
        ),
        "lengkap": (
            "Tulis SEMUA 5 section:\n"
            "1. KONDISI SAAT INI\n2. PREDIKSI RISIKO\n3. DAMPAK SOSIAL\n4. CATATAN ETIKA\n5. RENCANA AKSI\n"
            "Berikan porsi seimbang untuk semua section.\n\n"
            "Baris terakhir: RISK_LEVEL: rendah/sedang/tinggi/kritis"
        ),
    }
    focus_instruction = FOCUS_INSTRUCTIONS.get(focus, FOCUS_INSTRUCTIONS["lengkap"])

    task_report = Task(
        description=(
            f"Laporan EcoGuardian {city}. Jawab: \"{user_query[:100]}\"\n"
            f"{DATA_CONTEXT}\n\n"
            f"{focus_instruction}"
        ),
        expected_output="Laporan sesuai fokus dengan 3 rencana aksi terstruktur, diakhiri RISK_LEVEL.",
        agent=report_agent,
        context=[task_monitor, task_predict, task_social, task_ethics],
    )

    crew = Crew(
        agents=[monitor_agent, predict_agent, social_agent, ethics_agent, report_agent],
        tasks=[task_monitor, task_predict, task_social, task_ethics, task_report],
        process=Process.sequential,
        verbose=False,
    )
    return crew, (task_monitor, task_predict, task_social, task_ethics, task_report)

# ---------------------------------------------------------------------------
# Orchestrator utama
# ---------------------------------------------------------------------------

async def run_ecoguardian_agents(
    user_query: str,
    city: str = "Jakarta",
    country_code: str = "ID",
    session_id: str = "default"
) -> dict:

    if not os.getenv("GROQ_API_KEY"):
        return {
            "success": False,
            "response": "GROQ_API_KEY tidak ditemukan.",
            "risk_level": "sedang", "city": city, "metrics": {},
            "forecast": [], "monitor": {}, "predict": {}, "social": {},
            "ethics": {}, "actions": [], "sources": [], "history": [],
        }

    _save_message(session_id, "user", user_query)
    env_data = await fetch_all_env_data(city, country_code)

    def _run_crew():
        # Fase 1: Monitor, Predict, Social paralel (hemat ~30 detik)
        import concurrent.futures

        def run_single_agent(agent, task):
            """Jalankan satu agen secara independen."""
            mini_crew = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
            )
            result = mini_crew.kickoff()
            time.sleep(2)  # jeda setelah tiap agen
            return str(result).strip()

        crew, tasks = build_crew(env_data, user_query, city)
        task_monitor, task_predict, task_social, task_ethics, task_report = tasks

        # Ambil agen dari crew
        monitor_ag, predict_ag, social_ag, ethics_ag, report_ag = crew.agents

        # Jalankan 3 agen pertama paralel di thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            f_monitor = executor.submit(run_single_agent, monitor_ag, task_monitor)
            f_predict  = executor.submit(run_single_agent, predict_ag, task_predict)
            f_social   = executor.submit(run_single_agent, social_ag, task_social)
            out_monitor = f_monitor.result()
            out_predict  = f_predict.result()
            out_social   = f_social.result()

        time.sleep(2)

        # Fase 2: Ethics dulu (ringan), lalu Report
        out_ethics = run_single_agent(ethics_ag, task_ethics)

        # Report agent
        final_crew = Crew(
            agents=[report_ag],
            tasks=[task_report],
            process=Process.sequential,
            verbose=False,
        )
        final_result = final_crew.kickoff()
        final_text = str(final_result).strip()

        outputs = [out_monitor, out_predict, out_social, out_ethics, final_text]
        return final_text, outputs

    loop = asyncio.get_event_loop()
    task_outputs = [""] * 5
    final_text = ""

    for attempt in range(3):
        try:
            final_text, task_outputs = await loop.run_in_executor(None, _run_crew)
            break
        except Exception as e:
            err = str(e)
            if "rate_limit" in err.lower() and attempt < 2:
                wait = (attempt + 1) * 25  # 25s, 50s
                await asyncio.sleep(wait)
                continue
            final_text = f"Terjadi kesalahan pada agen: {err}"
            break

    # Extract risk level — cari di seluruh teks, tidak hanya baris terakhir
    risk_level = "sedang"
    clean_lines = []
    for line in final_text.split("\n"):
        stripped = line.strip().upper()
        if "RISK_LEVEL:" in stripped or "RISK LEVEL:" in stripped:
            val = re.split(r'RISK[_ ]LEVEL\s*:', line, flags=re.IGNORECASE)[-1].strip().lower()
            # ambil kata pertama saja
            val = val.split()[0].rstrip('.,;') if val.split() else ""
            if val in ("rendah", "sedang", "tinggi", "kritis"):
                risk_level = val
            # jangan masukkan baris ini ke output
        else:
            clean_lines.append(line)
    final_text = "\n".join(clean_lines).strip()

    _save_message(session_id, "assistant", final_text)
    _save_analysis(session_id, user_query, city, final_text[:500], risk_level)

    # Parse output tiap agen — fleksibel, support JSON dan teks bebas
    def parse_output(text: str, fallback_key: str) -> dict:
        if not text:
            return {}
        try:
            start, end = text.find("{"), text.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
        except Exception:
            pass
        return {fallback_key: text}  # teks penuh tanpa dipotong

    monitor_result = parse_output(task_outputs[0], "ringkasan")
    predict_result = parse_output(task_outputs[1], "prediksi")
    social_result  = parse_output(task_outputs[2], "dampak")
    ethics_result  = parse_output(task_outputs[3], "catatan_etika")

    # Ekstrak skor sosial dari teks jika tidak ada di JSON
    if "skor_kerentanan_sosial" not in social_result:
        import re as _re
        raw_social = task_outputs[2] if len(task_outputs) > 2 else ""
        m = _re.search(r'[Ss]kor[^\d]*(\d{1,3})', raw_social)
        social_result["skor_kerentanan_sosial"] = int(m.group(1)) if m else 0

    # Parse rencana aksi dari laporan final
    action_plan = parse_action_plan(final_text)

    # Metrics dengan fallback WAQI
    aq           = env_data.get("air_quality", {})
    weather      = env_data.get("weather", {})
    temperature  = weather.get("temperature", aq.get("temperature", "N/A"))
    humidity     = weather.get("humidity", aq.get("humidity", "N/A"))
    wind_speed   = weather.get("wind_speed", "N/A")
    weather_desc = weather.get("description", "N/A")

    forecast_data = env_data.get("forecast", {})
    forecast_list = (
        forecast_data.get("forecast", [])[:5]
        if forecast_data.get("status") == "ok" else []
    )

    # Generate laporan file untuk download
    metrics_out = {
        "aqi": aq.get("aqi", "N/A"),
        "pm25": aq.get("pm25", "N/A"),
        "temperature": temperature,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "dominant_pollutant": aq.get("dominant_pollutant", "N/A"),
        "weather_desc": weather_desc,
    }

    report_text = generate_report_text(city, risk_level, final_text, metrics_out, action_plan, get_official_sources(country_code))
    report_path = save_report_file(report_text, city)

    return {
        "success": True,
        "response": final_text,
        "risk_level": risk_level,
        "city": city,
        "metrics": metrics_out,
        "forecast": forecast_list,
        "monitor": monitor_result,
        "predict": predict_result,
        "social": social_result,
        "ethics": ethics_result,
        "actions": action_plan,
        "notifications": {},
        "report_file": str(report_path),
        "sources": get_official_sources(country_code),
        "history": _get_history(session_id, limit=3),
        "ikl": compute_ikl(metrics_out, social_result, risk_level),
    }
