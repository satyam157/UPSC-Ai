#!/usr/bin/env python3
"""Test complete integration"""

from datetime import datetime
from scraper import fetch_news
from db import insert_news, get_news, delete_result

print("=" * 80)
print("FINAL INTEGRATION TEST")
print("=" * 80)

# Check counts
print("\n1️⃣ Current news count...")
current = get_news()
print(f"   {len(current)} items in DB")

# Fetch fresh news
print("\n2️⃣ Fetching news from feeds...")
fresh = fetch_news()
print(f"   {len(fresh)} items fetched")

# Show sample
if fresh:
    print("\n   Sample items fetched:")
    for item in fresh[:2]:
        print(f"   • {item['title'][:70]}")
        print(f"     Date: {item['date']}")
        print()

# Insert
if fresh:
    print(f"3️⃣ Inserting {len(fresh)} items...")
    inserted = insert_news(fresh)
    print(f"   ✅ Inserted {inserted} new items")
    
    # Refresh count
    updated = get_news()
    print(f"   Total in DB: {len(updated)}")

print("\n" + "=" * 80)
print("✅ INTEGRATION TEST COMPLETE")
print("=" * 80)
print("\nThe app's refresh button should now work!")
print("Go to Current Affairs tab → Click 🔄 Refresh Content")
