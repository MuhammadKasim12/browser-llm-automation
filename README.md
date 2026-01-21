# LinkedIn Job Application Bot

An automated job application bot that uses LLMs to navigate LinkedIn and apply to jobs via Easy Apply and external application sites.

## Features

- **Automated LinkedIn Easy Apply** - Fills out application forms automatically
- **External Site Support** - Handles Workday, Greenhouse, Lever, and other ATS platforms
- **Custom Resume Generation** - Generates tailored resumes for each job using AI
- **Multi-LLM Support** - Uses Cerebras, Groq, Mistral, or OpenRouter (all free tiers)
- **Persistent Browser Session** - Stays logged in between runs
- **Human-like Behavior** - Random delays, character-by-character typing to avoid detection
- **EEO Form Handling** - Automatically fills voluntary self-identification forms
- **Smart Dropdown Handling** - Keyboard navigation for complex dropdowns

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager (recommended) or pip

## Installation

1. **Clone and navigate to the directory:**
   ```bash
   cd browser-llm-automation
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Install Playwright browsers:**
   ```bash
   uv run playwright install chromium
   ```

## Configuration

All configuration is passed via environment variables. **Do NOT store credentials in files.**

### Required Environment Variables

Set these in your shell before running, or pass them inline:

```bash
# LLM API Keys (at least one required - all have free tiers)
export CEREBRAS_API_KEY=your_key_here      # Free: https://cerebras.ai
export GROQ_API_KEY=your_key_here          # Free: https://groq.com
export MISTRAL_API_KEY=your_key_here       # Free: https://mistral.ai
export OPENROUTER_API_KEY=your_key_here    # Free: https://openrouter.ai

# LinkedIn Credentials
export LINKEDIN_EMAIL=your_email@example.com
export LINKEDIN_PASSWORD=your_password

# Your Profile Information
export APPLICANT_FIRST_NAME=John
export APPLICANT_LAST_NAME=Doe
export APPLICANT_NAME="John Doe"
export APPLICANT_EMAIL=john.doe@email.com
export APPLICANT_PHONE="(555) 123-4567"
export APPLICANT_LOCATION="San Francisco, CA"
export APPLICANT_LINKEDIN=https://www.linkedin.com/in/johndoe
export APPLICANT_YEARS_EXPERIENCE="5+"
export APPLICANT_TITLE="Software Engineer"
export APPLICANT_GENDER=Male
export APPLICANT_RACE=Asian
```

### Running with Inline Environment Variables

You can also pass environment variables inline:

```bash
CEREBRAS_API_KEY=xxx LINKEDIN_EMAIL=you@email.com LINKEDIN_PASSWORD=secret \
  uv run python linkedin_apply.py "Software Developer" "San Jose, CA"
```

### Using a Secrets Manager (Recommended)

For production use, consider using a secrets manager like:
- **1Password CLI**: `op run -- uv run python linkedin_apply.py ...`
- **AWS Secrets Manager**
- **HashiCorp Vault**

## Usage

### Basic Usage

```bash
uv run python linkedin_apply.py "Job Title" "Location"
```

### Examples

```bash
# Search for Software Developer jobs in San Jose
uv run python linkedin_apply.py "Software Developer" "San Jose, CA"

# Search for SDET jobs in the Bay Area
uv run python linkedin_apply.py "SDET" "Bay Area"

# Search for remote jobs
uv run python linkedin_apply.py "Python Developer" "Remote"
```

### Options

The bot will:
1. Open a browser window (you'll see it running)
2. Log into LinkedIn (or use existing session)
3. Search for jobs matching your criteria
4. Filter for Easy Apply jobs, sorted by date (most recent first)
5. Apply to each job, generating a custom resume
6. Handle EEO forms automatically
7. Continue until you stop it (Ctrl+C)

## Resume Customization

The bot generates custom resumes for each job application. Place your base resume in:
```
../resume-generator-mobile/resumes/your_resume.pdf
```

Or configure the path in the code.

## Directory Structure

```
browser-llm-automation/
├── linkedin_apply.py      # Main application script
├── browser_controller.py  # Playwright browser control
├── dom_extractor.py       # DOM parsing for LLM
├── llm_planner.py         # LLM action planning
├── .env.example           # Example environment variables (no credentials)
├── .gitignore             # Prevents credentials from being committed
├── .browser_data/         # Persistent browser session (gitignored)
├── screenshots/           # Debug screenshots
└── output/                # Generated resumes
```

## Troubleshooting

### Login Issues
- The bot uses a persistent browser session in `.browser_data/`
- If login fails, delete `.browser_data/` and re-run
- First run will require manual login; subsequent runs reuse the session

### Dropdown Selection Issues
- The bot uses keyboard navigation (ArrowDown + Enter) for complex dropdowns
- If a dropdown fails, the bot will retry with different methods

### External Sites
- Some external ATS sites may require manual intervention
- The bot will pause and give you 10 seconds to help if stuck
- After 4 repeated identical actions, it skips to the next job

### Rate Limiting
- The bot automatically switches between LLM providers if rate limited
- Cerebras → Groq → Mistral → OpenRouter fallback chain

## Screenshots

Debug screenshots are saved to `screenshots/` when errors occur or loops are detected.

## Stopping the Bot

Press `Ctrl+C` to stop the bot gracefully. Your progress is saved.

## Legal Disclaimer

This tool is for educational purposes. Use responsibly and in accordance with LinkedIn's Terms of Service. Automated applications may violate platform policies.

## License

MIT