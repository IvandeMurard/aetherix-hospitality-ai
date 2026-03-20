"""
Agent 1: Analyzer
Extracts features from event description and generates embedding
"""

from mistralai import Mistral
import os
from dotenv import load_dotenv

load_dotenv()

class AnalyzerAgent:
    def __init__(self):
        self.mistral = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
    
    def extract_features(self, event_description: str) -> dict:
        """
        Extract structured features from event description
        """
        prompt = f"""Extract key features from this F&B event description:
"{event_description}"

Return JSON with these fields:
- day_of_week (Monday-Sunday or "unknown")
- event_type (concert, sports, festival, wedding, corporate, holiday, or "unknown")
- event_magnitude (small, medium, large, or "unknown")
- weather (if mentioned, otherwise "unknown")
- special_notes (any other relevant details)

Be concise. Output ONLY valid JSON, no markdown."""

        response = self.mistral.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse response
        import json
        features_text = response.choices[0].message.content
        # Strip markdown if present
        features_text = features_text.replace("```json", "").replace("```", "").strip()
        features = json.loads(features_text)
        
        return features
    
    def generate_embedding(self, event_description: str) -> list:
        """
        Generate vector embedding for event description
        """
        response = self.mistral.embeddings.create(
            model="mistral-embed",
            inputs=[event_description]
        )
        
        return response.data[0].embedding
    
    def analyze(self, event_description: str) -> dict:
        """
        Complete analysis: extract features + generate embedding
        """
        print(f"🔍 Analyzing: '{event_description}'")
        
        # Extract features
        features = self.extract_features(event_description)
        print(f"   Features extracted: {features}")
        
        # Generate embedding
        embedding = self.generate_embedding(event_description)
        print(f"   Embedding generated: {len(embedding)} dimensions")
        
        return {
            "original_description": event_description,
            "features": features,
            "embedding": embedding
        }

# Test
if __name__ == "__main__":
    agent = AnalyzerAgent()
    result = agent.analyze("Concert tomorrow evening, sunny weather")
    print(f"\n✅ Analyzer working!")
    print(f"   Features: {result['features']}")

