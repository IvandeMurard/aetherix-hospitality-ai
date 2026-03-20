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
        similar_patterns: List[Dict],
        cognitive_context: Optional[str] = None
    ) -> Dict:
        """Calls Claude to explain the prediction rationale."""
        if not self.claude:
            return {"summary": "Claude API key missing. Numerical forecast only.", "confidence_factors": []}

        prompt = self._build_prompt(predicted_covers, confidence, target_date, service_type, context, similar_patterns, cognitive_context)
        
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

    def _build_prompt(self, predicted, confidence, dt, svc, context, patterns, cognitive_context) -> str:
        patterns_text = ""
        for p in patterns:
            # Handle different pattern structures (Qdrant payload vs mock)
            payload = p.get('payload', p)
            date_str = payload.get('date', 'Unknown')
            covers = payload.get('actual_covers', payload.get('covers', '??'))
            score = p.get('score', 1.0)
            patterns_text += f"- {date_str}: {covers} covers ({int(score*100)}% similar)\n"
            
        if not patterns_text:
            patterns_text = "No similar historical patterns found."
        
        cognition_text = f"\nLEARNINGS FROM PAST INTERACTIONS:\n{cognitive_context}\n" if cognitive_context else ""
        
        return f"""You are an expert restaurant operations assistant. 
Prophet (ML model) predicted {predicted} covers for {dt.strftime('%A, %B %d')} ({svc}) with {int(confidence*100)}% confidence.

SIMILAR PATTERNS:
{patterns_text}

CONTEXT:
WEATHER: {context.get('weather', {}).get('condition')}
EVENTS: {len(context.get('events', []))} events nearby
{cognition_text}
TASK: Write a 2-sentence explanation for WHY this prediction is plausible. 
Factor in the 'Learnings' if provided (e.g. if the manager previously noted a certain effect).
Keep it actionable for a manager.
"""

    def _extract_factors(self, context, patterns) -> List[str]:
        factors = []
        if context.get('weather'): factors.append(f"Weather: {context['weather'].get('condition')}")
        if context.get('events'): factors.append(f"{len(context['events'])} events nearby")
        if patterns: factors.append("Historical pattern matching")
        return factors
