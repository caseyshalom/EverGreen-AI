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

Sistem **Agentic AI** berbasis multi-agent untuk memantau kondisi lingkungan, memprediksi risiko iklim, dan menganalisis dampak sosial secara real-time.

## Environment Variables yang Dibutuhkan

Set di **Settings → Variables and Secrets** di Hugging Face Space kamu:

| Variable | Wajib | Keterangan |
|----------|-------|------------|
| `GROQ_API_KEY` | ✅ | API key dari [console.groq.com](https://console.groq.com) |
| `OPENWEATHER_API_KEY` | ✅ | API key dari [openweathermap.org](https://openweathermap.org/api) |
| `WAQI_TOKEN` | ✅ | Token dari [aqicn.org](https://aqicn.org/data-platform/token/) |
| `SUPABASE_URL` | ⬜ | URL project Supabase (opsional, fallback ke SQLite) |
| `SUPABASE_KEY` | ⬜ | Anon key Supabase (opsional) |

## Stack
- **Backend**: FastAPI + Uvicorn
- **AI**: CrewAI + Groq Llama-4 Scout 17B
- **Database**: Supabase / SQLite fallback
