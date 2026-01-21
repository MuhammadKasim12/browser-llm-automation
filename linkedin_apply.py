"""
LinkedIn Job Application Automation
Logs into LinkedIn and applies to jobs using Easy Apply.
Integrates resume customization based on job description.
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from browser_controller import BrowserController
from llm_planner import get_next_action
from dom_extractor import get_page_context

# Add resume generator to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'resume-generator-mobile'))

load_dotenv()


class LinkedInAgent:
    """LinkedIn-specific job application agent."""

    def __init__(self):
        self.controller = BrowserController(headless=False, slow_mo=150)
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

    async def _capture_debug_screenshot(self, label: str = "debug") -> str:
        """Capture a screenshot for debugging purposes."""
        self.screenshot_counter += 1
        # Sanitize label for filename
        safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)[:30]
        filename = f"{self.screenshot_counter:03d}_{safe_label}.png"
        filepath = self.screenshots_dir / filename
        try:
            await self.controller.page.screenshot(path=str(filepath), full_page=False, timeout=5000)
            print(f"📸 Screenshot saved: {filename}")
            return str(filepath)
        except Exception as e:
            print(f"⚠️ Screenshot skipped: {str(e)[:50]}")
            return ""

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
            # Try to find any existing resume
            default_resume = Path(__file__).parent.parent / 'resume-generator-mobile' / 'resumes' / 'mkasim_fullstack-resume.pdf'
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
        """Set up JavaScript listeners to capture user actions in the browser."""
        await self.controller.page.evaluate('''() => {
            window._userActions = [];

            // Listen for clicks
            document.addEventListener('click', (e) => {
                const el = e.target;
                const action = {
                    type: 'click',
                    tag: el.tagName,
                    text: (el.innerText || '').substring(0, 100),
                    id: el.id,
                    className: el.className,
                    name: el.getAttribute('name') || '',
                    placeholder: el.getAttribute('placeholder') || '',
                    timestamp: Date.now()
                };
                window._userActions.push(action);
                console.log('User click:', action);
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
                    timestamp: Date.now()
                };
                window._userActions.push(action);
                console.log('User input:', action);
            }, true);

            // Listen for select changes
            document.addEventListener('change', (e) => {
                const el = e.target;
                if (el.tagName === 'SELECT') {
                    const action = {
                        type: 'select',
                        tag: el.tagName,
                        value: el.value,
                        selectedText: el.options[el.selectedIndex]?.text || '',
                        id: el.id,
                        name: el.getAttribute('name') || '',
                        timestamp: Date.now()
                    };
                    window._userActions.push(action);
                    console.log('User select:', action);
                }
            }, true);
        }''')

    async def _get_user_actions(self):
        """Get user actions captured since last check."""
        try:
            actions = await self.controller.page.evaluate('() => { const a = window._userActions || []; window._userActions = []; return a; }')
            return actions
        except:
            return []

    async def _pause_for_user_intervention(self, reason: str, pause_seconds: int = 5) -> list:
        """Pause and let user intervene, then capture what they did."""
        print(f"\n🛑 PAUSED: {reason}")
        print(f"⏸️  You have {pause_seconds} seconds to manually fix this...")
        print("   (The bot will watch and learn from your actions)")

        # Clear any previous user actions
        await self._get_user_actions()

        # Wait and let user interact
        await asyncio.sleep(pause_seconds)

        # Capture what user did
        user_actions = await self._get_user_actions()

        if user_actions:
            print(f"👀 Observed {len(user_actions)} user action(s):")
            for action in user_actions:
                if action['type'] == 'click':
                    print(f"   - Click: {action.get('text', '')[:50]} ({action.get('tag')})")
                elif action['type'] == 'type':
                    print(f"   - Type: '{action.get('value', '')[:30]}' in {action.get('placeholder', action.get('name', 'field'))}")
                elif action['type'] == 'select':
                    print(f"   - Select: '{action.get('selectedText', '')}' from dropdown")

            # Store for learning
            self.user_interventions.append({
                "reason": reason,
                "actions": user_actions,
                "page_url": self.controller.page.url
            })
            print("✅ Learned from your actions! Will apply to future applications.")
        else:
            print("   (No user actions detected)")

        return user_actions

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

        # Set up listener for new pages/tabs
        async def handle_new_page(page):
            nonlocal external_page
            external_page = page
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
                    return False
        except Exception as e:
            print(f"⚠️ Error clicking Apply button: {e}")
            # Continue anyway - might have already opened

        # Wait a bit for new tab to open
        await asyncio.sleep(2)

        # Check if a new tab was opened
        all_pages = self.controller.context.pages
        if len(all_pages) > 1:
            # Switch to the newest page (external application site)
            external_page = all_pages[-1]
            await external_page.bring_to_front()
            self.controller.page = external_page
            print(f"📑 Switched to external site: {external_page.url[:60]}...")
            await asyncio.sleep(2)
        elif external_page:
            await external_page.bring_to_front()
            self.controller.page = external_page
            print(f"📑 Switched to popup: {external_page.url[:60]}...")
            await asyncio.sleep(2)

        # Wait for page to fully load
        try:
            await self.controller.page.wait_for_load_state("domcontentloaded", timeout=10000)
        except:
            pass

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
                else:
                    stuck_count += 1

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

                # If no elements found, wait and retry
                if "No interactive elements found" in page_context:
                    print("⏳ Waiting for page elements to load...")
                    print(f"📄 Page context preview:\n{page_context[:800]}")
                    await self._capture_debug_screenshot(f"ext_no_elements_{step}")
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
                    await self._capture_debug_screenshot(f"ext_loop_{step}")
                    print("⏸️  You have 10 seconds to manually help...")
                    await asyncio.sleep(10)
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
                # Close external tabs and switch back to original LinkedIn page
                await self._close_extra_tabs(original_page)
                return True

            if action.action_type == "error":
                # Don't give up immediately - wait for user intervention
                print(f"\n🛑 Bot stuck: {action.reason}")
                await self._capture_debug_screenshot(f"ext_error_{step}")
                print("⏸️  You have 10 seconds to manually help...")
                await asyncio.sleep(10)
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
        
        await self.controller.start()

        try:
            # Login
            if not await self.login():
                print("❌ Login failed")
                return

            # Setup user action listener for learning
            await self._setup_user_action_listener()

            # Search for jobs
            await self.search_jobs(keywords, location)

            print("\n🎯 Starting automatic job applications...")
            print("💡 TIP: If the bot gets stuck, you can manually intervene - it will learn from your actions!")

            applications_submitted = 0
            for i in range(max_applications):
                print(f"\n{'='*50}")
                print(f"📝 Application {i+1}/{max_applications}")
                print(f"{'='*50}")

                # Click on a job listing
                job_clicked = await self.click_next_job()
                if not job_clicked:
                    print("⚠️ No more jobs to click")
                    break

                await asyncio.sleep(2)

                # Extract job details for resume customization
                await self._extract_job_details()

                # Track this job as applied (even if it fails, to avoid retrying)
                job_key = f"{self.current_job_title or 'Unknown'} at {self.current_company or 'Unknown'}"
                if job_key in self.applied_jobs:
                    print(f"⏭️ Already tried this job, skipping: {job_key}")
                    continue
                self.applied_jobs.add(job_key)

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
            await self.controller.stop()


async def main():
    """Main entry point."""
    keywords = sys.argv[1] if len(sys.argv) > 1 else "Software Engineer"
    location = sys.argv[2] if len(sys.argv) > 2 else "San Jose, CA"

    agent = LinkedInAgent()
    await agent.run(keywords=keywords, location=location)


if __name__ == "__main__":
    asyncio.run(main())

