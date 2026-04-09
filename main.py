"""
EcoGuardian - FastAPI Backend
Orkestrasi API untuk sistem multi-agent lingkungan dan dampak sosial.
"""

import os
import uuid
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

load_dotenv()

from memory.db import init_db
from agents.orchestrator import run_ecoguardian_agents

init_db()

app = FastAPI(
    title="EcoGuardian AI",
    description="Multi-Agent AI untuk Pemantauan Lingkungan dan Dampak Sosial",
    version="1.0.0"
)

BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


class QueryRequest(BaseModel):
    query: str
    city: str = "Jakarta"
    country_code: str = "ID"
    session_id: str = ""


class QueryResponse(BaseModel):
    success: bool
    response: str
    risk_level: str = "sedang"
    city: str = "Jakarta"
    metrics: dict = {}
    forecast: list = []
    monitor: dict = {}
    predict: dict = {}
    social: dict = {}
    ethics: dict = {}
    actions: list = []
    notifications: dict = {}
    report_file: str = ""
    sources: list = []
    history: list = []
    session_id: str = ""


@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = BASE_DIR / "templates" / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.post("/api/analyze", response_model=QueryResponse)
async def analyze(req: QueryRequest):
    session_id = req.session_id or str(uuid.uuid4())

    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query tidak boleh kosong")

    result = await run_ecoguardian_agents(
        user_query=req.query,
        city=req.city or "Jakarta",
        country_code=req.country_code or "ID",
        session_id=session_id,
    )

    result["session_id"] = session_id
    return result


@app.get("/api/download-report")
async def download_report(file: str):
    """Download laporan yang sudah digenerate."""
    from fastapi.responses import FileResponse as FR
    import urllib.parse
    decoded = urllib.parse.unquote(file)
    path = Path(decoded)
    # Normalisasi path untuk validasi (support Windows backslash)
    normalized = str(path).replace("\\", "/")
    if not path.exists() or not normalized.startswith("data/reports"):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    return FR(
        path=str(path),
        filename=path.name,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    favicon_path = BASE_DIR / "static" / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(str(favicon_path))
    from fastapi.responses import Response
    return Response(status_code=204)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "EcoGuardian AI",
        "version": "1.0.0",
        "ai": {
            "groq": {
                "active": True,
                "model": "llama-3.1-8b-instant"
            }
        }
    }


@app.get("/api/cities")
async def get_cities():
    return {
        "cities": [
            {"name": "Jakarta", "country": "ID", "label": "Jakarta, Indonesia"},
            {"name": "Surabaya", "country": "ID", "label": "Surabaya, Indonesia"},
            {"name": "Bandung", "country": "ID", "label": "Bandung, Indonesia"},
            {"name": "Medan", "country": "ID", "label": "Medan, Indonesia"},
            {"name": "Semarang", "country": "ID", "label": "Semarang, Indonesia"},
            {"name": "Makassar", "country": "ID", "label": "Makassar, Indonesia"},
            {"name": "Singapore", "country": "SG", "label": "Singapura"},
            {"name": "Kuala Lumpur", "country": "MY", "label": "Kuala Lumpur, Malaysia"},
            {"name": "Bangkok", "country": "TH", "label": "Bangkok, Thailand"},
            {"name": "Tokyo", "country": "JP", "label": "Tokyo, Jepang"},
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true",
    )
