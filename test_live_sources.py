"""
Live connectivity test: Check each RSS source and count how many articles pass through.
"""
import sys
sys.path.insert(0, '.')

from news_fetcher_Advanced import fetch_all_news, RSS_FEEDS

print("=" * 70)
print("LIVE SOURCE CONNECTIVITY & FILTER TEST")
print("=" * 70)

# Test each feed individually to see per-source results
for label, rss_url, category, auto_pass in RSS_FEEDS:
    feed_tuple = [(label, rss_url, category, auto_pass)]
    articles = fetch_all_news(feeds=feed_tuple, max_per_feed=10, verbose=False)
    status = f"✅ {len(articles):2d} articles" if articles else "❌ 0 articles"
    ap_tag = " [AUTO-PASS]" if auto_pass else ""
    print(f"  {status} | {label:<28} | {category:<25}{ap_tag}")

print("\n" + "=" * 70)
print("FULL FETCH (all sources combined):")
print("=" * 70)
all_articles = fetch_all_news(max_per_feed=15, verbose=True)

# Summary by source
from collections import Counter
source_counts = Counter(a['source'] for a in all_articles)
print(f"\n{'─' * 50}")
print(f"{'SOURCE':<30} {'COUNT':>5}")
print(f"{'─' * 50}")
for src, count in source_counts.most_common():
    print(f"  {src:<28} {count:>5}")
print(f"{'─' * 50}")
print(f"  {'TOTAL':<28} {len(all_articles):>5}")

# Show sample PIB articles
pib_articles = [a for a in all_articles if 'pib' in a['source'].lower()]
if pib_articles:
    print(f"\n📢 PIB Articles ({len(pib_articles)} total):")
    for a in pib_articles[:10]:
        print(f"  • {a['title'][:75]}")
else:
    print("\n⚠️ No PIB articles fetched — check PIB RSS connectivity!")

# Show sample DTE articles
dte_articles = [a for a in all_articles if 'down to earth' in a['source'].lower()]
if dte_articles:
    print(f"\n🌍 Down to Earth Articles ({len(dte_articles)} total):")
    for a in dte_articles[:10]:
        print(f"  • {a['title'][:75]}")
else:
    print("\n⚠️ No Down to Earth articles fetched — check DTE RSS connectivity!")
