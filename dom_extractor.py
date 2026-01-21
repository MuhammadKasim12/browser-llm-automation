"""
DOM Extractor Module
Extracts interactive elements from web pages as structured text for LLM processing.
No vision API needed - works with DOM/HTML directly.
"""
from playwright.async_api import Page
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PageElement:
    """Represents an interactive element on the page."""
    index: int
    tag: str
    role: str
    text: str
    placeholder: str
    name: str
    element_type: str
    is_visible: bool
    selector: str
    current_value: str = ""


async def extract_interactive_elements(page: Page) -> List[PageElement]:
    """Extract all interactive elements from the page, prioritizing modals."""

    js_code = """
    () => {
        const elements = [];
        const seen = new Set();
        const interactiveSelectors = [
            'input', 'textarea', 'select',  // Prioritize input fields first
            'button', 'a[href]',
            '[role="button"]', '[role="link"]', '[role="textbox"]',
            '[role="radio"]', '[role="checkbox"]', '[role="option"]', '[role="combobox"]',
            '[role="listbox"]', '[role="menuitem"]',
            '[onclick]', '[data-testid]',
            // Common external site selectors
            '.btn', '.button', '[class*="button"]', '[class*="btn"]',
            '[class*="apply"]', '[class*="submit"]',
            'label', 'span[tabindex]', 'div[tabindex]',
            // More ATS-specific selectors
            '[class*="Apply"]', '[class*="APPLY"]',
            '[data-automation-id]', '[data-test]', '[data-qa]',
            '.job-apply', '#apply-button', '.apply-btn',
            '[class*="cta"]', '[class*="action"]'
        ];

        // Check for modal/dialog - prioritize modal content
        // But skip cookie consent modals
        let modal = document.querySelector('[role="dialog"], .artdeco-modal, [aria-modal="true"], #artdeco-modal-outlet > div');

        // Check if this is a cookie consent modal - if so, ignore it
        if (modal) {
            const modalText = (modal.innerText || '').toLowerCase();
            if (modalText.includes('cookie') || modalText.includes('privacy') || modalText.includes('consent')) {
                modal = null;  // Ignore cookie modals
            }
        }

        // For LinkedIn, use modal. For external sites, always search full document
        const isLinkedIn = window.location.hostname.includes('linkedin.com');
        const searchRoot = (modal && isLinkedIn) ? modal : document;
        const isModalOpen = !!modal && isLinkedIn;

        let index = 0;

        function processElement(el) {
            // Skip if already processed
            if (seen.has(el)) return;
            seen.add(el);

            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            const isVisible = rect.width > 0 && rect.height > 0 &&
                              style.visibility !== 'hidden' &&
                              style.display !== 'none' &&
                              style.opacity !== '0';

            if (!isVisible) return;

            // Get text content (more aggressive)
            let text = el.innerText || el.textContent || el.value || '';
            text = text.replace(/\\s+/g, ' ').substring(0, 150).trim();

            // Skip empty links/buttons without meaningful content
            if (!text && !el.getAttribute('placeholder') && !el.getAttribute('aria-label')) {
                if (el.tagName === 'A' || el.tagName === 'BUTTON') return;
            }

            // Set data attribute for finding later
            el.setAttribute('data-llm-index', index.toString());

            // Get associated label for input fields
            let labelText = '';
            if (el.id) {
                const label = document.querySelector('label[for="' + el.id + '"]');
                if (label) labelText = label.innerText?.trim() || '';
            }

            // Determine element type description
            const tagName = el.tagName.toLowerCase();
            let typeDesc = tagName;
            if (tagName === 'input') {
                typeDesc = 'input[' + (el.getAttribute('type') || 'text') + ']';
            }

            // For select elements, show the currently selected value
            let currentValue = '';
            if (tagName === 'select' && el.selectedIndex >= 0) {
                currentValue = el.options[el.selectedIndex]?.text || '';
            }

            elements.push({
                index: index++,
                tag: typeDesc,
                role: el.getAttribute('role') || tagName,
                text: text,
                placeholder: el.getAttribute('placeholder') || '',
                name: labelText || el.getAttribute('name') || el.getAttribute('aria-label') || '',
                element_type: el.getAttribute('type') || '',
                is_visible: isVisible,
                selector: '[data-llm-index="' + (index - 1) + '"]',
                in_modal: isModalOpen,
                current_value: currentValue
            });
        }

        for (const selector of interactiveSelectors) {
            try {
                searchRoot.querySelectorAll(selector).forEach(processElement);
            } catch (e) {
                // Some selectors might fail on certain pages
            }
        }

        // If no elements found and we're on external site, try more aggressive search
        if (elements.length === 0 && !isLinkedIn) {
            // Get ALL buttons and links
            document.querySelectorAll('button, a, [role="button"], input[type="submit"], input[type="button"]').forEach(processElement);
        }

        return {elements: elements, modal_open: isModalOpen};
    }
    """

    result = await page.evaluate(js_code)
    # Filter out 'in_modal' which is not in PageElement dataclass
    elements = [PageElement(**{k: v for k, v in el.items() if k not in ['in_modal']}) for el in result['elements']]
    return elements, result['modal_open']


async def get_page_context(page: Page) -> str:
    """Get a text representation of the page for the LLM."""

    title = await page.title()
    url = page.url
    elements, modal_open = await extract_interactive_elements(page)

    # Build text representation
    lines = [
        f"=== PAGE: {title} ===",
        f"URL: {url}",
    ]

    if modal_open:
        lines.append("")
        lines.append("*** MODAL/DIALOG IS OPEN - Focus on modal content below ***")
        lines.append("*** Fill form fields, then click Next/Submit button ***")

    # For external sites, add some page content for context
    if 'linkedin.com' not in url:
        try:
            page_text = await page.evaluate('''() => {
                // Get main content area
                const main = document.querySelector('main, article, [role="main"], .content, #content') || document.body;
                let text = main.innerText || '';
                // Get first 1500 chars for context
                return text.substring(0, 1500).trim();
            }''')
            if page_text:
                lines.append("")
                lines.append("=== PAGE CONTENT (first 1500 chars) ===")
                lines.append(page_text[:1500])
        except:
            pass

    lines.append("")
    lines.append("=== INTERACTIVE ELEMENTS ===")

    if len(elements) == 0:
        lines.append("(No interactive elements found - try scrolling or waiting)")

    for el in elements:
        desc = f"[{el.index}] {el.tag.upper()}"
        if el.role and el.role != el.tag:
            desc += f" (role={el.role})"
        if el.element_type:
            desc += f" type={el.element_type}"
        if el.text:
            desc += f" \"{el.text[:50]}\""
        if el.placeholder:
            desc += f" placeholder=\"{el.placeholder}\""
        if el.name:
            desc += f" name=\"{el.name}\""
        # Show current value for select elements - IMPORTANT for LLM to know what's already selected
        if el.current_value and el.current_value != "Select an option":
            desc += f" SELECTED=\"{el.current_value}\""
        lines.append(desc)

    return "\n".join(lines)


async def find_element_by_index(page: Page, index: int):
    """Find an element by its LLM index."""
    # Try data attribute first
    element = await page.query_selector(f'[data-llm-index="{index}"]')
    if element:
        return element
    
    # Re-extract and find by index
    elements, _ = await extract_interactive_elements(page)
    for el in elements:
        if el.index == index:
            if el.selector.startswith('#') or el.selector.startswith('['):
                return await page.query_selector(el.selector)
    return None

