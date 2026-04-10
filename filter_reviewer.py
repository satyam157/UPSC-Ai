"""
Filter Reviewer — filter_reviewer.py
======================================
Three complementary audit modes:

1. perform_filter_review()  [LLM-based qualitative]
   Uses an LLM to review a sample of recently fetched news and produce a
   qualitative "Filter Audit Report" (High-Value / Marginal / Noise breakdown)
   with blacklist/keyword suggestions.

2. run_db_audit()           [Rule-based, instant]
   Re-scores EVERY article currently stored in the DB against the LIVE
   filter logic.  Surfaces retroactive noise (items that passed an older
   filter version but would now be blocked) and computes per-category stats.
   Optionally deletes retroactive noise by PRIMARY KEY (safe, no title-match
   ambiguity).

3. run_full_audit()         [Combined: rule-based + LLM]
   Runs run_db_audit() first, then calls perform_filter_review() on the
   noise subset for deeper LLM inspection.  Best for weekly maintenance.

v5.0 Changes:
  - run_db_audit() now uses get_news_with_ids() + delete_news_by_ids() for
    safe PK-based purge (replaces brittle title-match DELETE).
  - Added export_audit_csv() to dump audit results to a CSV file.
  - Added run_full_audit() for a one-call combined workflow.
  - Category stats now include a pass-rate % bar in console output.
  - Audit report saved to DB includes per-category breakdown table.

Usage
-----
    # LLM audit (qualitative):
    python filter_reviewer.py --mode llm

    # Rule-based audit (fast, no LLM needed):
    python filter_reviewer.py --mode db

    # Combined audit:
    python filter_reviewer.py --mode full

    # Rule-based audit + delete retroactive noise:
    python filter_reviewer.py --mode db --purge

    # Export audit results to CSV:
    python filter_reviewer.py --mode db --csv audit_results.csv
"""

import csv
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

# ─── Internal imports ─────────────────────────────────────────────────────────
from filter import score_article
from db import get_news, get_news_with_ids, delete_news_by_ids, save_ai_report

try:
    from llm import ask_llm
    HAS_LLM = True
except ImportError:
    HAS_LLM = False


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — LLM-BASED FILTER REVIEW (qualitative)
# ══════════════════════════════════════════════════════════════════════════════

def get_recent_news(days: int = 2) -> List[Dict]:
    """Fetch news from the last X days from database for review."""
    news_data = get_news()
    cutoff = datetime.now() - timedelta(days=days)

    recent = []
    for n in news_data:
        # n structure: (title, content, date, url, source, category)
        try:
            date_str  = str(n[2]).strip()[:10]
            news_date = datetime.strptime(date_str, "%Y-%m-%d")
            if news_date >= cutoff:
                recent.append({
                    "title":    n[0],
                    "content":  n[1],
                    "date":     n[2],
                    "source":   n[4],
                    "category": n[5] if len(n) > 5 else "General",
                })
        except Exception:
            continue
    return recent


_UPSC_TOPIC_MAP = """
UPSC-relevant topics:
  Polity, Economy, IR/World Affairs, Environment, Science & Technology,
  Defence & Security, Social Issues, Governance & Schemes.
Noise: Sports scores, celebrity news, local crime, royal family drama,
  viral content, gadget reviews, IPO grey market, quarterly earnings.
"""

def perform_filter_review() -> str:
    """
    Performs an LLM meta-review of current news items to evaluate UPSC
    relevance filtering.  Returns the audit report text.
    """
    if not HAS_LLM:
        return "LLM not available — run `pip install groq` or configure GROQ_API_KEY."

    recent_news = get_recent_news(days=2)
    if not recent_news:
        return "No news items found for review in the last 2 days."

    sample_size = min(30, len(recent_news))
    sample      = recent_news[:sample_size]

    review_prompt = f"""You are a UPSC Filter Auditor. Review these {sample_size} news items.
{_UPSC_TOPIC_MAP}

NEWS ITEMS:
{json.dumps(sample, indent=2)}

TASK:
1. Categorize each item:
   - ✅ High Value: Crucial for Mains/Prelims (Policy, Economy, IR, S&T, Environment).
   - ⚠️  Marginal: Somewhat useful but borderline.
   - ❌ Noise/Irrelevant: Should have been filtered out.

2. Evaluate Filtering Quality:
   - Which noise items slipped through?
   - Suggest 5 specific BLACKLIST phrases to add.
   - Suggest 5 HIGH-VALUE keywords we might be missing.

3. Provide a "Daily Relevance Score" (0–100%) and brief explanation.

Format your response as a structured Audit Report."""

    try:
        review_text = ask_llm(review_prompt)
        save_ai_report("Filter Audit", datetime.now().strftime("%Y-%m-%d"), review_text)
        return review_text
    except Exception as e:
        return f"Error during AI review: {str(e)}"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — RULE-BASED DB AUDIT (instant, no LLM)
# ══════════════════════════════════════════════════════════════════════════════

def run_db_audit(
    days: int = 30,
    purge: bool = False,
    verbose: bool = True,
    csv_path: Optional[str] = None,
) -> Dict:
    """
    Re-score every article in the DB against the CURRENT filter logic.

    Parameters
    ----------
    days      : Only audit articles from the last N days (default 30).
    purge     : If True, delete retroactive noise articles from DB by PRIMARY KEY.
    verbose   : Print a live progress report to stdout.
    csv_path  : If provided, export full audit results to this CSV file path.

    Returns
    -------
    dict with:
        total           : int   — articles audited
        pass_count      : int   — articles that pass current filter
        noise_count     : int   — articles that would now be blocked
        hard_blocked    : list  — articles blocked by HARD_BLACKLIST
        soft_blocked    : list  — articles blocked by SOFT scoring
        by_category     : dict  — {category: {pass, noise, total}}
        relevance_score : float — pass_count / total * 100
        purged          : int   — rows deleted (if purge=True)
    """
    all_news = get_news_with_ids()    # (id, title, content, date, url, source, category)
    cutoff   = datetime.now() - timedelta(days=days)

    # Filter to requested window
    window = []
    for n in all_news:
        try:
            date_str  = str(n[3]).strip()[:10]   # n[3] = date
            news_date = datetime.strptime(date_str, "%Y-%m-%d")
            if news_date >= cutoff:
                window.append(n)
        except Exception:
            window.append(n)   # include if date unparseable

    if not window:
        if verbose:
            print("⚠️  No articles found in the requested date window.")
        return {}

    # ── Score every article ───────────────────────────────────────────────────
    hard_blocked_articles: List[Dict] = []
    soft_blocked_articles: List[Dict] = []
    passing_articles:      List[Dict] = []
    by_category:           Dict[str, Dict] = {}

    for n in window:
        row_id   = n[0]   # PRIMARY KEY
        title    = n[1] or ""
        content  = n[2] or ""
        date     = n[3] or ""
        url      = n[4] or ""
        source   = n[5] or ""
        category = n[6] if len(n) > 6 else "General"

        result = score_article(
            title=title,
            text=content,
            source_label=source,
            category=category,
        )

        # Track by category
        cat_stats = by_category.setdefault(category, {"pass": 0, "noise": 0, "total": 0})
        cat_stats["total"] += 1

        article_summary = {
            "id":       row_id,
            "title":    title[:80],
            "source":   source,
            "category": category,
            "date":     date,
            "url":      url,
            "score":    result["score"],
            "threshold":result["threshold"],
            "reason":   result["reason"],
            "hv_hits":  result.get("hv_hits", [])[:5],
            "soft_hits":result.get("soft_hits", [])[:3],
        }

        if result["hard_blocked"]:
            hard_blocked_articles.append({**article_summary, "blocked_by": result["reason"]})
            cat_stats["noise"] += 1
        elif not result["passes"]:
            soft_blocked_articles.append(article_summary)
            cat_stats["noise"] += 1
        else:
            passing_articles.append(article_summary)
            cat_stats["pass"] += 1

    noise_articles = hard_blocked_articles + soft_blocked_articles
    total          = len(window)
    pass_count     = len(passing_articles)
    noise_count    = len(noise_articles)
    rel_score      = round(pass_count / total * 100, 1) if total else 0.0

    # ── Console report ────────────────────────────────────────────────────────
    if verbose:
        sep = "═" * 72
        print(f"\n{sep}")
        print(f"  📊  UPSC FILTER DB AUDIT  —  last {days} day(s)")
        print(f"  Audited: {total}  |  Pass: {pass_count}  "
              f"|  Noise: {noise_count}  |  Score: {rel_score}%")
        print(sep)

        if hard_blocked_articles:
            print(f"\n  🚫  HARD-BLOCKED ({len(hard_blocked_articles)} — retroactive noise, safe to delete):")
            for a in hard_blocked_articles:
                print(f"    [id={a['id']:>5}] [{a['source']:<25}] {a['title'][:55]}")
                print(f"         ↳ {a['blocked_by']}")

        if soft_blocked_articles:
            print(f"\n  ⚠️   SOFT-BLOCKED ({len(soft_blocked_articles)} — low score/marginal):")
            for a in soft_blocked_articles[:20]:
                hits = ", ".join(a["soft_hits"]) if a["soft_hits"] else "low score"
                print(f"    [id={a['id']:>5}] [{a['source']:<25}] {a['title'][:55]}")
                print(f"         ↳ score={a['score']:.1f} (need {a['threshold']:.1f}) | {hits}")

        # ── Category table ────────────────────────────────────────────────────
        print(f"\n  📂  BY CATEGORY:")
        print(f"  {'Category':<35} {'Pass':>5} {'Noise':>6} {'Total':>6}  {'Rate':>5}  Bar")
        print(f"  {'─'*68}")
        for cat, s in sorted(by_category.items(), key=lambda x: -x[1]["total"]):
            pct = round(s["pass"] / s["total"] * 100) if s["total"] else 0
            bar = "█" * min(s["pass"], 20) + "░" * min(s["noise"], 20)
            print(f"  {cat:<35} {s['pass']:>5} {s['noise']:>6} {s['total']:>6}  {pct:>4}%  {bar}")

        status = (
            "✅ Excellent"  if rel_score >= 88 else
            "✅ Good"       if rel_score >= 80 else
            "⚠️  Needs work" if rel_score >= 65 else
            "❌ Poor"
        )
        print(f"\n  {'─'*72}")
        print(f"  Daily Relevance Score: {rel_score}%  ({status})")
        print(f"  {sep}\n")

    # ── Optional CSV export ───────────────────────────────────────────────────
    if csv_path:
        _export_csv(
            csv_path,
            hard_blocked_articles,
            soft_blocked_articles,
            passing_articles,
            verbose=verbose,
        )

    # ── Optional PK-based purge ───────────────────────────────────────────────
    purged = 0
    if purge and noise_articles:
        noise_ids = [a["id"] for a in noise_articles if a.get("id")]
        if noise_ids:
            purged = delete_news_by_ids(noise_ids)
            if verbose:
                print(f"  🗑️  Purged {purged} noise articles from DB (by primary key).")

    # ── Save report to DB ─────────────────────────────────────────────────────
    _save_audit_to_db(
        days=days,
        total=total,
        pass_count=pass_count,
        noise_count=noise_count,
        rel_score=rel_score,
        hard_blocked=hard_blocked_articles,
        soft_blocked=soft_blocked_articles,
        by_category=by_category,
        purged=purged,
    )

    return {
        "total":           total,
        "pass_count":      pass_count,
        "noise_count":     noise_count,
        "hard_blocked":    hard_blocked_articles,
        "soft_blocked":    soft_blocked_articles,
        "by_category":     by_category,
        "relevance_score": rel_score,
        "purged":          purged,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — COMBINED AUDIT (rule-based + LLM on noise subset)
# ══════════════════════════════════════════════════════════════════════════════

def run_full_audit(days: int = 7, purge: bool = False) -> Dict:
    """
    Combined audit:
    1. Run rule-based DB audit to identify noise.
    2. Send the noise subset (up to 20 items) to LLM for confirmation +
       keyword extraction suggestions.
    3. Return combined results.
    """
    print("═" * 72)
    print("  🔍  FULL AUDIT (Rule-based + LLM verification)")
    print("═" * 72)

    # Step 1: Rule-based pass
    db_result = run_db_audit(days=days, purge=False, verbose=True)

    if not db_result:
        return {}

    noise_items = db_result.get("hard_blocked", []) + db_result.get("soft_blocked", [])

    llm_report = ""
    if HAS_LLM and noise_items:
        sample = noise_items[:20]
        print(f"\n  🤖  Sending {len(sample)} noise items to LLM for deep review...")

        prompt = (
            "You are a UPSC Filter Auditor verifying rule-based noise detections.\n"
            "The following articles were flagged as noise by our rule-based filter.\n"
            "For each article: confirm if it should be deleted or reconsidered.\n"
            "At the end, suggest 5 new BLACKLIST phrases and 5 new HIGH-VALUE keywords.\n\n"
            f"NOISE ITEMS:\n{json.dumps(sample, indent=2, default=str)}"
        )
        try:
            llm_report = ask_llm(prompt)
            print("\n  📝  LLM Verification Report:")
            print("  " + "\n  ".join(llm_report.split("\n")[:30]))
        except Exception as e:
            llm_report = f"LLM verification failed: {e}"
            print(f"  ⚠️  {llm_report}")

    # Step 2: Now purge if requested (after LLM review)
    if purge and noise_items:
        noise_ids = [a["id"] for a in noise_items if a.get("id")]
        purged    = delete_news_by_ids(noise_ids)
        db_result["purged"] = purged
        print(f"\n  🗑️  Purged {purged} noise articles from DB.")

    db_result["llm_verification"] = llm_report
    return db_result


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _export_csv(
    csv_path: str,
    hard_blocked: List[Dict],
    soft_blocked: List[Dict],
    passing: List[Dict],
    verbose: bool = True,
) -> None:
    """Export full audit results to a CSV file."""
    rows = []
    for a in hard_blocked:
        rows.append({**a, "audit_result": "HARD_BLOCKED"})
    for a in soft_blocked:
        rows.append({**a, "audit_result": "SOFT_BLOCKED"})
    for a in passing:
        rows.append({**a, "audit_result": "PASS"})

    if not rows:
        return

    fieldnames = ["audit_result", "id", "title", "source", "category",
                  "date", "score", "threshold", "reason", "soft_hits", "hv_hits", "url"]

    path = Path(csv_path)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            # Convert lists to pipe-separated strings for CSV
            row = dict(row)
            row["soft_hits"] = " | ".join(row.get("soft_hits", []))
            row["hv_hits"]   = " | ".join(row.get("hv_hits", []))
            writer.writerow(row)

    if verbose:
        print(f"\n  📄  Audit CSV exported: {path.resolve()} ({len(rows)} rows)")


def _save_audit_to_db(
    days, total, pass_count, noise_count, rel_score,
    hard_blocked, soft_blocked, by_category, purged,
) -> None:
    """Persist the audit report text to the ai_reports table."""
    status = (
        "✅ Excellent"  if rel_score >= 88 else
        "✅ Good"       if rel_score >= 80 else
        "⚠️  Needs work" if rel_score >= 65 else
        "❌ Poor"
    )
    lines = [
        f"DB Audit Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Window: last {days} days | Total: {total} | "
        f"Pass: {pass_count} | Noise: {noise_count} | "
        f"Score: {rel_score}%  {status}",
        "",
        "=== HARD-BLOCKED ===",
    ]
    for a in hard_blocked:
        lines.append(f"  [id={a['id']}] [{a['source']}] {a['title']} — {a.get('blocked_by', a['reason'])}")

    lines += ["", "=== SOFT-BLOCKED (top 20) ==="]
    for a in soft_blocked[:20]:
        lines.append(f"  [id={a['id']}] [{a['source']}] {a['title']} — score={a['score']:.1f}")

    lines += ["", "=== BY CATEGORY ==="]
    for cat, s in sorted(by_category.items(), key=lambda x: -x[1]["total"]):
        pct = round(s["pass"] / s["total"] * 100) if s["total"] else 0
        lines.append(f"  {cat}: {s['pass']}/{s['total']} pass ({pct}%)")

    if purged:
        lines += ["", f"=== PURGED: {purged} articles deleted by PK ==="]

    try:
        save_ai_report(
            "DB Filter Audit",
            datetime.now().strftime("%Y-%m-%d"),
            "\n".join(lines),
        )
    except Exception:
        pass   # non-fatal if DB not available


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="UPSC Filter Reviewer — audit news filtering quality"
    )
    parser.add_argument(
        "--mode", choices=["llm", "db", "full"], default="db",
        help=(
            "'llm'  = qualitative LLM audit of recent news\n"
            "'db'   = rule-based DB rescore (default)\n"
            "'full' = DB rescore + LLM verification of noise"
        )
    )
    parser.add_argument(
        "--days", type=int, default=30,
        help="Audit articles from last N days (default: 30)"
    )
    parser.add_argument(
        "--purge", action="store_true",
        help="Delete retroactive noise articles from DB (safe PK-based delete)"
    )
    parser.add_argument(
        "--csv", type=str, default="",
        metavar="FILE",
        help="Export audit results to a CSV file (e.g. --csv audit.csv)"
    )
    args = parser.parse_args()

    if args.mode == "llm":
        print("Running LLM Filter Review...")
        report = perform_filter_review()
        print("\n" + "=" * 60)
        print("DAILY FILTER AUDIT REPORT (LLM)")
        print("=" * 60)
        print(report)

    elif args.mode == "full":
        run_full_audit(days=args.days, purge=args.purge)

    else:
        run_db_audit(
            days=args.days,
            purge=args.purge,
            verbose=True,
            csv_path=args.csv or None,
        )
