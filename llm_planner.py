"""
LLM Action Planner Module
Uses FREE LLM APIs (Cerebras or Groq) to decide what actions to take on a web page.
"""
import httpx
import json
import os
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class Action:
    """Represents an action to perform on the page."""
    action_type: str  # click, type, select, scroll, wait, done, error
    element_index: Optional[int] = None
    value: Optional[str] = None
    reason: str = ""


# LLM API URLs - try multiple providers with fallback
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
CEREBRAS_API_URL = "https://api.cerebras.ai/v1/chat/completions"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

SYSTEM_PROMPT = """You are a browser automation assistant for LinkedIn job applications.

The PAGE CONTEXT shows interactive elements in this format:
[index] TAG "visible text" placeholder="..." name="..."

Respond with ONLY this JSON (no other text):
{
    "action_type": "click|type|select|scroll|wait|done|error",
    "element_index": <number from [index] or null>,
    "value": "<text to type or select>",
    "reason": "<1-line explanation>"
}

Action types:
- click: Click element at [index]
- type: Type 'value' into input at [index] (CLEARS existing text first)
- select: Select 'value' from dropdown at [index]
- scroll: Scroll to see more
- wait: Wait for page load
- done: Goal achieved - include result in reason
- error: Cannot proceed

LINKEDIN EASY APPLY WORKFLOW:
1. If you see a modal with "Contact info", "Resume", "Work experience", etc. - you're IN the application form
2. Fill empty input fields with user profile data (name, email, phone, etc.)
3. For dropdowns (SELECT), choose the most appropriate option
4. Look for "Next", "Review", or "Submit application" buttons to proceed
5. IMPORTANT: Before clicking "Submit application", UNCHECK the "Follow [company]" checkbox if it's checked
6. If you see "Application submitted" or similar - respond with "done"
7. NEVER click "Easy Apply" if a modal is already open

FOLLOW COMPANY CHECKBOX:
- Before submitting, look for checkbox with text like "Follow [Company Name]" or "Follow company"
- If this checkbox is CHECKED, click it to UNCHECK it
- Only submit after ensuring this checkbox is unchecked

COMMON LINKEDIN QUESTIONS - Answer these:
- "Are you authorized to work in the US?" → Yes
- "Will you now or in the future require sponsorship?" → Yes
- "Will you now or in the future require visa sponsorship?" → Yes
- "Do you require visa sponsorship?" → Yes
- "Years of experience" → Use user's years_experience value
- "Do you have a valid driver's license?" → Yes
- "Are you willing to relocate?" → Yes
- "What is your desired salary?" → Leave blank or enter reasonable amount
- "Gender" or "Sex" → MUST set value to "Male" (the user's gender)
- "Race" or "Ethnicity" → MUST set value to "Asian" (the user's race)
- "Veteran status" → MUST set value to "I am not a protected veteran" or "No"
- "Disability status" → MUST set value to "No, I do not have a disability" or "No"

IMPORTANT FOR SELECT ACTIONS:
- When action_type is "select", the "value" field MUST contain the actual option text to select
- Example: {"action_type": "select", "element_index": 5, "value": "Male", "reason": "Select Male for gender"}
- NEVER leave "value" empty for select actions!
- For radio buttons with Yes/No options, click the appropriate radio button based on above answers
- For dropdowns, select the most appropriate option matching user's profile

TYPEAHEAD/AUTOCOMPLETE DROPDOWNS:
- Some dropdowns require TYPING to filter options (e.g., country, city, school)
- If you see an INPUT field that looks like a dropdown selector, use "type" action to enter a value
- After typing, the system will automatically select from the dropdown options that appear
- Example: {"action_type": "type", "element_index": 3, "value": "United States", "reason": "Type country name to filter dropdown"}

FIELD MATCHING - VERY IMPORTANT:
- Field with "first name" or "firstName" in name/placeholder → Use ONLY the first_name value
- Field with "last name" or "lastName" in name/placeholder → Use ONLY the last_name value
- Field with "phone" or "mobile" in name/placeholder → Use ONLY the phone value
- Field with "email" in name/placeholder → Use ONLY the email value
- Field with "city" or "location" or "address" in name/placeholder → Use ONLY the location value
- NEVER put phone number in a name field!
- NEVER put name in a phone field!
- Match the field label/placeholder EXACTLY to the correct profile value

CRITICAL RULES:
1. If the goal asks to "find" or "tell" information visible in the page context, respond with "done" and include the answer in "reason"
2. For forms, fill one field at a time using user profile data
3. Look for Next/Review/Submit buttons to proceed through multi-step forms
4. element_index must match exactly the [number] shown
5. Respond with JSON only - no markdown, no explanation text
6. If an input already has the correct value, skip it and click Next
7. For phone country code dropdowns, select "United States (+1)"
8. If Next button doesn't work, look for unfilled REQUIRED fields (marked with *)
9. For SELECT dropdowns with options, pick the first reasonable option
10. READ THE FIELD NAME/PLACEHOLDER before typing - put the RIGHT value in the RIGHT field!
11. IMPORTANT: If a SELECT element shows SELECTED="Male" or SELECTED="Asian", it's ALREADY FILLED - click Next instead!
12. NEVER try to select a value that's already selected - just click Next to proceed!

NEVER RETURN ERROR IF:
- You see any BUTTON, INPUT, SELECT, or SPAN elements on the page
- You see "Next", "Submit", "Apply", "Review", "Continue" buttons
- A modal/dialog is open
- There are any clickable elements visible

INSTEAD OF ERROR:
- Click "Next" or "Submit" if form looks complete
- Scroll down if you don't see expected elements
- Click any visible button to proceed
- Only return "error" if the page is completely empty or shows a clear error message
"""


async def get_next_action(
    goal: str,
    page_context: str,
    user_profile: Dict[str, str],
    history: list = None,
    api_key: str = None
) -> Action:
    """Use Cerebras LLM to determine the next action."""
    
    api_key = api_key or os.getenv("CEREBRAS_API_KEY")
    if not api_key:
        raise ValueError("CEREBRAS_API_KEY not set")
    
    # Build the prompt
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""
GOAL: {goal}

USER PROFILE:
{json.dumps(user_profile, indent=2)}

CURRENT PAGE:
{page_context}

{f"PREVIOUS ACTIONS: {json.dumps(history[-5:])}" if history else ""}

What action should I take next? Respond with JSON only.
"""}
    ]
    
    # Build list of providers to try with fallback
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    mistral_key = os.getenv("MISTRAL_API_KEY")

    providers = []
    # Try Mistral first (generous limits: 1 req/sec, 500k tokens/min)
    if mistral_key:
        providers.append({
            "name": "Mistral",
            "url": MISTRAL_API_URL,
            "key": mistral_key,
            "model": "mistral-small-latest",
            "headers": {}
        })
    if openrouter_key:
        providers.append({
            "name": "OpenRouter",
            "url": OPENROUTER_API_URL,
            "key": openrouter_key,
            "model": "meta-llama/llama-3.3-70b-instruct:free",
            "headers": {
                "HTTP-Referer": "https://github.com/browser-llm-automation",
                "X-Title": "LinkedIn Job Automation"
            }
        })
    if groq_key:
        providers.append({
            "name": "Groq",
            "url": GROQ_API_URL,
            "key": groq_key,
            "model": "llama-3.3-70b-versatile",
            "headers": {}
        })
    if api_key:
        providers.append({
            "name": "Cerebras",
            "url": CEREBRAS_API_URL,
            "key": api_key,
            "model": "llama-3.3-70b",
            "headers": {}
        })

    if not providers:
        return Action(action_type="error", reason="No LLM API keys configured")

    response = None
    last_error = None
    providers_tried = 0

    for provider in providers:
        providers_tried += 1
        max_retries = 2
        for attempt in range(max_retries):
            try:
                headers = {
                    "Authorization": f"Bearer {provider['key']}",
                    "Content-Type": "application/json",
                    **provider['headers']
                }
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(
                        provider['url'],
                        headers=headers,
                        json={
                            "model": provider['model'],
                            "messages": messages,
                            "temperature": 0.1,
                            "max_tokens": 300
                        }
                    )
                    if response.status_code == 429:
                        print(f"⏳ {provider['name']} rate limited, trying next provider...")
                        last_error = f"{provider['name']} rate limited"
                        # Wait a bit before trying next provider
                        import asyncio
                        await asyncio.sleep(2)
                        break  # Try next provider
                    response.raise_for_status()
                    # Success!
                    break
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2)
        else:
            continue  # All retries failed for this provider, try next

        # Check if we got a successful response
        if response and response.status_code == 200:
            break

    if response is None or response.status_code != 200:
        # If all providers are rate limited, wait longer before returning error
        if "rate limited" in (last_error or "").lower() and providers_tried >= len(providers):
            print("⏳ All providers rate limited, waiting 30 seconds...")
            import asyncio
            await asyncio.sleep(30)
            # Try the first provider again after waiting
            if providers:
                provider = providers[0]
                try:
                    headers = {
                        "Authorization": f"Bearer {provider['key']}",
                        "Content-Type": "application/json",
                        **provider['headers']
                    }
                    async with httpx.AsyncClient(timeout=60) as client:
                        response = await client.post(
                            provider['url'],
                            headers=headers,
                            json={
                                "model": provider['model'],
                                "messages": messages,
                                "temperature": 0.1,
                                "max_tokens": 300
                            }
                        )
                        if response.status_code == 200:
                            print(f"✅ {provider['name']} ready after wait")
                except:
                    pass

        if response is None or response.status_code != 200:
            return Action(action_type="error", reason=f"All LLM providers failed: {last_error}")

    try:
        result = response.json()
        if "choices" not in result:
            error_msg = result.get("error", {}).get("message", str(result))
            return Action(action_type="error", reason=f"API error: {error_msg}")
        content = result["choices"][0]["message"]["content"]
    except Exception as e:
        return Action(action_type="error", reason=f"Failed to parse API response: {str(e)}")

    # Parse JSON from response
    try:
        # Handle markdown code blocks
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        action_data = json.loads(content.strip())
        return Action(
            action_type=action_data.get("action_type", "error"),
            element_index=action_data.get("element_index"),
            value=action_data.get("value"),
            reason=action_data.get("reason", "")
        )
    except json.JSONDecodeError:
        return Action(
            action_type="error",
            reason=f"Failed to parse LLM response: {content[:100]}"
        )

