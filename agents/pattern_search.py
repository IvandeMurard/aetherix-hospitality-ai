"""
Qdrant Pattern Search
Finds similar historical scenarios
"""

from qdrant_client import QdrantClient
import os
from dotenv import load_dotenv

load_dotenv()

class PatternSearcher:
    def __init__(self):
        # Use in-memory Qdrant for local demo (seeded on API startup)
        self.qdrant = QdrantClient(":memory:")
        self.collection_name = "hospitality_patterns"
    
    def search_similar_patterns(self, embedding: list, limit: int = 3) -> list:
        """
        Search for similar past scenarios in Qdrant
        """
        print(f"🔎 Searching Qdrant for {limit} similar patterns...")
        
        results = self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=embedding,
            limit=limit
        )
        
        patterns = []
        for idx, result in enumerate(results):
            pattern = {
                "rank": idx + 1,
                "similarity_score": result.score,
                "scenario": result.payload
            }
            patterns.append(pattern)
            
            print(f"   #{idx+1}: {result.payload['event_name']} "
                  f"(similarity: {result.score:.3f})")
        
        return patterns

# Test
if __name__ == "__main__":
    from agents.analyzer import AnalyzerAgent
    
    # Analyze event
    analyzer = AnalyzerAgent()
    analysis = analyzer.analyze("Concert tomorrow evening")
    
    # Search patterns
    searcher = PatternSearcher()
    patterns = searcher.search_similar_patterns(analysis["embedding"])
    
    print(f"\n✅ Pattern search working! Found {len(patterns)} similar scenarios")

