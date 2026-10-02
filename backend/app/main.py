"""FastAPI entrypoint. TRD Sec 2, 14, 15."""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.database import init_db
from app.api.routes import router
from app.api.ui import router as ui_router

app = FastAPI(title="OSINT Misleading-News Platform (MVP)", version="1.0.0",
              description="Evidence-first OSINT: collect -> enrich (3-layer) -> A-E analysis -> assessment -> report. Groq LLM.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000",
                   "http://localhost:8001", "http://127.0.0.1:8001", "*"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

init_db()
app.include_router(router, prefix="/api")
app.include_router(ui_router, prefix="/api")

# dashboard
STATIC = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(STATIC):
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

@app.get("/")
def root():
    return {"ok": True, "docs": "/docs", "dashboard": "/dashboard", "health": "/health"}

@app.get("/health")
def health():
    from app.core.groq_client import groq_client
    return {"ok": True, "groq_configured": groq_client.available, "groq_model": groq_client.model}

@app.get("/dashboard")
def dashboard():
    p = os.path.join(os.path.dirname(__file__), "..", "static", "dashboard.html")
    if os.path.exists(p):
        return FileResponse(p, media_type="text/html")
    return {"hint": "dashboard.html missing"}
