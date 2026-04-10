import sys
import os
import requests
import feedparser
import time
from datetime import datetime, timedelta

# Add the current directory to sys.path
sys.path.append(os.path.abspath("e:/Software Center/UPSC-AI"))

from db import insert_news, trim_news_to_max
from filter import score_article
from scraper import enforce_news_limits

def historical_backfill(days=15):
    print(f"🚀 Starting historical backfill for {days} days...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    # Sources to target
    domains = ["thehindu.com", "indianexpress.com", "pib.gov.in", "livemint.com", "business-standard.com"]
    
    all_news = []
    
    for i in range(days):
        target_date = datetime.now() - timedelta(days=i)
        after_date = target_date.strftime("%Y-%m-%d")
        before_date = (target_date + timedelta(days=1)).strftime("%Y-%m-%d")
        
        print(f"📅 Fetching news for {after_date}...")
        
        for domain in domains:
            # Construct Google News RSS search URL
            query = f"site:{domain} UPSC after:{after_date} before:{before_date}"
            url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
            
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                feed = feedparser.parse(resp.content)
                
                count = 0
                for entry in feed.entries[:20]:  # Keep top 20 per domain per day
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    summary = entry.get("summary", entry.get("description", ""))
                    
                    if " - " in title:
                        title = title.rsplit(" - ", 1)[0].strip()
                    
                    # Scoring
                    score_res = score_article(title, text=summary)
                    if not score_res["passes"] and score_res["score"] < 2.5:
                        continue
                        
                    article = {
                        "title": title,
                        "url": link,
                        "source": f"Historical {domain.split('.')[0].capitalize()}",
                        "category": "Historical",
                        "summary": summary,
                        "date": after_date + " 12:00:00", # Set to noon for the day
                        "_score": score_res["score"]
                    }
                    all_news.append(article)
                    count += 1
                
                print(f"    ✅ {domain}: {count} articles")
                time.sleep(0.5) # Politeness
            except Exception as e:
                print(f"    ❌ Error {domain}: {e}")

    if not all_news:
        print("⚠️ No historical news found.")
        return

    print(f"📦 Total articles found: {len(all_news)}")
    
    # Enforce limits per day
    print("⚖️ Enforcing per-day limits...")
    capped_news = enforce_news_limits(all_news)
    
    # Insert into DB
    print(f"📥 Inserting {len(capped_news)} articles into the database...")
    inserted = insert_news(capped_news)
    print(f"✅ Successfully inserted {inserted} new articles.")
    
    # Final trim
    trim_news_to_max(35)
    print("✨ Historical backfill completed!")

if __name__ == "__main__":
    historical_backfill(15)
