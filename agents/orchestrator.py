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
    """
    Ekstrak rencana aksi terstruktur dari teks laporan.
    Support berbagai format output LLM.
    """
    import re as _re
    actions = []

    # Format 1: [PRIORITAS: x] [PELAKU: x] [AKSI: x] [DAMPAK: x]
    pattern1 = r'\[PRIORITAS:\s*(\w+)\]\s*\[PELAKU:\s*([^\]]+)\]\s*\[AKSI:\s*([^\]]+)\]\s*\[DAMPAK:\s*([^\]]+)\]'
    for m in _re.findall(pattern1, text, _re.IGNORECASE):
        actions.append({
            "prioritas": m[0].strip().lower(),
            "pelaku": m[1].strip(),
            "aksi": m[2].strip(),
            "dampak": m[3].strip(),
        })
    if actions:
        return actions[:6]

    # Format 2: PRIORITAS: x PELAKU: x AKSI: x DAMPAK: x (tanpa kurung siku, satu baris)
    pattern2 = r'PRIORITAS:\s*(\w+)\s+PELAKU:\s*(.+?)\s+AKSI:\s*(.+?)\s+DAMPAK:\s*(.+?)(?=PRIORITAS:|$)'
    for m in _re.findall(pattern2, text, _re.IGNORECASE | _re.DOTALL):
        actions.append({
            "prioritas": m[0].strip().lower(),
            "pelaku": _re.sub(r'\s+', ' ', m[1]).strip().rstrip('*'),
            "aksi": _re.sub(r'\s+', ' ', m[2]).strip().rstrip('*'),
            "dampak": _re.sub(r'\s+', ' ', m[3]).strip().rstrip('*'),
        })
    if actions:
        return actions[:6]

    # Format 3: multi-line — PRIORITAS: di satu baris, PELAKU/AKSI/DAMPAK di baris berikutnya
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        prio_match = _re.match(r'PRIORITAS:\s*(\w+)', line, _re.IGNORECASE)
        if prio_match:
            prio = prio_match.group(1).strip().lower()
            pelaku = aksi = dampak = ""
            # Cari PELAKU, AKSI, DAMPAK di baris-baris berikutnya (max 6 baris)
            for j in range(i+1, min(i+7, len(lines))):
                l = lines[j].strip()
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

    # Format 4: baris bernomor di bagian Rencana Aksi
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

def build_crew(env_data: dict, user_query: str, city: str):
    fast_llm = LLM(
        model="groq/llama-3.1-8b-instant",
        api_key=os.getenv("GROQ_API_KEY", ""),
        temperature=0.1,  # lebih deterministik & faktual
    )
    report_llm = LLM(
        model="groq/llama-3.1-8b-instant",
        api_key=os.getenv("GROQ_API_KEY", ""),
        temperature=0.15,  # laporan lebih konsisten
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
        "STANDAR: WHO AQI aman <50 | ISPU: Baik 0-50, Sedang 51-100, "
        "Tidak Sehat 101-199, Sangat Tidak Sehat 200-299, Berbahaya >300 | "
        "PM2.5 harian WHO <25μg/m³ | Banjir >50mm/hari | Suhu nyaman 20-28°C"
    )

    DATA_CONTEXT = (
        f"DATA REAL-TIME {city.upper()}:\n"
        f"- Kualitas Udara: {aqi_status}\n"
        f"- PM2.5: {pm25_status}\n"
        f"- Polutan dominan: {pollutant}\n"
        f"- Suhu: {temp_val}°C | Kelembaban: {hum_val}% | Angin: {wind_val} m/s\n"
        f"- Kondisi cuaca: {desc_val}\n"
        f"- {fc_summary}\n"
        f"- Gempa terbaru BMKG: M{eq.get('magnitude','N/A')} {eq.get('tanggal','N/A')} — {eq.get('wilayah','N/A')}\n"
        f"{STANDARDS}"
    )

    SOCIAL_CONTEXT = (
        f"DATA SOSIAL {city.upper()} (World Bank):\n"
        f"- Kemiskinan: {fmt('poverty_rate')}% | Air bersih: {fmt('clean_water_access')}%\n"
        f"- Sanitasi: {fmt('basic_sanitation')}% | Listrik: {fmt('electricity_access')}%"
    )

    # ── Agents dengan persona kuat ─────────────────────────────────────────

    monitor_agent = Agent(
        role="Dr. Rina — Ilmuwan Lingkungan Senior KLHK",
        goal=(
            "Analisis kualitas udara dan cuaca secara mendalam berbasis data nyata. "
            "Selalu bandingkan dengan standar WHO/ISPU. Jelaskan MENGAPA kondisi terjadi."
        ),
        backstory=(
            "Kamu adalah Dr. Rina, ilmuwan lingkungan senior KLHK dengan 20 tahun pengalaman. "
            "Kamu SELALU: (1) menyebut angka spesifik dari data, "
            "(2) membandingkan dengan standar WHO/ISPU secara eksplisit, "
            "(3) menjelaskan kausalitas — mengapa kondisi ini terjadi, "
            "(4) tidak pernah membuat klaim tanpa data. "
            "Jika data tidak tersedia, kamu tegas menyatakannya."
        ),
        llm=fast_llm, verbose=False, allow_delegation=False,
    )
    predict_agent = Agent(
        role="Prof. Budi — Ahli Klimatologi & Manajemen Risiko Bencana BMKG",
        goal=(
            "Prediksi risiko iklim dan bencana dengan probabilitas yang jelas. "
            "Gunakan data prakiraan untuk proyeksi 3-7 hari ke depan."
        ),
        backstory=(
            "Kamu adalah Prof. Budi, ahli klimatologi BMKG spesialis prediksi banjir dan polusi. "
            "Kamu SELALU: (1) menyebut persentase probabilitas risiko, "
            "(2) menjelaskan mekanisme kausal (curah hujan X mm → potensi banjir di Y), "
            "(3) tidak melebih-lebihkan risiko tanpa data, "
            "(4) memberi rentang waktu spesifik untuk setiap prediksi."
        ),
        llm=fast_llm, verbose=False, allow_delegation=False,
    )
    social_agent = Agent(
        role="Dr. Siti — Sosiolog & Pakar Keadilan Lingkungan",
        goal=(
            "Analisis dampak lingkungan pada kelompok rentan dengan perspektif keadilan sosial. "
            "Hitung skor kerentanan sosial 0-100 berbasis data World Bank."
        ),
        backstory=(
            "Kamu adalah Dr. Siti, sosiolog senior pakar keadilan lingkungan. "
            "Kamu SELALU: (1) mengidentifikasi kelompok paling terdampak dengan estimasi jumlah, "
            "(2) menghubungkan data sosial-ekonomi dengan risiko lingkungan secara kausal, "
            "(3) memberikan skor kerentanan 0-100 dengan penjelasan komponen, "
            "(4) merekomendasikan solusi inklusif yang mempertimbangkan keterbatasan ekonomi."
        ),
        llm=fast_llm, verbose=False, allow_delegation=False,
    )
    ethics_agent = Agent(
        role="Ir. Hasan — Auditor Etika AI & Transparansi Data",
        goal=(
            "Validasi seluruh output agen: periksa bias, klaim tanpa data, transparansi, keadilan. "
            "Berikan skor etika 0-100 dengan temuan spesifik."
        ),
        backstory=(
            "Kamu adalah Ir. Hasan, auditor etika AI yang menerapkan prinsip FAT "
            "(Fairness, Accountability, Transparency). "
            "Kamu SELALU: (1) memverifikasi setiap klaim dengan data sumbernya, "
            "(2) menandai klaim tidak berdasar dengan ⚠️, "
            "(3) memastikan rekomendasi realistis dan tidak diskriminatif, "
            "(4) memberikan skor etika dengan breakdown per dimensi."
        ),
        llm=fast_llm, verbose=False, allow_delegation=False,
    )
    report_agent = Agent(
        role="Dr. Arif — Analis Kebijakan Lingkungan & Komunikator Sains",
        goal=(
            "Susun laporan komprehensif yang menjawab pertanyaan user secara langsung "
            "dengan reasoning eksplisit dan rencana aksi terukur berbasis data."
        ),
        backstory=(
            "Kamu adalah Dr. Arif, analis kebijakan lingkungan yang ahli mengubah data kompleks "
            "menjadi rekomendasi aksi konkret dan terukur. "
            "Kamu SELALU: (1) menjawab pertanyaan user langsung di paragraf pertama, "
            "(2) menjelaskan reasoning step-by-step (observasi → interpretasi → kausalitas → rekomendasi), "
            "(3) menggunakan angka spesifik untuk setiap klaim, "
            "(4) membuat rencana aksi realistis dengan pelaku, timeline, dan dampak terukur."
        ),
        llm=report_llm, verbose=False, allow_delegation=False,
    )

    # ── Tasks dengan Chain-of-Thought & Few-Shot ──────────────────────────

    task_monitor = Task(
        description=(
            f"Pertanyaan user: '{user_query[:120]}'\n\n"
            f"{DATA_CONTEXT}\n\n"
            "Ikuti langkah Chain-of-Thought:\n"
            "1. OBSERVASI: Apa yang data tunjukkan secara faktual? (sebutkan angka)\n"
            "2. INTERPRETASI: Apa artinya bagi kesehatan manusia berdasarkan standar WHO/ISPU?\n"
            "3. KAUSALITAS: Mengapa kondisi ini terjadi? (faktor cuaca, musim, aktivitas manusia)\n"
            "4. RELEVANSI: Bagaimana ini menjawab pertanyaan user?\n"
            "5. REKOMENDASI: 2 aksi spesifik berbasis data\n\n"
            "Contoh format yang baik:\n"
            "'AQI 156 (Tidak Sehat) — 56 poin di atas batas ISPU 100. "
            "PM2.5 67μg/m³ = 2.7x batas harian WHO. "
            "Penyebab: suhu tinggi 32°C + kelembaban rendah mempercepat pembentukan ozon troposfer. "
            "Dampak: iritasi saluran napas pada populasi sensitif dalam 2-3 jam paparan luar ruangan.'\n\n"
            "PENTING: Jika data 'TIDAK TERSEDIA', nyatakan eksplisit — jangan mengarang nilai."
        ),
        expected_output=(
            "Analisis 5 langkah CoT: observasi faktual → interpretasi standar → "
            "kausalitas → relevansi → 2 rekomendasi berbasis angka."
        ),
        agent=monitor_agent,
        callback=lambda _: time.sleep(5),
    )

    task_predict = Task(
        description=(
            f"Pertanyaan user: '{user_query[:120]}'\n\n"
            f"{DATA_CONTEXT}\n\n"
            f"DATA PRAKIRAAN LENGKAP 7 HARI KE DEPAN:\n"
            f"{json.dumps(forecast_days, ensure_ascii=False, indent=2) if forecast_days else 'Data prakiraan tidak tersedia'}\n\n"
            "PENTING: Jika pertanyaan menyebut '7 hari', kamu WAJIB membahas setiap hari atau minimal per periode (hari 1-2, hari 3-4, hari 5-7).\n\n"
            "Ikuti langkah Chain-of-Thought:\n"
            "1. TREN HARIAN: Uraikan kondisi per hari atau per periode dari data prakiraan di atas\n"
            "2. IDENTIFIKASI RISIKO: Hari/periode mana yang paling berisiko? Mengapa?\n"
            "3. MEKANISME: Jelaskan mekanisme kausal risiko tersebut\n"
            "4. PROBABILITAS: Estimasi probabilitas (rendah <30% / sedang 30-60% / tinggi >60%)\n"
            "5. MITIGASI: 2 langkah mitigasi spesifik dengan timeline\n\n"
            "Format output wajib:\n"
            "TREN 7 HARI: [uraian per hari/periode dengan angka suhu dan curah hujan]\n"
            "RISIKO UTAMA: [nama] | PROBABILITAS: [%] | TIMEFRAME: [hari ke berapa]\n"
            "MEKANISME: [penjelasan kausal]\n"
            "MITIGASI 1: [aksi] — [timeline]\n"
            "MITIGASI 2: [aksi] — [timeline]"
        ),
        expected_output=(
            "Uraian tren 7 hari per periode, prediksi risiko dengan probabilitas, "
            "mekanisme kausal, dan 2 mitigasi bertimeline."
        ),
        agent=predict_agent,
        context=[task_monitor],
        callback=lambda _: time.sleep(5),
    )

    task_social = Task(
        description=(
            f"Pertanyaan user: '{user_query[:120]}'\n\n"
            f"{DATA_CONTEXT}\n\n"
            f"{SOCIAL_CONTEXT}\n\n"
            "Ikuti langkah Chain-of-Thought:\n"
            "1. PROFIL KERENTANAN: Siapa kelompok paling rentan?\n"
            "2. KAITAN DATA: Bagaimana data sosial-ekonomi memperburuk dampak lingkungan?\n"
            "3. SKOR KERENTANAN: Hitung skor 0-100 (kemiskinan 30% + air bersih 25% + sanitasi 25% + AQI 20%)\n"
            "4. DAMPAK SPESIFIK: Dampak pada tiap kelompok rentan\n"
            "5. REKOMENDASI INKLUSIF: 2 solusi yang mempertimbangkan keterbatasan ekonomi\n\n"
            "Format output wajib:\n"
            "SKOR KERENTANAN SOSIAL: [angka]/100\n"
            "KELOMPOK RENTAN: [daftar dengan estimasi jumlah]\n"
            "KAITAN LINGKUNGAN-SOSIAL: [penjelasan kausal]\n"
            "REKOMENDASI: [2 solusi inklusif]"
        ),
        expected_output=(
            "Skor kerentanan sosial dengan breakdown, kelompok rentan, "
            "kaitan kausal lingkungan-sosial, dan 2 rekomendasi inklusif."
        ),
        agent=social_agent,
        context=[task_monitor],
        callback=lambda _: time.sleep(5),
    )

    task_ethics = Task(
        description=(
            f"Audit etika analisis {city} untuk: '{user_query[:100]}'\n\n"
            "Periksa output agen sebelumnya dengan kriteria:\n"
            "1. VALIDITAS DATA (0-25 poin): Apakah setiap klaim didukung data nyata?\n"
            "2. TRANSPARANSI (0-25 poin): Apakah keterbatasan data disebutkan eksplisit?\n"
            "3. KEADILAN (0-25 poin): Apakah rekomendasi dapat diakses semua lapisan?\n"
            "4. AKURASI (0-25 poin): Apakah angka dan persentase konsisten?\n\n"
            "Format output wajib:\n"
            "SKOR ETIKA: [total]/100\n"
            "✅/⚠️ Validitas: [temuan]\n"
            "✅/⚠️ Transparansi: [temuan]\n"
            "✅/⚠️ Keadilan: [temuan]\n"
            "CATATAN: [keterbatasan data yang perlu diungkapkan ke user]"
        ),
        expected_output=(
            "Skor etika 0-100 dengan breakdown 4 dimensi dan catatan keterbatasan data."
        ),
        agent=ethics_agent,
        context=[task_monitor, task_predict, task_social],
        callback=lambda _: time.sleep(5),
    )

    task_report = Task(
        description=(
            f"Buat laporan EcoGuardian untuk {city}.\n\n"
            f"JAWAB LANGSUNG pertanyaan ini di paragraf pertama: \"{user_query[:150]}\"\n\n"
            f"{DATA_CONTEXT}\n\n"
            "FORMAT WAJIB — tulis persis dengan heading ini:\n\n"
            "1. KONDISI SAAT INI\n"
            "Jawab pertanyaan user langsung. Gunakan format reasoning:\n"
            "[Observasi data dengan angka] → [Interpretasi standar WHO/ISPU] → [Kausalitas mengapa terjadi]\n\n"
            "2. PREDIKSI RISIKO\n"
            "Format: [Risiko] | Probabilitas: [%] | Timeframe: [kapan] | Mekanisme: [mengapa]\n\n"
            "3. DAMPAK SOSIAL\n"
            "Format: [Kelompok] → [Dampak spesifik] → [Kaitan data sosial-ekonomi]\n\n"
            "4. CATATAN ETIKA\n"
            "Sebutkan apa yang TIDAK bisa disimpulkan dari data ini. Transparansi keterbatasan.\n\n"
            "5. RENCANA AKSI\n"
            "Tepat 3 aksi, format wajib:\n"
            "[PRIORITAS: tinggi/sedang/rendah] [PELAKU: siapa] [AKSI: tindakan spesifik] "
            "[DAMPAK: dampak terukur dalam angka/persentase]\n"
            "Sertakan alasan berbasis data untuk setiap aksi.\n\n"
            "Baris terakhir (wajib, harus persis seperti ini tanpa teks lain): RISK_LEVEL: rendah/sedang/tinggi/kritis"
        ),
        expected_output=(
            "Laporan 5 bagian dengan Chain-of-Thought reasoning, angka spesifik, "
            "3 rencana aksi terstruktur, diakhiri RISK_LEVEL."
        ),
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
            time.sleep(3)  # jeda setelah tiap agen
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

        time.sleep(3)

        # Fase 2: Ethics lalu Report (butuh konteks dari fase 1)
        out_ethics = run_single_agent(ethics_ag, task_ethics)
        time.sleep(3)

        # Report agent — jalankan dengan full crew untuk dapat konteks
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
