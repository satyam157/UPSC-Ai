#!/usr/bin/env python3
"""Quick test that news can be retrieved"""

from db import get_news

print("Getting news...")
news = get_news()
print(f"Retrieved: {len(news)} items")
if news:
    print("\nLatest 5:")
    for i, n in enumerate(news[:5], 1):
        print(f"{i}. {n[0][:70]} ({n[2]})")
