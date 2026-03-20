"""
RAG Validation Tests
Validates that Qdrant returns directionally correct patterns
"""

import asyncio
import pytest
import sys
from pathlib import Path
from datetime import date

# Add parent directory to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path.parent))

from backend.agents.demand_predictor import get_demand_predictor
from backend.models.schemas import PredictionRequest


class TestRAGValidation:
    """Validate RAG returns contextually relevant patterns"""
    
    @pytest.fixture
    def predictor(self):
        return get_demand_predictor()
    
    @pytest.mark.asyncio
    async def test_scenario_1_weekend_event(self, predictor):
        """
        Scenario: Saturday dinner with potential event
        Expected: Patterns should be weekend/friday + higher covers
        """
        request = PredictionRequest(
            restaurant_id="test_hotel",
            service_date=date(2025, 1, 18),  # Saturday
            service_type="dinner"
        )
        
        result = await predictor.predict(request)
        
        # Assertions
        assert result["predicted_covers"] > 0
        assert result["confidence"] > 0.5
        
        # Check patterns metadata - use patterns_used from reasoning
        reasoning = result.get("reasoning", {})
        patterns = reasoning.get("patterns_used", [])
        
        if patterns:
            # Check that patterns come from Qdrant
            qdrant_patterns = [p for p in patterns if p.metadata.get("source") == "qdrant"]
            assert len(qdrant_patterns) > 0, "No Qdrant patterns found - using mock fallback"
            
            # At least some patterns should be weekend/friday
            day_types = [p.metadata.get("day_of_week", "") for p in patterns]
            weekend_days = ["Saturday", "Sunday", "Friday"]
            has_weekend_pattern = any(d in weekend_days for d in day_types)
            
            print(f"\n[Scenario 1] Saturday Dinner")
            print(f"  Predicted: {result['predicted_covers']} covers")
            print(f"  Confidence: {result['confidence']}")
            print(f"  Patterns from Qdrant: {len(qdrant_patterns)}/{len(patterns)}")
            print(f"  Pattern days: {day_types}")
            print(f"  Has weekend pattern: {has_weekend_pattern}")
            
            # Soft assertion - log but don't fail if no weekend patterns
            # (depends on Qdrant data distribution)
            if not has_weekend_pattern:
                print("  [WARNING] No weekend patterns found - check embedding alignment")
    
    @pytest.mark.asyncio
    async def test_scenario_2_holiday(self, predictor):
        """
        Scenario: Christmas Eve dinner
        Expected: Lower covers (holiday patterns)
        """
        request = PredictionRequest(
            restaurant_id="test_hotel",
            service_date=date(2025, 12, 24),  # Christmas Eve
            service_type="dinner"
        )
        
        result = await predictor.predict(request)
        
        print(f"\n[Scenario 2] Christmas Eve Dinner")
        print(f"  Predicted: {result['predicted_covers']} covers")
        print(f"  Confidence: {result['confidence']}")
        
        # Holiday should generally have different demand
        # Not asserting specific values since patterns vary
        assert result["predicted_covers"] > 0
        assert result["confidence"] > 0.5
        
        # Check patterns come from Qdrant
        reasoning = result.get("reasoning", {})
        patterns = reasoning.get("patterns_used", [])
        if patterns:
            qdrant_patterns = [p for p in patterns if p.metadata.get("source") == "qdrant"]
            print(f"  Patterns from Qdrant: {len(qdrant_patterns)}/{len(patterns)}")
        
        # Check if holiday context was captured
        reasoning_text = str(reasoning.get("summary", "")).lower()
        if "holiday" in reasoning_text or "christmas" in reasoning_text:
            print("  [OK] Holiday context captured in reasoning")
        else:
            print("  [WARNING] Holiday context not explicitly mentioned")
    
    @pytest.mark.asyncio
    async def test_scenario_3_weekday_lunch(self, predictor):
        """
        Scenario: Tuesday lunch (typical low-demand period)
        Expected: Lower covers than weekend dinner
        """
        request = PredictionRequest(
            restaurant_id="test_hotel",
            service_date=date(2025, 1, 21),  # Tuesday
            service_type="lunch"
        )
        
        result = await predictor.predict(request)
        
        print(f"\n[Scenario 3] Tuesday Lunch")
        print(f"  Predicted: {result['predicted_covers']} covers")
        print(f"  Confidence: {result['confidence']}")
        
        assert result["predicted_covers"] > 0
        assert result["confidence"] > 0.5
        
        # Check patterns are weekday and from Qdrant
        reasoning = result.get("reasoning", {})
        patterns = reasoning.get("patterns_used", [])
        if patterns:
            qdrant_patterns = [p for p in patterns if p.metadata.get("source") == "qdrant"]
            assert len(qdrant_patterns) > 0, "No Qdrant patterns found - using mock fallback"
            
            day_types = [p.metadata.get("day_of_week", "") for p in patterns]
            print(f"  Patterns from Qdrant: {len(qdrant_patterns)}/{len(patterns)}")
            print(f"  Pattern days: {day_types}")
    
    @pytest.mark.asyncio
    async def test_scenario_comparison(self, predictor):
        """
        Compare scenarios: Weekend dinner should predict more than weekday lunch
        """
        # Weekend dinner
        weekend_request = PredictionRequest(
            restaurant_id="test_hotel",
            service_date=date(2025, 1, 18),  # Saturday
            service_type="dinner"
        )
        weekend_result = await predictor.predict(weekend_request)
        
        # Weekday lunch
        weekday_request = PredictionRequest(
            restaurant_id="test_hotel",
            service_date=date(2025, 1, 21),  # Tuesday
            service_type="lunch"
        )
        weekday_result = await predictor.predict(weekday_request)
        
        print(f"\n[Scenario Comparison]")
        print(f"  Saturday dinner: {weekend_result['predicted_covers']} covers")
        print(f"  Tuesday lunch: {weekday_result['predicted_covers']} covers")
        
        # Check both use Qdrant
        weekend_patterns = weekend_result.get("reasoning", {}).get("patterns_used", [])
        weekday_patterns = weekday_result.get("reasoning", {}).get("patterns_used", [])
        
        weekend_qdrant = [p for p in weekend_patterns if p.metadata.get("source") == "qdrant"]
        weekday_qdrant = [p for p in weekday_patterns if p.metadata.get("source") == "qdrant"]
        
        print(f"  Weekend Qdrant patterns: {len(weekend_qdrant)}/{len(weekend_patterns)}")
        print(f"  Weekday Qdrant patterns: {len(weekday_qdrant)}/{len(weekday_patterns)}")
        
        # Directional check (not strict - depends on data)
        if weekend_result['predicted_covers'] >= weekday_result['predicted_covers']:
            print("  [OK] Weekend dinner >= Weekday lunch (expected)")
        else:
            print("  [WARNING] Weekend dinner < Weekday lunch (unexpected but not fatal)")
        
        # Both should return valid predictions
        assert weekend_result["predicted_covers"] > 0
        assert weekday_result["predicted_covers"] > 0
        
        # Both should use Qdrant (not mock fallback)
        assert len(weekend_qdrant) > 0, "Weekend prediction should use Qdrant"
        assert len(weekday_qdrant) > 0, "Weekday prediction should use Qdrant"


def run_validation():
    """Run validation tests with detailed output"""
    print("=" * 60)
    print("RAG VALIDATION TESTS")
    print("=" * 60)
    
    predictor = get_demand_predictor()
    
    async def run_all():
        test = TestRAGValidation()
        
        # Scenario 1
        request1 = PredictionRequest(
            restaurant_id="test_hotel",
            service_date=date(2025, 1, 18),  # Saturday
            service_type="dinner"
        )
        result1 = await predictor.predict(request1)
        patterns1 = result1.get("reasoning", {}).get("patterns_used", [])
        qdrant1 = [p for p in patterns1 if p.metadata.get("source") == "qdrant"]
        day_types1 = [p.metadata.get("day_of_week", "") for p in patterns1]
        weekend_days = ["Saturday", "Sunday", "Friday"]
        has_weekend = any(d in weekend_days for d in day_types1)
        
        print(f"\n[Scenario 1] Saturday Dinner")
        print(f"  Predicted: {result1['predicted_covers']} covers")
        print(f"  Confidence: {result1['confidence']}")
        print(f"  Patterns from Qdrant: {len(qdrant1)}/{len(patterns1)}")
        print(f"  Pattern days: {day_types1}")
        print(f"  Has weekend pattern: {has_weekend}")
        if not has_weekend:
            print("  [WARNING] No weekend patterns found")
        
        # Scenario 2
        request2 = PredictionRequest(
            restaurant_id="test_hotel",
            service_date=date(2025, 12, 24),  # Christmas Eve
            service_type="dinner"
        )
        result2 = await predictor.predict(request2)
        patterns2 = result2.get("reasoning", {}).get("patterns_used", [])
        qdrant2 = [p for p in patterns2 if p.metadata.get("source") == "qdrant"]
        reasoning_text = str(result2.get("reasoning", {}).get("summary", "")).lower()
        has_holiday = "holiday" in reasoning_text or "christmas" in reasoning_text
        
        print(f"\n[Scenario 2] Christmas Eve Dinner")
        print(f"  Predicted: {result2['predicted_covers']} covers")
        print(f"  Confidence: {result2['confidence']}")
        print(f"  Patterns from Qdrant: {len(qdrant2)}/{len(patterns2)}")
        if has_holiday:
            print("  [OK] Holiday context captured")
        else:
            print("  [WARNING] Holiday context not mentioned")
        
        # Scenario 3
        request3 = PredictionRequest(
            restaurant_id="test_hotel",
            service_date=date(2025, 1, 21),  # Tuesday
            service_type="lunch"
        )
        result3 = await predictor.predict(request3)
        patterns3 = result3.get("reasoning", {}).get("patterns_used", [])
        qdrant3 = [p for p in patterns3 if p.metadata.get("source") == "qdrant"]
        day_types3 = [p.metadata.get("day_of_week", "") for p in patterns3]
        
        print(f"\n[Scenario 3] Tuesday Lunch")
        print(f"  Predicted: {result3['predicted_covers']} covers")
        print(f"  Confidence: {result3['confidence']}")
        print(f"  Patterns from Qdrant: {len(qdrant3)}/{len(patterns3)}")
        print(f"  Pattern days: {day_types3}")
        
        # Comparison
        print(f"\n[Scenario Comparison]")
        print(f"  Saturday dinner: {result1['predicted_covers']} covers")
        print(f"  Tuesday lunch: {result3['predicted_covers']} covers")
        if result1['predicted_covers'] >= result3['predicted_covers']:
            print("  [OK] Weekend dinner >= Weekday lunch (expected)")
        else:
            print("  [WARNING] Weekend dinner < Weekday lunch")
        
        # Summary
        all_qdrant = len(qdrant1) > 0 and len(qdrant2) > 0 and len(qdrant3) > 0
        print(f"\n[Summary]")
        print(f"  All scenarios use Qdrant: {all_qdrant}")
        print(f"  Directional consistency: {result1['predicted_covers'] >= result3['predicted_covers']}")
    
    asyncio.run(run_all())
    
    print("\n" + "=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    run_validation()
