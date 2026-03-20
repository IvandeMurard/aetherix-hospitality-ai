"""
Events Fetcher Agent
Fetches real-world events from PredictHQ API
"""

import os
from dotenv import load_dotenv
from datetime import datetime
from typing import List, Dict, Optional
import requests

load_dotenv()

class EventsFetcher:
    def __init__(self):
        self.api_key = os.getenv("PREDICTHQ_API_KEY") or os.getenv("PREDICTHQ_ACCESS_TOKEN")
        self.base_url = "https://api.predicthq.com/v1"
        
        if not self.api_key:
            print("⚠️  PREDICTHQ_API_KEY not found in environment variables")
            print("   Please add PREDICTHQ_API_KEY to your .env file")
            print("   Get your API key at: https://predicthq.com/")
            # Don't raise error, allow testing with mock data
    
    def fetch_events(
        self, 
        date: str, 
        location: str = "Paris, France",
        radius: str = "10km",
        limit: int = 10
    ) -> List[Dict]:
        """
        Fetch events for a specific date and location
        
        Args:
            date: Date in format "YYYY-MM-DD"
            location: Location string (e.g., "Paris, France")
            radius: Search radius (e.g., "10km")
            limit: Maximum number of events to return
        
        Returns:
            List of event dictionaries
        """
        print(f"🎪 Fetching events for {date} in {location}...")
        
        # Parse date
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
            start_date = target_date.strftime("%Y-%m-%d")
            end_date = target_date.strftime("%Y-%m-%d")
        except ValueError:
            print(f"   ⚠️  Invalid date format. Expected YYYY-MM-DD, got: {date}")
            return []
        
        # Prepare headers
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }
        
        # Prepare query parameters
        # Convert location string to coordinates if needed (e.g., "Paris, France" -> coordinates)
        # For now, use a default Paris coordinate if location is not in lat,lon format
        if "," in location and not any(char.isdigit() for char in location.split(",")[0]):
            # It's a city name, use Paris coordinates as default
            origin = "48.8566,2.3522"  # Paris coordinates
        else:
            origin = location
        
        params = {
            "start": f"{start_date}T00:00:00",
            "end": f"{end_date}T23:59:59",
            "location_around.origin": origin,
            "location_around.radius": radius,
            "limit": limit,
            "category": "concerts,sports,festivals,conferences,community,performing-arts"
        }
        
        if not self.api_key:
            print(f"   ⚠️  Cannot fetch events: API key not configured")
            return []
        
        try:
            # Make API request
            response = requests.get(
                f"{self.base_url}/events/",
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                events = data.get("results", [])
                
                # Format events
                formatted_events = []
                for event in events:
                    event_info = {
                        "title": event.get("title", "Unknown Event"),
                        "category": event.get("category", "unknown"),
                        "start": event.get("start", ""),
                        "location": event.get("location", {}).get("name", location),
                        "rank": event.get("rank", 0),
                        "phq_attendance": event.get("phq_attendance", {}).get("value", 0)
                    }
                    formatted_events.append(event_info)
                    
                    # Print event
                    category_emoji = {
                        "concerts": "🎵",
                        "sports": "⚽",
                        "festivals": "🎪",
                        "conferences": "💼",
                        "community": "👥",
                        "performing-arts": "🎭"
                    }
                    emoji = category_emoji.get(event_info["category"], "📅")
                    print(f"   {emoji} {event_info['title']} ({event_info['category']})")
                
                if formatted_events:
                    event_names = [e['title'] for e in formatted_events]
                    print(f"\n✅ Events found: {', '.join(event_names[:3])}")
                    if len(event_names) > 3:
                        print(f"   ... and {len(event_names) - 3} more")
                else:
                    print(f"   ℹ️  No events found for {date} in {location}")
                
                return formatted_events
            else:
                print(f"   ❌ API Error: {response.status_code}")
                print(f"   Response: {response.text}")
                return []
                
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Request failed: {e}")
            return []
    
    def get_events_summary(self, date: str, location: str = "Paris, France") -> str:
        """
        Get a natural language summary of events for a date
        
        Args:
            date: Date in format "YYYY-MM-DD"
            location: Location string
        
        Returns:
            Natural language summary string
        """
        events = self.fetch_events(date, location)
        
        if not events:
            return f"No events found for {date} in {location}"
        
        # Group by category
        by_category = {}
        for event in events:
            category = event["category"]
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(event["title"])
        
        # Build summary
        summary_parts = []
        for category, titles in by_category.items():
            if len(titles) == 1:
                summary_parts.append(f"{titles[0]} ({category})")
            else:
                summary_parts.append(f"{', '.join(titles[:2])} ({category})")
                if len(titles) > 2:
                    summary_parts[-1] += f" and {len(titles) - 2} more"
        
        return ", ".join(summary_parts)

# Test
if __name__ == "__main__":
    fetcher = EventsFetcher()
    
    # Test with a specific date
    test_date = "2024-11-20"
    events = fetcher.fetch_events(test_date, location="Paris, France")
    
    if events:
        print(f"\n📊 Summary:")
        print(f"   Total events found: {len(events)}")
        print(f"   Categories: {', '.join(set(e['category'] for e in events))}")
    else:
        print(f"\n⚠️  No events found. Check your API key and date format.")
