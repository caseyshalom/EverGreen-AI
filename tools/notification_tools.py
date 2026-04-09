"""
EcoGuardian - Notification Tools
Kirim alert via Telegram dan laporan via Email secara otonom.
"""

import os
import smtplib
import httpx
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Generate laporan teks
# ---------------------------------------------------------------------------

def generate_report_text(
    city: str,
    risk_level: str,
    response: str,
    metrics: dict,
    actions: list,
    sources: list,
) -> str:
    """Buat laporan teks terformat untuk dikirim via email/Telegram."""
    now = datetime.now().strftime("%d %B %Y, %H:%M WIB")
    risk_emoji = {"rendah": "🟢", "sedang": "🟡", "tinggi": "🔴", "kritis": "🚨"}.get(risk_level, "⚪")

    lines = [
        "=" * 60,
        f"  LAPORAN ECOGUARDIAN AI",
        f"  {city.upper()} — {now}",
        "=" * 60,
        "",
        f"TINGKAT RISIKO: {risk_emoji} {risk_level.upper()}",
        "",
        "── METRIK LINGKUNGAN ──────────────────────────────────────",
        f"  AQI          : {metrics.get('aqi', 'N/A')}",
        f"  PM2.5        : {metrics.get('pm25', 'N/A')} μg/m³",
        f"  Suhu         : {metrics.get('temperature', 'N/A')}°C",
        f"  Kelembaban   : {metrics.get('humidity', 'N/A')}%",
        f"  Angin        : {metrics.get('wind_speed', 'N/A')} m/s",
        f"  Kondisi      : {metrics.get('weather_desc', 'N/A')}",
        "",
        "── ANALISIS ───────────────────────────────────────────────",
        response,
        "",
    ]

    if actions:
        lines += [
            "── RENCANA AKSI ───────────────────────────────────────────",
        ]
        for i, a in enumerate(actions, 1):
            prio = a.get("prioritas", "sedang").upper()
            lines += [
                f"  {i}. [{prio}] {a.get('aksi', '')}",
                f"     Pelaku : {a.get('pelaku', '')}",
                f"     Dampak : {a.get('dampak', '')}",
                "",
            ]

    if sources:
        lines += [
            "── SUMBER DATA RESMI ──────────────────────────────────────",
        ]
        for s in sources[:5]:
            lines.append(f"  • {s['name']}: {s['url']}")
        lines.append("")

    lines += [
        "=" * 60,
        "  Dibuat oleh EcoGuardian AI — Multi-Agent System",
        "  Powered by CrewAI + Groq",
        "=" * 60,
    ]

    return "\n".join(lines)


def save_report_file(report_text: str, city: str) -> Path:
    """Simpan laporan ke file .txt sementara."""
    reports_dir = Path("data/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = reports_dir / f"ecoguardian_{city.lower().replace(' ', '_')}_{timestamp}.txt"
    filename.write_text(report_text, encoding="utf-8")
    return filename


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

async def send_telegram_alert(
    city: str,
    risk_level: str,
    response: str,
    metrics: dict,
    actions: list,
) -> dict:
    """
    Kirim alert Telegram otomatis jika risiko tinggi/kritis.
    Konfigurasi: TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID di .env
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id   = os.getenv("TELEGRAM_CHAT_ID", "")

    if not bot_token or not chat_id:
        return {"sent": False, "reason": "TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID belum diatur di .env"}

    risk_emoji = {"rendah": "🟢", "sedang": "🟡", "tinggi": "🔴", "kritis": "🚨"}.get(risk_level, "⚪")
    aqi = metrics.get("aqi", "N/A")
    temp = metrics.get("temperature", "N/A")
    pm25 = metrics.get("pm25", "N/A")

    # Ringkasan singkat untuk Telegram (maks 4096 karakter)
    summary = response[:600] + "..." if len(response) > 600 else response

    action_lines = ""
    for i, a in enumerate(actions[:3], 1):
        action_lines += f"\n{i}. [{a.get('prioritas','').upper()}] {a.get('aksi','')}"

    message = (
        f"{risk_emoji} *ALERT ECOGUARDIAN — {city.upper()}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌫️ AQI: `{aqi}` | 🌡️ Suhu: `{temp}°C` | 💨 PM2.5: `{pm25}`\n"
        f"⚠️ Risiko: *{risk_level.upper()}*\n\n"
        f"📋 *Ringkasan:*\n{summary}\n"
        f"\n🎯 *Rencana Aksi:*{action_lines}\n"
        f"\n_Dikirim otomatis oleh EcoGuardian AI_"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
            })
            data = resp.json()
            if data.get("ok"):
                return {"sent": True, "platform": "telegram", "city": city}
            else:
                return {"sent": False, "reason": data.get("description", "Unknown error")}
    except Exception as e:
        return {"sent": False, "reason": str(e)}


async def send_telegram_document(report_path: Path, city: str, risk_level: str) -> dict:
    """Kirim file laporan sebagai dokumen ke Telegram."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id   = os.getenv("TELEGRAM_CHAT_ID", "")

    if not bot_token or not chat_id:
        return {"sent": False, "reason": "Telegram tidak dikonfigurasi"}

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    caption = f"📄 Laporan lengkap EcoGuardian — {city} (Risiko: {risk_level})"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            with open(report_path, "rb") as f:
                resp = await client.post(url, data={
                    "chat_id": chat_id,
                    "caption": caption,
                }, files={"document": (report_path.name, f, "text/plain")})
            data = resp.json()
            return {"sent": data.get("ok", False), "platform": "telegram_doc"}
    except Exception as e:
        return {"sent": False, "reason": str(e)}


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

async def send_email_report(
    city: str,
    risk_level: str,
    report_text: str,
    report_path: Path,
    recipient_email: str = "",
) -> dict:
    """
    Kirim laporan via email menggunakan SMTP.
    Konfigurasi: EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT di .env
    Mendukung Gmail (smtp.gmail.com:587)
    """
    sender   = os.getenv("EMAIL_SENDER", "")
    password = os.getenv("EMAIL_PASSWORD", "")
    recipient = recipient_email or os.getenv("EMAIL_RECIPIENT", "")

    if not sender or not password or not recipient:
        return {"sent": False, "reason": "EMAIL_SENDER, EMAIL_PASSWORD, atau EMAIL_RECIPIENT belum diatur di .env"}

    risk_emoji = {"rendah": "🟢", "sedang": "🟡", "tinggi": "🔴", "kritis": "🚨"}.get(risk_level, "⚪")
    now = datetime.now().strftime("%d %B %Y %H:%M")

    subject = f"{risk_emoji} [EcoGuardian] Laporan Lingkungan {city} — Risiko {risk_level.upper()} ({now})"

    # Body HTML email
    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1a2e1a">
      <div style="background:linear-gradient(135deg,#16a34a,#0d9488);padding:24px;border-radius:12px 12px 0 0">
        <h1 style="color:#fff;margin:0;font-size:1.4rem">🌿 EcoGuardian AI</h1>
        <p style="color:rgba(255,255,255,0.85);margin:4px 0 0">Laporan Pemantauan Lingkungan & Dampak Sosial</p>
      </div>
      <div style="background:#f8faf8;padding:20px;border:1px solid #e2e8e2;border-top:none">
        <table style="width:100%;border-collapse:collapse">
          <tr>
            <td style="padding:8px;font-weight:600">Wilayah</td>
            <td style="padding:8px">{city}</td>
          </tr>
          <tr style="background:#fff">
            <td style="padding:8px;font-weight:600">Tingkat Risiko</td>
            <td style="padding:8px"><strong style="color:{'#dc2626' if risk_level in ('tinggi','kritis') else '#d97706' if risk_level=='sedang' else '#16a34a'}">{risk_emoji} {risk_level.upper()}</strong></td>
          </tr>
          <tr>
            <td style="padding:8px;font-weight:600">Waktu Analisis</td>
            <td style="padding:8px">{now}</td>
          </tr>
        </table>
        <hr style="border:1px solid #e2e8e2;margin:16px 0">
        <p style="font-size:0.85rem;color:#4a6a4a">
          Laporan lengkap terlampir dalam file .txt.<br>
          Laporan ini dibuat secara otomatis oleh sistem multi-agent EcoGuardian AI
          menggunakan data real-time dari WAQI, OpenWeatherMap, Open-Meteo, dan World Bank.
        </p>
        <p style="font-size:0.8rem;color:#7a967a;margin-top:16px">
          ⚠️ Laporan ini bersifat informatif dan tidak menggantikan penilaian ahli lingkungan profesional.
        </p>
      </div>
      <div style="background:#e2e8e2;padding:12px;border-radius:0 0 12px 12px;text-align:center;font-size:0.75rem;color:#7a967a">
        EcoGuardian AI — Powered by CrewAI + Groq | Data: WAQI, OpenWeatherMap, World Bank
      </div>
    </body></html>
    """

    try:
        msg = MIMEMultipart("mixed")
        msg["From"]    = sender
        msg["To"]      = recipient
        msg["Subject"] = subject

        # Attach HTML body
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        # Attach laporan file
        if report_path and report_path.exists():
            with open(report_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{report_path.name}"')
            msg.attach(part)

        smtp_host = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())

        return {"sent": True, "platform": "email", "recipient": recipient}

    except Exception as e:
        return {"sent": False, "reason": str(e)}
