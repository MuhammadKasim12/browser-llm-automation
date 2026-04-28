"""
LinkedIn Job Application Automation
Logs into LinkedIn and applies to jobs using Easy Apply.
Integrates resume customization based on job description.
"""
import asyncio
import os
import sys
import threading
import select
from pathlib import Path
from dotenv import load_dotenv

from browser_controller import BrowserController
from llm_planner import get_next_action
from dom_extractor import get_page_context

load_dotenv()


# Global flag for user intervention request
_user_wants_control = threading.Event()
_keyboard_listener_running = False
_keyboard_thread = None


def _keyboard_listener():
    """Background thread that listens for keyboard input to trigger user intervention."""
    global _keyboard_listener_running
    import termios
    import tty

    print("⌨️  Press 'i' at any time to INTERVENE and take control")
    print("⌨️  Press 'q' to quit the keyboard listener")

    old_settings = None
    try:
        # Save terminal settings
        old_settings = termios.tcgetattr(sys.stdin)
        # Set terminal to raw mode (non-blocking single char read)
        tty.setcbreak(sys.stdin.fileno())

        while _keyboard_listener_running:
            # Check if there's input available (non-blocking)
            if select.select([sys.stdin], [], [], 0.5)[0]:
                char = sys.stdin.read(1)
                if char.lower() == 'i':
                    print("\n\n🖐️  INTERVENTION REQUESTED! Bot will pause at next step...")
                    _user_wants_control.set()
                elif char.lower() == 'q':
                    print("\n⌨️  Keyboard listener stopped")
                    break
    except Exception as e:
        # Terminal doesn't support raw mode (e.g., running in IDE)
        pass
    finally:
        # Restore terminal settings
        if old_settings:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            except:
                pass


def start_keyboard_listener():
    """Start the background keyboard listener thread."""
    global _keyboard_listener_running, _keyboard_thread
    if not _keyboard_listener_running:
        _keyboard_listener_running = True
        _keyboard_thread = threading.Thread(target=_keyboard_listener, daemon=True)
        _keyboard_thread.start()


def stop_keyboard_listener():
    """Stop the background keyboard listener thread."""
    global _keyboard_listener_running
    _keyboard_listener_running = False


class LinkedInAgent:
    """LinkedIn-specific job application agent."""

    # Class-level storage for learned answers (persists across applications)
    learned_answers = {}

    def __init__(self, interactive: bool = True, connect_to_existing: bool = True):
        # Try to connect to existing Chrome browser first (avoids bot detection)
        self.controller = BrowserController(headless=False, slow_mo=150, connect_to_existing=connect_to_existing)
        self.interactive = interactive  # Enable interactive prompts for unknown questions
        self.email = os.getenv("LINKEDIN_EMAIL")
        self.password = os.getenv("LINKEDIN_PASSWORD")
        self.user_profile = {
            "first_name": os.getenv("APPLICANT_FIRST_NAME", ""),
            "last_name": os.getenv("APPLICANT_LAST_NAME", ""),
            "name": os.getenv("APPLICANT_NAME", ""),
            "email": os.getenv("APPLICANT_EMAIL", ""),
            "phone": os.getenv("APPLICANT_PHONE", ""),
            "location": os.getenv("APPLICANT_LOCATION", ""),
            "linkedin": os.getenv("APPLICANT_LINKEDIN", ""),
            "years_experience": os.getenv("APPLICANT_YEARS_EXPERIENCE", ""),
            "title": os.getenv("APPLICANT_TITLE", ""),
            "gender": os.getenv("APPLICANT_GENDER", "Male"),
            "race": os.getenv("APPLICANT_RACE", "Asian"),
        }
        self.action_history = []
        self.current_job_title = ""
        self.current_company = ""
        self.current_job_description = ""
        self.customized_resume_path = None
        self.user_interventions = []  # Learn from user actions
        self.learned_fixes = {}  # Store fixes for specific situations
        self.screenshot_counter = 0
        self.screenshots_dir = Path(__file__).parent / "screenshots"
        self.screenshots_dir.mkdir(exist_ok=True)
        self._load_learned_answers()  # Load previously learned answers
        self._load_learned_patterns()  # Load learned action patterns from user demonstrations

    async def _capture_debug_screenshot(self, label: str = "debug", full_page: bool = False) -> str:
        """Capture a screenshot for debugging purposes."""
        self.screenshot_counter += 1
        # Sanitize label for filename
        safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)[:30]
        suffix = "_full" if full_page else ""
        filename = f"{self.screenshot_counter:03d}_{safe_label}{suffix}.png"
        filepath = self.screenshots_dir / filename
        try:
            await self.controller.page.screenshot(path=str(filepath), full_page=full_page, timeout=10000)
            print(f"📸 Screenshot saved: {filename}")
            return str(filepath)
        except Exception as e:
            print(f"⚠️ Screenshot skipped: {str(e)[:50]}")
            return ""

    async def _capture_fullpage_screenshot(self, label: str = "fullpage") -> str:
        """Capture a full-page screenshot for analysis."""
        return await self._capture_debug_screenshot(label, full_page=True)

    async def _check_if_blocked(self) -> tuple[bool, str]:
        """Check if access is blocked by analyzing the page DOM.

        Returns (is_blocked, reason) tuple.
        """
        try:
            result = await self.controller.page.evaluate('''() => {
                const bodyText = document.body.innerText.toLowerCase();
                const title = document.title.toLowerCase();
                const url = window.location.href.toLowerCase();

                // Check for common block/security messages
                const blockPatterns = [
                    { pattern: 'access denied', reason: 'Access Denied' },
                    { pattern: 'access blocked', reason: 'Access Blocked' },
                    { pattern: 'blocked', reason: 'Blocked' },
                    { pattern: 'unusual activity', reason: 'Unusual Activity Detected' },
                    { pattern: 'suspicious activity', reason: 'Suspicious Activity' },
                    { pattern: 'security check', reason: 'Security Check Required' },
                    { pattern: 'security verification', reason: 'Security Verification' },
                    { pattern: 'verify you are human', reason: 'Human Verification Required' },
                    { pattern: 'are you a robot', reason: 'Robot Check' },
                    { pattern: 'prove you are human', reason: 'Human Verification' },
                    { pattern: 'captcha', reason: 'CAPTCHA Required' },
                    { pattern: 'rate limit', reason: 'Rate Limited' },
                    { pattern: 'too many requests', reason: 'Too Many Requests' },
                    { pattern: 'temporarily blocked', reason: 'Temporarily Blocked' },
                    { pattern: 'temporarily unavailable', reason: 'Temporarily Unavailable' },
                    { pattern: 'account restricted', reason: 'Account Restricted' },
                    { pattern: 'account suspended', reason: 'Account Suspended' },
                    { pattern: 'verify your identity', reason: 'Identity Verification Required' },
                    { pattern: 'complete the security check', reason: 'Security Check Required' },
                    { pattern: 'we need to verify', reason: 'Verification Required' },
                    { pattern: 'unusual sign-in', reason: 'Unusual Sign-in Detected' },
                    { pattern: 'challenge', reason: 'Challenge Required' },
                ];

                // Check URL for checkpoint/challenge patterns
                if (url.includes('checkpoint') || url.includes('challenge') ||
                    url.includes('security') || url.includes('captcha')) {
                    return { blocked: true, reason: 'Security Checkpoint in URL' };
                }

                // Check page content
                for (const {pattern, reason} of blockPatterns) {
                    if (bodyText.includes(pattern) || title.includes(pattern)) {
                        return { blocked: true, reason: reason };
                    }
                }

                // Check for reCAPTCHA or hCaptcha elements
                if (document.querySelector('iframe[src*="recaptcha"]') ||
                    document.querySelector('iframe[src*="hcaptcha"]') ||
                    document.querySelector('.g-recaptcha') ||
                    document.querySelector('.h-captcha') ||
                    document.querySelector('[data-sitekey]')) {
                    return { blocked: true, reason: 'CAPTCHA Widget Detected' };
                }

                return { blocked: false, reason: '' };
            }''')

            if result and result.get('blocked'):
                return (True, result.get('reason', 'Unknown block'))
            return (False, '')

        except Exception as e:
            # If we can't check, assume not blocked
            return (False, '')

    async def _extract_dom_structure(self) -> dict:
        """Extract comprehensive DOM structure for LLM analysis with actionable selectors."""
        try:
            return await self.controller.page.evaluate('''() => {
                const info = {
                    url: window.location.href,
                    title: document.title,
                    ats_type: 'unknown',
                    buttons: [],
                    links: [],
                    form_fields: [],
                    empty_required_fields: [],
                    error_messages: [],
                    headings: [],
                    page_sections: []
                };

                // Detect ATS type
                if (document.querySelector('[data-automation-id]') || window.location.href.includes('workday')) {
                    info.ats_type = 'workday';
                } else if (document.querySelector('[data-qa]') || window.location.href.includes('lever.co')) {
                    info.ats_type = 'lever';
                } else if (document.querySelector('[data-test]') || window.location.href.includes('greenhouse')) {
                    info.ats_type = 'greenhouse';
                } else if (window.location.href.includes('icims')) {
                    info.ats_type = 'icims';
                } else if (window.location.href.includes('taleo') || window.location.href.includes('oracle')) {
                    info.ats_type = 'taleo';
                } else if (window.location.href.includes('smartrecruiters')) {
                    info.ats_type = 'smartrecruiters';
                }

                // Helper to build a reliable CSS selector
                function getSelector(el) {
                    if (el.id) return '#' + el.id;
                    if (el.getAttribute('data-automation-id')) return '[data-automation-id="' + el.getAttribute('data-automation-id') + '"]';
                    if (el.getAttribute('data-qa')) return '[data-qa="' + el.getAttribute('data-qa') + '"]';
                    if (el.getAttribute('data-test')) return '[data-test="' + el.getAttribute('data-test') + '"]';
                    if (el.getAttribute('data-testid')) return '[data-testid="' + el.getAttribute('data-testid') + '"]';
                    if (el.name) return el.tagName.toLowerCase() + '[name="' + el.name + '"]';
                    // Fallback: text-based selector for buttons
                    const text = (el.innerText || el.value || '').trim().slice(0, 30);
                    if (text && (el.tagName === 'BUTTON' || el.tagName === 'A')) {
                        return el.tagName.toLowerCase() + ':has-text("' + text + '")';
                    }
                    return null;
                }

                // Helper to check if element is visible
                function isVisible(el) {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0 &&
                           style.visibility !== 'hidden' &&
                           style.display !== 'none' &&
                           style.opacity !== '0';
                }

                // Get all clickable buttons with selectors
                document.querySelectorAll('button, [role="button"], input[type="submit"], input[type="button"], a.btn, a.button').forEach((el, i) => {
                    if (!isVisible(el)) return;
                    // Skip our bot's pause button - don't let LLM click it!
                    if (el.id === 'bot-pause-btn') return;
                    const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim();
                    if (text && text.length < 100) {
                        const selector = getSelector(el);
                        info.buttons.push({
                            index: i,
                            text: text,
                            selector: selector,
                            disabled: el.disabled || el.getAttribute('aria-disabled') === 'true',
                            classes: el.className.toString().slice(0, 80),
                            type: el.type || 'button'
                        });
                    }
                });

                // Get links that might be navigation/action buttons
                document.querySelectorAll('a[href]').forEach((el, i) => {
                    if (!isVisible(el) || i >= 20) return;
                    const text = (el.innerText || el.getAttribute('aria-label') || '').trim();
                    if (text && text.length > 2 && text.length < 100) {
                        info.links.push({
                            index: i,
                            text: text,
                            href: el.href.slice(0, 100),
                            selector: getSelector(el)
                        });
                    }
                });

                // Get ALL form fields with their current state
                document.querySelectorAll('input, select, textarea').forEach((el, i) => {
                    if (i >= 40) return;
                    const visible = isVisible(el);
                    // Find associated label
                    let label = el.getAttribute('aria-label') || el.placeholder || '';
                    if (!label && el.id) {
                        const labelEl = document.querySelector('label[for="' + el.id + '"]');
                        if (labelEl) label = labelEl.innerText.trim();
                    }
                    if (!label) {
                        // Check parent or sibling for label text
                        const parent = el.closest('div, fieldset, label');
                        if (parent) {
                            const labelEl = parent.querySelector('label, .label, [class*="label"]');
                            if (labelEl) label = labelEl.innerText.trim().slice(0, 50);
                        }
                    }

                    const field = {
                        index: i,
                        type: el.type || el.tagName.toLowerCase(),
                        label: label.slice(0, 60),
                        name: el.name || '',
                        value: (el.value || '').slice(0, 100),
                        required: el.required || el.getAttribute('aria-required') === 'true' || label.includes('*'),
                        disabled: el.disabled || el.readOnly,
                        visible: visible,
                        selector: getSelector(el),
                        hasError: el.classList.contains('error') || el.getAttribute('aria-invalid') === 'true'
                    };

                    info.form_fields.push(field);

                    // Track empty required fields separately
                    if (field.required && !field.value && visible && !field.disabled) {
                        info.empty_required_fields.push({
                            label: field.label,
                            type: field.type,
                            selector: field.selector
                        });
                    }
                });

                // Get error messages
                document.querySelectorAll('[class*="error"], [class*="Error"], [role="alert"], .invalid-feedback, .field-error').forEach((el) => {
                    const text = el.innerText.trim();
                    if (text && text.length > 5 && text.length < 200 && isVisible(el)) {
                        info.error_messages.push(text);
                    }
                });

                // Get headings to understand page context
                document.querySelectorAll('h1, h2, h3').forEach((el, i) => {
                    if (i >= 10) return;
                    const text = el.innerText.trim();
                    if (text) info.headings.push(text.slice(0, 100));
                });

                // Identify major page sections
                document.querySelectorAll('section, [role="main"], form, .form-section, .application-section').forEach((el, i) => {
                    if (i >= 5) return;
                    const heading = el.querySelector('h1, h2, h3, legend, .section-title');
                    if (heading) {
                        info.page_sections.push(heading.innerText.trim().slice(0, 50));
                    }
                });

                return info;
            }''')
        except Exception as e:
            print(f"⚠️ Could not extract DOM structure: {e}")
            return {}

    async def _analyze_screenshot_with_llm(self, screenshot_path: str, question: str = None) -> str:
        """Analyze page DOM using LLM to determine next action.

        Uses comprehensive DOM extraction instead of screenshot vision.
        """
        # Get comprehensive DOM structure
        page_info = await self._extract_dom_structure()
        if not page_info:
            return ""

        # Format buttons with selectors
        buttons_str = "\n".join([
            f"  [{b['index']}] \"{b['text']}\" selector={b.get('selector', 'none')} disabled={b.get('disabled', False)}"
            for b in page_info.get('buttons', [])[:15]
        ]) or "None found"

        # Format form fields with values and required status
        fields_str = "\n".join([
            f"  [{f['index']}] {f['type']} label=\"{f['label']}\" value=\"{f.get('value', '')}\" required={f.get('required', False)} selector={f.get('selector', 'none')}"
            for f in page_info.get('form_fields', [])[:20] if f.get('visible', True)
        ]) or "None found"

        # Format empty required fields
        empty_required_str = "\n".join([
            f"  - {f['label']} ({f['type']}) selector={f.get('selector', 'none')}"
            for f in page_info.get('empty_required_fields', [])
        ]) or "None - all required fields filled"

        # Format error messages
        errors_str = "\n".join(page_info.get('error_messages', [])) or "None"

        # Build analysis prompt with rich DOM info
        analysis_prompt = f"""Analyze this external job application page DOM and tell me what action to take.

PAGE URL: {page_info.get('url', 'unknown')}
PAGE TITLE: {page_info.get('title', 'unknown')}
ATS TYPE: {page_info.get('ats_type', 'unknown')}

HEADINGS:
{chr(10).join(page_info.get('headings', ['None'])[:5])}

PAGE SECTIONS:
{chr(10).join(page_info.get('page_sections', ['None'])[:5])}

BUTTONS (with CSS selectors):
{buttons_str}

FORM FIELDS (with values and selectors):
{fields_str}

EMPTY REQUIRED FIELDS (need to be filled):
{empty_required_str}

ERROR MESSAGES ON PAGE:
{errors_str}

{f"SPECIFIC QUESTION: {question}" if question else ""}

IMPORTANT: Return the EXACT CSS selector for the element to interact with.

Respond with JSON:
{{
    "page_type": "login|application_form|job_listing|confirmation|error",
    "action": "click|fill|select|wait|skip",
    "selector": "exact CSS selector to use",
    "value": "value to type if action is fill, otherwise null",
    "target_button_text": "button text for fallback matching",
    "blocker": "none|login_required|captcha|account_creation|verification_code|error",
    "explanation": "brief explanation of what to do"
}}
"""

        try:
            import httpx
            import json

            api_key = os.getenv("CEREBRAS_API_KEY")
            if not api_key:
                return ""

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "https://api.cerebras.ai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama-3.3-70b",
                        "messages": [
                            {"role": "system", "content": "You are an expert at analyzing web page DOM for job application automation. Return ONLY valid JSON with exact CSS selectors."},
                            {"role": "user", "content": analysis_prompt}
                        ],
                        "temperature": 0.1,
                        "max_tokens": 500
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    if "```" in content:
                        content = content.split("```")[1]
                        if content.startswith("json"):
                            content = content[4:]
                    return content.strip()
        except Exception as e:
            print(f"⚠️ LLM DOM analysis failed: {e}")

        return ""

    async def _execute_llm_action(self, analysis_data: dict) -> bool:
        """Execute the action recommended by LLM DOM analysis.

        Returns True if action was executed successfully.
        """
        if not analysis_data:
            return False

        action = analysis_data.get('action', '')
        selector = analysis_data.get('selector', '')
        value = analysis_data.get('value', '')
        target_text = analysis_data.get('target_button_text', '')

        print(f"   📊 Page: {analysis_data.get('page_type', 'unknown')} | Action: {action}")

        # Check for blockers
        blocker = analysis_data.get('blocker', 'none')
        if blocker and blocker not in ['none', 'null']:
            print(f"   ⚠️ Blocker detected: {blocker}")
            if blocker in ['login_required', 'account_creation', 'captcha', 'verification_code']:
                return False

        if action == 'skip':
            print(f"   ⏭️ LLM suggests skipping: {analysis_data.get('explanation', '')}")
            return False

        if action == 'wait':
            print(f"   ⏳ Waiting for page to update...")
            await asyncio.sleep(3)
            return True

        if action == 'click':
            # Try the CSS selector first
            if selector and selector not in ['none', 'null', '']:
                try:
                    print(f"   🖱️ Clicking selector: {selector[:60]}")
                    el = await self.controller.page.query_selector(selector)
                    if el:
                        await el.click()
                        print(f"   ✅ Clicked via selector")
                        await asyncio.sleep(2)
                        return True
                except Exception as e:
                    print(f"   ⚠️ Selector click failed: {e}")

            # Fallback to text-based matching
            if target_text:
                print(f"   🔄 Falling back to text match: '{target_text}'")
                btn = await self.controller.page.query_selector(
                    f'button:has-text("{target_text}"), '
                    f'a:has-text("{target_text}"), '
                    f'[role="button"]:has-text("{target_text}"), '
                    f'input[type="submit"][value*="{target_text}" i]'
                )
                if btn:
                    await btn.click()
                    print(f"   ✅ Clicked via text match")
                    await asyncio.sleep(2)
                    return True

                # Try partial match
                btns = await self.controller.page.query_selector_all('button, a, [role="button"]')
                for btn in btns:
                    try:
                        btn_text = await btn.inner_text()
                        if target_text.lower() in btn_text.lower():
                            await btn.click()
                            print(f"   ✅ Clicked via partial match: '{btn_text[:40]}'")
                            await asyncio.sleep(2)
                            return True
                    except:
                        continue

            print(f"   ⚠️ Could not find element to click")
            return False

        if action == 'fill':
            if selector and value:
                try:
                    print(f"   ⌨️ Filling field: {selector[:40]} with '{value[:30]}'")
                    el = await self.controller.page.query_selector(selector)
                    if el:
                        await el.fill(value)
                        print(f"   ✅ Filled field")
                        await asyncio.sleep(1)
                        return True
                except Exception as e:
                    print(f"   ⚠️ Fill failed: {e}")
            return False

        if action == 'select':
            if selector and value:
                try:
                    print(f"   📋 Selecting option: '{value}' in {selector[:40]}")
                    el = await self.controller.page.query_selector(selector)
                    if el:
                        await el.select_option(value)
                        print(f"   ✅ Selected option")
                        await asyncio.sleep(1)
                        return True
                except Exception as e:
                    print(f"   ⚠️ Select failed: {e}")
            return False

        return False

    async def _ask_user_for_external_help(self, screenshot_path: str, page_url: str) -> dict:
        """Ask user for help when stuck on an external site."""
        if not self.interactive:
            return {"action": "skip", "value": ""}

        print("\n" + "="*60)
        print("🆘 EXTERNAL SITE - NEED YOUR HELP")
        print("="*60)
        print(f"📍 URL: {page_url[:80]}...")
        print(f"📸 Screenshot saved: {screenshot_path}")
        print()
        print("The bot is unsure what to do on this external site.")
        print()
        print("Options:")
        print("  [1] Tell me what button/link to click (type the text)")
        print("  [2] Skip this application (s)")
        print("  [3] I'll handle it manually - wait 30 seconds (m)")
        print("  [4] Quit interactive mode (q)")
        print()

        try:
            user_input = await self._async_input("Your choice (button text, s, m, or q): ")
            user_input = user_input.strip()

            if user_input.lower() == 's':
                return {"action": "skip", "value": ""}
            elif user_input.lower() == 'm':
                print("⏳ Waiting 30 seconds for your manual intervention...")
                await asyncio.sleep(30)
                return {"action": "continue", "value": ""}
            elif user_input.lower() == 'q':
                self.interactive = False
                return {"action": "skip", "value": ""}
            else:
                # User provided button text to click
                return {"action": "click", "value": user_input}
        except Exception as e:
            print(f"⚠️ Input error: {e}")
            return {"action": "skip", "value": ""}

    def _load_learned_answers(self):
        """Load previously learned answers from disk."""
        learned_file = Path(__file__).parent / "learned_answers.json"
        if learned_file.exists():
            try:
                import json
                with open(learned_file, 'r') as f:
                    LinkedInAgent.learned_answers = json.load(f)
                print(f"📚 Loaded {len(LinkedInAgent.learned_answers)} learned answers")
            except Exception as e:
                print(f"⚠️ Could not load learned answers: {e}")

    def _save_learned_answers(self):
        """Save learned answers to disk for future sessions."""
        learned_file = Path(__file__).parent / "learned_answers.json"
        try:
            import json
            with open(learned_file, 'w') as f:
                json.dump(LinkedInAgent.learned_answers, f, indent=2)
        except Exception as e:
            print(f"⚠️ Could not save learned answers: {e}")

    def _normalize_question(self, question: str) -> str:
        """Normalize a question for matching (lowercase, remove extra spaces)."""
        import re
        return re.sub(r'\s+', ' ', question.lower().strip())

    def _find_learned_answer(self, question: str) -> str:
        """Check if we have a learned answer for this question."""
        normalized = self._normalize_question(question)
        # Exact match
        if normalized in LinkedInAgent.learned_answers:
            return LinkedInAgent.learned_answers[normalized]
        # Partial match (for slight variations in question text)
        for key, value in LinkedInAgent.learned_answers.items():
            if normalized in key or key in normalized:
                return value
        return ""

    # ========== MACHINE LEARNING FROM USER DEMONSTRATIONS ==========

    learned_patterns = {}  # Class-level storage for learned action patterns

    def _load_learned_patterns(self):
        """Load previously learned action patterns from disk."""
        patterns_file = Path(__file__).parent / "learned_patterns.json"
        if patterns_file.exists():
            try:
                import json
                with open(patterns_file, 'r') as f:
                    LinkedInAgent.learned_patterns = json.load(f)
                print(f"🧠 Loaded {len(LinkedInAgent.learned_patterns)} learned patterns")
            except Exception as e:
                print(f"⚠️ Could not load learned patterns: {e}")

    def _save_learned_patterns(self):
        """Save learned action patterns to disk for future sessions."""
        patterns_file = Path(__file__).parent / "learned_patterns.json"
        try:
            import json
            with open(patterns_file, 'w') as f:
                json.dump(LinkedInAgent.learned_patterns, f, indent=2)
            print(f"💾 Saved {len(LinkedInAgent.learned_patterns)} learned patterns")
        except Exception as e:
            print(f"⚠️ Could not save learned patterns: {e}")

    def _generate_pattern_key(self, dom_info: dict) -> str:
        """Generate a unique key for a DOM pattern based on key features."""
        import hashlib

        # Extract key features that identify this situation
        features = []

        # ATS type is important
        ats_type = dom_info.get('ats_type', 'unknown')
        features.append(f"ats:{ats_type}")

        # URL pattern (domain + path pattern)
        url = dom_info.get('url', '')
        if url:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')
            # Simplify path to pattern (remove IDs, keep structure)
            import re
            path_pattern = re.sub(r'/[a-f0-9-]{20,}', '/{id}', parsed.path)
            path_pattern = re.sub(r'/\d+', '/{num}', path_pattern)
            features.append(f"url:{domain}{path_pattern}")

        # Headings (normalized)
        headings = dom_info.get('headings', [])[:3]
        for h in headings:
            normalized_heading = h.lower().strip()[:50]
            features.append(f"h:{normalized_heading}")

        # Error messages present
        errors = dom_info.get('error_messages', [])
        if errors:
            for e in errors[:2]:
                features.append(f"err:{e.lower()[:30]}")

        # Empty required fields
        empty_required = dom_info.get('empty_required_fields', [])
        for f in empty_required[:5]:
            label = f.get('label', '').lower()[:30]
            field_type = f.get('type', 'text')
            features.append(f"req:{field_type}:{label}")

        # Create a hash of the features
        feature_str = "|".join(sorted(features))
        pattern_hash = hashlib.md5(feature_str.encode()).hexdigest()[:12]

        return f"{ats_type}_{pattern_hash}"

    def _find_matching_pattern(self, dom_info: dict) -> dict:
        """Find a previously learned pattern that matches the current situation."""
        if not LinkedInAgent.learned_patterns:
            return None

        current_key = self._generate_pattern_key(dom_info)

        # Exact match
        if current_key in LinkedInAgent.learned_patterns:
            print(f"🎯 Found exact pattern match: {current_key}")
            return LinkedInAgent.learned_patterns[current_key]

        # Fuzzy matching based on features
        current_ats = dom_info.get('ats_type', 'unknown')
        current_headings = set(h.lower().strip() for h in dom_info.get('headings', []))
        current_errors = set(e.lower()[:30] for e in dom_info.get('error_messages', []))

        best_match = None
        best_score = 0

        for pattern_key, pattern_data in LinkedInAgent.learned_patterns.items():
            score = 0
            stored_dom = pattern_data.get('dom_state', {})

            # ATS type match (high weight)
            if stored_dom.get('ats_type') == current_ats:
                score += 30

            # Heading similarity
            stored_headings = set(h.lower().strip() for h in stored_dom.get('headings', []))
            heading_overlap = len(current_headings & stored_headings)
            score += heading_overlap * 15

            # Error message similarity
            stored_errors = set(e.lower()[:30] for e in stored_dom.get('error_messages', []))
            error_overlap = len(current_errors & stored_errors)
            score += error_overlap * 20

            # Empty required fields similarity
            current_req = set(f.get('label', '').lower() for f in dom_info.get('empty_required_fields', []))
            stored_req = set(f.get('label', '').lower() for f in stored_dom.get('empty_required_fields', []))
            req_overlap = len(current_req & stored_req)
            score += req_overlap * 10

            if score > best_score and score >= 30:  # Minimum threshold
                best_score = score
                best_match = pattern_data

        if best_match:
            print(f"🔍 Found fuzzy pattern match (score: {best_score})")
            return best_match

        return None

    def _store_learned_pattern(self, dom_info: dict, user_actions: list):
        """Store a new pattern learned from user demonstration."""
        if not user_actions:
            return

        pattern_key = self._generate_pattern_key(dom_info)

        # Convert user actions to replayable format
        actions_to_store = []
        for action in user_actions:
            action_data = {
                "type": action.get('type', 'click'),
                "selector": self._build_selector_from_action(action),
                "text": action.get('text', ''),
                "value": action.get('value', ''),
            }
            actions_to_store.append(action_data)

        pattern = {
            "dom_state": {
                "ats_type": dom_info.get('ats_type', 'unknown'),
                "headings": dom_info.get('headings', [])[:5],
                "error_messages": dom_info.get('error_messages', [])[:3],
                "empty_required_fields": dom_info.get('empty_required_fields', [])[:5],
                "url_pattern": self._extract_url_pattern(dom_info.get('url', '')),
            },
            "actions": actions_to_store,
            "times_used": 0,
            "success_count": 0,
        }

        LinkedInAgent.learned_patterns[pattern_key] = pattern
        self._save_learned_patterns()

        print(f"🧠 Learned new pattern: {pattern_key}")
        print(f"   Actions: {len(actions_to_store)}")
        for a in actions_to_store[:3]:
            print(f"   - {a['type']}: {a.get('text', a.get('selector', ''))[:40]}")

    def _build_selector_from_action(self, action: dict) -> str:
        """Build a CSS selector from a captured user action."""
        # Priority: id > name > data attributes > class + text
        if action.get('id'):
            return f"#{action['id']}"

        if action.get('dataAutomationId'):
            return f"[data-automation-id=\"{action['dataAutomationId']}\"]"

        if action.get('name'):
            tag = action.get('tag', '*').lower()
            return f"{tag}[name=\"{action['name']}\"]"

        if action.get('text'):
            tag = action.get('tag', 'button').lower()
            text = action['text'][:30]
            return f"{tag}:has-text(\"{text}\")"

        return ""

    def _extract_url_pattern(self, url: str) -> str:
        """Extract a generalizable URL pattern."""
        if not url:
            return ""
        from urllib.parse import urlparse
        import re
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        path = re.sub(r'/[a-f0-9-]{20,}', '/{id}', parsed.path)
        path = re.sub(r'/\d+', '/{num}', path)
        return f"{domain}{path}"

    async def _async_input(self, prompt: str) -> str:
        """Get user input asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: input(prompt))

    async def _ask_user_for_answer(self, question: str, answer_type: str, options: list = None) -> str:
        """Prompt user for answer to a question they haven't seen before.

        Args:
            question: The question text from the form
            answer_type: One of "text", "yes_no", or "dropdown"
            options: Available options for dropdown/radio questions

        Returns:
            User's answer, or empty string to fall back to LLM
        """
        if not self.interactive:
            return ""

        print("\n" + "="*60)
        print("🤔 UNKNOWN QUESTION - YOUR INPUT NEEDED")
        print("="*60)
        print(f"📋 Question: {question}")

        if answer_type == "yes_no":
            print("📝 Type: Yes/No question")
            print("\nOptions:")
            print("  [y] Yes")
            print("  [n] No")
            print("  [s] Skip (let LLM decide)")
            print("  [q] Skip all (disable interactive mode for this session)")

            response = await self._async_input("\n👉 Your choice (y/n/s/q): ")
            response = response.strip().lower()

            if response == 'q':
                self.interactive = False
                print("🤖 Interactive mode disabled. LLM will handle remaining questions.")
                return ""
            elif response == 's':
                return ""
            elif response in ['y', 'yes']:
                answer = "yes"
            elif response in ['n', 'no']:
                answer = "no"
            else:
                return ""

        elif answer_type == "dropdown" and options:
            print("📝 Type: Multiple choice")
            print("\nOptions:")
            for i, opt in enumerate(options, 1):
                print(f"  [{i}] {opt}")
            print(f"  [s] Skip (let LLM decide)")
            print(f"  [q] Skip all (disable interactive mode)")

            response = await self._async_input(f"\n👉 Your choice (1-{len(options)}/s/q): ")
            response = response.strip().lower()

            if response == 'q':
                self.interactive = False
                print("🤖 Interactive mode disabled. LLM will handle remaining questions.")
                return ""
            elif response == 's':
                return ""
            elif response.isdigit() and 1 <= int(response) <= len(options):
                answer = options[int(response) - 1]
            else:
                # Maybe they typed the option text directly
                for opt in options:
                    if response in opt.lower():
                        answer = opt
                        break
                else:
                    return ""
        else:
            # Text input
            print("📝 Type: Text input")
            print("\nEnter your answer (or press Enter to let LLM decide, 'q' to disable interactive mode):")

            response = await self._async_input("\n👉 Your answer: ")
            response = response.strip()

            if response.lower() == 'q':
                self.interactive = False
                print("🤖 Interactive mode disabled. LLM will handle remaining questions.")
                return ""
            elif not response:
                return ""
            else:
                answer = response

        # Remember this answer for future similar questions
        if answer:
            normalized = self._normalize_question(question)
            LinkedInAgent.learned_answers[normalized] = answer
            self._save_learned_answers()
            print(f"✅ Answer saved! Will reuse for similar questions.")

        print("="*60 + "\n")
        return answer

    async def _extract_job_details(self) -> dict:
        """Extract job title, company, and description from the current job page."""
        try:
            job_details = await self.controller.page.evaluate('''() => {
                const title = document.querySelector('.job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title, h1')?.innerText?.trim() || '';
                const company = document.querySelector('.job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name, a[data-tracking-control-name="public_jobs_topcard-org-name"]')?.innerText?.trim() || '';
                const description = document.querySelector('.jobs-description__content, .jobs-box__html-content, #job-details')?.innerText?.trim() || '';
                return { title, company, description };
            }''')

            self.current_job_title = job_details.get('title', '')
            self.current_company = job_details.get('company', '')
            self.current_job_description = job_details.get('description', '')[:5000]  # Limit size

            print(f"📋 Job: {self.current_job_title} at {self.current_company}")
            return job_details
        except Exception as e:
            print(f"⚠️ Could not extract job details: {e}")
            return {}

    async def _generate_customized_resume(self) -> str:
        """Generate a customized resume based on the job description."""
        if not self.current_job_description:
            print("⚠️ No job description available, using default resume")
            return None

        try:
            from generate_resume import load_resume, get_structured_resume, generate_pdf

            print("📝 Customizing resume for this job...")

            # Load base resume
            resume_content = load_resume()
            if not resume_content:
                print("⚠️ Could not load resume")
                return None

            # Generate customized resume
            data = get_structured_resume(
                self.current_job_title,
                self.current_company,
                self.current_job_description,
                resume_content[:8000]
            )

            if not data:
                print("⚠️ Could not generate customized resume")
                return None

            # Save PDF
            output_dir = Path(__file__).parent / 'output'
            output_dir.mkdir(exist_ok=True)

            safe_company = self.current_company.lower().replace(' ', '_').replace('.', '')[:20]
            pdf_path = str(output_dir / f"resume_{safe_company}.pdf")

            generate_pdf(data, pdf_path)
            self.customized_resume_path = pdf_path

            print(f"✅ Custom resume generated: {pdf_path}")
            return pdf_path

        except Exception as e:
            print(f"⚠️ Resume customization failed: {e}")
            return None

    async def _upload_resume(self) -> bool:
        """Upload the customized resume if available."""
        resume_path = self.customized_resume_path
        if not resume_path or not Path(resume_path).exists():
            # Try to find any existing resume in local resumes folder
            default_resume = Path(__file__).parent / 'resumes' / 'mkasim_fullstack-resume.pdf'
            if default_resume.exists():
                resume_path = str(default_resume)
            else:
                print("⚠️ No resume available to upload")
                return False

        try:
            # Find file input for resume upload
            file_input = await self.controller.page.query_selector('input[type="file"]')
            if file_input:
                await file_input.set_input_files(resume_path)
                await asyncio.sleep(1)
                print(f"📎 Uploaded resume: {Path(resume_path).name}")
                return True
        except Exception as e:
            print(f"⚠️ Resume upload failed: {e}")
        return False

    async def _setup_user_action_listener(self):
        """Set up JavaScript listeners to capture user actions in the browser for ML learning."""
        await self.controller.page.evaluate('''() => {
            window._userActions = [];

            // Helper to build best possible selector for an element
            function getBestSelector(el) {
                if (el.id) return '#' + el.id;
                if (el.getAttribute('data-automation-id')) return '[data-automation-id="' + el.getAttribute('data-automation-id') + '"]';
                if (el.getAttribute('data-qa')) return '[data-qa="' + el.getAttribute('data-qa') + '"]';
                if (el.getAttribute('data-testid')) return '[data-testid="' + el.getAttribute('data-testid') + '"]';
                if (el.name) return el.tagName.toLowerCase() + '[name="' + el.name + '"]';
                const text = (el.innerText || '').trim().substring(0, 30);
                if (text) return el.tagName.toLowerCase() + ':has-text("' + text + '")';
                return null;
            }

            // Listen for clicks (but ignore clicks on bot pause button)
            document.addEventListener('click', (e) => {
                const el = e.target;
                // Skip if clicking on the bot's own pause/resume button
                if (el.id === 'bot-pause-btn' || el.closest('#bot-pause-btn')) {
                    console.log('🎯 Ignoring click on bot pause button');
                    return;
                }
                const action = {
                    type: 'click',
                    tag: el.tagName,
                    text: (el.innerText || '').substring(0, 100),
                    id: el.id,
                    className: el.className.toString().substring(0, 100),
                    name: el.getAttribute('name') || '',
                    placeholder: el.getAttribute('placeholder') || '',
                    dataAutomationId: el.getAttribute('data-automation-id') || '',
                    dataQa: el.getAttribute('data-qa') || '',
                    selector: getBestSelector(el),
                    timestamp: Date.now()
                };
                window._userActions.push(action);
                console.log('🎯 User click captured:', action.selector || action.text);
            }, true);

            // Listen for typing
            document.addEventListener('input', (e) => {
                const el = e.target;
                const action = {
                    type: 'type',
                    tag: el.tagName,
                    value: el.value,
                    id: el.id,
                    name: el.getAttribute('name') || '',
                    placeholder: el.getAttribute('placeholder') || '',
                    dataAutomationId: el.getAttribute('data-automation-id') || '',
                    selector: getBestSelector(el),
                    timestamp: Date.now()
                };
                window._userActions.push(action);
                console.log('⌨️ User input captured:', action.selector || action.placeholder);
            }, true);

            // Listen for select changes
            document.addEventListener('change', (e) => {
                const el = e.target;
                if (el.tagName === 'SELECT' || el.tagName === 'INPUT') {
                    const action = {
                        type: el.tagName === 'SELECT' ? 'select' : 'change',
                        tag: el.tagName,
                        value: el.value,
                        selectedText: el.tagName === 'SELECT' ? (el.options[el.selectedIndex]?.text || '') : '',
                        id: el.id,
                        name: el.getAttribute('name') || '',
                        dataAutomationId: el.getAttribute('data-automation-id') || '',
                        selector: getBestSelector(el),
                        timestamp: Date.now()
                    };
                    window._userActions.push(action);
                    console.log('📋 User selection captured:', action.selector || action.value);
                }
            }, true);

            console.log('👁️ User action listener activated - watching and learning!');
        }''')

    async def _setup_overlay_auto_inject(self):
        """Set up automatic re-injection of pause overlay on every page load."""
        try:
            # Add simple script that runs on every page navigation
            init_script = '''
                // This runs on every page load/navigation
                window._botPauseRequested = false;
                window._botResumeRequested = false;
                window._botIsPaused = false;

                function createBotPauseBtn() {
                    if (document.getElementById("bot-pause-btn")) return;
                    if (!document.body) return;

                    var btn = document.createElement("button");
                    btn.id = "bot-pause-btn";
                    btn.textContent = "⏸️ PAUSE";
                    btn.style.cssText = "position:fixed;bottom:10px;right:10px;z-index:2147483647;padding:8px 16px;font-size:12px;font-weight:bold;color:white;background:#e74c3c;border:2px solid #c0392b;border-radius:6px;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,0.3);font-family:Arial,sans-serif;opacity:0.8;";

                    btn.onclick = function() {
                        if (!window._botIsPaused) {
                            window._botPauseRequested = true;
                            btn.textContent = "⏳ PAUSING...";
                            btn.style.background = "#f39c12";
                        } else {
                            window._botResumeRequested = true;
                            btn.textContent = "▶️ RESUMING...";
                            btn.style.background = "#3498db";
                        }
                    };

                    document.body.appendChild(btn);
                }

                // Create when DOM ready
                if (document.body) {
                    createBotPauseBtn();
                } else {
                    document.addEventListener("DOMContentLoaded", createBotPauseBtn);
                }

                // Re-inject periodically in case removed
                setInterval(function() {
                    if (document.body && !document.getElementById("bot-pause-btn")) {
                        createBotPauseBtn();
                    }
                }, 500);
            '''
            await self.controller.page.add_init_script(init_script)
            print("   🎛️ Pause overlay auto-inject enabled")
        except Exception as e:
            print(f"   ⚠️ Could not setup auto-inject: {str(e)[:80]}")

    async def _inject_pause_overlay(self):
        """Inject a floating pause button overlay using a simple div button.
        Falls back to simplest approach for maximum compatibility.
        """
        try:
            js_code = '''() => {
                // Global flags for pause/resume
                if (typeof window._botPauseRequested === "undefined") window._botPauseRequested = false;
                if (typeof window._botResumeRequested === "undefined") window._botResumeRequested = false;
                if (typeof window._botIsPaused === "undefined") window._botIsPaused = false;

                // Skip if button already exists (created by auto-inject)
                if (document.getElementById("bot-pause-btn")) {
                    return "button already exists";
                }

                // Create a simple button (bottom-right, smaller to avoid interfering with forms)
                var btn = document.createElement("button");
                btn.id = "bot-pause-btn";
                btn.textContent = "⏸️ PAUSE";
                btn.style.cssText = "position:fixed;bottom:10px;right:10px;z-index:2147483647;padding:8px 16px;font-size:12px;font-weight:bold;color:white;background:#e74c3c;border:2px solid #c0392b;border-radius:6px;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,0.3);font-family:Arial,sans-serif;opacity:0.8;";

                btn.onclick = function() {
                    if (!window._botIsPaused) {
                        window._botPauseRequested = true;
                        btn.textContent = "⏳ PAUSING...";
                        btn.style.background = "#f39c12";
                    } else {
                        window._botResumeRequested = true;
                        btn.textContent = "▶️ RESUMING...";
                        btn.style.background = "#3498db";
                    }
                };

                document.body.appendChild(btn);

                // Re-inject if removed
                setInterval(function() {
                    if (!document.getElementById("bot-pause-btn") && document.body) {
                        document.body.appendChild(btn);
                    }
                }, 500);

                return "button injected";
            }'''
            result = await self.controller.page.evaluate(js_code)
            print(f"   🎛️ Pause overlay: {result}")
        except Exception as e:
            print(f"   ⚠️ Could not inject overlay: {str(e)[:80]}")

    async def _update_pause_overlay_state(self, paused: bool, message: str = ""):
        """Update the pause overlay button state."""
        try:
            js_code = '''(args) => {
                window._botIsPaused = args.paused;
                window._botPauseRequested = false;
                window._botResumeRequested = false;

                // Update button text and color
                var btn = document.getElementById("bot-pause-btn");
                if (btn) {
                    if (args.paused) {
                        btn.textContent = "▶️ RESUME";
                        btn.style.background = "#27ae60";
                        btn.style.opacity = "1";
                    } else {
                        btn.textContent = "⏸️ PAUSE";
                        btn.style.background = "#e74c3c";
                        btn.style.opacity = "0.8";
                    }
                }
            }'''
            await self.controller.page.evaluate(js_code, {"paused": paused, "message": message})
        except:
            pass

    async def _check_pause_overlay_clicked(self) -> bool:
        """Check if user clicked the pause overlay button."""
        try:
            return await self.controller.page.evaluate('() => window._botPauseRequested === true')
        except:
            return False

    async def _check_resume_overlay_clicked(self) -> bool:
        """Check if user clicked the resume button."""
        try:
            return await self.controller.page.evaluate('() => window._botResumeRequested === true')
        except:
            return False

    async def _get_user_actions(self):
        """Get user actions captured since last check."""
        try:
            actions = await self.controller.page.evaluate('() => { const a = window._userActions || []; window._userActions = []; return a; }')
            return actions
        except:
            return []

    async def _pause_for_user_intervention(self, reason: str, pause_seconds: int = 30) -> list:
        """Pause and let user intervene, then capture and learn from their actions."""
        print(f"\n🛑 PAUSED: {reason}")
        print(f"⏸️  You have {pause_seconds} seconds to handle this...")
        print("   🧠 The bot is WATCHING and will LEARN from your actions!")
        print()

        # Capture DOM state BEFORE user interaction
        dom_before = await self._extract_dom_structure()

        # Set up action listener if not already done
        await self._setup_user_action_listener()

        # Clear any previous user actions
        await self._get_user_actions()

        # Wait and let user interact
        await asyncio.sleep(pause_seconds)

        # Capture what user did
        user_actions = await self._get_user_actions()

        if user_actions:
            print(f"\n👀 Observed {len(user_actions)} user action(s):")
            for action in user_actions:
                selector = action.get('selector', '')
                if action['type'] == 'click':
                    print(f"   🖱️ Click: {action.get('text', '')[:40]} | selector: {selector}")
                elif action['type'] == 'type':
                    print(f"   ⌨️ Type: '{action.get('value', '')[:20]}' | selector: {selector}")
                elif action['type'] == 'select':
                    print(f"   📋 Select: '{action.get('selectedText', '')}' | selector: {selector}")

            # LEARN: Store this pattern for future use
            self._store_learned_pattern(dom_before, user_actions)

            # Also store in session memory
            self.user_interventions.append({
                "reason": reason,
                "actions": user_actions,
                "page_url": self.controller.page.url,
                "dom_state": dom_before
            })
            print("\n✅ Pattern learned and saved! Will auto-apply to similar situations.")
        else:
            print("   (No user actions detected)")

        return user_actions

    async def _check_user_intervention_request(self) -> bool:
        """Check if user requested intervention (keyboard or overlay button).

        Returns True if user intervened, False otherwise.
        """
        global _user_wants_control

        # Check both keyboard shortcut and overlay button
        keyboard_request = _user_wants_control.is_set()
        overlay_request = await self._check_pause_overlay_clicked()

        if keyboard_request or overlay_request:
            # Reset flags
            if keyboard_request:
                _user_wants_control.clear()

            source = "keyboard shortcut" if keyboard_request else "pause button"

            print("\n" + "="*60)
            print("🖐️  USER INTERVENTION MODE")
            print("="*60)
            print(f"You requested control via {source}. Bot is now paused.")
            print("🧠 I'm watching your actions and will LEARN from them!")
            print()
            print("Options:")
            print("  • Interact with the browser to show me what to do")
            print("  • Click the ▶️ RESUME button in the browser when done")
            print("  • Or press ENTER in this terminal")
            print("="*60)

            # Capture DOM state BEFORE user interaction
            dom_before = await self._extract_dom_structure()

            # Set up action listener if not already done
            await self._setup_user_action_listener()

            # Clear any previous user actions
            await self._get_user_actions()

            # Update overlay to show "RESUME" button
            await self._update_pause_overlay_state(True, "🧠 Bot is watching... Click RESUME when done")

            # Wait for user to click Resume button OR press Enter in terminal
            print("\n⏸️  Waiting for you to interact and click RESUME or press ENTER...")

            while True:
                # Check if resume button was clicked
                if await self._check_resume_overlay_clicked():
                    print("   ▶️ Resume button clicked!")
                    break

                # Also check for Enter key (non-blocking would be complex, so we poll)
                await asyncio.sleep(0.5)

                # After 5 minutes, auto-resume
                # (We'll implement a simple timeout check via overlay)
                try:
                    # Check if the page still exists
                    _ = self.controller.page.url
                except:
                    print("   ⚠️ Page closed, resuming...")
                    break

            # Capture what user did
            user_actions = await self._get_user_actions()

            # Reset overlay state
            await self._update_pause_overlay_state(False)

            if user_actions:
                print(f"\n👀 Observed {len(user_actions)} user action(s):")
                for action in user_actions:
                    selector = action.get('selector', '')
                    if action['type'] == 'click':
                        print(f"   🖱️ Click: {action.get('text', '')[:40]} | selector: {selector}")
                    elif action['type'] == 'type':
                        print(f"   ⌨️ Type: '{action.get('value', '')[:20]}' | selector: {selector}")
                    elif action['type'] == 'select':
                        print(f"   📋 Select: '{action.get('selectedText', '')}' | selector: {selector}")

                # LEARN: Store this pattern for future use
                self._store_learned_pattern(dom_before, user_actions)

                # Also store in session memory
                self.user_interventions.append({
                    "reason": f"User requested intervention via {source}",
                    "actions": user_actions,
                    "page_url": self.controller.page.url,
                    "dom_state": dom_before
                })
                print("\n✅ Pattern learned and saved! Will auto-apply to similar situations.")
            else:
                print("   (No user actions detected)")

            print("\n▶️  Resuming automation...")
            return True

        return False

    async def _try_learned_pattern(self, dom_info: dict) -> bool:
        """Try to apply a previously learned pattern to the current situation.

        Returns True if a pattern was found and successfully applied.
        """
        pattern = self._find_matching_pattern(dom_info)
        if not pattern:
            return False

        actions = pattern.get('actions', [])
        if not actions:
            return False

        print(f"\n🧠 APPLYING LEARNED PATTERN ({len(actions)} actions)...")

        success = True
        for action in actions:
            try:
                action_type = action.get('type', 'click')
                selector = action.get('selector', '')
                value = action.get('value', '')
                text = action.get('text', '')

                if not selector:
                    # Try to build selector from text
                    if text:
                        selector = f'button:has-text("{text}"), a:has-text("{text}"), [role="button"]:has-text("{text}")'

                if not selector:
                    print(f"   ⚠️ No selector for action: {action_type}")
                    continue

                el = await self.controller.page.query_selector(selector)
                if not el:
                    # Try partial text match
                    if text:
                        els = await self.controller.page.query_selector_all('button, a, [role="button"], input[type="submit"]')
                        for e in els:
                            try:
                                el_text = await e.inner_text()
                                if text.lower() in el_text.lower():
                                    el = e
                                    break
                            except:
                                continue

                if not el:
                    print(f"   ⚠️ Element not found: {selector[:50]}")
                    continue

                if action_type == 'click':
                    await el.click()
                    print(f"   ✅ Clicked: {text or selector[:40]}")
                elif action_type == 'type':
                    await el.fill(value)
                    print(f"   ✅ Typed: {value[:20]}")
                elif action_type == 'select':
                    await el.select_option(value)
                    print(f"   ✅ Selected: {value}")

                await asyncio.sleep(1)

            except Exception as e:
                print(f"   ⚠️ Action failed: {e}")
                success = False

        if success:
            # Update success count
            pattern_key = self._generate_pattern_key(dom_info)
            if pattern_key in LinkedInAgent.learned_patterns:
                LinkedInAgent.learned_patterns[pattern_key]['times_used'] += 1
                LinkedInAgent.learned_patterns[pattern_key]['success_count'] += 1
                self._save_learned_patterns()
            print("   🎉 Learned pattern applied successfully!")

        return success

    async def _scroll_modal_to_element(self, element) -> None:
        """Scroll the modal container to make the element visible."""
        try:
            # Find the modal container (LinkedIn Easy Apply modal)
            modal_selectors = [
                '.jobs-easy-apply-modal',
                '.jobs-easy-apply-content',
                '.artdeco-modal__content',
                '[role="dialog"] .artdeco-modal__content',
                '.jobs-apply-modal__content',
                '.fb-dashboard-pages'
            ]

            modal = None
            for selector in modal_selectors:
                modal = await self.controller.page.query_selector(selector)
                if modal:
                    break

            if modal:
                # Scroll the element into view within the modal
                await element.evaluate('''(el) => {
                    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }''')
                await asyncio.sleep(0.3)
            else:
                # Fallback: just scroll element into view in the page
                await element.scroll_into_view_if_needed()
                await asyncio.sleep(0.2)
        except Exception as e:
            # Silently fail - scrolling is best effort
            pass

    async def _close_extra_tabs(self, keep_page) -> None:
        """Close all tabs except the one we want to keep (usually LinkedIn)."""
        try:
            all_pages = self.controller.context.pages
            for page in all_pages:
                if page != keep_page:
                    try:
                        await page.close()
                        print("   📑 Closed external tab")
                    except:
                        pass
            # Switch back to the kept page
            self.controller.page = keep_page
            await keep_page.bring_to_front()
        except Exception as e:
            # Fallback: just try to switch to keep_page
            try:
                self.controller.page = keep_page
                await keep_page.bring_to_front()
            except:
                pass

    async def _fill_all_eeo_dropdowns(self) -> bool:
        """Fill all EEO (Equal Employment Opportunity) dropdowns at once."""
        filled_any = False

        # First, scroll down within the modal to reveal all fields
        try:
            modal = await self.controller.page.query_selector('.jobs-easy-apply-content, .artdeco-modal__content, .fb-dashboard-pages')
            if modal:
                # Scroll to bottom of modal first to load all content
                await modal.evaluate('(el) => el.scrollTop = el.scrollHeight')
                await asyncio.sleep(0.5)
                # Then scroll back to top
                await modal.evaluate('(el) => el.scrollTop = 0')
                await asyncio.sleep(0.3)
        except Exception:
            pass

        # Get all select elements on the page
        selects = await self.controller.page.query_selector_all('select')
        print(f"   📋 Found {len(selects)} select elements")

        for i, select in enumerate(selects):
            try:
                # Scroll to make the dropdown visible within the modal
                await self._scroll_modal_to_element(select)

                # Get the label/name of this dropdown
                name = await select.get_attribute('name') or ''
                aria_label = await select.get_attribute('aria-label') or ''

                # Also try to get the associated label element
                select_id = await select.get_attribute('id') or ''
                label_el = None
                if select_id:
                    label_el = await self.controller.page.query_selector(f'label[for="{select_id}"]')
                if label_el:
                    label_from_el = await label_el.inner_text()
                else:
                    label_from_el = ''

                label_text = f"{name} {aria_label} {label_from_el}"
                label_lower = label_text.lower()

                # Get current selected value
                current_value = await select.evaluate('(el) => el.options[el.selectedIndex]?.text || ""')
                print(f"   📋 Select {i}: label='{label_text[:50]}', current='{current_value}'")

                # Skip if already has a real value selected
                if current_value and current_value != "Select an option":
                    print(f"   ⏭️ Skipping - already has value")
                    continue

                # Get all options to help identify the dropdown type
                options = await select.evaluate('''(el) => {
                    return Array.from(el.options).map(o => o.text.toLowerCase());
                }''')
                options_text = ' '.join(options)

                # Determine what to select based on the label OR the options
                value_to_select = None

                if 'gender' in label_lower or 'sex' in label_lower or ('male' in options_text and 'female' in options_text):
                    value_to_select = 'Male'
                elif 'lgbtq' in label_lower or 'sexual' in label_lower or 'lgbtq' in options_text:
                    value_to_select = 'No, I do not identify'  # Partial match for LGBTQIA+
                elif 'race' in label_lower or 'ethnic' in label_lower:
                    value_to_select = 'Asian'
                elif ('veteran' in label_lower and 'spouse' not in label_lower) or ('i am not a veteran' in options_text):
                    value_to_select = 'I am not a veteran'
                elif 'spouse' in label_lower or 'domestic partner' in label_lower:
                    value_to_select = 'No'  # Not a military spouse
                elif 'reserves' in label_lower:
                    value_to_select = 'No'  # Not in reserves
                elif 'disability' in label_lower or 'disabilities' in label_lower or 'have a disability' in options_text:
                    value_to_select = 'No'
                elif 'hispanic' in label_lower or 'latino' in label_lower:
                    value_to_select = 'No'
                else:
                    print(f"   ⏭️ No matching rule for this dropdown (options: {options[:3]}...)")

                if value_to_select:
                    try:
                        # Try to select by label (visible text)
                        await select.select_option(label=value_to_select, timeout=3000)
                        print(f"   ✅ EEO: Selected '{value_to_select}'")
                        filled_any = True
                    except Exception as e:
                        print(f"   ⚠️ Direct select failed, trying keyboard navigation...")
                        # Get all options with their indices
                        options = await select.evaluate('''(el) => {
                            return Array.from(el.options).map((o, i) => ({value: o.value, text: o.text, index: i}));
                        }''')
                        print(f"   📋 Available options: {[o['text'] for o in options]}")

                        # Find target option index
                        target_index = -1
                        for opt in options:
                            if value_to_select.lower() in opt['text'].lower():
                                target_index = opt['index']
                                break

                        if target_index >= 0:
                            # Use keyboard navigation: focus, then arrow keys
                            await select.focus()
                            await asyncio.sleep(0.2)

                            # Press Home to go to first option
                            await self.controller.page.keyboard.press('Home')
                            await asyncio.sleep(0.1)

                            # Navigate down to target
                            for _ in range(target_index):
                                await self.controller.page.keyboard.press('ArrowDown')
                                await asyncio.sleep(0.05)

                            # Confirm selection with Enter or Space
                            await self.controller.page.keyboard.press('Enter')
                            print(f"   ✅ EEO: Selected '{options[target_index]['text']}' (keyboard)")
                            filled_any = True
                        else:
                            # Last resort: try direct value selection
                            for opt in options:
                                if value_to_select.lower() in opt['text'].lower():
                                    try:
                                        await select.select_option(value=opt['value'], timeout=3000)
                                        print(f"   ✅ EEO: Selected '{opt['text']}' (partial match)")
                                        filled_any = True
                                        break
                                    except:
                                        pass
            except Exception as e:
                print(f"   ⚠️ Error processing select {i}: {e}")

        # Also handle checkboxes (acknowledgment checkboxes and race/ethnicity on EEO pages)
        try:
            checkboxes = await self.controller.page.query_selector_all('input[type="checkbox"]')
            print(f"   📋 Found {len(checkboxes)} checkboxes")
            asian_checked = False
            for i, checkbox in enumerate(checkboxes):
                try:
                    # Scroll to make checkbox visible before interacting
                    await self._scroll_modal_to_element(checkbox)

                    is_checked = await checkbox.is_checked()
                    if not is_checked:
                        # Get label for this checkbox
                        checkbox_id = await checkbox.get_attribute('id') or ''
                        label_el = None
                        if checkbox_id:
                            label_el = await self.controller.page.query_selector(f'label[for="{checkbox_id}"]')
                        label_text = ''
                        if label_el:
                            label_text = await label_el.inner_text()

                        label_lower = label_text.lower().strip()

                        # Check if it's an acknowledgment or consent checkbox
                        if any(kw in label_lower for kw in ['acknowledge', 'agree', 'consent', 'confirm', 'understand', 'certify', 'read']):
                            try:
                                await checkbox.check(timeout=3000, force=True)
                                print(f"   ✅ Checked acknowledgment checkbox: {label_text[:50]}")
                                filled_any = True
                            except Exception as e:
                                print(f"   ⚠️ Failed to check acknowledgment: {e}")
                        # Check if it's the Asian race checkbox (only check one race)
                        elif 'asian' in label_lower and not asian_checked:
                            try:
                                await checkbox.check(timeout=3000, force=True)
                                print(f"   ✅ Checked Asian race checkbox")
                                filled_any = True
                                asian_checked = True
                            except Exception as e:
                                print(f"   ⚠️ Failed to check Asian: {e}")
                        else:
                            # Only print first 7 to avoid spam
                            if i < 7:
                                print(f"   📋 Checkbox {i}: '{label_text[:50]}' (not checked)")
                except Exception as e:
                    print(f"   ⚠️ Error with checkbox {i}: {e}")
        except Exception as e:
            print(f"   ⚠️ Error finding checkboxes: {e}")

        # Handle Race/Ethnicity which might be a fieldset with checkboxes or radio buttons
        try:
            # Look for race/ethnicity fieldsets or groups
            race_fieldsets = await self.controller.page.query_selector_all('fieldset, [role="group"]')
            for fieldset in race_fieldsets:
                fieldset_text = await fieldset.inner_text()
                if 'race' in fieldset_text.lower() or 'ethnic' in fieldset_text.lower():
                    print(f"   📋 Found race/ethnicity fieldset")
                    # Scroll to make fieldset visible
                    await self._scroll_modal_to_element(fieldset)

                    # Find Asian checkbox/radio within this fieldset
                    asian_option = await fieldset.query_selector('input[value*="Asian" i], label:has-text("Asian") input, input + label:has-text("Asian")')
                    if asian_option:
                        await self._scroll_modal_to_element(asian_option)
                        is_checked = await asian_option.is_checked()
                        if not is_checked:
                            await asian_option.check()
                            print(f"   ✅ Selected Asian for race/ethnicity")
                            filled_any = True
                    else:
                        # Try clicking on label with "Asian"
                        asian_label = await fieldset.query_selector('label:has-text("Asian")')
                        if asian_label:
                            await self._scroll_modal_to_element(asian_label)
                            await asian_label.click()
                            print(f"   ✅ Clicked Asian label for race/ethnicity")
                            filled_any = True
        except Exception as e:
            print(f"   ⚠️ Error handling race fieldset: {e}")

        return filled_any

    async def _fill_additional_questions(self) -> bool:
        """Fill LinkedIn Easy Apply additional questions (text inputs, radios, dropdowns)."""
        filled_any = False
        page = self.controller.page

        print("   📝 Checking for additional questions...")

        # First scroll modal to reveal all fields
        try:
            modal = await page.query_selector('.jobs-easy-apply-content, .artdeco-modal__content')
            if modal:
                await modal.evaluate('(el) => el.scrollTop = el.scrollHeight')
                await asyncio.sleep(0.3)
                await modal.evaluate('(el) => el.scrollTop = 0')
                await asyncio.sleep(0.2)
        except:
            pass

        # Handle text input fields using JavaScript for better reliability
        try:
            filled_inputs = await page.evaluate('''() => {
                const results = [];
                const modal = document.querySelector('.jobs-easy-apply-content, .artdeco-modal__content, [role="dialog"]');
                if (!modal) return results;

                // Find all text inputs in the modal
                const inputs = modal.querySelectorAll('input[type="text"], input[type="number"], input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([type="file"])');

                for (const input of inputs) {
                    if (input.value && input.value.trim() !== '') continue; // Skip filled inputs
                    if (!input.offsetParent) continue; // Skip hidden inputs

                    // Get label text
                    let labelText = '';
                    const label = document.querySelector('label[for="' + input.id + '"]') ||
                                  input.closest('.fb-dash-form-element')?.querySelector('label') ||
                                  input.closest('.artdeco-text-input')?.querySelector('label') ||
                                  input.closest('div')?.querySelector('label');
                    if (label) labelText = label.innerText.toLowerCase();

                    // Also check aria-label and placeholder
                    labelText = labelText || input.getAttribute('aria-label')?.toLowerCase() ||
                                input.getAttribute('placeholder')?.toLowerCase() || '';

                    results.push({
                        id: input.id,
                        name: input.name,
                        label: labelText,
                        selector: input.id ? '#' + input.id : null
                    });
                }
                return results;
            }''')

            print(f"   📋 Found {len(filled_inputs)} empty text inputs")

            for input_info in filled_inputs:
                label = input_info.get('label', '')
                value = self._get_answer_for_question(label)

                # If hardcoded answer not found, check learned answers
                if not value and label:
                    value = self._find_learned_answer(label)
                    if value:
                        print(f"   📚 Using learned answer for: {label[:40]}")

                # If still no answer, ask user (interactive mode) or use LLM
                if not value and label:
                    value = await self._ask_user_for_answer(label, answer_type="text")

                # Final fallback to LLM
                if not value and label:
                    value = await self._get_llm_answer(label, answer_type="text")

                if value:
                    try:
                        selector = input_info.get('selector')
                        if selector:
                            input_el = await page.query_selector(selector)
                        else:
                            input_el = await page.query_selector(f'input[name="{input_info.get("name")}"]')

                        if input_el:
                            await input_el.fill(value)
                            print(f"   ✅ Filled '{label[:40]}' with '{value}'")
                            filled_any = True
                            await asyncio.sleep(0.2)
                    except Exception as e:
                        print(f"   ⚠️ Could not fill input: {e}")

        except Exception as e:
            print(f"   ⚠️ Error filling text inputs: {e}")

        # Handle textarea fields (hiring manager message, cover letter, etc.)
        try:
            textareas = await page.evaluate('''() => {
                const results = [];
                const modal = document.querySelector('.jobs-easy-apply-content, .artdeco-modal__content, [role="dialog"]');
                if (!modal) return results;

                // Find all textareas in the modal
                const areas = modal.querySelectorAll('textarea');

                for (const textarea of areas) {
                    if (textarea.value && textarea.value.trim() !== '') continue; // Skip filled textareas
                    if (!textarea.offsetParent) continue; // Skip hidden textareas

                    // Get label text
                    let labelText = '';
                    const label = document.querySelector('label[for="' + textarea.id + '"]') ||
                                  textarea.closest('.fb-dash-form-element')?.querySelector('label') ||
                                  textarea.closest('.artdeco-text-input')?.querySelector('label') ||
                                  textarea.closest('div')?.querySelector('label, span.t-14');
                    if (label) labelText = label.innerText.toLowerCase();

                    // Also check aria-label and placeholder
                    labelText = labelText || textarea.getAttribute('aria-label')?.toLowerCase() ||
                                textarea.getAttribute('placeholder')?.toLowerCase() || '';

                    results.push({
                        id: textarea.id,
                        name: textarea.name,
                        label: labelText,
                        selector: textarea.id ? '#' + textarea.id : null
                    });
                }
                return results;
            }''')

            if textareas:
                print(f"   📝 Found {len(textareas)} empty textareas")

            for textarea_info in textareas:
                label = textarea_info.get('label', '')

                # Check if this is a hiring manager message field
                is_hiring_manager_msg = any(kw in label for kw in [
                    'hiring manager', 'recruiter', 'message', 'note', 'cover',
                    'why', 'interested', 'additional information', 'tell us'
                ])

                if is_hiring_manager_msg:
                    # Generate personalized message for hiring manager
                    message = await self._generate_hiring_manager_message()
                    if message:
                        try:
                            selector = textarea_info.get('selector')
                            if selector:
                                textarea_el = await page.query_selector(selector)
                            else:
                                textarea_el = await page.query_selector(f'textarea[name="{textarea_info.get("name")}"]')

                            if textarea_el:
                                await textarea_el.fill(message)
                                print(f"   ✅ Filled hiring manager message ({len(message)} chars)")
                                filled_any = True
                                await asyncio.sleep(0.3)
                        except Exception as e:
                            print(f"   ⚠️ Could not fill textarea: {e}")
                else:
                    # For other textareas, use LLM to generate appropriate response
                    value = await self._get_llm_answer(label, answer_type="text")
                    if value:
                        try:
                            selector = textarea_info.get('selector')
                            if selector:
                                textarea_el = await page.query_selector(selector)
                            else:
                                textarea_el = await page.query_selector(f'textarea[name="{textarea_info.get("name")}"]')

                            if textarea_el:
                                await textarea_el.fill(value)
                                print(f"   ✅ Filled textarea '{label[:40]}' with response")
                                filled_any = True
                                await asyncio.sleep(0.2)
                        except Exception as e:
                            print(f"   ⚠️ Could not fill textarea: {e}")

        except Exception as e:
            print(f"   ⚠️ Error filling textareas: {e}")

        # Handle radio buttons (Yes/No questions) using JavaScript
        try:
            radio_groups = await page.evaluate('''() => {
                const results = [];
                const modal = document.querySelector('.jobs-easy-apply-content, .artdeco-modal__content, [role="dialog"]');
                if (!modal) return results;

                // Find all fieldsets with radio buttons
                const fieldsets = modal.querySelectorAll('fieldset');

                for (const fieldset of fieldsets) {
                    // Skip if already has a checked radio
                    if (fieldset.querySelector('input[type="radio"]:checked')) continue;

                    const radios = fieldset.querySelectorAll('input[type="radio"]');
                    if (radios.length < 2) continue;

                    // Get question text
                    const legend = fieldset.querySelector('legend, label, span');
                    const question = legend ? legend.innerText.toLowerCase() : '';

                    // Get radio options
                    const options = [];
                    for (const radio of radios) {
                        const label = radio.nextElementSibling ||
                                      radio.parentElement.querySelector('label') ||
                                      radio.closest('label');
                        const labelText = label ? label.innerText.trim().toLowerCase() : '';
                        options.push({
                            id: radio.id,
                            value: radio.value,
                            label: labelText
                        });
                    }

                    results.push({ question, options });
                }
                return results;
            }''')

            for group in radio_groups:
                question = group.get('question', '')
                options = group.get('options', [])
                option_labels = [opt.get('label', '') for opt in options]

                # Check if this is a simple yes/no question
                is_yes_no = any('yes' in lbl or 'no' in lbl or lbl in ['y', 'n'] for lbl in option_labels)

                if is_yes_no:
                    answer = self._get_yes_no_answer(question)

                    for opt in options:
                        label = opt.get('label', '')
                        if answer == 'yes' and ('yes' in label or label == 'y'):
                            # Use attribute selector [id="..."] instead of #id to handle special chars in LinkedIn IDs
                            opt_id = opt.get('id')
                            radio_el = await page.query_selector(f'[id="{opt_id}"]') if opt_id else None
                            if radio_el:
                                await radio_el.click()
                                print(f"   ✅ Selected 'Yes' for: {question[:40]}")
                                filled_any = True
                                break
                        elif answer == 'no' and ('no' in label or label == 'n'):
                            opt_id = opt.get('id')
                            radio_el = await page.query_selector(f'[id="{opt_id}"]') if opt_id else None
                            if radio_el:
                                await radio_el.click()
                                print(f"   ✅ Selected 'No' for: {question[:40]}")
                                filled_any = True
                                break
                else:
                    # Not a simple yes/no - check learned answers first
                    selected_answer = self._find_learned_answer(question)
                    if selected_answer:
                        print(f"   📚 Using learned answer for: {question[:40]}")

                    # If no learned answer, ask user (interactive mode)
                    if not selected_answer:
                        selected_answer = await self._ask_user_for_answer(question, answer_type="dropdown", options=option_labels)

                    # Final fallback to LLM
                    if not selected_answer:
                        selected_answer = await self._get_llm_answer(question, answer_type="dropdown", options=option_labels)

                    if selected_answer:
                        for opt in options:
                            if selected_answer.lower() in opt.get('label', '').lower() or opt.get('label', '').lower() in selected_answer.lower():
                                opt_id = opt.get('id')
                                radio_el = await page.query_selector(f'[id="{opt_id}"]') if opt_id else None
                                if radio_el:
                                    await radio_el.click()
                                    print(f"   ✅ Selected '{opt.get('label')}' for: {question[:40]}")
                                    filled_any = True
                                    break

        except Exception as e:
            print(f"   ⚠️ Error filling radio buttons: {e}")

        # Handle dropdowns for additional questions
        try:
            selects = await page.query_selector_all('select')
            for select in selects:
                try:
                    # Skip if already has a non-default value selected
                    selected_value = await select.evaluate('(el) => el.value')
                    selected_text = await select.evaluate('(el) => el.options[el.selectedIndex]?.text || ""')
                    if selected_value and selected_text.lower() not in ['select', 'select an option', 'please select', '--', '']:
                        continue

                    # Get label for this select
                    label_text = await select.evaluate('''(el) => {
                        const label = document.querySelector('label[for="' + el.id + '"]') ||
                                     el.closest('.fb-dash-form-element')?.querySelector('label') ||
                                     el.previousElementSibling;
                        return label ? label.innerText.toLowerCase() : '';
                    }''')

                    # Get options
                    options = await select.evaluate('(el) => Array.from(el.options).map(o => ({value: o.value, text: o.text}))')
                    option_texts = [opt['text'] for opt in options if opt['text'].strip()]

                    value_to_select = self._get_dropdown_answer(label_text, options)

                    # If hardcoded answer not found, check learned answers
                    if not value_to_select and label_text:
                        value_to_select = self._find_learned_answer(label_text)
                        if value_to_select:
                            print(f"   📚 Using learned answer for: {label_text[:30]}")

                    # If still no answer, ask user (interactive mode)
                    if not value_to_select and label_text and option_texts:
                        value_to_select = await self._ask_user_for_answer(label_text, answer_type="dropdown", options=option_texts)

                    # Final fallback to LLM
                    if not value_to_select and label_text and option_texts:
                        value_to_select = await self._get_llm_answer(label_text, answer_type="dropdown", options=option_texts)

                    if value_to_select:
                        try:
                            await select.select_option(label=value_to_select)
                            print(f"   ✅ Selected '{value_to_select}' for dropdown: {label_text[:30]}")
                            filled_any = True
                        except:
                            # Try by value or partial match
                            for opt in options:
                                if value_to_select.lower() in opt['text'].lower() or opt['text'].lower() in value_to_select.lower():
                                    await select.select_option(value=opt['value'])
                                    print(f"   ✅ Selected '{opt['text']}' for dropdown")
                                    filled_any = True
                                    break

                except Exception:
                    continue

        except Exception as e:
            print(f"   ⚠️ Error filling dropdowns: {e}")

        return filled_any

    async def _generate_hiring_manager_message(self) -> str:
        """Generate a personalized message for the hiring manager based on job and profile."""
        import httpx

        api_key = os.getenv("CEREBRAS_API_KEY") or os.getenv("GROQ_API_KEY")
        if not api_key:
            return ""

        api_url = "https://api.cerebras.ai/v1/chat/completions" if os.getenv("CEREBRAS_API_KEY") else "https://api.groq.com/openai/v1/chat/completions"
        model = "llama-3.3-70b" if os.getenv("CEREBRAS_API_KEY") else "llama-3.3-70b-versatile"

        # Build the prompt
        job_title = self.current_job_title or "this position"
        company = self.current_company or "your company"
        job_desc_snippet = (self.current_job_description or "")[:1500]  # Use first 1500 chars

        prompt = f"""Write a brief, personalized message to the hiring manager for a job application.

JOB DETAILS:
- Position: {job_title}
- Company: {company}
- Job Description Excerpt: {job_desc_snippet}

APPLICANT PROFILE:
- Name: {self.user_profile.get('name', 'Muhammad Kasim')}
- Current Title: {self.user_profile.get('title', 'Senior Software Engineer')}
- Years of Experience: {self.user_profile.get('years_experience', '13+')}
- Location: {self.user_profile.get('location', 'San Jose, CA')}

TONE & STYLE:
- FORMAL but HUMAN - professional language that still feels like a real person wrote it
- Confident without being arrogant
- Respectful of the reader's time

REQUIREMENTS:
1. Keep it to 2-3 sentences maximum (under 400 characters)
2. Start with a specific observation about the role or company that shows genuine interest
3. Connect your experience to ONE specific requirement from the job description
4. End with a forward-looking statement about contributing value
5. Use professional vocabulary but avoid corporate jargon and buzzwords
6. Do NOT use clichéd phrases like "I am excited", "I am thrilled", "passionate about", "leverage my skills"
7. Do NOT include a greeting (no "Dear Hiring Manager") or sign-off (no "Best regards")
8. Sound like a thoughtful professional, not a cover letter template

GOOD EXAMPLE: "The emphasis on scalable distributed systems in this role aligns well with my work architecting microservices at enterprise scale. With 13+ years building production systems handling millions of requests, I would welcome the opportunity to contribute to your engineering team."

BAD EXAMPLE: "I am excited about this opportunity and believe my skills make me a great fit. I am passionate about technology and would love to join your team."

Respond with ONLY the message text, nothing else."""

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    api_url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.7,  # Slightly more creative
                        "max_tokens": 200
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    message = result["choices"][0]["message"]["content"].strip()
                    # Clean up any quotes
                    message = message.strip('"\'')
                    print(f"   🤖 Generated hiring manager message")
                    return message
        except Exception as e:
            print(f"   ⚠️ Failed to generate hiring manager message: {e}")

        return ""

    async def _get_llm_answer(self, question: str, answer_type: str = "text", options: list = None) -> str:
        """Use LLM to generate an answer for a question that isn't handled by hardcoded logic.

        Args:
            question: The question text extracted from the UI
            answer_type: One of "text", "yes_no", or "dropdown"
            options: List of option texts for dropdown questions
        """
        import httpx

        api_key = os.getenv("CEREBRAS_API_KEY") or os.getenv("GROQ_API_KEY")
        if not api_key:
            return ""

        api_url = "https://api.cerebras.ai/v1/chat/completions" if os.getenv("CEREBRAS_API_KEY") else "https://api.groq.com/openai/v1/chat/completions"
        model = "llama-3.3-70b" if os.getenv("CEREBRAS_API_KEY") else "llama-3.3-70b-versatile"

        # Build context about the user
        user_context = f"""
Applicant Profile:
- Name: {self.user_profile.get('name', 'Muhammad Kasim')}
- Email: {self.user_profile.get('email', '')}
- Phone: {self.user_profile.get('phone', '')}
- Location: {self.user_profile.get('location', 'San Jose, CA')}
- Years of Experience: {self.user_profile.get('years_experience', '13+')}
- Current Title: {self.user_profile.get('title', 'Senior Software Engineer')}
- LinkedIn: {self.user_profile.get('linkedin', '')}
- Work Authorization: US Citizen, no sponsorship needed
- Willing to relocate: Yes
- Open to remote/hybrid: Yes
"""

        if answer_type == "text":
            prompt = f"""You are helping fill out a job application form. Answer the following question concisely and appropriately.

{user_context}

Question from the application form: "{question}"

Respond with ONLY the answer text, nothing else. Keep it brief and professional.
- For years of experience questions, use a number like "10" or "13"
- For salary questions, use a number like "150000"
- For date questions, use format like "2 weeks" or "Immediately"
- For text questions, keep it under 100 characters when possible
"""
        elif answer_type == "yes_no":
            prompt = f"""You are helping fill out a job application form. Determine the best Yes/No answer.

{user_context}

Question from the application form: "{question}"

Respond with ONLY "yes" or "no" (lowercase), nothing else.
- Answer "yes" for work authorization, willingness to relocate, background checks, etc.
- Answer "no" for sponsorship requirements, disability disclosures, criminal history, etc.
"""
        elif answer_type == "dropdown":
            options_str = "\n".join([f"- {opt}" for opt in (options or [])])
            prompt = f"""You are helping fill out a job application form. Select the best option from the dropdown.

{user_context}

Question from the application form: "{question}"

Available options:
{options_str}

Respond with ONLY the exact text of the best option to select, nothing else.
Choose the option that best represents the applicant's qualifications.
"""
        else:
            return ""

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    api_url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1,
                        "max_tokens": 100
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    answer = result["choices"][0]["message"]["content"].strip()
                    # Clean up the answer
                    answer = answer.strip('"\'')
                    print(f"   🤖 LLM answered '{question[:30]}...' with: {answer}")
                    return answer
        except Exception as e:
            print(f"   ⚠️ LLM answer failed: {e}")

        return ""

    def _get_answer_for_question(self, question: str) -> str:
        """Get answer for text input questions based on question content."""
        question = question.lower()

        # Years of experience questions - be specific about skills!
        if 'year' in question and 'experience' in question:
            # Skills I actually have experience with (from resume)
            # Only list skills that are genuinely in my background
            my_skills = {
                # Languages I know well
                'java': '10',
                'python': '6',
                'javascript': '10',
                'typescript': '5',
                'scala': '4',  # Ancestry (2021) + Intuit (current) for performance test scripting

                # Frontend I know
                'react': '6',
                'next.js': '4',
                'nextjs': '4',
                'html': '10',
                'css': '10',
                'frontend': '8',
                'front-end': '8',
                'front end': '8',

                # Backend I know
                'spring': '8',
                'spring boot': '6',
                'node': '5',
                'nodejs': '5',
                'node.js': '5',
                'backend': '10',
                'back-end': '10',
                'back end': '10',

                # Cloud & DevOps I know
                'aws': '5',
                'kubernetes': '3',
                'k8s': '3',
                'docker': '4',
                'jenkins': '4',
                'ci/cd': '5',

                # Databases I know
                'sql': '10',
                'mysql': '8',
                'postgresql': '5',
                'postgres': '5',
                'mongodb': '3',
                'redis': '3',
                'dynamodb': '2',
                'database': '10',

                # General skills
                'agile': '8',
                'scrum': '8',
                'microservices': '5',
                'api': '10',
                'rest': '10',
                'full stack': '10',
                'fullstack': '10',
                'full-stack': '10',
                'software engineer': '13',
                'software development': '13',
                'programming': '13',
                'web development': '10',
                'web application': '10',
            }

            # Skills I DON'T have or have minimal experience with
            # Return 0 for these skills
            skills_i_dont_have = [
                # Languages I don't know
                'php', 'ruby', 'go', 'golang', 'rust', 'kotlin', 'swift',
                'c++', 'c#', '.net', 'dotnet', 'perl', 'r language', 'r programming',
                'objective-c', 'objective c',
                # C language (careful matching - use ' c ' with spaces or 'c programming' or 'c language')
                ' c ', 'c programming', 'c language', 'c development', 'c/c++',
                # Unix/Linux/Shell scripting I don't have deep experience in
                'unix', 'linux', 'shell', 'bash', 'ksh', 'zsh', 'csh',
                'shell scripting', 'batch processing', 'batch developer', 'batch job',
                # Frontend I don't know
                'angular', 'vue', 'svelte', 'ember',
                # Backend I don't know
                'django', 'flask', 'rails', 'laravel',
                # Cloud/DevOps I don't know
                'azure', 'gcp', 'google cloud', 'terraform', 'ansible',
                # ML/AI I don't know
                'machine learning', 'ml', 'ai', 'artificial intelligence',
                'deep learning', 'tensorflow', 'pytorch', 'nlp', 'data science',
                'computer vision', 'neural network',
                # Big Data I don't know
                'hadoop', 'spark', 'kafka', 'elasticsearch', 'data engineering',
                # Enterprise I don't know
                'salesforce', 'sap', 'oracle', 'peoplesoft', 'servicenow',
                # Mobile I don't know
                'ios', 'android', 'mobile', 'flutter', 'react native',
                # Blockchain I don't know
                'blockchain', 'solidity', 'web3', 'cryptocurrency',
                # Gaming I don't know
                'unity', 'unreal', 'game development', 'game engine',
                # Embedded/IoT I don't know
                'embedded', 'firmware', 'iot', 'hardware',
                # Legacy I don't know
                'mainframe', 'cobol', 'fortran', 'as400', 'jcl',
                # Security I don't know
                'cybersecurity', 'penetration testing', 'security engineering',
                # Networking I don't know
                'cisco', 'networking', 'ccna', 'ccnp',
            ]

            # Check if asking about a skill I don't have
            for skill in skills_i_dont_have:
                if skill in question:
                    # Return 0 for skills I don't have
                    return '0'

            # Check for specific skill mentions in the question
            for skill, years in my_skills.items():
                if skill in question:
                    return years

            # If no specific skill found but asking about general experience, return total years
            if any(term in question for term in ['total', 'overall', 'professional', 'work experience', 'industry']):
                return self.user_profile.get('years_experience', '13').replace('+', '')

            # IMPORTANT: For ANY unknown specific skill question, return 0 instead of letting LLM guess
            # This prevents the bot from claiming years of experience in skills we don't have
            return '0'

        # Salary expectations
        if 'salary' in question or 'compensation' in question or 'pay' in question:
            return "150000"

        # Location/city
        if 'city' in question or 'location' in question:
            return self.user_profile.get('location', 'San Jose, CA')

        # LinkedIn profile
        if 'linkedin' in question:
            return self.user_profile.get('linkedin', '')

        # Phone
        if 'phone' in question or 'mobile' in question:
            return self.user_profile.get('phone', '')

        # Website/portfolio
        if 'website' in question or 'portfolio' in question or 'github' in question:
            return "N/A"

        # Start date / notice period
        if 'start' in question or 'notice' in question or 'available' in question:
            return "2 weeks"

        # GPA
        if 'gpa' in question:
            return "3.5"

        # Default for numeric fields
        if any(word in question for word in ['how many', 'number of', 'count']):
            return "5"

        return ""

    def _get_yes_no_answer(self, question: str) -> str:
        """Determine Yes/No answer for common application questions."""
        question = question.lower()

        # Questions that should be answered YES
        yes_questions = [
            'authorized to work', 'legally authorized', 'work authorization',
            'eligible to work', 'right to work', 'work permit',
            'willing to', 'able to', 'agree to', 'consent',
            'driver', 'license', 'driving',  # driver's license
            'background check', 'drug test', 'drug screen',
            'relocate', 'relocation', 'open to relocation',
            'commute', 'travel', 'remote',
            'us citizen', 'citizen', 'permanent resident',
            'over 18', 'at least 18', '18 years',
            'experience with', 'proficient', 'familiar with',
            'currently reside', 'based in'
        ]

        # Questions that should be answered NO
        no_questions = [
            'sponsorship', 'visa sponsorship', 'require sponsorship',
            'need sponsorship', 'immigration sponsorship',
            'disability', 'disabled', 'handicap',
            'convicted', 'felony', 'criminal',
            'non-compete', 'non compete',
            'lawsuit', 'litigation'
        ]

        for phrase in yes_questions:
            if phrase in question:
                return 'yes'

        for phrase in no_questions:
            if phrase in question:
                return 'no'

        # Default to yes for most unknown questions
        return 'yes'

    def _get_dropdown_answer(self, label: str, options: list) -> str:
        """Get answer for dropdown questions."""
        label = label.lower()
        option_texts = [o['text'].lower() for o in options]

        # Education level
        if 'education' in label or 'degree' in label:
            for pref in ["master's", "master", "bachelor's", "bachelor", "bs", "ms", "ba"]:
                for opt in options:
                    if pref in opt['text'].lower():
                        return opt['text']

        # Experience level
        if 'experience' in label or 'years' in label:
            for opt in options:
                text = opt['text'].lower()
                if '10' in text or '5' in text or 'senior' in text or 'expert' in text:
                    return opt['text']

        # Work authorization
        if 'authorization' in label or 'authorized' in label:
            for opt in options:
                if 'yes' in opt['text'].lower() or 'authorized' in opt['text'].lower():
                    return opt['text']

        # Willing to relocate
        if 'relocate' in label or 'relocation' in label:
            for opt in options:
                if 'yes' in opt['text'].lower():
                    return opt['text']

        # Try to find a sensible default (not "Select" or empty)
        for opt in options:
            text = opt['text'].lower().strip()
            if text and text not in ['select', 'select an option', 'please select', '--', '']:
                return opt['text']

        return ""

    async def _fill_external_eeo_fields(self) -> bool:
        """Fill EEO fields on external job sites (Greenhouse, Workday, etc.)."""
        filled_any = False
        page = self.controller.page

        # EEO field mappings: (field pattern, value to select)
        eeo_mappings = [
            # Gender
            (['gender', 'sex'], 'Male'),
            # Race/Ethnicity
            (['race', 'ethnicity', 'ethnic'], 'Asian'),
            # Veteran status
            (['veteran'], 'I am not'),
            # Disability
            (['disability', 'disabilities'], 'No, I don'),
            # Hispanic/Latino
            (['hispanic', 'latino'], 'No'),
            # LGBTQ+
            (['lgbtq', 'sexual orientation'], 'decline'),
        ]

        # Handle standard <select> dropdowns
        selects = await page.query_selector_all('select')
        for select in selects:
            try:
                # Scroll to make dropdown visible
                await self._scroll_modal_to_element(select)

                # Get the label for this select
                select_id = await select.get_attribute('id') or ''
                select_name = await select.get_attribute('name') or ''

                # Try to get label text
                label = ""
                if select_id:
                    label_elem = await page.query_selector(f'label[for="{select_id}"]')
                    if label_elem:
                        label = await label_elem.inner_text()
                if not label:
                    # Check parent for label
                    parent = await select.evaluate('(el) => el.parentElement?.innerText || ""')
                    label = str(parent)[:100]

                label_lower = (label + select_name + select_id).lower()

                for patterns, value in eeo_mappings:
                    if any(p in label_lower for p in patterns):
                        options = await select.evaluate('(el) => Array.from(el.options).map(o => ({v: o.value, t: o.text}))')
                        for opt in options:
                            if value.lower() in opt['t'].lower():
                                await select.select_option(value=opt['v'])
                                print(f"   ✅ EEO select: {patterns[0]} -> '{opt['t']}'")
                                filled_any = True
                                break
                        break
            except Exception as e:
                pass

        # Handle custom dropdowns (div-based with listbox/combobox) using keyboard navigation
        custom_dropdowns = await page.query_selector_all(
            '[role="listbox"], [role="combobox"], [data-automation*="select"], '
            '.select-dropdown, .dropdown-trigger, button[aria-haspopup="listbox"], '
            '[class*="dropdown"], [class*="select"]'
        )

        for dropdown in custom_dropdowns:
            try:
                # Scroll to make dropdown visible
                await self._scroll_modal_to_element(dropdown)

                # Get label for this dropdown
                label = await dropdown.evaluate('''(el) => {
                    // Check aria-label
                    if (el.getAttribute("aria-label")) return el.getAttribute("aria-label");
                    // Check aria-labelledby
                    const labelledBy = el.getAttribute("aria-labelledby");
                    if (labelledBy) {
                        const labelEl = document.getElementById(labelledBy);
                        if (labelEl) return labelEl.innerText;
                    }
                    // Check parent label
                    const parent = el.closest("label, .field, .form-group, [data-field]");
                    if (parent) return parent.innerText;
                    return el.innerText || "";
                }''')

                label_lower = label.lower() if label else ""

                for patterns, value in eeo_mappings:
                    if any(p in label_lower for p in patterns):
                        # Focus on the dropdown first
                        await dropdown.focus()
                        await asyncio.sleep(0.3)

                        # Click to open dropdown
                        await dropdown.click()
                        await asyncio.sleep(0.5)

                        # Get all visible options
                        options = await page.query_selector_all('[role="option"], li[class*="option"], div[class*="option"]')
                        if not options:
                            # Try pressing down arrow to see options
                            await page.keyboard.press('ArrowDown')
                            await asyncio.sleep(0.3)
                            options = await page.query_selector_all('[role="option"], li[class*="option"], div[class*="option"]')

                        # Find the target option index
                        target_index = -1
                        for i, opt in enumerate(options):
                            opt_text = await opt.inner_text()
                            if value.lower() in opt_text.lower():
                                target_index = i
                                break

                        if target_index >= 0:
                            # Use keyboard to navigate to the option
                            # First go to top with Home or multiple Up arrows
                            await page.keyboard.press('Home')
                            await asyncio.sleep(0.2)

                            # Navigate down to the target option
                            for _ in range(target_index):
                                await page.keyboard.press('ArrowDown')
                                await asyncio.sleep(0.1)

                            # Select with Enter
                            await page.keyboard.press('Enter')
                            print(f"   ✅ EEO dropdown (keyboard): {patterns[0]} -> '{value}'")
                            filled_any = True
                        else:
                            # Fallback: try clicking directly on option
                            option = await page.query_selector(f'[role="option"]:has-text("{value}")')
                            if option:
                                await option.click()
                                print(f"   ✅ EEO dropdown (click): {patterns[0]} -> '{value}'")
                                filled_any = True
                            else:
                                # Try partial match with click
                                for opt in options:
                                    opt_text = await opt.inner_text()
                                if value.lower() in opt_text.lower():
                                    await opt.click()
                                    print(f"   ✅ EEO dropdown: {patterns[0]} -> '{opt_text}'")
                                    filled_any = True
                                    break
                        break
            except Exception as e:
                pass

        # Handle radio buttons for EEO fields
        radio_groups = await page.query_selector_all('fieldset, [role="radiogroup"], .radio-group')
        for group in radio_groups:
            try:
                group_text = await group.inner_text()
                group_lower = group_text.lower()

                for patterns, value in eeo_mappings:
                    if any(p in group_lower for p in patterns):
                        # Find the right radio option
                        radios = await group.query_selector_all('input[type="radio"]')
                        for radio in radios:
                            label = await radio.evaluate('''(el) => {
                                const label = el.nextElementSibling || el.closest("label");
                                return label ? label.innerText : "";
                            }''')
                            if value.lower() in label.lower():
                                await radio.click()
                                print(f"   ✅ EEO radio: {patterns[0]} -> '{label}'")
                                filled_any = True
                                break
                        break
            except Exception as e:
                pass

        # Handle checkboxes for acknowledgment
        checkboxes = await page.query_selector_all('input[type="checkbox"]')
        for checkbox in checkboxes:
            try:
                is_checked = await checkbox.is_checked()
                if not is_checked:
                    label = await checkbox.evaluate('''(el) => {
                        const label = document.querySelector(`label[for="${el.id}"]`) || el.closest("label");
                        return label ? label.innerText : "";
                    }''')
                    label_lower = label.lower()
                    # Check acknowledgment checkboxes
                    if any(term in label_lower for term in ['acknowledge', 'agree', 'certify', 'confirm', 'i understand']):
                        await checkbox.check()
                        print(f"   ✅ Checked acknowledgment: {label[:40]}...")
                        filled_any = True
            except Exception as e:
                pass

        return filled_any

    async def _is_workday_site(self) -> bool:
        """Check if current page is a Workday application site."""
        try:
            url = self.controller.page.url.lower()
            if 'workday' in url or 'myworkday' in url or 'wd5' in url or 'wd3' in url:
                return True
            # Check for Workday-specific elements
            has_workday = await self.controller.page.evaluate('''() => {
                return !!(
                    document.querySelector('[data-automation-id]') ||
                    document.querySelector('.WDFC') ||
                    document.querySelector('[class*="workday"]') ||
                    document.body.innerHTML.includes('workday') ||
                    document.querySelector('[data-uxi-widget-type]')
                );
            }''')
            return has_workday
        except:
            return False

    async def _fill_workday_form(self) -> bool:
        """Fill Workday-specific form fields."""
        filled_any = False
        page = self.controller.page

        try:
            # Workday uses data-automation-id attributes extensively
            # Common field patterns in Workday
            workday_fields = [
                # Name fields
                ('legalNameSection_firstName', self.user_profile['first_name']),
                ('legalNameSection_lastName', self.user_profile['last_name']),
                ('firstName', self.user_profile['first_name']),
                ('lastName', self.user_profile['last_name']),
                ('name', f"{self.user_profile['first_name']} {self.user_profile['last_name']}"),
                # Contact fields
                ('email', self.user_profile['email']),
                ('phone', self.user_profile['phone']),
                ('phoneNumber', self.user_profile['phone']),
                ('addressSection_addressLine1', self.user_profile.get('address', '')),
                ('addressSection_city', self.user_profile.get('city', 'San Jose')),
                ('addressSection_postalCode', self.user_profile.get('zip', '')),
                # LinkedIn
                ('linkedinQuestion', 'https://linkedin.com/in/muhammad-kasim-0b297416'),
                ('linkedin', 'https://linkedin.com/in/muhammad-kasim-0b297416'),
            ]

            for field_id, value in workday_fields:
                if not value:
                    continue
                try:
                    # Try data-automation-id selector first (Workday's primary pattern)
                    field = await page.query_selector(f'[data-automation-id="{field_id}"]')
                    if not field:
                        # Try common variations
                        field = await page.query_selector(f'[data-automation-id*="{field_id}"]')
                    if not field:
                        field = await page.query_selector(f'input[name*="{field_id}" i]')
                    if not field:
                        field = await page.query_selector(f'input[id*="{field_id}" i]')

                    if field:
                        current_val = await field.input_value() if await field.is_visible() else ''
                        if not current_val:
                            await field.fill(value)
                            print(f"   ✅ Workday field '{field_id}': {value[:30]}...")
                            filled_any = True
                            await asyncio.sleep(0.2)
                except Exception as e:
                    pass

            # Handle Workday custom dropdowns (they use data-automation-id="selectWidget")
            dropdowns = await page.query_selector_all('[data-automation-id="selectWidget"], [data-automation-id*="dropdown"]')
            for dropdown in dropdowns:
                try:
                    # Get the label/question for this dropdown
                    label = await dropdown.evaluate('''(el) => {
                        const label = el.closest('[data-automation-id]')?.querySelector('label');
                        return label ? label.innerText.toLowerCase() : '';
                    }''')

                    # Check if already has value
                    current_value = await dropdown.inner_text()
                    if current_value and 'select' not in current_value.lower():
                        continue

                    # Country dropdown
                    if 'country' in label:
                        await dropdown.click()
                        await asyncio.sleep(0.5)
                        us_option = await page.query_selector('[data-automation-id="promptOption"]:has-text("United States")')
                        if us_option:
                            await us_option.click()
                            print("   ✅ Workday dropdown: Country -> United States")
                            filled_any = True
                            await asyncio.sleep(0.3)

                    # State dropdown
                    elif 'state' in label or 'province' in label:
                        await dropdown.click()
                        await asyncio.sleep(0.5)
                        ca_option = await page.query_selector('[data-automation-id="promptOption"]:has-text("California")')
                        if ca_option:
                            await ca_option.click()
                            print("   ✅ Workday dropdown: State -> California")
                            filled_any = True
                            await asyncio.sleep(0.3)

                    # Phone type dropdown
                    elif 'phone' in label and 'type' in label:
                        await dropdown.click()
                        await asyncio.sleep(0.5)
                        mobile_option = await page.query_selector('[data-automation-id="promptOption"]:has-text("Mobile")')
                        if mobile_option:
                            await mobile_option.click()
                            print("   ✅ Workday dropdown: Phone Type -> Mobile")
                            filled_any = True
                            await asyncio.sleep(0.3)

                except Exception as e:
                    pass

            # Handle "How did you hear about us" type questions
            source_dropdowns = await page.query_selector_all('[data-automation-id*="source"], [data-automation-id*="howDidYouHear"]')
            for dropdown in source_dropdowns:
                try:
                    await dropdown.click()
                    await asyncio.sleep(0.5)
                    linkedin_option = await page.query_selector('[data-automation-id="promptOption"]:has-text("LinkedIn")')
                    if linkedin_option:
                        await linkedin_option.click()
                        print("   ✅ Workday: How did you hear -> LinkedIn")
                        filled_any = True
                except:
                    pass

            # Handle resume upload in Workday
            resume_path = self._get_current_resume_path()
            if resume_path:
                try:
                    # Workday file upload buttons
                    file_input = await page.query_selector('input[type="file"][data-automation-id*="resume"]')
                    if not file_input:
                        file_input = await page.query_selector('input[type="file"][data-automation-id*="file"]')
                    if not file_input:
                        file_input = await page.query_selector('input[type="file"]')

                    if file_input:
                        await file_input.set_input_files(resume_path)
                        print(f"   📎 Workday: Uploaded resume")
                        filled_any = True
                        await asyncio.sleep(1)
                except:
                    pass

            # Handle "Yes/No" questions using Workday radio buttons
            radio_groups = await page.query_selector_all('[data-automation-id="radioGroup"]')
            for group in radio_groups:
                try:
                    question = await group.evaluate('''(el) => {
                        const label = el.closest('[data-automation-id]')?.querySelector('label, legend');
                        return label ? label.innerText.toLowerCase() : '';
                    }''')

                    # Common yes/no questions
                    select_yes = any(term in question for term in [
                        'authorized', 'legally', 'eligible', 'work in', 'united states',
                        '18 years', 'legal age'
                    ])
                    select_no = any(term in question for term in [
                        'sponsorship', 'require visa', 'need sponsorship'
                    ])

                    if select_yes:
                        yes_radio = await group.query_selector('[data-automation-id*="radio"]:has-text("Yes")')
                        if yes_radio:
                            await yes_radio.click()
                            print(f"   ✅ Workday radio: '{question[:40]}...' -> Yes")
                            filled_any = True
                    elif select_no:
                        no_radio = await group.query_selector('[data-automation-id*="radio"]:has-text("No")')
                        if no_radio:
                            await no_radio.click()
                            print(f"   ✅ Workday radio: '{question[:40]}...' -> No")
                            filled_any = True

                except Exception as e:
                    pass

            # Click Next/Continue/Submit buttons
            if filled_any:
                await asyncio.sleep(0.5)
                next_btn = await page.query_selector(
                    '[data-automation-id="bottom-navigation-next-button"], '
                    '[data-automation-id="navigationButton-next"], '
                    'button[data-automation-id*="submit"], '
                    'button[data-automation-id*="next"]'
                )
                if next_btn:
                    try:
                        await next_btn.click()
                        print("   ✅ Clicked Workday Next/Submit button")
                        await asyncio.sleep(2)
                    except:
                        pass

        except Exception as e:
            print(f"   ⚠️ Workday form error: {e}")

        return filled_any

    def _get_current_resume_path(self) -> str:
        """Get the path to the most recently generated resume."""
        try:
            output_dir = Path("output")
            if output_dir.exists():
                pdfs = sorted(output_dir.glob("resume_*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True)
                if pdfs:
                    return str(pdfs[0])
        except:
            pass
        return ""

    async def _apply_learned_fixes(self, page_context: str) -> bool:
        """Apply fixes learned from previous user interventions."""
        if not self.user_interventions:
            return False

        # Check if any learned intervention matches current context
        for intervention in self.user_interventions:
            for action in intervention.get('actions', []):
                if action['type'] == 'select':
                    # Try to find and apply select action
                    try:
                        value = action.get('value')
                        name = action.get('name') or action.get('id')
                        if name and value:
                            selector = f'select[name="{name}"], select[id="{name}"]'
                            select_el = await self.controller.page.query_selector(selector)
                            if select_el:
                                await select_el.select_option(value=value)
                                print(f"🧠 Applied learned fix: Selected '{action.get('selectedText', value)}' from dropdown")
                                return True
                    except:
                        pass

                elif action['type'] == 'click':
                    # Try to find and click similar element
                    try:
                        text = action.get('text', '')[:30]
                        if text:
                            btn = await self.controller.page.query_selector(f'button:has-text("{text}"), a:has-text("{text}")')
                            if btn:
                                await btn.click()
                                print(f"🧠 Applied learned fix: Clicked '{text}'")
                                return True
                    except:
                        pass

        return False

    async def login(self) -> bool:
        """Log into LinkedIn with human-like behavior."""
        import random
        print("🔐 Checking LinkedIn session...")

        # First, check if we're already on LinkedIn and logged in (don't navigate to login page yet)
        current_url = self.controller.page.url

        # If we're already on LinkedIn (from persistent session), check if logged in
        if "linkedin.com" in current_url:
            # Check for logged-in indicators
            if any(x in current_url for x in ["feed", "mynetwork", "jobs", "messaging", "in/"]):
                print("✅ Already logged in (persistent session)!")
                return True

            # Check for nav bar or profile elements that indicate login
            logged_in_check = await self.controller.page.query_selector('nav.global-nav, .global-nav__me, [data-control-name="identity_welcome_message"]')
            if logged_in_check:
                print("✅ Already logged in (detected nav bar)!")
                return True

        # Navigate to feed to check session (not login page - that can invalidate session)
        await self.controller.goto("https://www.linkedin.com/feed/")

        # Wait for page to fully load and check redirect
        try:
            await self.controller.page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        await asyncio.sleep(3)

        # Take screenshot for debugging
        try:
            await self.controller.page.screenshot(path="screenshots/login_page.png")
            print("   📸 Session check screenshot saved")
        except:
            pass

        # Check for "Choose an account" or user profile button to click for existing session
        # LinkedIn sometimes shows partially hidden username buttons when multiple accounts are available
        try:
            # Look for user profile buttons with name/email showing
            user_profile_btn = await self.controller.page.query_selector(
                'button[data-test-id="profile-card"], '
                '[data-test-id="profile-card"], '
                '.profile-card, '
                'button:has-text("@"), '
                '[class*="profile"] button, '
                '.artdeco-dropdown__trigger, '
                'button[aria-label*="account"], '
                '[data-control-name="identity_profile_photo"]'
            )
            if user_profile_btn:
                print("   🔑 Found existing session button, clicking to use existing account...")
                await user_profile_btn.click()
                await asyncio.sleep(2)
        except Exception as e:
            pass  # No profile button found, continue with normal flow

        # Check if already logged in (session is valid - we should be on feed)
        current_url = self.controller.page.url
        if "feed" in current_url or "mynetwork" in current_url or "jobs" in current_url or "messaging" in current_url:
            print("✅ Already logged in (persistent session)!")
            return True

        # Check if we were redirected to login page - session expired
        if "login" not in current_url and "uas" not in current_url and "authwall" not in current_url:
            # Could be logged in but on a different page
            if "linkedin.com" in current_url and "checkpoint" not in current_url:
                print("✅ Already logged in (persistent session)!")
                return True

        # Session expired or not logged in - need to login
        print("🔐 Session expired, logging in...")
        await self.controller.goto("https://www.linkedin.com/login")

        # Wait for login page to load
        try:
            await self.controller.page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass
        await asyncio.sleep(2)

        # Human-like delay before starting to type
        await asyncio.sleep(random.uniform(1.5, 3.0))

        # Type email with human-like character-by-character input
        # Try multiple selectors without :visible (it can be unreliable)
        email_input = await self.controller.page.query_selector('#username')
        print(f"   Debug: #username selector found: {email_input is not None}")

        if not email_input:
            email_input = await self.controller.page.query_selector('input[name="session_key"][type="text"]')
            print(f"   Debug: session_key[type=text] found: {email_input is not None}")
        if not email_input:
            email_input = await self.controller.page.query_selector('input[autocomplete="username"]')
            print(f"   Debug: autocomplete=username found: {email_input is not None}")
        if not email_input:
            # LinkedIn login page uses #username - wait for it to be visible
            try:
                email_input = await self.controller.page.wait_for_selector('#username', timeout=5000)
                print(f"   Debug: Waited for #username: {email_input is not None}")
            except:
                pass
        if not email_input:
            # Try to find any visible text input that looks like email field
            all_text_inputs = await self.controller.page.query_selector_all('input[type="text"], input[type="email"]')
            print(f"   Debug: Found {len(all_text_inputs)} text/email inputs")
            for inp in all_text_inputs:
                is_visible = await inp.is_visible()
                if is_visible:
                    email_input = inp
                    print(f"   Debug: Found visible text input")
                    break

        if not email_input:
            # No login form - might be redirected to feed (already logged in)
            current_url = self.controller.page.url
            print(f"   Debug: Current URL = {current_url}")
            if "login" not in current_url and "authwall" not in current_url and "checkpoint" not in current_url:
                print("✅ Already logged in (no login form visible)!")
                return True

            # Check for security checkpoint
            if "checkpoint" in current_url:
                print("⚠️  Security checkpoint detected. Please complete it manually...")
                print("    Waiting 60 seconds for you to complete verification...")
                await asyncio.sleep(60)
                return "feed" in self.controller.page.url or "jobs" in self.controller.page.url

            # Maybe login form is there but with different selectors
            all_inputs = await self.controller.page.query_selector_all('input')
            print(f"   Debug: Found {len(all_inputs)} input elements on page")
            for inp in all_inputs[:5]:
                inp_type = await inp.get_attribute('type') or ''
                inp_name = await inp.get_attribute('name') or ''
                inp_id = await inp.get_attribute('id') or ''
                print(f"   Debug: input type={inp_type}, name={inp_name}, id={inp_id}")

            print("⚠️ Login form not found")
            return False

        # Type email
        await email_input.click()
        await asyncio.sleep(random.uniform(0.2, 0.5))
        # Type character by character like a human
        for char in self.email:
            await email_input.type(char, delay=random.randint(50, 150))
        await asyncio.sleep(random.uniform(0.3, 0.8))

        # Human pause between email and password (like looking at keyboard)
        await asyncio.sleep(random.uniform(0.5, 1.2))

        # Type password with human-like speed
        password_input = await self.controller.page.query_selector('input[name="session_password"]')
        if password_input:
            await password_input.click()
            await asyncio.sleep(random.uniform(0.2, 0.4))
            # Type character by character
            for char in self.password:
                await password_input.type(char, delay=random.randint(40, 120))
            await asyncio.sleep(random.uniform(0.3, 0.7))

        # Human pause before clicking submit (like moving mouse)
        await asyncio.sleep(random.uniform(0.5, 1.0))

        # Click sign in
        sign_in_btn = await self.controller.page.query_selector('button[type="submit"]')
        if sign_in_btn:
            await sign_in_btn.click()
            # Wait for page to load with natural variation
            await asyncio.sleep(random.uniform(2.5, 4.0))

        # Check if logged in
        if "feed" in self.controller.page.url or "mynetwork" in self.controller.page.url:
            print("✅ Successfully logged in!")
            return True

        # Check for security challenge
        if "checkpoint" in self.controller.page.url:
            print("⚠️  Security challenge detected. Please complete it manually...")
            print("    Waiting 60 seconds for you to complete verification...")
            await asyncio.sleep(60)
            return "feed" in self.controller.page.url

        print("✅ Login appears successful")
        return True
    
    async def search_jobs(self, keywords: str, location: str = ""):
        """Search for jobs on LinkedIn with human-like behavior."""
        import random
        print(f"🔍 Searching for: {keywords}")

        search_url = f"https://www.linkedin.com/jobs/search/?keywords={keywords.replace(' ', '%20')}"
        if location:
            search_url += f"&location={location.replace(' ', '%20')}"
        search_url += "&f_AL=true"  # Easy Apply filter
        search_url += "&sortBy=DD"  # Sort by Date (most recent first)

        await self.controller.goto(search_url)
        # Human-like wait for page load with variation
        await asyncio.sleep(random.uniform(2.0, 4.0))

        # Sometimes humans scroll a bit to see the results
        if random.random() < 0.5:
            await self.controller.page.evaluate(f"window.scrollBy(0, {random.randint(100, 300)})")
            await asyncio.sleep(random.uniform(0.5, 1.5))

        print("📋 Job search results loaded")
        self.applied_jobs = set()

        # Take a screenshot for debugging
        try:
            await self.controller.page.screenshot(path="screenshots/job_search_results.png")
            print("   📸 Screenshot saved: screenshots/job_search_results.png")
        except Exception as e:
            print(f"   ⚠️ Could not save screenshot: {e}")

        # Debug: Check what job card selectors exist
        debug_info = await self.controller.page.evaluate('''() => {
            const selectors = [
                '.jobs-search-results__list-item',
                '.scaffold-layout__list-item',
                '[data-job-id]',
                '.job-card-container',
                '.jobs-search-results-list__list-item',
                'li[class*="job"]',
                'div[class*="job-card"]',
                '.jobs-search-results-list',
                '.jobs-search__results-list',
                // New selectors to try
                '.jobs-search-results-list li',
                '.jobs-search__results-list li',
                'ul li',
                '[data-occludable-job-id]',
                '.job-card-list',
                '.jobs-search-results-list > ul > li'
            ];
            const results = {};
            for (const sel of selectors) {
                results[sel] = document.querySelectorAll(sel).length;
            }

            // Also get the first few li elements' class names
            const listItems = document.querySelectorAll('.jobs-search__results-list li, .jobs-search-results-list li');
            const liClasses = [];
            for (let i = 0; i < Math.min(3, listItems.length); i++) {
                liClasses.push(listItems[i].className);
            }
            results['li_classes'] = liClasses;

            return results;
        }''')
        print(f"   📊 Job card selectors found: {debug_info}")

    async def click_next_job(self) -> bool:
        """Click on the next job in the list using JavaScript for reliability."""
        import random
        try:
            # Human-like delay before clicking on job
            await asyncio.sleep(random.uniform(1.5, 3.0))

            # Use JavaScript to find and click a job we haven't applied to
            applied_list = list(self.applied_jobs)

            result = await self.controller.page.evaluate('''(appliedJobs) => {
                // Find all job cards in the list - try multiple selectors in order of specificity
                // LinkedIn's structure varies, so we try multiple approaches
                let jobCards = document.querySelectorAll('.scaffold-layout__list-item, [data-occludable-job-id]');

                if (jobCards.length === 0) {
                    // Try the jobs-search__results-list li selector (found 7 in recent test)
                    jobCards = document.querySelectorAll('.jobs-search__results-list li');
                }

                if (jobCards.length === 0) {
                    // Try alternative selectors
                    jobCards = document.querySelectorAll('.jobs-search-results__list-item, [data-job-id], .job-card-container');
                }

                if (jobCards.length === 0) {
                    // Try even more generic selectors
                    jobCards = document.querySelectorAll('li[class*="job"], div[class*="job-card"]');
                }

                if (jobCards.length === 0) {
                    // Last resort: any li in the main content area
                    const mainList = document.querySelector('.jobs-search__results-list, .jobs-search-results-list');
                    if (mainList) {
                        jobCards = mainList.querySelectorAll('li');
                    }
                }

                const debugInfo = { totalCards: jobCards.length, skippedApplied: 0, skippedNoTitle: 0 };

                for (const card of jobCards) {
                    // Check if this job has "Applied" badge - skip it
                    const cardText = card.innerText.toLowerCase();
                    if (cardText.includes('applied') && !cardText.includes('easy apply')) {
                        debugInfo.skippedApplied++;
                        continue;
                    }

                    // Get job title from the card - try multiple selectors
                    let titleEl = card.querySelector('.job-card-list__title, .artdeco-entity-lockup__title');
                    if (!titleEl) {
                        titleEl = card.querySelector('a[href*="/jobs/view"], a[class*="job-card"]');
                    }
                    if (!titleEl) {
                        titleEl = card.querySelector('strong, h3, [class*="title"]');
                    }

                    const companyEl = card.querySelector('.job-card-container__company-name, .artdeco-entity-lockup__subtitle, [class*="company"]');

                    if (titleEl) {
                        const title = titleEl.innerText.trim();
                        const company = companyEl ? companyEl.innerText.trim() : '';
                        const jobKey = title + ' at ' + company;

                        // Check if we've already applied to this job (in our session tracking)
                        let alreadyApplied = false;
                        for (const applied of appliedJobs) {
                            if (applied.includes(title) || jobKey.includes(applied.split(' at ')[0])) {
                                alreadyApplied = true;
                                break;
                            }
                        }

                        if (!alreadyApplied) {
                            // Click on this job
                            const clickTarget = card.querySelector('a') || titleEl;
                            if (clickTarget) {
                                clickTarget.click();
                                return { success: true, job: title, company: company, debug: debugInfo };
                            }
                        }
                    } else {
                        debugInfo.skippedNoTitle++;
                    }
                }

                return { success: false, reason: 'No new jobs found', debug: debugInfo };
            }''', applied_list)

            if result.get('success'):
                print(f"   Clicked on: {result.get('job', 'Unknown')}")
                # Human-like delay to read job details
                await asyncio.sleep(random.uniform(1.5, 3.5))
                return True
            else:
                # Debug info
                debug = result.get('debug', {})
                print(f"   📊 Debug: {debug.get('totalCards', 0)} cards found, {debug.get('skippedApplied', 0)} already applied, {debug.get('skippedNoTitle', 0)} no title")
                # Scroll down to load more jobs
                print("   No new jobs visible, scrolling...")
                scroll_amount = random.randint(300, 600)
                await self.controller.page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                await asyncio.sleep(random.uniform(1.5, 2.5))

                # Try once more with LLM
                page_context = await get_page_context(self.controller.page)
                applied_str = ", ".join(applied_list[-5:]) if applied_list else "None yet"

                goal = f"""
Click on a job listing that I haven't applied to yet.
ALREADY APPLIED TO THESE JOBS (skip these): {applied_str}
Click on a DIFFERENT job title or job card.
"""

                action = await get_next_action(
                    goal=goal,
                    page_context=page_context,
                    user_profile=self.user_profile,
                    history=[]
                )

                print(f"   LLM action: {action.action_type} - {action.reason[:50]}")

                if action.action_type == "click" and action.element_index is not None:
                    success = await self.controller.execute_action(action)
                    if success:
                        await asyncio.sleep(2)
                        return True

            return False

        except Exception as e:
            print(f"⚠️ Error clicking job: {e}")
            return False

    async def _uncheck_follow_company(self):
        """Uncheck the 'Follow company' checkbox if it's checked."""
        try:
            # Use JavaScript to find and uncheck ANY checked checkbox with "Follow" in its label
            unchecked = await self.controller.page.evaluate('''() => {
                // Find all checked checkboxes in the modal
                const modal = document.querySelector('[role="dialog"], .artdeco-modal, [aria-modal="true"]');
                if (!modal) return false;

                // Look for labels containing "Follow"
                const labels = modal.querySelectorAll('label');
                for (const label of labels) {
                    if (label.textContent.toLowerCase().includes('follow')) {
                        const checkbox = label.querySelector('input[type="checkbox"]');
                        if (checkbox && checkbox.checked) {
                            checkbox.click();
                            return true;
                        }
                        // Also try clicking the label itself
                        const input = document.getElementById(label.getAttribute('for'));
                        if (input && input.checked) {
                            input.click();
                            return true;
                        }
                    }
                }

                // Fallback: find any checked checkbox and check if parent has "follow" text
                const checkboxes = modal.querySelectorAll('input[type="checkbox"]:checked');
                for (const cb of checkboxes) {
                    const parent = cb.closest('div, label, span');
                    if (parent && parent.textContent.toLowerCase().includes('follow')) {
                        cb.click();
                        return true;
                    }
                }

                return false;
            }''')

            if unchecked:
                print("📌 Unchecked 'Follow company' checkbox!")
                await asyncio.sleep(0.5)
                return True

        except Exception as e:
            print(f"⚠️ Could not uncheck follow checkbox: {e}")
        return False

    async def _dismiss_application_confirmation(self):
        """Click OK/Done button to dismiss the application confirmation dialog."""
        try:
            await asyncio.sleep(1)  # Wait for confirmation dialog to appear

            # Try multiple selectors for the dismiss/done button
            dismiss_selectors = [
                'button[aria-label="Dismiss"]',
                'button:has-text("Done")',
                'button:has-text("OK")',
                'button:has-text("Got it")',
                '[data-test-modal-close-btn]',
                '.artdeco-modal__dismiss',
                'button.artdeco-button--primary:has-text("Done")',
                '[aria-label="Done"]',
            ]

            for selector in dismiss_selectors:
                try:
                    btn = await self.controller.page.query_selector(selector)
                    if btn and await btn.is_visible():
                        await btn.click()
                        print(f"   ✅ Clicked dismiss button: {selector[:40]}")
                        await asyncio.sleep(0.5)
                        return True
                except:
                    continue

            # Fallback: Use JavaScript to find and click any button with "Done", "OK", or "Dismiss"
            clicked = await self.controller.page.evaluate('''() => {
                const modal = document.querySelector('[role="dialog"], .artdeco-modal, [aria-modal="true"]');
                if (!modal) return false;

                const buttons = modal.querySelectorAll('button');
                for (const btn of buttons) {
                    const text = btn.innerText.toLowerCase().trim();
                    const label = (btn.getAttribute('aria-label') || '').toLowerCase();
                    if (text === 'done' || text === 'ok' || text === 'got it' ||
                        label.includes('dismiss') || label.includes('done')) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }''')

            if clicked:
                print("   ✅ Dismissed confirmation dialog via JavaScript")
                await asyncio.sleep(0.5)
                return True

        except Exception as e:
            print(f"   ⚠️ Could not dismiss confirmation: {e}")
        return False

    async def _is_external_application(self) -> bool:
        """Check if the job requires applying on external website."""
        try:
            # Use JavaScript to check for Easy Apply vs external Apply
            result = await self.controller.page.evaluate('''() => {
                // Check for Easy Apply button
                const easyApply = document.querySelector('button.jobs-apply-button--top-card');
                if (easyApply) {
                    const text = easyApply.innerText.toLowerCase();
                    if (text.includes('easy apply')) {
                        return { isExternal: false, reason: 'Easy Apply button found' };
                    }
                    if (text.includes('apply') && !text.includes('easy')) {
                        return { isExternal: true, reason: 'Apply button without Easy Apply' };
                    }
                }

                // Check all buttons
                const buttons = document.querySelectorAll('button');
                let hasEasyApply = false;
                let hasApply = false;

                for (const btn of buttons) {
                    const text = btn.innerText.toLowerCase();
                    if (text.includes('easy apply')) hasEasyApply = true;
                    if (text === 'apply' || text.includes('apply now')) hasApply = true;
                }

                if (hasApply && !hasEasyApply) {
                    return { isExternal: true, reason: 'Only Apply button, no Easy Apply' };
                }

                // Check for text indicators
                const pageText = document.body.innerText.toLowerCase();
                if (pageText.includes('apply on company website') ||
                    pageText.includes('apply on employer')) {
                    return { isExternal: true, reason: 'Text indicates external application' };
                }

                return { isExternal: false, reason: 'Easy Apply available' };
            }''')

            if result.get('isExternal'):
                print(f"🌐 External: {result.get('reason')}")
            return result.get('isExternal', False)
        except Exception as e:
            print(f"⚠️ Could not check application type: {e}")
            return False

    async def apply_external_job(self, max_steps: int = 40) -> bool:
        """Apply to a job on an external website using LinkedIn credentials."""
        print("🌐 External application detected - applying on company website...")

        # First, extract job description from LinkedIn page BEFORE clicking Apply
        job_description = ""
        try:
            job_description = await self.controller.page.evaluate('''() => {
                const desc = document.querySelector('.jobs-description__content, .jobs-box__html-content, #job-details');
                return desc ? desc.innerText.trim().substring(0, 3000) : '';
            }''')
            if job_description:
                print(f"📋 Extracted job description ({len(job_description)} chars)")
                self.current_job_description = job_description
        except Exception as e:
            print(f"⚠️ Could not extract job description: {e}")

        # Generate customized resume BEFORE going to external site
        resume_path = await self._generate_customized_resume()
        if resume_path:
            print(f"📄 Resume ready for upload: {Path(resume_path).name}")

        # Store reference to current page
        original_page = self.controller.page
        external_page = None

        # Track how many pages we start with
        initial_page_count = len(self.controller.context.pages)

        # Set up listener for new pages/tabs (will be removed after setup)
        new_pages_opened = []
        async def handle_new_page(page):
            nonlocal external_page
            external_page = page
            new_pages_opened.append(page)
            print("📑 New tab/popup detected!")

        self.controller.context.on("page", handle_new_page)

        # Click the Apply button to go to external site
        try:
            apply_btn = await self.controller.page.query_selector('button:has-text("Apply"):visible')
            if not apply_btn:
                # Try other selectors
                apply_btn = await self.controller.page.query_selector('.jobs-apply-button--top-card')
            if not apply_btn:
                apply_btn = await self.controller.page.query_selector('button[aria-label*="Apply"]')

            if apply_btn:
                # Use JS click to avoid timeout issues
                await self.controller.page.evaluate('(btn) => btn.click()', apply_btn)
                await asyncio.sleep(4)
            else:
                # Try clicking via JavaScript
                clicked = await self.controller.page.evaluate('''() => {
                    const btns = document.querySelectorAll('button');
                    for (const btn of btns) {
                        const text = btn.innerText.toLowerCase().trim();
                        if (text === 'apply' || text === 'apply now') {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }''')
                if clicked:
                    await asyncio.sleep(4)
                else:
                    print("⚠️ Could not find Apply button")
                    # Remove listener before returning
                    try:
                        self.controller.context.remove_listener("page", handle_new_page)
                    except:
                        pass
                    return False
        except Exception as e:
            print(f"⚠️ Error clicking Apply button: {e}")
            # Continue anyway - might have already opened

        # Remove the page listener to prevent duplicate tab handling
        try:
            self.controller.context.remove_listener("page", handle_new_page)
        except:
            pass

        # Wait a bit for new tab to open
        await asyncio.sleep(2)

        # Check if a new tab was opened
        all_pages = self.controller.context.pages
        if len(all_pages) > initial_page_count:
            # Close any duplicate tabs (keep only the newest external tab)
            if len(all_pages) > 2:
                print(f"   🧹 Cleaning up duplicate tabs (found {len(all_pages)} tabs)")
                for page in all_pages[1:-1]:  # Keep original and newest only
                    if page != original_page and page != all_pages[-1]:
                        try:
                            await page.close()
                        except:
                            pass
            # Switch to the newest page (external application site)
            external_page = self.controller.context.pages[-1]
            await external_page.bring_to_front()
            self.controller.page = external_page
            print(f"📑 Switched to external site: {external_page.url[:60]}...")
            # Re-inject overlay and action listener on new page
            await self._inject_pause_overlay()
            await self._setup_user_action_listener()
            await asyncio.sleep(2)
        elif external_page:
            await external_page.bring_to_front()
            self.controller.page = external_page
            print(f"📑 Switched to popup: {external_page.url[:60]}...")
            # Re-inject overlay and action listener on new page
            await self._inject_pause_overlay()
            await self._setup_user_action_listener()
            await asyncio.sleep(2)

        # Wait for page to fully load
        try:
            await self.controller.page.wait_for_load_state("domcontentloaded", timeout=10000)
        except:
            pass

        # Analyze initial page DOM to understand what we're dealing with
        print("🔍 Analyzing external site DOM...")
        analysis = await self._analyze_screenshot_with_llm(None, "What type of page is this and what should I click to start the job application?")
        if analysis:
            try:
                import json
                analysis_data = json.loads(analysis)

                # Check for blockers first
                blocker = analysis_data.get('blocker', 'none')
                if blocker and blocker not in ['none', 'null']:
                    print(f"   ⚠️ Blocker detected: {blocker}")
                    if blocker in ['login_required', 'account_creation', 'captcha', 'verification_code']:
                        if self.interactive:
                            user_help = await self._ask_user_for_external_help(None, self.controller.page.url)
                            if user_help.get('action') == 'skip':
                                await self._close_extra_tabs(original_page)
                                return False

                # Execute the recommended action using selector
                await self._execute_llm_action(analysis_data)

            except Exception as e:
                print(f"   ⚠️ Analysis parsing failed: {e}")

        # Try "Sign in with LinkedIn" if available (faster application)
        try:
            linkedin_signin = await self.controller.page.query_selector(
                'button:has-text("Sign in with LinkedIn"), '
                'a:has-text("Sign in with LinkedIn"), '
                'button:has-text("Apply with LinkedIn"), '
                'a:has-text("Apply with LinkedIn"), '
                '[data-automation-id*="linkedin"], '
                '[class*="linkedin-button"]'
            )
            if linkedin_signin:
                print("🔗 Found 'Sign in with LinkedIn' option - clicking...")
                await linkedin_signin.click()
                await asyncio.sleep(3)
                # LinkedIn OAuth popup may open - handle it
                all_pages = self.controller.context.pages
                if len(all_pages) > 1:
                    oauth_page = all_pages[-1]
                    await oauth_page.bring_to_front()
                    # Click "Allow" or similar on OAuth page
                    try:
                        allow_btn = await oauth_page.query_selector('button:has-text("Allow"), button:has-text("Authorize"), button[type="submit"]')
                        if allow_btn:
                            await allow_btn.click()
                            print("   ✅ Authorized LinkedIn OAuth")
                            await asyncio.sleep(2)
                    except:
                        pass
        except Exception as e:
            pass  # No LinkedIn sign-in option

        # Extract job description from external site if we didn't get it from LinkedIn
        if not job_description:
            try:
                job_description = await self.controller.page.evaluate('''() => {
                    const body = document.body.innerText;
                    return body.substring(0, 3000);
                }''')
                self.current_job_description = job_description
                print(f"📋 Extracted description from external site ({len(job_description)} chars)")
            except:
                pass

        goal = f"""
You are on an EXTERNAL COMPANY JOB WEBSITE. Apply to the job.

JOB: {self.current_job_title} at {self.current_company}

PROFILE DATA TO USE:
- first_name = "{self.user_profile['first_name']}"
- last_name = "{self.user_profile['last_name']}"
- email = "{self.user_profile['email']}"
- phone = "{self.user_profile['phone']}"
- location = "{self.user_profile['location']}"
- linkedin = "https://linkedin.com/in/muhammadkasim"

LOGIN CREDENTIALS (if a login is required):
- Email: {self.email}
- Password: {self.password}

WHAT TO DO:
1. Look for an "Apply" or "Apply Now" or "Start Application" button and CLICK IT
2. If you see a job description page, look for the Apply button
3. If you see a form, FILL OUT all the fields with profile data above
4. Click "Next", "Continue", "Submit", or any similar button
5. If login required, use the credentials above. If signup needed, use same email/password.
6. If you see "Application submitted" or "Thank you" message, respond with "done"

CRITICAL - DO NOT RETURN "error":
- If you see ANY buttons (Apply, Next, Submit, Continue) - CLICK THEM
- If you see ANY form fields - FILL THEM
- If the page is loading, use action "wait"
- If you need to scroll to see more, use action "scroll"
- ONLY return "error" if the page shows "Page not found" or similar error message

COMMON BUTTON TEXTS TO CLICK:
- "Apply", "Apply Now", "Apply for this job"
- "Submit", "Submit Application"
- "Next", "Continue", "Proceed"
- "Sign In", "Log In", "Create Account"
"""

        last_url = ""
        stuck_count = 0
        last_actions_ext = []  # Track last actions to detect loops
        max_repeated_actions = 4  # Max times to repeat same action before giving up

        for step in range(max_steps):
            # Check for user intervention request (keyboard shortcut)
            await self._check_user_intervention_request()

            # Check if access is blocked - if so, skip immediately
            is_blocked, block_reason = await self._check_if_blocked()
            if is_blocked:
                print(f"\n🚫 ACCESS BLOCKED: {block_reason}")
                print("   ⏭️ Skipping this application and moving to next job...")
                await self._close_extra_tabs(original_page)
                return False

            print(f"\n--- External Step {step + 1}/{max_steps} ---")

            try:
                # Check if URL changed (page navigated)
                current_url = self.controller.page.url
                if current_url != last_url:
                    print(f"📍 Page: {current_url[:70]}...")
                    last_url = current_url
                    stuck_count = 0
                    # Wait for page to load when URL changes
                    try:
                        await self.controller.page.wait_for_load_state("networkidle", timeout=5000)
                    except:
                        await asyncio.sleep(2)

                    # Check if this is a Workday site and handle specially
                    if await self._is_workday_site():
                        print("🏢 Detected Workday application site")
                        filled = await self._fill_workday_form()
                        if filled:
                            stuck_count = 0
                            continue
                else:
                    stuck_count += 1

                # Try Workday form filling if stuck
                if stuck_count >= 2 and await self._is_workday_site():
                    print("🏢 Trying Workday-specific form filling...")
                    filled = await self._fill_workday_form()
                    if filled:
                        stuck_count = 0
                        continue

                # If stuck on same page too long, try filling EEO fields or scrolling
                if stuck_count >= 5:
                    # Check if this is a voluntary self-identification / EEO page
                    page_text = await self.controller.page.inner_text('body')
                    page_text_lower = page_text.lower()
                    is_eeo_page = any(term in page_text_lower for term in [
                        'voluntary self-identification', 'self-identification', 'eeo',
                        'equal employment', 'gender identity', 'race/ethnicity',
                        'veteran status', 'disability status', 'demographic'
                    ])

                    if is_eeo_page:
                        print("📋 Detected EEO/Self-Identification page - filling fields...")
                        filled = await self._fill_external_eeo_fields()
                        if filled:
                            stuck_count = 0
                            # Try to submit/continue after filling EEO
                            submit_btn = await self.controller.page.query_selector(
                                'button[type="submit"], button:has-text("Submit"), button:has-text("Continue"), '
                                'button:has-text("Next"), input[type="submit"]'
                            )
                            if submit_btn:
                                try:
                                    await submit_btn.click()
                                    print("   ✅ Clicked submit/continue button")
                                    await asyncio.sleep(2)
                                except:
                                    pass
                            continue

                    print("⚠️ Seems stuck on this page, scrolling down...")
                    await self.controller.page.evaluate("window.scrollBy(0, 300)")
                    await asyncio.sleep(1)
                    stuck_count = 0

                # Wait a bit for dynamic content to load
                await asyncio.sleep(1)

                # Handle cookie consent popups on external sites
                try:
                    cookie_btns = await self.controller.page.query_selector_all('button, [role="button"], a')
                    for btn in cookie_btns[:20]:  # Check first 20 buttons
                        text = await btn.inner_text()
                        text_lower = text.lower().strip()
                        if text_lower in ['allow', 'accept', 'accept all', 'allow all', 'agree', 'ok', 'got it', 'i agree', 'accept cookies']:
                            print(f"🍪 Dismissing cookie popup: '{text}'")
                            await btn.click()
                            await asyncio.sleep(1)
                            break
                except Exception as e:
                    pass  # No cookie popup or already dismissed

                page_context = await get_page_context(self.controller.page)

                # If no elements found, take full-page screenshot and analyze
                if "No interactive elements found" in page_context:
                    print("⏳ Waiting for page elements to load...")
                    print(f"📄 Page context preview:\n{page_context[:500]}")

                    # Analyze DOM with LLM and execute suggested action
                    print("🔍 Analyzing page DOM...")
                    analysis = await self._analyze_screenshot_with_llm(None, "What should I click to proceed with the job application?")
                    if analysis:
                        try:
                            import json
                            analysis_data = json.loads(analysis)

                            # Execute LLM recommendation using selector
                            if await self._execute_llm_action(analysis_data):
                                stuck_count = 0
                                continue  # Re-analyze after action
                        except Exception as e:
                            print(f"   ⚠️ Analysis error: {e}")

                    # FALLBACK: Try learned pattern from previous user demonstrations
                    print("🧠 Trying learned patterns as fallback...")
                    dom_info = await self._extract_dom_structure()
                    if await self._try_learned_pattern(dom_info):
                        print("   ✅ Learned pattern applied successfully!")
                        stuck_count = 0
                        await asyncio.sleep(2)
                        continue

                    await asyncio.sleep(3)
                    page_context = await get_page_context(self.controller.page)

            except Exception as e:
                print(f"⚠️ Page error: {e}")
                # Try to switch back to original page
                try:
                    self.controller.page = original_page
                except:
                    pass
                return False

            # Try to upload resume if there's a file input
            try:
                file_input = await self.controller.page.query_selector('input[type="file"]')
                if file_input and resume_path:
                    await file_input.set_input_files(resume_path)
                    print(f"📎 Uploaded resume: {Path(resume_path).name}")
                    await asyncio.sleep(1)
            except Exception as e:
                pass  # No file input or already uploaded

            action = await get_next_action(
                goal=goal,
                page_context=page_context,
                user_profile=self.user_profile,
                history=self.action_history[-5:]
            )

            print(f"🎯 Action: {action.action_type} | {action.reason}")

            # Track action for loop detection
            action_key = f"{action.action_type}:{action.element_index}:{action.reason[:50]}"
            last_actions_ext.append(action_key)
            if len(last_actions_ext) > max_repeated_actions:
                last_actions_ext.pop(0)

            # Check for repeated actions (loop detection)
            if len(last_actions_ext) >= max_repeated_actions:
                if len(set(last_actions_ext)) == 1:
                    print(f"\n⚠️ Detected loop: same action repeated {max_repeated_actions} times")
                    print(f"   Action: {action.reason}")

                    # Analyze DOM to find correct button
                    print("🔍 Analyzing DOM to find correct button...")
                    analysis = await self._analyze_screenshot_with_llm(None, "The bot is stuck in a loop. What is the correct button to click?")
                    if analysis:
                        try:
                            import json
                            analysis_data = json.loads(analysis)

                            # Execute LLM recommendation using selector
                            if await self._execute_llm_action(analysis_data):
                                last_actions_ext.clear()
                                continue
                        except:
                            pass

                    # FALLBACK: Try learned pattern from previous user demonstrations
                    print("🧠 Trying learned patterns as fallback...")
                    dom_info = await self._extract_dom_structure()
                    if await self._try_learned_pattern(dom_info):
                        print("   ✅ Learned pattern applied successfully!")
                        last_actions_ext.clear()
                        await asyncio.sleep(2)
                        continue

                    # If analysis and learned patterns didn't help, ask user interactively
                    if self.interactive:
                        # Capture screenshot for user help
                        ext_screenshot_path = f"screenshots/external_help_{step}.png"
                        try:
                            await self.controller.page.screenshot(path=ext_screenshot_path, full_page=True)
                        except:
                            ext_screenshot_path = None
                        user_help = await self._ask_user_for_external_help(ext_screenshot_path, current_url)
                        if user_help.get('action') == 'click' and user_help.get('value'):
                            # User told us what to click
                            btn_text = user_help.get('value')
                            btn = await self.controller.page.query_selector(f'button:has-text("{btn_text}"), a:has-text("{btn_text}"), [role="button"]:has-text("{btn_text}")')
                            if btn:
                                print(f"   ✅ Clicking user-specified button: '{btn_text}'")
                                await btn.click()
                                await asyncio.sleep(2)
                                last_actions_ext.clear()
                                continue
                            else:
                                print(f"   ⚠️ Could not find button with text: '{btn_text}'")
                        elif user_help.get('action') == 'continue':
                            # User handled it manually
                            last_actions_ext.clear()
                            continue
                        elif user_help.get('action') == 'skip':
                            print("   ⏭️ User requested skip")
                            await self._close_extra_tabs(original_page)
                            return False
                    else:
                        # Non-interactive: Use learning system to watch and learn
                        print("🧠 Pausing for manual intervention (learning enabled)...")
                        dom_before = await self._extract_dom_structure()
                        user_actions = await self._pause_for_user_intervention("Stuck on external site", 30)
                        if user_actions:
                            # Pattern was learned, continue
                            last_actions_ext.clear()
                            continue

                    # Check if page changed
                    if self.controller.page.url != current_url:
                        print("✅ Page changed, continuing...")
                        last_actions_ext.clear()
                        continue
                    print("❌ Stuck in loop, skipping this application")
                    # Close external tabs and switch back to original page
                    await self._close_extra_tabs(original_page)
                    return False

            if action.action_type == "done":
                print("\n✅ EXTERNAL APPLICATION SUBMITTED!")
                # Click OK/Done to dismiss confirmation dialog
                await self._dismiss_application_confirmation()
                # Close external tabs and switch back to original LinkedIn page
                await self._close_extra_tabs(original_page)
                return True

            if action.action_type == "error":
                print(f"\n🛑 Bot stuck: {action.reason}")

                # Analyze DOM to find the right action
                print("🔍 Analyzing DOM to find a way forward...")
                analysis = await self._analyze_screenshot_with_llm(None, f"Bot error: {action.reason}. What should I do?")
                if analysis:
                    try:
                        import json
                        analysis_data = json.loads(analysis)

                        # Execute LLM recommendation using selector
                        if await self._execute_llm_action(analysis_data):
                            continue
                    except:
                        pass

                # FALLBACK: Try learned pattern from previous user demonstrations
                print("🧠 Trying learned patterns as fallback...")
                dom_info = await self._extract_dom_structure()
                if await self._try_learned_pattern(dom_info):
                    print("   ✅ Learned pattern applied successfully!")
                    await asyncio.sleep(2)
                    continue

                # If analysis and learned patterns didn't help, ask user interactively
                if self.interactive:
                    user_help = await self._ask_user_for_external_help(None, current_url)
                    if user_help.get('action') == 'click' and user_help.get('value'):
                        btn_text = user_help.get('value')
                        btn = await self.controller.page.query_selector(f'button:has-text("{btn_text}"), a:has-text("{btn_text}"), [role="button"]:has-text("{btn_text}")')
                        if btn:
                            print(f"   ✅ Clicking user-specified button: '{btn_text}'")
                            await btn.click()
                            await asyncio.sleep(2)
                            continue
                    elif user_help.get('action') == 'continue':
                        continue
                    elif user_help.get('action') == 'skip':
                        print("   ⏭️ User requested skip")
                        await self._close_extra_tabs(original_page)
                        return False
                else:
                    # Non-interactive: Use learning system to watch and learn
                    print("🧠 Pausing for manual intervention (learning enabled)...")
                    user_actions = await self._pause_for_user_intervention("Bot error on external site", 30)
                    if user_actions:
                        # Pattern was learned, continue
                        continue

                # Check if page changed
                if self.controller.page.url != current_url:
                    print("✅ Page changed, continuing...")
                    continue
                print("❌ No progress, giving up on this application")
                # Close external tabs and switch back to original page
                await self._close_extra_tabs(original_page)
                return False

            await self.controller.execute_action(action)
            await asyncio.sleep(2)

            # Check if a new tab opened after the action and handle it
            all_pages = self.controller.context.pages
            if len(all_pages) > 2:  # More than original + current external tab
                print(f"   🧹 New tabs detected ({len(all_pages)} total), cleaning up...")
                # Close duplicate tabs, keep only the original LinkedIn and current working tab
                current_external = self.controller.page
                for page in list(all_pages):
                    if page != original_page and page != current_external:
                        try:
                            # Check if this is a newer page we should switch to
                            if page != all_pages[-1]:
                                await page.close()
                            else:
                                # Switch to the newest page
                                await page.bring_to_front()
                                self.controller.page = page
                                print(f"   📑 Switched to new page: {page.url[:50]}...")
                        except:
                            pass

        # Max steps reached - close external tabs and switch back to LinkedIn
        await self._close_extra_tabs(original_page)
        return False

    async def apply_to_job(self, max_steps: int = 30) -> bool:
        """Apply to the current job using LLM-guided automation."""

        goal = f"""
Apply to this job using Easy Apply.

PROFILE DATA - USE THESE EXACT VALUES:
- first_name = "{self.user_profile['first_name']}"
- last_name = "{self.user_profile['last_name']}"
- email = "{self.user_profile['email']}"
- phone = "{self.user_profile['phone']}"
- location = "{self.user_profile['location']}"
- years_experience = "{self.user_profile['years_experience']}"

FIELD MATCHING - VERY IMPORTANT:
- Field labeled "First name" or "first name" → type "{self.user_profile['first_name']}" (NOT phone!)
- Field labeled "Last name" or "last name" → type "{self.user_profile['last_name']}"
- Field labeled "Phone" or "Mobile" → type "{self.user_profile['phone']}"
- Field labeled "Email" → type "{self.user_profile['email']}"
- Field labeled "City" or "Location" → type "{self.user_profile['location']}"

Steps:
1. Click "Easy Apply" button if visible
2. Fill EMPTY required fields matching FIELD labels to PROFILE values above
3. Click "Next" or "Continue" to progress
4. BEFORE clicking Submit: UNCHECK the "Follow [company]" checkbox
5. Click "Submit application" at the end
6. If you see "Application sent" or success message → respond with "done"

CRITICAL:
- READ the field label/placeholder BEFORE typing
- Put the RIGHT value in the RIGHT field
- Phone number goes ONLY in phone field, NOT in name fields!
"""

        last_actions = []  # Track last few actions to detect loops
        consecutive_failures = 0  # Track consecutive action failures

        resume_uploaded = False

        # Setup user action listener for learning
        await self._setup_user_action_listener()

        for step in range(max_steps):
            # Check for user intervention request (keyboard shortcut)
            await self._check_user_intervention_request()

            print(f"\n--- Step {step + 1}/{max_steps} ---")

            try:
                page_context = await get_page_context(self.controller.page)
            except Exception as e:
                print(f"⚠️ Browser closed or page error: {e}")
                return False

            # Check if there's a resume upload section and we haven't uploaded yet
            if not resume_uploaded and ("resume" in page_context.lower() or "upload" in page_context.lower()):
                uploaded = await self._upload_resume()
                if uploaded:
                    resume_uploaded = True
                    await asyncio.sleep(1)

            # Try to apply learned fixes first
            if consecutive_failures >= 2 or (last_actions and len(set(last_actions[-3:])) == 1):
                applied = await self._apply_learned_fixes(page_context)
                if applied:
                    consecutive_failures = 0
                    last_actions.clear()
                    await asyncio.sleep(1)
                    continue

            # Proactively check for EEO/self-identification page and fill it BEFORE LLM tries
            page_context_lower = page_context.lower()
            is_eeo_page = any(term in page_context_lower for term in [
                'voluntary self-identification', 'self-identification', 'equal employment',
                'gender identity', 'race/ethnicity', 'veteran status', 'disability status',
                'demographic information', 'eeo survey'
            ])

            if is_eeo_page:
                print("📋 Detected EEO/Self-Identification page - filling fields proactively...")
                filled = await self._fill_all_eeo_dropdowns()
                if filled:
                    await asyncio.sleep(1)
                    # Try to click Next/Continue after filling
                    next_btn = await self.controller.page.query_selector(
                        'button:has-text("Next"), button:has-text("Continue"), button:has-text("Review"), button:has-text("Submit")'
                    )
                    if next_btn:
                        is_disabled = await next_btn.get_attribute('disabled')
                        aria_disabled = await next_btn.get_attribute('aria-disabled')
                        if not is_disabled and aria_disabled != 'true':
                            await next_btn.click()
                            print("   ✅ Clicked Next after EEO page")
                            await asyncio.sleep(1.5)
                            continue  # Skip LLM for this step

            # Proactively check for Additional Questions page and fill it BEFORE LLM tries
            is_additional_questions = any(term in page_context_lower for term in [
                'additional questions', 'additional information', 'screening questions',
                'how many years', 'years of experience', 'authorized to work',
                'work authorization', 'do you have', 'are you', 'willing to'
            ])

            if is_additional_questions:
                print("📝 Detected Additional Questions page - filling fields proactively...")
                filled = await self._fill_additional_questions()
                if filled:
                    await asyncio.sleep(0.5)
                    # Try to click Next/Continue after filling
                    next_btn = await self.controller.page.query_selector(
                        'button:has-text("Next"), button:has-text("Continue"), button:has-text("Review"), button:has-text("Submit")'
                    )
                    if next_btn:
                        is_disabled = await next_btn.get_attribute('disabled')
                        aria_disabled = await next_btn.get_attribute('aria-disabled')
                        if not is_disabled and aria_disabled != 'true':
                            await next_btn.click()
                            print("   ✅ Clicked Next after Additional Questions")
                            await asyncio.sleep(1.5)
                            continue  # Skip LLM for this step

            action = await get_next_action(
                goal=goal,
                page_context=page_context,
                user_profile=self.user_profile,
                history=self.action_history[-5:]  # Only last 5 actions
            )

            # Detect loops - if same action repeated 3+ times, try something else
            action_key = f"{action.action_type}:{action.element_index}"
            last_actions.append(action_key)
            if len(last_actions) > 5:
                last_actions.pop(0)

            if len(last_actions) >= 3 and len(set(last_actions[-3:])) == 1:
                print("⚠️ Detected loop, trying to break out...")
                await self._capture_debug_screenshot(f"loop_{step}")

                # FIRST: Try to fill additional questions (text inputs, radios, dropdowns)
                print("📝 Attempting to fill additional questions...")
                filled_questions = await self._fill_additional_questions()
                if filled_questions:
                    last_actions.clear()
                    await asyncio.sleep(0.5)
                    # Try clicking Next after filling questions
                    next_btn = await self.controller.page.query_selector('button:has-text("Next"), button:has-text("Review"), button:has-text("Continue")')
                    if next_btn:
                        is_disabled = await next_btn.get_attribute('disabled')
                        aria_disabled = await next_btn.get_attribute('aria-disabled')
                        if not is_disabled and aria_disabled != 'true':
                            try:
                                await next_btn.click(timeout=3000)
                                print("   ✅ Clicked Next after filling questions")
                                await asyncio.sleep(1)
                            except:
                                pass
                    continue

                # Check if we're on an EEO page with dropdowns - fill them all at once
                if 'gender' in page_context.lower() or 'veteran' in page_context.lower() or 'disability' in page_context.lower():
                    print("📋 Detected EEO page - filling all dropdowns and checkboxes...")
                    filled = await self._fill_all_eeo_dropdowns()
                    last_actions.clear()
                    await asyncio.sleep(1)

                    # Always try clicking Next/Review/Submit after EEO page handling
                    next_btn = await self.controller.page.query_selector('button:has-text("Next"), button:has-text("Review"), button:has-text("Submit")')
                    if next_btn:
                        # Check if button is enabled
                        is_disabled = await next_btn.get_attribute('disabled')
                        aria_disabled = await next_btn.get_attribute('aria-disabled')
                        if is_disabled or aria_disabled == 'true':
                            print("   ⚠️ Next button is disabled - there may be unfilled required fields")
                            # Try to find and fill any remaining required fields
                            required_fields = await self.controller.page.query_selector_all('[required], [aria-required="true"]')
                            print(f"   📋 Found {len(required_fields)} required fields")
                            for field in required_fields:
                                tag = await field.evaluate('el => el.tagName.toLowerCase()')
                                value = await field.input_value() if tag in ['input', 'textarea'] else ''
                                if not value:
                                    name = await field.get_attribute('name') or await field.get_attribute('aria-label') or ''
                                    print(f"   ⚠️ Empty required field: {name}")
                        else:
                            try:
                                await next_btn.click(timeout=3000)
                                print("   ✅ Clicked Next/Review button")
                                await asyncio.sleep(1)
                            except Exception as e:
                                print(f"   ⚠️ Failed to click Next: {e}")
                    continue

                # First, try applying learned fixes
                applied = await self._apply_learned_fixes(page_context)
                if applied:
                    last_actions.clear()
                    await asyncio.sleep(1)
                    continue

                # Try clicking Next/Submit/Review button directly with retry logic
                found_button = False
                for btn_text in ["Submit application", "Submit", "Review", "Next", "Continue"]:
                    btn = await self.controller.page.query_selector(f'button:has-text("{btn_text}")')
                    if btn:
                        try:
                            # Uncheck follow company before submit
                            if "Submit" in btn_text:
                                await self._uncheck_follow_company()

                            # Retry click with DOM re-query to handle detachment
                            for retry in range(3):
                                try:
                                    # Re-query the button to get fresh reference
                                    btn = await self.controller.page.query_selector(f'button:has-text("{btn_text}")')
                                    if btn:
                                        await btn.click(timeout=3000)
                                        await asyncio.sleep(1)
                                        last_actions.clear()
                                        found_button = True
                                        break
                                except Exception as e:
                                    if retry < 2:
                                        await asyncio.sleep(0.5)
                                        continue
                                    # Try JavaScript click as last resort
                                    try:
                                        await self.controller.page.evaluate(f'''() => {{
                                            const btn = document.querySelector('button');
                                            const buttons = Array.from(document.querySelectorAll('button'));
                                            const target = buttons.find(b => b.innerText.includes("{btn_text}"));
                                            if (target) target.click();
                                        }}''')
                                        await asyncio.sleep(1)
                                        found_button = True
                                    except:
                                        pass
                            if found_button:
                                break
                        except:
                            pass

                # If still stuck, pause for user intervention
                if not found_button:
                    user_actions = await self._pause_for_user_intervention(
                        reason=f"Stuck in loop: {action.reason}",
                        pause_seconds=5
                    )
                    if user_actions:
                        last_actions.clear()
                        consecutive_failures = 0
                        continue

                # If stuck for too long (10+ loops), check if we're done or dismiss
                if not found_button and step > 25:
                    # Check if application was submitted
                    page_text = await self.controller.page.inner_text("body")
                    if "application sent" in page_text.lower() or "application submitted" in page_text.lower():
                        print("\n✅ APPLICATION SUBMITTED!")
                        await self._dismiss_application_confirmation()
                        return True
                    # Dismiss modal and move on
                    dismiss_btn = await self.controller.page.query_selector('[aria-label="Dismiss"], button:has-text("Discard")')
                    if dismiss_btn:
                        await dismiss_btn.click()
                        print("⚠️ Modal dismissed - stuck in loop")
                        return False
                continue

            self.action_history.append({
                "step": step + 1,
                "action": action.action_type,
                "reason": action.reason
            })

            print(f"🎯 Action: {action.action_type} | {action.reason}")

            if action.action_type == "done":
                print("\n✅ APPLICATION SUBMITTED!")
                # Click the "Done" or "OK" button to dismiss the confirmation dialog
                await self._dismiss_application_confirmation()
                return True

            # Before submitting or reviewing, ALWAYS try to uncheck "Follow company" checkbox
            if "submit" in action.reason.lower() or "review" in action.reason.lower():
                await self._uncheck_follow_company()

            if action.action_type == "error":
                # Capture screenshot for debugging
                await self._capture_debug_screenshot(f"error_{step}")
                # Pause for user to help
                user_actions = await self._pause_for_user_intervention(
                    reason=f"Bot error: {action.reason}",
                    pause_seconds=5
                )
                if user_actions:
                    consecutive_failures = 0
                    continue
                print(f"\n❌ Cannot proceed: {action.reason}")
                return False

            success = await self.controller.execute_action(action)

            # If action failed, pause for user intervention
            if not success:
                consecutive_failures += 1
                if last_actions:
                    last_actions.pop()

                # After 2 consecutive failures, ask user for help
                if consecutive_failures >= 2:
                    user_actions = await self._pause_for_user_intervention(
                        reason=f"Action failed: {action.reason}",
                        pause_seconds=5
                    )
                    if user_actions:
                        consecutive_failures = 0
                        continue
            else:
                consecutive_failures = 0

            # Add delay to avoid rate limiting on Cerebras API
            await asyncio.sleep(2)

        return False
    
    async def run(self, keywords: str, location: str = "", max_applications: int = 5):
        """Run the LinkedIn job application bot."""

        print(f"\n{'='*60}")
        print("🤖 LINKEDIN JOB APPLICATION BOT")
        print(f"{'='*60}")
        print(f"🔍 Keywords: {keywords}")
        print(f"📍 Location: {location or 'Any'}")
        print(f"📝 Max applications: {max_applications}")
        print(f"{'='*60}\n")

        # Start keyboard listener for user intervention
        start_keyboard_listener()

        await self.controller.start()

        # Setup auto-inject for pause overlay (runs on every page load)
        await self._setup_overlay_auto_inject()

        try:
            # Login
            if not await self.login():
                print("❌ Login failed")
                return

            # Setup user action listener for learning
            await self._setup_user_action_listener()

            # Inject pause overlay button in browser (immediate injection)
            await self._inject_pause_overlay()

            # Search for jobs
            await self.search_jobs(keywords, location)

            print("\n🎯 Starting automatic job applications...")
            print("="*60)
            print("🎛️  TO TAKE CONTROL:")
            print("   • Click the ⏸️ PAUSE BOT button in the browser")
            print("   • Or press 'i' on your keyboard")
            print("   • Press Ctrl+C to stop completely")
            print("="*60)

            applications_submitted = 0
            for i in range(max_applications):
                # Check for user intervention request
                await self._check_user_intervention_request()

                print(f"\n{'='*50}")
                print(f"📝 Application {i+1}/{max_applications}")
                print(f"{'='*50}")

                # Click on a job listing
                job_clicked = await self.click_next_job()
                if not job_clicked:
                    print("⚠️ No more jobs to click")
                    break

                await asyncio.sleep(2)

                # Check for user intervention request
                await self._check_user_intervention_request()

                # Extract job details for resume customization (need this early to track the job)
                await self._extract_job_details()

                # Track this job as visited (even if it fails or is skipped, to avoid retrying)
                job_key = f"{self.current_job_title or 'Unknown'} at {self.current_company or 'Unknown'}"
                if job_key in self.applied_jobs:
                    print(f"⏭️ Already tried this job, skipping: {job_key}")
                    continue
                self.applied_jobs.add(job_key)

                # Check for "missing required qualifications" warning - skip these jobs
                try:
                    missing_quals = await self.controller.page.evaluate('''() => {
                        const pageText = document.body.innerText.toLowerCase();
                        if (pageText.includes('your profile is missing required qualifications') ||
                            pageText.includes('missing required qualifications') ||
                            pageText.includes('profile is missing qualifications')) {
                            return true;
                        }
                        // Also check for specific warning elements
                        const warnings = document.querySelectorAll('[class*="qualification"], [class*="warning"], [class*="alert"]');
                        for (const el of warnings) {
                            if (el.innerText.toLowerCase().includes('missing') &&
                                el.innerText.toLowerCase().includes('qualification')) {
                                return true;
                            }
                        }
                        return false;
                    }''')
                    if missing_quals:
                        print("⏭️ Skipping job - Your profile is missing required qualifications")
                        # Click the X button to dismiss this job so it won't show again
                        try:
                            dismissed = await self.controller.page.evaluate('''() => {
                                // Find the X/dismiss button on the job card or job details panel
                                const dismissSelectors = [
                                    'button[aria-label*="Dismiss"]',
                                    'button[aria-label*="dismiss"]',
                                    'button[aria-label*="Remove"]',
                                    'button[aria-label*="remove"]',
                                    'button[aria-label*="Hide"]',
                                    'button[aria-label*="hide"]',
                                    '.job-card-container button[aria-label*="Dismiss"]',
                                    '.jobs-details-top-card button[aria-label*="Dismiss"]',
                                    '[data-job-id] button[aria-label*="Dismiss"]',
                                    'button.artdeco-button--circle[aria-label*="Dismiss"]',
                                    'button svg[data-test-icon="close-small"]',
                                    'button:has(svg[data-test-icon="close"])'
                                ];

                                for (const selector of dismissSelectors) {
                                    const btn = document.querySelector(selector);
                                    if (btn) {
                                        btn.click();
                                        return true;
                                    }
                                }

                                // Try to find X button near the job title
                                const jobCard = document.querySelector('.jobs-details-top-card, .job-card-container--selected, [class*="job-card"][class*="selected"]');
                                if (jobCard) {
                                    const closeBtn = jobCard.querySelector('button[aria-label*="ismiss"], button[aria-label*="emove"], button[aria-label*="lose"]');
                                    if (closeBtn) {
                                        closeBtn.click();
                                        return true;
                                    }
                                }
                                return false;
                            }''')
                            if dismissed:
                                print("   ❌ Dismissed job from list")
                                await asyncio.sleep(1)
                        except Exception as e:
                            pass  # Continue even if dismiss fails
                        continue
                except:
                    pass  # Continue if check fails

                # Generate customized resume based on job description
                await self._generate_customized_resume()

                # Check if it's an external application or Easy Apply
                is_external = await self._is_external_application()

                if is_external:
                    # Apply on external website
                    success = await self.apply_external_job()
                else:
                    # Use Easy Apply
                    success = await self.apply_to_job()

                if success:
                    applications_submitted += 1
                    print(f"✅ Application {applications_submitted} submitted!")
                else:
                    print("⚠️ Could not complete this application, moving to next...")

                await asyncio.sleep(2)

            print(f"\n{'='*50}")
            print(f"🎉 COMPLETED: {applications_submitted} applications submitted")
            print(f"{'='*50}")

        except KeyboardInterrupt:
            print("\n👋 Stopping...")
        finally:
            stop_keyboard_listener()
            await self.controller.stop()


async def main():
    """Main entry point."""
    keywords = sys.argv[1] if len(sys.argv) > 1 else "Software Engineer"
    location = sys.argv[2] if len(sys.argv) > 2 else "San Jose, CA"

    agent = LinkedInAgent()
    await agent.run(keywords=keywords, location=location)


if __name__ == "__main__":
    asyncio.run(main())

