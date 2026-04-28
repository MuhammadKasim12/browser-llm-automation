#!/usr/bin/env python3
"""
Professional Resume Generator with AI Customization
Generates PDF and DOCX resumes using industry-standard templates

Supports multiple LLM providers:
- cerebras: Cerebras API - llama-3.3-70b (fast inference)
- groq: Groq API - llama-3.3-70b-versatile
- openrouter: OpenRouter API - various free models
"""

import requests
import json
import os
from pathlib import Path

# LLM Provider Configuration
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
    }
}


def get_llm_config():
    """Get the current LLM provider configuration - prioritize Groq (70B follows multi-step prompts)"""
    for provider_name in ["groq", "cerebras", "openrouter"]:
        config = LLM_PROVIDERS[provider_name]
        api_key = os.environ.get(config["env_key"], "")
        if api_key:
            print(f"✅ Using {config['name']} LLM provider")
            return {
                "provider": provider_name,
                "name": config["name"],
                "url": config["url"],
                "model": config["model"],
                "api_key": api_key
            }
    raise ValueError("❌ No API key found. Set CEREBRAS_API_KEY, GROQ_API_KEY, or OPENROUTER_API_KEY")


def load_resume():
    """Load resume from local resumes folder"""
    try:
        from resume_handler import ResumeHandler
        resumes_dir = Path(__file__).parent / 'resumes'
        if not resumes_dir.exists():
            print(f"❌ Resumes folder not found: {resumes_dir}")
            return None
        
        handler = ResumeHandler(str(resumes_dir))
        resume = handler.get_default_resume()
        resume_content = resume.content if resume else ""
        print(f"📄 Loaded resume: {len(resume_content)} chars")
        
        # NOTE: Current role (Galaxy I Tech with Apple/Intuit) is now handled in
        # get_structured_resume() with role-based selection (Intuit for SWE, Apple for QA)
        # Don't add it here to avoid duplication

        return resume_content
    except Exception as e:
        print(f"Error loading resume: {e}")
        return None


# Personal Brand Profile - Use this to maintain consistent messaging
PERSONAL_BRAND = {
    "profile_snapshot": {
        "who_i_am": "Result-driven professional focused on building structured, scalable, and high-impact digital solutions aligned with real business goals.",
        "core_approach": ["Problem-first thinking", "Business value over hype", "Scalable architecture mindset"],
        "values": ["Quality", "Ownership", "Growth"]
    },
    "expertise_foundation": {
        "focus_areas": ["Full-Stack Development", "Headless CMS Architecture", "UI Performance Optimization", "API Integration & System Design"],
        "tech_stack": ["React", "Next.js", "TypeScript", "Node.js", "Headless CMS"]
    },
    "positioning": {
        "what_sets_apart": ["Modern tech stack expertise", "Business-driven development approach", "Strong problem-solving mindset"],
        "tagline": "Strategy + execution + scalability"
    },
    "work_structure": {
        "how_i_operate": ["Requirement analysis", "Solution planning", "Development & testing", "Deployment & optimization"],
        "flow": "From idea → architecture → production"
    },
    "professional_traits": {
        "how_i_show_up": ["Reliable & proactive", "Detail-oriented", "Collaborative team player"],
        "strengths": ["Focused", "Adaptive", "Results-oriented"]
    },
    "delivery_communication": {
        "how_i_create_results": ["Clear documentation & communication", "Clean, maintainable code", "On-time delivery with quality assurance"]
    }
}


def get_structured_resume(job_title: str, company: str, job_description: str, resume_content: str) -> dict:
    """Get AI-customized resume in structured JSON format"""

    # Load current role configuration
    current_role_config = None
    current_role_path = Path(__file__).parent / 'data' / 'current_role.json'
    if current_role_path.exists():
        with open(current_role_path) as f:
            current_role_config = json.load(f)

    # Determine role type based on job title
    job_title_lower = job_title.lower()
    role_type = "software_engineer"  # default
    if any(kw in job_title_lower for kw in ['qa', 'quality', 'sdet', 'test', 'automation']):
        role_type = "qa_engineer"

    print(f"🎯 Role type detected: {role_type} (using {'Apple' if role_type == 'qa_engineer' else 'Intuit'} experience)")

    # Build current experience text based on role type
    current_experience_text = ""
    selected_client = "Intuit" if role_type == "software_engineer" else "Apple"  # default
    if current_role_config:
        exp = current_role_config.get('current_experience', {})
        role_selection = current_role_config.get('role_selection', {})
        selected_client = role_selection.get(role_type, 'Intuit')

        # Find the matching client from current experience
        for client in exp.get('clients', []):
            if client.get('name') == selected_client:
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

        # Add missing PayPal experience based on role type
        missing_exp = current_role_config.get('missing_experience', {})
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

        # Add date corrections
        date_corrections = current_role_config.get('date_corrections', {})
        if date_corrections:
            current_experience_text += f"""

DATE CORRECTIONS (APPLY THESE):
{chr(10).join(f'• {company}: {dates}' for company, dates in date_corrections.items())}
"""

        # Add Altimetrik CoE info
        exp_restructure = current_role_config.get('experience_restructure', {})
        if 'Altimetrik' in exp_restructure:
            alt = exp_restructure['Altimetrik']
            coe = alt.get('coe', {})
            current_experience_text += f"""

ALTIMETRIK CONTEXT:
- Dates: {alt.get('dates')}
- Type: {alt.get('type')}
- Note: {alt.get('note')}
- {coe.get('role', '')}
"""

    # Build personalized context from brand profile
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

    # Add current experience to prompt if available
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
"""

    prompt = f"""{brand_context}
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
            "company": "Company Name",
            "location": "City, State",
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

    try:
        llm_config = get_llm_config()
    except ValueError as e:
        print(str(e))
        return None

    print(f"🤖 Using {llm_config['name']} ({llm_config['model']})")

    headers = {
        "Authorization": f"Bearer {llm_config['api_key']}",
        "Content-Type": "application/json"
    }

    if llm_config['provider'] == 'openrouter':
        headers["HTTP-Referer"] = "https://github.com/resume-generator"
        headers["X-Title"] = "Resume Generator"

    payload = {
        "model": llm_config['model'],
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Job: {job_title} at {company}\n\nJob Description:\n{job_description}\n\nResume:\n{resume_content}"}
        ],
        "max_tokens": 8000,
        "temperature": 0.5
    }

    if llm_config['provider'] in ['groq', 'cerebras']:
        payload["response_format"] = {"type": "json_object"}

    response = requests.post(llm_config['url'], headers=headers, json=payload)
    try:
        result = response.json()
    except Exception:
        print(f"❌ HTTP {response.status_code}: {response.text[:500]}")
        return None

    if "error" in result:
        error = result['error']
        print(f"❌ API Error: {error.get('message', str(error)) if isinstance(error, dict) else error}")
        return None

    if "choices" not in result:
        print(f"❌ HTTP {response.status_code}: unexpected response shape: {str(result)[:500]}")
        return None

    try:
        content = result["choices"][0]["message"]["content"]
        print(f"📝 LLM Response (first 500 chars): {content[:500]}")
        data = json.loads(content)
        if 'skills' in data:
            print(f"🔧 Skills structure: {type(data['skills'])} - {data['skills']}")
        if 'experience' in data and data['experience']:
            data['experience'] = sort_experience_by_date(data['experience'])
            print(f"📅 Sorted {len(data['experience'])} jobs by date (most recent first)")
        return data
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        return None


def sort_experience_by_date(experience_list: list) -> list:
    """Sort experience by date, most recent first, and normalize date formats."""
    import re
    from datetime import datetime

    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }

    month_abbrev = {
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
        7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
    }

    present_sentinels = ('present', 'current', 'till date', 'till now',
                         'now', 'today', 'ongoing')

    def parse_date(date_str: str) -> datetime:
        if not date_str:
            return datetime.min
        date_str = date_str.strip().lower()
        if date_str in present_sentinels:
            return datetime.max
        # Match "MMM YYYY" or longer month names (e.g., "Sep 2022", "Sept 2024", "September 2024")
        match = re.match(r'([a-z]{3,9})\s*(\d{4})', date_str)
        if match:
            month_str, year_str = match.groups()
            return datetime(int(year_str), month_map.get(month_str[:3], 1), 1)
        # Match "YYYY-MM-DD" format (e.g., "2022-09-17")
        match = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_str)
        if match:
            year, month, day = match.groups()
            return datetime(int(year), int(month), int(day))
        # Match "YYYY-MM" format (e.g., "2022-09")
        match = re.match(r'(\d{4})-(\d{2})', date_str)
        if match:
            year, month = match.groups()
            return datetime(int(year), int(month), 1)
        # Match just year
        match = re.match(r'(\d{4})', date_str)
        if match:
            return datetime(int(match.group(1)), 1, 1)
        return datetime.min

    def normalize_single_date(date_str: str) -> str:
        """Convert any date format to 'MMM YYYY' format."""
        if not date_str:
            return ""
        date_str = date_str.strip()
        lower_str = date_str.lower()
        if lower_str in present_sentinels:
            return 'Present'
        # Already in correct format? (MMM YYYY) or longer month name (e.g., "Sept 2024")
        if re.match(r'^[A-Za-z]{3,9}\s+\d{4}$', date_str):
            parsed = parse_date(date_str)
            if parsed not in (datetime.min, datetime.max):
                return f"{month_abbrev[parsed.month]} {parsed.year}"
            return date_str.title()
        # Parse and reformat
        parsed = parse_date(date_str)
        if parsed == datetime.min:
            return date_str  # Return as-is if can't parse
        return f"{month_abbrev[parsed.month]} {parsed.year}"

    def normalize_date_range(dates: str) -> str:
        """Normalize a date range like 'Sep 2022 - Oct 2023' or '2022-09-17 - 2023-10-31'."""
        if not dates:
            return ""
        dates = dates.strip()

        # Split on " - " or " – " (with spaces) or just "–" (en-dash) or "—" (em-dash)
        # This avoids splitting on hyphens inside ISO dates like "2022-09-17"
        parts = re.split(r'\s+[-–—]\s+|(?<!\d)[-–—](?!\d)', dates)

        # If that didn't work (no match), try to detect ISO date range pattern
        if len(parts) == 1 and re.match(r'\d{4}-\d{2}-\d{2}\s*[-–]\s*\d{4}-\d{2}-\d{2}', dates):
            # Handle "2022-09-17 - 2023-10-31" format
            iso_match = re.match(r'(\d{4}-\d{2}-\d{2})\s*[-–]\s*(\d{4}-\d{2}-\d{2})', dates)
            if iso_match:
                parts = [iso_match.group(1), iso_match.group(2)]

        if len(parts) == 2:
            start = normalize_single_date(parts[0])
            end = normalize_single_date(parts[1])
            return f"{start} - {end}"
        elif len(parts) == 1:
            return normalize_single_date(parts[0])
        return dates  # Return as-is if unexpected format

    def get_end_date(job: dict) -> datetime:
        dates = job.get('dates', '')
        if not dates:
            return datetime.min
        parts = re.split(r'\s*[-–]\s*', dates)
        return parse_date(parts[-1]) if parts else datetime.min

    # Normalize dates for all jobs FIRST
    for job in experience_list:
        if 'dates' in job:
            original = job['dates']
            job['dates'] = normalize_date_range(job['dates'])

    # Now sort by the normalized dates
    sorted_exp = sorted(experience_list, key=get_end_date, reverse=True)

    # Print the sorted and normalized experience
    for i, job in enumerate(sorted_exp):
        print(f"   {i+1}. {job.get('company', 'Unknown')} ({job.get('dates', 'No date')})")
    return sorted_exp


def generate_pdf(data: dict, output_path: str):
    """Generate PDF resume using ReportLab"""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER

    doc = SimpleDocTemplate(output_path, pagesize=letter,
                           leftMargin=0.6*inch, rightMargin=0.6*inch,
                           topMargin=0.5*inch, bottomMargin=0.5*inch)

    styles = getSampleStyleSheet()
    name_style = ParagraphStyle('Name', parent=styles['Title'], fontSize=22,
                                textColor=HexColor('#1e3a5f'), alignment=TA_CENTER, spaceAfter=4)
    title_style = ParagraphStyle('JobTitle', parent=styles['Normal'], fontSize=12,
                                 textColor=HexColor('#2563eb'), alignment=TA_CENTER, spaceAfter=4)
    contact_style = ParagraphStyle('Contact', parent=styles['Normal'], fontSize=9,
                                   textColor=HexColor('#6b7280'), alignment=TA_CENTER, spaceAfter=12)
    section_style = ParagraphStyle('Section', parent=styles['Heading2'], fontSize=11,
                                   textColor=HexColor('#1e3a5f'), spaceAfter=6, spaceBefore=10)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10,
                                textColor=HexColor('#374151'), spaceAfter=4, leading=14)
    exp_title_style = ParagraphStyle('ExpTitle', parent=styles['Normal'], fontSize=10,
                                     textColor=HexColor('#1a1a1a'), fontName='Helvetica-Bold')
    company_style = ParagraphStyle('Company', parent=styles['Normal'], fontSize=9,
                                   textColor=HexColor('#2563eb'), fontName='Helvetica-Oblique', spaceAfter=4)
    bullet_style = ParagraphStyle('Bullet', parent=styles['Normal'], fontSize=9,
                                  textColor=HexColor('#374151'), leftIndent=12, spaceAfter=2, leading=12)

    story = []
    story.append(Paragraph(data.get('name', ''), name_style))
    story.append(Paragraph(data.get('title', ''), title_style))
    contact = f"{data.get('email', '')} &nbsp;|&nbsp; {data.get('phone', '')} &nbsp;|&nbsp; {data.get('location', '')}"
    story.append(Paragraph(contact, contact_style))

    story.append(Paragraph('PROFESSIONAL SUMMARY', section_style))
    story.append(Paragraph(data.get('summary', ''), body_style))

    story.append(Paragraph('TECHNICAL SKILLS', section_style))
    skills_data = data.get('skills') or {}
    if isinstance(skills_data, dict):
        skills_items = skills_data.items()
    elif isinstance(skills_data, list):
        skills_items = [('Skills', skills_data)]
    else:
        skills_items = [('Skills', str(skills_data))]
    for category, skills in skills_items:
        skills_text = ', '.join(str(s) for s in skills) if isinstance(skills, list) else str(skills)
        story.append(Paragraph(f"<b>{category}:</b> {skills_text}", body_style))

    story.append(Paragraph('PROFESSIONAL EXPERIENCE', section_style))
    for job in data.get('experience', []):
        story.append(Paragraph(f"<b>{job.get('title', '')}</b> | {job.get('dates', '')}", exp_title_style))
        company = job.get('company', '')
        location = job.get('location', '')
        company_line = f"{company} - {location}" if location else company
        story.append(Paragraph(company_line, company_style))
        for point in job.get('points', []):
            story.append(Paragraph(f"• {point}", bullet_style))
        story.append(Spacer(1, 6))

    # Education section
    if data.get('education'):
        story.append(Paragraph('EDUCATION', section_style))
        for edu in data.get('education', []):
            degree = edu.get('degree', '')
            school = edu.get('school', '')
            location = edu.get('location', '')
            year = edu.get('year', '')

            # Build education line
            edu_line = f"<b>{degree}</b>"
            if year:
                edu_line += f" | {year}"
            story.append(Paragraph(edu_line, exp_title_style))

            school_line = school
            if location:
                school_line += f" - {location}"
            story.append(Paragraph(school_line, company_style))
            story.append(Spacer(1, 4))

    doc.build(story)
    print(f"✅ PDF saved: {output_path}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("📄 PROFESSIONAL RESUME GENERATOR")
    print("="*60 + "\n")

    resume = load_resume()
    if not resume:
        print("❌ Could not load resume")
        exit(1)

    job_title = input("Job Title: ").strip() or "Senior Software Engineer"
    company = input("Company: ").strip() or "Google"
    print("Job Description (paste, then press Enter twice):")
    lines = []
    while True:
        line = input()
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)
    job_description = "\n".join(lines[:-1]) if lines else "Software Engineer role"

    print("\n⏳ AI is customizing your resume...\n")
    data = get_structured_resume(job_title, company, job_description, resume[:8000])

    if not data:
        print("❌ Failed to generate structured resume")
        exit(1)

    output_dir = Path(__file__).parent / 'output'
    output_dir.mkdir(exist_ok=True)

    safe_company = company.lower().replace(' ', '_').replace('.', '')
    generate_pdf(data, str(output_dir / f"resume_{safe_company}.pdf"))
    print(f"\n🎉 Done! Check the 'output' folder.")

