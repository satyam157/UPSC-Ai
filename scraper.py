# ─────────────────────────────────────────────────────────────
# SMART UPSC NEWS FILTER SYSTEM
# scraper.py  —  Pipeline orchestration layer
#
# Responsibilities:
#   1. Thin wrapper over news_fetcher_Advanced.fetch_all_news
#   2. Similarity-based deduplication (cross-source)
#   3. Optional LLM-based second-pass filter + summary injection
#   4. Dynamic score-based threshold (keeps top-tier articles)
#
# v5.0 Changes:
#   - score_article() now delegates to filter.score_article() for
#     consistent, deep scoring instead of a 7-keyword approximation.
#   - AI filter prompt is context-richer with explicit UPSC topic map.
#   - dynamic_threshold_filter applies AFTER AI pass so noise already
#     dropped by LLM doesn't inflate the threshold.
#   - remove_similar_news applied both before and after AI filter.
#   - Editorial sources preserved even when similar headline exists
#     from a regular news article.
# ─────────────────────────────────────────────────────────────

import difflib
import re
import requests
import feedparser
from datetime import datetime
from typing import List, Dict

# ─── Internal imports ────────────────────────────────────────
try:
    from filter import (
        is_relevant as filter_is_relevant,
        score_article as filter_score_article,
        normalize_title,
    )
    _HAS_FILTER = True
except ImportError:
    _HAS_FILTER = False
    filter_is_relevant  = lambda text, **kw: True
    filter_score_article = lambda title, **kw: {"passes": True, "score": 0.0, "threshold": 0.0, "reason": "filter unavailable"}
    normalize_title      = lambda t: t.lower().strip()

# ─── CONSTANTS ────────────────────────────────────────────────────────────────
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )
}

# ─── RSS FEED REGISTRY (kept for backward compatibility) ─────────────────────
# The canonical registry lives in news_fetcher_Advanced.py (RSS_FEEDS).
# This list is used only if someone calls scraper.py functions directly.
RSS_FEEDS = [
    # ── THE HINDU (Priority #1) ──────────────────────────────────────────────
    ("The Hindu Editorial",  "https://www.thehindu.com/opinion/editorial/?service=rss",              "Editorial",          True),
    ("The Hindu Lead",       "https://www.thehindu.com/opinion/lead/?service=rss",                   "Lead",               True),
    ("The Hindu Op-Ed",      "https://www.thehindu.com/opinion/op-ed/?service=rss",                  "Op-Ed",              True),
    ("The Hindu Opinion",    "https://www.thehindu.com/opinion/?service=rss",                         "Opinion",            True),
    ("The Hindu National",   "https://www.thehindu.com/news/national/?service=rss",                  "National",           False),
    ("The Hindu International", "https://www.thehindu.com/news/international/?service=rss",          "International",      False),
    ("The Hindu Economy",    "https://www.thehindu.com/business/?service=rss",                       "Economy",            False),
    ("The Hindu S&T",        "https://www.thehindu.com/sci-tech/?service=rss",                       "Science & Technology", False),
    ("The Hindu Environment","https://www.thehindu.com/sci-tech/energy-and-environment/?service=rss","Environment",        False),

    # ── INDIAN EXPRESS (Priority #2) ─────────────────────────────────────────
    ("IE Explained",         "https://indianexpress.com/section/explained/feed/",          "Explained",          True),
    ("IE Opinion",           "https://indianexpress.com/section/opinion/feed/",            "Opinion",            True),
    ("Indian Express",       "https://indianexpress.com/section/india/feed/",              "National",           False),
    ("Indian Express S&T",   "https://indianexpress.com/section/technology/feed/",         "Science & Technology", False),
    ("Indian Express World", "https://indianexpress.com/section/world/feed/",              "International",      False),
    ("Indian Express Economy","https://indianexpress.com/section/business/feed/",          "Economy",            False),
    ("Indian Express Polity","https://indianexpress.com/section/political-pulse/feed/",   "Polity",             False),

    # ── PIB (Priority #3 — Official Gov) ─────────────────────────────────────
    ("PIB",               "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",                                        "Governance", True),
    ("PIB English",       "https://news.google.com/rss/search?q=site:pib.gov.in+when:3d&hl=en-IN&gl=IN&ceid=IN:en",        "Governance", True),
    ("PIB Press Releases","https://news.google.com/rss/search?q=site:pib.gov.in+press+release+when:3d&hl=en-IN&gl=IN&ceid=IN:en","Governance",True),

    # ── OTHER SOURCES ────────────────────────────────────────────────────────
    ("Down to Earth",     "https://news.google.com/rss/search?q=site:downtoearth.org.in+when:3d&hl=en-IN&gl=IN&ceid=IN:en","Environment",True),
    ("The Print",         "https://news.google.com/rss/search?q=site:theprint.in+when:2d&hl=en-IN&gl=IN&ceid=IN:en",       "Analysis",   False),
    ("The Wire",          "https://news.google.com/rss/search?q=site:thewire.in+when:2d&hl=en-IN&gl=IN&ceid=IN:en",        "Analysis",   False),
    ("Livemint Editorial","https://www.livemint.com/rss/opinion",                                                            "Editorial",  True),
    ("Livemint News",     "https://www.livemint.com/rss/news",                                                               "Economy",    False),
    ("Business Standard", "https://news.google.com/rss/search?q=site:business-standard.com+when:2d&hl=en-IN&gl=IN&ceid=IN:en","Economy", False),
]


# ─── DEDUPLICATION HELPERS ────────────────────────────────────────────────────

# Sources whose content has editorial/analytical value worth keeping even when
# a similar headline already exists from a plain-news source.
EDITORIAL_ANALYSIS_SOURCES = {
    "the hindu editorial", "the hindu opinion", "the hindu lead",
    "ie explained", "indian express opinion",
    "bs editorial", "livemint editorial",
    "down to earth",
}

def _normalize_for_dedup(title: str) -> str:
    """Lowercase, strip LIVE:/BREAKING: prefix, remove punctuation for similarity checks."""
    t = normalize_title(title)          # strips LIVE:, BREAKING:, JUST IN:
    t = re.sub(r"[^a-z0-9 ]", "", t)   # remove punctuation
    t = re.sub(r"\s+", " ", t).strip()
    return t

def is_similar(a: str, b: str, threshold: float = 0.76) -> bool:
    """True if two normalized titles are ≥ threshold similar."""
    return difflib.SequenceMatcher(None, a, b).ratio() >= threshold

def remove_similar_news(news_list: List[Dict]) -> List[Dict]:
    """
    Remove duplicate/similar news across sources.

    Rules:
    - Editorial/analysis articles are preserved even if a similar regular news
      article exists — they provide deeper UPSC analysis value.
    - Regular news duplicates are removed (first-seen wins).
    - Similarity threshold: 76% (SequenceMatcher ratio).
    """
    unique_news: List[Dict] = []
    seen: List[tuple] = []   # (normalized_title, source_type)

    for article in news_list:
        title  = article.get("title", "")
        source = article.get("source", "").lower()
        norm   = _normalize_for_dedup(title)
        is_editorial = source in EDITORIAL_ANALYSIS_SOURCES

        is_dup = False
        for seen_norm, seen_is_editorial in seen:
            if is_similar(norm, seen_norm):
                # Keep editorials even when a similar regular article was seen first
                if is_editorial and not seen_is_editorial:
                    continue   # Not treated as dup — editorial adds value
                is_dup = True
                break

        if not is_dup:
            unique_news.append(article)
            seen.append((norm, is_editorial))

    return unique_news


# ─── SCORING ──────────────────────────────────────────────────────────────────

def score_article(text: str, category: str, source: str, title: str = "") -> int:
    """
    Compute an article's relevance score using the filter module's deep scoring.

    Delegates to `filter.score_article()` which uses the full keyword bank,
    source-trust tiers, and soft-blacklist penalties.

    Returns an integer score for backward compat with dynamic_threshold_filter.
    """
    if not _HAS_FILTER:
        # Minimal fallback
        keywords = ["government", "india", "policy", "court", "rbi", "budget",
                    "economy", "environment", "climate", "defence", "space"]
        return sum(1 for kw in keywords if kw in (text + " " + title).lower())

    result = filter_score_article(
        title=title or text[:120],
        text=text,
        source_label=source,
        category=category,
    )
    # Clamp to int; multiply by 2 so top-scoring articles get scores in range
    # similar to old system (old max ~10–12, new float range ~2–20)
    raw = result.get("score", 0.0)
    return max(0, int(raw))


def dynamic_threshold_filter(news_list: List[Dict]) -> List[Dict]:
    """
    Keep only articles that score above a dynamic threshold.

    Threshold = max(3, top_score * 0.30)
    Editorial/Explained articles bypass the filter — they are pre-curated.
    """
    if not news_list:
        return []

    # Score each article
    for n in news_list:
        n["_score"] = score_article(
            text=n.get("content", ""),
            category=n.get("category", ""),
            source=n.get("source", ""),
            title=n.get("title", ""),
        )

    # Editorial feeds always pass
    editorial_cats = {"Editorial", "Explained", "Opinion", "Lead", "Op-Ed"}
    always_pass    = [n for n in news_list if n.get("category") in editorial_cats]
    scored_rest    = [n for n in news_list if n.get("category") not in editorial_cats]

    if not scored_rest:
        return always_pass

    top_score = max((n["_score"] for n in scored_rest), default=0)
    threshold  = max(3, int(top_score * 0.30))

    kept = [n for n in scored_rest if n["_score"] >= threshold]

    # Sort by score descending within each group
    kept.sort(key=lambda x: x["_score"], reverse=True)
    always_pass.sort(key=lambda x: x.get("date", ""), reverse=True)

    return always_pass + kept


def ensure_diversity(news_list: List[Dict]) -> List[Dict]:
    """
    Ensure category diversity: surface at least one article per category,
    then append the rest in score order.
    """
    seen_categories: set = set()
    first_of_cat:    List[Dict] = []
    rest:            List[Dict] = []

    for n in news_list:
        cat = n.get("category", "General")
        if cat not in seen_categories:
            first_of_cat.append(n)
            seen_categories.add(cat)
        else:
            rest.append(n)

    return first_of_cat + rest


# ─── UPSC TOPIC MAP (for AI prompt context) ───────────────────────────────────
_UPSC_TOPIC_MAP = """
UPSC-relevant topics (keep these):
  Polity: Constitution, Supreme Court, Parliament, elections, federalism, RTI, lokpal
  Economy: RBI, GDP, inflation, GST, budget, FDI, FPI, MSP, IBC, SEBI, MSME
  IR/World: India-China, India-US, India-Pak, SCO, BRICS, G20, QUAD, AUKUS, UN, WTO
  Environment: climate change, COP, net-zero, biodiversity, IUCN, wildlife, pollution
  Science & Technology: ISRO, NISAR, Chandrayaan, AI policy, semiconductor, 5G
  Defence: Operation Sindoor, surgical strike, DRDO, missile, submarine, LOC
  Social: caste census, reservation, tribal rights, NEET, NEP, gender equality
  Governance: PIB schemes, welfare missions, digital India, e-governance

NOT UPSC-relevant (reject these):
  Sports scores, IPL, cricket updates, celebrity gossip, fashion, astrology,
  local crime (non-policy), royal family news, viral videos, gadget reviews,
  quarterly earnings unrelated to policy, app updates, IPO grey market.
"""


# ─── AI SECOND-PASS FILTER ────────────────────────────────────────────────────

def apply_ai_filter_and_summary(articles: List[Dict]) -> List[Dict]:
    """
    LLM-based second-pass: strict UPSC relevance filter + crisp summary injection.

    - Processes in batches of 15.
    - Articles kept get a one-sentence UPSC-focused summary prepended to content.
    - If LLM is unavailable, returns articles unchanged (fail-safe).
    """
    if not articles:
        return []

    try:
        from llm import ask_llm
    except ImportError:
        print("[WARN] llm.py not found — skipping AI filter pass.")
        return articles

    kept_articles: List[Dict] = []
    batch_size = 15

    for i in range(0, len(articles), batch_size):
        batch = articles[i : i + batch_size]

        prompt = (
            "You are a strict UPSC Civil Services Exam News Curator.\n"
            f"{_UPSC_TOPIC_MAP}\n"
            "For each article below, decide:\n"
            "  KEEP: YES  — if it is genuinely relevant to the topic map above.\n"
            "  KEEP: NO   — if it is noise, repetitive, purely ceremonial, or low-ROI.\n"
            "If KEEP: YES, add a one-sentence UPSC-focused summary (max 25 words).\n\n"
            "Reply STRICTLY in this format for every article (no extra text):\n"
            "UID: <uid>\n"
            "KEEP: <YES or NO>\n"
            "CATEGORY: <one of: Polity|Economy|IR|Environment|S&T|Defence|Social|Governance|Other>\n"
            "SUMMARY: <summary or N/A>\n"
            "---\n\n"
            "ARTICLES:\n"
        )

        for a in batch:
            safe_title   = str(a.get("title",   "")).replace("\n", " ")[:150]
            safe_content = str(a.get("content", "")).replace("\n", " ")[:300]
            safe_source  = str(a.get("source",  ""))[:40]
            prompt += (
                f"UID: {a['uid']}\n"
                f"TITLE: {safe_title}\n"
                f"CONTENT: {safe_content}\n"
                f"SOURCE: {safe_source}\n"
                f"CATEGORY: {a.get('category','')}\n---\n"
            )

        batch_num = i // batch_size + 1
        total_batches = (len(articles) + batch_size - 1) // batch_size
        print(f"  [AI Filter] Batch {batch_num}/{total_batches} "
              f"({len(batch)} articles)...")

        try:
            resp    = ask_llm(prompt)
            uid_map = {a["uid"]: a for a in batch}
            blocks  = resp.split("UID:")[1:]

            for block in blocks:
                lines = [ln.strip() for ln in block.strip().split("\n") if ln.strip()]
                if not lines:
                    continue
                uid = lines[0].strip()
                if uid not in uid_map:
                    continue

                keep_line = next((l for l in lines if l.startswith("KEEP:")),    "KEEP: NO")
                cat_line  = next((l for l in lines if l.startswith("CATEGORY:")), "")
                sum_line  = next((l for l in lines if l.startswith("SUMMARY:")), "SUMMARY: ")

                keep    = "YES" in keep_line.upper()
                summary = sum_line.replace("SUMMARY:", "").strip()
                ai_cat  = cat_line.replace("CATEGORY:", "").strip()

                art = uid_map[uid]
                if keep:
                    # Inject AI summary and override category if AI gave a tighter one
                    if summary and summary.upper() != "N/A":
                        art["content"] = (
                            f"🤖 {summary}\n\n"
                            f"{art.get('content', '')}"
                        )
                    if ai_cat and ai_cat != "Other":
                        art["ai_category"] = ai_cat
                    kept_articles.append(art)
                else:
                    print(f"    ↳ [AI DROP] {art['title'][:70]}")

        except Exception as e:
            print(f"  [AI Filter] Batch {batch_num} failed: {e} — keeping all.")
            kept_articles.extend(batch)   # fail-safe: keep all if LLM errors

    return kept_articles


# ─── PUBLIC HELPERS (used by app.py & filter_reviewer.py) ────────────────────

def is_upsc_relevant_topic(title: str) -> bool:
    """Interface required by app.py and tests."""
    return filter_is_relevant(title, title=title)

def is_relevant(text: str, source_label: str = "", title: str = "",
                strict: bool = False, category: str = "") -> bool:
    """Wrapper for internal scraper use."""
    return filter_is_relevant(
        text, source_label=source_label, title=title,
        strict=strict, category=category,
    )


# ─── MAIN FETCH FUNCTION ──────────────────────────────────────────────────────

def fetch_news(max_per_feed: int = 30, days: int = 1) -> List[Dict]:
    """
    Intelligent UPSC News Fetcher — full pipeline:

    1. Fetch from all RSS feeds via news_fetcher_Advanced.fetch_all_news()
       (includes URL-hash dedup + normalized-title dedup + relevance scoring).
    2. Similarity dedup across sources (remove_similar_news).
    3. LLM second-pass filter + summary injection (apply_ai_filter_and_summary).
    4. Post-AI similarity dedup (catches near-duplicates that were in different
       LLM batches).
    5. Dynamic score-based threshold (dynamic_threshold_filter).
    6. Category diversity pass (ensure_diversity).

    Parameters
    ----------
    max_per_feed : Maximum articles per RSS feed.
    days         : Days of news to fetch (default 1; set higher for catch-up).

    Returns
    -------
    List of article dicts, each with keys:
        title, url, content, source, category, date, uid
    Sorted oldest-first (for correct DB insertion order).
    """
    try:
        from news_fetcher_Advanced import fetch_all_news
    except ImportError as e:
        print(f"[ERROR] news_fetcher_Advanced import failed: {e}")
        return []

    # ── Step 1: RSS fetch + initial filter ───────────────────────────────────
    articles = fetch_all_news(
        max_per_feed=max_per_feed,
        verbose=False,
        days=days,
    )
    print(f"  [Fetcher]  {len(articles)} articles after RSS filter")

    if not articles:
        return []

    # ── Step 2: Cross-source similarity dedup ─────────────────────────────────
    articles = remove_similar_news(articles)
    print(f"  [Dedup 1]  {len(articles)} articles after similarity dedup")

    # ── Step 3: LLM second-pass filter ───────────────────────────────────────
    articles = apply_ai_filter_and_summary(articles)
    print(f"  [AI Pass]  {len(articles)} articles after AI filter")

    # ── Step 4: Post-AI similarity dedup ─────────────────────────────────────
    articles = remove_similar_news(articles)
    print(f"  [Dedup 2]  {len(articles)} articles after post-AI dedup")

    # ── Step 5: Dynamic score threshold ──────────────────────────────────────
    articles = dynamic_threshold_filter(articles)
    print(f"  [Threshold] {len(articles)} articles after score threshold")

    # ── Step 6: Category diversity ────────────────────────────────────────────
    articles = ensure_diversity(articles)

    # ── Step 7: Normalize date to YYYY-MM-DD for DB storage ──────────────────
    for a in articles:
        date_str = a.get("date", "")
        if " " in date_str:
            a["date"] = date_str.split(" ")[0]

    # Reverse to oldest-first so INSERT order matches chronological IDs
    articles.reverse()

    print(f"  [Final]    {len(articles)} articles ready for DB")
    return articles