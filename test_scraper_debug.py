#!/usr/bin/env python3
"""Debug script to test news fetching"""

import feedparser
from datetime import datetime
from filter import is_relevant

def test_feeds():
    urls = [
        "https://pib.gov.in/RssMain.aspx",
        "https://www.thehindu.com/news/national/feeder/default.rss",
        "https://indianexpress.com/section/india/feed/",
        "https://indianexpress.com/section/explained/feed/"
    ]
    
    print("=" * 80)
    print("TESTING RSS FEEDS")
    print("=" * 80)
    
    for url in urls:
        print(f"\n📡 Testing: {url}")
        print("-" * 80)
        
        try:
            feed = feedparser.parse(url)
            print(f"✓ Feed parsed. Entries found: {len(feed.entries)}")
            
            if feed.entries:
                print("\nFirst 5 titles from this feed:")
                for i, entry in enumerate(feed.entries[:5], 1):
                    title = entry.get("title", "NO TITLE")
                    is_rel = is_relevant(title)
                    status = "✓ PASS" if is_rel else "✗ BLOCKED"
                    print(f"  {i}. [{status}] {title[:80]}")
            else:
                print("✗ No entries in feed!")
                
        except Exception as e:
            print(f"✗ ERROR: {e}")
    
    print("\n" + "=" * 80)
    print("TESTING FILTER FUNCTION")
    print("=" * 80)
    
    test_titles = [
        "Government announces new policy on climate change",
        "RBI raises interest rates by 50 basis points",
        "India wins UNESCO award for heritage conservation",
        "Supreme Court ruling on environmental protection",
        "New bill passed in Parliament for education reform",
        "India-Pakistan border talks resume",
        "Economic survey predicts 7% GDP growth",
        "Bollywood actress wins award", # Should be blocked
        "IPL match result: Mumbai wins", # Should be blocked
        "Election commission announces new rules",
        "Housing prices surge in major cities",
        "Food inflation reaches 10%",
        "This is a very short title", # Should be blocked (too short)
    ]
    
    print("\nTesting filter on sample titles:")
    print("-" * 80)
    
    for title in test_titles:
        is_rel = is_relevant(title)
        status = "✓ PASS" if is_rel else "✗ BLOCKED"
        print(f"{status} | {title}")

if __name__ == "__main__":
    test_feeds()
