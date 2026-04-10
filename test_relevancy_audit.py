"""
UPSC Relevancy Audit — test_relevancy_audit.py
===============================================
Fetches news from EACH category separately and shows:
  • What articles are being fetched
  • Which pass/fail the UPSC relevance filter
  • Scores and reasoning for borderline articles

Usage:
    python test_relevancy_audit.py              # audit all categories, last 1 day
    python test_relevancy_audit.py --days 3     # audit last 3 days
    python test_relevancy_audit.py --category "Science & Technology"
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from news_fetcher_Advanced import fetch_all_news, RSS_FEEDS
from filter import is_relevant

# ── Category groups for auditing ──────────────────────────────────────────────
CATEGORY_GROUPS = {
    "Science & Technology": ["Science & Technology"],
    "International / World": ["International"],
    "Economy": ["Economy"],
    "Polity": ["Polity", "National"],
    "Lead / Op-Ed": ["Lead", "Op-Ed", "Opinion"],
    "Environment": ["Environment"],
    "Editorial / Explained": ["Editorial", "Explained"],
    "Governance (PIB)": ["PIB — All Ministries", "PIB — English", "PIB — Press Releases", "Governance"],
}


def audit_category(category_name, category_values, days=1):
    """Fetch and audit a specific category group."""
    # Filter feeds matching these categories
    matching_feeds = [
        f for f in RSS_FEEDS
        if f[2] in category_values  # category is at index 2
    ]
    
    if not matching_feeds:
        print(f"\n⚠️  No feeds found for category: {category_name}")
        return []

    print(f"\n{'═'*70}")
    print(f"  📊 RELEVANCY AUDIT: {category_name}")
    print(f"     Feeds: {len(matching_feeds)} | Window: {days} day(s)")
    print(f"{'═'*70}")
    
    articles = fetch_all_news(
        feeds=matching_feeds,
        max_per_feed=15,
        verbose=True,
        days=days,
    )
    
    if not articles:
        print(f"\n  ℹ️  No articles fetched for {category_name}")
        return []

    # Print articles with relevance analysis
    print(f"\n  📰 Articles ({len(articles)} total):")
    print(f"  {'─'*65}")
    
    for i, a in enumerate(articles, 1):
        source = a['source']
        title = a['title'][:75]
        date = a['date']
        category = a['category']
        
        # Show relevance check result for non-auto-pass articles
        status = "✅ PASS"
        detail = ""
        
        # Check if this was auto-pass
        feed_entry = next((f for f in matching_feeds 
                          if f[0] == source), None)
        is_auto = feed_entry[3] if feed_entry else False
        
        if is_auto:
            detail = "(trusted source)"
        
        # Re-run relevance check matching actual fetch behavior
        rel = is_relevant(
            text=a.get('content', ''),
            source_label=source,
            title=a['title'],
            strict=False,
            category=category,
        )
        if rel:
            status = "✅ PASS"
        else:
            status = "❌ SKIP"
        
        print(f"  {i:>3}. [{status}] {title}")
        print(f"       Source: {source} | Category: {category} | Date: {date} {detail}")
        if i < len(articles):
            print()
    
    return articles


def main():
    import argparse
    parser = argparse.ArgumentParser(description="UPSC News Relevancy Audit")
    parser.add_argument("--days", type=int, default=1,
                       help="Number of days to fetch (default: 1)")
    parser.add_argument("--category", type=str, default=None,
                       help="Audit a specific category (e.g., 'Science & Technology')")
    args = parser.parse_args()
    
    days = args.days
    
    print(f"╔{'═'*68}╗")
    print(f"║{'UPSC NEWS RELEVANCY AUDIT':^68}║")
    print(f"║{'Checking what articles pass/fail from each category':^68}║")
    print(f"║{f'Window: {days} day(s)':^68}║")
    print(f"╚{'═'*68}╝")
    
    total_articles = {}
    
    if args.category:
        # Audit specific category
        if args.category in CATEGORY_GROUPS:
            arts = audit_category(
                args.category, 
                CATEGORY_GROUPS[args.category],
                days=days,
            )
            total_articles[args.category] = len(arts)
        else:
            print(f"\nUnknown category: {args.category}")
            print(f"Available: {', '.join(CATEGORY_GROUPS.keys())}")
            return
    else:
        # Audit all categories
        for cat_name, cat_values in CATEGORY_GROUPS.items():
            arts = audit_category(cat_name, cat_values, days=days)
            total_articles[cat_name] = len(arts)
    
    # Summary
    print(f"\n\n{'═'*70}")
    print(f"  📋 SUMMARY (last {days} day(s))")
    print(f"{'═'*70}")
    print(f"  {'Category':<35} {'Articles':>10}")
    print(f"  {'─'*45}")
    for cat, count in total_articles.items():
        bar = "█" * min(count, 30)
        print(f"  {cat:<35} {count:>10}  {bar}")
    total = sum(total_articles.values())
    print(f"  {'─'*45}")
    print(f"  {'TOTAL':<35} {total:>10}")


if __name__ == "__main__":
    main()
