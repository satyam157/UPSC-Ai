#!/usr/bin/env python3
"""Test web scraping functionality for Syllabus Resources"""

from syllabus_scraper import fetch_resource_content, combine_articles_for_summary, RESOURCE_URLS

print("=" * 80)
print("TESTING WEB SCRAPING FOR UPSC RESOURCES")
print("=" * 80)

resource_types = ["Yojana", "Kurukshetra", "Economic Survey", "Budget", "India Yearbook"]

for resource in resource_types[:1]:  # Test just Yojana first
    print(f"\n🔍 Testing {resource}...")
    print(f"Sources: {RESOURCE_URLS[resource]['primary_urls'][:1]}")
    
    articles, errors = fetch_resource_content(resource)
    
    if articles:
        print(f"✅ Successfully fetched {len(articles)} source(s)")
        for idx, article in enumerate(articles, 1):
            print(f"   Source {idx}: {article['url']}")
            print(f"   Content length: {len(article['content'])} chars")
            print(f"   Preview: {article['content'][:100]}...")
        
        # Test combining
        combined = combine_articles_for_summary(articles)
        print(f"\n✅ Combined content ({len(combined)} chars) ready for summarization")
    else:
        print(f"❌ Failed to fetch. Errors:")
        for error in errors:
            print(f"   - {error}")

print("\n" + "=" * 80)
print("Testing completed. If errors above, check:")
print("- Internet connection")
print("- Website accessibility (some sites may block scraping)")
print("- Try 'Fetch Latest from Internet' button in Streamlit app")
print("=" * 80)
