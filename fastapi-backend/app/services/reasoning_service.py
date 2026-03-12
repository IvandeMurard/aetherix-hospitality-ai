from anthropic import AsyncAnthropic
import os
from typing import Dict, List, Optional
from datetime import date

class ReasoningService:
    """
    Service for generating explainable AI reasoning using Claude.
    Explains Prophet's numerical forecast using RAG patterns and external context.
    """
    
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        self.claude = AsyncAnthropic(api_key=api_key) if api_key else None

    async def generate_explanation(
        self,
        predicted_covers: int,
        confidence: float,
        target_date: date,
        service_type: str,
        context: Dict,
        similar_patterns: List[Dict]
    ) -> Dict:
        """Calls Claude to explain the prediction rationale."""
        if not self.claude:
            return {"summary": "Claude API key missing. Numerical forecast only.", "confidence_factors": []}

        prompt = self._build_prompt(predicted_covers, confidence, target_date, service_type, context, similar_patterns)
        
        try:
            message = await self.claude.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=300,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
            explanation = message.content[0].text.strip()
            return {
                "summary": explanation,
                "confidence_factors": self._extract_factors(context, similar_patterns)
            }
        except Exception as e:
            return {"summary": f"Reasoning failed: {str(e)}", "confidence_factors": []}

    def _build_prompt(self, predicted, confidence, dt, svc, context, patterns) -> str:
        patterns_text = "\n".join([
            f"- {p['payload'].get('date')}: {p['payload'].get('actual_covers')} covers ({int(p['score']*100)}% similar)"
            for p in patterns
        ]) or "No similar historical patterns found."
        
        return f"""You are an expert restaurant operations assistant. 
Prophet (ML model) predicted {predicted} covers for {dt.strftime('%A, %B %d')} ({svc}) with {int(confidence*100)}% confidence.

SIMILAR PATTERNS:
{patterns_text}

CONTEXT:
Weather: {context.get('weather', {}).get('condition')}
Events: {len(context.get('events', []))} events nearby

TASK: Write a 2-sentence explanation for WHY this prediction is plausible. 
DO NOT recalculate the number. Keep it actionable for a manager.
"""

    def _extract_factors(self, context, patterns) -> List[str]:
        factors = []
        if context.get('weather'): factors.append(f"Weather: {context['weather'].get('condition')}")
        if context.get('events'): factors.append(f"{len(context['events'])} events nearby")
        if patterns: factors.append("Historical pattern matching")
        return factors
