"""
Job Application Automation
Uses the browser agent to automatically apply to jobs.
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

from agent import BrowserAgent

load_dotenv()


# Job application goal template
JOB_APPLICATION_GOAL = """
Apply to this job position. Fill in the application form with my profile information:
- Name: {name}
- Email: {email}
- Phone: {phone}
- Location: {location}
- LinkedIn: {linkedin}

Steps to follow:
1. Look for an "Apply" or "Apply Now" button and click it
2. Fill in any required fields with my information
3. Upload resume if there's a file upload (skip if not possible)
4. Submit the application
5. Confirm the application was submitted

If asked for information not in my profile, make reasonable assumptions or skip optional fields.
Report 'done' when the application is submitted successfully.
Report 'error' if you cannot proceed or the application requires login/account creation.
"""


async def apply_to_job(job_url: str, resume_path: str = None):
    """Apply to a job given its URL."""
    
    # Build the goal with user profile
    goal = JOB_APPLICATION_GOAL.format(
        name=os.getenv("APPLICANT_NAME", ""),
        email=os.getenv("APPLICANT_EMAIL", ""),
        phone=os.getenv("APPLICANT_PHONE", ""),
        location=os.getenv("APPLICANT_LOCATION", ""),
        linkedin=os.getenv("APPLICANT_LINKEDIN", ""),
    )
    
    if resume_path:
        goal += f"\nResume file to upload: {resume_path}"
    
    agent = BrowserAgent(headless=False)
    success = await agent.run(url=job_url, goal=goal)
    
    return success


async def main():
    """Main entry point."""
    
    if len(sys.argv) < 2:
        print("""
🤖 Job Application Bot
======================

Usage:
    python apply_job.py <job_url> [resume_path]

Examples:
    python apply_job.py "https://boards.greenhouse.io/company/jobs/123"
    python apply_job.py "https://example.com/careers/job" "./resume.pdf"

Supported job boards:
    ✅ Greenhouse
    ✅ Lever
    ✅ Workday (basic)
    ✅ Direct company career pages
    
    ⚠️ LinkedIn (requires login)
    ⚠️ Indeed (may require login)
""")
        return
    
    job_url = sys.argv[1]
    resume_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"\n🚀 Starting job application automation...")
    print(f"📍 URL: {job_url}")
    if resume_path:
        print(f"📄 Resume: {resume_path}")
    
    success = await apply_to_job(job_url, resume_path)
    
    if success:
        print("\n🎉 Application submitted successfully!")
    else:
        print("\n❌ Application could not be completed")
        print("   Check the action summary above for details")


if __name__ == "__main__":
    asyncio.run(main())

