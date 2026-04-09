import feedparser

def scrape_pyq():
    urls = [
        "https://www.insightsonindia.com/category/prelims-2013/feed/"
    ]

    pyqs = []

    for url in urls:
        feed = feedparser.parse(url)

        for e in feed.entries[:10]:
            pyqs.append({
                "question": e.title,
                "topic": detect_topic(e.title)
            })

    return pyqs


def detect_topic(text):
    text = text.lower()
    if "economy" in text:
        return "Economy"
    elif "constitution" in text:
        return "Polity"
    else:
        return "General"


def analyze(news, pyqs):
    freq = {}
    matched = []

    for p in pyqs:
        freq[p["topic"]] = freq.get(p["topic"], 0) + 1

    for n in news:
        for p in pyqs:
            if p["topic"].lower() in n.lower():
                matched.append(p["question"])

    return freq, matched