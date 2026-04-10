
from news_fetcher_Advanced import fetch_all_news

# Test specifically for PIB Economy
test_feeds = [
    ("pib", "https://pib.gov.in/RssMain.aspx?ModId=3&Lang=1&Regid=3", "PIB — Economy", False),
]

print("Fetching PIB Economy...")
articles = fetch_all_news(feeds=test_feeds, max_per_feed=10, verbose=True)

for a in articles:
    print(f"- {a['title']}")
if not articles:
    print("No articles passed the strict PIB filter.")
