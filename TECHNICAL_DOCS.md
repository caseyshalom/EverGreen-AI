# Dokumentasi Teknis EverGreen AI

**Versi:** 1.0.0  
**Stack:** Python 3.11 · FastAPI · CrewAI · Groq · Supabase/SQLite  
**Author:** Team G.R.E.E.N

---

## Daftar Isi

1. [Gambaran Arsitektur](#1-gambaran-arsitektur)
2. [Struktur Direktori](#2-struktur-direktori)
3. [Environment Variables](#3-environment-variables)
4. [Modul: main.py](#4-modul-mainpy)
5. [Modul: agents/orchestrator.py](#5-modul-agentsorchestrator)
6. [Modul: tools/env_tools.py](#6-modul-toolsenv_toolspy)
7. [Modul: tools/notification_tools.py](#7-modul-toolsnotification_toolspy)
8. [Modul: memory/db.py](#8-modul-memorydbpy)
9. [Modul: memory/supabase_db.py](#9-modul-memorysupabase_dbpy)
10. [Skema Database](#10-skema-database)
11. [Alur Data End-to-End](#11-alur-data-end-to-end)
12. [Algoritma & Formula](#12-algoritma--formula)
13. [API Reference](#13-api-reference)
14. [Error Handling & Fallback](#14-error-handling--fallback)
15. [Deployment](#15-deployment)

---

## 1. Gambaran Arsitektur

EverGreen AI adalah sistem **Agentic AI** berbasis multi-agent yang bekerja dalam dua fase:

```
User Request
    │
    ▼
FastAPI Backend (main.py)
    │
    ├── fetch_all_env_data()  ← async parallel: WAQI + OWM + Open-Meteo + WorldBank + BMKG
    │
    ▼
CrewAI Orchestrator (orchestrator.py)
    │
    ├── [FASE 1 — ThreadPoolExecutor, max_workers=3]
    │   ├── Monitor Agent   → analisis AQI/cuaca
    │   ├── Predict Agent   → prediksi risiko 7 hari
    │   └── Social Agent    → skor kerentanan sosial
    │
    └── [FASE 2 — Sequential]
        ├── Ethics Agent    → audit validitas & keadilan
        └── Report Agent    → laporan final + rencana aksi
            │
            ▼
        compute_ikl()       → Indeks Kesehatan Lingkungan 0-100
            │
            ▼
        Database (Supabase → fallback SQLite)
            │
            ▼
        JSON Response → Frontend
```

**Prinsip desain:**
- Fase 1 berjalan paralel untuk menghemat waktu (~30 detik lebih cepat)
- Setiap agen punya persona spesifik untuk meningkatkan kualitas output LLM
- Semua API call menggunakan `asyncio.gather()` untuk konkurensi penuh
- Database menggunakan pola **primary-fallback**: Supabase → SQLite lokal

---

## 2. Struktur Direktori

```
EverGreen-AI/
├── main.py                   # FastAPI app, semua endpoint, alert logic, CHI
├── requirements.txt          # Dependencies Python
├── Dockerfile                # Container untuk Hugging Face Spaces
├── .env                      # API keys (tidak di-commit)
├── supabase_setup.sql        # DDL setup tabel Supabase
│
├── agents/
│   ├── __init__.py
│   └── orchestrator.py       # CrewAI pipeline: 5 agen, IKL, parse action plan
│
├── tools/
│   ├── __init__.py
│   ├── env_tools.py          # Fetch data: WAQI, OWM, Open-Meteo, WorldBank, BMKG
│   └── notification_tools.py # Generate & simpan laporan .txt
│
├── memory/
│   ├── __init__.py
│   ├── db.py                 # SQLite: sessions, env_cache, analysis_history
│   └── supabase_db.py        # Supabase wrapper + fallback ke SQLite
│
├── static/
│   ├── css/style.css         # Stylesheet utama (dark/light mode, responsive)
│   ├── favicon.ico
│   └── js/
│       ├── app.js            # Logic dashboard: analisis, peta, EcoBot, auto-monitor
│       └── social_features.js # Community Health Index, radar chart, dampak sosial
│
├── templates/
│   └── index.html            # Single-page dashboard
│
└── data/
    ├── evergreen.db          # SQLite database (auto-generated saat runtime)
    └── reports/              # File laporan .txt hasil analisis
```

---

## 3. Environment Variables

| Variable | Wajib | Default | Keterangan |
|----------|-------|---------|------------|
| `GROQ_API_KEY` | ✅ | — | API key Groq untuk LLM Llama-4 Scout |
| `OPENWEATHER_API_KEY` | ✅ | — | API key OpenWeatherMap (cuaca + geocoding) |
| `WAQI_TOKEN` | ✅ | `"demo"` | Token WAQI untuk data AQI |
| `SUPABASE_URL` | ⬜ | — | URL project Supabase (opsional) |
| `SUPABASE_KEY` | ⬜ | — | Anon key Supabase (opsional) |
| `HOST` | ⬜ | `"0.0.0.0"` | Host server |
| `PORT` | ⬜ | `7860` | Port server |
| `DEBUG` | ⬜ | `"false"` | Aktifkan hot-reload uvicorn |

> Jika `SUPABASE_URL` dan `SUPABASE_KEY` tidak diisi, sistem otomatis menggunakan SQLite lokal di `data/evergreen.db`.

---

## 4. Modul: `main.py`

Entry point aplikasi FastAPI. Bertanggung jawab atas routing, validasi input, alert logic, dan kalkulasi Community Health Index (CHI).

### Inisialisasi

```python
load_dotenv()          # Load .env
init_db()              # Inisialisasi SQLite (buat tabel jika belum ada)
app = FastAPI(...)     # Buat instance FastAPI
app.mount("/static")   # Serve static files
```

### Konstanta: `ALERT_THRESHOLDS`

Threshold alert berbasis standar WHO/ISPU:

```python
ALERT_THRESHOLDS = {
    "aqi":           {"sedang": 100, "tinggi": 150, "kritis": 200},
    "pm25":          {"sedang": 25,  "tinggi": 55,  "kritis": 150},
    "precipitation": {"sedang": 10,  "tinggi": 20,  "kritis": 50},   # mm/hari
    "wind_speed":    {"sedang": 10,  "tinggi": 20,  "kritis": 30},   # m/s
}
```

### Fungsi: `evaluate_alert_level(metrics, forecast)`

Mengevaluasi level alert dari data real-time tanpa memanggil AI.

**Parameter:**
- `metrics` — dict berisi `aqi`, `pm25`, `wind_speed`, dll.
- `forecast` — list prakiraan 3 hari ke depan

**Return:**
```python
{
    "alerts": [{"type": str, "value": str, "level": str, "action": str}],
    "max_level": "aman" | "sedang" | "tinggi" | "kritis",
    "has_alert": bool,
    "auto_triggered": True
}
```

**Logika level:** menggunakan `level_order` dict untuk memastikan `max_level` hanya naik, tidak turun.

### Pydantic Models

```python
class QueryRequest(BaseModel):
    query: str
    city: str = "Jakarta"
    country_code: str = "ID"
    session_id: str = ""

class QueryResponse(BaseModel):
    success: bool
    response: str
    risk_level: str        # rendah | sedang | tinggi | kritis
    city: str
    metrics: dict          # AQI, PM2.5, suhu, kelembaban, angin
    forecast: list         # Prakiraan 7 hari
    monitor: dict          # Output Monitor Agent
    predict: dict          # Output Predict Agent
    social: dict           # Output Social Agent
    ethics: dict           # Output Ethics Agent
    actions: list          # Rencana aksi terstruktur
    ikl: dict              # Indeks Kesehatan Lingkungan
    sources: list          # Sumber data resmi
    history: list          # Riwayat analisis sesi
    session_id: str
```

### Community Health Index (CHI) — `GET /api/social-features/{city}`

Formula CHI dihitung di endpoint ini:

```
CHI = (100 - AQI/3) × 0.35
    + clean_water_access × 0.25
    + basic_sanitation × 0.25
    + (100 - poverty_rate × 3) × 0.15
```

| Skor | Label |
|------|-------|
| ≥ 80 | Sangat Baik |
| ≥ 60 | Baik |
| ≥ 40 | Sedang |
| < 40 | Buruk |

---

## 5. Modul: `agents/orchestrator.py`

Inti sistem multi-agent. Mengatur pipeline CrewAI, membangun agen, dan mengeksekusi analisis.

### Fungsi: `fetch_all_env_data(city, country_code)`

Mengambil semua data lingkungan secara paralel menggunakan `asyncio.gather()`.

```python
async def fetch_all_env_data(city: str, country_code: str) -> dict:
    # Jalankan semua API call sekaligus
    results = await asyncio.gather(
        get_air_quality(city),
        get_weather(city),
        get_social_data(country_code),
        get_earthquake_data(),
        get_forecast(lat, lon),   # hanya jika koordinat tersedia
        return_exceptions=True
    )
    # Exception per-task ditangani secara individual (tidak crash keseluruhan)
```

**Return keys:** `air_quality`, `weather`, `social`, `earthquake`, `forecast`, `coords`

### Fungsi: `_detect_focus(query)`

Mendeteksi intent query untuk menentukan output format laporan.

| Query mengandung | Focus |
|-----------------|-------|
| "kondisi kualitas udara hari ini" | `kualitas_udara` |
| "prediksi risiko lingkungan 7 hari" | `cuaca` |
| "kelompok masyarakat yang paling rentan" | `sosial` |
| "rekomendasi aksi konkret" | `aksi` |
| "analisis lengkap" | `lengkap` |
| *(lainnya)* | `lengkap` |

### Fungsi: `build_crew(env_data, user_query, city)`

Membangun 5 agen CrewAI dengan persona dan task masing-masing.

**LLM Configuration:**
```python
fast_llm = LLM(
    model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
    temperature=0.1,   # deterministik untuk analisis
    timeout=60,
    max_retries=2,
)
report_llm = LLM(
    temperature=0.15,  # sedikit lebih kreatif untuk laporan
)
```

**Context Injection:** Setiap task menerima `DATA_CONTEXT` berisi data real-time yang sudah diformat:
```
DATA JAKARTA: AQI=SEDANG (87 — 37 poin di atas zona baik) | PM2.5=32μg/m³ — MELEBIHI batas WHO...
```

**Task Dependencies:**
```
task_monitor ──┬──► task_predict (context: monitor)
               └──► task_social  (context: monitor)
                         │
               ┌─────────┴──────────┐
               ▼                    ▼
          task_ethics (context: monitor + predict + social)
               │
               ▼
          task_report (context: semua task sebelumnya)
```

### Fungsi: `parse_action_plan(text)`

Parser multi-format untuk mengekstrak rencana aksi dari output LLM yang tidak selalu konsisten.

Mendukung 4 format output:

**Format 1** (bracket):
```
[PRIORITAS: tinggi] [PELAKU: Pemda] [AKSI: Pasang sensor] [DAMPAK: 30% lebih cepat]
```

**Format 2** (inline tanpa bracket):
```
PRIORITAS: tinggi PELAKU: Pemda AKSI: Pasang sensor DAMPAK: 30% lebih cepat
```

**Format 3** (multi-line):
```
PRIORITAS: tinggi
PELAKU: Pemda
AKSI: Pasang sensor
DAMPAK: 30% lebih cepat
```

**Format 4** (numbered list fallback):
```
1. Pasang sensor udara di 10 titik strategis
2. Distribusi masker N95 untuk warga rentan
```

### Fungsi: `compute_ikl(metrics, social, risk_level)`

Menghitung Indeks Kesehatan Lingkungan (IKL) skor 0–100.

```
IKL = Σ(skor_komponen × bobot) / total_bobot

Komponen:
  Kualitas Udara    = max(0, 100 - AQI/3)        bobot: 0.35
  Tingkat Risiko    = {rendah:90, sedang:60,       bobot: 0.25
                        tinggi:30, kritis:10}
  Kesejahteraan     = max(0, 100 - skor_vuln)     bobot: 0.25
  Kenyamanan Suhu   = max(0, 100 - |T-24|×5)      bobot: 0.15
```

| IKL | Label | Warna |
|-----|-------|-------|
| ≥ 80 | Sangat Baik | `#22c55e` |
| ≥ 60 | Baik | `#16a34a` |
| ≥ 40 | Sedang | `#f59e0b` |
| ≥ 20 | Buruk | `#ef4444` |
| < 20 | Kritis | `#ef4444` |

### Fungsi: `run_greenai_agents(user_query, city, country_code, session_id)`

Orchestrator utama yang dipanggil dari endpoint `/api/analyze`.

**Alur eksekusi:**
1. Validasi `GROQ_API_KEY`
2. Simpan pesan user ke database
3. Fetch semua data lingkungan (`fetch_all_env_data`)
4. Jalankan `_run_crew()` di thread executor (agar tidak block event loop)
5. Fase 1: Monitor + Predict + Social paralel via `ThreadPoolExecutor(max_workers=3)`
6. Fase 2: Ethics → Report secara sekuensial
7. Extract `RISK_LEVEL` dari output laporan via regex
8. Bersihkan internal reasoning text (Thought:, Action:, Observation:, dll.)
9. Hitung IKL, parse action plan, susun response
10. Simpan hasil ke database

**Retry logic:**
```python
for attempt in range(3):
    try:
        final_text, task_outputs = await loop.run_in_executor(None, _run_crew)
        break
    except Exception as e:
        if "rate_limit" in err.lower() and attempt < 2:
            wait = (attempt + 1) * 25  # 25s, lalu 50s
            await asyncio.sleep(wait)
```

---

## 6. Modul: `tools/env_tools.py`

Semua fungsi pengambilan data eksternal. Semua fungsi bersifat `async` menggunakan `httpx.AsyncClient`.

### `get_air_quality(city: str) → dict`

**Sumber:** WAQI API (`https://api.waqi.info/feed/{city}/`)  
**Auth:** `WAQI_TOKEN` (default: `"demo"` — rate limited)  
**Timeout:** 10 detik

**Return fields:**
| Field | Tipe | Keterangan |
|-------|------|------------|
| `aqi` | int | Air Quality Index |
| `pm25` | float | PM2.5 μg/m³ |
| `pm10` | float | PM10 μg/m³ |
| `o3` | float | Ozon |
| `no2` | float | Nitrogen dioksida |
| `co` | float | Karbon monoksida |
| `dominant_pollutant` | str | Polutan dominan |
| `station` | str | Nama stasiun pengukur |
| `updated_at` | str | Waktu update terakhir |

### `get_weather(city: str) → dict`

**Sumber:** OpenWeatherMap API (`/data/2.5/weather`)  
**Auth:** `OPENWEATHER_API_KEY`  
**Unit:** metric (°C, m/s)  
**Bahasa:** Indonesia (`lang=id`)

**Return fields:** `temperature`, `feels_like`, `humidity`, `pressure`, `description`, `wind_speed`, `visibility`, `clouds`

### `get_forecast(lat: float, lon: float) → dict`

**Sumber:** Open-Meteo API (`https://api.open-meteo.com/v1/forecast`)  
**Auth:** Tidak diperlukan  
**Timezone:** `Asia/Jakarta`  
**Periode:** 7 hari ke depan

**Return per hari:**
```python
{
    "date": "2026-05-20",
    "temp_max": 34.2,
    "temp_min": 26.1,
    "precipitation": 12.5,   # mm
    "wind_max": 18.3,         # km/h
    "uv_index": 8.0
}
```

### `get_social_data(country_code: str) → dict`

**Sumber:** World Bank API (`https://api.worldbank.org/v2/country/{code}/indicator/{indicator}`)  
**Auth:** Tidak diperlukan  
**Data:** Most Recent Value (MRV) per indikator

**Indikator yang diambil:**

| Kode WB | Label | Keterangan |
|---------|-------|------------|
| `SI.POV.DDAY` | `poverty_rate` | % populasi di bawah $2.15/hari |
| `SI.POV.GINI` | `gini_index` | Koefisien Gini ketimpangan |
| `EG.ELC.ACCS.ZS` | `electricity_access` | % akses listrik |
| `IT.NET.USER.ZS` | `internet_access` | % pengguna internet |
| `SH.STA.BASS.ZS` | `basic_sanitation` | % akses sanitasi dasar |
| `SH.H2O.BASW.ZS` | `clean_water_access` | % akses air bersih |

### `get_earthquake_data() → dict`

**Sumber:** BMKG (`https://data.bmkg.go.id/DataMKG/TEWS/autogempa.json`)  
**Auth:** Tidak diperlukan  
**Data:** Gempa terbaru (auto-update BMKG)

**Return fields:** `tanggal`, `jam`, `magnitude`, `kedalaman`, `wilayah`, `potensi`, `koordinat`

### `get_city_coordinates(city: str) → dict | None`

Geocoding dengan strategi **hardcoded-first**:
1. Cek `CITY_COORDS_FALLBACK` dict (30+ kota Indonesia + 4 kota Asia)
2. Jika tidak ada, query OpenWeatherMap Geocoding API

**Alasan hardcoded-first:** Lebih akurat untuk kota Indonesia, tidak bergantung API call tambahan.

---

## 7. Modul: `tools/notification_tools.py`

### `generate_report_text(city, risk_level, response, metrics, actions, sources) → str`

Menghasilkan laporan teks terformat untuk diunduh user.

**Format output:**
```
============================================================
  LAPORAN EverGreen AI
  JAKARTA — 20 Mei 2026, 14:30 WIB
============================================================

TINGKAT RISIKO: [SEDANG] SEDANG

── METRIK LINGKUNGAN ──────────────────────────────────────
  AQI          : 87
  PM2.5        : 32.1 ug/m3
  ...

── ANALISIS ───────────────────────────────────────────────
[output dari Report Agent]

── RENCANA AKSI ───────────────────────────────────────────
  1. [TINGGI] Pasang sensor udara...
     Pelaku : Pemerintah DKI
     Dampak : Deteksi 30% lebih cepat

── SUMBER DATA RESMI ──────────────────────────────────────
  - BMKG: https://www.bmkg.go.id
  ...
============================================================
```

### `save_report_file(report_text, city) → Path`

Menyimpan laporan ke `data/reports/evergreen_{city}_{timestamp}.txt`.

**Naming convention:** `evergreen_jakarta_20260520_143022.txt`

---

## 8. Modul: `memory/db.py`

Layer database SQLite lokal. Digunakan sebagai fallback ketika Supabase tidak tersedia.

**Path database:** `data/evergreen.db` (relatif terhadap root project)

### Skema Tabel

**`sessions`** — Riwayat percakapan per sesi:
```sql
CREATE TABLE sessions (
    id         TEXT PRIMARY KEY,
    created_at TEXT,
    updated_at TEXT,
    messages   TEXT DEFAULT '[]'   -- JSON array
)
```

**`env_cache`** — Cache data lingkungan (belum digunakan aktif, reserved):
```sql
CREATE TABLE env_cache (
    cache_key  TEXT PRIMARY KEY,
    data       TEXT,               -- JSON
    fetched_at TEXT
)
```

**`analysis_history`** — Riwayat analisis:
```sql
CREATE TABLE analysis_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT,
    query          TEXT,
    city           TEXT,
    result_summary TEXT,
    risk_level     TEXT,
    created_at     TEXT
)
```

### Fungsi-fungsi

| Fungsi | Keterangan |
|--------|------------|
| `init_db()` | Buat tabel jika belum ada. Dipanggil saat startup. |
| `save_message(session_id, role, content)` | Append pesan ke JSON array di tabel `sessions` |
| `get_session_messages(session_id, last_n=10)` | Ambil N pesan terakhir dari sesi |
| `cache_env_data(cache_key, data)` | Simpan data ke cache dengan timestamp |
| `get_cached_env_data(cache_key, max_age_minutes=30)` | Ambil cache jika masih fresh |
| `save_analysis(session_id, query, city, summary, risk_level)` | Simpan ringkasan analisis |
| `get_analysis_history(session_id, limit=5)` | Ambil riwayat analisis terbaru |

---

## 9. Modul: `memory/supabase_db.py`

Wrapper Supabase dengan pola **primary-fallback** ke SQLite. Menggunakan singleton pattern untuk koneksi.

### Pola Singleton

```python
_supabase_client = None  # global singleton

def get_supabase():
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(url, key)
    return _supabase_client
```

Jika koneksi gagal (exception), `_reset_client()` dipanggil untuk memaksa reconnect di request berikutnya.

### Pola Fallback

Setiap fungsi mengikuti pola yang sama:
```python
def save_message(session_id, role, content):
    sb = get_supabase()
    if not sb:                          # Supabase tidak tersedia
        return _fallback_save_message(...)  # → SQLite
    try:
        sb.table("sessions")...execute()
    except Exception:
        _reset_client()                 # Reset untuk reconnect
        _fallback_save_message(...)     # → SQLite
```

### Tabel Supabase

Sama dengan SQLite, ditambah tabel `shared_reports`:

```sql
CREATE TABLE shared_reports (
    share_id   TEXT PRIMARY KEY,   -- 8 karakter UUID
    city       TEXT,
    risk_level TEXT,
    response   TEXT,               -- max 2000 karakter
    metrics    JSONB,
    created_at TIMESTAMPTZ
)
```

---

## 10. Skema Database

### SQLite (`data/evergreen.db`)

```
sessions
├── id (PK)
├── created_at
├── updated_at
└── messages (JSON array)

env_cache
├── cache_key (PK)
├── data (JSON)
└── fetched_at

analysis_history
├── id (PK, autoincrement)
├── session_id
├── query
├── city
├── result_summary
├── risk_level
└── created_at
```

### Supabase (PostgreSQL)

```
sessions          → sama dengan SQLite (messages: JSONB)
analysis_history  → sama dengan SQLite
shared_reports    → hanya di Supabase
├── share_id (PK, 8 char)
├── city
├── risk_level
├── response (max 2000 char)
├── metrics (JSONB)
└── created_at
```

**Index Supabase:**
```sql
CREATE INDEX idx_analysis_session ON analysis_history(session_id);
CREATE INDEX idx_analysis_city    ON analysis_history(city);
CREATE INDEX idx_analysis_created ON analysis_history(created_at DESC);
```

---

## 11. Alur Data End-to-End

### Request Analisis (`POST /api/analyze`)

```
1. Client kirim: { query, city, country_code, session_id }
2. FastAPI validasi: query tidak boleh kosong
3. Generate session_id jika kosong (uuid4)
4. Panggil run_greenai_agents()
   a. Simpan pesan user ke DB
   b. fetch_all_env_data() — parallel API calls
   c. _run_crew() di thread executor
      - Fase 1: Monitor + Predict + Social (ThreadPoolExecutor, max_workers=3)
        * Setiap agen: build mini_crew → kickoff → clean output → sleep(2s)
      - sleep(2s) antar fase
      - Fase 2: Ethics → sleep(2s) → Report
   d. Extract RISK_LEVEL dari output via regex
   e. Bersihkan reasoning artifacts (Thought:, Action:, dll.)
   f. compute_ikl() → skor 0-100
   g. parse_action_plan() → list aksi terstruktur
   h. Simpan hasil ke DB
5. Return QueryResponse JSON
```

### Request Auto-Monitor (`GET /api/auto-monitor/{city}`)

```
1. Fetch AQI + cuaca secara parallel (asyncio.gather)
2. Fetch forecast jika koordinat tersedia
3. evaluate_alert_level() — tanpa AI, murni threshold
4. Return alert jika ada kondisi melampaui threshold
```

Endpoint ini dirancang untuk dipanggil periodik dari frontend setiap 30 menit.

### Request EcoBot Chat (`POST /api/ecobot-chat`)

```
1. Ambil message, context (dari analisis terakhir), history (max 6 pesan)
2. Build system prompt dengan konteks analisis terbaru
3. Panggil Groq API langsung (bukan via CrewAI)
4. Return reply
```

EcoBot menggunakan Groq API secara langsung (bukan CrewAI) karena lebih ringan dan cepat untuk chat interaktif.

---

## 12. Algoritma & Formula

### Skor Kerentanan Sosial (Social Agent)

```
Skor = kemiskinan × 0.30
     + (100 - air_bersih) × 0.25
     + (100 - sanitasi) × 0.25
     + AQI_normalized × 0.20

AQI_normalized = min(100, AQI / 3)
```

Semakin tinggi skor = semakin rentan (0 = tidak rentan, 100 = sangat rentan).

### Indeks Kesehatan Lingkungan (IKL)

```
IKL = (max(0, 100 - AQI/3) × 0.35)
    + (risk_score × 0.25)
    + (max(0, 100 - skor_vuln) × 0.25)
    + (max(0, 100 - |suhu - 24| × 5) × 0.15)

risk_score: rendah=90, sedang=60, tinggi=30, kritis=10
```

### Community Health Index (CHI)

```
CHI = max(0, 100 - AQI/3) × 0.35
    + air_bersih × 0.25
    + sanitasi × 0.25
    + max(0, 100 - kemiskinan × 3) × 0.15
```

### Estimasi Dampak Sosial

```python
affected_pct = min(95, poverty + max(0, (aqi - 50) / 3))
affected     = population × affected_pct / 100
work_days    = affected × 0.05 × 12   # 5% kehilangan 12 hari kerja/tahun
health_cost  = affected × 0.002       # miliar IDR
```

### Skor Radar Kerentanan per Kelompok

```python
anak_anak  = min(100, aqi/1.5 + poverty×2)
lansia     = min(100, aqi/1.2 + (100-water)×0.5)
ibu        = min(100, pm25×1.2 + poverty)
masyarakat = min(100, poverty×3 + (100-sanitation)×0.3)
disabilitas = min(100, aqi/2 + (100-electricity)×0.5)
```

---

## 13. API Reference

### `POST /api/analyze`

Analisis lingkungan lengkap menggunakan 5 agen AI.

**Request:**
```json
{
  "query": "Analisis lengkap kondisi lingkungan",
  "city": "Jakarta",
  "country_code": "ID",
  "session_id": "optional-uuid"
}
```

**Response:**
```json
{
  "success": true,
  "response": "...",
  "risk_level": "sedang",
  "city": "Jakarta",
  "metrics": { "aqi": 87, "pm25": 32.1, "temperature": 31, "humidity": 78, "wind_speed": 3.2 },
  "forecast": [{ "date": "2026-05-20", "temp_max": 34, "temp_min": 26, "precipitation": 5.2 }],
  "actions": [{ "prioritas": "tinggi", "pelaku": "Pemda DKI", "aksi": "...", "dampak": "..." }],
  "ikl": { "score": 62, "label": "Baik", "color": "#16a34a", "components": [...] },
  "sources": [{ "name": "BMKG", "url": "https://bmkg.go.id", "desc": "..." }],
  "session_id": "uuid"
}
```

### `GET /api/auto-monitor/{city}`

**Query params:** `country_code` (default: `ID`)

**Response:**
```json
{
  "city": "Jakarta",
  "metrics": { "aqi": 87, "pm25": 32.1, ... },
  "forecast": [...],
  "alerts": [{ "type": "Kualitas Udara", "value": "AQI 87", "level": "sedang", "action": "Batasi aktivitas luar" }],
  "max_level": "sedang",
  "has_alert": true,
  "thresholds": { "aqi": { "sedang": 100, "tinggi": 150, "kritis": 200 }, ... }
}
```

### `GET /api/social-features/{city}`

**Response:**
```json
{
  "chi": { "score": 68, "label": "Baik", "color": "#16a34a" },
  "vulnerability_dimensions": [{ "name": "Kemiskinan", "value": 8.5, "level": "sedang" }],
  "social_impact": { "affected_people": 2100000, "work_days_lost": 1260000, "health_cost_billion_idr": 4200 },
  "radar_groups": [{ "name": "Anak-anak", "score": 65 }],
  "community_actions": { "Warga & Keluarga": ["..."] }
}
```

### `POST /api/ecobot-chat`

**Request:**
```json
{
  "message": "Apa dampak AQI 87 bagi kesehatan?",
  "context": "...(ringkasan analisis terakhir, max 800 char)...",
  "history": [{ "role": "user", "content": "..." }, { "role": "assistant", "content": "..." }]
}
```

**Response:**
```json
{ "reply": "AQI 87 termasuk kategori SEDANG...", "success": true }
```

### `GET /api/stats`

**Response:**
```json
{
  "total": 1250,
  "risk_distribution": { "rendah": 320, "sedang": 580, "tinggi": 290, "kritis": 60 },
  "top_cities": [{ "city": "Jakarta", "count": 450 }],
  "hour_distribution": [0, 0, 2, 5, ...]   // 24 elemen, index = jam
}
```

### `POST /api/share-report`

**Request:** `{ city, risk_level, response, metrics }`  
**Response:** `{ "share_id": "a1b2c3d4", "url": "/share/a1b2c3d4" }`

### `GET /api/indonesia-weather-map`

**Response:**
```json
{
  "provinces": [
    { "province": "DKI Jakarta", "city": "Jakarta", "lat": -6.2088, "lon": 106.8456,
      "temp_max": 34, "temp_min": 26, "precipitation": 5.2, "wind_max": 18, "uv_index": 8 }
  ]
}
```

---

## 14. Error Handling & Fallback

### Strategi Per Layer

| Layer | Error | Penanganan |
|-------|-------|------------|
| API eksternal | Timeout / network error | Return `{"status": "error", "message": str(e)}` |
| `asyncio.gather` | Exception per-task | `return_exceptions=True` — task lain tetap jalan |
| CrewAI / Groq | Rate limit | Retry 3x dengan backoff 25s, 50s |
| CrewAI / Groq | Exception lain | Return pesan error ke user |
| Supabase | Connection error | Auto-fallback ke SQLite |
| Supabase | Query error | `_reset_client()` + fallback ke SQLite |
| Geocoding | Kota tidak ditemukan | Fallback ke `CITY_COORDS_FALLBACK` dict |

### Output Cleaning

Output LLM sering mengandung internal reasoning yang bocor. Dibersihkan via regex:

```python
raw = re.sub(r'^Thought:.*$', '', raw, flags=MULTILINE)
raw = re.sub(r'^I now can give.*$', '', raw, flags=MULTILINE)
raw = re.sub(r'^Final Answer:\s*', '', raw, flags=MULTILINE)
raw = re.sub(r'^Action:.*$', '', raw, flags=MULTILINE)
raw = re.sub(r'^Action Input:.*$', '', raw, flags=MULTILINE)
raw = re.sub(r'^Observation:.*$', '', raw, flags=MULTILINE)
raw = re.sub(r'\n{3,}', '\n\n', raw)  # bersihkan blank lines berlebih
```

---

## 15. Deployment

### Lokal

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
# Buat .env dengan API keys
python main.py
# Buka http://127.0.0.1:7860
```

### Hugging Face Spaces (Docker)

File `Dockerfile` sudah dikonfigurasi untuk HF Spaces:
- Base image: `python:3.11-slim`
- Port: `7860` (default HF)
- User: `appuser` (uid 1000, non-root sesuai requirement HF)
- Data directory dibuat saat build: `data/reports/`

**Environment variables** diset di HF Space Settings → Variables and Secrets.

**Branch deployment:** `hf-deploy` (terpisah dari `main` GitHub)

### Catatan Performa

| Operasi | Estimasi Waktu |
|---------|---------------|
| Fetch semua data API | ~2–4 detik |
| Fase 1 (3 agen paralel) | ~15–25 detik |
| Fase 2 (Ethics + Report) | ~15–20 detik |
| **Total analisis** | **~35–55 detik** |
| Auto-monitor (tanpa AI) | ~2–5 detik |
| EcoBot chat | ~2–4 detik |

Bottleneck utama adalah rate limit Groq (30.000 token/menit). Delay `sleep(2)` antar task sengaja ditambahkan untuk menghindari rate limit error.

---

*Dokumentasi ini dibuat berdasarkan source code EverGreen AI v1.0.0*
