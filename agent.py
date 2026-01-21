"""
Browser Automation Agent
Combines browser control with LLM planning for automated web tasks.
"""
import asyncio
import os
from typing import Dict, List
from dotenv import load_dotenv

from browser_controller import BrowserController
from llm_planner import get_next_action, Action

load_dotenv()


def get_user_profile() -> Dict[str, str]:
    """Load user profile from environment variables."""
    return {
        "name": os.getenv("APPLICANT_NAME", ""),
        "email": os.getenv("APPLICANT_EMAIL", ""),
        "phone": os.getenv("APPLICANT_PHONE", ""),
        "location": os.getenv("APPLICANT_LOCATION", ""),
        "linkedin": os.getenv("APPLICANT_LINKEDIN", ""),
        "years_experience": os.getenv("APPLICANT_YEARS_EXPERIENCE", ""),
        "title": os.getenv("APPLICANT_TITLE", ""),
    }


class BrowserAgent:
    """AI-powered browser automation agent."""
    
    def __init__(self, headless: bool = False):
        self.controller = BrowserController(headless=headless)
        self.user_profile = get_user_profile()
        self.action_history: List[Dict] = []
        self.max_steps = 20
        
    async def run(self, url: str, goal: str) -> bool:
        """Run the agent to achieve a goal on a website."""
        
        print(f"\n{'='*60}")
        print(f"🤖 BROWSER AGENT")
        print(f"{'='*60}")
        print(f"🎯 Goal: {goal}")
        print(f"🌐 URL: {url}")
        print(f"{'='*60}\n")
        
        await self.controller.start()
        
        try:
            await self.controller.goto(url)
            
            for step in range(self.max_steps):
                print(f"\n--- Step {step + 1}/{self.max_steps} ---")
                
                # Get page context
                page_context = await self.controller.get_page_context()
                
                # Ask LLM for next action
                action = await get_next_action(
                    goal=goal,
                    page_context=page_context,
                    user_profile=self.user_profile,
                    history=self.action_history
                )
                
                # Record action
                self.action_history.append({
                    "step": step + 1,
                    "action": action.action_type,
                    "element": action.element_index,
                    "value": action.value,
                    "reason": action.reason
                })
                
                # Execute action
                if action.action_type == "done":
                    print("\n✅ GOAL ACHIEVED!")
                    return True
                    
                if action.action_type == "error":
                    print(f"\n❌ AGENT STOPPED: {action.reason}")
                    return False
                
                success = await self.controller.execute_action(action)
                if not success:
                    print("⚠️ Action failed, retrying...")
                    
                # Small delay between actions
                await asyncio.sleep(0.5)
            
            print("\n⚠️ Max steps reached")
            return False
            
        finally:
            await self.controller.stop()
            self._print_summary()
    
    def _print_summary(self):
        """Print a summary of actions taken."""
        print(f"\n{'='*60}")
        print("📋 ACTION SUMMARY")
        print(f"{'='*60}")
        for action in self.action_history:
            print(f"  Step {action['step']}: {action['action']} - {action['reason'][:50]}")
        print(f"{'='*60}\n")


async def main():
    """Test the agent with a simple task."""
    agent = BrowserAgent(headless=False)
    
    # Simple test: Find the top post on Hacker News
    success = await agent.run(
        url="https://news.ycombinator.com",
        goal="Find and tell me the title of the #1 top post on the page"
    )
    
    print(f"Result: {'Success' if success else 'Failed'}")


if __name__ == "__main__":
    asyncio.run(main())

