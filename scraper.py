import feedparser
from datetime import datetime
from filter import is_relevant

DAYS_TO_KEEP = 7  # 🔥 configurable

def fetch_news():
    urls = [
        "https://pib.gov.in/RssMain.aspx",
        "https://www.thehindu.com/news/national/feeder/default.rss",
        "https://indianexpress.com/section/india/feed/",
        "https://indianexpress.com/section/explained/feed/"

    ]

    news = []
    today = datetime.now().strftime("%Y-%m-%d")

    for url in urls:
        feed = feedparser.parse(url)

        for e in feed.entries[:15]:
            title = e.title

            if is_relevant(title):
                news.append({
                    "title": title,
                    "content": e.summary,
                    "date": today
                })

    return news