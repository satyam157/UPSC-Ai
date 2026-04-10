#!/usr/bin/env python3
"""
URL Content Fetcher & Summarizer v6.0 — Advanced Multi-Source UPSC Summarizer
==============================================================================
Fetches content from coaching institutes and generates crisp UPSC-relevant summaries
with advanced features:

v6.0 Upgrades:
  • Multi-source cross-referencing: auto-searches for related coaching institute analyses
  • PDF text integration: accepts raw text alongside URLs for richer context
  • Comparative analysis: when multiple articles cover the same topic
  • Prelims probable questions embedded in summary
  • Timeline extraction for chronological events
  • Enhanced entity deep-dive with more structured data
  • Batch processing with progress tracking
"""

import requests
from bs4 import BeautifulSoup
from llm import ask_llm, ask_llm_high_quality
from urllib.parse import urljoin, quote_plus
import time
import re

# Coaching institute URLs (most reliable sources)
COACHING_INSTITUTES = {
    "Next IAS": "https://nextias.com",
    "Vision IAS": "https://visionias.in",
    "Forum IAS": "https://forumias.com",
    "Vajiram & Ravi": "https://vajiramandrav.com",
    "Drishti IAS": "https://www.drishtiias.com",
    "Insights IAS": "https://www.insightsonindia.com",
}


class URLSummarizer:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.timeout = 15
    
    def fetch_article(self, url):
        """
        Fetch article content from URL with better error handling
        Returns: (title, content, source, error_message)
        """
        try:
            # Ensure URL has protocol
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # Identify source coaching institute
            source = "Unknown"
            for institute, base_url in COACHING_INSTITUTES.items():
                if base_url in url:
                    source = institute
                    break
            
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            response = requests.get(url, headers=self.headers, timeout=self.timeout, 
                                   allow_redirects=True, verify=False)
            response.raise_for_status()
            
            # Check if response is too short
            if len(response.content) < 1000:
                return None, None, source, f"⚠️ Page content too short - likely a list/index page"
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for tag in soup(['script', 'style', 'nav', 'footer', 'ads', 'sidebar', 
                           'noscript', 'iframe', 'form']):
                tag.decompose()
            
            # Remove ad-related divs
            for div in soup.find_all(['div', 'aside'], class_=re.compile(
                r'(ad|sidebar|social|share|comment|related|popup|banner|newsletter)', re.I)):
                div.decompose()
            
            # Get title
            title = None
            if soup.find('h1'):
                title = soup.find('h1').get_text(strip=True)
            elif soup.find('title'):
                title = soup.find('title').get_text(strip=True)
                title = title.split('|')[0].strip()  # Remove extra | suffixes
            else:
                title = "Article - No Title Found"
            
            # Get main content - try multiple strategies
            content_sections = []
            
            # Strategy 1: Look for article containers
            article_div = (
                soup.find('article') or 
                soup.find('main') or 
                soup.find(attrs={'class': re.compile(
                    r'(content|post-content|article-content|entry-content|article-body|'
                    r'course-content|td-post-content|single-post|blog-content)', re.I)}) or
                soup.find(attrs={'id': re.compile(
                    r'(content|post|article|main-content|post-body)', re.I)})
            )
            
            if article_div:
                paragraphs = article_div.find_all(['p', 'li', 'h2', 'h3', 'blockquote'], recursive=True)
            else:
                # Fallback: Get all paragraphs
                paragraphs = soup.find_all(['p', 'h2', 'h3'])
            
            # Extract and filter content
            for para in paragraphs:
                text = para.get_text(strip=True)
                if len(text) > 30:  # Only meaningful paragraphs
                    # Tag headings for structure
                    if para.name in ('h2', 'h3'):
                        content_sections.append(f"## {text}")
                    else:
                        content_sections.append(text)
            
            # Also extract any tables (important for data-heavy UPSC content)
            tables = article_div.find_all('table') if article_div else soup.find_all('table')
            for table in tables[:3]:  # Max 3 tables
                rows = table.find_all('tr')
                table_text = []
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    row_text = " | ".join(c.get_text(strip=True) for c in cells)
                    if row_text:
                        table_text.append(row_text)
                if table_text:
                    content_sections.append("[TABLE]\n" + "\n".join(table_text))
            
            content = '\n\n'.join(content_sections[:30])  # Limit to first 30 sections
            
            if len(content) < 500:
                return None, None, source, f"⚠️ Insufficient content extracted - try a different URL"
            
            return title, content[:14000], source, None  # Limit to ~3500-4000 tokens
        
        except requests.exceptions.Timeout:
            return None, None, "Unknown", f"⏱️ Timeout fetching URL (>{self.timeout}s) - try again or use different URL"
        except requests.exceptions.ConnectionError:
            return None, None, "Unknown", f"🔗 Connection refused - website may be down or blocking automated access"
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None, None, "Unknown", f"❌ Page not found (404) - URL may be broken"
            else:
                return None, None, "Unknown", f"❌ HTTP Error {e.response.status_code}"
        except Exception as e:
            return None, None, "Unknown", f"❌ Error: {str(e)[:100]}"
    
    def fetch_related_coaching_content(self, topic: str) -> list:
        """
        Search for related content from coaching institutes about the given topic.
        Returns list of (source, title, snippet) tuples.
        """
        related = []
        
        # Search Drishti IAS (most accessible for scraping)
        search_urls = [
            f"https://www.drishtiias.com/search?q={quote_plus(topic)}",
            f"https://www.insightsonindia.com/?s={quote_plus(topic)}",
        ]
        
        for search_url in search_urls:
            try:
                resp = requests.get(search_url, headers=self.headers, timeout=8, verify=False)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    # Extract search result titles
                    for link in soup.find_all('a', href=True)[:5]:
                        title = link.get_text(strip=True)
                        if len(title) > 20 and topic.lower().split()[0] in title.lower():
                            source = "Drishti IAS" if "drishti" in search_url else "Insights IAS"
                            related.append((source, title, link['href']))
                            if len(related) >= 3:
                                break
            except Exception:
                continue
        
        return related
    
    def generate_summary(self, title, content, source="Unknown", additional_context=""):
        """
        Generate crisp UPSC-relevant summary with NCERT connections.
        
        v6.0 Enhancements:
          • Prelims Probable Questions section
          • Timeline extraction
          • Committee/Report deep-dives
          • Cross-referenced with DB content
        
        Returns: (summary_with_ncert, error_message)
        """
        try:
            # Fetch related context from DB for cross-referencing
            db_context = ""
            try:
                from db import get_news, get_url_summaries
                # Get related news
                news = get_news()
                if news:
                    related_news = []
                    topic_words = set(title.lower().split()[:5]) if title else set()
                    for n in news[:100]:
                        n_title = str(n[0] or "").lower()
                        if any(w in n_title for w in topic_words if len(w) > 4):
                            related_news.append(n[0])
                        if len(related_news) >= 3:
                            break
                    if related_news:
                        db_context += "\n\nRELATED NEWS IN DATABASE:\n" + "\n".join(f"• {n}" for n in related_news)
                
                # Get related summaries
                summaries = get_url_summaries(limit=20)
                if summaries:
                    related_sums = []
                    for s in summaries[:20]:
                        s_title = str(s[2] or "").lower()
                        if any(w in s_title for w in topic_words if len(w) > 4):
                            related_sums.append(f"{s[2]} ({s[3]})")
                        if len(related_sums) >= 2:
                            break
                    if related_sums:
                        db_context += "\n\nRELATED COACHING ANALYSES:\n" + "\n".join(f"• {s}" for s in related_sums)
            except Exception:
                pass
            
            extra_context = additional_context + db_context
            context_block = f"\n\nADDITIONAL CONTEXT FOR CROSS-REFERENCING:\n{extra_context}" if extra_context else ""
            
            prompt = f"""You are an expert UPSC exam coach and IAS topper mentor. Create a **structured, exam-focused summary** — NO repetition, every line must add unique value.

## ⚠️ FACTUAL INTEGRITY RULES:
- ONLY include facts DIRECTLY from the article or well-established static knowledge.
- NEVER use: "likely", "perhaps", "possibly", "may have", "could be", "it is believed", "reportedly".
- Every claim must have a verifiable anchor: Act name, Article number, year, report name, or data source.
- If information is not in the article and you're adding proactive context, prefix with "📎 Static Fact:"

**Article:** {title}
**Source:** {source}
**Content:** {content[:8000]}
{context_block}

## OUTPUT FORMAT (follow EXACTLY):

### 📌 One-Liner
(Single sentence — what happened, who, when. Must contain at least one specific date/name/number.)

### 🔑 Key Points (Exam-Critical)
| # | Argument WITH (in the article) | Argument AGAINST (in the article) | Significance & Critical Impact |
|---|--------------------------------|-----------------------------------|--------------------------------|
| 1 | [Pro-argument/Fact] | [Critical counter-view/Concern] | [Analytical Takeaway / Impact] |
| 2 | [Fact] | [Concern/Limitation] | [Impact/Implication] |
| 3 | [Fact] | [Concern/Limitation] | [Impact/Implication] |
(Ensure "Argument AGAINST" captures dissent or risks from the article for full insight.)
**CRITICAL RULE for Table:** DO NOT repeat the same argument or core phrase across different rows. Each row MUST add unique value. If the article has fewer than 5 unique points, provide only those (e.g. only 2 or 3 rows) rather than using filler or repeating text.

### 📊 Data, Reports & Evidence (Factual Audit)
- [List EVERY specific number, percentage, committee name, report title, or survey mentioned in the article]
- [If the article cites a government report, name it with year]
- [If statistical claims are made, extract the exact figures]
(This section is STRICTLY extractive — only facts FROM the article. Minimum 3 data points.)

### ⏳ Timeline (if applicable)
- [Year/Date]: [Event/Development]
- [Year/Date]: [Event/Development]
(Extract any chronological progression of events, policies, or developments from the article)

### ⚡ Challenges (Author's Perspective)
- [Strictly extract the author's specific concerns or limitations — use their words, not paraphrases]

### 🛤️ Way Forward (Author's Recommendations)
- [Focus on the author's specific solutions and recommendations — cite specific proposals]

### 🌍 Global Context / Comparison
- [Any international comparisons or global trends mentioned — with country names and specific data]

### 🧭 Tone & Perspective
- **Tone:** [e.g. Critical, Supportive, Reformist, Analytical]
- **Core Stance:** [1-sentence stance of the author — use a direct quote if possible]

### 🌍 UPSC Entity Deep-Dive (Proactive)
(Identify 1-2 most critical entities. Provide FACTUAL data only — every bullet must have a number, date, or Act reference.)
**Follow these sub-rules based on entity type (ONLY output the relevant block, NO "Not applicable" fields):**
- **If Geography/Place:**
  - **About:** (Location with state/district, coordinates if notable)
  - **Key Data:** (Area/Length with numbers; tributaries; drainage basin)
  - **Biodiversity:** (Name specific species with IUCN status in parentheses)
  - **Designations:** (Ramsar/UNESCO/NP status with year of designation)
- **If Organization / Body / Scheme:**
  - **Genesis:** (Established: [year]; HQ: [city]; Parent: [Ministry]; Enabling Act: [name])
  - **Type:** (Statutory under [Act, Section X] / Constitutional under Article [X])
  - **Mandate:** (List specific powers with Section references)
- **If Species / Environment:**
  - **Scientific Name & Family**
  - **IUCN Status:** [Exact category]; **CITES:** Appendix [I/II/III]; **WPA 1972:** Schedule [I-VI]
  - **Habitat:** [Specific ecosystem, states, altitude range]

### 📝 Prelims Probable Questions
(Generate 2-3 MCQ-style questions that UPSC could ask from this article. Include correct answer.)
1. **Q:** [Statement-based or factual question from the article]
   **Options:** A) ... B) ... C) ... D) ...
   **Answer:** [Correct option with brief reason]
2. **Q:** [Second question — different concept]
   **Options:** A) ... B) ... C) ... D) ...
   **Answer:** [Correct option with brief reason]

### 🏷️ UPSC High-Value Keywords
(Extract 5-8 keywords. Each MUST follow this format — no exceptions:)
- **[Keyword]**: [One SPECIFIC, VERIFIABLE fact with a number/date/Act reference. NOT a generic description.]
  Example ✅: **Finance Commission**: Constitutional body under Article 280; 16th FC chaired by Arvind Subramanian recommended 42% devolution to states.
  Example ❌: **Finance Commission**: An important body that deals with financial matters between centre and states.

### 🎯 UPSC Relevance & Mains Integration
- **GS Paper:** GS-[1/2/3/4] | **Topic:** [Specific syllabus topic]
- **Essay Connection:** [How this can be used in an Essay - specific hook]
- **Probable Mains Question:** [One analytical question this could generate]
- **Answer Framework:** [Brief structure: Intro angle → Body points → Conclusion stance]

### 📚 NCERT Link
- **Source:** Class [X] [Subject] → Chapter: "[Name]"
- **Connection:** [1-2 lines on how it connects]
- **Contextual Excerpt:** [Provide a 2-3 sentence verbatim-style line or paragraph from this chapter that captures the core concept relevant to the news.]

### 🔗 Cross-References
- **Related Topics:** [2-3 related UPSC topics this connects to]
- **Previous Year Connection:** [If this topic appeared in PYQs — cite year and paper. If not, write "No direct PYQ match found"]
- **Coaching Perspective:** [How coaching institutes typically frame this topic]

### 💾 Remember
→ [One key takeaway — a SPECIFIC fact, not a generalization]
→ [One date/number/name to memorize]
→ [One Article/Act/Amendment to cite in answers]

**RULES: MAX 600 WORDS. No filler. No repeating the title. Each section adds unique value. Every bullet must contain at least one specific fact.**"""

            summary = ask_llm_high_quality(prompt)
            return summary, None
        
        except Exception as e:
            return None, f"❌ Error generating summary: {str(e)[:150]}"
    
    def generate_text_summary(self, raw_text: str, title: str = "User Text Input"):
        """
        Generate a UPSC summary from raw text input (not from a URL).
        Useful for PDF-extracted text, copied content, etc.
        
        Returns: (summary, error_message)
        """
        if len(raw_text.strip()) < 100:
            return None, "⚠️ Text too short. Please provide at least 100 characters."
        
        return self.generate_summary(title, raw_text, source="User Input")
    
    def generate_comparative_summary(self, articles: list):
        """
        Generate a comparative analysis when multiple articles cover the same topic.
        
        Args:
            articles: List of (title, content, source) tuples
        
        Returns: (comparative_summary, error_message)
        """
        if len(articles) < 2:
            return None, "⚠️ Need at least 2 articles for comparative analysis."
        
        articles_text = ""
        for i, (title, content, source) in enumerate(articles, 1):
            articles_text += f"\n--- ARTICLE {i} ({source}) ---\nTitle: {title}\nContent: {content[:3000]}\n"
        
        prompt = f"""You are an expert UPSC exam coach. Perform a COMPARATIVE ANALYSIS of these articles on the same topic.

{articles_text}

## OUTPUT FORMAT:

### 📌 Common Thread
(What is the shared topic/issue across all articles?)

### ⚖️ Comparative Table
| Dimension | {' | '.join(f'Article {i+1} ({a[2]})' for i, a in enumerate(articles))} |
|-----------|{'|'.join(['---'] * len(articles))}|
| Core Stance | [stance per article] |
| Key Argument | [main argument per article] |
| Data Cited | [key numbers per article] |
| Solution Proposed | [recommendation per article] |

### 🔍 Divergence Points
(Where do the articles DISAGREE or present different perspectives?)

### 🎯 UPSC Synthesis
(How to combine insights from all articles into a comprehensive UPSC answer)

### 📝 Prelims Questions (from combined content)
1. Q: [Question] → Answer: [Option]
2. Q: [Question] → Answer: [Option]

### 💡 Mains Answer Integration
(How to use contrasting viewpoints in a balanced Mains answer)

**MAX 400 WORDS.**"""

        try:
            summary = ask_llm_high_quality(prompt)
            return summary, None
        except Exception as e:
            return None, f"❌ Error: {str(e)[:100]}"
    
    def summarize_url(self, url):
        """
        Complete flow: Fetch URL → Generate Summary with NCERT
        Returns: (title, summary_with_ncert, source, error_message)
        """
        title, content, source, fetch_error = self.fetch_article(url)
        
        if fetch_error:
            return None, None, source, fetch_error
        
        summary, summary_error = self.generate_summary(title, content, source)
        
        if summary_error:
            return title, None, source, summary_error
        
        return title, summary, source, None
    
    def summarize_with_pdf_context(self, url: str, pdf_text: str = ""):
        """
        Fetch URL and generate summary enriched with PDF text context.
        Useful when the user has a related PDF (NCERT chapter, Yojana issue, etc.)
        
        Returns: (title, summary, source, error_message)
        """
        title, content, source, fetch_error = self.fetch_article(url)
        
        if fetch_error:
            return None, None, source, fetch_error
        
        additional_context = ""
        if pdf_text:
            additional_context = f"\n\nRELATED PDF CONTENT (use for deeper analysis):\n{pdf_text[:3000]}"
        
        summary, summary_error = self.generate_summary(
            title, content, source, additional_context=additional_context
        )
        
        if summary_error:
            return title, None, source, summary_error
        
        return title, summary, source, None


def fetch_and_summarize_urls(urls_list):
    """
    Fetch and summarize multiple URLs (teaching resource articles)
    urls_list: list of URLs from coaching institutes
    Returns: list of (url, title, summary_with_ncert, source, error)
    """
    summarizer = URLSummarizer()
    results = []
    
    for idx, url in enumerate(urls_list):
        try:
            # Ensure URL has protocol
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            title, summary, source, error = summarizer.summarize_url(url)
            
            if error:
                results.append((url, None, None, "Unknown", error))
            else:
                results.append((url, title, summary, source, None))
        
        except Exception as e:
            results.append((url, None, None, "Unknown", f"❌ Unexpected error: {str(e)[:100]}"))
        
        # Rate limiting - don't hammer servers
        if idx < len(urls_list) - 1:
            time.sleep(1)
    
    return results
