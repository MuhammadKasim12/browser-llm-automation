#!/usr/bin/env python3
"""Headless parity test: deployed web /api/generate vs. local engine.

Calls the live web API and the local engine with identical inputs, renders
both PDFs through the same renderer, and prints a structural diff.

Usage:
    python scripts/test_web_vs_local.py \\
        --jd-file /tmp/apple_jd.txt \\
        --title "Senior Software Engineer" \\
        --company Apple

    python scripts/test_web_vs_local.py \\
        --url https://browser-llm-automation.vercel.app \\
        --jd "Build distributed systems in Java/Spring..." \\
        --title "Backend Engineer" \\
        --company Stripe \\
        --out output/web_vs_local
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "api"))

from _engine import (  # noqa: E402
    LLMError,
    find_current_role_config,
    generate_resume_json,
    load_default_resume_text,
    render_pdf_bytes,
)

DEFAULT_URL = "https://browser-llm-automation.vercel.app"


def call_web(url: str, title: str, company: str, jd: str, source_resume: str) -> dict:
    r = requests.post(
        f"{url.rstrip('/')}/api/generate",
        json={
            "job_title": title,
            "company": company,
            "job_description": jd,
            "source_resume": source_resume,
        },
        timeout=180,
    )
    if r.status_code != 200:
        raise RuntimeError(f"WEB HTTP {r.status_code}: {r.text[:500]}")
    return r.json()


def call_local(title: str, company: str, jd: str, source_resume: str) -> dict:
    return generate_resume_json(
        job_title=title,
        company=company,
        job_description=jd,
        resume_content=source_resume[:8000],
        current_role_config=find_current_role_config(),
    )


def summarize(label: str, data: dict) -> dict:
    meta = data.get("_meta") or {}
    exp = data.get("experience") or []
    jobs = [
        {"company": j.get("company", ""), "dates": j.get("dates", ""),
         "bullets": len(j.get("points") or [])}
        for j in exp
    ]
    return {
        "label": label,
        "provider": meta.get("provider"), "model": meta.get("model"),
        "title": data.get("title", ""),
        "summary_chars": len(data.get("summary", "")),
        "jobs_count": len(jobs),
        "jobs": jobs,
    }


def diff(web: dict, loc: dict) -> list[str]:
    issues: list[str] = []
    if web["jobs_count"] != loc["jobs_count"]:
        issues.append(f"jobs_count mismatch: web={web['jobs_count']} local={loc['jobs_count']}")
    for i, (a, b) in enumerate(zip(web["jobs"], loc["jobs"])):
        if a["company"] != b["company"]:
            issues.append(f"job[{i}] company: web={a['company']!r} local={b['company']!r}")
        if a["dates"] != b["dates"]:
            issues.append(f"job[{i}] dates: web={a['dates']!r} local={b['dates']!r}")
        if a["bullets"] != b["bullets"]:
            issues.append(f"job[{i}] bullet count: web={a['bullets']} local={b['bullets']}")
    return issues


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--jd"), p.add_argument("--jd-file")
    p.add_argument("--title", required=True)
    p.add_argument("--company", required=True)
    p.add_argument("--out", default="output/web_vs_local")
    p.add_argument("--source-resume-file", help="Optional override; defaults to api/_default_resume.txt")
    p.add_argument("--skip-web", action="store_true")
    p.add_argument("--skip-local", action="store_true")
    args = p.parse_args()

    if args.jd_file:
        jd = Path(args.jd_file).read_text()
    elif args.jd:
        jd = args.jd
    else:
        p.error("must provide --jd or --jd-file")

    src = (Path(args.source_resume_file).read_text()
           if args.source_resume_file else load_default_resume_text())

    out_dir = REPO_ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in args.company.lower()).strip("_") or "resume"

    results = {}
    if not args.skip_web:
        print(f"[web]   POST {args.url}/api/generate ...", flush=True)
        web_json = call_web(args.url, args.title, args.company, jd, src)
        (out_dir / f"{safe}_web.json").write_text(json.dumps(web_json, indent=2))
        (out_dir / f"{safe}_web.pdf").write_bytes(render_pdf_bytes(web_json))
        results["web"] = summarize("WEB", web_json)
        print(f"[web]   provider={results['web']['provider']} model={results['web']['model']}")

    if not args.skip_local:
        print("[local] generate_resume_json(...) ...", flush=True)
        loc_json = call_local(args.title, args.company, jd, src)
        (out_dir / f"{safe}_local.json").write_text(json.dumps(loc_json, indent=2))
        (out_dir / f"{safe}_local.pdf").write_bytes(render_pdf_bytes(loc_json))
        results["local"] = summarize("LOCAL", loc_json)
        print(f"[local] provider={results['local']['provider']} model={results['local']['model']}")

    print("\n" + "=" * 70)
    for r in results.values():
        print(f"{r['label']:6} provider={r['provider']:10} model={r['model']:42} title={r['title']!r}")
        for i, j in enumerate(r["jobs"]):
            print(f"  {i+1:>2}. {j['company']:45} {j['dates']:22} bullets={j['bullets']}")
        print()

    if "web" in results and "local" in results:
        issues = diff(results["web"], results["local"])
        print("STRUCTURAL DIFF:")
        if not issues:
            print("  ✅ identical job order, dates, and bullet counts")
        else:
            for i in issues:
                print(f"  ❌ {i}")

    print(f"\nArtifacts written to {out_dir}/")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (LLMError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
