"""Reusable resume-tailoring engine. Shared between CLI and FastAPI backend."""
from __future__ import annotations

import io
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import requests

LLM_PROVIDERS = {
    "cerebras": {
        "name": "Cerebras",
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "llama3.1-8b",
        "env_key": "CEREBRAS_API_KEY",
    },
    "groq": {
        "name": "Groq",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama-3.3-70b-versatile",
        "env_key": "GROQ_API_KEY",
    },
    "openrouter": {
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "env_key": "OPENROUTER_API_KEY",
    },
}

PERSONAL_BRAND = {
    "profile_snapshot": {
        "who_i_am": "Result-driven professional focused on building structured, scalable, and high-impact digital solutions aligned with real business goals.",
        "core_approach": ["Problem-first thinking", "Business value over hype", "Scalable architecture mindset"],
    },
    "expertise_foundation": {
        "focus_areas": ["Full-Stack Development", "Headless CMS Architecture", "UI Performance Optimization", "API Integration & System Design"],
        "tech_stack": ["React", "Next.js", "TypeScript", "Node.js", "Headless CMS"],
    },
    "positioning": {
        "what_sets_apart": ["Modern tech stack expertise", "Business-driven development approach", "Strong problem-solving mindset"],
    },
    "professional_traits": {
        "how_i_show_up": ["Reliable & proactive", "Detail-oriented", "Collaborative team player"],
        "strengths": ["Focused", "Adaptive", "Results-oriented"],
    },
    "delivery_communication": {
        "how_i_create_results": ["Clear documentation & communication", "Clean, maintainable code", "On-time delivery with quality assurance"],
    },
}


class LLMError(RuntimeError):
    pass


def get_llm_config(preferred: Optional[str] = None, order: Iterable[str] = ("cerebras", "groq", "openrouter")) -> dict:
    """Pick a provider whose API key is set. `preferred` overrides order if its key exists."""
    candidates = list(order)
    if preferred and preferred in LLM_PROVIDERS:
        candidates = [preferred] + [p for p in candidates if p != preferred]
    for name in candidates:
        cfg = LLM_PROVIDERS.get(name)
        if not cfg:
            continue
        if os.environ.get(cfg["env_key"]):
            return {"provider": name, **cfg, "api_key": os.environ[cfg["env_key"]]}
    raise LLMError("No API key found. Set CEREBRAS_API_KEY, GROQ_API_KEY, or OPENROUTER_API_KEY.")


def find_current_role_config() -> Optional[dict]:
    """Look for data/current_role.json in repo root (one or two levels up)."""
    here = Path(__file__).resolve()
    for parent in [here.parent, here.parent.parent, here.parent.parent.parent]:
        candidate = parent / "data" / "current_role.json"
        if candidate.exists():
            try:
                return json.loads(candidate.read_text())
            except Exception:
                return None
    return None


def load_default_resume_text() -> str:
    """Return cached resume text shipped with backend/ (or empty string)."""
    p = Path(__file__).parent / "default_resume.txt"
    if p.exists():
        return p.read_text(encoding="utf-8", errors="ignore").strip()
    return ""


def _build_prompt(job_title: str, company: str, job_description: str, resume_content: str,
                  current_role_config: Optional[dict], role_type: str) -> str:
    selected_client = "Intuit" if role_type == "software_engineer" else "Apple"
    current_experience_text = ""
    if current_role_config:
        exp = current_role_config.get("current_experience", {})
        sel_map = current_role_config.get("role_selection", {})
        selected_client = sel_map.get(role_type, selected_client)
        for client in exp.get("clients", []):
            if client.get("name") == selected_client:
                bullets = "\n".join("- " + p for p in client.get("points", []))
                current_experience_text += (
                    f"\nCURRENT ROLE (MUST BE FIRST IN EXPERIENCE LIST):\n"
                    f"Company: Galaxy I Tech (Contract)\nClient: {client.get('name')}\n"
                    f"Title: {client.get('title')}\nLocation: {exp.get('location')}\n"
                    f"Dates: {client.get('dates')}\nPoints:\n{bullets}\n"
                )
                break
        missing_exp = current_role_config.get("missing_experience", {})
        paypal_key = f"PayPal_{'QE' if role_type == 'qa_engineer' else 'SWE'}"
        if paypal_key in missing_exp:
            paypal = missing_exp[paypal_key]
            bullets = "\n".join("- " + p for p in paypal.get("points", []))
            current_experience_text += (
                f"\nMISSING EXPERIENCE (between Ancestry and Proofpoint):\n"
                f"Company: {paypal.get('company')}\nTitle: {paypal.get('title')}\n"
                f"Location: {paypal.get('location')}\nDates: {paypal.get('dates')}\nPoints:\n{bullets}\n"
            )
        date_corrections = current_role_config.get("date_corrections", {})
        if date_corrections:
            corrections = "\n".join(f"- {c}: {d}" for c, d in date_corrections.items())
            current_experience_text += f"\nDATE CORRECTIONS (APPLY THESE):\n{corrections}\n"

        if current_experience_text:
            current_experience_text += (
                f"\nCRITICAL EXPERIENCE INSTRUCTIONS (MUST FOLLOW):\n"
                f"1. The CURRENT ROLE at Galaxy I Tech (Client: {selected_client}) MUST be the FIRST experience entry.\n"
                f"2. Include the MISSING PayPal experience (Mar 2020 - Aug 2021) in chronological position.\n"
                f"3. Apply all DATE CORRECTIONS (e.g., Citi ends Jun 2025, NOT Present).\n"
                f"4. Order all other experiences in reverse chronological order after the current role.\n"
                f"5. Do NOT invent or duplicate experiences.\n"
            )

    brand = (
        f"PROFILE: {PERSONAL_BRAND['profile_snapshot']['who_i_am']}\n"
        f"CORE APPROACH: {', '.join(PERSONAL_BRAND['profile_snapshot']['core_approach'])}\n"
        f"FOCUS AREAS: {', '.join(PERSONAL_BRAND['expertise_foundation']['focus_areas'])}\n"
        f"WHAT SETS APART: {', '.join(PERSONAL_BRAND['positioning']['what_sets_apart'])}\n"
        f"TRAITS: {', '.join(PERSONAL_BRAND['professional_traits']['how_i_show_up'])}\n"
        f"DELIVERY: {', '.join(PERSONAL_BRAND['delivery_communication']['how_i_create_results'])}\n"
        f"MODERN STACK: {', '.join(PERSONAL_BRAND['expertise_foundation']['tech_stack'])}"
    )

    return _PROMPT_TEMPLATE.format(brand=brand, current=current_experience_text, selected=selected_client)



_PROMPT_TEMPLATE = """CANDIDATE PERSONAL BRAND:
{brand}
{current}
Analyze the resume and job description, then return a JSON object with this EXACT structure:
{{
    "name": "Full Name",
    "title": "Professional Title tailored to job",
    "email": "muhammadkasim@gmail.com",
    "phone": "(510) 771-4493",
    "location": "San Jose, CA",
    "linkedin": "linkedin URL or empty string",
    "summary": "3-4 sentence professional summary tailored to the job and reflecting the brand above",
    "skills": {{
        "Languages": "Python, Java, JavaScript, TypeScript, etc",
        "Frameworks": "React, Next.js, Node.js, Spring Boot, etc",
        "Cloud & DevOps": "AWS, Kubernetes, Docker, etc",
        "Databases": "PostgreSQL, MongoDB, etc"
    }},
    "experience": [
        {{
            "title": "Job Title",
            "company": "Company Name",
            "location": "City, State",
            "dates": "MMM YYYY - MMM YYYY",
            "points": ["bullet 1", "bullet 2", "bullet 3"]
        }}
    ]
}}

CRITICAL REQUIREMENTS:
- Skills MUST be comma-separated strings, NOT arrays
- Each job MUST have 3-5 bullet points in "points" array
- FIRST EXPERIENCE MUST be the CURRENT ROLE specified above (Galaxy I Tech) when present
- Order experience REVERSE CHRONOLOGICALLY (most recent first) AFTER the current role
- Use date format "MMM YYYY - MMM YYYY" (e.g., "Sep 2022 - Oct 2023")
- Apply Citi date correction: Oct 2024 - Jun 2025 (NOT Present)
- Keep all information truthful; quantify achievements where possible

SKILLS HONESTY (CRITICAL):
- ONLY list skills that are ACTUALLY in the provided resume
- DO NOT invent skills from the job description that are not in the resume
- Focus on highlighting TRANSFERABLE skills that ARE in the resume

HUMANIZATION:
- Vary sentence structures; avoid template-sounding bullets
- Use natural action verbs: Led, Built, Designed, Drove, Collaborated, Architected
- Tell mini-stories: Problem -> Solution -> Impact

Return ONLY valid JSON, no other text."""


_MONTH_MAP = {m: i for i, m in enumerate(
    ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"], start=1)}
_MONTH_ABBR = {v: k.title() for k, v in _MONTH_MAP.items()}


def _parse_date(date_str: str) -> datetime:
    if not date_str:
        return datetime.min
    s = date_str.strip().lower()
    if s in ("present", "current"):
        return datetime.max
    m = re.match(r"([a-z]{3})\s*(\d{4})", s)
    if m:
        return datetime(int(m.group(2)), _MONTH_MAP.get(m.group(1)[:3], 1), 1)
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"(\d{4})-(\d{2})", s)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), 1)
    m = re.match(r"(\d{4})", s)
    if m:
        return datetime(int(m.group(1)), 1, 1)
    return datetime.min


def _normalize_single(date_str: str) -> str:
    if not date_str:
        return ""
    s = date_str.strip()
    if s.lower() in ("present", "current"):
        return "Present"
    if re.match(r"^[A-Za-z]{3}\s+\d{4}$", s):
        return s.title()
    parsed = _parse_date(s)
    if parsed in (datetime.min, datetime.max):
        return s
    return f"{_MONTH_ABBR[parsed.month]} {parsed.year}"


def _normalize_range(dates: str) -> str:
    if not dates:
        return ""
    s = dates.strip()
    parts = re.split(r"\s+[-–—]\s+|(?<!\d)[-–—](?!\d)", s)
    if len(parts) == 1 and re.match(r"\d{4}-\d{2}-\d{2}\s*[-–]\s*\d{4}-\d{2}-\d{2}", s):
        m = re.match(r"(\d{4}-\d{2}-\d{2})\s*[-–]\s*(\d{4}-\d{2}-\d{2})", s)
        if m:
            parts = [m.group(1), m.group(2)]
    if len(parts) == 2:
        return f"{_normalize_single(parts[0])} - {_normalize_single(parts[1])}"
    if len(parts) == 1:
        return _normalize_single(parts[0])
    return s


def sort_experience_by_date(experience_list: list) -> list:
    for job in experience_list:
        if "dates" in job:
            job["dates"] = _normalize_range(job["dates"])
    def end_date(job):
        parts = re.split(r"\s*[-–]\s*", job.get("dates", ""))
        return _parse_date(parts[-1]) if parts else datetime.min
    return sorted(experience_list, key=end_date, reverse=True)



def _detect_role_type(job_title: str) -> str:
    t = (job_title or "").lower()
    if any(kw in t for kw in ("qa", "quality", "sdet", "test", "automation")):
        return "qa_engineer"
    return "software_engineer"


def generate_resume_json(
    job_title: str,
    company: str,
    job_description: str,
    resume_content: str,
    current_role_config: Optional[dict] = None,
    preferred_provider: Optional[str] = None,
) -> dict:
    """Call the LLM and return the structured resume JSON. Raises LLMError on failure."""
    role_type = _detect_role_type(job_title)
    if current_role_config is None:
        current_role_config = find_current_role_config()

    prompt = _build_prompt(job_title, company, job_description, resume_content,
                           current_role_config, role_type)
    cfg = get_llm_config(preferred=preferred_provider)

    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    if cfg["provider"] == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/resume-generator"
        headers["X-Title"] = "Resume Generator"
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Job: {job_title} at {company}\n\nJob Description:\n{job_description}\n\nResume:\n{resume_content}"},
        ],
        "max_tokens": 4000,
        "temperature": 0.5,
    }
    if cfg["provider"] in ("groq", "cerebras"):
        payload["response_format"] = {"type": "json_object"}

    resp = requests.post(cfg["url"], headers=headers, json=payload, timeout=120)
    try:
        result = resp.json()
    except Exception:
        raise LLMError(f"HTTP {resp.status_code}: {resp.text[:400]}")

    if "error" in result:
        err = result["error"]
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        raise LLMError(f"{cfg['name']} API error: {msg}")
    if "choices" not in result:
        msg = result.get("message") or str(result)[:400]
        raise LLMError(f"{cfg['name']} HTTP {resp.status_code}: {msg}")

    content = result["choices"][0]["message"]["content"]
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise LLMError(f"Invalid JSON from {cfg['name']}: {e}; content head: {content[:200]}")

    if "experience" in data and isinstance(data["experience"], list):
        data["experience"] = sort_experience_by_date(data["experience"])
    data["_meta"] = {"provider": cfg["provider"], "model": cfg["model"]}
    return data


def _build_pdf_story(data: dict):
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.enums import TA_CENTER

    styles = getSampleStyleSheet()
    name_style = ParagraphStyle("Name", parent=styles["Title"], fontSize=22,
                                textColor=HexColor("#1e3a5f"), alignment=TA_CENTER, spaceAfter=4)
    title_style = ParagraphStyle("JobTitle", parent=styles["Normal"], fontSize=12,
                                 textColor=HexColor("#2563eb"), alignment=TA_CENTER, spaceAfter=4)
    contact_style = ParagraphStyle("Contact", parent=styles["Normal"], fontSize=9,
                                   textColor=HexColor("#6b7280"), alignment=TA_CENTER, spaceAfter=12)
    section_style = ParagraphStyle("Section", parent=styles["Heading2"], fontSize=11,
                                   textColor=HexColor("#1e3a5f"), spaceAfter=6, spaceBefore=10)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10,
                                textColor=HexColor("#374151"), spaceAfter=4, leading=14)
    exp_title_style = ParagraphStyle("ExpTitle", parent=styles["Normal"], fontSize=10,
                                     textColor=HexColor("#1a1a1a"), fontName="Helvetica-Bold")
    company_style = ParagraphStyle("Company", parent=styles["Normal"], fontSize=9,
                                   textColor=HexColor("#2563eb"), fontName="Helvetica-Oblique", spaceAfter=4)
    bullet_style = ParagraphStyle("Bullet", parent=styles["Normal"], fontSize=9,
                                  textColor=HexColor("#374151"), leftIndent=12, spaceAfter=2, leading=12)

    story = [Paragraph(data.get("name", ""), name_style),
             Paragraph(data.get("title", ""), title_style)]
    contact = f"{data.get('email','')} &nbsp;|&nbsp; {data.get('phone','')} &nbsp;|&nbsp; {data.get('location','')}"
    story.append(Paragraph(contact, contact_style))
    story.append(Paragraph("PROFESSIONAL SUMMARY", section_style))
    story.append(Paragraph(data.get("summary", ""), body_style))
    story.append(Paragraph("TECHNICAL SKILLS", section_style))
    for category, skills in (data.get("skills") or {}).items():
        text = ", ".join(str(s) for s in skills) if isinstance(skills, list) else skills
        story.append(Paragraph(f"<b>{category}:</b> {text}", body_style))
    story.append(Paragraph("PROFESSIONAL EXPERIENCE", section_style))
    for job in data.get("experience", []) or []:
        story.append(Paragraph(f"<b>{job.get('title','')}</b> | {job.get('dates','')}", exp_title_style))
        story.append(Paragraph(f"{job.get('company','')} - {job.get('location','')}", company_style))
        for point in job.get("points", []) or []:
            story.append(Paragraph(f"• {point}", bullet_style))
        story.append(Spacer(1, 6))
    if data.get("education"):
        story.append(Paragraph("EDUCATION", section_style))
        for edu in data["education"]:
            line = f"<b>{edu.get('degree','')}</b>"
            if edu.get("year"):
                line += f" | {edu['year']}"
            story.append(Paragraph(line, exp_title_style))
            sch = edu.get("school", "")
            if edu.get("location"):
                sch += f" - {edu['location']}"
            story.append(Paragraph(sch, company_style))
            story.append(Spacer(1, 4))
    return story


def render_pdf_bytes(data: dict) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.6*inch, rightMargin=0.6*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    doc.build(_build_pdf_story(data))
    return buf.getvalue()


def extract_text_from_upload(filename: str, content: bytes) -> str:
    """Extract text from an uploaded PDF/DOCX/TXT for use as source resume."""
    name = (filename or "").lower()
    if name.endswith(".txt"):
        return content.decode("utf-8", errors="ignore").strip()
    if name.endswith(".pdf"):
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        return "\n".join((p.extract_text() or "") for p in reader.pages).strip()
    if name.endswith(".docx") or name.endswith(".doc"):
        from docx import Document
        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs).strip()
    raise ValueError(f"Unsupported file type: {filename}")
