"""Resume Generator — Vercel serverless entry point (self-contained, mirrors caasp pattern)."""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Vercel-friendly defaults (env vars set in Vercel dashboard win via setdefault).
# Prefer Groq so we get the 70B model that follows multi-step prompts. Do NOT
# set LLM_MODEL here — each provider has its own correct default in LLM_PROVIDERS,
# and a stale LLM_MODEL silently downgrades Groq to 8B or sends an invalid name.
os.environ.setdefault("LLM_PROVIDER", "groq")

# Make sibling modules in api/ importable
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from _db import Generation, get_db, init_db
from _engine import (
    LLMError,
    extract_text_from_upload,
    find_current_role_config,
    generate_resume_json,
    load_default_resume_text,
    render_pdf_bytes,
)

load_dotenv()
init_db()

app = FastAPI(title="Resume Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    job_title: str
    company: str
    job_description: str
    source_resume: Optional[str] = None
    preferred_provider: Optional[str] = None


class RenderRequest(BaseModel):
    data: dict
    save_to_history: bool = True
    job_title: Optional[str] = None
    company: Optional[str] = None
    job_description: Optional[str] = None
    source_resume: Optional[str] = None


def _safe_filename(company: str) -> str:
    s = (company or "resume").lower()
    return "".join(c if c.isalnum() else "_" for c in s).strip("_") or "resume"


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/source-resume")
def source_resume():
    text = load_default_resume_text()
    return {"text": text, "length": len(text)}


@app.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    content = await file.read()
    try:
        text = extract_text_from_upload(file.filename or "", content)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to extract text: {e}")
    return {"filename": file.filename, "text": text, "length": len(text)}


@app.post("/api/generate")
def generate(req: GenerateRequest):
    resume_text = req.source_resume or load_default_resume_text()
    if not resume_text:
        raise HTTPException(400, "No source resume available.")
    try:
        data = generate_resume_json(
            job_title=req.job_title,
            company=req.company,
            job_description=req.job_description,
            resume_content=resume_text[:8000],
            current_role_config=find_current_role_config(),
            preferred_provider=req.preferred_provider,
        )
    except LLMError as e:
        raise HTTPException(502, f"LLM error: {e}")
    return data


@app.post("/api/render-pdf")
def render_pdf(req: RenderRequest, db: Session = Depends(get_db)):
    if not req.data or not isinstance(req.data, dict):
        raise HTTPException(400, "Missing 'data' object")
    try:
        pdf = render_pdf_bytes(req.data)
    except Exception as e:
        raise HTTPException(500, f"PDF rendering failed: {e}")

    if req.save_to_history:
        meta = req.data.get("_meta") or {}
        gen = Generation(
            created_at=datetime.utcnow().isoformat(timespec="seconds"),
            job_title=req.job_title or req.data.get("title", "")[:200],
            company=req.company or "",
            job_description=req.job_description or "",
            source_resume=req.source_resume or "",
            data_json=json.dumps(req.data),
            pdf_blob=pdf,
            provider=meta.get("provider"),
            model=meta.get("model"),
        )
        db.add(gen); db.commit(); db.refresh(gen)
        headers = {"X-Generation-Id": str(gen.id)}
    else:
        headers = {}

    fname = f"resume_{_safe_filename(req.company or req.data.get('title', 'resume'))}.pdf"
    headers["Content-Disposition"] = f'attachment; filename="{fname}"'
    return Response(content=pdf, media_type="application/pdf", headers=headers)


@app.get("/api/history")
def list_history(db: Session = Depends(get_db), limit: int = 50):
    rows = db.query(Generation).order_by(Generation.id.desc()).limit(limit).all()
    return [{
        "id": r.id, "created_at": r.created_at,
        "job_title": r.job_title, "company": r.company,
        "provider": r.provider, "model": r.model,
    } for r in rows]


@app.get("/api/history/{gen_id}")
def get_history(gen_id: int, db: Session = Depends(get_db)):
    r = db.query(Generation).get(gen_id)
    if not r:
        raise HTTPException(404, "Not found")
    return {
        "id": r.id, "created_at": r.created_at,
        "job_title": r.job_title, "company": r.company,
        "job_description": r.job_description,
        "source_resume": r.source_resume,
        "data": json.loads(r.data_json),
        "provider": r.provider, "model": r.model,
        "has_pdf": r.pdf_blob is not None,
    }


@app.get("/api/history/{gen_id}/pdf")
def get_history_pdf(gen_id: int, db: Session = Depends(get_db)):
    r = db.query(Generation).get(gen_id)
    if not r or not r.pdf_blob:
        raise HTTPException(404, "Not found")
    fname = f"resume_{_safe_filename(r.company)}.pdf"
    return Response(content=r.pdf_blob, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@app.delete("/api/history/{gen_id}")
def delete_history(gen_id: int, db: Session = Depends(get_db)):
    r = db.query(Generation).get(gen_id)
    if not r:
        raise HTTPException(404, "Not found")
    db.delete(r); db.commit()
    return {"deleted": gen_id}


# ── Vercel handler ────────────────────────────────────────────────────────────
from mangum import Mangum
handler = Mangum(app, lifespan="off")
