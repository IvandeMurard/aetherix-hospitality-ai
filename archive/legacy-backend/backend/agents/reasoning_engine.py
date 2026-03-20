"""
Reasoning Engine Agent
Generates human-readable explanations for predictions using Claude AI
"""

from typing import Dict, List, Optional
from datetime import date
from anthropic import AsyncAnthropic
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from ..models.schemas import Pattern


class ReasoningEngine:
    """
    Agent responsible for generating explainable AI reasoning
    
    Uses Claude to:
    - Analyze similar patterns
    - Explain prediction rationale
    - Identify confidence factors
    - Generate human-readable summaries
    """
    
    def __init__(self):
        """Initialize reasoning engine"""
        # Use Anthropic SDK directly
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        self.claude = AsyncAnthropic(api_key=api_key)
    
    async def generate_explanation(
        self,
        predicted_covers: int,
        range_min: int,
        range_max: int,
        confidence: float,
        date: str,
        weather: Dict,
        events: List,
        features: Dict,
        patterns: Optional[List[Pattern]] = None,
        day_of_week: Optional[str] = None,
        service_type: Optional[str] = None,
    ) -> Dict:
        """
        Génère une explication pour une prédiction Prophet.
        
        IMPORTANT: Le chiffre est déjà calculé par Prophet (déterministe).
        Claude doit EXPLIQUER ce chiffre, pas le recalculer.
        
        Args:
            predicted_covers: Chiffre calculé par Prophet
            range_min: Borne inférieure de l'intervalle
            range_max: Borne supérieure de l'intervalle
            confidence: Score de confiance (0-1)
            date: Date au format YYYY-MM-DD
            weather: Dict avec condition, temperature, etc.
            events: Liste d'événements
            features: Dict avec weather_score, event_impact, etc.
            patterns: Patterns RAG (contexte interne, SOPs)
            day_of_week: Jour de la semaine
            service_type: Type de service (lunch/dinner/brunch)
        
        Returns:
            Dict avec summary, confidence_factors, patterns_used
        """
        print("  [REASONING] Generating explanation for Prophet prediction...")
        
        # Construire le prompt
        prompt = self._build_explanation_prompt(
            predicted_covers=predicted_covers,
            range_min=range_min,
            range_max=range_max,
            confidence=confidence,
            date=date,
            weather=weather,
            events=events,
            features=features,
            patterns=patterns,
            day_of_week=day_of_week,
            service_type=service_type
        )
        
        print(f"  [REASONING] Prompt preview: {prompt[:500]}...")
        
        # Appeler Claude
        try:
            message = await self.claude.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=500,
                temperature=0.3,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            reasoning_text = message.content[0].text
            print(f"  [REASONING] OK - Generated {len(reasoning_text)} chars")
            
            # Parser la réponse
            reasoning = self._parse_explanation(
                reasoning_text,
                patterns or [],
                weather,
                events,
                confidence
            )
            
            return reasoning
            
        except Exception as e:
            print(f"  [REASONING] Error calling Claude: {e}")
            return self._fallback_explanation(predicted_covers, confidence, patterns or [])
    
    def _build_explanation_prompt(
        self,
        predicted_covers: int,
        range_min: int,
        range_max: int,
        confidence: float,
        date: str,
        weather: Dict,
        events: List,
        features: Dict,
        patterns: Optional[List[Pattern]],
        day_of_week: Optional[str],
        service_type: Optional[str],
    ) -> str:
        """
        Construit le prompt pour expliquer une prédiction Prophet.
        
        Le prompt interdit explicitement de recalculer le chiffre.
        """
        # Formater les patterns RAG
        patterns_text = ""
        if patterns:
            patterns_text = "\n".join([
                f"- {p.date.strftime('%Y-%m-%d')} ({p.event_type or 'Regular service'}): "
                f"{p.actual_covers} covers, {int(p.similarity*100)}% similar"
                for p in patterns[:5]  # Top 5 patterns
            ])
        else:
            patterns_text = "  - No similar patterns found"
        
        # Formater les événements
        events_text = "\n".join([
            f"  - {e.get('type', 'Event')}: {e.get('name', 'Unknown')} "
            f"({e.get('distance_km', 'N/A')}km, {e.get('expected_attendance', 0):,} attendees, "
            f"{e.get('impact', 'medium')} impact)"
            for e in events[:3]
        ]) if events else "  - No major events"
        
        # Formater la météo
        weather_text = (
            f"{weather.get('condition', 'Unknown')}, "
            f"{weather.get('temperature', 'N/A')}°C, "
            f"{weather.get('precipitation', 0)}% precipitation"
        )
        
        # Formater les features utilisées
        features_text = []
        if features.get('weather_score'):
            features_text.append(f"Weather score: {features['weather_score']:.2f}")
        if features.get('event_impact'):
            features_text.append(f"Event impact: {features['event_impact']:.2f}")
        if features.get('occupancy'):
            features_text.append(f"Occupancy: {features['occupancy']:.2f}")
        
        features_summary = ", ".join(features_text) if features_text else "Standard conditions"
        
        prompt = f"""You are an expert restaurant operations assistant. Prophet (a deterministic ML model) has calculated a forecast.

**IMPORTANT: DO NOT RECALCULATE THE NUMBER. Explain WHY this prediction is plausible.**

PREDICTION (from Prophet):
- Date: {date} ({day_of_week or 'Unknown'}) - {service_type or 'service'}
- Predicted covers: {predicted_covers}
- Prediction interval: {range_min} - {range_max}
- Confidence: {int(confidence*100)}%

CONTEXT INTERNE (patterns historiques similaires):
{patterns_text}

CONTEXTE EXTERNE:
- Weather: {weather_text}
- Events nearby:
{events_text}
- Features utilisées: {features_summary}

TASK: Write a 2-3 sentence explanation for WHY {predicted_covers} covers is a plausible prediction.

REQUIREMENTS:
- Start with confidence level (High/Medium/Low)
- Reference similar historical patterns if available
- Explain key factors (events, weather, day of week, seasonality)
- DO NOT calculate or estimate a number - Prophet already did that
- Keep it concise and actionable for restaurant managers
- NO jargon, NO technical terms

EXAMPLE OUTPUT:
"High confidence (85%) for this Saturday dinner. Prophet's forecast of 145 covers aligns with three similar Saturday evenings with nearby concerts that averaged 142-151 covers. The Coldplay concert 3.2km away with 50K attendance will likely drive post-event dining demand, though rain may slightly reduce walk-ins."

YOUR EXPLANATION:"""
        
        return prompt
    
    def _parse_explanation(
        self,
        reasoning_text: str,
        patterns: List[Pattern],
        weather: Dict,
        events: List,
        confidence: float
    ) -> Dict:
        """Parse la réponse Claude en format structuré"""
        summary = reasoning_text.strip()
        
        # Extraire les facteurs de confiance
        confidence_factors = []
        
        # Patterns similaires
        if patterns:
            avg_similarity = sum(p.similarity for p in patterns) / len(patterns) if patterns else 0
            if avg_similarity > 0.9:
                confidence_factors.append("Very similar historical patterns")
            elif avg_similarity > 0.8:
                confidence_factors.append("Similar historical patterns")
            else:
                confidence_factors.append(f"{len(patterns)} historical patterns analyzed")
        
        # Événements
        if events:
            for event in events[:1]:
                confidence_factors.append(f"{event.get('type', 'Event')} nearby ({event.get('distance_km', 'N/A')}km)")
        
        # Météo
        weather_condition = weather.get('condition')
        if weather_condition:
            confidence_factors.append(f"Weather: {weather_condition}")
        
        return {
            "summary": summary,
            "confidence_factors": confidence_factors,
            "patterns_used": patterns
        }
    
    def _fallback_explanation(
        self,
        predicted_covers: int,
        confidence: float,
        patterns: List[Pattern]
    ) -> Dict:
        """Fallback si Claude échoue"""
        confidence_level = "High" if confidence > 0.85 else "Medium" if confidence > 0.70 else "Moderate"
        
        summary = (
            f"{confidence_level} confidence ({int(confidence*100)}%) for Prophet's prediction of "
            f"{predicted_covers} covers. "
        )
        
        if patterns:
            summary += f"Based on {len(patterns)} similar historical patterns."
        else:
            summary += "Based on Prophet's time-series analysis."
        
        return {
            "summary": summary,
            "confidence_factors": [
                "Prophet ML forecast",
                "Time-series analysis",
                f"{len(patterns)} historical patterns" if patterns else "Historical data"
            ],
            "patterns_used": patterns
        }
    
    async def generate_reasoning(
        self,
        predicted_covers: int,
        confidence: float,
        patterns: List[Pattern],
        context: Dict,
        service_date: date,
        service_type: str
    ) -> Dict:
        """
        Generate comprehensive reasoning for prediction
        
        Args:
            predicted_covers: Predicted number of covers
            confidence: Confidence score (0-1)
            patterns: List of similar historical patterns
            context: External context (events, weather, etc)
            service_date: Date of service
            service_type: lunch/dinner/brunch
            
        Returns:
            Dict with summary, confidence_factors, pattern insights
        """
        print("  [REASONING] Generating explanation with Claude...")
        
        # Build prompt for Claude
        prompt = self._build_reasoning_prompt(
            predicted_covers=predicted_covers,
            confidence=confidence,
            patterns=patterns,
            context=context,
            service_date=service_date,
            service_type=service_type
        )
        # DEBUG: Print first 500 chars of prompt
        print(f"  [REASONING] Prompt preview: {prompt[:500]}...")  # DEBUG
        
        # Call Claude API
        try:
            message = await self.claude.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=500,
                temperature=0.3,  # Lower temperature for consistent explanations
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Extract reasoning from Claude's response
            reasoning_text = message.content[0].text
            
            print(f"  [REASONING] OK - Generated {len(reasoning_text)} chars")
            print(f"  [REASONING] Claude response preview: {reasoning_text[:200]}...")  # DEBUG
            
            # Parse Claude's response into structured format
            reasoning = self._parse_reasoning(reasoning_text, patterns, context)
            
            return reasoning
            
        except Exception as e:
            print(f"  [REASONING] Error calling Claude: {e}")
            print(f"  [REASONING] Using fallback reasoning")  # DEBUG
            # Fallback to basic reasoning
            return self._fallback_reasoning(predicted_covers, confidence, patterns)
    
    def _build_reasoning_prompt(
        self,
        predicted_covers: int,
        confidence: float,
        patterns: List[Pattern],
        context: Dict,
        service_date: date,
        service_type: str
    ) -> str:
        """
        Build prompt for Claude to generate reasoning
        
        Prompt engineering: Clear structure, examples, constraints
        """
        
        # Format patterns for prompt
        patterns_text = "\n".join([
            f"- {p.date.strftime('%Y-%m-%d')} ({p.event_type or 'Regular service'}): "
            f"{p.actual_covers} covers, {int(p.similarity*100)}% similar"
            for p in patterns[:3]  # Top 3 patterns
        ])
        
        # Format context - Enhanced
        events_text = "\n".join([
            f"  - {e['type']}: {e['name']} ({e['distance_km']}km, {e['expected_attendance']:,} attendees, {e['start_time']}, {e['impact']} impact)"
            for e in context.get('events', [])
        ]) or "  - No major events"
        
        weather_data = context.get('weather', {})
        weather_text = (
            f"{weather_data.get('condition', 'Unknown')}, "
            f"{weather_data.get('temperature', 'N/A')}C, "
            f"{weather_data.get('precipitation', 0)}% precipitation, "
            f"{weather_data.get('wind_speed', 0)}km/h wind"
        )
        
        day_type = context.get('day_type', 'weekday')
        
        prompt = f"""You are an expert restaurant operations assistant. Generate a concise explanation for a staffing prediction.

PREDICTION DETAILS:
- Date: {service_date.strftime('%A, %B %d, %Y')} ({service_type})
- Predicted covers: {predicted_covers}
- Confidence: {int(confidence*100)}%

SIMILAR HISTORICAL PATTERNS:
{patterns_text}

EXTERNAL CONTEXT:
- Day: {context.get('day_of_week', 'Unknown')} ({day_type})
- Events nearby:
{events_text}
- Weather: {weather_text}
- Holiday: {'Yes' if context.get('is_holiday') else 'No'}

TASK: Write a 2-3 sentence explanation for WHY we predict {predicted_covers} covers with {int(confidence*100)}% confidence.

REQUIREMENTS:
- Start with confidence level (High/Medium/Low)
- Reference the most relevant pattern(s)
- Explain key factors (events, weather, day of week)
- Keep it concise and actionable for restaurant managers
- NO jargon, NO technical terms

EXAMPLE OUTPUT:
"High confidence (88%) for this Saturday dinner. Three similar Saturday evenings with nearby concerts averaged 145 covers. The Coldplay concert 3.2km away with 50K attendance will likely drive post-event dining demand, though rain may slightly reduce walk-ins."

YOUR EXPLANATION:"""
        
        return prompt
    
    def _parse_reasoning(
        self, 
        reasoning_text: str, 
        patterns: List[Pattern],
        context: Dict
    ) -> Dict:
        """
        Parse Claude's response into structured format
        
        Extracts:
        - Summary (the main explanation)
        - Confidence factors (list of key drivers)
        """
        
        # Summary is Claude's full response
        summary = reasoning_text.strip()
        
        # Extract confidence factors from context and patterns
        confidence_factors = []
        
        # Day of week factor
        if context.get('day_of_week'):
            confidence_factors.append(f"Similar {context['day_of_week']} patterns")
        
        # Event factor
        if context.get('events'):
            for event in context['events'][:1]:  # First event only
                confidence_factors.append(f"{event['type']} nearby ({event['distance_km']}km)")
        
        # Weather factor
        weather_condition = context.get('weather', {}).get('condition')
        if weather_condition:
            confidence_factors.append(f"Weather: {weather_condition}")
        
        # Pattern similarity
        if patterns:
            avg_similarity = sum(p.similarity for p in patterns) / len(patterns)
            if avg_similarity > 0.9:
                confidence_factors.append("Very similar historical patterns")
            elif avg_similarity > 0.8:
                confidence_factors.append("Similar historical patterns")
        
        return {
            "summary": summary,
            "confidence_factors": confidence_factors,
            "patterns_used": patterns  # Will be formatted by main.py
        }
    
    def _fallback_reasoning(
        self,
        predicted_covers: int,
        confidence: float,
        patterns: List[Pattern]
    ) -> Dict:
        """
        Fallback reasoning if Claude API fails
        
        Simple template-based explanation
        """
        
        confidence_level = "High" if confidence > 0.85 else "Medium" if confidence > 0.70 else "Moderate"
        
        summary = (
            f"{confidence_level} confidence ({int(confidence*100)}%) based on "
            f"{len(patterns)} similar historical patterns averaging "
            f"{predicted_covers} covers."
        )
        
        return {
            "summary": summary,
            "confidence_factors": [
                "Historical patterns",
                "Day of week similarity",
                "Service type match"
            ],
            "patterns_used": patterns
        }


# Singleton instance
_reasoning_engine = None

def get_reasoning_engine() -> ReasoningEngine:
    """Get reasoning engine singleton"""
    global _reasoning_engine
    if _reasoning_engine is None:
        _reasoning_engine = ReasoningEngine()
    return _reasoning_engine