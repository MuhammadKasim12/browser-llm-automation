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
        "model": "qwen-3-235b-a22b-instruct-2507",
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
    "mistral": {
        "name": "Mistral",
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-large-latest",
        "env_key": "MISTRAL_API_KEY",
    },
}

_DEFAULT_PROVIDER_ORDER = ("groq", "cerebras", "openrouter", "mistral")

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


def get_llm_config(preferred: Optional[str] = None, order: Iterable[str] = _DEFAULT_PROVIDER_ORDER) -> dict:
    """Pick a provider whose API key is set. `preferred` (or LLM_PROVIDER env) wins if its key exists."""
    chain = get_llm_config_chain(preferred=preferred, order=order)
    if not chain:
        raise LLMError("No API key found. Set CEREBRAS_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY, or MISTRAL_API_KEY.")
    return chain[0]


def get_llm_config_chain(preferred: Optional[str] = None,
                         order: Iterable[str] = _DEFAULT_PROVIDER_ORDER) -> list:
    """Return ALL providers with API keys set, in fallback order (preferred first)."""
    candidates = list(order)
    env_pref = os.environ.get("LLM_PROVIDER", "").lower().strip() or None
    chosen = preferred or env_pref
    if chosen and chosen in LLM_PROVIDERS:
        candidates = [chosen] + [p for p in candidates if p != chosen]
    model_override = os.environ.get("LLM_MODEL", "").strip() or None
    chain = []
    for name in candidates:
        cfg = LLM_PROVIDERS.get(name)
        if not cfg or not os.environ.get(cfg["env_key"]):
            continue
        resolved = {"provider": name, **cfg, "api_key": os.environ[cfg["env_key"]]}
        # Only honor LLM_MODEL when paired with an explicit LLM_PROVIDER (or `preferred`)
        # that matches the chosen provider, otherwise an override meant for one provider
        # leaks across providers (e.g. Cerebras model name sent to Groq).
        if model_override and chosen == name:
            resolved["model"] = model_override
        chain.append(resolved)
    return chain


def _is_rate_limit_error(msg: str) -> bool:
    """True if the error is transient/retryable on a different provider.

    Covers explicit rate limits (429/quota/TPM) plus transient upstream
    failures from any provider (OpenRouter 'Provider returned error',
    Cerebras queue overflows, generic 5xx) that another provider may
    successfully answer. Auth/config errors (401/403/model-not-found)
    intentionally still abort the chain.
    """
    m = (msg or "").lower()
    if any(s in m for s in ("rate limit", "ratelimit", "429", "too many requests",
                             "quota", "tpm", "tokens per minute", "rpm",
                             "queue_exceeded", "queue exceeded")):
        return True
    if any(s in m for s in ("provider returned error", "service unavailable",
                             "internal server error", "bad gateway",
                             "gateway timeout", "upstream", "503", "502", "504",
                             "timed out", "timeout")):
        return True
    return False


def find_current_role_config() -> Optional[dict]:
    """Load current_role.json bundled in api/ (Vercel) with fallback to data/ in repo root."""
    here = Path(__file__).resolve()
    candidates = [
        here.parent / "_current_role.json",
        here.parent.parent / "data" / "current_role.json",
        here.parent.parent.parent / "data" / "current_role.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return json.loads(candidate.read_text())
            except Exception:
                return None
    return None


def load_default_resume_text() -> str:
    """Return cached resume text bundled in api/ (or empty string)."""
    for p in (Path(__file__).parent / "_default_resume.txt",
              Path(__file__).parent / "default_resume.txt"):
        if p.exists():
            return p.read_text(encoding="utf-8", errors="ignore").strip()
    return ""


def _build_prompt(job_title: str, company: str, job_description: str, resume_content: str,
                  current_role_config: Optional[dict], role_type: str) -> str:
    """Mirrors generate_resume.py prompt verbatim so web output matches local CLI."""
    selected_client = "Intuit" if role_type == "software_engineer" else "Apple"
    current_experience_text = ""
    if current_role_config:
        exp = current_role_config.get("current_experience", {})
        role_selection = current_role_config.get("role_selection", {})
        selected_client = role_selection.get(role_type, selected_client)

        for client in exp.get("clients", []):
            if client.get("name") == selected_client:
                current_experience_text = f"""
CURRENT ROLE (MUST BE FIRST IN EXPERIENCE LIST):
Company: Galaxy I Tech (Contract)
Client: {client.get('name')}
Title: {client.get('title')}
Location: {exp.get('location')}
Dates: {client.get('dates')}
Points:
{chr(10).join('• ' + p for p in client.get('points', []))}
"""
                break

        missing_exp = current_role_config.get("missing_experience", {})
        paypal_key = f"PayPal_{'QE' if role_type == 'qa_engineer' else 'SWE'}"
        if paypal_key in missing_exp:
            paypal = missing_exp[paypal_key]
            current_experience_text += f"""

MISSING EXPERIENCE (INCLUDE IN TIMELINE - between Ancestry and Proofpoint):
Company: {paypal.get('company')}
Title: {paypal.get('title')}
Location: {paypal.get('location')}
Dates: {paypal.get('dates')}
Points:
{chr(10).join('• ' + p for p in paypal.get('points', []))}
"""

        date_corrections = current_role_config.get("date_corrections", {})
        if date_corrections:
            current_experience_text += f"""

DATE CORRECTIONS (APPLY THESE):
{chr(10).join(f'• {co}: {d}' for co, d in date_corrections.items())}
"""

        exp_restructure = current_role_config.get("experience_restructure", {})
        if "Altimetrik" in exp_restructure:
            alt = exp_restructure["Altimetrik"]
            coe = alt.get("coe", {})
            current_experience_text += f"""

ALTIMETRIK CONTEXT:
- Dates: {alt.get('dates')}
- Type: {alt.get('type')}
- Note: {alt.get('note')}
- {coe.get('role', '')}
"""

        older_experience = current_role_config.get("older_experience", [])
        if older_experience:
            blocks = []
            for entry in older_experience:
                bullets = chr(10).join('• ' + p for p in entry.get('points', []))
                blocks.append(
                    f"Company: {entry.get('company')}\n"
                    f"Title: {entry.get('title')}\n"
                    f"Location: {entry.get('location')}\n"
                    f"Dates: {entry.get('dates')}\n"
                    f"Points:\n{bullets}"
                )
            current_experience_text += (
                "\n\nOLDER EXPERIENCE (MUST INCLUDE - APPEND AFTER ANCESTRY IN CHRONOLOGICAL ORDER):\n"
                + "\n\n".join(blocks)
                + "\n"
            )

        truncation = current_role_config.get("history_truncation", {})
        if truncation:
            excluded = ", ".join(truncation.get("exclude_companies", []))
            current_experience_text += f"""

HISTORY TRUNCATION (STRICT):
- DO NOT include any role that started before {truncation.get('exclude_before', 'Nov 2012')}
- DO NOT include these companies under any circumstance: {excluded}
- DO NOT invent any company that is not present in the resume or in the explicit lists above
"""

    brand_context = f"""
CANDIDATE'S PERSONAL BRAND (Use this to shape the resume voice and positioning):

PROFILE: {PERSONAL_BRAND['profile_snapshot']['who_i_am']}

CORE APPROACH:
- {chr(10).join('• ' + a for a in PERSONAL_BRAND['profile_snapshot']['core_approach'])}

EXPERTISE FOCUS AREAS:
- {chr(10).join('• ' + a for a in PERSONAL_BRAND['expertise_foundation']['focus_areas'])}

WHAT SETS THIS CANDIDATE APART:
- {chr(10).join('• ' + d for d in PERSONAL_BRAND['positioning']['what_sets_apart'])}

PROFESSIONAL TRAITS (reflect these in bullet points):
- {chr(10).join('• ' + t for t in PERSONAL_BRAND['professional_traits']['how_i_show_up'])}
- {chr(10).join('• ' + s for s in PERSONAL_BRAND['professional_traits']['strengths'])}

DELIVERY STYLE (incorporate into achievements):
- {chr(10).join('• ' + d for d in PERSONAL_BRAND['delivery_communication']['how_i_create_results'])}

MODERN TECH STACK (prioritize these when relevant to JD):
{', '.join(PERSONAL_BRAND['expertise_foundation']['tech_stack'])}
"""

    experience_instructions = ""
    if current_experience_text:
        experience_instructions = f"""
{current_experience_text}

CRITICAL EXPERIENCE INSTRUCTIONS (MUST FOLLOW):
1. ONLY include the ONE current role listed above (Galaxy I Tech with {selected_client}) - DO NOT add any other clients
2. The CURRENT ROLE at Galaxy I Tech - Client: {selected_client} MUST be the FIRST experience entry
3. Include the MISSING PayPal experience in the correct chronological position (Mar 2020 - Aug 2021)
4. Apply all DATE CORRECTIONS listed above (e.g., Citi ends Jun 2025, NOT Present)
5. Order all other experiences in reverse chronological order (most recent first)
6. DO NOT invent or duplicate experiences - only use what's in the resume + the additions above
7. INCLUDE ALL bullet points listed for the CURRENT ROLE above - do not summarize, condense, or omit any of them
8. PRESERVE the FULL text of every bullet point exactly as a complete sentence ending with proper punctuation - do not abbreviate, shorten, or drop trailing words/letters
9. The CURRENT ROLE's "company" field MUST be EXACTLY: "Galaxy I Tech (Contract) - Client: {selected_client}" - DO NOT split the client into the location field, DO NOT drop the "Client: {selected_client}" suffix
10. Every job's "location" field MUST be a geographic location only (e.g. "San Jose, CA", "SF Bay Area", "San Francisco, CA"). It MUST NEVER contain any date, year, month, ISO timestamp, or date range. Dates ALWAYS go in the "dates" field, never in "location"
11. INCLUDE every entry from the OLDER EXPERIENCE block above verbatim (company, title, location, dates exactly as provided) - do NOT collapse, merge, rename, or skip any of them
12. ENFORCE the HISTORY TRUNCATION rules: never include excluded companies (e.g. Zyme Solutions, Wipro), never include any role that started before the exclude_before date, and never invent a company that is not present in the resume or in the explicit blocks above
"""

    return f"""{brand_context}
{experience_instructions}

Analyze the resume and job description, then return a JSON object with this EXACT structure:
{{
    "name": "Full Name",
    "title": "Professional Title tailored to job",
    "email": "muhammadkasim@gmail.com",
    "phone": "(510) 771-4493",
    "location": "San Jose, CA",
    "linkedin": "linkedin URL or empty string",
    "summary": "3-4 sentence professional summary that reflects the PERSONAL BRAND above while tailored to the job",
    "skills": {{
        "Languages": "Python, Java, JavaScript, TypeScript, etc",
        "Frameworks": "React, Next.js, Node.js, Spring Boot, etc",
        "Cloud & DevOps": "AWS, Kubernetes, Docker, etc",
        "Databases": "PostgreSQL, MongoDB, etc"
    }},
    "experience": [
        {{
            "title": "Job Title",
            "company": "Company Name (full string, including any '- Client: X' suffix)",
            "location": "City, State (geographic location ONLY - never a date, year, or month)",
            "dates": "MMM YYYY - MMM YYYY",
            "points": [
                "First bullet point showing problem-first thinking with metrics",
                "Second bullet point demonstrating business value delivery",
                "Third bullet point highlighting scalable architecture work"
            ]
        }}
    ]
}}

CRITICAL REQUIREMENTS:
- Skills MUST be comma-separated strings, NOT arrays
- Each job MUST have 3-5 bullet points in "points" array
- FIRST EXPERIENCE MUST be the CURRENT ROLE specified above (Galaxy I Tech) - this is MANDATORY
- Order experience REVERSE CHRONOLOGICALLY (most recent first) AFTER the current role
- Use date format "MMM YYYY - MMM YYYY" (e.g., "Sep 2022 - Oct 2023")
- Include ALL work experience from the original resume PLUS the current role and PayPal experience specified above
- Apply Citi date correction: Oct 2024 - Jun 2025 (NOT Present)
- Keep all information truthful
- Quantify achievements where possible (%, $, time saved, users impacted)

JOB DESCRIPTION KEYWORD MATCHING:
- Analyze job description for key requirements and technologies
- Rewrite bullet points to naturally incorporate JD keywords
- Prioritize experiences that match what the JD is asking for
- Highlight React, Next.js, TypeScript, Node.js when relevant to the role

PERSONAL BRAND VOICE (CRITICAL):
- The summary MUST reflect: "{PERSONAL_BRAND['profile_snapshot']['who_i_am'][:60]}..."
- Bullet points should show: Problem-first thinking, Business value delivery, Scalable solutions
- Convey reliability, proactivity, and attention to detail
- Show clear documentation/communication skills through structured achievements
- Demonstrate "Strategy + execution + scalability" through concrete examples

HUMANIZATION (AVOID AI-SOUNDING TEXT):
- Write like a real person, not a template
- Vary sentence structures - don't start every bullet the same way
- Use natural action verbs: Led, Built, Designed, Drove, Collaborated, Architected, Streamlined
- Include context and specifics that make achievements authentic
- Avoid buzzword stuffing - be specific and genuine
- Tell mini-stories: Problem → Solution → Impact

SKILLS HONESTY (CRITICAL - DO NOT VIOLATE):
- ONLY list skills that are ACTUALLY mentioned in the provided resume
- DO NOT add skills from the job description that are NOT in the resume
- DO NOT fabricate or invent skills the candidate doesn't have
- If the job requires a skill not in the resume (e.g., Scala, Ruby, Go), DO NOT add it
- Focus on highlighting TRANSFERABLE skills that ARE in the resume
- It's better to have fewer honest skills than to lie about capabilities

Return ONLY valid JSON, no other text."""


_MONTH_MAP = {m: i for i, m in enumerate(
    ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"], start=1)}
_MONTH_ABBR = {v: k.title() for k, v in _MONTH_MAP.items()}


_PRESENT_SENTINELS = ("present", "current", "till date", "till now",
                      "now", "today", "ongoing")


def _parse_date(date_str: str) -> datetime:
    if not date_str:
        return datetime.min
    s = date_str.strip().lower()
    if s in _PRESENT_SENTINELS:
        return datetime.max
    m = re.match(r"([a-z]{3,9})\s*(\d{4})", s)
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
    if s.lower() in _PRESENT_SENTINELS:
        return "Present"
    if re.match(r"^[A-Za-z]{3,9}\s+\d{4}$", s):
        parsed = _parse_date(s)
        if parsed not in (datetime.min, datetime.max):
            return f"{_MONTH_ABBR[parsed.month]} {parsed.year}"
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


def _call_one_provider(cfg: dict, prompt: str, job_title: str, company: str,
                       job_description: str, resume_content: str) -> dict:
    """Single LLM call. Raises LLMError on any failure."""
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
        "max_tokens": 12000,
        "temperature": 0.5,
    }
    if cfg["provider"] in ("groq", "cerebras", "mistral"):
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


def generate_resume_json(
    job_title: str,
    company: str,
    job_description: str,
    resume_content: str,
    current_role_config: Optional[dict] = None,
    preferred_provider: Optional[str] = None,
) -> dict:
    """Call the LLM with provider fallback on rate-limit errors.

    Tries preferred provider first; on 429/rate-limit, falls through to the
    next provider with an API key configured. Other errors abort immediately.
    """
    role_type = _detect_role_type(job_title)
    if current_role_config is None:
        current_role_config = find_current_role_config()

    prompt = _build_prompt(job_title, company, job_description, resume_content,
                           current_role_config, role_type)
    chain = get_llm_config_chain(preferred=preferred_provider)
    if not chain:
        raise LLMError("No API key found. Set CEREBRAS_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY, or MISTRAL_API_KEY.")

    last_error: Optional[LLMError] = None
    for idx, cfg in enumerate(chain):
        print(f"[resume-llm] attempt={idx+1}/{len(chain)} provider={cfg['provider']} model={cfg['model']} role_type={role_type} role_config_loaded={current_role_config is not None}", flush=True)
        try:
            return _call_one_provider(cfg, prompt, job_title, company, job_description, resume_content)
        except LLMError as e:
            last_error = e
            if _is_rate_limit_error(str(e)) and idx < len(chain) - 1:
                next_cfg = chain[idx + 1]
                print(f"[resume-llm] rate-limited on {cfg['provider']}; falling back to {next_cfg['provider']} ({next_cfg['model']})", flush=True)
                continue
            raise
    raise last_error or LLMError("All providers exhausted")


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
    skills_data = data.get("skills") or {}
    if isinstance(skills_data, dict):
        skills_items = skills_data.items()
    elif isinstance(skills_data, list):
        skills_items = [("Skills", skills_data)]
    else:
        skills_items = [("Skills", str(skills_data))]
    for category, skills in skills_items:
        text = ", ".join(str(s) for s in skills) if isinstance(skills, list) else str(skills)
        story.append(Paragraph(f"<b>{category}:</b> {text}", body_style))
    story.append(Paragraph("PROFESSIONAL EXPERIENCE", section_style))
    for job in data.get("experience", []) or []:
        story.append(Paragraph(f"<b>{job.get('title','')}</b> | {job.get('dates','')}", exp_title_style))
        company = job.get('company', '')
        location = job.get('location', '')
        company_line = f"{company} - {location}" if location else company
        story.append(Paragraph(company_line, company_style))
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
