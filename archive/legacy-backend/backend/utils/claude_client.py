# -*- coding: utf-8 -*-
"""
Claude API Client
Handles all interactions with Anthropic's Claude API
"""

import os
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()

class ClaudeClient:
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Please create a .env file with your API key. "
                "See .env.example for reference."
            )
        self.client = AsyncAnthropic(api_key=api_key)
        # Using claude-3-5-haiku-20241022 - Haiku 3.5 (improved reasoning)
        self.model = "claude-3-5-haiku-20241022"
    
    async def generate_prediction(self, prompt: str) -> str:
        """
        Generate a prediction using Claude
        """
        try:
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return message.content[0].text
        except Exception as e:
            raise Exception(f"Claude API error: {str(e)}")
    
    async def test_connection(self) -> dict:
        """
        Test Claude API connection
        """
        try:
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=100,
                messages=[
                    {"role": "user", "content": "Respond with: Claude API connected successfully"}
                ]
            )
            return {
                "status": "success",
                "message": message.content[0].text,
                "model": self.model
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - closes HTTP connections"""
        await self.close()
    
    async def close(self):
        """
        Close the underlying HTTP client connections
        """
        # AsyncAnthropic uses httpx.AsyncClient internally
        # Access the underlying client and close it
        if hasattr(self.client, '_client') and hasattr(self.client._client, 'aclose'):
            await self.client._client.aclose()
        elif hasattr(self.client, 'close'):
            await self.client.close()
        elif hasattr(self.client, 'aclose'):
            await self.client.aclose()


# Singleton instance
_claude_client = None

def get_claude_client() -> ClaudeClient:
    """Get Claude client singleton (optional - can be None if API key not set)"""
    global _claude_client
    if _claude_client is None:
        try:
            _claude_client = ClaudeClient()
        except ValueError:
            # API key not set - return None for MVP phase (using mocked data)
            return None
    return _claude_client