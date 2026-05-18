---
title: EverGreen AI
emoji: 🌿
colorFrom: green
colorTo: teal
sdk: docker
pinned: false
license: mit
short_description: Multi-Agent AI untuk Pemantauan Lingkungan & Dampak Sosial
---

# 🌿 EverGreen AI

Sistem **Agentic AI** berbasis multi-agent untuk memantau kondisi lingkungan, memprediksi risiko iklim, dan menganalisis dampak sosial secara real-time. Didukung 5 agen AI yang bekerja paralel dan sekuensial, menghasilkan laporan lengkap dengan rencana aksi konkret dalam hitungan menit.

## 🤖 Pipeline Multi-Agent

| Agen | Peran |
|------|-------|
| 🌫️ **Monitor Agent** | Analisis AQI, PM2.5, polutan dominan vs standar WHO/ISPU |
| 📈 **Predict Agent** | Prediksi risiko banjir & polusi 7 hari ke depan |
| 👥 **Social Agent** | Skor kerentanan sosial 0–100, identifikasi kelompok rentan |
| 🛡️ **Ethics Agent** | Validasi validitas, transparansi, keadilan, akurasi |
| 📋 **Report Agent** | Laporan final + 3 rencana aksi terstruktur |

## ✨ Fitur Utama

- **Indeks Kesehatan Lingkungan (IKL)** — skor gabungan 0–100
- **Peta choropleth** — data cuaca 34 provinsi Indonesia
- **Community Health Index** — kualitas udara + sosial-ekonomi
- **EcoBot AI Chat** — chatbot kontekstual berbasis Groq
- **Auto-Monitor** — alert otomatis threshold WHO/ISPU
- **Share & Download** laporan analisis

## 🌐 Data Sources

WAQI · OpenWeatherMap · Open-Meteo · World Bank · BMKG

## ⚙️ Environment Variables

Set di **Settings → Variables and Secrets**:

| Variable | Wajib | Keterangan |
|----------|-------|------------|
| `GROQ_API_KEY` | ✅ | [console.groq.com](https://console.groq.com) |
| `OPENWEATHER_API_KEY` | ✅ | [openweathermap.org](https://openweathermap.org/api) |
| `WAQI_TOKEN` | ✅ | [aqicn.org/data-platform/token](https://aqicn.org/data-platform/token/) |
| `SUPABASE_URL` | ⬜ | Opsional — fallback ke SQLite |
| `SUPABASE_KEY` | ⬜ | Opsional |

## 🛠️ Stack

**Backend:** Python 3.11 · FastAPI · Uvicorn  
**AI/LLM:** CrewAI ≥0.80 · Groq `llama-4-scout-17b-16e-instruct`  
**Database:** Supabase (PostgreSQL) + SQLite fallback  
**Frontend:** HTML5 · CSS3 · JavaScript · Leaflet.js
