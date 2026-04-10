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
from datetime import datetime, timedelta
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


# Priority order for Regular News (All News tab)
# User Requested: Hindu > IE > Livemint > Wire > Print > BS > DTE
NEWS_PRIORITY_MAP = {
    "the hindu": 1,
    "indian express": 2,
    "livemint": 3,
    "the wire": 4,
    "the print": 5,
    "business standard": 6,
    "down to earth": 7,
    "pib": 8,
}

def get_source_rank(source_label):
    """Used for sorting regular news in the 'All News' tab and for trimming."""
    sl = str(source_label or "").lower()
    for key, rank in NEWS_PRIORITY_MAP.items():
        if key in sl:
            return rank
    return 100 # Default for unknown sources

def get_editorial_rank(source_label):
    """
    UI Priority for Editorials (UPSC focus): 
    1. The Hindu Editorial & IE Explained (Rank 1)
    2. Other Whitelisted Editorials (BS, Livemint) (Rank 2)
    3. The Hindu Opinion (Rank 3)
    4. The Hindu Lead / Op-Ed (Rank 4)
    5. Others (Rank 5)
    """
    sl = str(source_label or "").lower()
    
    # Rank 1: Top Tier Editorials
    if "the hindu editorial" in sl or "ie explained" in sl or "indian express explained" in sl:
        return 1
        
    # Rank 2: Other High-Quality Editorials
    if "editorial" in sl:
        return 2
        
    # Rank 3: High-Quality Opinion
    if "the hindu" in sl and "opinion" in sl:
        return 3
        
    # Rank 4: Lead / Op-Ed
    if "lead" in sl or "op-ed" in sl:
        return 4
        
    # Rank 5: General Analytical
    if "opinion" in sl or "explained" in sl:
        return 5
        
    return 6

# ─── DEDUPLICATION HELPERS ────────────────────────────────────────────────────

# Sources whose content has editorial/analytical value worth keeping even when
# a similar headline already exists from a plain-news source.
EDITORIAL_ANALYSIS_SOURCES = {
    "the hindu editorial", "the hindu opinion", "the hindu lead", "the hindu op-ed",
    "ie explained", "indian express opinion",
    "livemint editorial", "bs editorial",
    "the wire", "the print", "down to earth", "pib",
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

    # Editorial/Explained pieces have a more lenient dynamic threshold
    # to ensure quality without being too aggressive.
    editorial_cats = {"Editorial", "Explained", "Opinion", "Lead", "Op-Ed"}
    always_pass    = [n for n in news_list if n.get("category") in editorial_cats]
    scored_rest    = [n for n in news_list if n.get("category") not in editorial_cats]

    if not scored_rest:
        # Still apply a minimal threshold to editorials if they are being filtered
        return [n for n in always_pass if n.get("_score", 0) >= 2]

    top_score = max((n["_score"] for n in scored_rest), default=0)
    threshold  = max(3, int(top_score * 0.30))

    kept = [n for n in scored_rest if n["_score"] >= threshold]
    
    # Filter editorials more strictly than before (at least score 2)
    kept_editorials = [n for n in always_pass if n.get("_score", 0) >= 2]

    # Sort by score descending within each group
    kept.sort(key=lambda x: x["_score"], reverse=True)
    kept_editorials.sort(key=lambda x: (get_editorial_rank(x.get("source")), -x.get("_score", 0)))

    return kept_editorials + kept


def enforce_news_limits(news_list: List[Dict]) -> List[Dict]:
    """
    Enforce the 30-40 news limit policy:

    PRIORITY ORDER:
      1. Editorials/Explained/Opinion — ALWAYS included, no cap.
         These are critical for UPSC Mains answer writing.
      2. PIB — Important governance content, included after editorials.
      3. Regular news — Capped to fill remaining slots.

    LIMITS:
      - Target: 30 non-editorial news items.
      - Extension: Up to 50 if remaining articles are highly relevant
        (score >= 70th percentile of kept articles).
      - Editorials: Capped at 25.
      - Explained: Target 15, Max 20.

    Also removes duplicate-looking articles within the final list.
    """
    if not news_list:
        return []

    # ── Separate editorials from regular news/PIB ────────────────────────
    editorial_cats = {"editorial", "explained", "opinion", "lead", "op-ed"}
    editorial_sources = EDITORIAL_ANALYSIS_SOURCES

    # ── Group by Date ───────────────────────────────────────────────────
    news_by_day = {}
    for n in news_list:
        d = n.get("date", "Unknown").split(" ")[0]
        if d not in news_by_day:
            news_by_day[d] = []
        news_by_day[d].append(n)

    final_capped_news = []
    
    for d, day_list in news_by_day.items():
        # Separate into 4 buckets: Editorials (25), Explained (15/20), PIB (10/15), Regular (30/40)
        day_editorials = []
        day_explained = []
        day_pib = []
        day_regular = []
        
        for n in day_list:
            cat = str(n.get("category", "")).lower()
            src = str(n.get("source", "")).lower()
            
            if cat == "explained" or "explained" in src:
                day_explained.append(n)
            elif cat in {"editorial", "opinion", "lead", "op-ed"} or src in EDITORIAL_ANALYSIS_SOURCES:
                day_editorials.append(n)
            elif "pib" in src or "pib" in cat:
                day_pib.append(n)
            else:
                day_regular.append(n)
        
        # Helper for capping a bucket
        def cap_bucket(bucket, target, maximum):
            if len(bucket) <= target:
                return bucket
            
            # Primary: Source Rank (Lower is better)
            # Secondary: Score (Higher is better)
            bucket.sort(key=lambda x: (get_source_rank(x.get("source")), -x.get("_score", 0)))
            
            capped = bucket[:target]
            # Extension check
            kept_scores = [n.get("_score", 0) for n in capped if n.get("_score", 0) > 0]
            if kept_scores:
                kept_scores.sort()
                bar = kept_scores[int(len(kept_scores) * 0.70)] if len(kept_scores) > 0 else 5
            else: bar = 5
            
            for n in bucket[target:]:
                if len(capped) >= maximum: break
                if n.get("_score", 0) >= bar:
                    capped.append(n)
            return capped

        # Apply specific limits (Target 30, Max 50 for regular news)
        day_pib_capped = cap_bucket(day_pib, 10, 15)
        day_regular_capped = cap_bucket(day_regular, 30, 50)
        day_explained_capped = cap_bucket(day_explained, 15, 20)
        
        # Sort and cap Editorials (Target 25)
        day_editorials.sort(key=lambda x: (get_editorial_rank(x.get("source")), -x.get("_score", 0)))
        day_editorials_capped = day_editorials[:25]
        
        final_capped_news.extend(day_editorials_capped + day_explained_capped + day_pib_capped + day_regular_capped)

    # ── Final dedup pass on combined list ────────────────────────────────
    final = remove_similar_news(final_capped_news)
    
    # Global final sort by date DESC, then source rank ASC, then score DESC
    final.sort(key=lambda x: (x.get("date", ""), -get_source_rank(x.get("source")), x.get("_score", 0)))
    final.reverse() # Newest date, then best rank, then best score

    print(f"  [Limits]   Per-day enforcement completed. Total kept: {len(final)}")
    return final


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
            "If KEEP: YES, add a one-sentence UPSC-focused summary (max 25 words).\n"
            "**CRITICAL RULE:** DO NOT repeat the same summary or phrase for different articles.\n\n"
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

def fetch_full_news_content(url: str, timeout: int = 8) -> tuple[bool, str]:
    """
    Fetch the full article content from a given URL.
    Returns (success_boolean, extracted_text).
    """
    try:
        from bs4 import BeautifulSoup
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=timeout, verify=False)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "meta"]):
            tag.decompose()
            
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        
        if len(text) < 100:
            return False, "Content too short or blocked"
            
        return True, text[:5000]
    except Exception as e:
        return False, f"Failed to fetch content: {str(e)}"


# ─── MAIN FETCH FUNCTION ──────────────────────────────────────────────────────

def fetch_news(max_per_feed: int = 30, days: int = 1, target_date=None) -> List[Dict]:
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
    7. **Enforce 30-40 news limit** (editorials exempt, always included).

    LIMITS POLICY:
      - Editorials/Explained/Opinion: NO LIMIT — always included in full.
      - News + PIB: Target 30, max 40 (only if highly relevant).
      - Duplicate-looking articles removed at multiple stages.

    Parameters
    ----------
    max_per_feed : Maximum articles per RSS feed.
    days         : Days of news to fetch (default 1; set higher for catch-up).
    target_date  : Optional datetime.date — fetch news for this specific date.
                   When provided, overrides `days` and generates Google News
                   search feeds scoped to the target date.

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

    custom_feeds = None

    # ── Step 0a: Specific-date mode ──────────────────────────────────────────
    if target_date is not None:
        # target_date is a datetime.date object
        date_str = target_date.strftime("%Y-%m-%d")
        end_date_str = (target_date + timedelta(days=1)).strftime("%Y-%m-%d")
        days_ago = (datetime.now().date() - target_date).days
        effective_days = max(days_ago + 1, 2)

        print(f"📅 Specific-date mode: Fetching news for {date_str} ({days_ago} day(s) ago)")

        try:
            from news_fetcher_Advanced import RSS_FEEDS as BASE_FEEDS
            custom_feeds = list(BASE_FEEDS)

            # Key high-value domains for UPSC
            domains = [
                "thehindu.com", "indianexpress.com", "pib.gov.in",
                "livemint.com", "thewire.in", "theprint.in",
                "downtoearth.org.in", "business-standard.com",
            ]

            # Generate date-scoped Google News search feeds for each domain
            for domain in domains:
                query = f"site:{domain} after:{date_str} before:{end_date_str}"
                search_url = (
                    f"https://news.google.com/rss/search?q={query}"
                    f"&hl=en-IN&gl=IN&ceid=IN:en"
                )
                custom_feeds.append((
                    f"Search {domain.split('.')[0].capitalize()}",
                    search_url,
                    "Historical",
                    False,
                ))

            # Also add UPSC-specific keyword searches for the target date
            upsc_queries = [
                "UPSC+OR+policy+OR+government+OR+parliament",
                "Supreme+Court+OR+RBI+OR+budget+OR+economy",
                "ISRO+OR+defence+OR+environment+OR+climate",
            ]
            for uq in upsc_queries:
                search_url = (
                    f"https://news.google.com/rss/search?q={uq}"
                    f"+after:{date_str}+before:{end_date_str}"
                    f"&hl=en-IN&gl=IN&ceid=IN:en"
                )
                custom_feeds.append((
                    "UPSC Search",
                    search_url,
                    "Historical",
                    False,
                ))
        except Exception as e:
            print(f"[WARN] Failed to build date-specific feeds: {e}")

        # Override days to cover the target date in the cutoff logic
        days = effective_days

    # ── Step 0b: Deep Historical mode (days > 2, no specific date) ───────────
    elif days > 2:
        print(f"🕵️ Deep Historical mode active ({days} days). Generating targeted search for older dates...")
        try:
            from news_fetcher_Advanced import RSS_FEEDS as BASE_FEEDS
            custom_feeds = list(BASE_FEEDS)
            
            # Key high-value domains for UPSC
            domains = ["thehindu.com", "indianexpress.com", "pib.gov.in"]
            
            # ONLY generate search feeds for dates older than what standard RSS covers (usually ~2 days)
            for d_offset in range(2, days):
                hist_date = datetime.now() - timedelta(days=d_offset)
                date_str = hist_date.strftime("%Y-%m-%d")
                end_date_str = (hist_date + timedelta(days=1)).strftime("%Y-%m-%d")
                
                for domain in domains:
                    query = f"site:{domain} UPSC after:{date_str} before:{end_date_str}"
                    search_url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
                    custom_feeds.append((f"Search {domain.split('.')[0].capitalize()}", search_url, "Historical", False))
        except Exception as e:
            print(f"[WARN] Failed to inject historical feeds: {e}")

    # ── Step 1: RSS fetch + initial filter ───────────────────────────────────
    articles = fetch_all_news(
        feeds=custom_feeds,
        max_per_feed=max_per_feed,
        verbose=False,
        days=days,
        max_total=500 if days > 1 else 150 # Higher total to accommodate exempt items (PIB, Editorial, etc.)
    )
    print(f"  [Fetcher]  {len(articles)} articles after RSS filter")

    if not articles:
        return []

    # ── Step 1b: If target_date given, filter strictly to that date ───────────
    if target_date is not None:
        target_str = target_date.strftime("%Y-%m-%d")
        before_filter = len(articles)
        articles = [a for a in articles if a.get("date", "").startswith(target_str)]
        print(f"  [DateFilter] {len(articles)} of {before_filter} articles match {target_str}")

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

    # ── Step 7: Enforce 30-40 news limit (editorials exempt) ─────────────────
    articles = enforce_news_limits(articles)
    print(f"  [Enforced] {len(articles)} articles after 30-40 limit enforcement")

    # ── Step 8: Normalize date to YYYY-MM-DD for DB storage ──────────────────
    for a in articles:
        date_str = a.get("date", "")
        if " " in date_str:
            a["date"] = date_str.split(" ")[0]

    # Reverse to oldest-first so INSERT order matches chronological IDs
    articles.reverse()

    print(f"  [Final]    {len(articles)} articles ready for DB")
    return articles