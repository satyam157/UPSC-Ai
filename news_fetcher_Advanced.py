"""
UPSC News Fetcher  —  news_fetcher_Advanced.py
===============================================
Fetches from RSS feeds of:
  • The Hindu         — Editorial, Opinion, National, International, Economy, S&T
  • Indian Express    — Explained, Opinion, India, World, Economy
  • PIB               — All ministries
  • Business Standard — Economy, Policy
  • Down to Earth     — Environment
  • The Wire          — Politics, Economy, Science (Google News RSS)
  • Livemint          — Economy, Opinion

Key design:
  • Every article carries its source label from the feed, so the filter
    always knows whether it is an editorial / explained piece.
  • Hindu editorials and IE Explained pieces auto-pass the relevance check
    (they are pre-curated); all other feeds go through keyword scoring.
  • Dual deduplication:
      - URL-hash dedup (primary): catches same story from same feed.
      - Normalized-title dedup (secondary): catches LIVE:/BREAKING: variants
        and cross-feed duplicates with identical normalized title.

v5.0 Changes:
  - FIXED: normalized-title dedup was declared but never applied — now enforced
    BEFORE the relevance gate so LIVE:/BREAKING: re-publishes are caught early.
  - Added The Wire & Mint Economy feeds.
  - Google News redirect URL resolver (strips the /rss/articles/... wrapper).
  - Content snippet now stores up to 600 chars (was 400) for better AI context.

Requirements (pip install):
    feedparser          — RSS parsing
    requests            — HTTP fallback for feeds that block feedparser UA

Usage:
    from news_fetcher_Advanced import fetch_all_news
    articles = fetch_all_news()          # returns list of dicts
    for a in articles:
        print(a['source'], '|', a['title'])
"""

import hashlib
import time
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False
    print("[WARN] feedparser not installed. Run: pip install feedparser")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1  —  RSS FEED REGISTRY
# Each entry:  (label, rss_url, category, auto_pass)
#   label     : source label passed to is_relevant()
#   rss_url   : the actual RSS / Atom feed URL
#   category  : human-readable category tag stored on each article
#   auto_pass : if True, ALL articles from this feed skip keyword scoring
#               (used for Hindu Editorial and IE Explained)
# ─────────────────────────────────────────────────────────────────────────────

RSS_FEEDS = [

    # ══════════════════════════════════════════════════════════════════════════
    # THE HINDU  —  https://www.thehindu.com/rss/
    # ══════════════════════════════════════════════════════════════════════════

    # Editorial — auto_pass=True: every piece is already curated
    (
        "the hindu editorial",
        "https://www.thehindu.com/opinion/editorial/?service=rss",
        "Editorial",
        True,
    ),
    # Op-Ed / Lead (long-form opinion) — auto_pass=True
    (
        "the hindu opinion",
        "https://www.thehindu.com/opinion/op-ed/?service=rss",
        "Opinion",
        True,
    ),
    (
        "the hindu opinion",
        "https://www.thehindu.com/opinion/lead/?service=rss",
        "Opinion",
        True,
    ),
    # News sections — auto_pass=False: filter normally
    (
        "the hindu",
        "https://www.thehindu.com/news/national/?service=rss",
        "National",
        False,
    ),
    (
        "the hindu",
        "https://www.thehindu.com/news/international/?service=rss",
        "International",
        False,
    ),
    (
        "the hindu",
        "https://www.thehindu.com/business/?service=rss",
        "Economy",
        False,
    ),
    (
        "the hindu",
        "https://www.thehindu.com/sci-tech/?service=rss",
        "Science & Technology",
        False,
    ),
    (
        "the hindu",
        "https://www.thehindu.com/sci-tech/energy-and-environment/?service=rss",
        "Environment",
        False,
    ),
    # Full opinion section (catches columns, interviews, etc.)
    (
        "the hindu opinion",
        "https://www.thehindu.com/opinion/?service=rss",
        "Opinion",
        True,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # INDIAN EXPRESS  —  https://indianexpress.com/rss-feeds/
    # ══════════════════════════════════════════════════════════════════════════

    # Explained — auto_pass=True
    (
        "ie explained",
        "https://indianexpress.com/section/explained/feed/",
        "Explained",
        True,
    ),
    # Opinion — auto_pass=True
    (
        "indian express opinion",
        "https://indianexpress.com/section/opinion/feed/",
        "Opinion",
        True,
    ),
    # News sections
    (
        "indian express",
        "https://indianexpress.com/section/india/feed/",
        "National",
        False,
    ),
    (
        "indian express",
        "https://indianexpress.com/section/world/feed/",
        "International",
        False,
    ),
    (
        "indian express",
        "https://indianexpress.com/section/business/feed/",
        "Economy",
        False,
    ),
    (
        "indian express",
        "https://indianexpress.com/section/technology/feed/",
        "Science & Technology",
        False,
    ),
    (
        "indian express",
        "https://indianexpress.com/section/political-pulse/feed/",
        "Polity",
        False,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # PIB  (Press Information Bureau)
    # ══════════════════════════════════════════════════════════════════════════
    # PIB direct RSS (returns Hindi — still valuable for policy content)
    (
        "pib",
        "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",
        "PIB — All Ministries",
        True,
    ),
    # PIB via Google News RSS (English articles — general)
    (
        "pib",
        "https://news.google.com/rss/search?q=site:pib.gov.in+when:3d&hl=en-IN&gl=IN&ceid=IN:en",
        "PIB — English",
        True,
    ),
    # PIB Press Releases (broader search — catches ministry-specific releases
    # like Monument Conservation, Coal Auctions, Scheme updates etc.)
    (
        "pib",
        "https://news.google.com/rss/search?q=site:pib.gov.in+press+release+when:3d&hl=en-IN&gl=IN&ceid=IN:en",
        "PIB — Press Releases",
        True,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # BUSINESS STANDARD (direct RSS returns 403; using Google News RSS)
    # ══════════════════════════════════════════════════════════════════════════
    (
        "business standard",
        "https://news.google.com/rss/search?q=site:business-standard.com+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
        "Economy",
        False,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # DOWN TO EARTH  (Environment focus — very UPSC relevant)
    # Direct RSS is dead; using Google News RSS fallback
    # ══════════════════════════════════════════════════════════════════════════
    (
        "down to earth",
        "https://news.google.com/rss/search?q=site:downtoearth.org.in+when:3d&hl=en-IN&gl=IN&ceid=IN:en",
        "Environment",
        True,   # auto_pass=True — DTE is a premium UPSC source
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # THE PRINT  (Policy, governance, analysis)
    # Direct feed broken; using Google News RSS
    # ══════════════════════════════════════════════════════════════════════════
    (
        "the print",
        "https://news.google.com/rss/search?q=site:theprint.in+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
        "Analysis",
        False,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # LIVEMINT
    # ══════════════════════════════════════════════════════════════════════════
    (
        "livemint",
        "https://www.livemint.com/rss/news",
        "Economy",
        False,
    ),
    (
        "livemint editorial",
        "https://www.livemint.com/rss/opinion",
        "Opinion",
        True,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # THE WIRE  (Politics, Economy, Science — strong UPSC analysis)
    # ══════════════════════════════════════════════════════════════════════════
    (
        "the wire",
        "https://news.google.com/rss/search?q=site:thewire.in+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
        "Analysis",
        False,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # MINT ECONOMY  (Budget, RBI, fiscal policy focus)
    # ══════════════════════════════════════════════════════════════════════════
    (
        "livemint",
        "https://www.livemint.com/rss/economy",
        "Economy",
        False,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # ECONOMIC TIMES — Policy & Economy
    # ══════════════════════════════════════════════════════════════════════════
    (
        "economic times",
        "https://news.google.com/rss/search?q=site:economictimes.indiatimes.com+policy+OR+budget+OR+RBI+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
        "Economy",
        False,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # SCIENCE REPORTER / DST  (ISRO, DRDO, S&T — UPSC Prelims focus)
    # ══════════════════════════════════════════════════════════════════════════
    (
        "pib",
        "https://news.google.com/rss/search?q=site:pib.gov.in+ISRO+OR+DRDO+OR+science+when:5d&hl=en-IN&gl=IN&ceid=IN:en",
        "Science & Technology",
        True,
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2  —  IMPORT THE FILTER
# Importing from news_filter.py which must be in the same directory.
# ─────────────────────────────────────────────────────────────────────────────

def _load_filter():
    """Safely import is_relevant and normalize_title from filter.py."""
    try:
        from filter import is_relevant, normalize_title
        return is_relevant, normalize_title
    except ImportError:
        # Fallback: always return True (no filtering)
        print("[WARN] filter.py not found — all articles will be returned unfiltered.")
        _noop_norm = lambda t: t.lower().strip()
        return (lambda text, source_label="", title="", strict=False, category="": True), _noop_norm


is_relevant, normalize_title = _load_filter()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3  —  RSS FETCHER
# ─────────────────────────────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )
}


def _fetch_feed(rss_url: str, verbose: bool = False) -> Optional[object]:
    """
    Fetch and parse an RSS feed.
    Tries feedparser first; falls back to requests + feedparser if the
    feed server blocks feedparser's default user-agent.
    Returns a feedparser result object, or None on failure.
    """
    if not HAS_FEEDPARSER:
        return None

    # Attempt 1: direct feedparser fetch
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries:
            return feed
    except Exception as e:
        if verbose: print(f"        ↳ [DEBUG] Feedparser failed: {e}")
        pass

    # Attempt 2: fetch raw bytes via requests, then parse
    if HAS_REQUESTS:
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            resp = requests.get(rss_url, headers=_HEADERS, timeout=15, verify=False)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            if feed.entries:
                return feed
        except Exception as e:
            if verbose: print(f"        ↳ [DEBUG] Request failed: {e}")
            pass

    return None


def _parse_date(entry) -> str:
    """Extract a normalized ISO date string from a feed entry."""
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def _clean(text: str) -> str:
    """Strip HTML tags and normalise whitespace."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _uid(url: str) -> str:
    """Stable deduplication key from the article URL."""
    return hashlib.md5(url.encode()).hexdigest()


_GOOGLE_REDIRECT_RE = re.compile(r"https://news\.google\.com/rss/articles/([^?]+)")

def _resolve_google_url(url: str) -> str:
    """
    Google News RSS entries have URLs like:
        https://news.google.com/rss/articles/CBMi...
    These redirect to the real article URL.
    We try to resolve the redirect (non-blocking); fall back to the raw URL.
    """
    if not _GOOGLE_REDIRECT_RE.match(url):
        return url
    if not HAS_REQUESTS:
        return url
    try:
        resp = requests.head(url, headers=_HEADERS, timeout=5, allow_redirects=True)
        if resp.url and resp.url != url:
            return resp.url
    except Exception:
        pass
    return url


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4  —  MAIN PUBLIC FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def _parse_date_obj(entry) -> datetime:
    """Extract a datetime object from a feed entry for date comparisons."""
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def _adjust_google_news_url(url: str, days: int) -> str:
    """Rewrite 'when:Xd' in a Google News RSS URL to match the requested days."""
    return re.sub(r'when:\d+d', f'when:{days}d', url)


def fetch_all_news(
    feeds: list = None,
    max_per_feed: int = 30,
    delay_between_feeds: float = 0.5,
    verbose: bool = True,
    days: int = 1,
) -> List[Dict]:
    """
    Fetch articles from all registered RSS feeds, filter for UPSC relevance,
    deduplicate by URL, and return a sorted list of article dicts.

    Parameters
    ----------
    feeds               : List of (label, url, category, auto_pass) tuples.
                          Defaults to RSS_FEEDS.
    max_per_feed        : Maximum articles to pull from a single feed.
    delay_between_feeds : Seconds to wait between feed requests (politeness).
    verbose             : Print a one-line summary per feed.
    days                : Number of days of news to fetch (default: 1).
                          For catch-up, set to the number of missed days.
                          Google News feeds automatically adjust their
                          time window; direct RSS feeds are date-filtered.

    Returns
    -------
    List of dicts, each with keys:
        title, url, summary, source, category, date, uid
    Sorted newest-first.
    """
    if feeds is None:
        feeds = RSS_FEEDS

    # Date cutoff: only include articles published within `days` days
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    seen_uids:   set = set()
    seen_norms:  set = set()   # normalized titles for LIVE:/BREAKING: dedup
    results:     list = []

    if verbose:
        print(f"📅 Fetching news for the last {days} day(s) "
              f"(cutoff: {cutoff.strftime('%Y-%m-%d %H:%M')} UTC)\n")

    for label, rss_url, category, auto_pass in feeds:

        # ── Adjust Google News URLs for the requested time window ─────
        actual_url = rss_url
        if "news.google.com" in rss_url:
            actual_url = _adjust_google_news_url(rss_url, max(days, 2))
            # Google News needs at least 2d to return results reliably

        if verbose:
            print(f"[FETCH] {label:<30} {category:<25} {actual_url[:55]}...")

        feed = _fetch_feed(actual_url, verbose=verbose)
        if feed is None:
            if verbose:
                print(f"        ↳ ❌ Failed to fetch")
            time.sleep(delay_between_feeds)
            continue

        count = 0
        skipped_old = 0
        for entry in feed.entries[:max_per_feed]:
            url     = getattr(entry, "link", "") or ""
            title   = _clean(getattr(entry, "title",   "") or "")
            summary = _clean(getattr(entry, "summary", "") or
                             getattr(entry, "description", "") or "")

            if not url or not title:
                continue

            # ── Date filtering ────────────────────────────────────────────
            # Skip articles older than the requested window
            entry_date = _parse_date_obj(entry)
            if entry_date < cutoff:
                skipped_old += 1
                continue

            # ── Google News RSS handling ──────────────────────────────────
            # Google News titles include " - Source Name" suffix; strip it
            if "news.google.com" in rss_url:
                # Strip source suffix like " - Down To Earth", " - PIB" etc.
                if " - " in title:
                    title = title.rsplit(" - ", 1)[0].strip()
                # Try to get the original source URL from the entry
                source_tag = getattr(entry, "source", None)
                if source_tag and hasattr(source_tag, "href"):
                    # Use domain from source for dedup purposes
                    pass  # URL from Google News still works for reading

            # ── Normalized-title dedup (catches LIVE:/BREAKING: re-publishes) ─
            # This runs BEFORE the UID check and BEFORE relevance scoring so that
            # the cheaper/faster check eliminates duplicates early.
            norm = normalize_title(title)
            if norm and norm in seen_norms:
                # Duplicate headline — skip silently
                continue

            uid = _uid(url)
            if uid in seen_uids:
                continue

            # ── Relevance check ───────────────────────────────────────────────
            # ALL articles go through the filter, including PIB/DTE/editorials.
            # Trusted sources get a generous source bonus (1.5) and low threshold
            # so most genuinely relevant content passes, but administrative fluff
            # (guard ceremonies, pension camps, ship arrivals) is blocked via
            # soft blacklist penalties.
            relevant = is_relevant(
                text=summary,
                source_label=label,
                title=title,
                strict=False,
                category=category,
            )

            if not relevant:
                if verbose and (auto_pass or label in [
                    "pib", "down to earth", "the print", "the wire"
                ]):
                    print(f"        ↳ [SKIP] {title[:70]}...")
                continue

            # ── Resolve Google News redirect URLs ────────────────────────────
            if "news.google.com/rss/articles" in url:
                url = _resolve_google_url(url)
                uid  = _uid(url)   # recompute uid after resolution

            seen_uids.add(uid)
            seen_norms.add(norm)
            results.append({
                "title":    title,
                "url":      url,
                "content":  summary[:600],   # extended from 400 → 600 for AI context
                "source":   label,
                "category": category,
                "date":     _parse_date(entry),
                "uid":      uid,
            })
            count += 1

        suffix = f" ({skipped_old} older skipped)" if skipped_old else ""
        if verbose:
            print(f"        ↳ ✅ {count} relevant articles{suffix}")

        time.sleep(delay_between_feeds)

    # Sort newest-first
    results.sort(key=lambda x: x["date"], reverse=True)

    if verbose:
        print(f"\n{'─'*60}")
        print(f"Total articles fetched: {len(results)} (last {days} day(s))")

    return results


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5  —  CONVENIENCE FETCH FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def fetch_hindu_editorials(max_articles: int = 10) -> List[Dict]:
    """
    Fetch only The Hindu Editorial and Op-Ed / Lead articles.
    All articles auto-pass relevance (editorial feeds are pre-curated).
    """
    editorial_feeds = [f for f in RSS_FEEDS if "the hindu" in f[0] and f[3]]
    return fetch_all_news(feeds=editorial_feeds, max_per_feed=max_articles)


def fetch_ie_explained(max_articles: int = 10) -> List[Dict]:
    """
    Fetch only Indian Express Explained and Opinion articles.
    All articles auto-pass relevance.
    """
    explained_feeds = [f for f in RSS_FEEDS if "ie explained" in f[0] or
                       "indian express opinion" in f[0]]
    return fetch_all_news(feeds=explained_feeds, max_per_feed=max_articles)


def fetch_pib(max_articles: int = 20) -> List[Dict]:
    """Fetch PIB press releases (all auto-pass)."""
    pib_feeds = [f for f in RSS_FEEDS if f[0] == "pib"]
    return fetch_all_news(feeds=pib_feeds, max_per_feed=max_articles)


def fetch_by_category(category: str) -> List[Dict]:
    """
    Fetch articles filtered by category label.
    category: "Editorial" | "Explained" | "National" | "International"
              | "Economy" | "Environment" | "Science & Technology" | etc.
    """
    cat_feeds = [f for f in RSS_FEEDS if category.lower() in f[2].lower()]
    return fetch_all_news(feeds=cat_feeds)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6  —  STREAMLIT DISPLAY HELPER
# Call this from your app.py to render the news inside the Ask Esu page
# or a dedicated "Current Affairs" page.
# ─────────────────────────────────────────────────────────────────────────────

def render_news_streamlit(articles: List[Dict], title: str = "📰 Today's News"):
    """
    Render a list of article dicts inside a Streamlit page.
    Requires: import streamlit as st
    """
    try:
        import streamlit as st
    except ImportError:
        print("[WARN] Streamlit not available.")
        return

    SOURCE_COLORS = {
        "the hindu editorial":   "#d32f2f",
        "the hindu opinion":     "#c62828",
        "the hindu":             "#e53935",
        "ie explained":          "#1565c0",
        "indian express opinion":"#0d47a1",
        "indian express":        "#1976d2",
        "pib":                   "#2e7d32",
        "bs editorial":          "#6a1b9a",
        "business standard":     "#7b1fa2",
        "down to earth":         "#00695c",
        "the print":             "#f57f17",
        "livemint":              "#4e342e",
        "livemint editorial":    "#3e2723",
    }
    DEFAULT_COLOR = "#546e7a"

    st.markdown(f"## {title}")

    if not articles:
        st.info("No articles found. Check your internet connection or try again later.")
        return

    # Group by category for cleaner display
    from collections import defaultdict
    by_cat = defaultdict(list)
    for a in articles:
        by_cat[a["category"]].append(a)

    # Priority order
    priority = [
        "Editorial", "Explained", "Opinion",
        "National", "International", "Economy",
        "Environment", "Science & Technology",
        "Polity", "PIB — All Ministries", "PIB — Economy",
        "PIB — Science & Technology", "PIB — Environment",
        "Analysis", "State News",
    ]
    ordered_cats = [c for c in priority if c in by_cat]
    ordered_cats += [c for c in by_cat if c not in ordered_cats]

    for cat in ordered_cats:
        cat_articles = by_cat[cat]
        st.markdown(f"### {cat}  `{len(cat_articles)} articles`")

        for a in cat_articles:
            color = SOURCE_COLORS.get(a["source"], DEFAULT_COLOR)
            with st.expander(f"📌 {a['title']}", expanded=False):
                st.markdown(
                    f"<span style='background:{color};color:white;"
                    f"padding:3px 10px;border-radius:20px;"
                    f"font-size:12px;font-weight:700'>"
                    f"{a['source'].upper()}</span>"
                    f"&nbsp;&nbsp;<span style='color:#888;font-size:12px'>"
                    f"{a['date']}</span>",
                    unsafe_allow_html=True
                )
                st.markdown(f"**{a['summary']}**" if a["summary"] else "")
                st.markdown(
                    f"[🔗 Read Full Article]({a['url']})",
                    unsafe_allow_html=True
                )
        st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7  —  HOW TO ADD THIS PAGE TO app.py
# ─────────────────────────────────────────────────────────────────────────────
#
#  In your app.py, add "Current Affairs" to menu_options:
#
#      menu_options = [
#          "Daily Entry", "Calendar", "Set Target", "Study Target Manager",
#          "Productivity Analysis", "Ask Esu", "Expenses",
#          "Current Affairs",          # ← ADD THIS
#      ]
#
#  Then add the menu handler:
#
#      elif menu == "Current Affairs":
#          from news_fetcher import (
#              fetch_all_news, fetch_hindu_editorials,
#              fetch_ie_explained, fetch_pib, render_news_streamlit
#          )
#
#          st.title("📰 Current Affairs — UPSC News Feed")
#
#          tab_all, tab_editorial, tab_explained, tab_pib = st.tabs([
#              "🗞️ All News",
#              "📝 Hindu Editorial",
#              "💡 IE Explained",
#              "📣 PIB",
#          ])
#
#          with tab_all:
#              if st.button("🔄 Fetch All News"):
#                  with st.spinner("Fetching from all sources..."):
#                      st.session_state["news_all"] = fetch_all_news()
#              render_news_streamlit(
#                  st.session_state.get("news_all", []),
#                  title="All UPSC News"
#              )
#
#          with tab_editorial:
#              if st.button("🔄 Fetch Hindu Editorials"):
#                  with st.spinner("Fetching Hindu editorials..."):
#                      st.session_state["news_editorial"] = fetch_hindu_editorials()
#              render_news_streamlit(
#                  st.session_state.get("news_editorial", []),
#                  title="The Hindu — Editorial & Opinion"
#              )
#
#          with tab_explained:
#              if st.button("🔄 Fetch IE Explained"):
#                  with st.spinner("Fetching IE Explained..."):
#                      st.session_state["news_explained"] = fetch_ie_explained()
#              render_news_streamlit(
#                  st.session_state.get("news_explained", []),
#                  title="Indian Express — Explained & Opinion"
#              )
#
#          with tab_pib:
#              if st.button("🔄 Fetch PIB Releases"):
#                  with st.spinner("Fetching PIB releases..."):
#                      st.session_state["news_pib"] = fetch_pib()
#              render_news_streamlit(
#                  st.session_state.get("news_pib", []),
#                  title="PIB — Government Press Releases"
#              )
#
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8  —  QUICK TEST (run directly: python news_fetcher.py)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "═" * 65)
    print("  UPSC News Fetcher — connectivity test")
    print("═" * 65)

    # Test only a few feeds to check connectivity quickly
    test_feeds = [
        ("the hindu editorial",  "https://www.thehindu.com/opinion/editorial/?service=rss",   "Editorial",  True),
        ("ie explained",         "https://indianexpress.com/section/explained/feed/",          "Explained",  True),
        ("pib",                  "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",    "PIB",        True),
        ("the hindu",            "https://www.thehindu.com/news/national/?service=rss",        "National",   False),
        ("indian express",       "https://indianexpress.com/section/world/feed/",              "World",      False),
    ]

    articles = fetch_all_news(feeds=test_feeds, max_per_feed=5, verbose=True)

    print(f"\n{'─'*65}")
    print(f"{'SOURCE':<28} {'CATEGORY':<15} TITLE")
    print(f"{'─'*65}")
    for a in articles:
        src  = a['source'][:26]
        cat  = a['category'][:13]
        title = a['title'][:55]
        print(f"{src:<28} {cat:<15} {title}")

    print(f"\n✅ Done — {len(articles)} articles ready for use.")
