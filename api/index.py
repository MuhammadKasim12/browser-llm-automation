"""Vercel serverless entry point.

Mounts backend/main.py:app as a Mangum-wrapped Lambda handler.
- LLM defaults to Groq llama-3.1-8b-instant (fits Vercel's 10s timeout).
- DB persistence via DATABASE_URL env var (Neon Postgres in prod).
"""
import os
import sys
from pathlib import Path

# Vercel-specific defaults (only set if not already in env)
os.environ.setdefault("LLM_PROVIDER", "groq")
os.environ.setdefault("LLM_MODEL", "llama-3.1-8b-instant")

# Make backend/ importable as flat modules (matches local uvicorn layout)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from main import app  # noqa: E402  (backend/main.py)
from mangum import Mangum  # noqa: E402

handler = Mangum(app, lifespan="off")
