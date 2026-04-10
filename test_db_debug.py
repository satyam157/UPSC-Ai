#!/usr/bin/env python3
"""Debug script to test database operations"""

import feedparser
from datetime import datetime
from filter import is_relevant
from db import insert_news, get_news, get_connection

def test_db_operations():
    print("=" * 80)
    print("TESTING DATABASE OPERATIONS")
    print("=" * 80)
    
    # Test connection
    print("\n1️⃣ Testing database connection...")
    conn = get_connection()
    if conn:
        print("✓ Database connection successful")
        conn.close()
    else:
        print("✗ Database connection FAILED!")
        return
    
    # Check existing news
    print("\n2️⃣ Checking existing news in database...")
    existing = get_news()
    print(f"   Total news items in DB: {len(existing)}")
    if existing:
        print(f"   Most recent: {existing[0][0][:60]}")
        print(f"   Date: {existing[0][2]}")
    
    # Fetch from feeds
    print("\n3️⃣ Fetching news from feeds...")
    urls = [
        "https://www.thehindu.com/news/national/feeder/default.rss",
        "https://indianexpress.com/section/india/feed/",
    ]
    
    all_fetched = []
    for url in urls:
        feed = feedparser.parse(url)
        for e in feed.entries[:5]:
            title = e.get("title", "").strip()
            if title and is_relevant(title):
                all_fetched.append({
                    "title": title,
                    "content": getattr(e, "summary", "").strip(),
                    "link": getattr(e, "link", "").strip(),
                    "date": datetime.now().strftime("%Y-%m-%d")
                })
                print(f"   ✓ {title[:70]}")
    
    if not all_fetched:
        print("   ✗ No news items passed filter!")
        return
        
    print(f"\n   Total to insert: {len(all_fetched)}")
    
    # Try to insert
    print("\n4️⃣ Attempting to insert news...")
    try:
        insert_news(all_fetched)
        print("✓ News insertion attempted")
    except Exception as e:
        print(f"✗ Error during insertion: {e}")
        return
    
    # Check again
    print("\n5️⃣ Checking database after insertion...")
    updated = get_news()
    print(f"   Total news items now: {len(updated)}")
    if len(updated) > len(existing):
        print(f"   ✓ Added {len(updated) - len(existing)} new items")
    else:
        print(f"   ✗ No new items added (duplicate check active)")

if __name__ == "__main__":
    test_db_operations()
