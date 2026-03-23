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
            return self._heuristic_explanation(
                predicted_covers, confidence, target_date, service_type, context, similar_patterns
            )

        prompt = self._build_prompt(predicted_covers, confidence, target_date, service_type, context, similar_patterns, cognitive_context)
        
        try:
            message = await self.claude.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=300,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
            explanation = message.content[0].text.strip()
            return {
                "summary": explanation,
                "confidence_factors": self._extract_factors(context, similar_patterns),
                "claude_used": True,
            }
        except Exception as e:
            import asyncio
            from app.services.ops_dispatcher import dispatch_error
            asyncio.ensure_future(dispatch_error(
                title="Reasoning service failure — Claude API error",
                detail=f"Exception: {e}\nDate: {target_date} | Service: {service_type} | Covers: {predicted_covers}",
                tags=["claude", "reasoning"],
            ))
            return {
                **self._heuristic_explanation(
                    predicted_covers, confidence, target_date, service_type, context, similar_patterns
                ),
                "claude_used": False,
                "fallback_reason": str(e),
            }

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

    def _heuristic_explanation(
        self,
        predicted: int,
        confidence: float,
        dt: date,
        svc: str,
        context: Dict,
        patterns: List[Dict],
    ) -> Dict:
        """Rule-based explanation used when Claude is unavailable.

        Produces a human-readable summary using only the data already in hand —
        no LLM call required. This ensures the /predict endpoint always returns
        an actionable reasoning block.
        """
        day_name = dt.strftime("%A")
        conf_pct = int(confidence * 100)

        # Pattern anchor sentence
        if patterns:
            best = patterns[0]
            payload = best.get("payload", best)
            hist_covers = payload.get("actual_covers", payload.get("covers", "?"))
            hist_date = payload.get("date", "a similar past date")
            pattern_note = (
                f"Historical data shows {hist_covers} covers on {hist_date} "
                f"under similar conditions."
            )
        else:
            pattern_note = "No close historical pattern available for direct comparison."

        # Context modifiers
        weather = context.get("weather", {})
        weather_note = ""
        if weather.get("condition"):
            weather_note = f" Current weather is {weather['condition']}."

        events = context.get("events", [])
        event_note = ""
        if events:
            event_note = f" {len(events)} nearby event(s) may drive additional demand."

        occ = context.get("occupancy")
        occ_note = f" Hotel occupancy is at {int(occ * 100)}%." if occ else ""

        summary = (
            f"Prophet forecasts {predicted} covers for {svc} on {day_name} "
            f"with {conf_pct}% confidence. "
            f"{pattern_note}{weather_note}{event_note}{occ_note}"
        ).strip()

        return {
            "summary": summary,
            "confidence_factors": self._extract_factors(context, patterns),
            "claude_used": False,
        }
