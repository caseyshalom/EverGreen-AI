# 🌿 EverGreen AI — Dokumentasi Teknis

> Sistem **Agentic AI** untuk Pemantauan Lingkungan, Prediksi Risiko Iklim, dan Analisis Dampak Sosial secara Real-Time.

Author: Team G.R.E.E.N

---

## 1. Arsitektur Sistem & AI Agent

### Gambaran Umum

EverGreen AI menggabungkan **5 API data lingkungan**, **5 AI Agent otonom**, dan **1 dashboard interaktif** dalam satu sistem terpadu. Setiap request analisis memicu pipeline multi-agent yang bekerja secara paralel dan sekuensial untuk menghasilkan laporan komprehensif.

```
┌─────────────────────────────────────────────────────────────┐
│                        USER / BROWSER                        │
│              Dashboard (HTML + CSS + JavaScript)             │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP Request
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   FASTAPI BACKEND (main.py)                  │
│  • Routing & Validasi    • Alert Logic (WHO/ISPU threshold)  │
│  • Community Health Index (CHI)    • Download Report      │
└──────────────────────────┬──────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
   │  WAQI API   │  │    OWM API  │  │ Open-Meteo  │
   │  AQI/PM2.5  │  │   Cuaca     │  │ Forecast 7h │
   └─────────────┘  └─────────────┘  └─────────────┘
          ▼                ▼                ▼
   ┌─────────────┐  ┌─────────────┐
   │  World Bank │  │    BMKG     │
   │  Data Sosial│  │    Gempa    │
   └─────────────┘  └─────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              CREWAI ORCHESTRATOR (orchestrator.py)           │
│                                                              │
│  ┌─── FASE 1: PARALEL (ThreadPoolExecutor, max_workers=3) ──┐│
│  │  🌫️ Monitor Agent   📈 Predict Agent   👥 Social Agent   ││
│  └───────────────────────────────────────────────────────────┘│
│                           │                                  │
│  ┌─── FASE 2: SEQUENTIAL ────────────────────────────────────┐│
│  │         🛡️ Ethics Agent  →  📋 Report Agent              ││
│  └───────────────────────────────────────────────────────────┘│
└──────────────────────────┬──────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
   │  Supabase   │  │   SQLite    │  │  JSON resp  │
   │ (Primary DB)│  │  (Fallback) │  │  ke Frontend│
   └─────────────┘  └─────────────┘  └─────────────┘
```

---

### LLM & Framework

| Komponen | Teknologi |
|----------|-----------|
| **LLM** | Meta **Llama 4 Scout 17B** (`meta-llama/llama-4-scout-17b-16e-instruct`) |
| **LLM Provider** | **Groq** — inferensi ultra-cepat, limit 30.000 token/menit (free tier) |
| **Agentic Framework** | **CrewAI ≥ 0.80.0** |
| **Backend** | **FastAPI** + Uvicorn (Python 3.11) |
| **HTTP Client** | `httpx` (async) |
| **Database** | **Supabase** (PostgreSQL cloud) + **SQLite** (fallback lokal) |
| **Frontend** | HTML5, CSS3, JavaScript ES2022, Leaflet.js |

---

### Alur Kerja Agent

EverGreen AI menggunakan **kombinasi dua pola**:

#### Pola 1 — Parallel Execution (Fase 1)

Tiga agen pertama berjalan **bersamaan** menggunakan `ThreadPoolExecutor` untuk menghemat waktu ~30 detik:

```
Monitor Agent ──┐
Predict Agent ──┼──► (berjalan paralel, tidak saling tunggu)
Social Agent  ──┘
```

#### Pola 2 — Sequential dengan Context Chaining (Fase 2)

Ethics dan Report Agent berjalan **berurutan** dan menerima output dari semua agen sebelumnya sebagai konteks:

```
[Monitor + Predict + Social output]
            │
            ▼
      Ethics Agent  ──► validasi bias & akurasi
            │
            ▼
      Report Agent  ──► laporan final + rencana aksi
```

#### Pola Berpikir Agent: Chain-of-Thought (CoT)

Setiap agen menggunakan prompt CoT 5 langkah:
1. **OBSERVASI** — baca angka dari data real-time
2. **INTERPRETASI** — bandingkan dengan standar WHO/ISPU
3. **KAUSALITAS** — jelaskan mengapa kondisi ini terjadi
4. **RELEVANSI** — hubungkan dengan pertanyaan user
5. **REKOMENDASI** — berikan 2 aksi konkret

#### Memory & State

- **Session memory** disimpan di database (Supabase/SQLite) per `session_id`
- Setiap request membawa riwayat analisis sesi untuk konteks
- EcoBot Chat menyimpan history 6 pesan terakhir untuk percakapan kontekstual

---

### Profil 5 AI Agent

| Agent | Persona | Tugas | Output |
|-------|---------|-------|--------|
| 🌫️ **Monitor** | Dr. Rina — Ilmuwan KLHK | Analisis AQI, PM2.5, cuaca vs standar WHO/ISPU | Analisis CoT 5 langkah |
| 📈 **Predict** | Prof. Budi — Klimatologi BMKG | Prediksi risiko banjir & polusi 7 hari | Tren + probabilitas + mitigasi |
| 👥 **Social** | Dr. Siti — Sosiolog | Skor kerentanan sosial 0–100, kelompok rentan | Skor + kelompok + rekomendasi inklusif |
| 🛡️ **Ethics** | Ir. Hasan — Auditor AI | Validasi 4 dimensi: Validitas, Transparansi, Keadilan, Akurasi | Skor etika 0–100 |
| 📋 **Report** | Dr. Arif — Analis Kebijakan | Laporan final + 3 rencana aksi terstruktur | Laporan lengkap + RISK_LEVEL |

---

### Database & Backend

**Backend:** Python 3.11 + **FastAPI** 0.115 + Uvicorn 0.30

**Database — Dual Layer:**

```
Request masuk
     │
     ▼
Supabase (PostgreSQL) ──► jika SUPABASE_URL & SUPABASE_KEY tersedia
     │
     └── Gagal / tidak dikonfigurasi
              │
              ▼
         SQLite lokal (data/evergreen.db) ──► selalu tersedia
```

**Tabel database:**

| Tabel | Database | Fungsi |
|-------|----------|--------|
| `sessions` | Supabase + SQLite | Riwayat percakapan per sesi (JSON array) |
| `analysis_history` | Supabase + SQLite | Log analisis: kota, query, ringkasan, risk level |

---

## 2. Struktur Folder Proyek

```
EverGreen-AI/
│
├── 📄 main.py                    # FastAPI app — semua endpoint, alert logic, CHI
├── 📄 requirements.txt           # Dependencies Python
├── 📄 Dockerfile                 # Container untuk Hugging Face Spaces (port 7860)
├── 📄 supabase_setup.sql         # DDL setup tabel Supabase
├── 📄 .env                       # API keys (tidak di-commit ke Git)
├── 📄 .gitignore
│
├── 📁 agents/
│   ├── 📄 __init__.py
│   └── 📄 orchestrator.py        # ⭐ Inti sistem: CrewAI pipeline, 5 agen, IKL
│
├── 📁 tools/
│   ├── 📄 __init__.py
│   ├── 📄 env_tools.py           # Fetch data: WAQI, OWM, Open-Meteo, WorldBank, BMKG
│   └── 📄 notification_tools.py  # Generate & simpan laporan .txt
│
├── 📁 memory/
│   ├── 📄 __init__.py
│   ├── 📄 db.py                  # SQLite: sessions, env_cache, analysis_history
│   └── 📄 supabase_db.py         # Supabase wrapper + auto-fallback ke SQLite
│
├── 📁 static/
│   ├── 📁 css/
│   │   └── 📄 style.css          # Stylesheet (dark/light mode, responsive)
│   ├── 📁 js/
│   │   ├── 📄 app.js             # Logic dashboard: analisis, peta, EcoBot, auto-monitor
│   │   └── 📄 social_features.js # CHI, radar chart kerentanan, dampak sosial
│   └── 📄 favicon.ico
│
├── 📁 templates/
│   └── 📄 index.html             # Single-page dashboard
│
└── 📁 data/
    ├── 📄 evergreen.db           # SQLite database (auto-generated saat runtime)
    └── 📁 reports/               # File laporan .txt hasil analisis
```

---

## 3. Penjelasan Kode Utama

### 3.1 Inisialisasi Agent & Task (CrewAI)

```python
# agents/orchestrator.py

def build_crew(env_data: dict, user_query: str, city: str):
    # LLM dikonfigurasi dengan temperature rendah untuk analisis deterministik
    fast_llm = LLM(
        model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.1,   # deterministik untuk analisis data
        timeout=60,
        max_retries=2,
    )

    # Setiap agent punya persona spesifik untuk meningkatkan kualitas output LLM
    monitor_agent = Agent(
        role="Dr. Rina — Ilmuwan Lingkungan Senior KLHK",
        goal="Analisis kualitas udara dan cuaca berbasis data nyata. Bandingkan dengan standar WHO/ISPU.",
        backstory="Ilmuwan KLHK 20 tahun. Selalu sebut angka spesifik, jelaskan kausalitas.",
        llm=fast_llm,
        allow_delegation=False,
    )

    # Task menerima data real-time sebagai konteks langsung di prompt
    task_monitor = Task(
        description=(
            f"Pertanyaan: '{user_query}'\n"
            f"DATA {city}: AQI={aqi_status} | PM2.5={pm25_status} | Suhu={temp}°C\n\n"
            "Analisis CoT: 1.OBSERVASI 2.INTERPRETASI 3.KAUSALITAS 4.RELEVANSI 5.REKOMENDASI"
        ),
        expected_output="Analisis 5 langkah CoT dengan angka spesifik dan 2 rekomendasi.",
        agent=monitor_agent,
        callback=lambda _: time.sleep(2),  # rate limit protection
    )
```

> **Penjelasan:** Setiap agent diberi persona yang kuat (nama, jabatan, backstory) agar LLM menghasilkan output yang lebih spesifik dan berbasis data. Data real-time diinjeksikan langsung ke dalam prompt task sebagai `DATA_CONTEXT`.

---

### 3.2 Pipeline Paralel + Sequential

```python
# agents/orchestrator.py — fungsi _run_crew() di dalam run_greenai_agents()

def _run_crew():
    crew, tasks = build_crew(env_data, user_query, city)
    monitor_ag, predict_ag, social_ag, ethics_ag, report_ag = crew.agents

    # ── FASE 1: Jalankan 3 agen PARALEL ──────────────────────────
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f_monitor = executor.submit(run_single_agent, monitor_ag, task_monitor)
        f_predict  = executor.submit(run_single_agent, predict_ag, task_predict)
        f_social   = executor.submit(run_single_agent, social_ag,  task_social)
        out_monitor = f_monitor.result()
        out_predict  = f_predict.result()
        out_social   = f_social.result()

    # ── FASE 2: Ethics → Report SEQUENTIAL ───────────────────────
    out_ethics = run_single_agent(ethics_ag, task_ethics)
    # Report agent menerima output semua agen sebelumnya sebagai konteks
    final_result = run_single_agent(report_ag, task_report)
```

> **Penjelasan:** Fase 1 menggunakan `ThreadPoolExecutor` agar 3 agen berjalan bersamaan, menghemat ~30 detik. Fase 2 berjalan sekuensial karena Ethics Agent perlu mengevaluasi output Fase 1, dan Report Agent perlu output Ethics untuk laporan final.

---

### 3.3 Fetch Data Lingkungan (Async Parallel)

```python
# tools/env_tools.py

async def get_air_quality(city: str) -> dict:
    token = os.getenv("WAQI_TOKEN", "demo")
    url = f"https://api.waqi.info/feed/{city}/?token={token}"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        data = resp.json()

    if data.get("status") == "ok":
        d = data["data"]
        return {
            "aqi": d.get("aqi"),
            "pm25": d["iaqi"].get("pm25", {}).get("v"),
            "dominant_pollutant": d.get("dominentpol"),
            # ... field lainnya
        }

# agents/orchestrator.py — semua API dipanggil sekaligus
async def fetch_all_env_data(city: str, country_code: str) -> dict:
    results = await asyncio.gather(
        get_air_quality(city),
        get_weather(city),
        get_social_data(country_code),
        get_earthquake_data(),
        get_forecast(lat, lon),
        return_exceptions=True   # satu API gagal tidak crash semua
    )
```

> **Penjelasan:** Semua API call dijalankan bersamaan dengan `asyncio.gather()`. Parameter `return_exceptions=True` memastikan jika satu API gagal (timeout, error), API lainnya tetap berjalan dan hasilnya tetap dikembalikan.

---

### 3.4 Fallback Database (Supabase → SQLite)

```python
# memory/supabase_db.py

_supabase_client = None  # Singleton pattern

def get_supabase():
    global _supabase_client
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        return None   # Supabase tidak dikonfigurasi → gunakan SQLite
    if _supabase_client is None:
        _supabase_client = create_client(url, key)
    return _supabase_client

def save_analysis(session_id, query, city, summary, risk_level):
    sb = get_supabase()
    if not sb:
        return _fallback_save_analysis(...)  # → SQLite otomatis

    try:
        sb.table("analysis_history").insert({...}).execute()
    except Exception:
        _reset_client()                      # reset untuk reconnect
        _fallback_save_analysis(...)         # → SQLite sebagai backup
```

> **Penjelasan:** Sistem menggunakan pola **primary-fallback**. Jika Supabase tidak dikonfigurasi atau koneksi gagal, semua operasi database otomatis dialihkan ke SQLite lokal tanpa error ke user.

---

### 3.5 Kalkulasi Indeks Kesehatan Lingkungan (IKL)

```python
# agents/orchestrator.py

def compute_ikl(metrics: dict, social: dict, risk_level: str) -> dict:
    scores = []

    # Komponen 1: Kualitas Udara (bobot 35%)
    aqi_score = max(0, 100 - (float(metrics["aqi"]) / 3))
    scores.append(("Kualitas Udara", round(aqi_score), 0.35))

    # Komponen 2: Tingkat Risiko (bobot 25%)
    risk_scores = {"rendah": 90, "sedang": 60, "tinggi": 30, "kritis": 10}
    scores.append(("Tingkat Risiko", risk_scores[risk_level], 0.25))

    # Komponen 3: Kesejahteraan Sosial (bobot 25%)
    social_ikl = max(0, 100 - float(social.get("skor_kerentanan_sosial", 50)))
    scores.append(("Kesejahteraan Sosial", round(social_ikl), 0.25))

    # Komponen 4: Kenyamanan Suhu — optimal 24°C (bobot 15%)
    temp_score = max(0, 100 - abs(float(metrics["temperature"]) - 24) * 5)
    scores.append(("Kenyamanan Suhu", round(temp_score), 0.15))

    # Hitung weighted average
    total_weight = sum(w for _, _, w in scores)
    ikl = round(sum(s * w for _, s, w in scores) / total_weight)

    return {"score": ikl, "label": label, "color": color, "components": [...]}
```

> **Penjelasan:** IKL adalah skor gabungan 0–100 yang menggabungkan kualitas udara, tingkat risiko, kondisi sosial, dan kenyamanan suhu dengan bobot berbeda. Semakin tinggi skor = semakin sehat lingkungannya.

---

## 4. Konfigurasi Lingkungan (Environment Variables)

Buat file `.env` di root project dengan isi berikut:

```env
# ── WAJIB — Aplikasi tidak akan berjalan tanpa ini ──────────
GROQ_API_KEY=your_groq_api_key_here
OPENWEATHER_API_KEY=your_openweather_api_key_here
WAQI_TOKEN=your_waqi_token_here

# ── OPSIONAL — Jika tidak diisi, otomatis pakai SQLite lokal ─
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your_supabase_anon_key_here

# ── SERVER — Opsional, ada default ──────────────────────────
HOST=127.0.0.1
PORT=8080
DEBUG=false
```

### Cara Mendapatkan API Key

| Variable | Daftar di | Free Tier |
|----------|-----------|-----------|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | 30.000 token/menit |
| `OPENWEATHER_API_KEY` | [openweathermap.org/api](https://openweathermap.org/api) | 1.000 calls/hari |
| `WAQI_TOKEN` | [aqicn.org/data-platform/token](https://aqicn.org/data-platform/token/) | Gratis non-komersial |
| `SUPABASE_URL` + `SUPABASE_KEY` | [supabase.com](https://supabase.com) | 500MB database gratis |

> ⚠️ **Jangan pernah commit file `.env` ke Git.** File ini sudah ada di `.gitignore`.

---

## 5. Panduan Instalasi & Menjalankan Aplikasi

### Cara 1 — Menjalankan Lokal

**Langkah 1: Clone repository**
```bash
git clone https://github.com/caseyshalom/EverGreen-AI.git
cd EverGreen-AI
```

**Langkah 2: Buat virtual environment**
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / Mac
python3 -m venv .venv
source .venv/bin/activate
```

**Langkah 3: Install dependencies**
```bash
pip install -r requirements.txt
```

> ⏳ Proses ini memakan waktu ~3–5 menit karena `crewai` cukup besar.

**Langkah 4: Buat file `.env`**
```bash
# Salin template dan isi dengan API key kamu
cp .env.example .env   # atau buat manual
```

**Langkah 5: (Opsional) Setup Supabase**

Jika ingin menggunakan Supabase, jalankan `supabase_setup.sql` di Supabase SQL Editor.  
Jika tidak, sistem otomatis menggunakan SQLite lokal — tidak perlu setup apapun.

**Langkah 6: Jalankan aplikasi**
```bash
python main.py
```

Buka browser: **`http://127.0.0.1:8080`**

---

### Cara 2 — Menjalankan via Docker

```bash
# Build image
docker build -t evergreen-ai .

# Jalankan container
docker run -p 7860:7860 \
  -e GROQ_API_KEY=your_key \
  -e OPENWEATHER_API_KEY=your_key \
  -e WAQI_TOKEN=your_token \
  evergreen-ai
```

Buka browser: **`http://localhost:7860`**

---

### Cara 3 — Akses via Hugging Face Spaces

Aplikasi sudah di-deploy di:  
🔗 **[huggingface.co/spaces/caseyshalom/evergreen-ai](https://huggingface.co/spaces/caseyshalom/evergreen-ai)**

Tidak perlu instalasi apapun — langsung bisa digunakan.

---

### Estimasi Waktu Respons

| Operasi | Waktu |
|---------|-------|
| Fetch data API (5 sumber) | ~2–4 detik |
| Analisis 5 agen AI | ~35–55 detik |
| Auto-monitor (tanpa AI) | ~2–5 detik |
| EcoBot chat | ~2–4 detik |

> Bottleneck utama adalah rate limit Groq (30.000 token/menit). Delay 2 detik antar task sengaja ditambahkan untuk menghindari error rate limit.

---

### Requirements

```
fastapi==0.115.0
uvicorn==0.30.6
groq>=0.9.0
crewai>=0.80.0
crewai-tools>=0.17.0
httpx>=0.27.0
python-dotenv>=1.0.0
pydantic>=2.0.0
aiofiles>=24.0.0
supabase>=2.0.0
```

**Python version:** 3.11+

---

*EverGreen AI — Masa Depan Berkelanjutan Dimulai dari Data yang Tepat 🌿*
