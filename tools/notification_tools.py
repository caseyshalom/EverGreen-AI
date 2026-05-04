# -*- coding: utf-8 -*-
"""
EverGreen AI - Notification Tools
Generate dan simpan laporan analisis.
"""

from datetime import datetime
from pathlib import Path


def generate_report_text(
    city: str,
    risk_level: str,
    response: str,
    metrics: dict,
    actions: list,
    sources: list,
) -> str:
    """Buat laporan teks terformat untuk diunduh."""
    now = datetime.now().strftime("%d %B %Y, %H:%M WIB")
    risk_label = {"rendah": "[RENDAH]", "sedang": "[SEDANG]", "tinggi": "[TINGGI]", "kritis": "[KRITIS]"}.get(risk_level, "[SEDANG]")

    lines = [
        "=" * 60,
        f"  LAPORAN EverGreen AI",
        f"  {city.upper()} — {now}",
        "=" * 60,
        "",
        f"TINGKAT RISIKO: {risk_label} {risk_level.upper()}",
        "",
        "── METRIK LINGKUNGAN ──────────────────────────────────────",
        f"  AQI          : {metrics.get('aqi', 'N/A')}",
        f"  PM2.5        : {metrics.get('pm25', 'N/A')} ug/m3",
        f"  Suhu         : {metrics.get('temperature', 'N/A')}C",
        f"  Kelembaban   : {metrics.get('humidity', 'N/A')}%",
        f"  Angin        : {metrics.get('wind_speed', 'N/A')} m/s",
        f"  Kondisi      : {metrics.get('weather_desc', 'N/A')}",
        "",
        "── ANALISIS ───────────────────────────────────────────────",
        response,
        "",
    ]

    if actions:
        lines += ["── RENCANA AKSI ───────────────────────────────────────────"]
        for i, a in enumerate(actions, 1):
            prio = a.get("prioritas", "sedang").upper()
            lines += [
                f"  {i}. [{prio}] {a.get('aksi', '')}",
                f"     Pelaku : {a.get('pelaku', '')}",
                f"     Dampak : {a.get('dampak', '')}",
                "",
            ]

    if sources:
        lines += ["── SUMBER DATA RESMI ──────────────────────────────────────"]
        for s in sources[:5]:
            lines.append(f"  - {s['name']}: {s['url']}")
        lines.append("")

    lines += [
        "=" * 60,
        "  Dibuat oleh EverGreen AI — Multi-Agent System",
        "  Powered by CrewAI + Groq",
        "=" * 60,
    ]

    return "\n".join(lines)


def save_report_file(report_text: str, city: str) -> Path:
    """Simpan laporan ke file .txt."""
    reports_dir = Path("data/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = reports_dir / f"evergreen_{city.lower().replace(' ', '_')}_{timestamp}.txt"
    filename.write_text(report_text, encoding="utf-8")
    return filename
