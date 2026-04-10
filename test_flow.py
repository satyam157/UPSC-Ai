#!/usr/bin/env python3
"""Test complete news fetch and insert flow"""

from scraper import fetch_news
from db import insert_news, get_news

print("=" * 80)
print("COMPLETE NEWS FLOW TEST")
print("=" * 80)

# Check current count
print("\n1️⃣ Current news count in DB...")
existing = get_news()
print(f"   Total: {len(existing)}")
if existing:
    print(f"   Most recent: {existing[0][0][:60]}")

# Fetch new  
print("\n2️⃣ Fetching news...")
news = fetch_news()
print(f"   Fetched: {len(news)} items")
if news:
    for n in news[:3]:
        print(f"   - {n['title'][:60]}")

# Insert
if news:
    print(f"\n3️⃣ Inserting {len(news)} items...")
    count = insert_news(news)
    print(f"   Inserted: {count} items")
    
    # Check new count
    print("\n4️⃣ New count after insert...")
    new_news = get_news()
    print(f"   Total: {len(new_news)}")
    print(f"   Added: {len(new_news) - len(existing)} new items")
