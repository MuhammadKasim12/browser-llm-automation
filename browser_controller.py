"""
Browser Controller Module
Executes actions on the browser using Playwright.
Includes humanization to avoid bot detection.
"""
import asyncio
import os
import random
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from typing import Optional
from dotenv import load_dotenv

from dom_extractor import find_element_by_index, get_page_context
from llm_planner import Action

load_dotenv()


# ============= HUMANIZATION UTILITIES =============

async def human_delay(min_ms: int = 100, max_ms: int = 500):
    """Random delay to simulate human reaction time."""
    delay = random.randint(min_ms, max_ms) / 1000
    await asyncio.sleep(delay)


async def human_typing_delay():
    """Random delay between keystrokes (50-150ms like real typing)."""
    await asyncio.sleep(random.randint(50, 150) / 1000)


async def human_think_delay():
    """Longer pause to simulate human thinking (0.5-2s)."""
    await asyncio.sleep(random.uniform(0.5, 2.0))


async def human_scroll(page: Page):
    """Scroll with natural human-like behavior."""
    scroll_amount = random.randint(200, 600)
    await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
    await human_delay(200, 500)


async def move_mouse_naturally(page: Page, x: int, y: int):
    """Move mouse to position with natural curve."""
    # Get current position (or start from random edge)
    try:
        current = await page.evaluate("() => ({x: window.mouseX || 0, y: window.mouseY || 0})")
        start_x, start_y = current.get('x', random.randint(0, 100)), current.get('y', random.randint(0, 100))
    except:
        start_x, start_y = random.randint(0, 200), random.randint(0, 200)

    # Generate intermediate points for natural curve
    steps = random.randint(5, 12)
    for i in range(1, steps + 1):
        progress = i / steps
        # Add slight curve/randomness to path
        curve_x = random.randint(-10, 10) * (1 - progress)
        curve_y = random.randint(-10, 10) * (1 - progress)

        next_x = start_x + (x - start_x) * progress + curve_x
        next_y = start_y + (y - start_y) * progress + curve_y

        await page.mouse.move(next_x, next_y)
        await asyncio.sleep(random.randint(10, 30) / 1000)

    # Store current position
    await page.evaluate(f"() => {{ window.mouseX = {x}; window.mouseY = {y}; }}")


async def human_type(page: Page, element, text: str):
    """Type text character by character with human-like delays."""
    # Focus the element first
    await element.focus()
    await human_delay(100, 300)

    # Clear existing content
    await element.fill("")
    await human_delay(50, 150)

    # Type each character with varying speed
    for char in text:
        await element.type(char, delay=random.randint(30, 120))
        # Occasional longer pause (like when thinking)
        if random.random() < 0.05:
            await human_delay(200, 500)


class BrowserController:
    """Controls browser automation with LLM-guided actions and humanization."""

    # List of realistic user agents
    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]

    def __init__(self, headless: bool = None, slow_mo: int = None, humanize: bool = True):
        self.headless = headless if headless is not None else os.getenv("HEADLESS", "false").lower() == "true"
        self.slow_mo = slow_mo if slow_mo is not None else int(os.getenv("SLOW_MO", "50"))  # Reduced - we add our own delays
        self.humanize = humanize
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None

    async def start(self, use_persistent: bool = True):
        """Start the browser with human-like settings. Reuses existing window if available."""
        self.playwright = await async_playwright().start()

        # Random viewport size (realistic variations)
        width = random.randint(1200, 1400)
        height = random.randint(750, 900)

        # Path for persistent browser data (cookies, localStorage, etc.)
        user_data_dir = os.path.join(os.path.dirname(__file__), '.browser_data')

        if use_persistent and not self.headless:
            # Use persistent context to maintain login sessions
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=self.headless,
                slow_mo=self.slow_mo,
                viewport={"width": width, "height": height},
                user_agent=random.choice(self.USER_AGENTS),
                locale='en-US',
                timezone_id='America/Los_Angeles',
                geolocation={'latitude': 37.3382, 'longitude': -121.8863},  # San Jose
                permissions=['geolocation'],
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--no-first-run',
                ]
            )
            self.browser = None  # No separate browser with persistent context

            # Hide webdriver property
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            """)

            # Reuse existing page if available, don't open new tab
            if self.context.pages:
                self.page = self.context.pages[0]
                print("🌐 Reusing existing browser window (persistent session)")
            else:
                self.page = await self.context.new_page()
                print("🌐 Browser started (humanized mode + persistent session)")
        else:
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--no-first-run',
                ]
            )

            self.context = await self.browser.new_context(
                viewport={"width": width, "height": height},
                user_agent=random.choice(self.USER_AGENTS),
                locale='en-US',
                timezone_id='America/Los_Angeles',
                geolocation={'latitude': 37.3382, 'longitude': -121.8863},
                permissions=['geolocation'],
            )

            # Hide webdriver property
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            """)

            self.page = await self.context.new_page()
            print("🌐 Browser started (humanized mode)")

        return self

    async def stop(self):
        """Stop the browser."""
        if self.browser:
            await self.browser.close()
        elif self.context:
            # For persistent context, close the context
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
        print("🛑 Browser stopped")

    async def goto(self, url: str):
        """Navigate to a URL with human-like behavior."""
        print(f"📍 Navigating to: {url}")

        if self.humanize:
            await human_delay(200, 600)  # Small pause before navigation

        await self.page.goto(url, wait_until="domcontentloaded")

        if self.humanize:
            # Random small scroll after page load (humans often do this)
            await human_delay(500, 1500)
            if random.random() < 0.3:
                await human_scroll(self.page)

    async def execute_action(self, action: Action) -> bool:
        """Execute an action on the page with humanization. Returns True if successful."""

        print(f"🎯 Action: {action.action_type} | {action.reason}")

        # Add human-like delay before action
        if self.humanize:
            await human_delay(300, 800)

        if action.action_type == "done":
            print("✅ Goal achieved!")
            return True

        if action.action_type == "error":
            print(f"❌ Error: {action.reason}")
            return False

        if action.action_type == "wait":
            wait_time = random.uniform(1.5, 3.0) if self.humanize else 2
            await asyncio.sleep(wait_time)
            return True

        if action.action_type == "scroll":
            if self.humanize:
                await human_scroll(self.page)
            else:
                await self.page.evaluate("window.scrollBy(0, 500)")
                await asyncio.sleep(0.5)
            return True

        if action.element_index is None:
            print("⚠️ No element index provided")
            return False

        element = await find_element_by_index(self.page, action.element_index)
        if not element:
            print(f"⚠️ Element [{action.element_index}] not found")
            return False
        
        try:
            if action.action_type == "click":
                # Move mouse naturally to element before clicking
                if self.humanize:
                    try:
                        box = await element.bounding_box()
                        if box:
                            # Click at slightly random position within element
                            x = box['x'] + box['width'] * random.uniform(0.3, 0.7)
                            y = box['y'] + box['height'] * random.uniform(0.3, 0.7)
                            await move_mouse_naturally(self.page, x, y)
                            await human_delay(50, 200)
                    except:
                        pass

                # Use force click with shorter timeout to avoid blocking on modals
                # Retry with DOM re-query if element is detached
                click_success = False
                for retry in range(3):
                    try:
                        await element.click(timeout=5000)
                        click_success = True
                        break
                    except Exception as e:
                        error_msg = str(e).lower()
                        if "not attached to the dom" in error_msg or "detached" in error_msg:
                            print(f"   ⚠️ Element detached, re-querying (retry {retry + 1}/3)...")
                            await asyncio.sleep(0.3)
                            # Re-query the element
                            element = await find_element_by_index(self.page, action.element_index)
                            if not element:
                                break
                        else:
                            # Try force click if normal click fails
                            try:
                                await element.click(force=True, timeout=3000)
                                click_success = True
                                break
                            except:
                                break

                if not click_success:
                    print(f"   ⚠️ Click failed after retries")
                    return False

                if self.humanize:
                    await human_delay(300, 700)
                else:
                    await asyncio.sleep(0.5)

            elif action.action_type == "type":
                if self.humanize:
                    # Human-like typing with character-by-character input
                    await human_type(self.page, element, action.value or "")
                else:
                    # Fast fill for non-humanized mode
                    await element.fill(action.value or "")

                if self.humanize:
                    await human_delay(200, 500)
                else:
                    await asyncio.sleep(0.5)

                # ALWAYS check for dropdown options after typing - many fields are typeahead/autocomplete
                tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
                if tag_name == "input":
                    # Wait a bit for dropdown to appear
                    wait_time = random.uniform(0.8, 1.5) if self.humanize else 1
                    await asyncio.sleep(wait_time)

                    # Check for dropdown options with various selectors
                    option_selectors = [
                        '[role="option"]',
                        '.basic-typeahead__selectable',
                        '.search-typeahead-v2__hit',
                        '[role="listbox"] li',
                        '[class*="autocomplete"] li',
                        '[class*="dropdown"] li',
                        '[class*="suggestion"]',
                        '.typeahead-result',
                        '[data-automation-id*="option"]',
                    ]

                    option = None
                    for selector in option_selectors:
                        try:
                            option = await self.page.query_selector(selector)
                            if option and await option.is_visible():
                                break
                            option = None
                        except:
                            continue

                    if option:
                        try:
                            if self.humanize:
                                await human_delay(100, 300)
                            await option.click()
                            print(f"   ✅ Selected dropdown option after typing")
                            await human_delay(200, 400) if self.humanize else await asyncio.sleep(0.3)
                        except Exception:
                            # Press Enter to select if click fails
                            try:
                                await element.press("Enter")
                                print(f"   ✅ Pressed Enter to select option")
                            except:
                                pass

            elif action.action_type == "select":
                # Check if it's a standard select element
                tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
                value_lower = (action.value or "").lower()
                print(f"   📋 Select action: tag={tag_name}, value='{action.value}'")

                if tag_name == "select":
                    # Standard select element - first get available options
                    try:
                        options = await element.evaluate('''(el) => {
                            return Array.from(el.options).map(o => ({value: o.value, text: o.text}));
                        }''')
                        print(f"   📋 Available options: {options}")
                    except Exception as e:
                        print(f"   ⚠️ Could not get options: {e}")
                        options = []

                    selected = False

                    # For EEO fields, use smart matching first
                    eeo_mappings = {
                        'no': ['no, i don', 'no, i do not', 'i am not', "don't have", "don\u2019t have"],
                        'yes': ['yes, i', 'i have a', 'i am a', 'i identify'],
                        'male': ['male'],
                        'female': ['female'],
                        'asian': ['asian'],
                        'wish not': ['wish not to', 'prefer not', 'decline'],
                        'not a veteran': ['not a veteran', 'i am not a veteran'],
                        'disability': ["don't have a disability", "don\u2019t have a disability", 'no, i do not have'],
                    }

                    # Try smart matching for EEO values
                    if options and not selected:
                        print(f"   🔍 Trying EEO smart match for value: '{value_lower}'")
                        for key, patterns in eeo_mappings.items():
                            if key in value_lower:
                                print(f"   🔍 Matched key '{key}', trying patterns: {patterns}")
                                for opt in options:
                                    opt_lower = opt['text'].lower()
                                    for pattern in patterns:
                                        if pattern in opt_lower:
                                            print(f"   🔍 Pattern '{pattern}' found in option '{opt['text']}'")
                                            try:
                                                await element.select_option(value=opt['value'], timeout=3000)
                                                print(f"   ✅ Selected '{opt['text']}' by EEO smart match")
                                                selected = True
                                                break
                                            except Exception as e:
                                                print(f"   ⚠️ EEO smart match failed: {e}")
                                    if selected:
                                        break
                                if selected:
                                    break

                    # Try by label (with short timeout)
                    if not selected:
                        try:
                            await element.select_option(label=action.value, timeout=3000)
                            print(f"   ✅ Selected '{action.value}' by label")
                            selected = True
                        except Exception as e1:
                            # Try by value
                            try:
                                await element.select_option(value=action.value, timeout=3000)
                                print(f"   ✅ Selected '{action.value}' by value")
                                selected = True
                            except Exception as e2:
                                pass

                    # Try partial match if not selected
                    if not selected and options:
                        for opt in options:
                            if action.value.lower() in opt['text'].lower():
                                try:
                                    await element.select_option(value=opt['value'], timeout=3000)
                                    print(f"   ✅ Selected '{opt['text']}' by partial match")
                                    selected = True
                                    break
                                except Exception as e3:
                                    print(f"   ⚠️ Partial match failed: {e3}")
                else:
                    # LinkedIn EEO questions use radio buttons with labels, not dropdowns
                    # First, try to find and click the label/radio directly by text
                    clicked = await self.page.evaluate('''(value) => {
                        const valueLower = value.toLowerCase();

                        // LinkedIn EEO uses labels with data-test-text-selectable-option__label
                        const labels = document.querySelectorAll('[data-test-text-selectable-option__label]');
                        for (const label of labels) {
                            const labelText = label.getAttribute('data-test-text-selectable-option__label') || '';
                            if (labelText.toLowerCase().includes(valueLower)) {
                                label.click();
                                return true;
                            }
                        }

                        // Try clicking radio inputs by their associated label text
                        const allLabels = document.querySelectorAll('label');
                        for (const label of allLabels) {
                            if (label.innerText.toLowerCase().includes(valueLower)) {
                                // Click the label or its associated input
                                const forId = label.getAttribute('for');
                                if (forId) {
                                    const input = document.getElementById(forId);
                                    if (input) {
                                        input.click();
                                        return true;
                                    }
                                }
                                label.click();
                                return true;
                            }
                        }

                        // Try role="option" elements
                        const options = document.querySelectorAll('[role="option"], [role="listbox"] li');
                        for (const opt of options) {
                            if (opt.innerText.toLowerCase().includes(valueLower)) {
                                opt.click();
                                return true;
                            }
                        }

                        return false;
                    }''', action.value or "")

                    if clicked:
                        print(f"   ✅ Selected '{action.value}' via JavaScript")
                    else:
                        print(f"   ⚠️ JS selection failed, trying keyboard navigation...")
                        # Focus on element first
                        if self.humanize:
                            await human_delay(100, 300)
                        await element.focus()
                        await asyncio.sleep(0.2)

                        # Click to open dropdown
                        await element.click()
                        await human_delay(300, 600) if self.humanize else await asyncio.sleep(0.5)

                        # Get all visible options
                        options = await self.page.query_selector_all('[role="option"], li[class*="option"], div[class*="option"]')

                        # Find target option index
                        target_index = -1
                        value_lower = (action.value or "").lower()
                        for i, opt in enumerate(options):
                            try:
                                opt_text = await opt.inner_text()
                                if value_lower in opt_text.lower():
                                    target_index = i
                                    break
                            except:
                                continue

                        if target_index >= 0:
                            # Use keyboard to navigate: Home + ArrowDown
                            await self.page.keyboard.press('Home')
                            await asyncio.sleep(0.1)

                            for _ in range(target_index):
                                await self.page.keyboard.press('ArrowDown')
                                await asyncio.sleep(0.05)

                            await self.page.keyboard.press('Enter')
                            print(f"   ✅ Selected '{action.value}' via keyboard navigation")
                        else:
                            # Last fallback: try direct option click
                            option_selectors = [
                                f'[role="option"]:has-text("{action.value}")',
                                f'.artdeco-dropdown__content-inner button:has-text("{action.value}")',
                            ]

                            for selector in option_selectors:
                                try:
                                    option = await self.page.query_selector(selector)
                                    if option:
                                        if self.humanize:
                                            await human_delay(100, 300)
                                        await option.click()
                                        print(f"   ✅ Selected via fallback selector")
                                        break
                                except:
                                    continue

                if self.humanize:
                    await human_delay(200, 500)
                else:
                    await asyncio.sleep(0.3)

            # Occasional random micro-pause (humans aren't perfectly consistent)
            if self.humanize and random.random() < 0.1:
                await human_think_delay()

            return True

        except Exception as e:
            print(f"⚠️ Action failed: {e}")
            return False
    
    async def get_page_context(self) -> str:
        """Get the current page context for LLM."""
        return await get_page_context(self.page)
    
    async def screenshot(self, path: str = "screenshot.png"):
        """Take a screenshot."""
        await self.page.screenshot(path=path)
        print(f"📸 Screenshot saved: {path}")


async def main():
    """Test the browser controller."""
    controller = BrowserController(headless=False)
    await controller.start()
    
    try:
        await controller.goto("https://news.ycombinator.com")
        context = await controller.get_page_context()
        print(context[:2000])
    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())

