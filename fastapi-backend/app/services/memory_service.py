import os
import httpx
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class MemoryService:
    """
    Cognitive Memory Layer (Phase 3).
    Interfaces with Backboard.io to persist conversational context and "rejected logic".
    """
    
    def __init__(self):
        self.api_key = os.getenv("BACKBOARD_API_KEY")
        self.project_id = os.getenv("BACKBOARD_PROJECT_ID")
        self.base_url = "https://api.backboard.io/v1" # Placeholder for actual Backboard API URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def store_reflection(self, tenant_id: str, context: str, outcome: str):
        """
        Stores a "reflection" of an interaction (e.g. why a manager rejected an alert).
        """
        if not self.api_key:
            logger.warning("Backboard API key missing. Skipping memory storage.")
            return

        payload = {
            "projectId": self.project_id,
            "tags": [tenant_id, "reflection"],
            "content": f"Context: {context} | Outcome: {outcome}"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(f"{self.base_url}/memories", json=payload, headers=self.headers)
                if response.status_code == 201:
                    logger.info(f"Successfully stored reflection for tenant {tenant_id}")
                else:
                    logger.error(f"Backboard Error: {response.text}")
            except Exception as e:
                logger.error(f"Failed to connect to Backboard: {str(e)}")

    async def get_relevant_context(self, tenant_id: str, current_query: str) -> str:
        """
        Retrieves relevant historical context based on semantic similarity.
        """
        if not self.api_key:
            return ""

        # Simplified search logic for Backboard
        params = {
            "projectId": self.project_id,
            "tag": tenant_id,
            "query": current_query,
            "limit": 3
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/memories/search", params=params, headers=self.headers)
                if response.status_code == 200:
                    memories = response.json().get("data", [])
                    return "\n".join([m.get("content", "") for m in memories])
                return ""
            except Exception as e:
                logger.error(f"Failed to connect to Backboard: {str(e)}")
                return ""

    async def learn_from_feedback(self, tenant_id: str, alert_id: str, feedback: str):
        """
        Specifically stores negative feedback to prevent "Boy who cried wolf" repetition.
        """
        await self.store_reflection(tenant_id, f"AlertID: {alert_id}", f"Manager Feedback: {feedback}")
